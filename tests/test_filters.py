"""Filters module fixes: matching, failure isolation, storage, flood control."""

import asyncio
import time
import pytest

from info import bot
from modules.filters import set_filter, remove_filter, get_filters, reply_to_filter
from core.group_settings import (
    MAX_FILTER_KEYWORD_LENGTH, MAX_FILTERS_PER_CHAT,
    add_filter, read_filters, validate_filter_keyword, normalize_filter_keyword,
)
from core.db import IMYDB


def make_msg(text, chat_id, thread_id=None):
    chat = type("Chat", (), {
        "id": chat_id, "title": "T", "username": None, "first_name": None,
        "type": "private" if chat_id == 100 else "group",
    })()
    return type("Msg", (), {
        "text": text, "chat": chat, "from_user": type("User", (), {"id": 999})(),
        "message_thread_id": thread_id,
    })()


def make_reply_msg(**kwargs):
    defaults = {
        "text": None, "entities": None, "caption": None, "caption_entities": None,
        "sticker": None, "photo": None, "document": None, "video": None,
        "audio": None, "animation": None, "voice": None,
    }
    defaults.update(kwargs)
    return type("Msg", (), defaults)()


def _seed(gid, filters):
    IMYDB(f"runtime/filters/{gid}_filters").set("filters", filters)


def _clear_cooldown():
    from modules import filters as _f

    _f._recent_triggers.clear()


async def _allow(*args, **kwargs):
    return True


@pytest.fixture(autouse=True)
def _clean_filters(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(100, {})
    _seed(200, {})
    _clear_cooldown()
    yield
    _clear_cooldown()


# ----------------------------------------------------------------------
# 1. Keyword matching: punctuation, multi-word, case, regex metacharacters
# ----------------------------------------------------------------------
def test_keyword_punctuation_and_multiword(monkeypatch):
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {"hello": {"type": "text", "data": "hi there"}})

    asyncio.run(reply_to_filter(make_msg("hello!", 200)))
    assert sent == ["hi there"]

    _clear_cooldown()
    asyncio.run(reply_to_filter(make_msg("Hello, all", 200)))
    assert sent == ["hi there", "hi there"]

    _clear_cooldown()
    _seed(200, {"good morning": {"type": "text", "data": "mornin'"}})
    asyncio.run(reply_to_filter(make_msg("good morning everyone", 200)))
    assert sent[-1].startswith("mornin")


def test_keyword_case_insensitive(monkeypatch):
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {"hello": {"type": "text", "data": "hi"}})

    asyncio.run(reply_to_filter(make_msg("HeLlO", 200)))
    assert sent == ["hi"]


def test_keyword_regex_metacharacters(monkeypatch):
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {
        "c++": {"type": "text", "data": "cpp"},
        "a.b": {"type": "text", "data": "dot"},
    })

    asyncio.run(reply_to_filter(make_msg("I like c++", 200)))
    assert sent == ["cpp"]

    _clear_cooldown()
    asyncio.run(reply_to_filter(make_msg("version a.b is out", 200)))
    assert sent == ["cpp", "dot"]


def test_keyword_no_match_inside_longer_word(monkeypatch):
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {"rules": {"type": "text", "data": "rules"}})

    asyncio.run(reply_to_filter(make_msg("check the ruleset", 200)))
    assert sent == []


