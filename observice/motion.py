import asyncio
import logging
from typing import Awaitable, Callable

import cv2
import numpy as np

from observice.config import MotionConfig

logger = logging.getLogger("observice")


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
    while True:
        if motion.enabled:
            cap = cv2.VideoCapture(stream_url)
            ok, frame = cap.read()
            cap.release()
            if ok:
                if prev_frame is not None and frame_changed(prev_frame, frame, motion.threshold):
                    logger.info("Motion detected")
                    await on_change(frame)
                prev_frame = frame
            else:
                logger.warning("Could not read frame from %s", stream_url)
        await asyncio.sleep(motion.check_interval)
