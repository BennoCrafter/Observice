# Observice

<img src="assets/observice.svg" width="96" alt="Observice icon">

A small, self-hosted camera-watching service: serves a camera as an RTSP stream, watches it for motion, notifies you when something changes, and integrates with Home Assistant over MQTT.

Point it at any camera — a room, a door, a 3D printer — see **Make it yours** below for what to change.

## How it fits together

- **RTSP stream** (`observice/capture.py`): a GStreamer RTSP server publishes the camera at `rtsp://<host>:8554/cam`. Home Assistant (or VLC, `ffplay`, ...) can watch it directly — no extra code needed on either side.
- **Motion detection** (`observice/motion.py`): polls that stream on an interval, diffs consecutive frames, and fires a callback when they differ enough.
- **Discord** (`observice/discord_notify.py`): posts the frame that triggered motion to a Discord webhook, optionally @-mentioning a list of user IDs.
- **Home Assistant** (`observice/mqtt_bridge.py`): publishes MQTT-discovery entities (motion sensor, two switches, one number) so HA auto-creates them, and listens for HA pushing those settings back — that's how you can flip "Discord Notifications" or change the check interval from the HA UI.
- **`observice/config.py`**: one `assets/config.yaml`, loaded once at startup; changes made from HA are written back to this file so they survive a restart.

## Install

Pick one of the two paths below. Either way, first:

1. Plug in a USB (or CSI) camera to whatever host you're running on, make sure `/dev/video0` exists (`ls /dev/video0`).
2. `cp assets/default_config.yaml assets/config.yaml` and fill in your Discord webhook URL / bot token and MQTT broker details (see **Configuration** below).

### Option A — systemd (recommended on a Raspberry Pi)

Running directly on the host avoids container/GStreamer version mismatches (see the note in the Dockerfile) and gives simpler camera access.

```bash
sudo apt install -y python3-gi gir1.2-gst-rtsp-server-1.0 \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
pip install -r assets/requirements.txt
sudo cp deploy/observice.service /etc/systemd/system/
sudo systemctl enable --now observice
journalctl -u observice -f   # check it started cleanly
```

### Option B — Docker

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

If the container fails on `import gi`, that's the apt-vs-pip Python version mismatch noted in the Dockerfile — use Option A instead.

### Daily reboot (optional)

A crontab line is all a nightly reboot needs:

```bash
sudo crontab -e
# add:
0 4 * * * /sbin/reboot
```

## Configuration (`assets/config.yaml`)

| Section   | Field            | Meaning                                                              |
|-----------|------------------|-----------------------------------------------------------------------|
| `camera`  | `width/height/framerate` | Stream resolution/fps                                        |
|           | `rtsp_port`      | Port the RTSP server listens on (default `8554`)                      |
|           | `device`         | Linux only: override `/dev/video0` with another v4l2 device path      |
| `motion`  | `enabled`        | Turn motion detection on/off (also settable from HA)                  |
|           | `check_interval` | Seconds between frame comparisons (also settable from HA)             |
|           | `threshold`      | Mean pixel-difference above which a frame counts as "changed"         |
| `discord` | `enabled`        | Turn Discord notifications on/off (also settable from HA)             |
|           | `webhook_url`    | Discord webhook to post snapshots to                                  |
|           | `token`          | Bot token — only used by `scripts/download_discord_images.py`         |
|           | `listening_users`| Discord user IDs to @-mention on each notification                    |
| `mqtt`    | `enabled`        | Turn the Home Assistant/MQTT bridge on/off                            |
|           | `host/port`      | Your MQTT broker (the HA "Mosquitto broker" add-on, typically)        |
|           | `username/password` | Broker credentials, if required                                    |
|           | `base_topic`     | MQTT topic prefix (default `observice/camera`) — also names the HA device; use a unique one per instance, e.g. `observice/frontdoor` |

## Home Assistant setup

1. **Camera**: the video doesn't go over MQTT — HA pulls the RTSP stream straight from Observice. Add a camera entity pointing at it:
   ```yaml
   camera:
     - platform: generic
       stream_source: rtsp://<host-ip>:8554/cam
   ```
2. **MQTT**: make sure HA's MQTT integration is configured against the same broker as `mqtt.host`/`mqtt.port` in your config. Once Observice connects, it auto-publishes discovery entities under `homeassistant/...` — a motion sensor, a "Log" sensor (latest log line; past lines in its history), a "Motion Detection" switch, a "Discord Notifications" switch, and a "Motion Check Interval" number will appear in HA without any manual YAML.
3. Flipping those switches/number in HA writes straight back to `assets/config.yaml` on the host.

## Discord image downloader

A one-off script to pull every image ever posted in a Discord channel into a local folder:

```bash
python scripts/download_discord_images.py --channel-id <channel id> --out ./downloads
# --token defaults to discord.token in assets/config.yaml if omitted
```

## Make it yours

Everything here is deliberately plain Python + YAML, not framework-locked, so repurposing it is mostly config and small, obvious edits:

- **Different camera / location**: just a config change — edit `camera.device` (and `assets/config.yaml`'s `mqtt.base_topic`, so it doesn't collide with another instance) to point at a different room, printer-cam, or device. Run a second instance for a second camera.
- **Different notification channel**: `observice/discord_notify.py` is a single `send_image()` function — swap it for a Slack webhook, a Telegram bot, an email, whatever; `observice/main.py`'s `on_motion()` callback is the one place that calls it.
- **Different Home Assistant identity**: the HA device id/name is derived from `mqtt.base_topic` — `observice/frontdoor` shows up as "Observice observice/frontdoor".
- **Different trigger logic**: `observice/motion.py`'s `frame_changed()` is one small, pure function (frame diff vs. a threshold) — replace it with whatever detection makes sense for your use case (object detection, a specific zone, a different sensor entirely) without touching the RTSP, Discord, or MQTT pieces.
- **More entities in HA**: `ENTITIES`/`FIELD_MAP` in `observice/mqtt_bridge.py` are a small table, not a framework — add a row to expose another setting to HA.

## Development

Camera capture (`observice/capture.py`, `observice/main.py`) needs GStreamer + PyGObject, which aren't pip packages — see the apt/brew commands in `assets/requirements.txt`. Everything else (`config.py`, `motion.py`, `discord_notify.py`, `mqtt_bridge.py`) has no hardware dependency and is covered by the self-checks in `tests/`:

```bash
pip install -r assets/requirements.txt
PYTHONPATH=. python tests/test_motion.py
PYTHONPATH=. python tests/test_mqtt_bridge.py
```
