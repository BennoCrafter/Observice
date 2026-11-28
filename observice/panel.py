"""Web dashboard: live preview, change events with clips, logs, config editor, release update.

Runs as its own systemd unit (deploy/observice-panel.service) so it stays up while
it restarts the camera service. Start locally with: python -m observice.panel
Try it without a camera or GStreamer: python -m observice.panel --demo
"""
import base64
import gzip
import hashlib
import hmac
import json
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

from observice import recordings
from observice.config import Config, _from_dict, load_config, save_config, schema
from observice.logger import setup_logger

CONFIG_PATH = Path("assets/config.yaml")
PAGE_PATH = Path("assets/panel.html")
NO_FEED_PATH = Path("assets/no-livefeed.jpeg")
LOG_PATH = Path("logs/observice_log")  # shared with the camera service (observice/logger.py)
RECORDINGS_DIR = recordings.RECORDINGS_DIR
LIVE_FRAME_PATH = recordings.LIVE_FRAME_PATH
LIVE_FRAME_MAX_AGE = 5  # seconds; older = camera not delivering
LOG_TAIL_BYTES = 512 * 1024
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ - \S+ - (\w+) - (.*)$")
MEDIA_PATH = re.compile(r"^/recordings/([\w-]+)\.(jpg|mp4)$")
MEDIA_TYPES = {"jpg": "image/jpeg", "mp4": "video/mp4"}
WIFI_PROFILE = "observice-wifi"  # the NetworkManager connection the panel creates; others are left as fallback
SUDO_NMCLI = ("sudo", "-n", "nmcli")
NO_ADMIN = "Not allowed yet: run the installer once more on the Pi (see README, 'Reboot and Wi-Fi from the panel')."

logger = setup_logger()


def run(*cmd: str, timeout: int = 60) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


# These sudo commands must match the sudoers rule install-pi.sh writes, argument for argument.
def restart_camera() -> tuple[bool, str]:
    return run("sudo", "-n", "systemctl", "restart", "observice")


def can_admin() -> bool:
    """False on installs from before the reboot/Wi-Fi sudoers rule; re-running install-pi.sh adds it."""
    return run("sudo", "-n", "-l", "/usr/bin/systemctl", "reboot")[0]


def reboot_soon() -> None:
    subprocess.Popen(["sh", "-c", "sleep 1; sudo -n systemctl reboot"])  # after the HTTP response is out


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
    """Rejects unknown keys, wrong types and out-of-range values, so the panel can't break the camera service."""
    specs = {s["key"]: {f["key"]: f for f in s["fields"]} for s in schema()}
    if not isinstance(data, dict):
        raise ValueError("config must be an object")
    for section, values in data.items():
        if section not in specs or not isinstance(values, dict):
            raise ValueError(f"unknown section: {section}")
        for key, value in values.items():
            spec = specs[section].get(key)
            if spec is None:
                raise ValueError(f"unknown field: {section}.{key}")
            name = f"{section}.{key}"
            if not _type_ok(value, spec["default"]):
                raise ValueError(f"{name} must be {spec['type']}, got {value!r}")
            if "options" in spec and value not in spec["options"]:
                raise ValueError(f"{name} must be one of {spec['options']}")
            if not spec.get("min", value) <= value <= spec.get("max", value):
                raise ValueError(f"{name} must be between {spec['min']} and {spec['max']}")
    return _from_dict(Config, data)


def parse_log(text: str) -> list[dict]:
    """Log lines -> entries; lines that don't start a record (tracebacks) belong to the one before."""
    entries = []
    for line in text.splitlines():
        m = LOG_LINE.match(line)
        if m:
            entries.append({"time": m[1], "level": m[2], "message": m[3]})
        elif entries and line.strip():
            entries[-1]["message"] += "\n" + line
    return entries


def read_log(path: Path, limit: int = 500) -> list[dict]:
    try:
        with path.open("rb") as fh:
            fh.seek(max(0, path.stat().st_size - LOG_TAIL_BYTES))
            text = fh.read().decode(errors="replace")
    except OSError:
        return []
    if len(text.encode()) >= LOG_TAIL_BYTES:
        text = text.partition("\n")[2]  # drop the line we started in the middle of
    return parse_log(text)[-limit:]


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


