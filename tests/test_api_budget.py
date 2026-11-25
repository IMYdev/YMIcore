"""Milestone 3: Telegram API budget and bounded in-memory state."""

import asyncio
import time
import types

import pytest

from info import bot


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _chat(chat_id, chat_type="supergroup"):
    return types.SimpleNamespace(id=chat_id, type=chat_type, title="T",
                                 username=None, first_name=None)


def _sticker_msg(chat_id, set_name):
    return types.SimpleNamespace(
        chat=_chat(chat_id), message_id=7, message_thread_id=None,
        sticker=types.SimpleNamespace(set_name=set_name, file_id="f"),
        from_user=types.SimpleNamespace(id=5, first_name="A", last_name=None, username="a"),
        text=None,
    )


def _count_api(monkeypatch, *names):
    calls = []
    for name in names:
        async def fake(*a, _name=name, **k):
            calls.append(_name)
            if _name == "get_me":
                return types.SimpleNamespace(id=42, username="YMIbot")
            if _name == "get_chat_member":
                return types.SimpleNamespace(status="creator")
            return True
        monkeypatch.setattr(bot, name, fake)
    return calls


def test_get_me_fetched_once_for_commands_and_stickers(monkeypatch):
    import main
    from core.permissions import _SNAPSHOTS, _STAMPS
    from core.group_settings import add_sticker

    calls = _count_api(monkeypatch, "get_me", "get_chat_member", "delete_message")
    add_sticker(-300, "bad_set")
    for i in range(100):
        assert asyncio.run(main.addressed_to_us("/ban@YMIbot x"))
    for i in range(100):
        _SNAPSHOTS.pop(-300, None)
        _STAMPS.pop(-300, None)  # force a permission refresh every sticker
        asyncio.run(main.sticker_handler(_sticker_msg(-300, "bad_set")))
    assert calls.count("get_me") == 1
    assert calls.count("delete_message") == 100


def test_failed_get_me_is_not_cached(monkeypatch):
    from core import utils
    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("network")
        return types.SimpleNamespace(id=1, username="b")

    monkeypatch.setattr(bot, "get_me", flaky)
    with pytest.raises(RuntimeError):
        asyncio.run(utils.bot_me())
    assert asyncio.run(utils.bot_me()).username == "b"
    asyncio.run(utils.bot_me())
    assert len(attempts) == 2


def test_sticker_in_chat_without_blocked_sets_makes_no_api_calls(monkeypatch):
    import main
    import os
    calls = _count_api(monkeypatch, "get_me", "get_chat_member", "delete_message")
    asyncio.run(main.sticker_handler(_sticker_msg(-301, "any_set")))
    asyncio.run(main.sticker_handler(_sticker_msg(-301, None)))
    assert calls == []
    assert not os.path.exists("runtime/banned/301_stickers.json")


def test_sticker_from_unblocked_set_makes_no_api_calls(monkeypatch):
    import main
    from core.group_settings import add_sticker
    calls = _count_api(monkeypatch, "get_me", "get_chat_member", "delete_message")
    add_sticker(-302, "bad_set")
    asyncio.run(main.sticker_handler(_sticker_msg(-302, "fine_set")))
    assert calls == []


def test_purge_is_capped_and_concurrency_limited(monkeypatch):
    from modules import purge as purge_mod
    calls, running, peak = [], [0], [0]

    async def fake_delete_messages(chat_id, ids):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        await asyncio.sleep(0.001)
        calls.append(list(ids))
        running[0] -= 1

    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    async def allow(*a, **k):
        return True

    monkeypatch.setattr(bot, "delete_messages", fake_delete_messages)
    monkeypatch.setattr(bot, "send_message", fake_send_message)
    monkeypatch.setattr(purge_mod, "is_privileged", allow)
    msg = types.SimpleNamespace(
        chat=_chat(-1), from_user=types.SimpleNamespace(id=1), message_id=50_000,
        reply_to_message=types.SimpleNamespace(message_id=1), message_thread_id=None,
        text="/purge",
    )
    asyncio.run(purge_mod.purge(msg))
    deleted = [i for chunk in calls for i in chunk]
    assert len(calls) <= 10
    assert peak[0] <= 3
    assert len(deleted) == purge_mod.MAX_PURGE_MESSAGES
    assert max(deleted) == 50_000 and min(deleted) == 50_000 - 999
    assert "latest 1000" in sent[-1]


def test_small_purge_deletes_whole_range(monkeypatch):
    from modules import purge as purge_mod
    calls, sent = [], []

    async def fake_delete_messages(chat_id, ids):
        calls.extend(ids)

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    async def allow(*a, **k):
        return True

    monkeypatch.setattr(bot, "delete_messages", fake_delete_messages)
    monkeypatch.setattr(bot, "send_message", fake_send_message)
    monkeypatch.setattr(purge_mod, "is_privileged", allow)
    msg = types.SimpleNamespace(
        chat=_chat(-1), from_user=types.SimpleNamespace(id=1), message_id=20,
        reply_to_message=types.SimpleNamespace(message_id=11), message_thread_id=None,
        text="/purge",
    )
    asyncio.run(purge_mod.purge(msg))
    assert sorted(calls) == list(range(11, 21))
    assert "latest" not in sent[-1]


def test_captcha_locks_released_after_sessions_resolve(monkeypatch):
    from modules import captcha
    monkeypatch.setattr(captcha, "LOCKS", {})
    _count_api(monkeypatch, "ban_chat_member", "unban_chat_member", "delete_message",
               "send_message", "answer_callback_query")

    async def run():
        for uid in range(1000):
            captcha.create_session(-5, uid, "U", time.time() - 1000)
            sess = captcha.get_session(-5, uid)
            await captcha.punish(sess, "timeout")
    monkeypatch.setattr(asyncio, "create_task", lambda coro: coro.close())
    asyncio.run(run())
    assert captcha.LOCKS == {}


def test_captcha_lock_kept_while_contended():
    from modules import captcha

    async def run():
        lock = captcha._get_lock("k")
        async with lock:
            captcha._release_lock("k")
            assert "k" in captcha.LOCKS
        captcha._release_lock("k")
        assert "k" not in captcha.LOCKS
    asyncio.run(run())


def test_admin_cache_stays_bounded(monkeypatch):
    from web import auth
    monkeypatch.setattr(auth, "_admin_cache", {})

    async def fake_is_admin(chat_id, uid):
        return True

    monkeypatch.setattr(auth, "is_user_admin", fake_is_admin)

    async def run():
        for uid in range(5000):
            await auth.can_manage_group(uid + 1, -100)
    asyncio.run(run())
    assert len(auth._admin_cache) <= auth.ADMIN_CACHE_MAX + 1
