from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class CameraConfig:
    width: int = 1280
    height: int = 720
    framerate: int = 30
    rtsp_port: int = 8554
    device: str = ""  # Linux only: v4l2 device path, e.g. /dev/video2. Empty = /dev/video0.


@dataclass
class MotionConfig:
    enabled: bool = True
    check_interval: int = 60  # seconds between frame comparisons
    threshold: float = 25.0  # mean pixel-diff above this counts as "changed"


@dataclass
class DiscordConfig:
    enabled: bool = False
    webhook_url: str = ""
    token: str = ""  # only needed for scripts/download_discord_images.py
    listening_users: list[int] = field(default_factory=list)


@dataclass
class MqttConfig:
    enabled: bool = True
    host: str = "homeassistant.local"
    port: int = 8123
    username: str = ""
    password: str = ""
    base_topic: str = "observice/camera"


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    mqtt: MqttConfig = field(default_factory=MqttConfig)


def _from_dict(data_class, data: dict):
    values = {}
    for f in fields(data_class):
        if f.name not in data:
            continue
        value = data[f.name]
        if hasattr(f.type, "__dataclass_fields__"):
            value = _from_dict(f.type, value)
        values[f.name] = value
    return data_class(**values)


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    return _from_dict(Config, data)


def save_config(config: Config, path: Path) -> None:
    with path.open("w") as fh:
        yaml.safe_dump(asdict(config), fh, sort_keys=False)
