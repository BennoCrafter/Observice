import cv2
import numpy as np

# Per-pixel brightness difference (0-255) that counts a pixel as changed; filters sensor noise.
PIXEL_DELTA = 25


def changed_percent(prev: np.ndarray, curr: np.ndarray, ignore_border_percent: float = 0.0) -> float:
    """Share (0-100) of pixels that differ noticeably between two grayscale frames."""
    if prev.shape != curr.shape:
        return 100.0
    h, w = curr.shape[:2]
    by, bx = int(h * ignore_border_percent / 100), int(w * ignore_border_percent / 100)
    prev, curr = prev[by:h - by, bx:w - bx], curr[by:h - by, bx:w - bx]
    if curr.size == 0:
        return 0.0
    # Blur first so single noisy pixels and compression artefacts don't count.
    diff = cv2.absdiff(cv2.GaussianBlur(prev, (5, 5), 0), cv2.GaussianBlur(curr, (5, 5), 0))
    return float(np.count_nonzero(diff > PIXEL_DELTA)) * 100 / diff.size


class EventTracker:
    """Turns a stream of per-frame "changed?" answers into events.

    An event starts on the first changed frame and ends after quiet_seconds without
    change, or when it reaches max_seconds (the next change then starts a new one).
    """

    def __init__(self, quiet_seconds: float, max_seconds: float):
        self.quiet_seconds = quiet_seconds
        self.max_seconds = max_seconds
        self.started_at: float | None = None
        self.last_change = 0.0

    @property
    def active(self) -> bool:
        return self.started_at is not None

    def update(self, now: float, changed: bool) -> str | None:
        """Returns "start", "end" or None."""
        if not self.active:
            if changed:
                self.started_at = self.last_change = now
                return "start"
            return None
        if changed:
            self.last_change = now
        if now - self.last_change >= self.quiet_seconds or now - self.started_at >= self.max_seconds:
            self.started_at = None
            return "end"
        return None
