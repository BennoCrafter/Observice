#!/bin/bash
# Installs/updates Observice as a systemd service on Raspberry Pi OS.
#   curl -fsSL https://raw.githubusercontent.com/BennoCrafter/Observice/main/install-pi.sh | bash
# Run as your normal user (not root); it uses sudo where needed.
# Image build (image/src/modules/observice) runs it as root with:
#   OBSERVICE_USER=observice OBSERVICE_REF=<tag> install-pi.sh --no-start
# OBSERVICE_USER: service user, created if missing. OBSERVICE_REF: git ref, default newest v* release.
set -euo pipefail

REPO=https://github.com/BennoCrafter/observice
DIR=/opt/observice
ME=$(whoami)
# Re-runs keep whoever owns an existing install (e.g. the image's "observice" user) as the service user.
USER_NAME=${OBSERVICE_USER:-$(stat -c %U "$DIR" 2>/dev/null || echo "$ME")}
NO_START=
[ "${1:-}" = --no-start ] && NO_START=1

if [ "$USER_NAME" = root ]; then
    echo "Run as your normal user, not root/sudo — the service runs as that user." >&2
    exit 1
fi

if ! id "$USER_NAME" &>/dev/null; then
    # Home is not $DIR: Imager moves an existing account's home if its login user has the same name.
    sudo useradd --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin "$USER_NAME"
fi

echo "📦 Installing system packages..."
sudo apt-get update
sudo apt-get install -y git python3-venv python3-gi gir1.2-gst-rtsp-server-1.0 \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly

# Owned by whoever runs this while installing, handed to the service user at the end.
sudo mkdir -p "$DIR"
sudo chown -R "$ME": "$DIR"
if [ -d "$DIR/.git" ]; then
    echo "🔄 Updating $DIR..."
    git -C "$DIR" fetch --quiet --tags --force
else
    echo "⬇️  Cloning into $DIR..."
    git clone "$REPO" "$DIR"
fi

# Follow GitHub releases; until the first v* tag exists, stay on main.
REF=${OBSERVICE_REF:-$(git -C "$DIR" tag -l 'v*' --sort=-v:refname | head -1)}
if [ -n "$REF" ]; then
    echo "📌 Checking out $REF..."
    git -C "$DIR" checkout --quiet "$REF"
else
    git -C "$DIR" pull --ff-only
fi

echo "🐍 Setting up venv..."
# Pi OS blocks system-wide pip (PEP 668); --system-site-packages keeps apt's python3-gi importable.
python3 -m venv --system-site-packages "$DIR/venv"
"$DIR/venv/bin/pip" install -r "$DIR/assets/requirements.txt"

[ -f "$DIR/assets/config.yaml" ] || cp "$DIR/assets/default_config.yaml" "$DIR/assets/config.yaml"
# The service (and panel updates) write config/images/logs and run git here.
sudo chown -R "$USER_NAME": "$DIR"

if ! id -nG "$USER_NAME" | grep -qw video; then
    sudo usermod -aG video "$USER_NAME"
    echo "⚠️  Added $USER_NAME to the video group — reboot for camera access."
fi

echo "⚙️  Installing systemd services..."
for unit in observice observice-panel; do
    sed "s/^User=.*/User=$USER_NAME/" "$DIR/deploy/$unit.service" | sudo tee /etc/systemd/system/$unit.service >/dev/null
done

# Lets the web panel restart the services without a password (and nothing else).
SUDOERS=$(mktemp)
cat > "$SUDOERS" <<EOS
$USER_NAME ALL=(root) NOPASSWD: /usr/bin/systemctl restart observice, /usr/bin/systemctl --no-block restart observice-panel
EOS
sudo visudo -cf "$SUDOERS" >/dev/null
sudo install -m 0440 -o root -g root "$SUDOERS" /etc/sudoers.d/observice-panel
rm "$SUDOERS"

sudo systemctl enable observice observice-panel
if [ -n "$NO_START" ]; then
    echo "✅ Installed ${REF:-main}; services start on next boot."
    exit 0
fi
sudo systemctl daemon-reload
sudo systemctl restart observice observice-panel

echo "✅ Done. Dashboard: http://$(hostname -I | cut -d' ' -f1) (set panel.password in $DIR/assets/config.yaml)"
echo "   Logs: journalctl -u observice -f"
