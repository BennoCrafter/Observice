# Observice

<img src="assets/observice.svg" width="96" alt="Observice icon">

Turns a Raspberry Pi with a USB camera into a self-hosted camera watcher: an RTSP stream, motion alerts to Discord, Home Assistant integration over MQTT, and a web panel at `http://observice.local`.

## Install

### Flash the image (Raspberry Pi 3, 4, 5, Zero 2 W)

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Open its app options → **Image Repository** → **Edit**, and enter:
   ```
   https://github.com/BennoCrafter/Observice/releases/latest/download/observice.rpi-imager.json
   ```
   (Use this instead of *Use custom* with a downloaded file — only the repository entry lets Imager set up your user and Wi-Fi.)
3. Choose your Pi, then **Observice** as the OS, then your SD card.
4. In the customisation steps, set a username/password, your Wi-Fi and enable SSH. Leave the hostname as `observice` (change it if you run more than one).
5. Write the card, plug the camera into the Pi and power it on.
6. After a minute or two open **http://observice.local**, fill in Discord/MQTT in the config editor and set a panel password — until you do, anyone on your network can open the panel.

To get the normal Raspberry Pi OS list back in Imager, reset the Image Repository to its default.

### Or: install on an existing Raspberry Pi OS

Run as your normal user (not root):

```bash
curl -fsSL https://raw.githubusercontent.com/BennoCrafter/Observice/main/install-pi.sh | bash
```

It installs the apt packages and a venv into `/opt/observice`, adds you to the `video` group and sets up two systemd services (`observice`, `observice-panel`) running as you. Then open `http://<pi-ip>` to configure it. Logs: `journalctl -u observice -f`.

## Updating

The panel's **Check for updates** / **Update & restart** moves to the newest GitHub release (never an older one). Re-running `install-pi.sh` does the same.

## Home Assistant

1. **Camera**: *Settings → Devices & services → Add integration → Generic Camera*, **Stream source** `rtsp://observice.local:8554/cam`, leave **Still image URL** empty.
2. **MQTT**: install the *Mosquitto broker* add-on, create an HA user for Observice and put its name/password in `mqtt.username`/`mqtt.password`. Observice then auto-creates a motion sensor, a log sensor, "Motion Detection" and "Discord Notifications" switches and a "Motion Check Interval" number. Changes made in HA are written back to the config.

## Configuration

Edited in the panel; stored in `/opt/observice/assets/config.yaml`.

| Section   | Field            | Meaning                                                              |
|-----------|------------------|-----------------------------------------------------------------------|
| `camera`  | `width/height/framerate` | Stream resolution/fps                                        |
|           | `rtsp_port`      | RTSP port (default `8554`)                                            |
|           | `device`         | v4l2 device, empty = `/dev/video0`                                    |
| `motion`  | `enabled`        | Motion detection on/off                                               |
|           | `check_interval` | Seconds between frame comparisons                                     |
|           | `threshold`      | Mean pixel difference that counts as "changed"                        |
| `discord` | `enabled`        | Discord notifications on/off                                          |
|           | `webhook_url`    | Webhook to post snapshots to                                          |
|           | `token`          | Bot token, only for `scripts/download_discord_images.py`              |
|           | `listening_users`| Discord user IDs to @-mention                                         |
| `mqtt`    | `enabled`        | Home Assistant/MQTT bridge on/off                                     |
|           | `host/port`      | MQTT broker                                                           |
|           | `username/password` | Broker credentials                                                 |
|           | `base_topic`     | Topic prefix, also names the HA device — make it unique per camera, e.g. `observice/frontdoor` |
| `panel`   | `port`           | Panel port (default `80`)                                             |
|           | `password`       | Panel password (any username); empty = no login                       |

## Development

- `observice/main.py` runs the RTSP stream (`capture.py`), motion detection (`motion.py`), Discord (`discord_notify.py`) and MQTT (`mqtt_bridge.py`); `observice/panel.py` is the web panel.
- GStreamer/PyGObject aren't pip packages — see `assets/requirements.txt` for the apt/brew commands.
- Tests: `pip install -r assets/requirements.txt pytest && pytest tests`
- `scripts/download_discord_images.py --channel-id <id> --out ./downloads` downloads every image from a Discord channel.

### Releasing

Push a `v*` tag (`git tag v0.2.0 && git push --tags`). GitHub Actions builds the image with [CustomPiOS](https://github.com/guysoft/CustomPiOS) from `image/` (~15 min) and publishes a release with the image and the Imager repository file. `image/build.sh` builds the image locally with Docker.
