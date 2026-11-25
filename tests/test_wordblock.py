"""Word blocklist module fixes: matching, storage, flood control."""

import asyncio
import time
import pytest

from info import bot
from modules.blocklist import block_words, block_word, unblock_word, list_blocked_words
from core.group_settings import (
    MAX_BLOCKED_WORD_LENGTH, MAX_BLOCKED_WORDS_PER_CHAT,
    add_blocked_word, read_blocked_words, validate_blocked_word, normalize_blocked_word,
)
from core.db import IMYDB


def make_msg(text, chat_id, thread_id=None):
    chat = type("Chat", (), {
        "id": chat_id, "title": "T", "username": None, "first_name": None,
        "type": "private" if chat_id == 100 else "group",
    })()
    msg = type("Msg", (), {
        "text": text, "chat": chat, "from_user": type("User", (), {"id": 999})(),
        "message_thread_id": thread_id,
    })()
    msg.message_id = 12345
    return msg


def _seed(gid, words):
    IMYDB(f"runtime/banned/{gid}_words.json").set("words", words)


def _clear_word_queue():
    from modules import blocklist as _b

    _b._word_queue.clear()


async def _allow(*args, **kwargs):
    return True


@pytest.fixture(autouse=True)
def _clean_wordlist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed("200", [])
    _seed("300", [])
    _clear_word_queue()
    yield
    _clear_word_queue()


# ----------------------------------------------------------------------
# 1. Keyword matching: whole-word boundaries, multi-word, case-insensitivity
# ----------------------------------------------------------------------
def test_keyword_matching(monkeypatch):
    deleted = []

    async def fake_delete_messages(chat_id, ids):
        deleted.extend(ids)

    monkeypatch.setattr(bot, "delete_messages", fake_delete_messages)

    from modules import blocklist as bl
    from core.group_settings import add_blocked_word

    add_blocked_word("200", "hello")

    msg = make_msg("hello!", 200)
    handled = asyncio.run(bl.block_words(msg))
    assert handled is True
    asyncio.run(bl._flush(200))
    assert deleted == [msg.message_id]

    _seed("200", ["hello"])
    msg2 = make_msg("HELLO world", 200)
    handled2 = asyncio.run(bl.block_words(msg2))
    assert handled2 is True
    asyncio.run(bl._flush(200))
    assert len(deleted) == 2

    _seed("200", ["good morning"])
    msg3 = make_msg("good morning everyone", 200)
    handled3 = asyncio.run(bl.block_words(msg3))
    assert handled3 is True
    asyncio.run(bl._flush(200))
    assert len(deleted) == 3

    _seed("200", ["good morning"])
    msg4 = make_msg("good\tmorning", 200)
    handled4 = asyncio.run(bl.block_words(msg4))
    assert handled4 is True
    asyncio.run(bl._flush(200))
    assert len(deleted) == 4

    _seed("200", ["cat"])
    msg5 = make_msg("category", 200)
    handled5 = asyncio.run(bl.block_words(msg5))
    assert handled5 is False
    asyncio.run(bl._flush(200))
    assert len(deleted) == 4

    _seed("200", ["cat"])
    msg6 = make_msg("cat!", 200)
    handled6 = asyncio.run(bl.block_words(msg6))
    assert handled6 is True
    asyncio.run(bl._flush(200))
    assert len(deleted) == 5


def test_commands_not_matched(monkeypatch):
    deleted = []

    async def fake_delete_messages(chat_id, ids):
        deleted.extend(ids)

    monkeypatch.setattr(bot, "delete_messages", fake_delete_messages)

    from modules import blocklist as bl
    from core.group_settings import add_blocked_word
    add_blocked_word("200", "filter")

    msg = make_msg("/filter", 200)
    handled = asyncio.run(bl.block_words(msg))
    assert handled is False
    asyncio.run(bl._flush(200))
    assert deleted == []


def test_caption_handled(monkeypatch):
    deleted = []

    async def fake_delete_messages(chat_id, ids):
        deleted.extend(ids)

    monkeypatch.setattr(bot, "delete_messages", fake_delete_messages)

    from modules import blocklist as bl
    from core.group_settings import add_blocked_word
    add_blocked_word("200", "hi")

    msg = type("Msg", (), {
        "text": None,
        "caption": "hi there",
        "chat": type("Chat", (), {"id": 200})(),
        "from_user": type("User", (), {"id": 999})(),
        "message_id": 1001,
    })()

    handled = asyncio.run(bl.block_words(msg))
    assert handled is True
    asyncio.run(bl._flush(200))
    assert deleted == [1001]


