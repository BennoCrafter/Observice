import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str = "observice",
    log_file: str | Path = "logs/observice_log",
    level: int = logging.INFO,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    log_file = Path(log_file)
    os.makedirs(log_file.parent, exist_ok=True)
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
