"""Greeting templates: validation and safe rendering of bad saved templates."""

import asyncio

import pytest

from info import bot
from core.db import IMYDB
from core.group_settings import validate_message_template
from core.validation import validate_template
from modules import greetings


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("template", ["Hi {firstname", "Hi }", "Hi {", "{firstname.upper}", "{}"])
def test_bad_templates_rejected(template):
    assert validate_template(template) is False
    assert validate_message_template(template) is not None


@pytest.mark.parametrize("template", [
    "Hello {firstname}!", "{username} {lastname}", "No placeholders",
])
def test_good_templates_accepted(template):
    assert validate_template(template) is True


def _user():
    return type("User", (), {"id": 5, "first_name": "Ann", "last_name": None, "username": "ann"})()


def test_bad_saved_template_falls_back_to_default(monkeypatch):
    sent, logged = [], []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    async def fake_log_error(bot_, error, context_msg=None):
        logged.append(error)

    monkeypatch.setattr(bot, "send_message", fake_send_message)
    monkeypatch.setattr(greetings, "log_error", fake_log_error)
    db = IMYDB("runtime/greetings/1_greetings.json")
    db.set("greeting", "Hi {firstname")

    asyncio.run(greetings._send_event_message(-1, _user(), "greeting", db))
    assert sent == ["Hello Ann, welcome!"]
    assert len(logged) == 1


def test_greeting_command_rejects_unbalanced_brace(monkeypatch):
    replies = []

    async def fake_reply_to(m, text, **kw):
        replies.append(text)

    async def allow(*a, **k):
        return True

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr(greetings, "is_privileged", allow)
    chat = type("Chat", (), {"id": -1, "type": "supergroup"})()
    msg = type("Msg", (), {"text": "/greeting Hi {firstname", "caption": None, "chat": chat,
                           "from_user": _user(), "reply_to_message": None,
                           "message_thread_id": None})()
    asyncio.run(greetings.set_greeting(msg))
    assert "allowed" in replies[-1]
    assert IMYDB("runtime/greetings/1_greetings.json").get("greeting") is None


def test_chat_member_handler_logs_instead_of_raising(monkeypatch):
    import main
    logged = []

    async def boom(m):
        raise RuntimeError("boom")

    async def fake_log_error(bot_, error, context_msg=None):
        logged.append(str(error))

    monkeypatch.setattr(main, "hello", boom)
    monkeypatch.setattr(main, "log_error", fake_log_error)
    update = type("U", (), {"chat": type("C", (), {"id": 1, "type": "private"})()})()
    asyncio.run(main.chat_m(update))
    assert logged == ["boom"]


def test_handle_errors_hides_exception_text(monkeypatch):
    from core import utils
    replies = []

    async def fake_reply_to(m, text, **kw):
        replies.append(text)

    async def quiet_log(*a, **k):
        return None

    monkeypatch.setattr(bot, "reply_to", fake_reply_to)
    monkeypatch.setattr(utils, "log_error", quiet_log)

    @utils.handle_errors
    async def explode(m):
        raise RuntimeError("secret path /srv/bot/runtime")

    asyncio.run(explode(object()))
    assert replies == [utils.GENERIC_ERROR_REPLY]
