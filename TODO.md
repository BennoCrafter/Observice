# TODO

- [ ] Test the Docker apt-vs-pip `python3-gi` version mismatch on actual Raspberry Pi OS (see Dockerfile comment); drop Option A (systemd) from the README if it turns out fine.
- [ ] Verify RPi CSI camera (not just USB/v4l2) works with the `v4l2src` pipeline in `observice/capture.py`, or switch to `libcamerasrc`.
