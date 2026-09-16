import asyncio

from telebot.formatting import hlink

import modules.downloader as downloader
from core.imysdb import IMYDB


def make_user(username=None, uid=1, first_name="Rhys"):
    return type("User", (), {"id": uid, "first_name": first_name, "username": username})()


def make_msg(text, chat_id=100, username=None):
    chat = type("Chat", (), {"id": chat_id, "title": "Test Group", "username": None, "first_name": None})()
    return type("Msg", (), {"text": text, "chat": chat, "from_user": make_user(username)})()


def test_extract_skipped_when_downloader_off(monkeypatch):
    monkeypatch.setattr(downloader, "Downloader", False)
    calls = []

    async def fake_ig(m, link):
        calls.append(link)

    monkeypatch.setattr(downloader, "instagram_dl", fake_ig)
    asyncio.run(downloader.extract_supported_url(make_msg("https://www.instagram.com/p/abc123/")))
    assert calls == []


def test_extract_skipped_when_no_text(monkeypatch):
    calls = []

    async def fake_ig(m, link):
        calls.append(link)

    monkeypatch.setattr(downloader, "instagram_dl", fake_ig)
    asyncio.run(downloader.extract_supported_url(make_msg(None)))
    assert calls == []


def test_extract_skipped_when_no_url(monkeypatch):
    calls = []

    async def fake_ig(m, link):
        calls.append(link)

    monkeypatch.setattr(downloader, "instagram_dl", fake_ig)
    asyncio.run(downloader.extract_supported_url(make_msg("just some text")))
    assert calls == []


def test_extract_routes_instagram(monkeypatch):
    calls = []

    async def fake_ig(m, link):
        calls.append(link)

    monkeypatch.setattr(downloader, "instagram_dl", fake_ig)
    url = "https://www.instagram.com/reel/abc123/?utm=1"
    asyncio.run(downloader.extract_supported_url(make_msg(url)))
    assert calls == ["https://www.instagram.com/reel/abc123/"]


def test_extract_routes_facebook(monkeypatch):
    calls = []

    async def fake_fb(m, link):
        calls.append(link)

    monkeypatch.setattr(downloader, "facebook_dl", fake_fb)
    url = "https://www.facebook.com/reel/123"
    asyncio.run(downloader.extract_supported_url(make_msg(url)))
    assert calls == [url]


def test_extract_routes_twitter_and_x(monkeypatch):
    for host in ("twitter.com", "x.com"):
        calls = []

        async def fake_tw(m, link):
            calls.append(link)

        monkeypatch.setattr(downloader, "twitter_dl", fake_tw)
        url = f"https://{host}/user/status/123"
        asyncio.run(downloader.extract_supported_url(make_msg(url)))
        assert calls == [url]


def test_extract_ignores_youtube_links(monkeypatch):
    calls = []

    for name in ("instagram_dl", "facebook_dl", "twitter_dl"):

        async def fake_dl(m, link):
            calls.append(link)

        monkeypatch.setattr(downloader, name, fake_dl)
    url = "https://youtu.be/ZwZcVy4tWws"
    asyncio.run(downloader.extract_supported_url(make_msg(url)))
    assert calls == []


def test_caption_with_username():
    m = make_msg("x", username="charlie")
    info = {"description": "hello world", "title": "title"}
    caption = downloader.get_shared_caption(m, info, "https://www.instagram.com/p/abc123/")
    assert "Shared by @charlie" in caption
    assert "hello world" in caption
    assert "Source" in caption


def test_caption_without_username():
    m = make_msg("x", username=None)
    info = {"title": "fallback title"}
    caption = downloader.get_shared_caption(m, info, "https://www.instagram.com/p/abc123/")
    assert "Shared by" in caption
    assert "fallback title" in caption


def test_caption_long_trims_to_user_and_source():
    m = make_msg("x", username="charlie")
    info = {"description": "d" * 2000}
    url = "https://www.instagram.com/p/abc123/"
    caption = downloader.get_shared_caption(m, info, url)
    assert caption == f"Shared by @charlie\n{hlink('Source', url, escape=False)}"


def test_module_enabled_default(tmp_path, monkeypatch):
    from main import is_module_enabled_in_group

    monkeypatch.chdir(tmp_path)
    assert asyncio.run(is_module_enabled_in_group("autodl", 100)) is True


def test_module_disabled_per_group(tmp_path, monkeypatch):
    from main import is_module_enabled_in_group

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/modules/module_controller.json").set("groups.100.autodl_enabled", False)
    assert asyncio.run(is_module_enabled_in_group("autodl", 100)) is False
    assert asyncio.run(is_module_enabled_in_group("autodl", 101)) is True