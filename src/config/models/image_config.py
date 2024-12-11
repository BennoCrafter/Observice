from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageConfig:
    images_dir: Path
    quality: str
    type: str