# ----------------------------------------------------------------------
# 2. Queue enqueueing
# ----------------------------------------------------------------------
def test_queue_enqueues(monkeypatch):
    from modules import blocklist as bl

    _seed("200", ["test"])
    bl._word_queue.clear()

    msg = make_msg("test", 200)
    asyncio.run(bl.block_words(msg))

    assert 200 in bl._word_queue
    assert bl._word_queue[200] == [msg.message_id]


# ----------------------------------------------------------------------
# 3. Limits: word length, count per chat
# ----------------------------------------------------------------------
def test_word_length_cap():
    long_word = "a" * (MAX_BLOCKED_WORD_LENGTH + 1)
    err = validate_blocked_word("200", long_word)
    assert err and str(MAX_BLOCKED_WORD_LENGTH) in err

    err2 = validate_blocked_word("200", "short")
    assert err2 is None


def test_word_count_cap():
    for i in range(MAX_BLOCKED_WORDS_PER_CHAT):
        add_blocked_word("200", f"w{i}")

    assert len(read_blocked_words("200")) == MAX_BLOCKED_WORDS_PER_CHAT
    err = validate_blocked_word("200", "extra")
    assert err and str(MAX_BLOCKED_WORDS_PER_CHAT) in err


def test_normalize():
    assert normalize_blocked_word("Hello  world") == "hello world"
    assert normalize_blocked_word("  foo  bar  ") == "foo bar"
    assert normalize_blocked_word("") == ""


# ----------------------------------------------------------------------
# 4. Simple command routes (synchronous)
# ----------------------------------------------------------------------
def test_block_word_command(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append(text)

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.blocklist.is_privileged", _allow)

    cmd = make_msg("/blockword test", 200)
    asyncio.run(block_word(cmd))
    assert any("added" in r.lower() for r in replied)

    cmd2 = make_msg("/unblockword test", 200)
    asyncio.run(unblock_word(cmd2))
    assert any("removed" in r.lower() for r in replied)


def test_list_blocked_words(monkeypatch):
    captured = []

    async def fake_send_message(chat_id, text, **kw):
        captured.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    from core.group_settings import add_blocked_word
    add_blocked_word("200", "cat")
    add_blocked_word("200", "dog")

    asyncio.run(list_blocked_words(make_msg("list", 200)))
    assert captured
    assert any("cat" in msg for msg in captured)
    assert any("dog" in msg for msg in captured)


def test_mute_duration_for():
    from modules import blocklist as bl

    assert bl.mute_duration_for(1) == 60
    assert bl.mute_duration_for(2) == 120
    assert bl.mute_duration_for(3) == 240
    assert bl.mute_duration_for(4) == 480
    assert bl.mute_duration_for(100) == bl.MAX_MUTE_SECONDS


def test_block_word_mute_escalates(monkeypatch):
    from datetime import datetime

    restricted = []

    async def fake_restrict(chat_id, user_id, permissions=None, until_date=None):
        restricted.append(until_date)

    monkeypatch.setattr(bot, "restrict_chat_member", fake_restrict)
    monkeypatch.setattr("modules.blocklist.is_moderatable", _allow)

    from modules import blocklist as bl
    from core.group_settings import add_blocked_word, read_word_mute_count

    add_blocked_word("200", "hello")

    def make_user_msg(user_id):
        msg = make_msg("hello", 200)
        msg.from_user = type("User", (), {"id": user_id})()
        return msg

    now = datetime.now()
    for i in range(3):
        asyncio.run(bl.block_words(make_user_msg(555)))
        assert len(restricted) == i + 1

    deltas = [(t - now).total_seconds() for t in restricted]
    for got, want in zip(deltas, (60, 120, 240)):
        assert want - 5 <= got <= want + 5
    assert read_word_mute_count("200", 555) == 3


def test_no_mute_for_admin(monkeypatch):
    calls = []

    async def fake_restrict(*args, **kwargs):
        calls.append(1)

    monkeypatch.setattr(bot, "restrict_chat_member", fake_restrict)

    async def deny(*args, **kwargs):
        return False

    monkeypatch.setattr("modules.blocklist.is_moderatable", deny)

    from modules import blocklist as bl
    from core.group_settings import add_blocked_word

    add_blocked_word("200", "hello")
    msg = make_msg("hello", 200)
    msg.from_user = type("User", (), {"id": 555})()

    asyncio.run(bl.block_words(msg))
    assert calls == []


def test_block_word_reply_survives_markup_characters(monkeypatch):
    replied = []

    async def fake_reply_to(m, text, **kw):
        replied.append((text, kw.get("parse_mode")))

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr("modules.blocklist.is_privileged", _allow)

    asyncio.run(block_word(make_msg("/blockword snake_case*<b>", 200)))
    text, mode = replied[-1]
    assert mode == "HTML"
    assert "added" in text
    assert "<code>snake_case*&lt;b&gt;</code>" in text
    assert "went wrong" not in text
