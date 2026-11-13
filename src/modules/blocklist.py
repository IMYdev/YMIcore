from info import bot
from core.group_settings import add_sticker, delete_sticker, read_stickers
from core.utils import (handle_errors, is_privileged, get_args, topic_kwargs)

@handle_errors
async def sticker_block(m):
    if not m.sticker or not m.sticker.set_name:
        return

    if m.sticker.set_name in read_stickers(m.chat.id):
        try:
            await bot.delete_message(m.chat.id, m.message_id)
        except:
            pass

@handle_errors
async def block_set(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await bot.reply_to(m, "Reply to a sticker to block its set.")

    set_name = m.reply_to_message.sticker.set_name
    if not set_name:
        return await bot.reply_to(m, "This sticker doesn't belong to a set.")

    if add_sticker(m.chat.id, set_name):
        await bot.reply_to(m, f"Sticker set `{set_name}` added to blacklist.")
    else:
        await bot.reply_to(m, f"Sticker set `{set_name}` is already blacklisted.")

@handle_errors
async def get_blacklist(m):
    stickers = read_stickers(m.chat.id)

    if stickers:
        output = '\n'.join([f"`{name}`" for name in stickers])
        await bot.send_message(m.chat.id, f"Banned sticker sets:\n{output}", parse_mode="Markdown", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, "No sticker sets are currently banned.", **topic_kwargs(m))

@handle_errors
async def unblock_set(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Please specify a sticker set name to unblock.")

    set_name = args[0]

    if set_name in read_stickers(m.chat.id):
        delete_sticker(m.chat.id, set_name)
        await bot.send_message(m.chat.id, f"Sticker set `{set_name}` unblocked.", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, f"Sticker set `{set_name}` is not blocked.", **topic_kwargs(m))
