from info import bot
from core.imysdb import IMYDB
from core.utils import (handle_errors, is_user_admin, is_user_owner, get_args, topic_kwargs)
from core.activity import (log_event, user_label, chat_label)
from core.formatting import markdown_to_html
from telebot.formatting import (format_text, hbold, hitalic, hcode)
from telebot.types import MessageEntity
from web.groups import set_developer_group, is_developer_group


def _entities(items):
    # custom_emoji often can't be re-sent by the bot; its text fallback is enough.
    return [e for e in (MessageEntity.to_list_of_dicts(items) or []) if e["type"] != "custom_emoji"]

@handle_errors
async def set_note(m):
    if not (await is_user_admin(m.chat.id, m.from_user.id) or is_developer_group(m.chat.id)):
        return await bot.reply_to(m, "Admins only")
    
    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Please provide a note name.")
    
    note_name = args[0]
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/notes/{chat_id}_notes.json')

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to save as a note.")

    msg = m.reply_to_message
    reply_with = {}
    caption = getattr(msg, "caption", None) or ""
    entities = _entities(getattr(msg, "entities", None))
    caption_entities = _entities(getattr(msg, "caption_entities", None))
    if msg.text: reply_with = {"type": "text", "data": msg.text}
    elif msg.sticker: reply_with = {"type": "sticker", "data": msg.sticker.file_id}
    elif msg.photo: reply_with = {"type": "photo", "data": msg.photo[-1].file_id, "text": caption}
    elif msg.document: reply_with = {"type": "document", "data": msg.document.file_id, "text": caption}
    elif msg.video: reply_with = {"type": "video", "data": msg.video.file_id, "text": caption}
    elif msg.audio: reply_with = {"type": "audio", "data": msg.audio.file_id, "text": caption}
    else: reply_with = {"type": "unknown", "data": None}

    if reply_with["type"] == "text" and entities:
        reply_with["entities"] = entities
    elif caption_entities:
        reply_with["caption_entities"] = caption_entities

    notes = db.get('notes', {})
    next_id = max(map(int, notes.keys()), default=0) + 1
    notes[str(next_id)] = {"name": note_name, "reply": reply_with}
    db.set('notes', notes)

    await bot.reply_to(m, f"Note saved. ID: {next_id}.")

@handle_errors
async def get_notes(m):
    if not m.text or not m.text.startswith("#") or not m.text[1:].isdigit():
        return
    
    note_id = m.text[1:]
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
    notes = db.get('notes', {})

    if note_id in notes:
        note = notes[note_id]
        t, d = note['reply']['type'], note['reply']['data']
        caption = note['reply'].get('text')
        entities = note['reply'].get('entities')
        caption_entities = note['reply'].get('caption_entities')
        if t == "text":
            if entities: await bot.send_message(m.chat.id, d, entities=entities, **topic_kwargs(m))
            else: await bot.send_message(m.chat.id, markdown_to_html(d), parse_mode="HTML", **topic_kwargs(m))
        elif t == "sticker": await bot.send_sticker(m.chat.id, d, **topic_kwargs(m))
        elif t == "photo":
            if caption_entities: await bot.send_photo(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
            elif caption: await bot.send_photo(m.chat.id, d, caption=markdown_to_html(caption), parse_mode="HTML", **topic_kwargs(m))
            else: await bot.send_photo(m.chat.id, d, **topic_kwargs(m))
        elif t == "document":
            if caption_entities: await bot.send_document(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
            elif caption: await bot.send_document(m.chat.id, d, caption=markdown_to_html(caption), parse_mode="HTML", **topic_kwargs(m))
            else: await bot.send_document(m.chat.id, d, **topic_kwargs(m))
        elif t == "video":
            if caption_entities: await bot.send_video(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
            elif caption: await bot.send_video(m.chat.id, d, caption=markdown_to_html(caption), parse_mode="HTML", **topic_kwargs(m))
            else: await bot.send_video(m.chat.id, d, **topic_kwargs(m))
        elif t == "audio":
            if caption_entities: await bot.send_audio(m.chat.id, d, caption=caption, caption_entities=caption_entities, **topic_kwargs(m))
            elif caption: await bot.send_audio(m.chat.id, d, caption=markdown_to_html(caption), parse_mode="HTML", **topic_kwargs(m))
            else: await bot.send_audio(m.chat.id, d, **topic_kwargs(m))
        else: await bot.send_message(m.chat.id, "Note is unreadable.", **topic_kwargs(m))
        log_event(
            "note_fetch",
            chat_id=m.chat.id, chat_name=chat_label(m.chat),
            user_id=getattr(m.from_user, "id", None), user_name=user_label(m.from_user),
            detail=note.get("name") or f"#{note_id}",
        )
    else:
        await bot.send_message(m.chat.id, f"No note with ID {note_id}.", **topic_kwargs(m))

@handle_errors
async def notes_list(m):
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
    notes = db.get('notes', {})

    if not notes:
        return await bot.send_message(m.chat.id, "Catalog empty. No notes registered.", **topic_kwargs(m))

    formatted_notes = '\n'.join([f"{hcode(str(nid))}. {n['name']}" for nid, n in notes.items()])
    formatted_reply = format_text(
        hitalic("Catalog of notes:"),
        formatted_notes,
        hbold("Retrieve notes via #note_number")
    )
    await bot.send_message(m.chat.id, formatted_reply, parse_mode="HTML", **topic_kwargs(m))

@handle_errors
async def remove_note(m):
    if not (await is_user_admin(m.chat.id, m.from_user.id) or is_developer_group(m.chat.id)):
        return await bot.reply_to(m, "Admins only")
    
    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Command error: Note ID required for removal.")
    
    note_key = args[0]
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
    notes = db.get('notes', {})
    
    if note_key in notes:
        del notes[note_key]
        # Renumber remaining notes strictly
        notes = {str(i+1): v for i, (k, v) in enumerate(notes.items())}
        db.set('notes', notes)
        await bot.send_message(m.chat.id, f"Note ID {note_key} removed.", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, f"No note matching ID {note_key} found.", **topic_kwargs(m))


async def devgroup_command(message):
    args = get_args(message)
    if not args or args[0] not in ("on", "off"):
        return await bot.reply_to(message, "Usage: /devgroup on|off")
    chat_id = message.chat.id
    if not await is_user_owner(chat_id, message.from_user.id):
        return await bot.reply_to(message, "Only the group owner can toggle developer mode.")
    enabled = args[0] == "on"
    set_developer_group(chat_id, enabled)
    await bot.reply_to(message, f"Developer group mode {'enabled' if enabled else 'disabled'}.")
