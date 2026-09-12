from info import bot
from core.imysdb import IMYDB
from core.utils import (handle_errors, is_user_admin)

@handle_errors
async def set_filter(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admin only.")
    
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
    
    if msg.text: reply_with = {"type": "text", "data": msg.text}
    elif msg.sticker: reply_with = {"type": "sticker", "data": msg.sticker.file_id}
    elif msg.photo: reply_with = {"type": "photo", "data": msg.photo[-1].file_id}
    elif msg.document: reply_with = {"type": "document", "data": msg.document.file_id}
    elif msg.audio: reply_with = {"type": "audio", "data": msg.audio.file_id}
    elif msg.video: reply_with = {"type": "video", "data": msg.video.file_id}
    else: reply_with = {"type": "unknown", "data": None}

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
            if t == "text": await bot.send_message(m.chat.id, d)
            elif t == "sticker": await bot.send_sticker(m.chat.id, d)
            elif t == "photo": await bot.send_photo(m.chat.id, d)
            elif t == "document": await bot.send_document(m.chat.id, d)
            elif t == "audio": await bot.send_audio(m.chat.id, d)
            elif t == "video": await bot.send_video(m.chat.id, d)
            break

@handle_errors
async def get_filters(m):
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/filters/{chat_id}_filters')
    filters = db.get('filters', {})
    if filters:
        output = '\n'.join([f"`{key}`" for key in filters])
        await bot.send_message(m.chat.id, f"Filters:\n{output}", parse_mode="Markdown")
    else:
        await bot.send_message(m.chat.id, "No filters set.")

@handle_errors
async def remove_filter(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admin only.")
        
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
        await bot.send_message(m.chat.id, f'Filter "{keyword}" removed.')
    else:
        await bot.send_message(m.chat.id, f'Filter "{keyword}" not found.')