def _nmcli_fields(line: str) -> list[str]:
    # nmcli -t separates with ":" and escapes ":" inside values (e.g. SSIDs) as "\\:"
    return [f.replace("\\:", ":") for f in re.split(r"(?<!\\):", line)]


def wifi_adapters() -> list[dict]:
    """Every Wi-Fi adapter with what it's connected to. kind: Built-in (SDIO on a Pi) or USB."""
    adapters = {}
    for dev in sorted(Path("/sys/class/net").glob("wlan*")):
        bus = (dev / "device" / "subsystem").resolve().name
        adapters[dev.name] = {"device": dev.name, "kind": "USB" if bus == "usb" else "Built-in",
                              "mac": (dev / "address").read_text().strip(), "ssid": None, "signal": None}
    # LC_ALL=C: on a German system ACTIVE reads "ja"/"nein" instead of "yes"/"no"
    _, out = run("env", "LC_ALL=C", "nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,DEVICE", "dev", "wifi", "list", "--rescan", "no")
    for line in out.splitlines():
        fields = _nmcli_fields(line)
        if len(fields) == 4 and fields[0] == "yes" and fields[3] in adapters:
            adapters[fields[3]].update(ssid=fields[1], signal=int(fields[2]), dbm=_wifi_dbm(fields[3]))
    return list(adapters.values())


def wifi_networks(rescan: bool = False) -> list[dict]:
    """Visible networks, strongest first: one entry per SSID with its best signal per adapter."""
    nmcli = SUDO_NMCLI if rescan else ("nmcli",)  # a fresh scan needs root for a service user
    _, out = run("env", "LC_ALL=C", *nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY,DEVICE", "dev", "wifi", "list",
                 "--rescan", "yes" if rescan else "no", timeout=30)
    networks: dict[str, dict] = {}
    for line in out.splitlines():
        fields = _nmcli_fields(line)
        if len(fields) != 4 or not fields[0]:
            continue
        ssid, signal, security, device = fields[0], int(fields[1]), fields[2], fields[3]
        net = networks.setdefault(ssid, {"ssid": ssid, "secure": bool(security.strip("- ")), "signal": {}})
        net["signal"][device] = max(signal, net["signal"].get(device, 0))
    return sorted(networks.values(), key=lambda n: -max(n["signal"].values()))


def wifi_connect(ssid: str, password: str, device: str) -> None:
    """Joins `ssid` with the adapter `device`; meant to run in a background thread.

    Safe against typos: existing connections stay; if the new one doesn't come up, it's deleted again
    and NetworkManager reconnects the old way. On success the other adapter is left unused, and power
    saving is off (it made a USB adapter answer hundreds of ms late).
    """
    adapter = next(a for a in wifi_adapters() if a["device"] == device)
    run(*SUDO_NMCLI, "connection", "delete", WIFI_PROFILE)
    args = ["connection", "add", "type", "wifi", "con-name", WIFI_PROFILE, "ssid", ssid,
            "802-11-wireless.mac-address", adapter["mac"], "802-11-wireless.powersave", "2",
            "connection.autoconnect-priority", "10"]
    if password:
        args += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    ok, out = run(*SUDO_NMCLI, *args)
    if ok:
        ok, out = run(*SUDO_NMCLI, "--wait", "40", "connection", "up", WIFI_PROFILE, timeout=60)
    if not ok:
        run(*SUDO_NMCLI, "connection", "delete", WIFI_PROFILE)
        # No network name in logs: they end up in Home Assistant and get shared when asking for help.
        logger.error("Could not join the Wi-Fi with the %s adapter (%s), kept the old connection: %s",
                     adapter["kind"], device, out.replace(ssid, "<network>"))
        return
    # Keep the other Wi-Fi profiles as fallback, but on this adapter only, so the other one stays idle.
    _, profiles = run("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show")
    for fields in map(_nmcli_fields, profiles.splitlines()):
        if len(fields) == 2 and fields[1] == "802-11-wireless" and fields[0] != WIFI_PROFILE:
            run(*SUDO_NMCLI, "connection", "modify", fields[0],
                "802-11-wireless.mac-address", adapter["mac"], "802-11-wireless.powersave", "2")
    for other in wifi_adapters():
        if other["device"] != device:
            run(*SUDO_NMCLI, "device", "disconnect", other["device"])
    logger.info("Joined the Wi-Fi with the %s adapter (%s)", adapter["kind"], device)


