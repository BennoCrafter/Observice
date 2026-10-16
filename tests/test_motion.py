import numpy as np

from observice.motion import frame_changed


def test_identical_frames_not_changed():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert frame_changed(frame, frame.copy(), threshold=25) is False


def test_different_frames_changed():
    prev = np.zeros((10, 10, 3), dtype=np.uint8)
    curr = np.full((10, 10, 3), 255, dtype=np.uint8)
    assert frame_changed(prev, curr, threshold=25) is True


if __name__ == "__main__":
    test_identical_frames_not_changed()
    test_different_frames_changed()
    print("ok")
