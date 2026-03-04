from info import bot
from core.imysdb import IMYDB
from core.utils import (handle_errors, is_user_admin, get_args)
from telebot.formatting import (format_text, hbold, hitalic, hcode)

@handle_errors
async def set_note(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admin only")
    
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
    if msg.text: reply_with = {"type": "text", "data": msg.text}
    elif msg.sticker: reply_with = {"type": "sticker", "data": msg.sticker.file_id}
    elif msg.photo: reply_with = {"type": "photo", "data": msg.photo[-1].file_id}
    elif msg.document: reply_with = {"type": "document", "data": msg.document.file_id}
    elif msg.video: reply_with = {"type": "video", "data": msg.video.file_id}
    else: reply_with = {"type": "unknown", "data": None}

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
        if t == "text": await bot.send_message(m.chat.id, d)
        elif t == "sticker": await bot.send_sticker(m.chat.id, d)
        elif t == "photo": await bot.send_photo(m.chat.id, d)
        elif t == "document": await bot.send_document(m.chat.id, d)
        elif t == "video": await bot.send_video(m.chat.id, d)
        else: await bot.send_message(m.chat.id, "Note is unreadable.")
    else:
        await bot.send_message(m.chat.id, f"No note with ID {note_id}.")

@handle_errors
async def notes_list(m):
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
    notes = db.get('notes', {})

    if not notes:
        return await bot.send_message(m.chat.id, "Catalog empty. No notes registered.")

    formatted_notes = '\n'.join([f"{hcode(str(nid))}. {n['name']}" for nid, n in notes.items()])
    formatted_reply = format_text(
        hitalic("Catalog of notes:"),
        formatted_notes,
        hbold("Retrieve notes via #note_number")
    )
    await bot.send_message(m.chat.id, formatted_reply, parse_mode="HTML")

@handle_errors
async def remove_note(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admin only")

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
        await bot.send_message(m.chat.id, f"Note ID {note_key} removed.")
    else:
        await bot.send_message(m.chat.id, f"No note matching ID {note_key} found.")
