from dataclasses import dataclass


@dataclass
class DiscordConfig:
    token: str
    webhook_url: str
    receiver_channel_id: int
    destination_channel_id: int
    listening_users: list[int]
