import traceback
import os
from datetime import datetime

ERROR_LOG_CHAT_ID = -int(os.getenv("LOG_ID"))  # Replace with your actual log channel/chat ID

async def log_error(bot, error, context_msg=None):
    """
    Send a detailed error report to the log chat.
    Includes user, chat, IDs, and timestamp.
    """
    try:
        m = context_msg  # this should be the message object from TeleBot
        user = m.from_user
        chat = m.chat

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        err_text = (
            f"⚠️ <b><u>Bot Error Report</u></b>\n\n"
            f"<b>🧑‍💻 User:</b> {user.first_name} (ID: <code>{user.id}</code>)\n"
            f"<b>💬 Chat:</b> {chat.title or chat.first_name} (ID: <code>{chat.id}</code>)\n"
            f"<b>🕒 Time:</b> <code>{timestamp}</code>\n\n"
            f"<b>📍 Context:</b> {m.text}\n\n"
            f"<b>🚨 Error:</b>\n<code>{str(error)}</code>\n\n"
            f"<b>📜 Traceback:</b>\n<code>{traceback.format_exc()}</code>"
        )

        await bot.send_message(ERROR_LOG_CHAT_ID, err_text, parse_mode="HTML")
    except Exception as log_err:
        print("Error while logging another error:", log_err)
