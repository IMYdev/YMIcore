import functools
import traceback
from telebot.formatting import (hbold, hcode, format_text, escape_html)
from telebot.types import (InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions)
from datetime import datetime
from info import (Logs, ERROR_LOG_CHAT_ID, bot, BOT_OWNER)


async def log_error(bot, error, context_msg=None):
    if not Logs:
        return
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        user_info = "Unknown"
        chat_info = "Unknown"
        context_text = "No context"

        if context_msg:
            msg = getattr(context_msg, 'message', context_msg)
            user = getattr(context_msg, 'from_user', None)
            chat = getattr(msg, 'chat', None)

            if user:
                try:
                    name = escape_html(user.first_name or "User")
                    user_info = f"{name} (ID: {hcode(str(user.id))})"
                except Exception as e:
                    print(f"Error extracting user_info: {e}")

            if chat:
                try:
                    title = chat.title or chat.first_name or "Chat"
                    chat_info = f"{escape_html(title)} (ID: {hcode(str(chat.id))})"
                except Exception as e:
                    print(f"Error extracting chat_info: {e}")

            try:
                text = getattr(context_msg, 'text', None) or getattr(context_msg, 'data', None) or str(context_msg)
                context_text = escape_html(text[:1000]) # Limit length
            except:
                pass

        err_text = format_text(
            hbold("⚠️ Bot Error Report"),
            "",
            f"{hbold('🧑‍💻 User:')} {user_info}",
            f"{hbold('💬 Chat:')} {chat_info}",
            f"{hbold('🕒 Time:')} {hcode(timestamp)}",
            "",
            f"{hbold('📍 Context:')} {hcode(context_text)}",
            "",
            f"{hbold('🚨 Error:')}\n{hcode(str(error))}",
            "",
            f"{hbold('📜 Traceback:')}\n{hcode(traceback.format_exc())}"
        )

        await bot.send_message(ERROR_LOG_CHAT_ID, err_text, parse_mode="HTML")

    except Exception as log_err:
        print("Error while logging another error:", log_err)
        traceback.print_exc()


GENERIC_ERROR_REPLY = "Something went wrong. The error has been logged."


def handle_errors(func):
    """Decorator to handle errors and log them.

    The chat only gets a generic reply; the exception and traceback go to the
    error log chat, so internals never leak into groups.
    """
    @functools.wraps(func)
    async def wrapper(m, *args, **kwargs):
        try:
            return await func(m, *args, **kwargs)
        except Exception as e:
            await log_error(bot, e, m)
            try:
                await bot.reply_to(m, GENERIC_ERROR_REPLY)
            except Exception:
                pass
    return wrapper


_BOT_ME = None


async def bot_me():
    """The bot's own User, fetched once. A failed fetch is not cached."""
    global _BOT_ME
    if _BOT_ME is None:
        _BOT_ME = await bot.get_me()
    return _BOT_ME


def reset_bot_me() -> None:
    """Forget the cached bot identity (tests, or after a BotFather rename)."""
    global _BOT_ME
    _BOT_ME = None


async def is_moderatable(chat_id, user_id, *, require_admin=False) -> bool:
    """Whether a user can be moderated (warned/muted/kicked/banned).

    Parameters
    ----------
    require_admin=False
        If True, only normal members are eligible for modification.
        If False, exclude admins, creators, and the instance owner.
    """
    if is_owner_id(user_id):
        return False
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        status = member.status
    except Exception:
        return False
    if require_admin:
        return status == 'administrator'
    return status not in ('administrator', 'creator')

async def is_user_admin(chat_id, user_id):
    """Check if a user is an admin or creator in a chat."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

async def is_bot_owner(user_id):
    """Check if a user is the instance owner."""
    return is_owner_id(user_id)


def is_owner_id(user_id) -> bool:
    """Synchronous owner check, for code that cannot await."""
    return bool(BOT_OWNER) and str(user_id) == str(BOT_OWNER)


async def is_privileged(chat_id, user_id, *, allow_devgroup=False) -> bool:
    """Owner, chat admin, or (optionally) a developer-group member."""
    if await is_bot_owner(user_id):
        return True
    if allow_devgroup:
        from core.groups import is_developer_group
        if is_developer_group(chat_id):
            return True
    return await is_user_admin(chat_id, user_id)


async def is_user_owner(chat_id, user_id):
    """Check if a user is the creator (owner) of a chat."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status == 'creator'
    except Exception:
        return False


def get_args(m):
    """Extract arguments from a command message."""
    text = m.text or m.caption
    if not text:
        return []
    parts = text.split()
    return parts[1:] if len(parts) > 1 else []


async def get_target_user(m):
    """Extract target user from reply or arguments."""
    if m.reply_to_message:
        return m.reply_to_message.from_user
    
    args = get_args(m)
    if args:
        # Check if it's a mention or ID
        arg = args[0]
        if arg.startswith('@'):
            return None 
        try:
            user_id = int(arg)
            member = await bot.get_chat_member(m.chat.id, user_id)
            return member.user
        except:
            return None
    return None


def get_media_info(m):
    """Extract media type and file_id from a message."""
    if m.photo:
        return "photo", m.photo[-1].file_id
    elif m.video:
        return "video", m.video.file_id
    elif m.audio:
        return "audio", m.audio.file_id
    elif m.voice:
        return "voice", m.voice.file_id
    elif m.document:
        return "document", m.document.file_id
    elif m.sticker:
        return "sticker", m.sticker.file_id
    elif m.animation:
        return "animation", m.animation.file_id
    return None, None

def topic_kwargs(message):
    """Return the topic ID for an outgoing message."""
    thread_id = getattr(message, "message_thread_id", None)

    return {"message_thread_id": thread_id} if thread_id is not None else {}


def chunk_list(items, chunk_size=100):
    """Yield consecutive slices of at most chunk_size items."""
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def link_markup(button, row_width=1):
    """Inline keyboard holding a single URL button, or None."""
    if not button:
        return None
    markup = InlineKeyboardMarkup(row_width=row_width)
    markup.add(InlineKeyboardButton(button["text"], url=button["url"]))
    return markup


def mute_permissions() -> ChatPermissions:
    """Permissions for a muted member (no messaging, media, polls, previews)."""
    return ChatPermissions(
        can_send_messages=False, can_send_media_messages=False,
        can_send_polls=False, can_send_other_messages=False,
        can_add_web_page_previews=False, can_send_audios=False,
        can_send_documents=False, can_send_photos=False, can_send_videos=False,
        can_send_video_notes=False, can_send_voice_notes=False,
    )


def open_permissions() -> ChatPermissions:
    """Full permissions (normal chat member)."""
    return ChatPermissions(
        can_send_messages=True, can_send_media_messages=True,
        can_send_polls=True, can_send_other_messages=True,
        can_add_web_page_previews=True, can_send_audios=True,
        can_send_documents=True, can_send_photos=True, can_send_videos=True,
        can_send_video_notes=True, can_send_voice_notes=True,
    )
