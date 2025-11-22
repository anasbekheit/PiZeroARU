import collections
import logging
import queue
import sys
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

import numpy as np
import pydantic
import sounddevice as sd
import yaml
from numpy.typing import NDArray
from pydantic import BaseModel, Field

# --- Configuration & Types ---
SENTINEL: None = None
DTYPE_MAP: Final[dict[int, str]] = {
    1: "int8",
    2: "int16",
    4: "int32",
}
LOG_FILE: Final[str] = "app.log"


class AudioConfig(BaseModel):
    rate: int = Field(gt=0, description="Sampling rate in Hz")
    channels: int = Field(gt=0, le=2, description="Input channels (1 or 2)")
    duration_sec: int = Field(gt=0, description="Duration per file in seconds")
    sample_width: int = Field(default=2, description="Bytes per sample (1, 2, or 4)")
    max_queue_size: int = Field(default=10, gt=0)
    device_match: str = Field(min_length=1)
    retry_sec: int = Field(default=5, gt=0)


class PathsConfig(BaseModel):
    recordings: Path
    logging: Path


class FormatsConfig(BaseModel):
    log: str
    date: str
    time: str


class AppConfig(BaseModel):
    audio: AudioConfig
    paths: PathsConfig
    formats: FormatsConfig


@dataclass(frozen=False)
class AppState:
    buffer: list[NDArray[np.generic]]
    sample_count: int
    status_flags: collections.deque[str | sd.CallbackFlags]


AudioBuffer = list[NDArray[np.generic]]
QueueItem = AudioBuffer | None


def setup_logging(cfg: AppConfig) -> None:
    """
    Sets up the application's logging.
    """

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.hasHandlers():
        return

    formatter = logging.Formatter(
        cfg.formats.log, datefmt=f"{cfg.formats.date} [{cfg.formats.time}]"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    try:
        cfg.paths.logging.mkdir(parents=True, exist_ok=True)
        log_filepath = cfg.paths.logging / LOG_FILE

        file_handler = logging.FileHandler(log_filepath)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    except Exception as e:
        print(f"ERROR: Failed to set up logging FileHandler: {e}", file=sys.stderr)
        print("Application will continue logging to the console only.")


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config missing: {path.absolute()}")

    with open(path) as f:
        try:
            raw_data = yaml.safe_load(f)
            return AppConfig(**raw_data)
        except (yaml.YAMLError, pydantic.ValidationError) as e:
            raise ValueError(f"Configuration Invalid: {e}") from e


def disk_writer(q: queue.Queue[QueueItem], cfg: AppConfig) -> None:
    logger = logging.getLogger("Writer")

    while True:
        buffer = q.get()
        if buffer is SENTINEL:
            q.task_done()
            break

        try:
            data = np.concatenate(buffer)
            timestamp = datetime.now()

            # Recordings/YYYY-MM-DD/HH_MM_SS.wav
            folder = cfg.paths.recordings / timestamp.strftime(cfg.formats.date)
            folder.mkdir(parents=True, exist_ok=True)

            filepath = folder / f"{timestamp.strftime(cfg.formats.time)}.wav"

            with wave.open(str(filepath), "wb") as wf:
                wf.setnchannels(cfg.audio.channels)
                wf.setsampwidth(cfg.audio.sample_width)
                wf.setframerate(cfg.audio.rate)
                wf.writeframes(data.tobytes())

            logger.info(f"Saved: {filepath.name}")

        except Exception:
            logger.exception("Write failed")
        finally:
            q.task_done()


def find_device(keyword: str) -> int:
    """Returns device index or -1 if not found."""
    try:
        for idx, device in enumerate(sd.query_devices()):
            if keyword in device["name"] and device["max_input_channels"] > 0:
                return idx
    except Exception:
        pass
    return -1


def run_supervisor(cfg: AppConfig) -> None:
    setup_logging(cfg)
    logger = logging.getLogger("Supervisor")

    data_queue: queue.Queue[QueueItem] = queue.Queue(maxsize=cfg.audio.max_queue_size)

    writer = threading.Thread(target=disk_writer, args=(data_queue, cfg), daemon=True)
    writer.start()

    samples_per_file: Final[int] = cfg.audio.rate * cfg.audio.duration_sec
    dtype: Final[str] = DTYPE_MAP[cfg.audio.sample_width]

    state: AppState = AppState(buffer=[], sample_count=0, status_flags=collections.deque())

    def recording_callback(
        indata: NDArray[np.generic], frames: int, _time: int, status: sd.CallbackFlags
    ) -> None:
        if status:
            state.status_flags.append(status)

        state.buffer.append(indata.copy())
        state.sample_count += frames

        if state.sample_count >= samples_per_file:
            try:
                data_queue.put_nowait(list(state.buffer))
            except queue.Full:
                state.status_flags.append("Queue Full")
            finally:
                state.buffer.clear()
                state.sample_count = 0

    while True:
        try:
            idx = find_device(cfg.audio.device_match)
            if idx == -1:
                logger.warning(
                    f"Device '{cfg.audio.device_match} not found.\
                         Retrying in {cfg.audio.retry_sec}s"
                )
                time.sleep(cfg.audio.retry_sec)
                continue

            logger.info(f"Starting capture on device {idx}")

            with sd.InputStream(
                device=idx,
                channels=cfg.audio.channels,
                samplerate=cfg.audio.rate,
                dtype=dtype,
                callback=recording_callback,
            ) as stream:
                while True:
                    if not stream.active:
                        raise OSError("Stream became inactive. Device likely detached.")

                    while state.status_flags:
                        flag = state.status_flags.pop()
                        logger.warning(f"Audio Status Warning: {flag}")

                    time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt signal (Ctrl+C) detected: Stopping")
            data_queue.put(SENTINEL)
            writer.join()
            break
        except Exception as e:
            logger.error(f"Stream error: {e}. Restarting")
            time.sleep(cfg.audio.retry_sec)


if __name__ == "__main__":
    config = load_config(Path(__file__).parent / "config.yaml")
    run_supervisor(config)
