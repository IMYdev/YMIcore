"""Permission snapshot, Telegram rights mapping, and gating integration."""

import asyncio
import types

import pytest

from info import bot
from core import permissions as perms
import module_manager as mm


@pytest.fixture
def real_gating(monkeypatch):
    """Undo the conftest stub so module_manager uses the real permission gate."""
    monkeypatch.setattr(mm, "missing_rights", perms.missing_rights)


@pytest.fixture
def clean_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    perms._SNAPSHOTS.clear()
    perms._STAMPS.clear()
    yield
    perms._SNAPSHOTS.clear()
    perms._STAMPS.clear()


def fake_member(**flags):
    """A ChatMemberAdministrator-like object with can_* flags."""
    return types.SimpleNamespace(status="administrator", **flags)


def fake_update(chat_id, status, **flags):
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(id=chat_id),
        new_chat_member=types.SimpleNamespace(status=status, **flags),
    )


# ---------------------------------------------------------------------------
# Mapping + snapshot
# ---------------------------------------------------------------------------

def test_required_rights_mapping():
    assert perms.REQUIRED_RIGHTS["purge"] == {"delete"}
    assert perms.REQUIRED_RIGHTS["ban"] == {"restrict"}
    assert perms.REQUIRED_RIGHTS["pin"] == {"pin"}
    assert perms.REQUIRED_RIGHTS["captcha_verification"] == {"restrict", "delete"}
    assert perms.REQUIRED_RIGHTS["word_block"] == {"delete", "restrict"}
    # unmapped features need no admin right
    assert "notes" not in perms.REQUIRED_RIGHTS
    assert "filter_trigger" not in perms.REQUIRED_RIGHTS


def test_missing_rights_without_snapshot_fails_closed(clean_snapshot):
    assert perms.missing_rights(-100, 'command', 'purge') == frozenset({"delete"})
    assert perms.missing_rights(-100, 'command', 'notes') == frozenset()
    assert perms.missing_rights(-100, 'event', 'captcha_verification') == frozenset({"restrict", "delete"})


def test_missing_rights_with_partial_snapshot(clean_snapshot):
    perms._SNAPSHOTS[-100] = {"delete": True, "restrict": False, "promote": False, "pin": True}
    assert perms.missing_rights(-100, 'command', 'purge') == frozenset()
    assert perms.missing_rights(-100, 'command', 'ban') == frozenset({"restrict"})
    assert perms.missing_rights(-100, 'command', 'pin') == frozenset()
    assert perms.missing_rights(-100, 'event', 'word_block') == frozenset({"restrict"})


def test_right_label():
    assert perms.right_label(frozenset()) == ""
    assert perms.right_label(frozenset({"delete"})) == "delete messages"
    assert perms.right_label(frozenset({"restrict", "delete"})) == "delete messages and restrict members"


# ---------------------------------------------------------------------------
# Telegram API refresh
# ---------------------------------------------------------------------------

def test_refresh_extracts_admin_flags_and_caches(clean_snapshot, monkeypatch):
    calls = {"chat_member": 0}

    async def fake_me():
        return types.SimpleNamespace(id=42)

    async def fake_get_chat_member(chat_id, user_id):
        calls["chat_member"] += 1
        assert user_id == 42
        return fake_member(can_delete_messages=True, can_restrict_members=False,
                           can_promote_members=True, can_pin_messages=False)

    monkeypatch.setattr(bot, "get_me", fake_me)
    monkeypatch.setattr(bot, "get_chat_member", fake_get_chat_member)

    asyncio.run(perms.refresh_permissions(-100))
    assert perms._SNAPSHOTS[-100] == {
        "delete": True, "restrict": False, "promote": True, "pin": False,
    }
    assert calls["chat_member"] == 1

    # TTL: second call does not hit the API.
    asyncio.run(perms.refresh_permissions(-100))
    assert calls["chat_member"] == 1

    # force=True bypasses TTL.
    asyncio.run(perms.refresh_permissions(-100, force=True))
    assert calls["chat_member"] == 2


def test_refresh_creator_has_all_rights(clean_snapshot, monkeypatch):
    async def fake_me():
        return types.SimpleNamespace(id=42)

    async def fake_get_chat_member(chat_id, user_id):
        return types.SimpleNamespace(status="creator")

    monkeypatch.setattr(bot, "get_me", fake_me)
    monkeypatch.setattr(bot, "get_chat_member", fake_get_chat_member)

    asyncio.run(perms.refresh_permissions(-100))
    assert all(perms._SNAPSHOTS[-100].values())


