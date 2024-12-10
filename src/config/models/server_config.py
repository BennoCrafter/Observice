from dataclasses import dataclass


@dataclass
class ServerConfig:
    port: int
    url: str
