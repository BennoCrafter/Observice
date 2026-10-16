FROM python:3.12-slim

# GStreamer + PyGObject bindings aren't pip-installable; pull them from apt.
# ponytail: apt's python3-gi targets the distro's system Python, which can be
# a different minor version than this image's /usr/local Python 3.12 — if
# `import gi` fails at runtime, that version mismatch is why. The systemd
# install path in deploy/observice.service (running directly on Raspberry Pi
# OS's own Python) sidesteps this entirely and is the more reliable option.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-gi \
    gir1.2-gst-rtsp-server-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY assets/requirements.txt assets/requirements.txt
RUN pip install --no-cache-dir -r assets/requirements.txt

COPY . .

CMD ["python", "-m", "observice.main"]
