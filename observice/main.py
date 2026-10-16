import asyncio
import logging
import signal
import socket
import tempfile
import threading
from pathlib import Path

import cv2
from gi.repository import GLib

from observice.capture import RTSPServer
from observice.config import load_config
from observice.discord_notify import send_image
from observice.logger import setup_logger
from observice.motion import run_motion_loop
from observice.mqtt_bridge import MqttBridge

CONFIG_PATH = Path("assets/config.yaml")

logger = setup_logger()


def lan_ip() -> str:
    # UDP connect sends nothing; it just makes the OS pick the outbound interface
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return socket.gethostname()


async def main() -> None:
    print(Path("assets/ascii_name.txt").read_text())
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    config = load_config(CONFIG_PATH)

    rtsp = RTSPServer(config.camera)
    glib_loop = GLib.MainLoop()
    threading.Thread(target=glib_loop.run, daemon=True).start()
    logger.info("RTSP stream ready at rtsp://%s:%s/cam", lan_ip(), rtsp.port)

    bridge = MqttBridge(config, CONFIG_PATH) if config.mqtt.enabled else None
    if bridge:
        bridge.connect()

    async def on_motion(frame):
        if bridge:
            bridge.publish_motion(True)
        if config.discord.enabled and config.discord.webhook_url:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            cv2.imwrite(str(tmp_path), frame)
            send_image(config.discord.webhook_url, tmp_path, config.discord.listening_users)
            tmp_path.unlink(missing_ok=True)

    stream_url = f"rtsp://127.0.0.1:{config.camera.rtsp_port}/cam"
    try:
        await run_motion_loop(stream_url, config.motion, on_motion)
    finally:
        if bridge:
            bridge.close()
        glib_loop.quit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Observice stopped")