def test_keyword_normalization_on_save(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append(text)

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.filters.is_privileged", _allow)

    cmd = make_msg("/filter Good   Morning", 200)
    cmd.reply_to_message = make_reply_msg(text="mornin'")

    asyncio.run(set_filter(cmd))
    assert "good morning" in replied[0]
    assert "saved" in replied[0]


# ----------------------------------------------------------------------
# 2. Broken filter fails silently; next matching filter still fires
# ----------------------------------------------------------------------
def test_broken_filter_silent_next_fires(monkeypatch):
    photo_attempts = []
    sent = []

    async def fake_send_photo(chat_id, photo, **kw):
        photo_attempts.append(photo)
        raise RuntimeError("bad file_id")

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    async def fake_log_error(*args, **kwargs):
        return None

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    monkeypatch.setattr(bot, "send_message", fake_send_message)
    monkeypatch.setattr("modules.filters.log_error", fake_log_error)

    _seed(200, {
        "broken": {"type": "photo", "data": "BAD_FILE_ID"},
        "working": {"type": "text", "data": "ok"},
    })

    asyncio.run(reply_to_filter(make_msg("broken working", 200)))

    assert photo_attempts == ["BAD_FILE_ID"]
    assert sent == ["ok"]


# ----------------------------------------------------------------------
# 3. Unsupported reply types rejected; GIF and voice accepted
# ----------------------------------------------------------------------
def test_unsupported_reply_type_rejected(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append(text)

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.filters.is_privileged", _allow)

    # document is supported
    cmd = make_msg("/filter doc", 200)
    cmd.reply_to_message = make_reply_msg(document=type("Doc", (), {"file_id": "DOC1"})())
    asyncio.run(set_filter(cmd))
    assert "saved" in replied[-1].lower()

    # animation (GIF) is supported
    cmd = make_msg("/filter gif", 200)
    cmd.reply_to_message = make_reply_msg(animation=type("Anim", (), {"file_id": "ANIM1"})())
    asyncio.run(set_filter(cmd))
    assert "saved" in replied[-1].lower()

    # voice is supported
    cmd = make_msg("/filter voice", 200)
    cmd.reply_to_message = make_reply_msg(voice=type("Voice", (), {"file_id": "VOICE1"})())
    asyncio.run(set_filter(cmd))
    assert "saved" in replied[-1].lower()

    # unsupported (nothing set) is rejected
    cmd = make_msg("/filter loc", 200)
    cmd.reply_to_message = make_reply_msg()
    asyncio.run(set_filter(cmd))
    assert "isn't supported" in replied[-1]

    # empty text is rejected
    cmd = make_msg("/filter empty", 200)
    cmd.reply_to_message = make_reply_msg(text="")
    asyncio.run(set_filter(cmd))
    assert "isn't supported" in replied[-1]


def test_build_reply_media_types():
    from core.replies import build_reply

    msg = make_reply_msg(voice=type("Voice", (), {"file_id": "VOICE1"})())
    reply = build_reply(msg)
    assert reply["type"] == "voice"
    assert reply["data"] == "VOICE1"

    msg = make_reply_msg(
        animation=type("Anim", (), {"file_id": "ANIM1"})(),
        document=type("Doc", (), {"file_id": "DOC1"})(),
    )
    reply = build_reply(msg)
    assert reply["type"] == "animation"
    assert reply["data"] == "ANIM1"


# ----------------------------------------------------------------------
# 4. /filist: HTML escaping; multiple messages under 4096
# ----------------------------------------------------------------------
def test_filist_html_escaping(monkeypatch):
    captured = []

    async def fake_send_message(chat_id, text, **kw):
        captured.append((text, kw.get("parse_mode")))

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {
        "back`tick": {"type": "text", "data": "x"},
        "<b>bold</b>": {"type": "text", "data": "y"},
        "plain": {"type": "text", "data": "z"},
    })

    asyncio.run(get_filters(make_msg("list", 200)))

    assert len(captured) == 1
    text, pm = captured[0]
    assert pm == "HTML"
    assert "back`tick" in text
    assert "&lt;b&gt;bold&lt;/b&gt;" in text


def test_filist_multiple_messages_under_limit(monkeypatch):
    captured = []

    async def fake_send_message(chat_id, text, **kw):
        captured.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {f"kw{i}": {"type": "text", "data": "x"} for i in range(500)})

    asyncio.run(get_filters(make_msg("list", 200)))

    assert len(captured) >= 2
    for text in captured:
        assert len(text) < 4096


