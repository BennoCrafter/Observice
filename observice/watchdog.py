import os
import time
from typing import Callable


def _identity(path: str) -> int | None:
    try:
        return os.stat(path).st_ino
    except FileNotFoundError:
        return None


def watch_device(path: str, on_lost: Callable[[], None], interval: float = 2.0) -> None:
    """Blocks until the device node disappears or is recreated, then calls on_lost().

    A USB reset re-creates /dev/videoN within seconds; GStreamer keeps the dead
    handle and never recovers, so polling for "missing" alone would miss it.
    A recreated node gets a new inode, which is what we compare.
    """
    start = _identity(path)
    while _identity(path) == start:
        time.sleep(interval)
    on_lost()
