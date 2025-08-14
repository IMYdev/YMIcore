from info import bot
from core.imysdbMongo import IMYDB
from core.utils import log_error

async def is_user_admin(chat_id, user_id):
    chat_admins = await bot.get_chat_administrators(chat_id)
    for admin in chat_admins:
        if admin.user.id == user_id:
            return True
    return False

async def set_filter(m):
    try:
        if not await is_user_admin(m.chat.id, m.from_user.id):
            await bot.reply_to(m, "Admin only.")
            return
        parts = m.text.lower().split(maxsplit=1)
        if len(parts) < 2:
            await bot.reply_to(m, "Please provide a keyword.")
            return

        keyword = parts[1]
        chat_id = str(m.chat.id).lstrip('-')
        db = IMYDB(f'runtime/filters/{chat_id}_filters')

        if m.reply_to_message:
            if m.reply_to_message.text:
                reply_with = {"type": "text", "data": m.reply_to_message.text}
            elif m.reply_to_message.sticker:
                reply_with = {"type": "sticker", "data": m.reply_to_message.sticker.file_id}
            elif m.reply_to_message.photo:
                reply_with = {"type": "photo", "data": m.reply_to_message.photo[-1].file_id}
            elif m.reply_to_message.document:
                reply_with = {"type": "document", "data": m.reply_to_message.document.file_id}
            elif m.reply_to_message.audio:
                reply_with = {"type": "audio", "data": m.reply_to_message.audio.file_id}
            elif m.reply_to_message.video:
                reply_with = {"type": "video", "data": m.reply_to_message.video.file_id}
            else:
                reply_with = {"type": "unknown", "data": None}

            filters = db.get('filters', {})
            filters[keyword] = reply_with
            db.set('filters', filters)
            await bot.reply_to(m, "Filter saved.")
        else:
            await bot.reply_to(m, "Reply to a message to save as a filter.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

async def reply_to_filter(m):
    try:
        chat_id = str(m.chat.id).lstrip('-')
        db = IMYDB(f'runtime/filters/{chat_id}_filters')
        filters = db.get('filters', {})

        for keyword, reply_with in filters.items():
            if keyword in m.text.lower():
                t = reply_with["type"]
                d = reply_with["data"]
                if t == "text":
                    await bot.send_message(m.chat.id, d)
                elif t == "sticker":
                    await bot.send_sticker(m.chat.id, d)
                elif t == "photo":
                    await bot.send_photo(m.chat.id, d)
                elif t == "document":
                    await bot.send_document(m.chat.id, d)
                elif t == "audio":
                    await bot.send_audio(m.chat.id, d)
                elif t == "video":
                    await bot.send_video(m.chat.id, d)
                else:
                    await bot.send_message(m.chat.id, "Unsupported response type.")
                break
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

async def get_filters(m):
    chat_id = str(m.chat.id).lstrip('-')
    try:
        db = IMYDB(f'runtime/filters/{chat_id}_filters')
        filters = db.get('filters', {})
        if filters:
            output = '\n'.join([f"`{key}`" for key in filters])
            await bot.send_message(m.chat.id, f"Filters:\n{output}", parse_mode="Markdown")
        else:
            await bot.send_message(m.chat.id, "No filters set.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

async def remove_filter(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admin only.")
        return
    chat_id = str(m.chat.id).lstrip('-')
    try:
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.reply_to(m, "Please specify a filter to remove.")
            return

        keyword = parts[1]
        db = IMYDB(f'runtime/filters/{chat_id}_filters')
        filters = db.get('filters', {})

        if keyword in filters:
            del filters[keyword]
            db.set('filters', filters)
            await bot.send_message(m.chat.id, f'Filter "{keyword}" removed.')
        else:
            await bot.send_message(m.chat.id, f'Filter "{keyword}" not found.')
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")