# ----------------------------------------------------------------------
# 5. First match wins by position in message
# ----------------------------------------------------------------------
def test_earliest_keyword_wins(monkeypatch):
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {
        "zebra": {"type": "text", "data": "last"},
        "alpha": {"type": "text", "data": "first"},
    })

    asyncio.run(reply_to_filter(make_msg("alpha zebra", 200)))
    assert sent == ["first"]

    _clear_cooldown()
    asyncio.run(reply_to_filter(make_msg("zebra alpha", 200)))
    assert sent == ["first", "last"]


# ----------------------------------------------------------------------
# 6. Flood control: per-(chat,keyword) cooldown
# ----------------------------------------------------------------------
def test_flood_cooldown(monkeypatch):
    calls = {"n": 0}

    async def fake_send_message(chat_id, text, **kw):
        calls["n"] += 1

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    _seed(200, {"hi": {"type": "text", "data": "hello"}})

    asyncio.run(reply_to_filter(make_msg("hi there", 200)))
    assert calls["n"] == 1

    asyncio.run(reply_to_filter(make_msg("hi again", 200)))
    assert calls["n"] == 1  # cooldown blocked

    base = time.monotonic()
    monkeypatch.setattr("modules.filters.time.monotonic", lambda: base + 10)

    asyncio.run(reply_to_filter(make_msg("hi later", 200)))
    assert calls["n"] == 2


# ----------------------------------------------------------------------
# 7. Private chat: no storage read
# ----------------------------------------------------------------------
def test_private_chat_no_read_filters(monkeypatch):
    from modules import filters as _f

    calls = {"n": 0}

    def fake_read_filters(gid):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(_f, "read_filters", fake_read_filters)

    asyncio.run(reply_to_filter(make_msg("hi", 100)))  # private
    assert calls["n"] == 0

    asyncio.run(reply_to_filter(make_msg("hi", 200)))  # group
    assert calls["n"] == 1


# ----------------------------------------------------------------------
# 8. Minor items
# ----------------------------------------------------------------------
def test_overwrite_says_updated(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append(text)

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.filters.is_privileged", _allow)

    cmd = make_msg("/filter test", 200)
    cmd.reply_to_message = make_reply_msg(text="first")
    asyncio.run(set_filter(cmd))
    assert "saved" in replied[-1].lower()

    cmd = make_msg("/filter test", 200)
    cmd.reply_to_message = make_reply_msg(text="second")
    asyncio.run(set_filter(cmd))
    assert "updated" in replied[-1].lower()


def test_keyword_length_cap(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append(text)

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.filters.is_privileged", _allow)

    long_kw = "a" * (MAX_FILTER_KEYWORD_LENGTH + 1)
    cmd = make_msg(f"/filter {long_kw}", 200)
    cmd.reply_to_message = make_reply_msg(text="x")
    asyncio.run(set_filter(cmd))
    assert str(MAX_FILTER_KEYWORD_LENGTH) in replied[-1]


def test_filter_count_cap():
    for i in range(MAX_FILTERS_PER_CHAT):
        add_filter("200", f"k{i}", "x")
    assert len(read_filters("200")) == MAX_FILTERS_PER_CHAT
    err = validate_filter_keyword("200", "brandnew")
    assert err and str(MAX_FILTERS_PER_CHAT) in err
    # Updating an existing keyword is still allowed
    assert validate_filter_keyword("200", "k1") is None


def test_remove_filter_uses_reply_to(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append(text)

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.filters.is_privileged", _allow)

    _seed(200, {"test": {"type": "text", "data": "x"}})

    asyncio.run(remove_filter(make_msg("/stop test", 200)))
    assert "removed" in replied[-1].lower()

    asyncio.run(remove_filter(make_msg("/stop missing", 200)))
    assert "not found" in replied[-1].lower()


def test_shared_normalize():
    assert normalize_filter_keyword("Good   Morning") == "good morning"
    assert normalize_filter_keyword("HELLO") == "hello"
    assert normalize_filter_keyword("  a  b  ") == "a b"
