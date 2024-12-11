from dataclasses import dataclass
from src.config.models.server_url_config import ServerURLConfig


@dataclass
class ServerConfig:
    url: ServerURLConfig
