import yaml
import os

config_path = "assets/config.yaml"

class ConfigLoader:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"The configuration file '{config_path}' does not exist. Please setup Observice with the setup.sh script.")
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)

    def get(self, key, default=None):
        return self.config.get(key, default)
