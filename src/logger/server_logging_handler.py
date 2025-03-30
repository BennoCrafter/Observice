import requests
import logging
from src.config.models.server_url_config import ServerURLConfig
from src.utils.is_url_reachable import is_url_reachable
from src.utils.response import Response


class ServerLoggingHandler(logging.Handler):
    """
    Custom logging handler to send log records to a server.
    """

    def __init__(self, server_url: ServerURLConfig):
        super().__init__()
        self.server_url = server_url
        self.is_reachable: Response = is_url_reachable(server_url.base)

    def emit(self, record):
        if not self.is_reachable.is_success():
            print(
                f"Server URL is unreachable: {self.server_url} {self.is_reachable.message}"
            )
            # logger.error(f"Server URL is unreachable: {self.server_url}")
            return
        try:
            data = {
                "timestamp": record.created,
                "name": record.name,
                "level": record.levelname,
                "message": record.msg,
                "file": record.pathname,
                "line": record.lineno,
            }
            headers = {"Content-Type": "application/json"}

            response = requests.post(
                f"{self.server_url.base}{self.server_url.logs_api_endpoint}",
                json=data,
                headers=headers,
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send log to server: {e}")
