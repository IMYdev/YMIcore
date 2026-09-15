import asyncio

from core.imysdb import IMYDB


def make_msg(text, chat_id):
    chat = type("Chat", (), {"id": chat_id, "title": "T", "username": None, "first_name": None})()
    return type("Msg", (), {"text": text, "chat": chat, "from_user": None})()


def test_get_notes_forwards_markdown_caption(tmp_path, monkeypatch):
    from info import bot
    from modules.notes import get_notes

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/notes/100_notes.json").set("notes", {
        "1": {"name": "pic", "reply": {"type": "photo", "data": "FILE1", "text": "**boom**"}}
    })
    captured = {}

    async def fake_send_photo(chat_id, photo, **kw):
        captured.update(kw)

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    asyncio.run(get_notes(make_msg("#1", 100)))
    assert captured["caption"] == "<b>boom</b>"
    assert captured["parse_mode"] == "HTML"


def test_get_notes_media_without_caption(tmp_path, monkeypatch):
    from info import bot
    from modules.notes import get_notes

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/notes/100_notes.json").set("notes", {
        "1": {"name": "pic", "reply": {"type": "photo", "data": "FILE1"}}
    })
    captured = {}

    async def fake_send_photo(chat_id, photo, **kw):
        captured.update(kw)

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    asyncio.run(get_notes(make_msg("#1", 100)))
    assert "caption" not in captured
    assert "parse_mode" not in captured


def test_reply_to_filter_forwards_caption(tmp_path, monkeypatch):
    from info import bot
    from modules.filters import reply_to_filter

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/filters/100_filters").set("filters", {
        "hello": {"type": "photo", "data": "FILE1", "text": "hi there"}
    })
    captured = {}

    async def fake_send_photo(chat_id, photo, **kw):
        captured.update(kw)

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    asyncio.run(reply_to_filter(make_msg("say hello", 100)))
    assert captured["caption"] == "hi there"


def test_reply_to_filter_media_without_caption(tmp_path, monkeypatch):
    from info import bot
    from modules.filters import reply_to_filter

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/filters/100_filters").set("filters", {
        "hello": {"type": "photo", "data": "FILE1"}
    })
    captured = {}

    async def fake_send_photo(chat_id, photo, **kw):
        captured.update(kw)

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    asyncio.run(reply_to_filter(make_msg("say hello", 100)))
    assert "caption" not in captured