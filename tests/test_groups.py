from core.groups import (
    ban_group, banned_groups, record_group, unban_group,
    is_developer_group, set_developer_group,
)


def test_is_user_owner_mock(monkeypatch):
    import core.utils as cu
    class FakeMember:
        status = "creator"
    async def fake_get_chat_member(chat_id, user_id):
        return FakeMember()
    monkeypatch.setattr(cu.bot, "get_chat_member", fake_get_chat_member)
    import asyncio
    assert asyncio.run(cu.is_user_owner(123, 456)) is True
    FakeMember.status = "administrator"
    assert asyncio.run(cu.is_user_owner(123, 456)) is False


def test_developer_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert is_developer_group(-100123) is False
    set_developer_group(-100123, True)
    assert is_developer_group(-100123) is True
    set_developer_group("-100123", False)
    assert is_developer_group("-100123") is False


def test_ban_unban_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ban_group(-100123) is True
    assert ban_group(-100123) is False
    assert ban_group("100456") is True
    banned = banned_groups()
    assert any(b["gid"] == "-100123" for b in banned)
    assert any(b["gid"] == "100456" for b in banned)
    assert unban_group("-100123") is True
    assert unban_group("-100123") is False
    banned = banned_groups()
    assert all(b["gid"] != "-100123" for b in banned)


def test_banned_group_titles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record_group(-100123, "Bad Group")
    ban_group(-100123)
    entry = [b for b in banned_groups() if b["gid"] == "-100123"][0]
    assert entry["title"] == "Bad Group"