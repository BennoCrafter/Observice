from dataclasses import MISSING, asdict, dataclass, field, fields
from pathlib import Path

import yaml


def setting(default, label: str, help: str = "", **meta):
    """A config field plus what the panel needs to render and validate it.

    meta: unit, min, max, options (allowed values), secret (masked input), placeholder.
    Adding a field here is all it takes for it to show up in the panel.
    """
    meta = {"label": label, "help": help, **meta}
    if isinstance(default, list):
        return field(default_factory=lambda: list(default), metadata=meta)
    return field(default=default, metadata=meta)


@dataclass
class CameraConfig:
    width: int = setting(1280, "Width", "Stream width in pixels.", unit="px", min=160, max=3840)
    height: int = setting(720, "Height", "Stream height in pixels.", unit="px", min=120, max=2160)
    framerate: int = setting(30, "Frame rate", unit="fps", min=1, max=60)
    rtsp_port: int = setting(8554, "RTSP port", "Home Assistant reads rtsp://<host>:<port>/cam.", min=1, max=65535)
    device: str = setting("", "Device", "Linux only: v4l2 device path. Empty = /dev/video0.", placeholder="/dev/video0")
    rotation: int = setting(0, "Rotation", "For cameras mounted sideways or upside down. Costs CPU on a Pi 3.",
                            unit="°", options=[0, 90, 180, 270])
    mirror: bool = setting(False, "Mirror", "Flip the picture horizontally.")


@dataclass
class MotionConfig:
    enabled: bool = setting(True, "Detect changes")
    min_area_percent: float = setting(1.0, "Sensitivity", "Share of the picture that must change to start an event. Lower = more sensitive.",
                                      unit="%", min=0.1, max=100)
    quiet_seconds: int = setting(10, "Cooldown", "Seconds without change before an event ends.", unit="s", min=1, max=600)
    ignore_border_percent: float = setting(0.0, "Ignore border", "Ignore this much of each edge, e.g. a timestamp overlay or trees.",
                                           unit="%", min=0, max=40)


@dataclass
class RecordingConfig:
    enabled: bool = setting(True, "Record clips", "Off = snapshots only.")
    pre_roll_seconds: int = setting(5, "Pre-roll", "Seconds before the change included in each clip.", unit="s", min=0, max=30)
    max_clip_seconds: int = setting(60, "Max clip length", unit="s", min=5, max=600)
    keep_days: int = setting(7, "Keep for", "Older snapshots and clips are deleted.", unit="days", min=1, max=365)


@dataclass
class DiscordConfig:
    enabled: bool = setting(False, "Send to Discord", "Posts one snapshot per change.")
    webhook_url: str = setting("", "Webhook URL", "Channel settings → Integrations → Webhooks.", secret=True,
                               placeholder="https://discord.com/api/webhooks/…")
    token: str = setting("", "Bot token", "Only used by scripts/download_discord_images.py.", secret=True)
    listening_users: list[int] = setting([], "Mention users", "Discord user IDs to @-mention, comma-separated.")


@dataclass
class MqttConfig:
    enabled: bool = setting(True, "Home Assistant (MQTT)")
    host: str = setting("homeassistant.local", "Broker host")
    port: int = setting(1883, "Broker port", min=1, max=65535)
    username: str = setting("", "Username")
    password: str = setting("", "Password", secret=True)
    base_topic: str = setting("observice/camera", "Base topic", "Also names the HA device; make it unique per camera, e.g. observice/frontdoor.")


@dataclass
class PanelConfig:
    port: int = setting(80, "Port", "Panel address: http://<host>:<port>.", min=1, max=65535)
    password: str = setting("", "Password", "Login for this panel (any username). Empty = no login.", secret=True)
    preview_width: int = setting(640, "Preview width", "Live preview here and snapshots. Smaller loads faster over a weak Wi-Fi; clips keep full size.",
                                 unit="px", min=320, max=1920)
    preview_fps: int = setting(5, "Preview frame rate", "Live preview here only; Home Assistant gets the full stream.", unit="fps", min=1, max=15)
    preview_quality: int = setting(70, "Preview quality", "JPEG quality of the live preview.", unit="%", min=10, max=100)


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig, metadata={
        "label": "Camera", "help": "The USB camera and the RTSP stream Home Assistant watches."})
    motion: MotionConfig = field(default_factory=MotionConfig, metadata={
        "label": "Change detection", "help": "When a change starts and ends."})
    recording: RecordingConfig = field(default_factory=RecordingConfig, metadata={
        "label": "Recordings", "help": "Snapshots and clips of each change, listed under Changes."})
    discord: DiscordConfig = field(default_factory=DiscordConfig, metadata={
        "label": "Discord", "help": "Post a snapshot to a Discord channel when something changes."})
    mqtt: MqttConfig = field(default_factory=MqttConfig, metadata={
        "label": "Home Assistant", "help": "Motion sensor and switches in Home Assistant via MQTT."})
    panel: PanelConfig = field(default_factory=PanelConfig, metadata={
        "label": "Panel", "help": "This web panel."})


def schema() -> list[dict]:
    """Sections and fields with their metadata, in declaration order, for the panel's config form."""
    sections = []
    for section in fields(Config):
        items = []
        for f in fields(section.type):
            default = f.default_factory() if f.default is MISSING else f.default
            items.append({"key": f.name, "type": type(default).__name__, "default": default, **f.metadata})
        sections.append({"key": section.name, **section.metadata, "fields": items})
    return sections


def _from_dict(data_class, data: dict):
    # Unknown keys (e.g. fields removed in an update) are ignored, so old config files keep loading.
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
