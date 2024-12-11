from typing import Optional

import os
import inspect
from pathlib import Path

import logging
from src.config.models.server_url_config import ServerURLConfig
from src.logger.server_logging_handler import ServerLoggingHandler
from logging.handlers import RotatingFileHandler

from src.config import CONFIG


def setup_logger(logger_name: str | None = None, log_file: str | Path = "logs/observice_log", level: int = logging.INFO, server_url: Optional[ServerURLConfig] = None) -> logging.Logger:
    """
    Sets up a logger to log to a file, console, and send logs to a server.
    """
    if logger_name is None:
        logger_name = inspect.stack()[1].frame.f_globals['__name__']

    if CONFIG.logger.show_logs_in_server:
        server_url = CONFIG.server.url

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Ensure the logger isn't set up multiple times
    if not logger.hasHandlers():
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Create log directory if it doesn't exist
        log_file = Path(log_file)
        if log_file.parent != Path('.'):
            os.makedirs(log_file.parent, exist_ok=True)

        # Rotating file handler
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Server logging handler (if server_url is provided)
        if server_url is not None:
            server_handler = ServerLoggingHandler(server_url)
            server_handler.setLevel(level)
            server_handler.setFormatter(formatter)
            logger.addHandler(server_handler)

    return logger
