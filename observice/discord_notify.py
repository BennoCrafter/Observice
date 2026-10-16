import logging
from pathlib import Path

import requests

logger = logging.getLogger("observice")


def _format_mentions(user_ids: list[int]) -> str:
    return " ".join(f"<@{uid}>" for uid in user_ids)


def send_image(webhook_url: str, image_path: Path, listening_users: list[int] | None = None) -> bool:
    if not webhook_url.startswith("http"):
        logger.error("Invalid Discord webhook URL: %s", webhook_url)
        return False

    try:
        with image_path.open("rb") as fh:
            files = {"file": (image_path.name, fh, "image/jpeg")}
            data = {"content": _format_mentions(listening_users or [])}
            response = requests.post(webhook_url, files=files, data=data, timeout=10)
    except requests.exceptions.RequestException as e:
        logger.error("Error sending image to Discord: %s", e)
        return False

    if response.status_code != 200:
        logger.error("Discord webhook returned status %s", response.status_code)
        return False

    logger.info("Sent image to Discord")
    return True
