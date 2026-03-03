from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import bot
from core.imysdb import IMYDB
from core.utils import is_user_admin

db = IMYDB('runtime/modules/module_controller.json')

modules = {
    'anime': ['animewall', 'sauce'],
    'admin': ['ban', 'unban', 'promote', 'demote', 'pin', 'purge'],
    'notes' : ['notes', 'add', 'remove'],
    'filters': ['filter', 'filist', 'stop'],
    'greetings': ['greeting', 'goodbye', 'setcaptcha', 'captcha'],
    'general': ['start', 'info', 'wallpaper', 'help', 'modules', 'id', 'music', 'spoiler', 'blockset', 'blocklist', 'unblockset']
}

default_disabled = {
}

def create_module_list_keyboard(group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for module in modules.keys():
        if module == 'general':
            continue
        
        current_permission = db.get(f"groups.{group_id}.{module}_enabled", True)
        button_text = f"{module.capitalize()} (Enabled)" if current_permission else f"{module.capitalize()} (Disabled)"
        module_button = InlineKeyboardButton(text=button_text, callback_data=f"show_commands:{module}:{group_id}")
        keyboard.add(module_button)
    
    return keyboard

def create_command_list_keyboard(module_name, group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)

    all_enabled = all(db.get(f"groups.{group_id}.{cmd}_enabled", True) for cmd in modules[module_name])
    select_all_text = "Deselect All" if all_enabled else "Select All"
    select_all_button = InlineKeyboardButton(text=select_all_text, callback_data=f"toggle_all_commands:{module_name}:{group_id}")
    keyboard.add(select_all_button)

    for command in modules[module_name]:
        default_state = default_disabled.get(command, True)
        current_permission = db.get(f"groups.{group_id}.{command}_enabled", default_state)
        command_text = f"{command} (On)" if current_permission else f"{command} (Off)"
        command_button = InlineKeyboardButton(text=command_text, callback_data=f"toggle_command:{command}:{group_id}")
        keyboard.add(command_button)
    back_button = InlineKeyboardButton(text="Back to Modules", callback_data=f"back_to_modules:{group_id}")
    keyboard.add(back_button)
    
    return keyboard

async def send_module_keyboard(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admin only.")
        return
    group_id = str(m.chat.id)
    keyboard = create_module_list_keyboard(group_id)
    await bot.send_message(m.chat.id, "Select a module to manage:", reply_markup=keyboard)

async def toggle_module_or_command(call):
    if not await is_user_admin(call.message.chat.id, call.from_user.id):
        return

    action, item, group_id = call.data.split(":")[0], call.data.split(":")[1], call.data.split(":")[2]

    if action == "toggle_command":
        default_state = default_disabled.get(item, True)
        current_permission = db.get(f"groups.{group_id}.{item}_enabled", default_state)
        db.set(f"groups.{group_id}.{item}_enabled", not current_permission)
        new_permission = db.get(f"groups.{group_id}.{item}_enabled", True)
        await bot.answer_callback_query(call.id, f"{item} command {'enabled' if new_permission else 'disabled'}")

        module_name = None
        for key, commands in modules.items():
            if item in commands:
                module_name = key
                break

        if module_name:
            keyboard = create_command_list_keyboard(module_name, group_id)
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    elif action == "toggle_all_commands":
        all_enabled = all(db.get(f"groups.{group_id}.{cmd}_enabled", True) for cmd in modules[item])
        for command in modules[item]:
            db.set(f"groups.{group_id}.{command}_enabled", not all_enabled)

        action = "deselected" if all_enabled else "selected"
        await bot.answer_callback_query(call.id, f"All commands in {item} {action}")

        keyboard = create_command_list_keyboard(item, group_id)
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)