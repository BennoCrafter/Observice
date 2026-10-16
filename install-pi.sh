#!/bin/bash
# Installs/updates Observice as a systemd service on Raspberry Pi OS.
#   curl -fsSL https://raw.githubusercontent.com/BennoCrafter/Observice/main/install-pi.sh | bash
# Run as your normal user (not root); it uses sudo where needed.
set -euo pipefail

REPO=https://github.com/BennoCrafter/observice
DIR=/opt/observice
USER_NAME=$(whoami)

if [ "$USER_NAME" = root ]; then
    echo "Run as your normal user, not root/sudo — the service runs as that user." >&2
    exit 1
fi

echo "📦 Installing system packages..."
sudo apt-get update
sudo apt-get install -y git python3-venv python3-gi gir1.2-gst-rtsp-server-1.0 \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly

# Own $DIR so the service (and you) can write config/images/logs without sudo.
if [ -d "$DIR/.git" ]; then
    echo "🔄 Updating $DIR..."
    sudo chown -R "$USER_NAME": "$DIR"
    git -C "$DIR" pull --ff-only
else
    echo "⬇️  Cloning into $DIR..."
    sudo mkdir -p "$DIR"
    sudo chown "$USER_NAME": "$DIR"
    git clone "$REPO" "$DIR"
fi

echo "🐍 Setting up venv..."
# Pi OS blocks system-wide pip (PEP 668); --system-site-packages keeps apt's python3-gi importable.
python3 -m venv --system-site-packages "$DIR/venv"
"$DIR/venv/bin/pip" install -r "$DIR/assets/requirements.txt"

[ -f "$DIR/assets/config.yaml" ] || cp "$DIR/assets/default_config.yaml" "$DIR/assets/config.yaml"

if ! id -nG "$USER_NAME" | grep -qw video; then
    sudo usermod -aG video "$USER_NAME"
    echo "⚠️  Added $USER_NAME to the video group — reboot for camera access."
fi

echo "⚙️  Installing systemd service..."
sed "s/^User=.*/User=$USER_NAME/" "$DIR/deploy/observice.service" | sudo tee /etc/systemd/system/observice.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable observice
sudo systemctl restart observice

echo "✅ Done. Edit $DIR/assets/config.yaml, then: sudo systemctl restart observice"
echo "   Logs: journalctl -u observice -f"
