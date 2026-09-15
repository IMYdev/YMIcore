import json
import os
from datetime import date, datetime, timedelta

ACTIVITY_DIR = "runtime/activity"
RETENTION_DAYS = 7

EVENT_TYPES = (
    "command",
    "filter_trigger",
    "note_fetch",
    "greeting",
    "farewell",
    "captcha_pass",
    "captcha_fail",
    "panel_action",
)

_last_pruned = None


def _ensure_dir() -> None:
    os.makedirs(ACTIVITY_DIR, exist_ok=True)


def _file_for_day(day: date) -> str:
    return os.path.join(ACTIVITY_DIR, f"{day.isoformat()}.jsonl")


def _file_date(filename: str) -> date | None:
    try:
        return date.fromisoformat(os.path.splitext(os.path.basename(filename))[0])
    except ValueError:
        return None


def prune() -> None:
    cutoff = date.today() - timedelta(days=RETENTION_DAYS)
    if not os.path.isdir(ACTIVITY_DIR):
        return
    for name in os.listdir(ACTIVITY_DIR):
        day = _file_date(name)
        if day is not None and day < cutoff:
            try:
                os.remove(os.path.join(ACTIVITY_DIR, name))
            except OSError:
                pass


def user_label(user) -> str | None:
    if user is None:
        return None
    name = " ".join(
        p for p in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if p
    )
    return name or getattr(user, "username", None)


def chat_label(chat) -> str | None:
    if chat is None:
        return None
    return (
        getattr(chat, "title", None)
        or getattr(chat, "username", None)
        or getattr(chat, "first_name", None)
    )


def log_event(event_type, *, chat_id=None, chat_name=None, user_id=None, user_name=None, detail=None) -> None:
    global _last_pruned
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown activity event type: {event_type!r}")
    _ensure_dir()
    today = date.today()
    if _last_pruned != today:
        prune()
        _last_pruned = today
    record = {
        "ts": datetime.now().timestamp(),
        "type": event_type,
        "chat_id": None if chat_id is None else str(chat_id),
        "chat_name": chat_name,
        "user_id": None if user_id is None else str(user_id),
        "user_name": user_name,
        "detail": detail,
    }
    with open(_file_for_day(today), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _iter_records(days=RETENTION_DAYS):
    if not os.path.isdir(ACTIVITY_DIR):
        return
    start = date.today() - timedelta(days=days - 1)
    files = []
    for name in os.listdir(ACTIVITY_DIR):
        day = _file_date(name)
        if day is not None and start <= day <= date.today():
            files.append(name)
    files.sort(reverse=True)
    for name in files:
        try:
            with open(os.path.join(ACTIVITY_DIR, name), encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def read_events(days=RETENTION_DAYS, event_type=None, chat_id=None, limit=None) -> list:
    chat = None if chat_id is None else str(chat_id)
    results = []
    for record in _iter_records(days=days):
        if event_type and record.get("type") != event_type:
            continue
        if chat is not None and record.get("chat_id") != chat:
            continue
        results.append(record)
        if limit and len(results) >= limit:
            break
    return results


def stats(days=RETENTION_DAYS, chat_id=None) -> dict:
    chat = None if chat_id is None else str(chat_id)
    counts = {event_type: 0 for event_type in EVENT_TYPES}
    for record in _iter_records(days=days):
        if chat is not None and record.get("chat_id") != chat:
            continue
        event_type = record.get("type")
        if event_type in counts:
            counts[event_type] += 1
    return counts