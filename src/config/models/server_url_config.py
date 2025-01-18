from dataclasses import dataclass

@dataclass
class ServerURLConfig:
    base: str
    logs_api_endpoint: str
    logs_endpoint: str
