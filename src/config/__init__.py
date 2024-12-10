from src.config.config_loader import load_config
from src.config.models.config import Config
from pathlib import Path

config_path = Path("assets/config.yaml")
CONFIG: Config = load_config(config_path)