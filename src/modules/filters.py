import os
import re
import time

from info import bot
from core.group_settings import (
    add_filter, delete_filter, read_filters,
    normalize_filter_keyword, validate_filter_keyword,
)
from core.replies import build_reply, send_reply
from core.storage import group_path
from core.utils import handle_errors, is_privileged, topic_kwargs, log_error
from core.activity import (log_event, user_label, chat_label)
from module_manager import gated_event
from telebot.formatting import hcode

FILTER_COOLDOWN_SECONDS = 8.0
MAX_MESSAGE_CHARS = 4000
# (chat_id, keyword) -> monotonic time of last attempt. In-memory only.
_recent_triggers = {}
# chat_id -> (file stamp, filters dict, [(keyword, compiled pattern, reply)]).
# Reused only while the file stamp is unchanged and read_filters() still hands
# back the same (cached) dict, so edits from the bot, the web panel or another
# process are picked up on the next message.
_compiled_filters = {}


def _filter_pattern(keyword):
    """Boundary match so punctuation and multi-word keywords still hit."""
    return re.compile(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.IGNORECASE)


def _compiled(chat_id):
    filters = read_filters(chat_id)
    try:
        st = os.stat(group_path("filters", chat_id))
        stamp = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None
    cached = _compiled_filters.get(chat_id)
    if cached is not None and cached[1] is filters and cached[0] == stamp:
        return cached[2]
    entries = [
        (keyword, _filter_pattern(keyword), reply_with)
        for keyword, reply_with in filters.items()
        if reply_with.get("type") != "unknown"  # legacy broken entry; never respond
    ]
    _compiled_filters[chat_id] = (stamp, filters, entries)
    return entries


def _on_cooldown(chat_id, keyword):
    now = time.monotonic()
    # Prune opportunistically so the dict can't grow without bound.
    if len(_recent_triggers) > 1000:
        cut = now - FILTER_COOLDOWN_SECONDS
        for key, ts in list(_recent_triggers.items()):
            if ts < cut:
                del _recent_triggers[key]
    last = _recent_triggers.get((chat_id, keyword))
    if last is not None and now - last < FILTER_COOLDOWN_SECONDS:
        return True
    _recent_triggers[(chat_id, keyword)] = now
    return False


@handle_errors
async def set_filter(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await bot.reply_to(m, "Please provide a keyword.")

    keyword = normalize_filter_keyword(parts[1])

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to save as a filter.")

    reply = build_reply(m.reply_to_message)
    if reply["type"] == "unknown" or not reply.get("data") or (
        reply["type"] == "text" and not reply["data"].strip()
    ):
        return await bot.reply_to(m, "That message type isn't supported for filters.")

    err = validate_filter_keyword(m.chat.id, keyword)
    if err:
        return await bot.reply_to(m, err)

    verb = "updated" if keyword in read_filters(m.chat.id) else "saved"
    add_filter(m.chat.id, keyword, reply=reply)
    await bot.reply_to(m, f"Filter for '{keyword}' {verb}.", **topic_kwargs(m))


@handle_errors
@gated_event('filter_trigger')
async def reply_to_filter(m):
    if getattr(m.chat, "type", None) == "private":
        return
    if not m.text:
        return

    entries = _compiled(m.chat.id)
    if not entries:
        return

    text = m.text.casefold()
    matches = []
    for keyword, pattern, reply_with in entries:
        match = pattern.search(text)
        if match:
            matches.append((match.start(), -len(keyword), keyword, reply_with))

    # Earliest in the message wins; ties go to the longer keyword.
    # One reply per message unless an earlier send fails.
    for _, _, keyword, reply_with in sorted(matches):
        if _on_cooldown(m.chat.id, keyword):
            continue
        try:
            await send_reply(m.chat.id, reply_with, **topic_kwargs(m))
        except Exception as e:
            # Passive trigger: log silently, keep trying the next match.
            await log_error(bot, e, m)
            continue
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
    if not filters:
        return await bot.send_message(m.chat.id, "No filters set.", **topic_kwargs(m))

    lines, chunks, size = [], [], 0
    for key in filters:
        line = hcode(key)
        if size + len(line) + 1 > MAX_MESSAGE_CHARS:
            chunks.append("\n".join(lines))
            lines, size = [], 0
        lines.append(line)
        size += len(line) + 1
    if lines:
        chunks.append("\n".join(lines))

    for i, chunk in enumerate(chunks):
        header = "Filters:\n" if i == 0 else ""
        await bot.send_message(m.chat.id, header + chunk, parse_mode="HTML", **topic_kwargs(m))


@handle_errors
async def remove_filter(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await bot.reply_to(m, "Please specify a filter to remove.")

    keyword = normalize_filter_keyword(parts[1])

    if keyword in read_filters(m.chat.id):
        delete_filter(m.chat.id, keyword)
        await bot.reply_to(m, f'Filter "{keyword}" removed.', **topic_kwargs(m))
    else:
        await bot.reply_to(m, f'Filter "{keyword}" not found.', **topic_kwargs(m))
