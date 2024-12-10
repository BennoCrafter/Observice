from dataclasses import dataclass
from src.config.models.server_config import ServerConfig
from src.config.models.image_config import ImageConfig
from src.config.models.discord_config import DiscordConfig

@dataclass
class Config:
    server_config: ServerConfig
    image_config: ImageConfig
    discord_config: DiscordConfig
