import functools
import os
from itertools import chain

from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton)
from info import bot
from core.storage import module_db, MODULE_CONTROLLER
from core.utils import (is_privileged, topic_kwargs)

modules = {
    'anime': ['animewall', 'sauce'],
    'admin': ['ban', 'unban', 'promote', 'demote', 'pin', 'purge'],
    'notes': ['notes', 'add', 'remove'],
    'filters': ['filter', 'filist', 'stop'],
    'greetings': ['greeting', 'goodbye'],
    'captcha': ['setcaptcha', 'captcha', 'addcaptcha', 'delcaptcha', 'captchalist', 'captchatries'],
    'blocklist': ['blockset', 'blocklist', 'unblockset'],
    'downloader': [],
    'general': ['start', 'info', 'wallpaper', 'help', 'modules', 'id', 'spoiler'],
}

module_events = {
    'filters': ['filter_trigger'],
    'notes': ['note_fetch'],
    'greetings': ['greeting', 'farewell'],
    'captcha': ['captcha_verification'],
    'blocklist': ['sticker_block'],
    'downloader': ['link_download'],
}

EVENT_INFO = {
    'filter_trigger': ('Filter triggers', 'Reply when someone posts a saved keyword.'),
    'note_fetch': ('Note fetches', 'Send a note when someone writes #id.'),
    'greeting': ('Greetings', 'Welcome new members when they join.'),
    'farewell': ('Farewells', 'Say goodbye when a member leaves.'),
    'captcha_verification': ('Captcha verification', 'Require a captcha before new members can chat.'),
    'sticker_block': ('Sticker blocking', 'Delete stickers from blocked sets.'),
    'link_download': ('Link auto-download', 'Fetch media from supported links automatically.'),
}

COMMAND_ALIASES = {'nuke': 'purge'}
LEGACY_EVENT_COMMANDS = {'autodl': 'link_download'}
ALWAYS_ON = {'modules'}
UNSWITCHABLE_MODULES = {'general'}
UNMANAGED_COMMANDS = {'panel', 'devgroup', 'broadcast', 'bcast_list', 'bcast_delete', 'sub', 'unsub'}

default_disabled = {}
event_default_disabled = {}
module_default_disabled = {}

_COMMAND_MODULE = {}
for _module, _commands in modules.items():
    for _command in _commands:
        _COMMAND_MODULE[_command] = _module
_EVENT_MODULE = {}
for _module, _events in module_events.items():
    for _event in _events:
        _EVENT_MODULE[_event] = _module


# --------------------------------------------------------------------------
# Storage (stat-validated read cache).
# IMYDB reloads the whole file on construction; on a busy group a per-message
# gate would otherwise pay that full parse every message. The stamp changes on
# every atomic replace, so every writer (bot, web panel, tests) is seen.
# --------------------------------------------------------------------------

_groups_cache = {}


def _saved(gid):
    try:
        st = os.stat(MODULE_CONTROLLER)
    except OSError:
        st = None
    if st is None:
        data = module_db().get('groups', {}) or {}
    else:
        stamp = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
        cached = _groups_cache.get(MODULE_CONTROLLER)
        if cached and cached[0] == stamp:
            data = cached[1]
        else:
            try:
                data = module_db().get('groups', {}) or {}
            except Exception:
                if cached:
                    print(f"[!] module_controller.json unreadable; serving cached state")
                    data = cached[1]
                else:
                    raise
            _groups_cache[MODULE_CONTROLLER] = (stamp, data)
    saved = data.get(str(gid), {})
    return saved if isinstance(saved, dict) else {}


def module_of_command(command):
    return _COMMAND_MODULE.get(resolve_command(command))


def module_of_event(event):
    return _EVENT_MODULE.get(event)


def resolve_command(command):
    return COMMAND_ALIASES.get(command, command)


# --------------------------------------------------------------------------
# Resolution: effective = module_on AND component_flag, pinned wins.
# --------------------------------------------------------------------------

def command_flag(gid, command) -> bool:
    """RAW command state; 'autodl' reads the legacy event key."""
    command = resolve_command(command)
    legacy = LEGACY_EVENT_COMMANDS.get(command)
    if legacy:
        return event_flag(gid, legacy)
    saved = _saved(gid)
    return bool(saved.get(f'{command}_enabled', default_disabled.get(command, True)))


def event_flag(gid, event) -> bool:
    """RAW event state; falls back to the pre-event autodl_enabled key."""
    saved = _saved(gid)
    key = f'event_{event}_enabled'
    if key in saved:
        return bool(saved[key])
    if event == 'link_download' and 'autodl_enabled' in saved:
        return bool(saved['autodl_enabled'])
    return bool(event_default_disabled.get(event, True))


def is_module_enabled(gid, module) -> bool:
    if module in UNSWITCHABLE_MODULES:
        return True
    saved = _saved(gid)
    return bool(saved.get(
        f'module_{module}_enabled', module_default_disabled.get(module, True)
    ))


