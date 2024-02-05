import datetime
import logging
import os


class FolderStructure:
    def __init__(self, format, channels, rate, p):
        self.format = format
        self.channels = channels
        self.rate = rate
        self.p = p
        self.logger = logging.getLogger('create')

    def __enter__(self):
        try:
            now = datetime.datetime.now()
            day_folder = os.path.join("Recordings", now.strftime("%Y-%m-%d"))
            hour_folder = os.path.join(day_folder, now.strftime("%H"))

            if not os.path.exists(day_folder):
                os.makedirs(day_folder)
                self.logger.info(f"Day folder created: {day_folder}")

            if not os.path.exists(hour_folder):
                os.makedirs(hour_folder)
                self.logger.info("Hour folder created: %s", hour_folder)

            return hour_folder

        except Exception as e:
            self.logger.exception("Error creating folders: %s", e)
            raise e  # Re-raise the exception to propagate it

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.exception("Error creating folders: %s. Skipping current file.", exc_val)