def test_refresh_failure_fails_closed_but_retries(clean_snapshot, monkeypatch):
    calls = {"n": 0}

    async def fake_me():
        return types.SimpleNamespace(id=42)

    async def fake_get_chat_member(chat_id, user_id):
        calls["n"] += 1
        raise RuntimeError("network error")

    monkeypatch.setattr(bot, "get_me", fake_me)
    monkeypatch.setattr(bot, "get_chat_member", fake_get_chat_member)

    asyncio.run(perms.refresh_permissions(-100))
    assert perms._SNAPSHOTS[-100] == {}
    # stamp marked already-expired so the next call retries
    assert -100 in perms._STAMPS

    asyncio.run(perms.refresh_permissions(-100))
    assert calls["n"] == 2  # retried rather than cached for 5 minutes


def test_apply_member_update_clears_on_leave(clean_snapshot):
    perms._SNAPSHOTS[-100] = {"delete": True}
    perms._STAMPS[-100] = 12345
    asyncio.run(perms.apply_chat_member_update(fake_update(-100, "left")))
    assert -100 not in perms._SNAPSHOTS
    assert -100 not in perms._STAMPS


def test_apply_member_update_uses_update_directly(clean_snapshot, monkeypatch):
    calls = ["n"]

    async def fake_me():
        calls.append("me")

    monkeypatch.setattr(bot, "get_me", fake_me)

    update = fake_update(-100, "administrator", can_delete_messages=True,
                         can_restrict_members=True, can_promote_members=False,
                         can_pin_messages=False)
    asyncio.run(perms.apply_chat_member_update(update))
    assert calls == ["n"]  # no API call
    assert perms._SNAPSHOTS[-100]["delete"] is True
    assert perms._SNAPSHOTS[-100]["restrict"] is True
    assert perms._SNAPSHOTS[-100]["promote"] is False


# ---------------------------------------------------------------------------
# Integration with module gating
# ---------------------------------------------------------------------------

def test_command_gating_veto_keeps_raw_flag(clean_snapshot, real_gating, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = -100999
    # raw flags default to on
    assert mm.command_flag(gid, 'ban') is True
    # no snapshot -> blocked
    assert mm.is_command_enabled(gid, 'ban') is False
    assert mm.disabled_reason(gid, 'ban') == 'permission'
    assert mm.is_command_enabled(gid, 'notes') is True  # no right needed

    # partial rights: delete granted, restrict missing
    perms._SNAPSHOTS[gid] = {
        "delete": True, "restrict": False, "promote": False, "pin": False,
    }
    assert mm.is_command_enabled(gid, 'ban') is False
    assert mm.is_command_enabled(gid, 'purge') is True
    assert mm.is_command_enabled(gid, 'nuke') is True  # alias of purge
    assert mm.disabled_reason(gid, 'nuke') is None

    # full rights -> restored without writing anything
    perms._SNAPSHOTS[gid] = {
        "delete": True, "restrict": True, "promote": True, "pin": True,
    }
    assert mm.is_command_enabled(gid, 'ban') is True
    assert mm.command_flag(gid, 'ban') is True


def test_event_gating_veto(clean_snapshot, real_gating, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = -100998
    assert mm.is_event_enabled(gid, 'word_block') is False
    assert mm.is_event_enabled(gid, 'sticker_block') is False
    assert mm.is_event_enabled(gid, 'filter_trigger') is True  # no right needed

    perms._SNAPSHOTS[gid] = {
        "delete": True, "restrict": True, "promote": False, "pin": False,
    }
    assert mm.is_event_enabled(gid, 'word_block') is True
    assert mm.is_event_enabled(gid, 'sticker_block') is True
    assert mm.is_event_enabled(gid, 'captcha_verification') is True


def test_permission_lock_in_module_views(clean_snapshot, real_gating, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = -100997
    perms._SNAPSHOTS[gid] = {
        "delete": False, "restrict": False, "promote": False, "pin": False,
    }
    label = mm.module_status_label(gid, 'admin')
    assert '🔒' in label
    text, markup = mm.detail_view(gid, 'admin')
    assert 'Missing rights' in text
    buttons = [b for row in markup.keyboard for b in row]
    assert any('🔒' in b.text for b in buttons)

    # full rights -> no lock markers
    perms._SNAPSHOTS[gid] = {
        "delete": True, "restrict": True, "promote": True, "pin": True,
    }
    assert '🔒' not in mm.module_status_label(gid, 'admin')
    text, markup = mm.detail_view(gid, 'admin')
    assert 'Missing rights' not in text
