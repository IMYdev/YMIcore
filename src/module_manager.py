from itertools import chain

from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton)
from info import bot
from core.storage import module_db
from core.utils import (is_privileged, topic_kwargs)

modules = {
    'anime': ['animewall', 'sauce'],
    'admin': ['ban', 'unban', 'promote', 'demote', 'pin', 'purge'],
    'notes' : ['notes', 'add', 'remove'],
    'filters': ['filter', 'filist', 'stop'],
    'greetings': ['greeting', 'goodbye', 'setcaptcha', 'captcha', 'addcaptcha', 'delcaptcha', 'captchalist', 'captchatries'],
    'downloader': ['autodl'],
    'general': ['start', 'info', 'wallpaper', 'help', 'modules', 'id', 'spoiler', 'blockset', 'blocklist', 'unblockset'],
}

default_disabled = {}


def is_command_enabled(group_id, command) -> bool:
    """Whether a command is enabled for a group; the one place defaults apply."""
    default_state = default_disabled.get(command, True)
    return module_db().get(f"groups.{group_id}.{command}_enabled", default_state)


def set_command_enabled(group_id, command, enabled) -> None:
    module_db().set(f"groups.{group_id}.{command}_enabled", bool(enabled))


def read_module_states(gid) -> dict:
    saved = module_db().get(f"groups.{gid}", {})
    states = {}
    for command in chain(*modules.values()):
        states[command] = saved.get(
            f"{command}_enabled", default_disabled.get(command, True)
        )
    return states


def module_stats(gid):
    states = read_module_states(gid)
    enabled = sum(1 for value in states.values() if value)
    return enabled, len(states)


def create_module_list_keyboard(group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)

    for module, cmds in modules.items():
        if module == 'general':
            continue

        # If at least one command is enabled then the module is active.
        any_enabled = any(is_command_enabled(group_id, cmd) for cmd in cmds)
        status_text = "Enabled" if any_enabled else "Disabled"
        button_text = f"{module.capitalize()} ({status_text})"

        module_button = InlineKeyboardButton(text=button_text, callback_data=f"show_commands:{module}:{group_id}")
        keyboard.add(module_button)

    return keyboard

def create_command_list_keyboard(module_name, group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)

    all_enabled = all(is_command_enabled(group_id, cmd) for cmd in modules[module_name])
    select_all_text = "Deselect All" if all_enabled else "Select All"
    select_all_button = InlineKeyboardButton(text=select_all_text, callback_data=f"toggle_all_commands:{module_name}:{group_id}")
    keyboard.add(select_all_button)

    for command in modules[module_name]:
        current_permission = is_command_enabled(group_id, command)
        command_text = f"{command} (On)" if current_permission else f"{command} (Off)"
        command_button = InlineKeyboardButton(text=command_text, callback_data=f"toggle_command:{command}:{group_id}")
        keyboard.add(command_button)
    back_button = InlineKeyboardButton(text="Back to Modules", callback_data=f"back_to_modules:{group_id}")
    keyboard.add(back_button)

    return keyboard

async def send_module_keyboard(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admins only.")
        return
    group_id = str(m.chat.id)
    keyboard = create_module_list_keyboard(group_id)
    await bot.send_message(m.chat.id, "Select a module to manage:", reply_markup=keyboard, **topic_kwargs(m))

async def toggle_module_or_command(call):
    if not await is_privileged(call.message.chat.id, call.from_user.id):
        return

    action, item, group_id = call.data.split(":")[0], call.data.split(":")[1], call.data.split(":")[2]

    if action == "toggle_command":
        current_permission = is_command_enabled(group_id, item)
        set_command_enabled(group_id, item, not current_permission)
        new_permission = is_command_enabled(group_id, item)
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
        all_enabled = all(is_command_enabled(group_id, cmd) for cmd in modules[item])
        for command in modules[item]:
            set_command_enabled(group_id, command, not all_enabled)

        action = "deselected" if all_enabled else "selected"
        await bot.answer_callback_query(call.id, f"All commands in {item} {action}")

        keyboard = create_command_list_keyboard(item, group_id)
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)
