import numpy as np

from observice.motion import EventTracker, changed_percent


def test_changed_percent():
    frame = np.zeros((100, 100), dtype=np.uint8)
    assert changed_percent(frame, frame.copy()) == 0.0

    moved = frame.copy()
    moved[40:60, 40:60] = 255  # a 20x20 object = 4% of the picture
    assert 2 < changed_percent(frame, moved) < 6

    edge = frame.copy()
    edge[:, :10] = 255  # change only in the left 10%
    assert changed_percent(frame, edge) > 5
    assert changed_percent(frame, edge, ignore_border_percent=15) == 0.0

    assert changed_percent(frame, np.zeros((50, 50), dtype=np.uint8)) == 100.0


def test_event_tracker_start_quiet_end():
    t = EventTracker(quiet_seconds=10, max_seconds=60)
    assert t.update(0, False) is None
    assert t.update(1, True) == "start"
    assert t.update(5, True) is None
    assert t.update(14, False) is None  # 9 s quiet
    assert t.update(15, False) == "end"  # 10 s quiet
    assert not t.active


def test_event_tracker_caps_length():
    t = EventTracker(quiet_seconds=10, max_seconds=60)
    assert t.update(0, True) == "start"
    assert t.update(30, True) is None
    assert t.update(60, True) == "end"
    assert t.update(60.5, True) == "start"  # still moving: next event right away


if __name__ == "__main__":
    test_changed_percent()
    test_event_tracker_start_quiet_end()
    test_event_tracker_caps_length()
    print("ok")
