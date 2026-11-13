import asyncio

from telebot.formatting import hlink

import modules.downloader as downloader
from core.db import IMYDB


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


def test_extract_ignores_facebook_links(monkeypatch):
    calls = []

    for name in ("instagram_dl", "twitter_dl"):

        async def fake_dl(m, link):
            calls.append(link)

        monkeypatch.setattr(downloader, name, fake_dl)
    asyncio.run(downloader.extract_supported_url(make_msg("https://www.facebook.com/reel/123")))
    assert calls == []


def test_extract_routes_twitter_and_x(monkeypatch):
    for host in ("twitter.com", "x.com"):
        calls = []

        async def fake_tw(m, link):
            calls.append(link)

        monkeypatch.setattr(downloader, "twitter_dl", fake_tw)
        url = f"https://{host}/user/status/123"
        asyncio.run(downloader.extract_supported_url(make_msg(url)))
        assert calls == [url]


def test_extract_ignores_mirror_hosts(monkeypatch):
    calls = []

    async def fake_dl(m, link):
        calls.append(link)

    monkeypatch.setattr(downloader, "instagram_dl", fake_dl)
    monkeypatch.setattr(downloader, "twitter_dl", fake_dl)
    for url in (
        "https://fxtwitter.com/user/status/123",
        "https://fixupx.com/user/status/123",
        "https://vxinstagram.com/reel/abc123/",
        "https://kkinstagram.com/reel/abc123/",
    ):
        asyncio.run(downloader.extract_supported_url(make_msg(url)))
    assert calls == []


def test_extract_ignores_youtube_links(monkeypatch):
    calls = []

    for name in ("instagram_dl", "twitter_dl"):

        async def fake_dl(m, link):
            calls.append(link)

        monkeypatch.setattr(downloader, name, fake_dl)
    url = "https://youtu.be/ZwZcVy4tWws"
    asyncio.run(downloader.extract_supported_url(make_msg(url)))
    assert calls == []


def test_instagram_dl_reports_failure(monkeypatch):
    replies = []

    async def fake_og(m, url):
        return False

    async def fake_vx(m, url):
        return False

    async def fake_reply(m, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(downloader, "instagram_dl_og", fake_og)
    monkeypatch.setattr(downloader, "instagram_dl_vx", fake_vx)
    monkeypatch.setattr(downloader.bot, "reply_to", fake_reply)
    asyncio.run(downloader.instagram_dl(make_msg("x"), "https://www.instagram.com/reel/abc123/"))
    assert replies == ["Couldn't download this Instagram media."]


def test_instagram_dl_falls_back_to_vx(monkeypatch):
    replies = []

    async def fake_og(m, url):
        return False

    async def fake_vx(m, url):
        return True

    async def fake_reply(m, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(downloader, "instagram_dl_og", fake_og)
    monkeypatch.setattr(downloader, "instagram_dl_vx", fake_vx)
    monkeypatch.setattr(downloader.bot, "reply_to", fake_reply)
    asyncio.run(downloader.instagram_dl(make_msg("x"), "https://www.instagram.com/reel/abc123/"))
    assert replies == []


def test_vx_media_parses_video():
    page = '<meta property="og:video" content="https://vx/offload/x/0.mp4" /><meta property="og:description" content="hi &amp; bye" />'
    assert downloader._vx_media(page) == ("https://vx/offload/x/0.mp4", "hi & bye")
    assert downloader._vx_media("no media here") is None


def test_instagram_dl_vx_sends_offload_when_page_fails(monkeypatch):
    sent = []

    class FailingSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise RuntimeError("network")

        async def __aexit__(self, *args):
            pass

    async def fake_send(chat_id, video=None, caption=None, **kwargs):
        sent.append((video, caption))

    monkeypatch.setattr(downloader.aiohttp, "ClientSession", FailingSession)
    monkeypatch.setattr(downloader.bot, "send_video", fake_send)
    asyncio.run(downloader.instagram_dl_vx(make_msg("x"), "https://www.instagram.com/reel/abc123/"))
    assert sent[0][0] == "https://vxinstagram.com/offload/abc123/0.mp4"
    assert sent[0][1].startswith("Shared by")


def test_tweet_video_url_from_videos():
    data = {"tweet": {"media": {"videos": [{"type": "video", "url": "https://video.twimg.com/a.mp4"}]}}}
    assert downloader._tweet_video_url(data) == "https://video.twimg.com/a.mp4"


def test_tweet_video_url_from_all_skips_photos():
    data = {"tweet": {"media": {"all": [
        {"type": "photo", "url": "https://pbs.twimg.com/a.jpg"},
        {"type": "video", "url": "https://video.twimg.com/b.mp4"},
    ]}}}
    assert downloader._tweet_video_url(data) == "https://video.twimg.com/b.mp4"


def test_tweet_video_url_missing():
    assert downloader._tweet_video_url({"tweet": {"text": "no media"}}) is None


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