import asyncio
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.types import ChatPermissions
from info import (bot, BOT_OWNER)
from core.imysdb import IMYDB
from modules.downloader import extract_supported_url
from modules.filters import reply_to_filter
from modules.notes import get_notes
from modules.member import help_categories
from module_manager import create_command_list_keyboard, modules, create_module_list_keyboard, toggle_module_or_command, default_disabled
from modules.greetings import hello, bye, send_standard_greeting
from botcommands import handle_command
from modules.blocklist import sticker_block

async def is_module_enabled_in_group(command, chat_id):
    db = IMYDB('runtime/modules/module_controller.json')
    module_name = None
    for key, values in modules.items():
        if command in values:
            module_name = key
            break

    if module_name is None:
        return False
    
    group_id = str(chat_id)
    module_enabled = db.get(f"groups.{group_id}.{module_name}_enabled", True)
    default_state = default_disabled.get(command, True)
    current_permission = db.get(f"groups.{group_id}.{command}_enabled", default_state)
    return module_enabled and current_permission

@bot.message_handler(commands=['start', 'ban', 'unban', 'info', 'promote',
                                'demote', 'pin', 'id', 'image', 'wallpaper',
                                'ask', 'animewall', 'sauce', 'imagine',
                                'purge', 'filter', 'filist', 'stop', 'notes',
                                'remove', 'add', 'help', 'goodbye', 'greeting',
                                'reset', 'modules', 'q', 'music', 'leave',
                                'spoiler', 'blockset', 'blocklist', 'unblockset', 'setcaptcha', 'captcha'])

async def cmd_handler(m):
    db = IMYDB('runtime/banned/groups.json')
    banned = db.get("groups", {})

    if len(banned) >= 1:

        if str(m.chat.id) in str(banned['group_ids']):
            await bot.leave_chat(m.chat.id)

    command = m.text.lstrip('/').split()[0].split('@')[0]

    if command == "leave" and m.from_user.id == int(BOT_OWNER):
        chat_id = m.chat.id

        if len(m.text.split(" ", 1)) > 1:
            chat_id = m.text.split(" ", 1)[1]

        banned = db.get('groups', {})

        banned.setdefault('group_ids', [])

        if chat_id not in banned['group_ids']:
            banned['group_ids'].append(chat_id)

        db.set('groups', banned)

    if m.chat.type == 'private':
        restricted_in_pm = ['ban', 'unban', 'promote', 'demote', 'filter', 
                            'filist', 'stop', 'remove', 'notes', 'add',
                            'goodbye', 'greeting', 'pin', 'modules', 'blockset',
                            'blocklist', 'unblockset']
        if command in restricted_in_pm:
            await bot.reply_to(m, "This command is not available in private chats.")
            return

    else:
        if '@' in m.text:
            bot_username = (await bot.get_me()).username
            if m.text.split('@')[1].split()[0] != bot_username:
                return
        if not await is_module_enabled_in_group(command, m.chat.id):
            await bot.reply_to(m, f"The {command} command is disabled in this group.")
            return

    await handle_command(m, m.text.lower())

@bot.chat_member_handler()
async def chat_m(m: types.ChatMemberUpdated):
    await hello(m)
    await bye(m)

@bot.message_handler()
async def reply_message(m):
    await reply_to_filter(m)
    await get_notes(m)
    if "instagram.com/reel" or "youtube.com" or "youtu.be" or "tiktok.com" or "facebook.com" or "twitter.com" or "x.com" in m.text:
        await extract_supported_url(m)

@bot.message_handler(content_types=['sticker'])
async def sticker_handler(m):
    if not (await bot.get_chat_member(m.chat.id, bot.user.id)).can_delete_messages:
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
        if "message is not modified" in str(e):
            pass
        else:
            raise e

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_"))
async def handle_toggle_callback(call):
    await toggle_module_or_command(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("show_commands"))
async def handle_show_commands_callback(call):
    module_name, group_id = call.data.split(":")[1:]
    keyboard = create_command_list_keyboard(module_name, group_id)
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_modules"))
async def handle_back_to_modules_callback(call):
    group_id = call.data.split(":")[1]
    keyboard = create_module_list_keyboard(group_id)
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_cap:"))
async def verify_captcha(call):
    _, answer, user_id = call.data.split(":")
    if str(call.from_user.id) != user_id:
        return await bot.answer_callback_query(call.id, "This isn't your captcha!", show_alert=True)

    chat_id_str = str(call.message.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id_str}_greetings.json')
    
    max_tries = db.get('captcha_max_tries', 1)
    user_attempts = db.get('user_attempts', {})
    current_count = user_attempts.get(user_id, 0)

    if answer == db.get('captcha_ans'):
        await bot.restrict_chat_member(call.message.chat.id, int(user_id), 
            permissions=ChatPermissions(can_send_messages=True, can_send_polls=True, 
                                        can_send_other_messages=True, can_add_web_page_previews=True))
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        await bot.answer_callback_query(call.id, "Correct! Welcome.")
        await send_standard_greeting(call.message.chat.id, call.from_user, db)
        current_count += 1
        if current_count >= max_tries:
            await bot.answer_callback_query(call.id, "Too many failed attempts! You have been removed.", show_alert=True)
            await bot.ban_chat_member(call.message.chat.id, int(user_id))
            await bot.unban_chat_member(call.message.chat.id, int(user_id))
            await bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            user_attempts[user_id] = current_count
            db.set('user_attempts', user_attempts)
            await bot.answer_callback_query(call.id, f"Wrong! {max_tries - current_count} attempts left.", show_alert=True)

async def main():
    await bot.infinity_polling(allowed_updates=['message', 'chat_member', 'callback_query'], skip_pending=True)

if __name__ == "__main__":
    asyncio.run(main())