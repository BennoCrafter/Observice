#!/bin/bash
# Builds the Observice SD card image locally with the CustomPiOS Docker image.
#   image/build.sh                      # newest v* release
#   OBSERVICE_REF=main image/build.sh   # any git ref
# Needs privileged Docker with loop devices (Linux; Docker Desktop on macOS may or may not cope).
# Output: image/src/workspace/*.img
set -euo pipefail

SRC="$(cd "$(dirname "$0")/src" && pwd)"
docker run --rm --privileged -v /dev:/dev -v "$SRC:/distro" \
    -e OBSERVICE_REF="${OBSERVICE_REF:-}" \
    ghcr.io/guysoft/custompios:devel build --download --board raspberrypiarm64
