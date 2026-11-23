import base64

from observice.panel import authorized, parse_config


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


if __name__ == "__main__":
    test_parse_config_accepts_valid_and_rejects_bad_types()
    test_authorized()
    print("ok")
