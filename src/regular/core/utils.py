import traceback
import html
import functools
from datetime import datetime
from info import Logs, ERROR_LOG_CHAT_ID, bot


async def log_error(bot, error, context_msg=None):
    if not Logs:
        return
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        user_info = "Unknown"
        chat_info = "Unknown"
        context_text = "No context"

        if context_msg:
            try:
                user = context_msg.from_user
                user_info = f"{html.escape(user.first_name)} (ID: <code>{user.id}</code>)"
            except:
                pass

            try:
                chat = context_msg.chat
                title = chat.title or chat.first_name
                chat_info = f"{html.escape(title or 'Unknown')} (ID: <code>{chat.id}</code>)"
            except:
                pass

            try:
                context_text = html.escape(context_msg.text or str(context_msg))
            except:
                pass

        err_text = (
            f"⚠️ <b><u>Bot Error Report</u></b>\n\n"
            f"<b>🧑‍💻 User:</b> {user_info}\n"
            f"<b>💬 Chat:</b> {chat_info}\n"
            f"<b>🕒 Time:</b> <code>{timestamp}</code>\n\n"
            f"<b>📍 Context:</b> <code>{context_text}</code>\n\n"
            f"<b>🚨 Error:</b>\n<code>{html.escape(str(error))}</code>\n\n"
            f"<b>📜 Traceback:</b>\n<code>{html.escape(traceback.format_exc())}</code>"
        )

        await bot.send_message(ERROR_LOG_CHAT_ID, err_text, parse_mode="HTML")

    except Exception as log_err:
        print("Error while logging another error:", log_err)


def handle_errors(func):
    """Decorator to handle errors and log them."""
    @functools.wraps(func)
    async def wrapper(m, *args, **kwargs):
        try:
            return await func(m, *args, **kwargs)
        except Exception as e:
            await log_error(bot, e, m)
            try:
                await bot.reply_to(m, f"Error: {e}")
            except:
                pass
    return wrapper


async def is_user_admin(chat_id, user_id):
    """Check if a user is an admin or creator in a chat."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
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
