import asyncio
import os
import re
import time
from datetime import datetime, timedelta

from info import bot
from telebot.formatting import hcode
from core.group_settings import (
    add_sticker, delete_sticker, read_stickers,
    add_blocked_word, delete_blocked_word, read_blocked_words,
    increment_word_mute_count, read_word_mute_count,
    normalize_blocked_word, validate_blocked_word,
)
from core.storage import group_path
from core.utils import (chunk_list, get_args, handle_errors, is_moderatable, is_privileged,
                        mute_permissions, topic_kwargs)
from module_manager import gated_event

# Cached compiled word patterns per chat, invalidated on file change
_word_pattern_cache = {}  # chat_id -> (stamp, pattern or None)
_MAX_QUEUE = 100
_SWEEP_INTERVAL = 0.25
_word_queue = {}  # chat_id -> list of message ids

MAX_MUTE_SECONDS = 366 * 86400


def mute_duration_for(count: int) -> int:
    """Doubling mute ladder: 1m, 2m, 4m, 8m ... capped at Telegram's max."""
    seconds = 60 * (2 ** (count - 1))
    return min(seconds, MAX_MUTE_SECONDS)


def build_word_pattern(words):
    """Build regex from list of casefolded word/phrase strings."""
    # Sort by length to improve performance
    terms = sorted(words, key=len, reverse=True)
    # Multi-word phrase -> collapse whitespace with \s+
    alternatives = []
    for w in terms:
        parts = w.split()
        alternatives.append(r"\s+".join(re.escape(p) for p in parts))
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)", re.IGNORECASE)


def _word_pattern(chat_id):
    path = group_path("words", chat_id)
    try:
        st = os.stat(path)
        stamp = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None
    cached = _word_pattern_cache.get(chat_id)
    if cached and cached[0] == stamp:
        return cached[1]
    words = read_blocked_words(chat_id)
    pattern = build_word_pattern(words) if words else None
    _word_pattern_cache[chat_id] = (stamp, pattern)
    return pattern


async def _flush(chat_id):
    ids = _word_queue.pop(chat_id, None)
    if not ids:
        return
    for chunk in chunk_list(ids, 100):
        try:
            await bot.delete_messages(chat_id, chunk)
        except Exception:
            pass


async def word_block_sweeper():
    while True:
        await asyncio.sleep(_SWEEP_INTERVAL)
        try:
            for chat_id in list(_word_queue):
                await _flush(chat_id)
        except Exception:
            pass


def _enqueue(chat_id, message_id):
    q = _word_queue.setdefault(chat_id, [])
    q.append(message_id)
    if len(q) >= _MAX_QUEUE:
        asyncio.get_running_loop().create_task(_flush(chat_id))


@gated_event('word_block')
@handle_errors
async def block_words(m) -> bool:
    """Delete messages containing a blocked word. Returns True if handled."""
    if getattr(m.chat, "type", None) == "private":
        return False
    text = m.text or m.caption
    if not text or text.startswith('/'):
        return False
    pattern = _word_pattern(m.chat.id)
    if pattern is None:
        return False
    if not pattern.search(text.casefold()):
        return False
    _enqueue(m.chat.id, m.message_id)

    user = getattr(m, "from_user", None)
    if user is not None:
        await _maybe_mute(m.chat.id, user.id)
    return True


async def _maybe_mute(chat_id: int, user_id: int) -> None:
    """Mute the user with an escalating duration; escalation only counts on success."""
    if not await is_moderatable(chat_id, user_id):
        return  # admins, creators, and the bot owner are never muted
    count = read_word_mute_count(chat_id, user_id) + 1
    seconds = mute_duration_for(count)
    try:
        await bot.restrict_chat_member(
            chat_id, user_id,
            permissions=mute_permissions(),
            until_date=datetime.now() + timedelta(seconds=seconds),
        )
    except Exception:
        return  # missing rights or transient failure: don't escalate a mute that didn't happen
    increment_word_mute_count(chat_id, user_id)


# --------------------------------------------------------------------------
# Sticker blocklist
# --------------------------------------------------------------------------

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
        await bot.reply_to(m, f"Sticker set {hcode(set_name)} added to blacklist.", parse_mode="HTML")
    else:
        await bot.reply_to(m, f"Sticker set {hcode(set_name)} is already blacklisted.", parse_mode="HTML")


@handle_errors
async def get_blacklist(m):
    stickers = read_stickers(m.chat.id)

    if stickers:
        output = '\n'.join(hcode(name) for name in stickers)
        await bot.send_message(m.chat.id, f"Banned sticker sets:\n{output}", parse_mode="HTML", **topic_kwargs(m))
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
        await bot.send_message(m.chat.id, f"Sticker set {hcode(set_name)} unblocked.", parse_mode="HTML", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, f"Sticker set {hcode(set_name)} is not blocked.", parse_mode="HTML", **topic_kwargs(m))


# --------------------------------------------------------------------------
# Word blocklist commands
# --------------------------------------------------------------------------

@handle_errors
async def block_word(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Please provide a word or phrase to block.")
    word = " ".join(args)
    try:
        added = add_blocked_word(m.chat.id, word)
    except ValueError as e:
        return await bot.reply_to(m, str(e))
    if added:
        await bot.reply_to(m, f"Word {hcode(word)} added to blocklist.", parse_mode="HTML", **topic_kwargs(m))
    else:
        await bot.reply_to(m, f"Word {hcode(word)} is already blocked.", parse_mode="HTML", **topic_kwargs(m))


@handle_errors
async def unblock_word(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Please specify a word or phrase to unblock.")
    word = " ".join(args)
    if delete_blocked_word(m.chat.id, word):
        await bot.reply_to(m, f"Word {hcode(word)} removed from blocklist.", parse_mode="HTML", **topic_kwargs(m))
    else:
        await bot.reply_to(m, f"Word {hcode(word)} was not blocked.", parse_mode="HTML", **topic_kwargs(m))


@handle_errors
async def list_blocked_words(m):
    words = read_blocked_words(m.chat.id)
    if not words:
        return await bot.send_message(m.chat.id, "No blocked words.", **topic_kwargs(m))

    lines, chunks, size = [], [], 0
    MAX_MSG_CHARS = 4000
    for w in words:
        line = hcode(w)
        if size + len(line) + 1 > MAX_MSG_CHARS:
            chunks.append("\n".join(lines))
            lines, size = [], 0
        lines.append(line)
        size += len(line) + 1
    if lines:
        chunks.append("\n".join(lines))

    for i, chunk in enumerate(chunks):
        header = "Blocked words:\n" if i == 0 else ""
        await bot.send_message(m.chat.id, header + chunk, parse_mode="HTML", **topic_kwargs(m))