def _wifi_dbm(device: str) -> float | None:
    try:
        for line in Path("/proc/net/wireless").read_text().splitlines()[2:]:
            name, _, values = line.partition(":")
            if name.strip() == device:
                return float(values.split()[2].rstrip("."))
    except (OSError, IndexError, ValueError):
        pass
    return None


def live_frame_fresh() -> bool:
    try:
        return time.time() - LIVE_FRAME_PATH.stat().st_mtime < LIVE_FRAME_MAX_AGE
    except OSError:
        return False


def status() -> dict:
    _, state = run("systemctl", "is-active", "observice")
    _, show = run("systemctl", "show", "-p", "ActiveEnterTimestamp", "-p", "NRestarts", "observice")
    _, commit = run("git", "describe", "--tags", "--always")
    props = dict(line.split("=", 1) for line in show.splitlines() if "=" in line)
    return {
        "state": state,
        "live": live_frame_fresh(),
        "since": props.get("ActiveEnterTimestamp", ""),
        "restarts": props.get("NRestarts", ""),
        "commit": commit,
        "host": socket.gethostname(),
    }


def latest_release() -> str:
    _, tags = run("git", "tag", "-l", "v*", "--sort=-v:refname")
    return tags.splitlines()[0] if tags else ""


def check_updates() -> dict:
    ok, out = run("git", "fetch", "--quiet", "--tags", "--force")
    if not ok:
        return {"ok": False, "output": out}
    tag = latest_release()
    if not tag:
        return {"ok": False, "output": "No releases published yet."}
    # Empty when HEAD already contains the tag, so an install ahead of it is never downgraded.
    _, pending = run("git", "log", "--format=%h", f"HEAD..{tag}")
    _, current = run("git", "describe", "--tags", "--abbrev=0")
    available = bool(pending)
    return {"ok": True, "current": current, "latest": tag, "available": available,
            "releases": release_notes(current) if available else []}