def is_command_enabled(gid, command) -> bool:
    command = resolve_command(command)
    if command in ALWAYS_ON:
        return True
    legacy = LEGACY_EVENT_COMMANDS.get(command)
    if legacy:
        return is_event_enabled(gid, legacy)
    module = module_of_command(command)
    if module and not is_module_enabled(gid, module):
        return False
    return command_flag(gid, command)


def is_event_enabled(gid, event) -> bool:
    module = module_of_event(event)
    if module and not is_module_enabled(gid, module):
        return False
    return event_flag(gid, event)


def set_command_enabled(gid, command, enabled) -> None:
    command = resolve_command(command)
    if command in ALWAYS_ON:
        return
    legacy = LEGACY_EVENT_COMMANDS.get(command)
    if legacy:
        set_event_enabled(gid, legacy, enabled)
        return
    module_db().set(f'groups.{gid}.{command}_enabled', bool(enabled))


def set_event_enabled(gid, event, enabled) -> None:
    module_db().set(f'groups.{gid}.event_{event}_enabled', bool(enabled))


def set_module_enabled(gid, module, enabled) -> None:
    if module in UNSWITCHABLE_MODULES:
        return
    module_db().set(f'groups.{gid}.module_{module}_enabled', bool(enabled))


def disabled_reason(gid, command):
    """'module' | 'command' | None for an incoming command name."""
    command = resolve_command(command)
    if command in ALWAYS_ON:
        return None
    legacy = LEGACY_EVENT_COMMANDS.get(command)
    if legacy:
        module = module_of_event(legacy)
        if module and not is_module_enabled(gid, module):
            return 'module'
        return None if event_flag(gid, legacy) else 'command'
    module = module_of_command(command)
    if module and not is_module_enabled(gid, module):
        return 'module'
    return None if command_flag(gid, command) else 'command'


def read_module_states(gid) -> dict:
    """RAW command flags, one entry per registered command (unchanged shape)."""
    saved = _saved(gid)
    return {
        command: saved.get(
            f'{command}_enabled', default_disabled.get(command, True)
        )
        for command in chain(*modules.values())
    }


def read_event_states(gid) -> dict:
    return {event: event_flag(gid, event) for event in chain(*module_events.values())}


def read_module_switches(gid) -> dict:
    return {
        module: is_module_enabled(gid, module)
        for module in modules if module not in UNSWITCHABLE_MODULES
    }


def module_stats(gid):
    enabled = sum(1 for c in chain(*modules.values()) if is_command_enabled(gid, c))
    enabled += sum(1 for e in chain(*module_events.values()) if is_event_enabled(gid, e))
    total = sum(len(v) for v in modules.values()) + sum(len(v) for v in module_events.values())
    return enabled, total


# --------------------------------------------------------------------------
# Event gating
# --------------------------------------------------------------------------

