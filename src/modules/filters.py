from info import bot
from core.group_settings import add_filter, delete_filter, read_filters
from core.replies import build_reply, send_reply
from core.utils import handle_errors, is_privileged, topic_kwargs
from core.activity import (log_event, user_label, chat_label)


@handle_errors
async def set_filter(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    parts = m.text.lower().split(maxsplit=1)
    if len(parts) < 2:
        return await bot.reply_to(m, "Please provide a keyword.")

    keyword = parts[1]

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to save as a filter.")

    add_filter(m.chat.id, keyword, reply=build_reply(m.reply_to_message))
    await bot.reply_to(m, f"Filter for '{keyword}' saved.")

@handle_errors
async def reply_to_filter(m):
    if not m.text: return

    filters = read_filters(m.chat.id)
    words = m.text.lower().split()
    for keyword, reply_with in filters.items():
        if keyword in words:
            await send_reply(m.chat.id, reply_with, **topic_kwargs(m))
            log_event(
                "filter_trigger",
                chat_id=m.chat.id, chat_name=chat_label(m.chat),
                user_id=getattr(m.from_user, "id", None), user_name=user_label(m.from_user),
                detail=keyword,
            )
            break

@handle_errors
async def get_filters(m):
    filters = read_filters(m.chat.id)
    if filters:
        output = '\n'.join([f"`{key}`" for key in filters])
        await bot.send_message(m.chat.id, f"Filters:\n{output}", parse_mode="Markdown", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, "No filters set.", **topic_kwargs(m))

@handle_errors
async def remove_filter(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await bot.reply_to(m, "Please specify a filter to remove.")

    keyword = parts[1].lower()

    if keyword in read_filters(m.chat.id):
        delete_filter(m.chat.id, keyword)
        await bot.send_message(m.chat.id, f'Filter "{keyword}" removed.', **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, f'Filter "{keyword}" not found.', **topic_kwargs(m))
