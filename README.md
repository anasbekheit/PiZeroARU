# AIMS-PiZARU

AIMS South Africa AI for Science
For the: Machine Learning for Ecology Course

![AIMS-ARU](https://github.com/AIMS-Research/PiZeroARU/assets/15357701/99434d2e-79ae-4299-8e68-74d74b7a2038)


## Getting Started
- Prerequisites: Ensure you have Python 3 and PyAudio installed
- Download: Clone or download this repository
- Run: Open a terminal in the project directory and execute: `python ARU.py`

## How it Works
- Upon starting the script for the first time a new `session` is started with an id `timestamp`
- Device: The program automatically detects your `USB Audio Device`
- The program starts recording after detecting your `USB Audio Device`
- `config.json`: Specify recording duration and other configuration

## Outputs
- The output directory is `Recordings`
- The program outputs a `./logs/recordings-$session$.logs` file for each session
- The program outputs `./$YYYY-HH-DD$/$HH$/$timestamp$.wav` files for each recordings
