import os
import platform
import signal
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from gi.repository import GLib

from observice.capture import Camera, camera_device
from observice.config import Config, load_config
from observice.discord_notify import send_image
from observice.logger import setup_logger
from observice.motion import EventTracker, changed_percent
from observice.mqtt_bridge import MqttBridge
from observice.recordings import RECORDINGS_DIR, list_events, new_event_id, prune, write_event
from observice.watchdog import watch_device

CONFIG_PATH = Path("assets/config.yaml")
STALL_SECONDS = 15  # no detection frame for this long = camera stalled

logger = setup_logger()


def lan_ip() -> str:
    # UDP connect sends nothing; it just makes the OS pick the outbound interface
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return socket.gethostname()


def close_unfinished_events(directory: Path) -> None:
    # A crash or restart mid-event leaves end=None; without this it would show as "live" forever.
    for event in list_events(directory, limit=5):
        if event["end"] is None:
            event["end"] = datetime.fromtimestamp((directory / f"{event['id']}.json").stat().st_mtime).isoformat()
            write_event(directory, event)


class ChangeEvents:
    """Turns detection frames into events: snapshot, clip, MQTT motion state and a Discord post."""

    def __init__(self, config: Config, bridge: MqttBridge | None):
        self.config = config
        self.bridge = bridge
        self.camera: Camera | None = None
        self.tracker = EventTracker(config.motion.quiet_seconds, config.recording.max_clip_seconds)
        self.prev_frame = None
        self.event: dict | None = None
        self.last_frame_at = time.monotonic()

    def on_frame(self, frame) -> None:
        self.last_frame_at = time.monotonic()
        prev, self.prev_frame = self.prev_frame, frame
        if prev is None or not self.config.motion.enabled:
            return
        percent = changed_percent(prev, frame, self.config.motion.ignore_border_percent)
        action = self.tracker.update(time.monotonic(), percent >= self.config.motion.min_area_percent)
        if action == "start":
            self._start(percent)
        elif self.event and percent > self.event["peak_percent"]:
            self.event["peak_percent"] = round(percent, 1)
            self._save_snapshot()  # keep the most-changed frame as the thumbnail
        if action == "end":
            self._end()

    def _start(self, percent: float) -> None:
        now = datetime.now()
        event_id = new_event_id(RECORDINGS_DIR, now)
        self.event = {"id": event_id, "start": now.isoformat(timespec="seconds"), "end": None,
                      "duration": None, "peak_percent": round(percent, 1), "has_clip": False}
        snapshot = self._save_snapshot()
        write_event(RECORDINGS_DIR, self.event)
        if self.config.recording.enabled:
            self.camera.recorder.start(RECORDINGS_DIR / event_id)
        logger.info("Change detected (%.1f%% of the picture)", percent)
        if self.bridge:
            self.bridge.publish_motion(True)
        discord = self.config.discord
        if discord.enabled and discord.webhook_url and snapshot:
            threading.Thread(target=send_image, args=(discord.webhook_url, snapshot, discord.listening_users), daemon=True).start()

    def _save_snapshot(self) -> Path | None:
        jpeg = self.camera.latest_jpeg
        if jpeg is None:
            return None
        path = RECORDINGS_DIR / f"{self.event['id']}.jpg"
        path.write_bytes(jpeg)
        return path

    def _close(self) -> tuple[dict, datetime]:
        event, self.event = self.event, None
        end = datetime.now()
        event["end"] = end.isoformat(timespec="seconds")
        event["duration"] = round((end - datetime.fromisoformat(event["start"])).total_seconds())
        return event, end

    def _end(self) -> None:
        event, end = self._close()
        if self.bridge:
            self.bridge.publish_motion(False)
        logger.info("Change ended after %ss", event["duration"])

        finish_clip = self.camera.recorder.stop()

        def finish() -> None:  # writing the MP4 blocks; keep it off the camera's streaming thread
            event["has_clip"] = finish_clip()
            write_event(RECORDINGS_DIR, event)
            prune(RECORDINGS_DIR, self.config.recording.keep_days, end)

        threading.Thread(target=finish, daemon=True).start()

    def finish_now(self) -> None:
        """On shutdown: close the open event and clip so neither is left half-written."""
        if self.event:
            event, _ = self._close()
            event["has_clip"] = self.camera.recorder.stop()()
            write_event(RECORDINGS_DIR, event)


def main() -> None:
    print(Path("assets/ascii_name.txt").read_text())
    config = load_config(CONFIG_PATH)
    RECORDINGS_DIR.mkdir(exist_ok=True)
    close_unfinished_events(RECORDINGS_DIR)
    prune(RECORDINGS_DIR, config.recording.keep_days, datetime.now())

    bridge = MqttBridge(config, CONFIG_PATH) if config.mqtt.enabled else None
    if bridge:
        bridge.connect()

    events = ChangeEvents(config, bridge)
    camera = Camera(config.camera, config.recording.pre_roll_seconds, events.on_frame)
    events.camera = camera
    loop = GLib.MainLoop()
    exit_code = 0

    def fail(message: str) -> None:
        nonlocal exit_code
        logger.error("%s, exiting so systemd restarts the service", message)
        exit_code = 1
        loop.quit()

    def on_bus_error(bus, msg) -> None:
        fail(f"Camera pipeline error: {msg.parse_error()[0].message}")

    def check_stalled() -> bool:
        if time.monotonic() - events.last_frame_at > STALL_SECONDS:
            fail("Camera stream stalled")
        return True

    bus = camera.pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message::error", on_bus_error)
    GLib.timeout_add_seconds(5, check_stalled)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, loop.quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, loop.quit)

    if platform.system() == "Linux":
        device = camera_device(config.camera)

        def camera_lost() -> None:
            logger.error("Camera %s disconnected (USB reset?), exiting so systemd restarts the service", device)
            os._exit(1)  # GStreamer may hang on the dead device; a clean shutdown could too

        threading.Thread(target=watch_device, args=(device, camera_lost), daemon=True).start()

    camera.start()
    logger.info("RTSP stream ready at rtsp://%s:%s/cam", lan_ip(), config.camera.rtsp_port)
    try:
        loop.run()
    finally:
        events.finish_now()
        camera.stop()
        if bridge:
            bridge.close()
        logger.info("Observice stopped")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
