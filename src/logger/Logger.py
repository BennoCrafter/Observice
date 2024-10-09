import logging
from logging.handlers import RotatingFileHandler
import os

from src.utils.response import Response


def setup_logger(logger_name, log_file, level=logging.INFO):
    """Set up a logger with a specific name, log file, and log level."""

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    if not logger.hasHandlers():
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
        handler.setLevel(level)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Define the log format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.addHandler(console_handler)

    return logger
