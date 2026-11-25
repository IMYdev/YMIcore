"""core.db read cache: reuse, invalidation by any writer, failure handling."""

import asyncio
import json
import os
import time

import pytest

from core import db as dbmod
from core.db import IMYDB


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dbmod.clear_cache()
    yield
    dbmod.clear_cache()


def _age(path, seconds=10):
    """Backdate a file so its cached copy is trusted (not 'racy')."""
    past = time.time() - seconds
    os.utime(path, (past, past))


def _count_parses(monkeypatch):
    calls = []
    real = json.load

    def counting(f, *a, **k):
        calls.append(1)
        return real(f, *a, **k)

    monkeypatch.setattr("core.imysdb.imydb.json.load", counting)
    return calls


def test_unchanged_file_is_parsed_once(monkeypatch):
    IMYDB("runtime/x.json").set("a", 1)
    _age("runtime/x.json")
    parses = _count_parses(monkeypatch)
    first = IMYDB("runtime/x.json")
    second = IMYDB("runtime/x.json")
    assert first.get("a") == second.get("a") == 1
    assert len(parses) == 1
    assert first.data is second.data


def test_recently_written_file_is_reread_then_trusted(monkeypatch):
    IMYDB("runtime/x.json").set("a", 1)
    parses = _count_parses(monkeypatch)
    IMYDB("runtime/x.json")
    assert len(parses) == 1  # mtime too fresh to trust a stamp match
    time.sleep(dbmod.RACY_NS / 1e9 * 2)
    IMYDB("runtime/x.json")  # read well after the write: cached from here on
    IMYDB("runtime/x.json")
    IMYDB("runtime/x.json")
    assert len(parses) == 2


def test_atomic_write_from_another_process_is_seen():
    IMYDB("runtime/x.json").set("a", 1)
    _age("runtime/x.json")
    assert IMYDB("runtime/x.json").get("a") == 1
    tmp = "runtime/x.json.tmp"
    with open(tmp, "w") as f:
        json.dump({"a": 2}, f)
    os.replace(tmp, "runtime/x.json")
    assert IMYDB("runtime/x.json").get("a") == 2


def test_same_size_in_place_edit_right_after_read_is_seen():
    IMYDB("runtime/x.json").set("a", "aaaa")
    assert IMYDB("runtime/x.json").get("a") == "aaaa"
    with open("runtime/x.json", "w") as f:  # same inode, same size, same tick
        json.dump({"a": "bbbb"}, f, indent=4)
        f.write("\n")
    assert IMYDB("runtime/x.json").get("a") == "bbbb"


def test_write_through_one_instance_visible_to_new_ones():
    IMYDB("runtime/x.json").set("a", 1)
    _age("runtime/x.json")
    IMYDB("runtime/x.json")
    IMYDB("runtime/x.json").set("b", 2)
    assert IMYDB("runtime/x.json").data == {"a": 1, "b": 2}
    with open("runtime/x.json") as f:
        assert json.load(f) == {"a": 1, "b": 2}


def test_failed_save_drops_cached_copy(monkeypatch):
    IMYDB("runtime/x.json").set("a", 1)
    _age("runtime/x.json")
    db = IMYDB("runtime/x.json")

    def boom(self):
        raise OSError("disk full")

    with monkeypatch.context() as mp:
        mp.setattr(IMYDB, "_write", boom)
        with pytest.raises(OSError):
            db.set("a", 99)  # mutates the shared dict, then fails to save
    assert IMYDB("runtime/x.json").get("a") == 1  # back to what is on disk


def test_corrupt_file_still_quarantined():
    os.makedirs("runtime", exist_ok=True)
    with open("runtime/x.json", "w") as f:
        f.write("{not json")
    db = IMYDB("runtime/x.json")
    assert db.data == {}
    assert any(name.startswith("x.json.corrupt-") for name in os.listdir("runtime"))


def test_missing_file_is_created_like_upstream():
    db = IMYDB("runtime/new/x.json")
    assert db.data == {}
    assert os.path.exists("runtime/new/x.json")


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(dbmod, "MAX_CACHED_FILES", 5)
    for i in range(20):
        IMYDB(f"runtime/f{i}.json").set("i", i)
    assert len(dbmod._CACHE) <= 5


def test_compact_format_loads_in_upstream_imydb():
    from core.imysdb.imydb import IMYDB as Upstream
    IMYDB("runtime/c.json", indent=None).set("users", {"1": {"name": "Ann"}})
    with open("runtime/c.json") as f:
        raw = f.read()
    assert "\n    " not in raw and '":' in raw
    assert Upstream("runtime/c.json").get("users.1.name") == "Ann"


def test_panel_filter_edit_reaches_bot_on_next_message(monkeypatch):
    from info import bot
    from modules.filters import reply_to_filter
    from core.storage import group_path

    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)
    chat = type("Chat", (), {"id": -55, "title": "T", "type": "group"})()

    def msg(text):
        return type("Msg", (), {"text": text, "chat": chat,
                                "from_user": type("U", (), {"id": 1})(),
                                "message_thread_id": None})()

    IMYDB(group_path("filters", -55)).set("filters", {"hi": {"type": "text", "data": "aaaa"}})
    asyncio.run(reply_to_filter(msg("hi")))

    # The panel (or another process) rewrites the file in place, same size.
    with open(group_path("filters", -55), "w") as f:
        json.dump({"filters": {"hi": {"type": "text", "data": "bbbb"}}}, f, indent=4)
        f.write("\n")
    from modules import filters as _f
    _f._recent_triggers.clear()
    asyncio.run(reply_to_filter(msg("hi")))
    assert sent == ["aaaa", "bbbb"]


def test_filter_patterns_not_recompiled_while_file_unchanged(monkeypatch):
    from modules import filters as _f
    from core.group_settings import add_filter
    from core.storage import group_path

    add_filter(-56, "hello", body="x")
    _age(group_path("filters", -56))
    compiled = []
    real = _f._filter_pattern
    monkeypatch.setattr(_f, "_filter_pattern", lambda k: compiled.append(k) or real(k))
    for _ in range(5):
        _f._compiled(-56)
    assert compiled == ["hello"]
    add_filter(-56, "world", body="y")
    _f._compiled(-56)
    assert sorted(compiled) == ["hello", "hello", "world"]


def test_banned_check_reads_only_banned_list(monkeypatch):
    from core import groups
    groups.ban_group(-1)
    monkeypatch.setattr(groups, "group_title", lambda gid: pytest.fail("title lookup"))
    assert groups.is_banned(-1)
    assert not groups.is_banned(-2)
    assert groups.banned_ids() == {"-1"}
