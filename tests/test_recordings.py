import tempfile
from datetime import datetime
from pathlib import Path

from observice.recordings import delete_event, list_events, new_event_id, prune, write_event


def test_events_roundtrip_paging_delete_prune():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        now = datetime(2026, 11, 28, 16, 0, 0)
        first = new_event_id(d, now)
        write_event(d, {"id": first})
        second = new_event_id(d, now)  # same second
        assert second == f"{first}-2"
        write_event(d, {"id": second})
        old = new_event_id(d, datetime(2026, 11, 1, 8, 0, 0))
        write_event(d, {"id": old})
        (d / f"{old}.jpg").write_bytes(b"x")

        assert [e["id"] for e in list_events(d)] == [second, first, old]
        assert [e["id"] for e in list_events(d, before=first)] == [old]
        assert [e["id"] for e in list_events(d, limit=1)] == [second]

        assert prune(d, keep_days=7, now=now) == 1
        assert not (d / f"{old}.jpg").exists()

        assert delete_event(d, first)
        assert not delete_event(d, "../config")  # ids are validated before touching files
        assert [e["id"] for e in list_events(d)] == [second]


if __name__ == "__main__":
    test_events_roundtrip_paging_delete_prune()
    print("ok")
