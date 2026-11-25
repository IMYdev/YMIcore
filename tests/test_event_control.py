"""Event control and module master switches."""

import asyncio
from itertools import chain
from pathlib import Path

import pytest

from info import bot
from module_manager import (
    modules, module_events, EVENT_INFO, ALWAYS_ON, UNSWITCHABLE_MODULES,
    COMMAND_ALIASES, UNMANAGED_COMMANDS,
    is_command_enabled, is_event_enabled, is_module_enabled,
    set_command_enabled, set_event_enabled, set_module_enabled,
    command_flag, event_flag, read_event_states, read_module_states, module_stats,
    resolve_command, disabled_reason, gated_event,
    overview_view, detail_view, MODULES_PER_PAGE,
)
from core.storage import module_db
from core.db import IMYDB

SRC = Path(__file__).resolve().parents[1] / "src"
PY_FILES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def make_group_msg(text, chat_id, thread_id=None):
    chat = type("Chat", (), {
        "id": chat_id, "title": "T", "username": None, "first_name": None, "type": "supergroup",
    })()
    return type("Msg", (), {
        "text": text, "chat": chat,
        "from_user": type("User", (), {"id": 999, "first_name": "A", "last_name": None, "username": "a"})(),
        "message_thread_id": thread_id,
    })()


def make_private_msg(text, chat_id):
    chat = type("Chat", (), {
        "id": chat_id, "title": None, "username": None, "first_name": None, "type": "private",
    })()
    return type("Msg", (), {
        "text": text, "chat": chat,
        "from_user": type("User", (), {"id": chat_id, "first_name": "A", "last_name": None, "username": "a"})(),
        "message_thread_id": None,
    })()


def make_chat_member_update(chat_id, old_status, new_status):
    user = type("User", (), {"id": 42, "first_name": "Newbie", "last_name": None,
                             "username": "n00b", "is_bot": False})()
    new = type("ChatMember", (), {"status": new_status, "user": user})()
    old = type("ChatMember", (), {"status": old_status, "is_member": True})()
    chat = type("Chat", (), {"id": chat_id, "title": "T", "type": "supergroup"})()
    return type("Update", (), {
        "old_chat_member": old, "new_chat_member": new, "chat": chat, "message_thread_id": None,
    })()


