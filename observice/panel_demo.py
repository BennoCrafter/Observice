"""`python -m observice.panel --demo`: the real panel with a simulated camera, logs and change events.

For working on the panel on any machine: no camera, GStreamer, systemd or Pi needed. Uses a scratch
directory in the system temp dir; sample clips are rendered once with OpenCV + ffmpeg (skipped if
ffmpeg is missing, events then only have snapshots).
"""
import logging
import math
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from observice.config import Config, PanelConfig, save_config
from observice.recordings import close_unfinished_events, new_event_id, write_event

DEMO_DIR = Path(tempfile.gettempdir()) / "observice-demo"
PORT = 8080
SIZE = (1280, 720)
CLIP_SIZE = (640, 360)
CLIP_FPS = 15

logger = logging.getLogger("observice")
visit_started: float | None = None  # set while the simulated change is happening; the live feed shows the visitor
VISIT_SECONDS = 12


def scene(t: float, size=SIZE, visitor: float | None = None) -> np.ndarray:
    """A fake hallway: wall, floor, door, a lamp that flickers; visitor = 0..1 walks someone across."""
    w, h = size
    img = np.empty((h, w, 3), np.uint8)
    img[:] = (196, 205, 214)
    img[int(h * 0.68):] = (132, 150, 168)
    door = (int(w * 0.62), int(h * 0.2), int(w * 0.78), int(h * 0.68))
    cv2.rectangle(img, door[:2], door[2:], (88, 104, 128), -1)
    cv2.circle(img, (door[0] + int(w * 0.02), int(h * 0.45)), max(3, w // 200), (40, 190, 220), -1)
    glow = 150 + int(30 * math.sin(t * 2))
    cv2.circle(img, (int(w * 0.2), int(h * 0.18)), w // 22, (glow, glow + 40, 255), -1)
    if visitor is not None:
        x = int((visitor * 1.2 - 0.1) * w)
        cv2.ellipse(img, (x, int(h * 0.52)), (w // 32, h // 6), 0, 0, 360, (70, 60, 52), -1)
        cv2.circle(img, (x, int(h * 0.3)), w // 45, (150, 170, 205), -1)
    cv2.putText(img, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (int(w * 0.02), int(h * 0.95)),
                cv2.FONT_HERSHEY_SIMPLEX, w / 1600, (255, 255, 255), max(1, w // 640), cv2.LINE_AA)
    return img


def _render_clip(path: Path, seconds: float) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    w, h = CLIP_SIZE
    proc = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
         "-r", str(CLIP_FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
        stdin=subprocess.PIPE,
    )
    frames = int(seconds * CLIP_FPS)
    for i in range(frames):
        proc.stdin.write(scene(i / CLIP_FPS, CLIP_SIZE, visitor=i / frames).tobytes())
    proc.stdin.close()
    return proc.wait() == 0


def _seed_events(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.glob("*.json")):
        return
    now = datetime.now()
    for minutes_ago, duration, peak in [(4, 14, 6.2), (38, 22, 12.8), (95, 11, 2.1), (240, 41, 18.5),
                                        (410, 9, 1.4), (900, 27, 7.7), (1500, 16, 3.3), (2900, 60, 24.0)]:
        start = now - timedelta(minutes=minutes_ago)
        event_id = new_event_id(directory, start)
        cv2.imwrite(str(directory / f"{event_id}.jpg"), scene(minutes_ago, CLIP_SIZE, visitor=0.5))
        has_clip = _render_clip(directory / f"{event_id}.mp4", min(duration, 8))
        write_event(directory, {"id": event_id, "start": start.isoformat(timespec="seconds"),
                                "end": (start + timedelta(seconds=duration)).isoformat(timespec="seconds"),
                                "duration": duration, "peak_percent": peak, "has_clip": has_clip})


def _simulate(directory: Path) -> None:
    """Every ~40 s someone walks through: a change starts (in progress), lasts 12 s, then gets its clip."""
    global visit_started
    sample_clip = next(directory.glob("*.mp4"), None)
    while True:
        time.sleep(25)
        visit_started = time.time()
        start = datetime.now()
        event = {"id": new_event_id(directory, start), "start": start.isoformat(timespec="seconds"), "end": None,
                 "duration": None, "peak_percent": 4.6, "has_clip": False}
        cv2.imwrite(str(directory / f"{event['id']}.jpg"), scene(time.time(), CLIP_SIZE, visitor=0.5))
        write_event(directory, event)
        logger.info("Change detected (%.1f%% of the picture)", 4.6)
        time.sleep(VISIT_SECONDS)
        visit_started = None
        if sample_clip:
            shutil.copy(sample_clip, directory / f"{event['id']}.mp4")
        event.update(end=datetime.now().isoformat(timespec="seconds"), duration=12, has_clip=bool(sample_clip))
        write_event(directory, event)
        logger.info("Change ended after 12s")
        time.sleep(3)
        if int(time.time()) % 2:
            logger.warning("MQTT broker homeassistant.local:1883 unreachable, retrying")


def _seed_log(path: Path) -> None:
    now = datetime.now()
    lines = [
        (3600, "INFO", "RTSP stream ready at rtsp://192.168.178.129:8554/cam"),
        (3590, "WARNING", "MQTT broker homeassistant.local:1883 unreachable, retrying"),
        (3500, "INFO", "Connected to MQTT broker at homeassistant.local:1883"),
        (2400, "INFO", "Change detected (12.8% of the picture)"),
        (2378, "INFO", "Change ended after 22s"),
        (1800, "INFO", "Config updated from Home Assistant: quiet_seconds = 15"),
        (1200, "ERROR", "Discord webhook returned status 429"),
        (600, "ERROR", "Could not write clip 20261128-153301: timeout\nTraceback (most recent call last):\n"
                       '  File "observice/capture.py", line 171, in finish\n    part.replace(path.with_suffix(".mp4"))\n'
                       "OSError: [Errno 28] No space left on device"),
        (240, "INFO", "Change detected (6.2% of the picture)"),
        (226, "INFO", "Change ended after 14s"),
    ]
    with path.open("w") as fh:
        for seconds_ago, level, message in lines:
            stamp = (now - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%d %H:%M:%S,000")
            fh.write(f"{stamp} - observice - {level} - {message}\n")


def _stream(handler) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    config = handler.server_config()
    try:
        while True:
            now = time.time()
            visitor = (now - visit_started) / VISIT_SECONDS if visit_started else None
            frame = cv2.imencode(".jpg", scene(now, visitor=visitor), [cv2.IMWRITE_JPEG_QUALITY, config.panel.preview_quality])[1]
            handler._write_frame(frame.tobytes())
            time.sleep(1 / config.panel.preview_fps)
    except (BrokenPipeError, ConnectionResetError):
        pass


def install(panel) -> None:
    """Points the panel module at the demo directory and replaces everything that needs the Pi."""
    DEMO_DIR.mkdir(exist_ok=True)
    panel.CONFIG_PATH = DEMO_DIR / "config.yaml"
    panel.LOG_PATH = DEMO_DIR / "observice_log"
    panel.RECORDINGS_DIR = DEMO_DIR / "recordings"
    if not panel.CONFIG_PATH.exists():
        save_config(replace(Config(), panel=PanelConfig(port=PORT)), panel.CONFIG_PATH)
    if not panel.LOG_PATH.exists():
        _seed_log(panel.LOG_PATH)
    file_log = logging.FileHandler(panel.LOG_PATH)
    file_log.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_log)
    print("Rendering sample clips…", flush=True)
    _seed_events(panel.RECORDINGS_DIR)
    close_unfinished_events(panel.RECORDINGS_DIR)
    threading.Thread(target=_simulate, args=(panel.RECORDINGS_DIR,), daemon=True).start()

    started = (datetime.now() - timedelta(hours=3)).strftime("%a %Y-%m-%d %H:%M:%S")
    panel.status = lambda: {"state": "active", "since": started, "restarts": "0", "commit": "v0.2.0 (demo)",
                            "host": "observice", "wifi": {"ssid": "Home", "signal": 72, "dbm": -54.0, "device": "wlan0"}}
    panel.restart_camera = lambda: (True, "Demo: camera service not restarted.")
    # check_updates stays real (git fetch + GitHub releases); only installing is disabled here.
    panel.update = lambda: {"ok": False, "output": "Demo: updates are disabled."}
    panel.Handler.server_config = lambda self: panel.load_config(panel.CONFIG_PATH)
    panel.Handler._stream = _stream
    print(f"Demo data in {DEMO_DIR} (delete it to start fresh)", flush=True)