def _version(tag: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", tag))


def release_notes(current: str) -> list[dict]:
    """GitHub releases newer than `current`, newest first. Empty if GitHub can't be reached."""
    _, origin = run("git", "remote", "get-url", "origin")
    repo = re.search(r"github\.com[:/](.+?)(?:\.git)?$", origin)
    if not repo:
        return []
    try:
        res = requests.get(f"https://api.github.com/repos/{repo[1]}/releases", params={"per_page": 20}, timeout=10)
        res.raise_for_status()
        releases = res.json()
    except (requests.RequestException, ValueError):
        return []
    return [
        {"tag": r["tag_name"], "name": r["name"] or r["tag_name"], "notes": r["body"] or "", "date": r["published_at"]}
        for r in releases
        if not r["draft"] and _version(r["tag_name"]) > _version(current)
    ]


def update() -> dict:
    check = check_updates()
    if not check["ok"] or not check["available"]:
        return {"ok": False, "output": check.get("output", "Already on the latest release.")}
    steps = [
        ("git", "checkout", "--quiet", check["latest"]),
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
    logger.info("Updated to %s via panel", check["latest"])
    restart_panel_soon()
    return {"ok": True, "output": "\n\n".join(output)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # status polling would flood the journal

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        # Over a weak Wi-Fi every byte counts: unchanged responses (most polls) become a bodiless 304
        # via ETag, the rest are gzipped. "no-cache" lets the browser keep them but always revalidate.
        etag = '"%s"' % hashlib.sha1(body).hexdigest()[:16]
        if code == 200 and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("ETag", etag)
        if len(body) > 1024 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, compresslevel=5)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
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
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        media = MEDIA_PATH.match(url.path)
        if url.path == "/":
            self._send(200, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/status":
            self._json(status())
        elif url.path == "/api/config":
            self._json({"values": asdict(load_config(CONFIG_PATH)), "schema": schema()})
        elif url.path == "/api/logs":
            self._json({"entries": read_log(LOG_PATH)})
        elif url.path == "/api/events":
            before = query.get("before", [None])[0]
            self._json({"events": recordings.list_events(RECORDINGS_DIR, before)})
        elif url.path == "/api/updates":
            self._json(check_updates())
        elif url.path == "/api/wifi":
            rescan = query.get("rescan") == ["1"]
            self._json({"adapters": wifi_adapters(), "networks": wifi_networks(rescan), "can_admin": can_admin()})
        elif url.path == "/stream.mjpg":
            self._stream()
        elif media and recordings.ID_PATTERN.match(media[1]):
            self._send_file(RECORDINGS_DIR / f"{media[1]}.{media[2]}", MEDIA_TYPES[media[2]])
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
        elif self.path == "/api/reboot":
            if not can_admin():
                self._json({"ok": False, "output": NO_ADMIN})
                return
            logger.info("Rebooting via panel")
            self._json({"ok": True})
            reboot_soon()
        elif self.path == "/api/wifi":
            self._join_wifi()
        elif self.path == "/api/events/delete":
            event_id = self._body().get("id", "")
            ok = recordings.delete_event(RECORDINGS_DIR, event_id)
            if ok:
                logger.info("Deleted change %s via panel", event_id)
            self._json({"ok": ok})
        else:
            self._send(404, b"not found", "text/plain")

    def _join_wifi(self) -> None:
        body = self._body()
        ssid, password, device = body.get("ssid", ""), body.get("password", ""), body.get("device", "")
        if not can_admin():
            self._json({"ok": False, "output": NO_ADMIN})
        elif not 0 < len(ssid.encode()) <= 32 or (password and not 8 <= len(password) <= 63):
            self._json({"ok": False, "output": "Network name must be 1-32 bytes, password 8-63 characters."})
        elif device not in {a["device"] for a in wifi_adapters()}:
            self._json({"ok": False, "output": f"No Wi-Fi adapter {device!r}."})
        else:
            # Answer first: switching networks or adapters can change the Pi's address mid-request.
            self._json({"ok": True})
            logger.info("Joining a Wi-Fi with %s via panel", device)
            threading.Thread(target=wifi_connect, args=(ssid, password, device), daemon=True).start()

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def _send_file(self, path: Path, content_type: str) -> None:
        """Serves byte ranges too: browsers need them to seek in (Safari: to play) a video."""
        try:
            size = path.stat().st_size
        except OSError:
            self._send(404, b"not found", "text/plain")
            return
        start, end = 0, size - 1
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m and (m[1] or m[2]):
            start, end = (int(m[1]), int(m[2] or end)) if m[1] else (max(0, size - int(m[2])), end)
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        try:
            with path.open("rb") as fh:
                fh.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = fh.read(min(remaining, 256 * 1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # player seeked elsewhere

    def _save_config(self) -> None:
        try:
            new = parse_config(self._body())
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
        """MJPEG of the camera service's latest frame; no video decoding needed here."""
        fps = load_config(CONFIG_PATH).panel.preview_fps
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        sent = None
        try:
            while True:
                if not live_frame_fresh():
                    self._write_frame(NO_FEED_PATH.read_bytes())
                    sent = None
                    time.sleep(2)
                    continue
                stamp = LIVE_FRAME_PATH.stat().st_mtime_ns
                if stamp != sent:
                    sent = stamp
                    self._write_frame(LIVE_FRAME_PATH.read_bytes())
                time.sleep(0.5 / fps)  # check twice per frame
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser closed the tab
        except FileNotFoundError:
            pass  # camera service stopped between the check and the read; the browser reconnects

    def _write_frame(self, jpeg: bytes) -> None:
        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpeg))
        self.wfile.write(jpeg + b"\r\n")


def main() -> None:
    if "--demo" in sys.argv[1:]:
        from observice import panel_demo

        panel_demo.install(sys.modules[__name__])
    port = load_config(CONFIG_PATH).panel.port
    server = ThreadingHTTPServer(("", port), Handler)
    server.daemon_threads = True
    logger.info("Panel running at http://0.0.0.0:%s", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
