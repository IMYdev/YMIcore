import asyncio
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import bot
from core.imysdb import IMYDB
from modules.downloader import extract_supported_url
from modules.filters import reply_to_filter
from modules.notes import get_notes
from modules.member import help_categories
from module_manager import create_command_list_keyboard, modules, create_module_list_keyboard, toggle_module_or_command
from modules.greetings import hello, bye
from botcommands import my_comd

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
    command_enabled = db.get(f"groups.{group_id}.{command}_enabled", True)
    return module_enabled and command_enabled

@bot.message_handler(commands=['start', 'ban', 'unban', 'info', 'promote', 'demote', 'pin', 'id', 'face', 'image', 'wallpaper', 'ask', 'animewall', 'horny', 'sauce', 'imagine', 'purge', 'filter', 'filters', 'stop', 'notes', 'remove', 'add', 'help', 'goodbye', 'greeting', 'kickme', 'reset', 'create_fed', 'join_fed', 'leave_fed', 'fban', 'funban', 'feds', 'fpromote', 'fdemote', 'delete_fed', 'modules', 'q'])
async def myc(m):
    restricted_in_pm = ['ban', 'unban', 'promote', 'demote', 'filter', 'filters', 'kickme', 'stop', 'remove', 'notes', 'add', 'goodbye', 'greeting', 'pin', 'create_fed', 'join_fed', 'leave_fed', 'fban', 'funban', 'feds', 'fpromote', 'fdemote', 'delete_fed', 'modules']
    if m.chat.type == 'private' and m.text.lstrip('/').split()[0].split('@')[0] in restricted_in_pm:
        await bot.reply_to(m, "This command is not available in private chats.")
        return
    command = m.text.lstrip('/').split()[0].split('@')[0]
    if '@' in m.text:
        bot_username = (await bot.get_me()).username
        if m.text.split('@')[1].split()[0] != bot_username:
            return
    if not await is_module_enabled_in_group(command, m.chat.id):
        await bot.reply_to(m, f"The {command} command is disabled in this group.")
        return
    await my_comd(m)

@bot.chat_member_handler()
async def chat_m(m: types.ChatMemberUpdated):
    await hello(m)
    await bye(m)

@bot.message_handler(func=lambda m: True)
async def reply_message(m):
    await reply_to_filter(m)
    await get_notes(m)
    if "instagram.com/reel" or "youtube.com" or "youtu.be" or "tiktok.com" in m.text:
        await extract_supported_url(m)

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

async def main():
    await bot.infinity_polling(allowed_updates=['message', 'chat_member', 'callback_query'])

if __name__ == "__main__":
    asyncio.run(main())
