import base64
import os
import subprocess
import tempfile

from observice import panel
from observice.panel import _nmcli_fields, authorized, check_updates, parse_config, parse_log


def _basic(password: str) -> str:
    return "Basic " + base64.b64encode(f"any:{password}".encode()).decode()


def test_parse_config_accepts_valid_and_rejects_bad_types():
    config = parse_config({"motion": {"min_area_percent": 2, "enabled": False}, "discord": {"listening_users": [1, 2]}})
    assert config.motion.min_area_percent == 2 and config.motion.enabled is False
    assert config.camera.width == 1280  # missing fields keep defaults

    for bad in (
        {"motion": {"enabled": "yes"}},
        {"camera": {"width": True}},
        {"camera": {"rtsp_port": 1.5}},
        {"discord": {"listening_users": ["x"]}},
        {"camera": {"nope": 1}},
        {"camera": {"rotation": 45}},  # not one of the options
        {"motion": {"quiet_seconds": 0}},  # below min
        {"panel": {"preview_quality": 101}},  # above max
        {"nope": {}},
        [],
    ):
        try:
            parse_config(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def test_authorized():
    assert authorized(None, "")  # no password configured = open
    assert authorized(_basic("s3cret"), "s3cret")
    assert not authorized(_basic("wrong"), "s3cret")
    assert not authorized(None, "s3cret")
    assert not authorized("Basic !!!notbase64", "s3cret")


def test_check_updates_follows_release_tags():
    def git(*args, cwd):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)

    with tempfile.TemporaryDirectory() as tmp:
        origin, clone = f"{tmp}/origin", f"{tmp}/clone"
        git("init", "-q", origin, cwd=tmp)
        git("commit", "-q", "--allow-empty", "-m", "one", cwd=origin)
        git("tag", "v0.9.0", cwd=origin)
        git("commit", "-q", "--allow-empty", "-m", "two", cwd=origin)
        git("tag", "v0.10.0", cwd=origin)  # version sort, not string sort
        git("clone", "-q", origin, clone, cwd=tmp)
        git("checkout", "-q", "v0.9.0", cwd=clone)

        cwd = os.getcwd()
        os.chdir(clone)
        try:
            r = check_updates()
            assert r["ok"] and r["latest"] == "v0.10.0" and r["current"] == "v0.9.0" and r["available"], r
            git("commit", "-q", "--allow-empty", "-m", "three", cwd=origin)  # main ahead of newest tag
            git("pull", "-q", "origin", "HEAD", cwd=clone)
            r = check_updates()
            assert r["ok"] and not r["available"], r  # never offers a downgrade
        finally:
            os.chdir(cwd)


def test_parse_log_groups_tracebacks():
    entries = parse_log(
        "2026-11-28 16:14:52,382 - observice - INFO - RTSP stream ready\n"
        "2026-11-28 16:15:00,001 - observice - ERROR - Could not write clip\n"
        "Traceback (most recent call last):\n"
        '  File "x.py", line 1\n'
        "ValueError: boom\n"
    )
    assert [e["level"] for e in entries] == ["INFO", "ERROR"]
    assert entries[0] == {"time": "2026-11-28 16:14:52", "level": "INFO", "message": "RTSP stream ready"}
    assert entries[1]["message"].endswith("ValueError: boom")


def test_wifi_networks_parsing():
    assert _nmcli_fields(r"Cafe\: Gast:57:WPA2:wlan1") == ["Cafe: Gast", "57", "WPA2", "wlan1"]
    original = panel.run
    panel.run = lambda *cmd, **kw: (True, "HomeNet:49:WPA2:wlan0\nHomeNet:60:WPA2:wlan1\nHomeNet:30:WPA2:wlan1\n:40:WPA2:wlan1\nOpen:70::wlan1")
    try:
        networks = panel.wifi_networks()
    finally:
        panel.run = original
    assert [n["ssid"] for n in networks] == ["Open", "HomeNet"]  # strongest first, hidden SSIDs skipped
    assert networks[1] == {"ssid": "HomeNet", "secure": True, "signal": {"wlan0": 49, "wlan1": 60}}
    assert networks[0]["secure"] is False


if __name__ == "__main__":
    test_parse_config_accepts_valid_and_rejects_bad_types()
    test_authorized()
    test_check_updates_follows_release_tags()
    test_parse_log_groups_tracebacks()
    test_wifi_networks_parsing()
    print("ok")
