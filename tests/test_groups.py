from web.groups import ban_group, banned_groups, record_group, unban_group


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