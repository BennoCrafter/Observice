import tempfile
import threading
from pathlib import Path

from observice.watchdog import watch_device


def _run_watch(path: Path, change) -> bool:
    lost = threading.Event()
    thread = threading.Thread(target=watch_device, args=(str(path), lost.set, 0.01), daemon=True)
    thread.start()
    assert not lost.wait(0.05)  # unchanged device: keeps watching
    change()
    return lost.wait(1)


def test_detects_removed_and_recreated_device():
    with tempfile.TemporaryDirectory() as tmp:
        dev = Path(tmp, "video0")
        dev.touch()
        assert _run_watch(dev, dev.unlink)

        def recreate():
            # rename-over swaps in a new inode at once, like a fast USB re-enumeration
            Path(tmp, "new").touch()
            Path(tmp, "new").replace(dev)

        dev.touch()
        assert _run_watch(dev, recreate)


if __name__ == "__main__":
    test_detects_removed_and_recreated_device()
    print("ok")