# ----------------------------------------------------------------------
# 1. Defaults
# ----------------------------------------------------------------------
def test_defaults_all_on(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100777'
    for command in chain(*modules.values()):
        assert is_command_enabled(gid, command) is True
    for event in chain(*module_events.values()):
        assert is_event_enabled(gid, event) is True
    for module in modules:
        assert is_module_enabled(gid, module) is True


# ----------------------------------------------------------------------
# 2. Master switch never rewrites component flags
# ----------------------------------------------------------------------
def test_module_switch_roundtrip_restores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100778'
    set_command_enabled(gid, 'filter', False)
    enabled_before, _ = module_stats(gid)

    set_module_enabled(gid, 'filters', False)
    assert not is_command_enabled(gid, 'filter')
    assert not is_command_enabled(gid, 'filist')
    assert not is_command_enabled(gid, 'stop')
    assert not is_event_enabled(gid, 'filter_trigger')
    # Raw flags untouched.
    assert read_module_states(gid)['filter'] is False
    assert read_module_states(gid)['filist'] is True
    assert read_event_states(gid)['filter_trigger'] is True

    set_module_enabled(gid, 'filters', True)
    assert is_command_enabled(gid, 'filter') is False   # prior fine-grained setting kept
    assert is_command_enabled(gid, 'filist') is True
    assert is_event_enabled(gid, 'filter_trigger') is True
    enabled_after, _ = module_stats(gid)
    assert enabled_after == enabled_before


def test_stats_counts_components(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100779'
    total_commands = sum(len(v) for v in modules.values())
    total_events = sum(len(v) for v in module_events.values())
    enabled, total = module_stats(gid)
    assert total == total_commands + total_events
    assert enabled == total


# ----------------------------------------------------------------------
# 3. Pinning
# ----------------------------------------------------------------------
def test_pinned_modules_command_never_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100781'
    module_db().set(f'groups.{gid}.modules_enabled', False)
    assert is_command_enabled(gid, 'modules') is True
    set_command_enabled(gid, 'modules', False)
    assert is_command_enabled(gid, 'modules') is True


def test_unswitchable_general_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100782'
    set_module_enabled(gid, 'general', False)  # silent no-op
    assert is_module_enabled(gid, 'general') is True
    command_flag(gid, 'help')  # general commands keep their own flags
    set_command_enabled(gid, 'help', False)
    assert is_command_enabled(gid, 'help') is False


# ----------------------------------------------------------------------
# 5. Aliases
# ----------------------------------------------------------------------
def test_nuke_follows_purge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100783'
    assert resolve_command('nuke') == 'purge'
    assert is_command_enabled(gid, 'nuke') is True
    set_command_enabled(gid, 'purge', False)
    assert is_command_enabled(gid, 'nuke') is False
    assert disabled_reason(gid, 'nuke') == 'command'
    assert disabled_reason(gid, 'help') is None


def test_nuke_reason_is_module_when_admin_off(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = '-100784'
    set_module_enabled(gid, 'admin', False)
    assert disabled_reason(gid, 'nuke') == 'module'


# ----------------------------------------------------------------------
# 6. Gating
# ----------------------------------------------------------------------
def test_filter_and_note_events_gated_in_groups(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = 200
    IMYDB("runtime/filters/200_filters").set("filters", {"hello": {"type": "text", "data": "hi"}})
    IMYDB("runtime/notes/200_notes.json").set("notes", {"1": {"name": "n", "reply": {"type": "text", "data": "note!"}}})
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append((chat_id, text))

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    set_event_enabled(200, 'filter_trigger', False)
    set_event_enabled(200, 'note_fetch', False)
    from modules.filters import reply_to_filter
    from modules.notes import get_notes
    asyncio.run(reply_to_filter(make_group_msg("hello there", 200)))
    asyncio.run(get_notes(make_group_msg("#1", 200)))
    assert sent == []

    set_event_enabled(200, 'filter_trigger', True)
    set_event_enabled(200, 'note_fetch', True)
    asyncio.run(reply_to_filter(make_group_msg("hello there", 200)))
    asyncio.run(get_notes(make_group_msg("#1", 200)))
    assert sent == [(200, "hi"), (200, "note!")]


def test_private_chats_are_never_gated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/filters/100_filters").set("filters", {"hello": {"type": "text", "data": "hi"}})
    IMYDB("runtime/notes/100_notes.json").set("notes", {"1": {"name": "n", "reply": {"type": "text", "data": "note!"}}})
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append((chat_id, text))

    monkeypatch.setattr(bot, "send_message", fake_send_message)
    set_event_enabled(100, 'filter_trigger', False)
    set_event_enabled(100, 'note_fetch', False)
    from modules.filters import reply_to_filter
    from modules.notes import get_notes
    asyncio.run(reply_to_filter(make_private_msg("hello there", 100)))
    asyncio.run(get_notes(make_private_msg("#1", 100)))
    # Filters never fire in private chats by design; the note gate must not block either.
    assert sent == [(100, "note!")]


def test_greeting_and_farewell_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = 200
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    from modules.greetings import send_standard_greeting, bye
    user = type("User", (), {"id": 42, "first_name": "Newbie", "last_name": None, "username": None})()
    db = IMYDB("runtime/greetings/200_greetings.json")

    set_event_enabled(gid, 'greeting', False)
    asyncio.run(send_standard_greeting(gid, user, db))
    assert sent == []

    set_event_enabled(gid, 'greeting', True)
    asyncio.run(send_standard_greeting(gid, user, db))
    assert len(sent) == 1

    # farewell off: no goodbye message, but a pending captcha session is still cleaned up.
    set_event_enabled(gid, 'farewell', False)
    from modules.captcha import create_session, get_session
    create_session(gid, 42, "Newbie", 0.0)
    assert get_session(gid, 42) is not None
    asyncio.run(bye(make_chat_member_update(gid, "member", "left")))
    assert sent == ["Hello Newbie, welcome!"]
    assert get_session(gid, 42) is None


def test_hello_captcha_event_falls_back_to_greeting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = 200
    sent = []

    async def fake_send_message(chat_id, text, **kw):
        sent.append(text)

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    async def fake_start_verification(chat, user, db):
        sent.append("VERIFIED")

    import modules.captcha as captcha
    monkeypatch.setattr(captcha, "start_verification", fake_start_verification)

    async def fake_admins(chat_id):
        raise RuntimeError("no admin lookup in tests")

    monkeypatch.setattr(bot, "get_chat_administrators", fake_admins)

    db = IMYDB("runtime/greetings/200_greetings.json")
    db.set('captcha_enabled', True)
    db.set('captcha_questions', [{"q": "Q", "opts": ["A", "B"], "ans": "A"}])

    from modules.greetings import hello
    set_event_enabled(gid, 'captcha_verification', False)
    asyncio.run(hello(make_chat_member_update(gid, "left", "member")))
    assert sent == ["Hello Newbie, welcome!"]

    set_event_enabled(gid, 'captcha_verification', True)
    asyncio.run(hello(make_chat_member_update(gid, "left", "member")))
    assert sent[-1] == "VERIFIED"


# ----------------------------------------------------------------------
# 7. Registry integrity
# ----------------------------------------------------------------------
def test_registry_integrity():
    command_ids = list(chain(*modules.values()))
    event_ids = list(chain(*module_events.values()))
    assert len(set(command_ids)) == len(command_ids)
    assert len(set(event_ids)) == len(event_ids)
    for cid in command_ids:
        assert '.' not in cid and ':' not in cid
        assert not cid.startswith('event_') and not cid.startswith('module_')
    for eid in event_ids:
        assert '.' not in eid and ':' not in eid
    # every module_events key is a known module
    for module in module_events:
        assert module in modules
    # 64-byte callback limit for the widest button
    for module in modules:
        assert len(f'mod:all:1:{module}'.encode()) <= 64
        assert len(f'mod:master:1:{module}'.encode()) <= 64
    for module, event_list in module_events.items():
        for event in event_list:
            assert len(f'mod:evt:1:{module}:{event}'.encode()) <= 64


# ----------------------------------------------------------------------
# 8. Source wiring: every event is gated, every command is managed
# ----------------------------------------------------------------------
def test_every_event_is_gated_somewhere():
    for event in chain(*module_events.values()):
        found = False
        for path in PY_FILES:
            if path.name == 'module_manager.py':
                continue
            text = path.read_text()
            if event in text and ('is_event_enabled(' in text or 'gated_event(' in text):
                found = True
                break
        assert found, f'event {event} is never gated'


def test_every_command_is_managed_or_pinned():
    from botcommands import COMMANDS
    managed = set(chain(*modules.values()))
    for command in COMMANDS:
        assert command in managed or command in COMMAND_ALIASES or command in UNMANAGED_COMMANDS, command
    seen = {}
    for module, commands in modules.items():
        for command in commands:
            assert command not in seen, f'{command} in two modules: {seen[command]}, {module}'
            seen[command] = module
    for event in chain(*module_events.values()):
        assert event in EVENT_INFO


# ----------------------------------------------------------------------
# 9. Web panel
# ----------------------------------------------------------------------
OWNER = 999


def stub_bot():
    async def fake_send_message(chat_id, text, **kwargs):
        return type("Sent", (), {"message_id": 500, "chat": None})()

    async def fake_edit_message_text(text, chat_id=None, message_id=None, **kwargs):
        return True

    async def fake_delete_message(chat_id, message_id, **kwargs):
        return True

    async def fake_get_chat(chat_id):
        return type("Chat", (), {"id": chat_id, "first_name": "Owner", "last_name": None, "username": "owner"})()

    bot.send_message = fake_send_message
    bot.edit_message_text = fake_edit_message_text
    bot.delete_message = fake_delete_message
    bot.get_chat = fake_get_chat


def csrf_of(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start:html.index('"', start)]


def test_panel_module_switch_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stub_bot()
    from web import auth
    from web.server import create_app
    from aiohttp.test_utils import TestClient, TestServer
    from core.groups import record_group

    record_group(-10009008009, "Test Group", "supergroup")

    async def run():
        token, _ = auth.issue_admin_token(OWNER, "owner")
        client = TestClient(TestServer(create_app()))
        await client.start_server()
        try:
            response = await client.post("/auth/token", data={"token": token}, allow_redirects=False)
            assert response.status == 302
            body = await (await client.get("/groups/-10009008009/modules")).text()
            csrf = csrf_of(body)

            # module_on absent -> module off; commands from the form are stored
            resp = await client.post("/groups/-10009008009/modules", data={
                "csrf": csrf, "module": "filters", "cmd": ["filter"],
            }, allow_redirects=False)
            assert resp.status == 302
            gid = '-10009008009'
            assert is_module_enabled(gid, 'filters') is False
            assert command_flag(gid, 'filter') is True
            assert command_flag(gid, 'filist') is False   # not submitted
            assert is_command_enabled(gid, 'filter') is False  # module off wins

            # turn the module back on with a new GET to fetch a fresh CSRF
            body = await (await client.get("/groups/-10009008009/modules")).text()
            csrf = csrf_of(body)
            resp = await client.post("/groups/-10009008009/modules", data={
                "csrf": csrf, "module": "filters", "module_on": "on",
                "cmd": ["filter", "filist", "stop"], "event": ["filter_trigger"],
            }, allow_redirects=False)
            assert resp.status == 302
            assert is_module_enabled(gid, 'filters') is True
            assert is_command_enabled(gid, 'filist') is True
            assert is_event_enabled(gid, 'filter_trigger') is True
        finally:
            await client.close()

    asyncio.run(run())


def test_panel_rejects_unknown_module_and_ignores_pinned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stub_bot()
    from web import auth
    from web.server import create_app
    from aiohttp.test_utils import TestClient, TestServer
    from core.groups import record_group

    record_group(-10009008010, "Test Group 2", "supergroup")

    async def run():
        token, _ = auth.issue_admin_token(OWNER, "owner")
        client = TestClient(TestServer(create_app()))
        await client.start_server()
        try:
            response = await client.post("/auth/token", data={"token": token}, allow_redirects=False)
            assert response.status == 302
            gid = '-10009008010'
            body = await (await client.get(f"/groups/{gid}/modules")).text()
            csrf = csrf_of(body)

            resp = await client.post(f"/groups/{gid}/modules", data={
                "csrf": csrf, "module": "nonsense",
            }, allow_redirects=False)
            assert resp.status == 400

            # 'modules' is pinned: posting it writes nothing, whatever else is checked.
            resp = await client.post(f"/groups/{gid}/modules", data={
                "csrf": csrf, "module": "general", "cmd": ["modules", "help"],
            }, allow_redirects=False)
            assert resp.status == 302
            assert command_flag(gid, 'help') is True
        finally:
            await client.close()

    asyncio.run(run())


def test_module_views_render_and_callbacks_stay_under_telegram_limit(tmp_path, monkeypatch):
    """Validate overview and detail view builders stay within callback size limits."""
    monkeypatch.chdir(tmp_path)
    text, markup = overview_view('-100777', 1)
    assert 'page 1 of' in text
    buttons = [b for row in markup.keyboard for b in row]
    open_buttons = [b for b in buttons if (b.callback_data or '').startswith('mod:open:')]
    assert len(open_buttons) == MODULES_PER_PAGE
    # Telegram limits callbacks to 64 bytes
    for b in buttons:
        assert len((b.callback_data or '').encode()) <= 64

    # page 2 exists and has navigation
    text, markup = overview_view('-100777', 2)
    assert 'page 2 of' in text
    nav = [b.callback_data for row in markup.keyboard for b in row]
    assert any(d == 'mod:list:1' for d in nav)

    # detail view for filters includes components, master, bulk, back button
    text, markup = detail_view('-100777', 'filters', 1)
    assert 'filters · ON' in text
    cbs = [b.callback_data for row in markup.keyboard for b in row]
    assert 'mod:master:1:filters' in cbs
    assert 'mod:evt:1:filters:filter_trigger' in cbs
    assert 'mod:back:1' in cbs
    assert all(len(d.encode()) <= 64 for d in cbs)


# ----------------------------------------------------------------------
# Commands addressed with @: only the command token decides
# ----------------------------------------------------------------------
def _fake_me(monkeypatch, calls=None):
    async def fake_get_me():
        if calls is not None:
            calls.append(1)
        return type("Me", (), {"id": 1, "username": "YMIbot"})()
    monkeypatch.setattr(bot, "get_me", fake_get_me)


def test_at_in_arguments_does_not_drop_command(monkeypatch):
    from main import addressed_to_us
    _fake_me(monkeypatch)
    assert asyncio.run(addressed_to_us("/blockword @spammer"))
    assert asyncio.run(addressed_to_us("/filter a@b.com"))
    assert asyncio.run(addressed_to_us("/ban"))


def test_command_for_other_bot_is_ignored(monkeypatch):
    from main import addressed_to_us
    _fake_me(monkeypatch)
    assert not asyncio.run(addressed_to_us("/ban@OtherBot"))
    assert not asyncio.run(addressed_to_us("/ban@OtherBot @YMIbot"))
    assert asyncio.run(addressed_to_us("/ban@ymibot some reason"))


def test_group_command_with_at_argument_reaches_handler(tmp_path, monkeypatch):
    import main
    monkeypatch.chdir(tmp_path)
    _fake_me(monkeypatch)
    handled = []

    async def fake_handle_command(m):
        handled.append(m.text)

    async def no_refresh(*a, **k):
        return None

    monkeypatch.setattr(main, "handle_command", fake_handle_command)
    monkeypatch.setattr(main, "refresh_permissions", no_refresh)
    asyncio.run(main.cmd_handler(make_group_msg("/blockword @spammer", -100777)))
    asyncio.run(main.cmd_handler(make_group_msg("/blockword@OtherBot x", -100777)))
    assert handled == ["/blockword @spammer"]
