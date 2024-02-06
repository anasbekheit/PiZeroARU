import contextlib
import datetime
import json
import logging
import os
import threading
import time
import traceback
import wave
from operator import itemgetter
from queue import Queue

import pyaudio

from utils import FolderStructure

RETRY_SECONDS = 5
py_audio: pyaudio.PyAudio = None


def init_pyaudio():
    global py_audio
    if py_audio is None:
        py_audio = pyaudio.PyAudio()
    else:
        py_audio.terminate()  # Refresh PyAudio if already initialized
        py_audio = pyaudio.PyAudio()
    return py_audio


@contextlib.contextmanager
def pyaudio_context_manager():
    p = init_pyaudio()  # Initialize PyAudio
    try:
        yield p  # Yield the PyAudio object for use within the context
    finally:
        p.terminate()  # Ensure PyAudio is terminated properly


def determine_usb_index(p):
    index_to_use = -1
    for i in range(p.get_device_count()):
        device_name = str(p.get_device_info_by_index(i).get('name'))
        if 'USB Audio Device' in device_name:
            index_to_use = i
            break
    return index_to_use


def retry_until_device_found(p, logger=logging):
    """Retries finding the USB audio device until it's available."""
    logger.info("Searching for USB audio device...")
    init_pyaudio()
    dev_index = determine_usb_index(p)

    if dev_index == -1:
        logger.error("No USB audio device found")
        logger.info(f"Retrying to connect to a microphone every {RETRY_SECONDS} seconds...")

    while dev_index == -1:
        time.sleep(RETRY_SECONDS)  # Wait before retrying
        init_pyaudio()
        dev_index = determine_usb_index(p)

    device_name = p.get_device_info_by_index(dev_index).get("name")
    logger.info(f"Found {device_name} as input device.")
    return dev_index


def create_folder_structure_and_save_text_file(format, channels, rate, frames, p):
    logger = logging.getLogger('create')
    logger.debug("Entering function create_folder_structure_and_save_text_file")

    try:
        with FolderStructure(format, channels, rate, p) as hour_folder:
            wavefile_path = os.path.join(hour_folder, timestamp() + ".wav")
            logger.info("Writing audio data to WAV file: %s (channels: %s, rate: %s Hz)",
                        wavefile_path, channels, rate)

            with wave.open(wavefile_path, "wb") as wavefile:
                wavefile.setnchannels(channels)
                wavefile.setsampwidth(p.get_sample_size(format))
                wavefile.setframerate(rate)
                wavefile.writeframes(b"".join(frames))
                logger.debug("WAV file written successfully")

    except Exception as e:
        logger.exception("Error writing WAV file or creating folders: %s. Skipping current file.", e)

    logger.debug("Exiting function create_folder_structure_and_save_text_file")


def record_audio(p, format, channels, rate, chunk, duration, dev_index, queue: Queue, lock):
    logger = logging.getLogger('record')
    with contextlib.closing(p.open(format=format,
                                   channels=channels,
                                   rate=rate,
                                   input=True,
                                   frames_per_buffer=chunk,
                                   input_device_index=dev_index)) as stream:
        counter = 0
        wav_size = int((rate / chunk) * duration)
        while True:
            try:
                with lock:
                    frames = [None] * wav_size
                    for i in range(wav_size):
                        logger.debug("Reading audio chunk %s", i + 1)
                        data = stream.read(chunk)
                        frames[i] = data
                        logger.debug("Audio chunk %s read successfully", i + 1)
                    queue.put(frames)
                logger.info(f"Finished recording file number: {counter}")
                counter += 1

            except (IOError, OSError) as e:
                logger.error("Microphone disconnected: %s", e)
                logger.info("Closing current input stream")
                stream.close()

                logger.info("Refreshing pyAudio")
                dev_index = retry_until_device_found(p, logger=logger)
                stream = p.open(format=format,
                                channels=channels,
                                rate=rate,
                                input=True,
                                frames_per_buffer=chunk,
                                input_device_index=dev_index)
            except Exception as e:
                logger.exception("Unexpected error during recording: %s", e)
                raise e


def timestamp():
    current_datetime = datetime.datetime.now()

    return '{:04d}-{:02d}-{:02d}_{:02d}-{:02d}-{:02d}'.format(
        current_datetime.year, current_datetime.month, current_datetime.day,
        current_datetime.hour, current_datetime.minute, current_datetime.second
    )


def read_config(filename='config.json'):
    with open(filename, 'r') as config_file:
        config = json.load(config_file)
    return config


def initialize_logger(config):
    log_config = config['logging_settings']
    log_file, log_path, level, extension = itemgetter('log_file', 'log_path', 'level', 'extension')(log_config)

    if not os.path.exists(log_path):
        os.makedirs(log_path)

    recording_filepath = f'{log_path}/{log_file}-{timestamp()}.{extension}'

    # Create loggers with names indicating their purpose
    logger_record = logging.getLogger('record')
    logger_create_file = logging.getLogger('create')
    logger_thread = logging.getLogger('thread')

    # Configure formatter and file handler
    formatter = logging.Formatter('[%(asctime)s] %(name)-14s - %(levelname)-8s %(message)s')
    file_handler = logging.FileHandler(recording_filepath)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Add the file handler to each logger
    logging.getLogger().addHandler(file_handler)

    # Set logging levels for each logger (can be different if needed)
    logging.getLogger().setLevel(level)
    logger_record.setLevel(level)
    logger_thread.setLevel(level)
    logger_create_file.setLevel(level)

def get_record_settings(config):
    record_config = config['recording_settings']
    return itemgetter('format', 'channels', 'rate', 'chunk', 'duration')(record_config)


def write_files(queue, p, format, channels, rate):
    logger = logging.getLogger('thread')
    while True:
        frames = queue.get()
        logger.debug(f"writer thread unblocked")
        create_folder_structure_and_save_text_file(format, channels, rate, frames, p)
        queue.task_done()  # Signal completion to the queue


if __name__ == "__main__":
    config = read_config()
    initialize_logger(config)
    format, channels, rate, chunk, duration = get_record_settings(config)

    with pyaudio_context_manager() as p:
        dev_index = retry_until_device_found(p, logger=logging)

        logging.info(
            f"recording parameters: format={format}, channels={channels}, rate={rate}, chunk={chunk}, duration={duration}, dev_index={dev_index}"
        )

        queue = Queue()  # Create the shared queue
        lock = threading.Lock()  # Create a lock for thread synchronization

        # Start the threads directly
        record_thread = threading.Thread(
            target=record_audio,
            args=(p, format, channels, rate, chunk, duration, dev_index, queue, lock),
        )
        writer_thread = threading.Thread(
            target=write_files, args=(queue, p, format, channels, rate)
        )

        record_thread.start()
        writer_thread.start()

        try:
            # Wait for threads to finish
            queue.join()  # Wait for all items in the queue to be processed
            record_thread.join()  # Wait for the recording thread to finish
            writer_thread.join()  # Wait for the writer thread to finish

        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt Stopping recording...")
            queue.join()
            record_thread.join()
            writer_thread.join()

        except Exception as e:
            logging.critical("Recording failed: %s", traceback.format_exc())
            with lock:  # Acquire lock for graceful termination
                queue.join()  # Wait for queue to be processed
                record_thread.join()  # Wait for recording thread to finish
                writer_thread.join()  # Wait for writer thread to finish
