"""Change events on disk: <id>.json (metadata), <id>.jpg (snapshot), <id>.mp4 (clip, optional).

Written by the camera service, read and deleted by the panel.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

RECORDINGS_DIR = Path("recordings")
ID_PATTERN = re.compile(r"^\d{8}-\d{6}(-\d+)?$")  # 20261128-162233, -2 when two start in the same second
EXTENSIONS = (".json", ".jpg", ".mp4")


def new_event_id(directory: Path, now: datetime) -> str:
    base = now.strftime("%Y%m%d-%H%M%S")
    event_id, n = base, 1
    while (directory / f"{event_id}.json").exists():
        n += 1
        event_id = f"{base}-{n}"
    return event_id


def write_event(directory: Path, event: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{event['id']}.json.tmp"
    tmp.write_text(json.dumps(event))
    tmp.replace(directory / f"{event['id']}.json")  # atomic: the panel never reads half a file


def list_events(directory: Path, before: str | None = None, limit: int = 20) -> list[dict]:
    """Newest first; `before` is the id of the last event of the previous page."""
    ids = sorted((p.stem for p in directory.glob("*.json") if ID_PATTERN.match(p.stem)), reverse=True)
    if before:
        ids = [i for i in ids if i < before]
    events = []
    for event_id in ids[:limit]:
        try:
            events.append(json.loads((directory / f"{event_id}.json").read_text()))
        except (OSError, ValueError):
            continue  # deleted or being replaced right now
    return events


def delete_event(directory: Path, event_id: str) -> bool:
    if not ID_PATTERN.match(event_id):
        return False
    for ext in EXTENSIONS:
        (directory / f"{event_id}{ext}").unlink(missing_ok=True)
    return True


def prune(directory: Path, keep_days: int, now: datetime) -> int:
    cutoff = (now - timedelta(days=keep_days)).strftime("%Y%m%d-%H%M%S")
    old = [p.stem for p in directory.glob("*.json") if ID_PATTERN.match(p.stem) and p.stem < cutoff]
    for event_id in old:
        delete_event(directory, event_id)
    return len(old)


def close_unfinished_events(directory: Path) -> None:
    # A crash or restart mid-event leaves end=None; without this it would show as in progress forever.
    for event in list_events(directory, limit=5):
        if event["end"] is None:
            event["end"] = datetime.fromtimestamp((directory / f"{event['id']}.json").stat().st_mtime).isoformat(timespec="seconds")
            write_event(directory, event)
