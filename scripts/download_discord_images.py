#!/usr/bin/env python3
"""Download every image attachment posted in a Discord channel.

Usage:
    python scripts/download_discord_images.py --channel-id 123456789 --out ./downloads
"""
import argparse
from pathlib import Path

import requests
import yaml

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
DEFAULT_CONFIG_PATH = Path("assets/config.yaml")


def iter_messages(channel_id: str, token: str):
    headers = {"Authorization": f"Bot {token}"}
    before = None
    while True:
        params = {"limit": 100}
        if before:
            params["before"] = before
        response = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        messages = response.json()
        if not messages:
            return
        yield from messages
        before = messages[-1]["id"]


def download_images(channel_id: str, token: str, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for message in iter_messages(channel_id, token):
        for attachment in message.get("attachments", []):
            filename = attachment["filename"]
            if not filename.lower().endswith(IMAGE_EXTENSIONS):
                continue
            dest = out_dir / f"{message['id']}_{filename}"
            response = requests.get(attachment["url"], timeout=30)
            response.raise_for_status()
            dest.write_bytes(response.content)
            count += 1
    return count


def _default_token(config_path: Path) -> str:
    if not config_path.exists():
        return ""
    data = yaml.safe_load(config_path.read_text()) or {}
    return data.get("discord", {}).get("token", "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel-id", required=True, help="Discord channel ID to scan")
    parser.add_argument("--out", type=Path, required=True, help="Folder to save images into")
    parser.add_argument(
        "--token",
        default=None,
        help=f"Discord bot token (defaults to discord.token in {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()

    token = args.token or _default_token(DEFAULT_CONFIG_PATH)
    if not token:
        parser.error(f"No bot token given (use --token or set discord.token in {DEFAULT_CONFIG_PATH})")

    count = download_images(args.channel_id, token, args.out)
    print(f"Downloaded {count} image(s) to {args.out}")


if __name__ == "__main__":
    main()
