import json

from observice.config import Config
from observice.mqtt_bridge import ENTITIES, FIELD_MAP, _discovery


def test_discovery_topic_and_payload_shape():
    motion_entity = next(e for e in ENTITIES if e["object_id"] == "motion")
    topic, payload_json = _discovery(motion_entity, "observice/garage")
    payload = json.loads(payload_json)

    assert topic == "homeassistant/binary_sensor/observice_garage/motion/config"
    assert payload["state_topic"] == "observice/garage/motion/state"
    assert "command_topic" not in payload  # motion is read-only


def test_field_map_setter_updates_config():
    config = Config()
    _, apply_payload = FIELD_MAP["motion_enabled"]
    apply_payload(config, "OFF")
    assert config.motion.enabled is False


if __name__ == "__main__":
    test_discovery_topic_and_payload_shape()
    test_field_map_setter_updates_config()
    print("ok")
