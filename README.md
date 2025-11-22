# AIMS-PiZARU

AIMS South Africa AI for Science
For the: Machine Learning for Ecology Course

![AIMS-ARU](https://github.com/AIMS-Research/PiZeroARU/assets/15357701/99434d2e-79ae-4299-8e68-74d74b7a2038)

## Getting Started

### Prerequisites

- `uv` package manager (recommended)

### Installation

```bash
uv sync
```

### Running the Application

```bash
# Using uv
uv run main.py
```

## How it Works

- **Session Management**: Each run starts a new `session` with a unique timestamp ID
- **Audio Device Detection**: Automatically detects your audio device (configurable via `config.yaml`)
- **Recording**: Starts recording audio immediately upon device detection

## Configuration

Edit `config.yaml` to customize:

- **Audio settings**: Sample rate, channels, duration, device selection
- **Paths**: Output directories for recordings and logs
- **Logging formats**: Logging and date/time formats

Example:

```yaml
audio:
  rate: 44100
  channels: 1
  duration_sec: 10
  device_match: "default"

paths:
  recordings: "recordings"
  logging: "logs"
```

## Outputs

- **Recordings**: Stored in `./recordings/$YYYY-MM-DD$/$HH$/$timestamp$.wav`
- **Logs**: Persistent logs in `./logs/pizeroaru.log`
