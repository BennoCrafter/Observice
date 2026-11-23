"""Web dashboard: live preview, service status + logs, config editor, git update.

Runs as its own systemd unit (deploy/observice-panel.service) so it stays up while
it restarts the camera service. Start locally with: python -m observice.panel
"""
import base64
import hmac
import json
import subprocess
import sys
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

from observice.config import Config, _from_dict, load_config, save_config
from observice.logger import setup_logger

CONFIG_PATH = Path("assets/config.yaml")
PAGE_PATH = Path("assets/panel.html")
NO_FEED_PATH = Path("assets/no-livefeed.jpeg")
PREVIEW_FPS = 5  # browser preview only; HA still pulls full fps over RTSP

logger = setup_logger()


def run(*cmd: str, timeout: int = 60) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


# Both commands must match the sudoers rule install-pi.sh writes, argument for argument.
def restart_camera() -> tuple[bool, str]:
    return run("sudo", "-n", "systemctl", "restart", "observice")


def restart_panel_soon() -> None:
    # Delayed so the current HTTP response gets out before systemd stops us.
    subprocess.Popen(["sh", "-c", "sleep 1; sudo -n systemctl --no-block restart observice-panel"])


def _type_ok(value, default) -> bool:
    if isinstance(value, bool) or isinstance(default, bool):
        return type(value) is type(default)
    if isinstance(default, float):
        return isinstance(value, (int, float))
    if isinstance(default, list):
        return isinstance(value, list) and all(type(v) is int for v in value)
    return type(value) is type(default)


def parse_config(data) -> Config:
    """Rejects unknown keys and wrong types, so a typo in the panel can't crash the camera service."""
    defaults = asdict(Config())
    if not isinstance(data, dict):
        raise ValueError("config must be an object")
    for section, values in data.items():
        if section not in defaults or not isinstance(values, dict):
            raise ValueError(f"unknown section: {section}")
        for key, value in values.items():
            if key not in defaults[section]:
                raise ValueError(f"unknown field: {section}.{key}")
            if not _type_ok(value, defaults[section][key]):
                expected = type(defaults[section][key]).__name__
                raise ValueError(f"{section}.{key} must be {expected}, got {value!r}")
    return _from_dict(Config, data)


def authorized(header: str | None, password: str) -> bool:
    if not password:
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        _, _, given = base64.b64decode(header[6:]).decode().partition(":")
    except ValueError:
        return False
    return hmac.compare_digest(given.encode(), password.encode())


def status() -> dict:
    _, state = run("systemctl", "is-active", "observice")
    _, show = run("systemctl", "show", "-p", "ActiveEnterTimestamp", "-p", "NRestarts", "observice")
    _, commit = run("git", "log", "-1", "--format=%h %s (%cr)")
    _, logs = run("journalctl", "-u", "observice", "-n", "150", "--no-pager", "-o", "cat")
    props = dict(line.split("=", 1) for line in show.splitlines() if "=" in line)
    return {
        "state": state,
        "since": props.get("ActiveEnterTimestamp", ""),
        "restarts": props.get("NRestarts", ""),
        "commit": commit,
        "logs": logs,
    }


def check_updates() -> dict:
    ok, out = run("git", "fetch", "--quiet")
    if not ok:
        return {"ok": False, "output": out}
    _, pending = run("git", "log", "--format=%h %s", "HEAD..@{u}")
    return {"ok": True, "pending": pending.splitlines()}


def update() -> dict:
    steps = [
        ("git", "pull", "--ff-only"),
        (sys.executable, "-m", "pip", "install", "-q", "-r", "assets/requirements.txt"),
        ("sudo", "-n", "systemctl", "restart", "observice"),
    ]
    output = []
    for cmd in steps:
        ok, out = run(*cmd, timeout=600)
        output.append(f"$ {' '.join(cmd)}\n{out}".strip())
        if not ok:
            logger.error("Panel update failed at: %s", " ".join(cmd))
            return {"ok": False, "output": "\n\n".join(output)}
    logger.info("Updated from git via panel")
    restart_panel_soon()
    return {"ok": True, "output": "\n\n".join(output)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # status polling would flood the journal

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, code: int = 200) -> None:
        self._send(code, json.dumps(data).encode(), "application/json")

    def _check_auth(self) -> bool:
        if authorized(self.headers.get("Authorization"), load_config(CONFIG_PATH).panel.password):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Observice"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def do_GET(self):
        if not self._check_auth():
            return
        if self.path == "/":
            self._send(200, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._json(status())
        elif self.path == "/api/config":
            self._json(asdict(load_config(CONFIG_PATH)))
        elif self.path == "/api/updates":
            self._json(check_updates())
        elif self.path == "/stream.mjpg":
            self._stream()
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self._check_auth():
            return
        # A custom header can't be sent cross-site without CORS, which blocks CSRF from other pages.
        if self.headers.get("X-Observice") != "1":
            self._send(403, b"missing X-Observice header", "text/plain")
            return
        if self.path == "/api/config":
            self._save_config()
        elif self.path == "/api/restart":
            ok, out = restart_camera()
            self._json({"ok": ok, "output": out})
        elif self.path == "/api/update":
            self._json(update())
        else:
            self._send(404, b"not found", "text/plain")

    def _save_config(self) -> None:
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            new = parse_config(json.loads(body))
        except ValueError as e:  # includes JSONDecodeError
            self._json({"ok": False, "output": str(e)}, 400)
            return
        old = load_config(CONFIG_PATH)
        save_config(new, CONFIG_PATH)
        logger.info("Config saved via panel")
        ok, out = restart_camera()
        if new.panel.port != old.panel.port:
            restart_panel_soon()
        self._json({"ok": ok, "output": out or "Saved, camera service restarted."})

    def _stream(self) -> None:
        url = f"rtsp://127.0.0.1:{load_config(CONFIG_PATH).camera.rtsp_port}/cam"
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        cap = cv2.VideoCapture(url)
        last_sent = 0.0
        try:
            while True:
                ok, frame = cap.read()  # read every frame so the preview doesn't lag behind
                if not ok:
                    self._write_frame(NO_FEED_PATH.read_bytes())
                    cap.release()
                    time.sleep(3)
                    cap = cv2.VideoCapture(url)
                    continue
                if time.monotonic() - last_sent < 1 / PREVIEW_FPS:
                    continue
                last_sent = time.monotonic()
                self._write_frame(cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes())
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser closed the tab
        finally:
            cap.release()

    def _write_frame(self, jpeg: bytes) -> None:
        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpeg))
        self.wfile.write(jpeg + b"\r\n")


def main() -> None:
    port = load_config(CONFIG_PATH).panel.port
    server = ThreadingHTTPServer(("", port), Handler)
    server.daemon_threads = True
    logger.info("Panel running at http://0.0.0.0:%s", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
