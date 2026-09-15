from info import WEB_URL, WEB_BIND, WEB_PORT, bot
from core.utils import handle_errors, is_user_admin
from web.auth import is_owner, rotate_admin_token


@handle_errors
async def panel_command(m):
    user_id = m.from_user.id
    if not (is_owner(user_id) or await is_user_admin(m.chat.id, user_id)):
        return await bot.reply_to(m, "Admins only.")
    base = WEB_URL or f"http://{WEB_BIND}:{WEB_PORT}"
    token, _ = rotate_admin_token(user_id, "panel")
    message = (
        f"Your YMIcore panel token:\n\n<code>{token}</code>\n\n"
        f"Open {base} and paste it in, or use:\n{base}/?t={token}\n\n"
        "Never share this token. Re-run /panel anytime to rotate it (this revokes the old one)."
    )
    try:
        await bot.send_message(user_id, message, parse_mode="HTML")
    except Exception:
        await bot.reply_to(m, f"Your YMIcore panel token:\n\n{token}\n\nOpen {base} and paste it in.")