def gated_event(event):
    """Skip the handler when the event is off. Private chats are never gated."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(m, *args, **kwargs):
            chat = getattr(m, 'chat', None)
            chat_id = getattr(chat, 'id', None)
            if chat_id is None or getattr(chat, 'type', None) == 'private':
                return await func(m, *args, **kwargs)
            if not is_event_enabled(chat_id, event):
                return None
            return await func(m, *args, **kwargs)
        return wrapper
    return decorator


# --------------------------------------------------------------------------
# Bot keyboards and callbacks
# --------------------------------------------------------------------------

def _row_text(gid, kind, component, module_on):
    pinned = kind == 'command' and component in ALWAYS_ON
    raw = command_flag(gid, component) if kind == 'command' else event_flag(gid, component)
    label = component if kind == 'command' else EVENT_INFO.get(component, (component,))[0]
    text = f"{label} ({'On' if raw else 'Off'})"
    if pinned:
        text += ' (always on)'
    elif not module_on:
        text += ' (module off)'
    return text, pinned


def create_module_list_keyboard(group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for module in modules:
        if module in UNSWITCHABLE_MODULES:
            continue
        enabled = is_module_enabled(group_id, module)
        keyboard.add(
            InlineKeyboardButton(module.capitalize(), callback_data=f"show_commands:{module}:{group_id}"),
            InlineKeyboardButton('On' if enabled else 'Off', callback_data=f"toggle_module:{module}:{group_id}"),
        )
    return keyboard


def create_command_list_keyboard(module_name, group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    commands = modules.get(module_name, [])
    events = module_events.get(module_name, [])
    switchable = module_name not in UNSWITCHABLE_MODULES
    module_on = is_module_enabled(group_id, module_name)

    # all([]) is True; an empty module (downloader) must not offer Deselect All.
    toggleable_commands = [c for c in commands if c not in ALWAYS_ON]
    all_on = bool(toggleable_commands or events) and (
        all(command_flag(group_id, c) for c in toggleable_commands)
        and all(event_flag(group_id, e) for e in events)
    )
    keyboard.add(InlineKeyboardButton(
        'Deselect All' if all_on else 'Select All',
        callback_data=f'toggle_all_components:{module_name}:{group_id}',
    ))
    if switchable:
        keyboard.add(InlineKeyboardButton(
            f'Module: {"On" if module_on else "Off"}',
            callback_data=f'toggle_module:{module_name}:{group_id}',
        ))

    for command in commands:
        text, pinned = _row_text(group_id, 'command', command, module_on)
        keyboard.add(InlineKeyboardButton(
            text, callback_data=f'toggle_command:{command}:{group_id}'))
    for event in events:
        text, pinned = _row_text(group_id, 'event', event, module_on)
        keyboard.add(InlineKeyboardButton(
            text, callback_data=f'toggle_event:{event}:{group_id}'))
    keyboard.add(InlineKeyboardButton(
        text='Back to Modules', callback_data=f'back_to_modules:{group_id}'))
    return keyboard


async def send_module_keyboard(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admins only.")
        return
    group_id = str(m.chat.id)
    keyboard = create_module_list_keyboard(group_id)
    await bot.send_message(m.chat.id, "Select a module to manage:", reply_markup=keyboard, **topic_kwargs(m))


async def _edit_markup(call, keyboard):
    await bot.edit_message_reply_markup(
        call.message.chat.id, call.message.message_id, reply_markup=keyboard)


async def _refresh(call, module_name):
    await _edit_markup(call, create_command_list_keyboard(module_name, str(call.message.chat.id)))


async def show_commands(call):
    """Old keyboards still send show_commands; the gid in the data is not trusted."""
    if not await is_privileged(call.message.chat.id, call.from_user.id):
        return
    parts = call.data.split(':')
    module_name = parts[1] if len(parts) > 1 else ''
    if module_name not in modules:
        await bot.answer_callback_query(call.id, 'Unknown module.', show_alert=True)
        return
    await _refresh(call, module_name)


async def back_to_modules(call):
    if not await is_privileged(call.message.chat.id, call.from_user.id):
        return
    keyboard = create_module_list_keyboard(str(call.message.chat.id))
    await _edit_markup(call, keyboard)


async def toggle_module_or_command(call):
    if not await is_privileged(call.message.chat.id, call.from_user.id):
        return

    parts = call.data.split(':')
    action = parts[0] if parts else ''
    item = parts[1] if len(parts) > 1 else ''
    group_id = str(call.message.chat.id)

    if action == 'toggle_command':
        command = resolve_command(item)
        if command in ALWAYS_ON:
            await bot.answer_callback_query(call.id, f'{command} is always on.', show_alert=True)
            return
        current = command_flag(group_id, command)
        set_command_enabled(group_id, command, not current)
        await bot.answer_callback_query(call.id, f'{command} command {"enabled" if not current else "disabled"}')
        await _refresh(call, module_of_command(command) or item)

    elif action == 'toggle_event':
        if item not in _EVENT_MODULE:
            await bot.answer_callback_query(call.id, 'Unknown event.', show_alert=True)
            return
        current = event_flag(group_id, item)
        set_event_enabled(group_id, item, not current)
        await bot.answer_callback_query(call.id, f'{item} event {"enabled" if not current else "disabled"}')
        await _refresh(call, module_of_event(item) or item)

    elif action == 'toggle_module':
        if item in UNSWITCHABLE_MODULES:
            await bot.answer_callback_query(call.id, 'This module cannot be disabled.', show_alert=True)
            return
        current = is_module_enabled(group_id, item)
        set_module_enabled(group_id, item, not current)
        await bot.answer_callback_query(call.id, f'{item} module {"enabled" if not current else "disabled"}')
        # The list and the module screen both carry this button; tell them apart by the markup.
        markup = getattr(call.message, 'reply_markup', None)
        is_list = any(
            (btn.callback_data or '').startswith('show_commands')
            for row in getattr(markup, 'keyboard', []) for btn in row
        )
        if is_list:
            await _edit_markup(call, create_module_list_keyboard(group_id))
        elif item in modules:
            await _refresh(call, item)
        else:
            await _edit_markup(call, create_module_list_keyboard(group_id))

    elif action == 'toggle_all_commands':
        # Legacy keyboard path: commands only, never events.
        if item not in modules:
            await bot.answer_callback_query(call.id, 'Unknown module.', show_alert=True)
            return
        targets = [c for c in modules[item] if c not in ALWAYS_ON]
        if not targets:
            await bot.answer_callback_query(call.id, 'Nothing to toggle.')
            return
        all_on = all(command_flag(group_id, c) for c in targets)
        for command in targets:
            set_command_enabled(group_id, command, not all_on)
        await bot.answer_callback_query(call.id, f"All commands in {item} {'deselected' if all_on else 'selected'}")
        await _refresh(call, item)

    elif action == 'toggle_all_components':
        if item not in modules:
            await bot.answer_callback_query(call.id, 'Unknown module.', show_alert=True)
            return
        commands = [c for c in modules[item] if c not in ALWAYS_ON]
        events = module_events.get(item, [])
        if not commands and not events:
            await bot.answer_callback_query(call.id, 'Nothing to toggle.')
            return
        all_on = all(command_flag(group_id, c) for c in commands) and all(event_flag(group_id, e) for e in events)
        for command in commands:
            set_command_enabled(group_id, command, not all_on)
        for event in events:
            set_event_enabled(group_id, event, not all_on)
        await bot.answer_callback_query(
            call.id, f"All components in {item} {'deselected' if all_on else 'selected'}")
        await _refresh(call, item)
