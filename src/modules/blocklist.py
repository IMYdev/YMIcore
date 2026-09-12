from info import bot
from core.imysdb import IMYDB
from core.utils import (handle_errors, is_user_admin, get_args)

@handle_errors
async def sticker_block(m):
    if not m.sticker or not m.sticker.set_name:
        return

    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
    banned = db.get('stickers', [])

    if m.sticker.set_name in banned:
        try:
            await bot.delete_message(m.chat.id, m.message_id)
        except:
            pass

@handle_errors
async def block_set(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admin only.")

    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await bot.reply_to(m, "Reply to a sticker to block its set.")

    set_name = m.reply_to_message.sticker.set_name
    if not set_name:
        return await bot.reply_to(m, "This sticker doesn't belong to a set.")

    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
    banned = db.get('stickers', [])

    if set_name not in banned:
        banned.append(set_name)
        db.set('stickers', banned)
        await bot.reply_to(m, f"Sticker set `{set_name}` added to blacklist.")
    else:
        await bot.reply_to(m, f"Sticker set `{set_name}` is already blacklisted.")

@handle_errors
async def get_blacklist(m):
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
    stickers = db.get('stickers', [])

    if stickers:
        output = '\n'.join([f"`{name}`" for name in stickers])
        await bot.send_message(m.chat.id, f"Banned sticker sets:\n{output}", parse_mode="Markdown")
    else:
        await bot.send_message(m.chat.id, "No sticker sets are currently banned.")

@handle_errors
async def unblock_set(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admin only.")

    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Please specify a sticker set name to unblock.")

    set_name = args[0]
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/banned/{chat_id}_stickers.json')
    stickers = db.get('stickers', [])

    if set_name in stickers:
        stickers.remove(set_name)
        db.set('stickers', stickers)
        await bot.send_message(m.chat.id, f"Sticker set `{set_name}` unblocked.")
    else:
        await bot.send_message(m.chat.id, f"Sticker set `{set_name}` is not blocked.")
