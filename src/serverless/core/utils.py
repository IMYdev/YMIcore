import traceback
import os
from datetime import datetime
import html

ERROR_LOG_CHAT_ID = -int(os.getenv("LOG_ID"))  # Replace with your actual log channel/chat ID


async def log_error(bot, error, context_msg=None):
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
                chat_info = f"{html.escape(title)} (ID: <code>{chat.id}</code>)"
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

