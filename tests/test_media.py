import asyncio
import io

from multidict import CIMultiDict, CIMultiDictProxy
from aiohttp import web

from web.media import classify_upload, is_file_field, relay_to_telegram


def make_field(filename, content_type, data=b""):
    headers = CIMultiDictProxy(CIMultiDict())
    return web.FileField("file", filename, io.BytesIO(data), content_type, headers)


def test_classify_upload():
    assert classify_upload(make_field("a.png", "image/png")) == "photo"
    assert classify_upload(make_field("a.mp4", "video/mp4")) == "video"
    assert classify_upload(make_field("a.mp3", "audio/mpeg")) == "audio"
    assert classify_upload(make_field("a.bin", "application/octet-stream")) == "document"
    assert classify_upload(make_field("a", "")) == "document"


def test_is_file_field():
    assert is_file_field(make_field("a.png", "image/png"))
    assert not is_file_field("not-a-file")
    assert not is_file_field(None)


def make_msg(**kwargs):
    defaults = {
        "photo": None, "video": None, "audio": None, "voice": None,
        "document": None, "sticker": None, "animation": None,
    }
    defaults.update(kwargs)
    return type("Msg", (), defaults)()


def test_relay_to_telegram_photo(tmp_path, monkeypatch):
    from info import bot

    async def fake_send_photo(chat_id, data, **kw):
        captured = kw.get("disable_notification")
        assert captured is True
        return make_msg(photo=[type("PS", (), {"file_id": "FILE1"})()])

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    result = asyncio.run(relay_to_telegram(make_field("a.png", "image/png", b"x"), 999))
    assert result == {"type": "photo", "file_id": "FILE1"}


def test_relay_to_telegram_binary_returns_media_type(tmp_path, monkeypatch):
    from info import bot

    async def fake_send_document(chat_id, data, **kw):
        return make_msg(document=type("D", (), {"file_id": "FILE9"})())

    monkeypatch.setattr(bot, "send_document", fake_send_document)
    result = asyncio.run(relay_to_telegram(make_field("a.bin", "application/octet-stream", b"x"), 999))
    assert result == {"type": "document", "file_id": "FILE9"}


def test_relay_to_telegram_forwards_caption(tmp_path, monkeypatch):
    from info import bot

    captured = {}

    async def fake_send_photo(chat_id, data, **kw):
        captured.update(kw)
        return make_msg(photo=[type("PS", (), {"file_id": "FILE7"})()])

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    result = asyncio.run(
        relay_to_telegram(make_field("a.png", "image/png", b"x"), 999, caption="our logo")
    )
    assert result == {"type": "photo", "file_id": "FILE7"}
    assert captured.get("caption") == "our logo"