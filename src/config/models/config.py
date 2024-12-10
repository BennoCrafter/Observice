from dataclasses import dataclass
from src.config.models.server_config import ServerConfig
from src.config.models.image_config import ImageConfig
from src.config.models.discord_config import DiscordConfig
from src.config.models.logger_config import LoggerConfig
from src.config.models.image_receiver_config import ImageReceiverConfig
from src.config.models.change_detector_config import ChangeDetectorConfig

@dataclass
class Config:
    server: ServerConfig
    image: ImageConfig
    discord: DiscordConfig
    logger: LoggerConfig
    image_receiver: ImageReceiverConfig
    change_detector: ChangeDetectorConfig
