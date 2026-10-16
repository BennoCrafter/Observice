import json
import logging
from pathlib import Path

import paho.mqtt.client as mqtt

from observice.config import Config, save_config

logger = logging.getLogger("observice")

# One entry per HA entity this bridge exposes. "extra" holds fields specific
# to that HA component (device_class, unit_of_measurement, min/max, ...).
ENTITIES = [
    {
        "component": "binary_sensor",
        "object_id": "motion",
        "name": "Motion",
        "extra": {"device_class": "motion"},
        "settable": False,
    },
    {
        "component": "sensor",
        "object_id": "log",
        "name": "Log",
        "extra": {"entity_category": "diagnostic", "icon": "mdi:text-box-outline"},
        "settable": False,
    },
    {
        "component": "switch",
        "object_id": "motion_enabled",
        "name": "Motion Detection",
        "extra": {},
        "settable": True,
    },
    {
        "component": "switch",
        "object_id": "discord_enabled",
        "name": "Discord Notifications",
        "extra": {},
        "settable": True,
    },
    {
        "component": "number",
        "object_id": "check_interval",
        "name": "Motion Check Interval",
        "extra": {"min": 5, "max": 3600, "unit_of_measurement": "s"},
        "settable": True,
    },
]


def _bool_str(value: bool) -> str:
    return "ON" if value else "OFF"


# object_id -> (read current value from Config, apply an incoming MQTT payload to Config)
FIELD_MAP = {
    "motion_enabled": (
        lambda c: _bool_str(c.motion.enabled),
        lambda c, payload: setattr(c.motion, "enabled", payload == "ON"),
    ),
    "discord_enabled": (
        lambda c: _bool_str(c.discord.enabled),
        lambda c, payload: setattr(c.discord, "enabled", payload == "ON"),
    ),
    "check_interval": (
        lambda c: str(c.motion.check_interval),
        lambda c, payload: setattr(c.motion, "check_interval", int(payload)),
    ),
}


class MqttLogHandler(logging.Handler):
    """Mirrors log records to the HA "Log" sensor; HA's history keeps past lines."""

    def __init__(self, client: mqtt.Client, topic: str):
        super().__init__(logging.INFO)
        self.client = client
        self.topic = topic
        self.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        # HA rejects sensor states longer than 255 chars
        self.client.publish(self.topic, self.format(record)[:255], retain=True)


def _discovery(entity: dict, base_topic: str) -> tuple[str, str]:
    device_id = base_topic.replace("/", "_")
    object_id = entity["object_id"]
    topic = f"homeassistant/{entity['component']}/{device_id}/{object_id}/config"
    payload = {
        "name": entity["name"],
        "unique_id": f"{device_id}_{object_id}",
        "state_topic": f"{base_topic}/{object_id}/state",
        "availability_topic": f"{base_topic}/status",
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": {"identifiers": [device_id], "name": f"Observice {base_topic}", "manufacturer": "Observice"},
        **entity["extra"],
    }
    if entity["settable"]:
        payload["command_topic"] = f"{base_topic}/{object_id}/set"
    return topic, json.dumps(payload)


class MqttBridge:
    """Publishes HA MQTT-discovery entities and applies config changes HA sends back."""

    def __init__(self, config: Config, config_path: Path):
        self.config = config
        self.config_path = config_path
        self.base_topic = config.mqtt.base_topic

        self.client = mqtt.Client()
        if config.mqtt.username:
            self.client.username_pw_set(config.mqtt.username, config.mqtt.password)
        self.client.will_set(f"{self.base_topic}/status", "offline", retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.log_handler = MqttLogHandler(self.client, f"{self.base_topic}/log/state")

    def connect(self) -> None:
        self.client.connect(self.config.mqtt.host, self.config.mqtt.port)
        self.client.loop_start()
        logger.addHandler(self.log_handler)

    def close(self) -> None:
        logger.removeHandler(self.log_handler)
        self.client.publish(f"{self.base_topic}/status", "offline", retain=True)
        self.client.loop_stop()
        self.client.disconnect()

    def publish_motion(self, detected: bool) -> None:
        self.client.publish(f"{self.base_topic}/motion/state", _bool_str(detected))

    def _publish_state(self) -> None:
        for object_id, (get_value, _) in FIELD_MAP.items():
            self.client.publish(f"{self.base_topic}/{object_id}/state", get_value(self.config), retain=True)

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            # paho retries on its own; e.g. rc=5 means wrong mqtt.username/password
            logger.error("MQTT broker refused connection: %s", mqtt.connack_string(rc))
            return
        for entity in ENTITIES:
            topic, payload = _discovery(entity, self.base_topic)
            client.publish(topic, payload, retain=True)
        client.publish(f"{self.base_topic}/status", "online", retain=True)
        for object_id in FIELD_MAP:
            client.subscribe(f"{self.base_topic}/{object_id}/set")
        self._publish_state()
        logger.info("Connected to MQTT broker at %s:%s", self.config.mqtt.host, self.config.mqtt.port)

    def _on_message(self, client, userdata, msg):
        object_id = msg.topic.rsplit("/", 2)[-2]
        if object_id not in FIELD_MAP:
            return
        payload = msg.payload.decode()
        _, apply_payload = FIELD_MAP[object_id]
        apply_payload(self.config, payload)
        save_config(self.config, self.config_path)
        self._publish_state()
        logger.info("Config updated from Home Assistant: %s = %s", object_id, payload)
