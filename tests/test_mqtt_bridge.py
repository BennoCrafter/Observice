import json
import logging

from observice.config import Config
from observice.mqtt_bridge import ENTITIES, FIELD_MAP, MqttLogHandler, _discovery


def test_discovery_topic_and_payload_shape():
    motion_entity = next(e for e in ENTITIES if e["object_id"] == "motion")
    topic, payload_json = _discovery(motion_entity, "observice/camera")
    payload = json.loads(payload_json)

    assert topic == "homeassistant/binary_sensor/observice_camera/motion/config"
    assert payload["state_topic"] == "observice/camera/motion/state"
    assert "command_topic" not in payload  # motion is read-only


def test_field_map_setter_updates_config():
    config = Config()
    _, apply_payload = FIELD_MAP["motion_enabled"]
    apply_payload(config, "OFF")
    assert config.motion.enabled is False


def test_log_handler_publishes_truncated_line():
    published = []

    class FakeClient:
        def publish(self, topic, payload, retain=False):
            published.append((topic, payload))

    handler = MqttLogHandler(FakeClient(), "observice/camera/log/state")
    handler.emit(logging.LogRecord("observice", logging.INFO, "", 0, "x" * 300, None, None))

    topic, payload = published[0]
    assert topic == "observice/camera/log/state"
    assert payload.startswith("INFO x") and len(payload) == 255


if __name__ == "__main__":
    test_discovery_topic_and_payload_shape()
    test_field_map_setter_updates_config()
    test_log_handler_publishes_truncated_line()
    print("ok")
