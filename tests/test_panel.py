import base64
import os
import subprocess
import tempfile

from observice.panel import authorized, check_updates, parse_config


def _basic(password: str) -> str:
    return "Basic " + base64.b64encode(f"any:{password}".encode()).decode()


def test_parse_config_accepts_valid_and_rejects_bad_types():
    config = parse_config({"motion": {"threshold": 30, "enabled": False}, "discord": {"listening_users": [1, 2]}})
    assert config.motion.threshold == 30 and config.motion.enabled is False
    assert config.camera.width == 1280  # missing fields keep defaults

    for bad in (
        {"motion": {"enabled": "yes"}},
        {"camera": {"width": True}},
        {"camera": {"rtsp_port": 1.5}},
        {"discord": {"listening_users": ["x"]}},
        {"camera": {"nope": 1}},
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
            assert r["ok"] and r["latest"] == "v0.10.0" and len(r["pending"]) == 1, r
            git("commit", "-q", "--allow-empty", "-m", "three", cwd=origin)  # main ahead of newest tag
            git("pull", "-q", "origin", "HEAD", cwd=clone)
            r = check_updates()
            assert r["ok"] and r["pending"] == [], r  # never offers a downgrade
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    test_parse_config_accepts_valid_and_rejects_bad_types()
    test_authorized()
    test_check_updates_follows_release_tags()
    print("ok")
