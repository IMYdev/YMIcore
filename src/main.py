import asyncio
from telebot import types
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions)
from info import (bot, BOT_OWNER)
from core.utils import handle_errors, log_error, bot_me
from core.activity import (log_event, user_label, chat_label)
from core.users import migrate_users_registry, record_user
from core.permissions import (apply_chat_member_update, missing_rights,
                              refresh_permissions, right_label)
from modules.filters import reply_to_filter
from modules.notes import get_notes
from modules.member import help_categories
from module_manager import (
    is_event_enabled,
    resolve_command, module_of_command, disabled_reason,
    handle_mod_callback,
)
from modules.greetings import (hello, bye, send_standard_greeting)
from botcommands import (handle_command, COMMANDS)
from modules.blocklist import sticker_block, is_blocked_sticker, block_words, word_block_sweeper
from modules.broadcast import handle_broadcast_callback
from modules.migrate import handle_import_callback
from core.groups import ban_group_and_leave, is_banned, record_group
from web.server import start_web_server


def track_sender(m):
    """Remember the chat and, for private chats, the user behind it."""
    if getattr(m.chat, "type", None) != 'private':
        record_group(m.chat.id, getattr(m.chat, "title", None), getattr(m.chat, "type", None))
    if getattr(m.chat, "type", None) == 'private':
        record_user(getattr(m.from_user, "id", None),
                    user_label(m.from_user), getattr(m.from_user, "username", None))

async def addressed_to_us(text) -> bool:
    """False for /cmd@OtherBot. Only the command token is checked, so an @ in
    the arguments (/blockword @spammer, /filter a@b.com) is fine."""
    first = (text or "").split(maxsplit=1)[0] if (text or "").strip() else ""
    if '@' not in first:
        return True
    target = first.split('@', 1)[1].lower()
    username = (await bot_me()).username or ""
    return target == username.lower()


@bot.message_handler(commands=list(COMMANDS.keys()))
@handle_errors
async def cmd_handler(m):
    track_sender(m)

    if is_banned(m.chat.id):
        await bot.leave_chat(m.chat.id)
        return

    command = resolve_command(m.text.lstrip('/').split()[0].split('@')[0].lower())

    if command == "leave" and str(m.from_user.id) == str(BOT_OWNER):
        chat_id = m.chat.id
        args = m.text.split(" ", 1)
        if len(args) > 1:
            try:
                chat_id = int(args[1])
            except ValueError:
                pass

        await ban_group_and_leave(chat_id)
        await bot.reply_to(m, f"Leaving and banning group: {chat_id}")
        return

    if m.chat.type == 'private':
        restricted_in_pm = ['ban', 'unban', 'promote', 'demote', 'filter',
                            'filist', 'stop', 'remove', 'notes', 'add',
                            'goodbye', 'greeting', 'pin', 'modules', 'blockset',
                            'blocklist', 'unblockset', 'blockword', 'unblockword', 'blockwords', 'devgroup',
                            'warn', 'warnings', 'unwarn', 'mute', 'unmute', 'kick']
        if command in restricted_in_pm:
            await bot.reply_to(m, "This command is not available in private chats.")
            return
    else:
        if not await addressed_to_us(m.text):
            return

        await refresh_permissions(m.chat.id)
        reason = disabled_reason(m.chat.id, command)
        if reason == 'module':
            await bot.reply_to(m, f"The {module_of_command(command)} module is disabled in this group.")
            return
        if reason == 'command':
            await bot.reply_to(m, f"The {command} command is disabled in this group.")
            return
        if reason == 'permission':
            missing = missing_rights(m.chat.id, 'command', command)
            await bot.reply_to(m, f"I can't use /{command} here — I need permission to {right_label(missing)}.")
            return

    log_event(
        "command",
        chat_id=m.chat.id, chat_name=chat_label(m.chat),
        user_id=m.from_user.id, user_name=user_label(m.from_user),
        detail=command,
    )
    await handle_command(m)

@bot.chat_member_handler()
async def chat_m(m: types.ChatMemberUpdated):
    # A ChatMemberUpdated has nothing to reply to, so errors are only logged.
    try:
        if m.chat.type != 'private':
            await refresh_permissions(m.chat.id)
        await hello(m)
        await bye(m)
    except Exception as e:
        await log_error(bot, e, m)

@bot.my_chat_member_handler()
async def my_chat_m(m: types.ChatMemberUpdated):
    await apply_chat_member_update(m)

@bot.message_handler(content_types=['new_chat_members'])
@handle_errors
async def join_service_message(m):
    from modules.captcha import handle_join_service_message
    await handle_join_service_message(m)

@bot.message_handler()
async def reply_message(m):
    track_sender(m)
    if m.chat.type != 'private':
        await refresh_permissions(m.chat.id)
    if await block_words(m):
        return
    await reply_to_filter(m)
    await get_notes(m)

@bot.message_handler(content_types=['sticker'])
async def sticker_handler(m):
    if getattr(m.chat, 'type', None) != 'private':
        # Most stickers are not from a blocked set: answer that from disk
        # first, so they cost no Telegram request at all.
        if not is_blocked_sticker(m):
            return
        await refresh_permissions(m.chat.id)
        if not is_event_enabled(m.chat.id, 'sticker_block'):
            return
    await sticker_block(m)

@bot.callback_query_handler(func=lambda call: call.data.startswith("help_"))
async def help_category_switch(call):
    category = call.data.split("_")[1]
    markup = InlineKeyboardMarkup()
    buttons = [
        InlineKeyboardButton("General", callback_data="help_General"),
        InlineKeyboardButton("Admin", callback_data="help_Admin"),
    ]
    markup.add(*buttons)

    try:
        await bot.edit_message_text(
            help_categories[category],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise e

@bot.callback_query_handler(func=lambda call: call.data.startswith("mod:"))
async def mod_callback(call):
    await handle_mod_callback(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("bc_"))
async def broadcast_callback(call):
    await handle_broadcast_callback(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("imp:"))
async def import_callback(call):
    await handle_import_callback(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_cap:"))
async def verify_captcha(call):
    from modules.captcha import handle_captcha_callback
    await handle_captcha_callback(call)


async def main():
    print("Bot started...")
    migrate_users_registry()
    from modules.captcha import captcha_sweeper
    await asyncio.gather(
        _run_polling(), start_web_server(), captcha_sweeper(), word_block_sweeper(),
    )


async def _run_polling():
    try:
        await bot.infinity_polling(
            allowed_updates=['message', 'chat_member', 'my_chat_member', 'callback_query'],
            skip_pending=True,
        )
    except Exception as exc:
        print(f"[-] Fatal polling error, bot offline. Web panel keeps running: {exc}")

if __name__ == "__main__":
    asyncio.run(main())