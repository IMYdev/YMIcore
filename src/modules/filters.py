from info import bot
from core.db import IMYDB
from core.utils import (handle_errors, is_user_admin, is_bot_owner, topic_kwargs)
from core.activity import (log_event, user_label, chat_label)
from telebot.types import MessageEntity


def _entities(items):
    # custom_emoji often can't be re-sent by the bot; its text fallback is enough.
    return [e for e in (MessageEntity.to_list_of_dicts(items) or []) if e["type"] != "custom_emoji"]

@handle_errors
async def set_filter(m):
    if not await is_user_admin(m.chat.id, m.from_user.id) and not await is_bot_owner(m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    parts = m.text.lower().split(maxsplit=1)
    if len(parts) < 2:
        return await bot.reply_to(m, "Please provide a keyword.")

    keyword = parts[1]
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/filters/{chat_id}_filters')

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to save as a filter.")

    reply_with = {}
    msg = m.reply_to_message
    caption = getattr(msg, "caption", None) or ""
    entities = _entities(getattr(msg, "entities", None))
    caption_entities = _entities(getattr(msg, "caption_entities", None))

    if msg.text: reply_with = {"type": "text", "data": msg.text}
    elif msg.sticker: reply_with = {"type": "sticker", "data": msg.sticker.file_id}
    elif msg.photo: reply_with = {"type": "photo", "data": msg.photo[-1].file_id, "text": caption}
    elif msg.document: reply_with = {"type": "document", "data": msg.document.file_id, "text": caption}
    elif msg.audio: reply_with = {"type": "audio", "data": msg.audio.file_id, "text": caption}
    elif msg.video: reply_with = {"type": "video", "data": msg.video.file_id, "text": caption}
    else: reply_with = {"type": "unknown", "data": None}

    if reply_with["type"] == "text" and entities:
        reply_with["entities"] = entities
    elif caption_entities:
        reply_with["caption_entities"] = caption_entities

    filters = db.get('filters', {})
    filters[keyword] = reply_with
    db.set('filters', filters)
    await bot.reply_to(m, f"Filter for '{keyword}' saved.")

@handle_errors
async def reply_to_filter(m):
    if not m.text: return
    
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/filters/{chat_id}_filters')
    filters = db.get('filters', {})
    
    words = m.text.lower().split()
    for keyword, reply_with in filters.items():
        if keyword in words:
            t, d = reply_with["type"], reply_with["data"]
            caption = reply_with.get("text")
            entities = reply_with.get("entities")
            caption_entities = reply_with.get("caption_entities")
            if t == "text":
                if entities: await bot.send_message(m.chat.id, d, entities=entities, **topic_kwargs(m))
                else: await bot.send_message(m.chat.id, d, **topic_kwargs(m))
            elif t == "sticker": await bot.send_sticker(m.chat.id, d, **topic_kwargs(m))
            elif t == "photo":
                if caption_entities: await bot.send_photo(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
                elif caption: await bot.send_photo(m.chat.id, d, caption=caption, **topic_kwargs(m))
                else: await bot.send_photo(m.chat.id, d, **topic_kwargs(m))
            elif t == "document":
                if caption_entities: await bot.send_document(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
                elif caption: await bot.send_document(m.chat.id, d, caption=caption, **topic_kwargs(m))
                else: await bot.send_document(m.chat.id, d, **topic_kwargs(m))
            elif t == "audio":
                if caption_entities: await bot.send_audio(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
                elif caption: await bot.send_audio(m.chat.id, d, caption=caption, **topic_kwargs(m))
                else: await bot.send_audio(m.chat.id, d, **topic_kwargs(m))
            elif t == "video":
                if caption_entities: await bot.send_video(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
                elif caption: await bot.send_video(m.chat.id, d, caption=caption, **topic_kwargs(m))
                else: await bot.send_video(m.chat.id, d, **topic_kwargs(m))
            log_event(
                "filter_trigger",
                chat_id=m.chat.id, chat_name=chat_label(m.chat),
                user_id=getattr(m.from_user, "id", None), user_name=user_label(m.from_user),
                detail=keyword,
            )
            break

@handle_errors
async def get_filters(m):
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/filters/{chat_id}_filters')
    filters = db.get('filters', {})
    if filters:
        output = '\n'.join([f"`{key}`" for key in filters])
        await bot.send_message(m.chat.id, f"Filters:\n{output}", parse_mode="Markdown", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, "No filters set.", **topic_kwargs(m))

@handle_errors
async def remove_filter(m):
    if not await is_user_admin(m.chat.id, m.from_user.id) and not await is_bot_owner(m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
        
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await bot.reply_to(m, "Please specify a filter to remove.")

    keyword = parts[1].lower()
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/filters/{chat_id}_filters')
    filters = db.get('filters', {})

    if keyword in filters:
        del filters[keyword]
        db.set('filters', filters)
        await bot.send_message(m.chat.id, f'Filter "{keyword}" removed.', **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, f'Filter "{keyword}" not found.', **topic_kwargs(m))
