from dataclasses import dataclass


@dataclass
class ChangeDetectorConfig:
    refresh_rate: int
