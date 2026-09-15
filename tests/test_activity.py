import os
from datetime import date, timedelta

import core.activity as activity_mod
from core.activity import log_event, read_events, stats, prune


def test_log_event_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_event(
        "command",
        chat_id=-1001, chat_name="Test Chat",
        user_id=7, user_name="rhys",
        detail="help",
    )
    events = read_events()
    assert len(events) == 1
    e = events[0]
    assert e["type"] == "command"
    assert e["chat_id"] == "-1001"
    assert e["chat_name"] == "Test Chat"
    assert e["user_id"] == "7"
    assert e["user_name"] == "rhys"
    assert e["detail"] == "help"


def test_unknown_event_type_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        log_event("nope")
        assert False, "Expected ValueError for unknown event type"
    except ValueError:
        pass


def test_stats_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_event("command", chat_id=-1001)
    log_event("command", chat_id=-1001)
    log_event("filter_trigger", chat_id=-1001)
    log_event("greeting", chat_id=-1002)
    counts = stats()
    assert counts["command"] == 2
    assert counts["filter_trigger"] == 1
    assert counts["greeting"] == 1
    assert sum(counts.values()) == 4
    gid_counts = stats(chat_id=-1002)
    assert gid_counts["greeting"] == 1
    assert sum(gid_counts.values()) == 1


def test_prune_removes_old_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    activity_mod._ensure_dir()
    activity_mod._last_pruned = None
    old_day = date.today() - timedelta(days=activity_mod.RETENTION_DAYS + 1)
    with open(activity_mod._file_for_day(old_day), "w") as fh:
        fh.write("{}\n")
    recent_day = date.today() - timedelta(days=activity_mod.RETENTION_DAYS - 1)
    with open(activity_mod._file_for_day(recent_day), "w") as fh:
        fh.write("{}\n")
    prune()
    remaining = set(os.listdir(activity_mod.ACTIVITY_DIR))
    assert old_day.isoformat() + ".jsonl" not in remaining
    assert recent_day.isoformat() + ".jsonl" in remaining


def test_read_events_respects_chat_filter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_event("command", chat_id=-1001)
    log_event("command", chat_id=-2002)
    filtered = read_events(chat_id=-1001)
    assert len(filtered) == 1
    assert filtered[0]["chat_id"] == "-1001"
