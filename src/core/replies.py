"""Stored replies (notes and filters) share one build + send path."""

from info import bot
from core.formatting import markdown_to_html
from telebot.types import MessageEntity


def _entities(items):
    # custom_emoji often can't be re-sent by the bot; its text fallback is enough.
    return [e for e in (MessageEntity.to_list_of_dicts(items) or []) if e["type"] != "custom_emoji"]


def build_reply(msg) -> dict:
    """Turn a replied-to message into the dict stored by notes and filters."""
    caption = getattr(msg, "caption", None) or ""
    entities = _entities(getattr(msg, "entities", None))
    caption_entities = _entities(getattr(msg, "caption_entities", None))

    if msg.text: reply = {"type": "text", "data": msg.text}
    elif msg.sticker: reply = {"type": "sticker", "data": msg.sticker.file_id}
    elif msg.photo: reply = {"type": "photo", "data": msg.photo[-1].file_id, "text": caption}
    elif msg.document: reply = {"type": "document", "data": msg.document.file_id, "text": caption}
    elif msg.video: reply = {"type": "video", "data": msg.video.file_id, "text": caption}
    elif msg.audio: reply = {"type": "audio", "data": msg.audio.file_id, "text": caption}
    else: reply = {"type": "unknown", "data": None}

    if reply["type"] == "text" and entities:
        reply["entities"] = entities
    elif caption_entities:
        reply["caption_entities"] = caption_entities
    return reply


async def send_reply(chat_id, reply, *, fallback=None, **kwargs) -> None:
    """Send a stored reply dict; text and captions render markdown as HTML."""
    reply_type, data = reply["type"], reply["data"]
    caption = reply.get("text")
    entities = reply.get("entities")
    caption_entities = reply.get("caption_entities")

    if reply_type == "text":
        if entities:
            await bot.send_message(chat_id, data, entities=entities, **kwargs)
        else:
            await bot.send_message(chat_id, markdown_to_html(data or ""), parse_mode="HTML", **kwargs)
    elif reply_type == "sticker":
        await bot.send_sticker(chat_id, data, **kwargs)
    elif reply_type in ("photo", "document", "video", "audio"):
        send = getattr(bot, f"send_{reply_type}")
        if caption_entities:
            await send(chat_id, data, caption=caption, caption_entities=caption_entities, **kwargs)
        elif caption:
            await send(chat_id, data, caption=markdown_to_html(caption), parse_mode="HTML", **kwargs)
        else:
            await send(chat_id, data, **kwargs)
    elif fallback:
        await bot.send_message(chat_id, fallback, **kwargs)


__all__ = ["build_reply", "send_reply"]
