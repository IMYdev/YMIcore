import asyncio

from telebot.types import MessageEntity

from core.imysdb import IMYDB


def make_msg(text, chat_id, thread_id=None):
    chat = type("Chat", (), {"id": chat_id, "title": "T", "username": None, "first_name": None})()
    return type("Msg", (), {
        "text": text, "chat": chat, "from_user": None, "message_thread_id": thread_id,
    })()


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


def test_get_notes_replies_in_same_topic(tmp_path, monkeypatch):
    from info import bot
    from modules.notes import get_notes

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/notes/100_notes.json").set("notes", {
        "1": {"name": "hi", "reply": {"type": "text", "data": "hello"}}
    })
    captured = {}

    async def fake_send_message(chat_id, text, **kw):
        captured.update(kw)

    monkeypatch.setattr(bot, "send_message", fake_send_message)
    asyncio.run(get_notes(make_msg("#1", 100, thread_id=7)))
    assert captured["message_thread_id"] == 7


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


def make_reply_msg(**kwargs):
    defaults = {
        "text": None, "entities": None, "caption": None, "caption_entities": None,
        "sticker": None, "photo": None, "document": None, "video": None, "audio": None,
    }
    defaults.update(kwargs)
    return type("Msg", (), defaults)()


def test_set_note_stores_entities_without_custom_emoji(tmp_path, monkeypatch):
    import modules.notes as notes

    monkeypatch.chdir(tmp_path)

    async def fake_admin(*args, **kwargs):
        return True

    async def fake_reply(m, text, **kwargs):
        return None

    monkeypatch.setattr(notes, "is_user_admin", fake_admin)
    monkeypatch.setattr(notes.bot, "reply_to", fake_reply)

    command = make_msg("/add greet", 100)
    command.from_user = type("User", (), {"id": 999})()
    command.reply_to_message = make_reply_msg(
        text="hi there",
        entities=[MessageEntity("bold", 0, 2), MessageEntity("custom_emoji", 3, 5, custom_emoji_id="123")],
    )
    asyncio.run(notes.set_note(command))

    saved = IMYDB("runtime/notes/100_notes.json").get("notes")["1"]["reply"]
    assert saved["data"] == "hi there"
    assert saved["entities"][0]["type"] == "bold"
    assert all(e["type"] != "custom_emoji" for e in saved["entities"])


def test_get_notes_forwards_entities(tmp_path, monkeypatch):
    from info import bot
    from modules.notes import get_notes

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/notes/100_notes.json").set("notes", {
        "1": {"name": "hi", "reply": {
            "type": "text", "data": "hi there",
            "entities": [{"type": "bold", "offset": 0, "length": 2}],
        }}
    })
    captured = {}

    async def fake_send_message(chat_id, text, **kw):
        captured.update(kw)
        captured["text"] = text

    monkeypatch.setattr(bot, "send_message", fake_send_message)
    asyncio.run(get_notes(make_msg("#1", 100)))
    assert captured["text"] == "hi there"
    assert captured["entities"] == [{"type": "bold", "offset": 0, "length": 2}]
    assert "parse_mode" not in captured


def test_get_notes_forwards_caption_entities(tmp_path, monkeypatch):
    from info import bot
    from modules.notes import get_notes

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/notes/100_notes.json").set("notes", {
        "1": {"name": "pic", "reply": {
            "type": "photo", "data": "FILE1", "text": "hi there",
            "caption_entities": [{"type": "italic", "offset": 0, "length": 2}],
        }}
    })
    captured = {}

    async def fake_send_photo(chat_id, photo, **kw):
        captured.update(kw)

    monkeypatch.setattr(bot, "send_photo", fake_send_photo)
    asyncio.run(get_notes(make_msg("#1", 100)))
    assert captured["caption"] == "hi there"
    assert captured["caption_entities"] == [{"type": "italic", "offset": 0, "length": 2}]
    assert "parse_mode" not in captured


def test_reply_to_filter_forwards_entities(tmp_path, monkeypatch):
    from info import bot
    from modules.filters import reply_to_filter

    monkeypatch.chdir(tmp_path)
    IMYDB("runtime/filters/100_filters").set("filters", {
        "hello": {"type": "text", "data": "hi there", "entities": [{"type": "bold", "offset": 0, "length": 2}]}
    })
    captured = {}

    async def fake_send_message(chat_id, text, **kw):
        captured.update(kw)
        captured["text"] = text

    monkeypatch.setattr(bot, "send_message", fake_send_message)
    asyncio.run(reply_to_filter(make_msg("say hello", 100)))
    assert captured["text"] == "hi there"
    assert captured["entities"] == [{"type": "bold", "offset": 0, "length": 2}]