from info import bot
from core.imysdb import IMYDB
from core.utils import log_error

async def is_user_admin(chat_id, user_id):
    chat_admins = await bot.get_chat_administrators(chat_id)
    for admin in chat_admins:

        if admin.user.id == user_id:
            return True

    return False

async def sticker_block(m):
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
    banned = db.get('stickers', [])

    if m.sticker and m.sticker.set_name in banned:
        await bot.delete_message(m.chat.id, m.id)

async def block_set(m):

    if not await is_user_admin(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admin only.")
        return

    if not m.reply_to_message:
        await bot.reply_to(m, "Reply to a sticker.")
        return

    elif not m.reply_to_message.sticker:
        await bot.reply_to(m, "Reply to a sticker.")
        return

    set_name = m.reply_to_message.sticker.set_name
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
    banned = db.get('stickers', [])

    if set_name not in banned:
        banned.append(set_name)
        db.set('stickers', banned)

    await bot.reply_to(m, "Sticker set added to blacklist.")

async def get_blacklist(m):
    chat_id = str(m.chat.id).lstrip('-')
    try:
        db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
        stickers = db.get('stickers', [])

        if stickers:
            output = '\n'.join([f"`{set_name}`" for set_name in stickers])
            await bot.send_message(m.chat.id, f"Banned sets:\n{output}", parse_mode="Markdown")
        else:
            await bot.send_message(m.chat.id, "No banned sets.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

async def unblock_set(m):

    if not await is_user_admin(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admin only.")
        return

    chat_id = str(m.chat.id).lstrip('-')
    try:
        parts = m.text.split(maxsplit=1)

        if len(parts) < 2:
            await bot.reply_to(m, "Please specify a sticker set to remove.")
            return

        set_name = parts[1]
        db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
        stickers = db.get('stickers') or []

        if set_name in stickers:
            stickers.remove(set_name)
            db.set('stickers', stickers)
            await bot.send_message(m.chat.id, f"Sticker set `{set_name}` unblocked.")

        else:
            await bot.send_message(m.chat.id, f"Sticker set `{set_name}` is not blocked.")

    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")