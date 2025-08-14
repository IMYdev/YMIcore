from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import bot
from core.imysdbMongo import IMYDB

# Initialize the database
db = IMYDB('runtime/modules/module_controller.json')

# Define the main modules and categorize the commands
modules = {
    'anime': ['animewall', 'horny', 'sauce'],
    'admin': ['ban', 'unban', 'promote', 'demote', 'pin', 'purge', 'goodbye', 'greeting'],
    'notes' : ['notes', 'add', 'remove'],
    'filters': ['filter', 'filist', 'stop'],
    'greetings': ['greeting', 'goodbye'],
    'general': ['start', 'info', 'wallpaper', 'ask', 'imagine', 'help', 'reset', 'modules', 'id', 'music', 'leave']
}

# Disable adult features by default.
default_disabled = {
    'horny': False
}

# Function to check if the user is an admin
async def is_user_admin(chat_id, user_id):
    user = await bot.get_chat_member(chat_id, user_id)
    if user.status == "member" or user.status == "restricted":
        return False
    return True

# Create a keyboard to show modules first
def create_module_list_keyboard(group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for module in modules.keys():
        if module == 'general':
            continue  # Skip the 'general' module
        
        current_permission = db.get(f"groups.{group_id}.{module}_enabled", True)
        button_text = f"{module.capitalize()} (Enabled)" if current_permission else f"{module.capitalize()} (Disabled)"
        module_button = InlineKeyboardButton(text=button_text, callback_data=f"show_commands:{module}:{group_id}")
        keyboard.add(module_button)
    
    return keyboard

# Create a keyboard to show commands within a module
def create_command_list_keyboard(module_name, group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Add a "Select All" / "Deselect All" button
    all_enabled = all(db.get(f"groups.{group_id}.{cmd}_enabled", True) for cmd in modules[module_name])
    select_all_text = "Deselect All" if all_enabled else "Select All"
    select_all_button = InlineKeyboardButton(text=select_all_text, callback_data=f"toggle_all_commands:{module_name}:{group_id}")
    keyboard.add(select_all_button)

    # Add buttons for each command
    for command in modules[module_name]:
        default_state = default_disabled.get(command, True)
        current_permission = db.get(f"groups.{group_id}.{command}_enabled", default_state)
        command_text = f"{command} (On)" if current_permission else f"{command} (Off)"
        command_button = InlineKeyboardButton(text=command_text, callback_data=f"toggle_command:{command}:{group_id}")
        keyboard.add(command_button)
    # Add a "Back" button to return to the module list
    back_button = InlineKeyboardButton(text="Back to Modules", callback_data=f"back_to_modules:{group_id}")
    keyboard.add(back_button)
    
    return keyboard

# Function to send the initial module list keyboard
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

    # Split action, item (module or command), and group ID
    action, item, group_id = call.data.split(":")[0], call.data.split(":")[1], call.data.split(":")[2]

    if action == "toggle_command":
        # Toggle individual command
        default_state = default_disabled.get(item, True)
        current_permission = db.get(f"groups.{group_id}.{item}_enabled", default_state)
        db.set(f"groups.{group_id}.{item}_enabled", not current_permission)
        new_permission = db.get(f"groups.{group_id}.{item}_enabled", True)
        await bot.answer_callback_query(call.id, f"{item} command {'enabled' if new_permission else 'disabled'}")

        # Recreate the command list keyboard for the updated module
        module_name = None
        for key, commands in modules.items():
            if item in commands:
                module_name = key
                break

        if module_name:
            keyboard = create_command_list_keyboard(module_name, group_id)
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    elif action == "toggle_all_commands":
        # Toggle all commands in the module
        all_enabled = all(db.get(f"groups.{group_id}.{cmd}_enabled", True) for cmd in modules[item])
        for command in modules[item]:
            db.set(f"groups.{group_id}.{command}_enabled", not all_enabled)

        # Send confirmation message to user
        action = "deselected" if all_enabled else "selected"
        await bot.answer_callback_query(call.id, f"All commands in {item} {action}")

        # Recreate the keyboard with updated states
        keyboard = create_command_list_keyboard(item, group_id)
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)