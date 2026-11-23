import asyncio
import logging
from typing import Awaitable, Callable

import cv2
import numpy as np

from observice.config import MotionConfig

logger = logging.getLogger("observice")

# Consecutive unreadable polls before giving up; the camera is stalled, and a
# service restart (systemd Restart=on-failure) is what brings it back.
MAX_FAILED_READS = 3


def frame_changed(prev: np.ndarray, curr: np.ndarray, threshold: float) -> bool:
    if prev.shape != curr.shape:
        return True
    diff = cv2.absdiff(prev, curr)
    return float(diff.mean()) > threshold


async def run_motion_loop(
    stream_url: str,
    motion: MotionConfig,
    on_change: Callable[[np.ndarray], Awaitable[None]],
) -> None:
    """Polls the RTSP stream on an interval and calls on_change() when the frame
    differs from the previous one by more than motion.threshold.

    # ponytail: reopens the RTSP capture every poll instead of holding it open.
    # Simple and avoids stale-buffer issues at minute-scale intervals; if
    # check_interval needs to drop below ~5s, switch to a persistent
    # cv2.VideoCapture read in a background thread instead.
    """
    prev_frame = None
    failed_reads = 0
    while True:
        if motion.enabled:
            cap = cv2.VideoCapture(stream_url)
            ok, frame = cap.read()
            cap.release()
            if ok:
                failed_reads = 0
                if prev_frame is not None and frame_changed(prev_frame, frame, motion.threshold):
                    logger.info("Motion detected")
                    await on_change(frame)
                prev_frame = frame
            else:
                failed_reads += 1
                logger.warning("Could not read frame from %s (%d/%d)", stream_url, failed_reads, MAX_FAILED_READS)
                if failed_reads >= MAX_FAILED_READS:
                    raise RuntimeError("Camera stream stalled, exiting so systemd restarts the service")
        await asyncio.sleep(motion.check_interval)
