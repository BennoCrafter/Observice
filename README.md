# Observice

<img src="assets/observice.svg" width="96" alt="Observice icon">

Turns a Raspberry Pi with a USB camera into a self-hosted camera watcher: an RTSP stream, change detection with snapshots and video clips, alerts to Discord, Home Assistant integration over MQTT, and a web panel at `http://observice.local`.

## Install

### Flash the image (Raspberry Pi 3, 4, 5, Zero 2 W)

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Open its app options → **Image Repository** → **Edit**, and enter:
   ```
   https://github.com/BennoCrafter/Observice/releases/latest/download/observice.rpi-imager.json
   ```
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

The panel's **Check for updates** / **Update & restart** moves to the newest GitHub release. Re-running `install-pi.sh` does the same.

## Home Assistant

1. **Camera**: *Settings → Devices & services → Add integration → Generic Camera*, **Stream source** `rtsp://observice.local:8554/cam`, leave **Still image URL** empty. [Add Camera to HA](https://my.home-assistant.io/redirect/config_flow_start?domain=generic)
2. **MQTT**: install the *Mosquitto broker* add-on, create an HA user for Observice and put its name/password in `mqtt.username`/`mqtt.password`. Observice then auto-creates a motion sensor, a log sensor, "Motion Detection" and "Discord Notifications" switches and a "Motion Cooldown" number. Changes made in HA are written back to the config.

## Change detection

The camera service compares small frames twice a second. When enough of the picture changes, an event starts; it ends after the cooldown without change. Each event gets a snapshot and a clip (a few seconds before the change through its end), shown in the panel's **Changes** list and kept for a configurable number of days in `/opt/observice/recordings/`.

## Configuration

Everything is edited in the panel's **Settings** (stored in `/opt/observice/assets/config.yaml`), each field with an explanation. Settings are defined in `observice/config.py`: adding a field there with `setting(...)` is all it takes for it to appear in the panel, validated against its type, range and options.

## Development

- `observice/main.py` runs one capture pipeline (`capture.py`) that feeds the RTSP stream, change detection (`motion.py`) and clips (`recordings.py`), plus Discord (`discord_notify.py`) and MQTT (`mqtt_bridge.py`); `observice/panel.py` is the web panel.
- Work on the panel without a Pi or camera: `python -m observice.panel --demo`, then open http://localhost:8080 (simulated feed, logs and changes; needs `ffmpeg` for sample clips).
- GStreamer/PyGObject aren't pip packages — see `assets/requirements.txt` for the apt/brew commands.
- Tests: `pip install -r assets/requirements.txt pytest && pytest tests`
- `scripts/download_discord_images.py --channel-id <id> --out ./downloads` downloads every image from a Discord channel.

### Releasing

Push a `v*` tag (`git tag v0.2.0 && git push --tags`). GitHub Actions builds the image with [CustomPiOS](https://github.com/guysoft/CustomPiOS) from `image/` (~15 min) and publishes a release with the image and the Imager repository file. `image/build.sh` builds the image locally with Docker.
