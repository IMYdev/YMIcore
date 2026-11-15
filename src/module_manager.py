import functools
import os
from itertools import chain

from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton)
from info import bot
from core.storage import module_db, MODULE_CONTROLLER
from core.utils import (is_privileged, topic_kwargs)

# Pagination configuration
MODULES_PER_PAGE = 5

modules = {
    'anime': ['animewall', 'sauce'],
    'admin': ['ban', 'unban', 'promote', 'demote', 'pin', 'purge'],
    'notes': ['notes', 'add', 'remove'],
    'filters': ['filter', 'filist', 'stop'],
    'greetings': ['greeting', 'goodbye'],
    'captcha': ['setcaptcha', 'captcha', 'addcaptcha', 'delcaptcha', 'captchalist', 'captchatries'],
    'blocklist': ['blockset', 'blocklist', 'unblockset', 'blockword', 'unblockword', 'blockwords'],
    'downloader': [],
    'general': ['start', 'info', 'wallpaper', 'help', 'modules', 'id', 'spoiler'],
}

module_events = {
    'filters': ['filter_trigger'],
    'notes': ['note_fetch'],
    'greetings': ['greeting', 'farewell'],
    'captcha': ['captcha_verification'],
    'blocklist': ['sticker_block', 'word_block'],
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
    'word_block': ('Word blocking', 'Delete messages containing a blocked word or phrase.'),
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


def clear_module_overrides(gid, module) -> None:
    """Drop a module's master switch and all component overrides, legacy keys included."""
    module_db().delete(f'groups.{gid}.module_{module}_enabled')
    for command in modules.get(module, []):
        if command not in ALWAYS_ON:
            module_db().delete(f'groups.{gid}.{command}_enabled')
    for event in module_events.get(module, []):
        module_db().delete(f'groups.{gid}.event_{event}_enabled')
    if module == 'downloader':
        module_db().delete(f'groups.{gid}.autodl_enabled')


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
def module_counts(gid, module):
    """Return (effective, toggleable_total) for UI display; a paused module shows zero."""
    cmds = [c for c in modules.get(module, []) if c not in ALWAYS_ON]
    evs = module_events.get(module, [])
    raw_on = sum(1 for c in cmds if command_flag(gid, c)) + sum(
        1 for e in evs if event_flag(gid, e)
    )
    return (raw_on if is_module_enabled(gid, module) else 0), len(cmds) + len(evs)


def module_status_label(gid, module):
    """Button label for a module row in the overview."""
    effective, total = module_counts(gid, module)
    # Skip icon for paused or always-on modules
    if module in UNSWITCHABLE_MODULES:
        return f'✅ {module} · always on'
    if not is_module_enabled(gid, module):
        return f'⛔ {module} · paused'
    icon = '✅' if effective == total else '⚠️'
    return f'{icon} {module} · {effective}/{total}'



def overview_view(group_id, page=1):
    """Return (text, keyboard) for the paginated module list."""
    all_modules = list(modules.keys())
    total_pages = max(1, -(-len(all_modules) // MODULES_PER_PAGE))
    page = max(1, min(page, total_pages))
    start, end = (page - 1) * MODULES_PER_PAGE, page * MODULES_PER_PAGE

    keyboard = InlineKeyboardMarkup(row_width=1)
    for module in all_modules[start:end]:
        keyboard.add(InlineKeyboardButton(
            module_status_label(group_id, module),
            callback_data=f'mod:open:{page}:{module}'))
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton('◀ Prev', callback_data=f'mod:list:{page-1}'))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton('Next ▶', callback_data=f'mod:list:{page+1}'))
    if nav_row:
        keyboard.add(*nav_row)

    enabled, total = module_stats(group_id)
    return (f"Modules - page {page} of {total_pages}\n"
            f"{enabled} of {total} features active"), keyboard


def detail_view(group_id, module_name, page=1):
    """(text, keyboard) for a module: master toggle, bulk actions, component rows, nav."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    module_on = is_module_enabled(group_id, module_name)
    effective, total = module_counts(group_id, module_name)

    # Master toggle (skip for unswitchable)
    if module_name not in UNSWITCHABLE_MODULES:
        keyboard.add(InlineKeyboardButton(
            'Turn module off' if module_on else 'Turn module on',
            callback_data=f'mod:master:{page}:{module_name}'))
    # Bulk actions
    keyboard.add(
        InlineKeyboardButton('Enable all', callback_data=f'mod:all:{page}:{module_name}'),
        InlineKeyboardButton('Reset', callback_data=f'mod:reset:{page}:{module_name}')
    )
    # Commands (paired two per row)
    commands = modules.get(module_name, [])
    for i in range(0, len(commands), 2):
        row = []
        for c in commands[i:i+2]:
            pinned = c in ALWAYS_ON
            on = True if pinned else command_flag(group_id, c)
            label = c
            if pinned:
                label = f'🔒 {label}'
            icon = '✅' if on else ('⏸' if not module_on else '⛔')
            row.append(InlineKeyboardButton(
                f'{icon} {label}',
                callback_data=f'mod:cmd:{page}:{module_name}:{c}'))
        keyboard.add(*row)
    # Events (one per row)
    for evt in module_events.get(module_name, []):
        on = event_flag(group_id, evt)
        icon = '✅' if on else ('⏸' if not module_on else '⛔')
        label = f'Event · {EVENT_INFO.get(evt, (evt,))[0]}'
        keyboard.add(InlineKeyboardButton(
            f'{icon} {label}',
            callback_data=f'mod:evt:{page}:{module_name}:{evt}'))
    # Navigation
    all_modules = list(modules.keys())
    idx = all_modules.index(module_name)
    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton('◀ Prev', callback_data=f'mod:open:{page}:{all_modules[idx - 1]}'))
    if idx < len(all_modules) - 1:
        nav_row.append(InlineKeyboardButton('Next ▶', callback_data=f'mod:open:{page}:{all_modules[idx + 1]}'))
    nav_row.append(InlineKeyboardButton('Modules', callback_data=f'mod:back:{page}'))
    keyboard.add(*nav_row)

    master_status = 'Always on' if module_name in UNSWITCHABLE_MODULES else ('ON' if module_on else 'OFF')
    lines = [f'{module_name} · {master_status}']
    if module_name not in UNSWITCHABLE_MODULES:
        lines.append(f'module {idx+1} of {len(all_modules)} · {effective}/{total} features active')
    lines.append('Tap a command or event to toggle it.')
    return '\n'.join(lines), keyboard


async def _render(call, text, keyboard):
    """Render a callback response with text first (correct pyTelegramBotAPI order)."""
    try:
        await bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboard,
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            # Fall back to sending a new message
            await bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=keyboard,
                message_thread_id=getattr(call.message, 'message_thread_id', None),
            )


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

async def send_module_keyboard(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        await bot.reply_to(m, "Admins only.")
        return
    group_id = str(m.chat.id)
    text, keyboard = overview_view(group_id, 1)
    await bot.send_message(m.chat.id, text, reply_markup=keyboard, **topic_kwargs(m))


async def _flip(call, module, page, current, toggle, label):
    """Flip a flag to its inverse, acknowledge, and swap to the detail view."""
    gid = str(call.message.chat.id)
    toggle(not current)
    await _answered(call, f'{label} {"enabled" if not current else "disabled"}',
                    detail_view(gid, module, page))


async def _answered(call, note, view):
    """Acknowledge with a note, then swap the message to the new view."""
    await bot.answer_callback_query(call.id, note)
    await _render(call, *view)


async def handle_mod_callback(call):
    """Route mod:<action>:<page>:<module>[:<component>] callbacks."""
    if not await is_privileged(call.message.chat.id, call.from_user.id):
        await bot.answer_callback_query(call.id, "Admins only.")
        return
    parts = call.data.split(':')
    action = parts[1] if len(parts) > 1 else ''
    group_id = str(call.message.chat.id)
    try:
        page = max(1, int(parts[2]))
    except (ValueError, IndexError):
        page = 1
    module = parts[3] if len(parts) > 3 else ''
    component = parts[4] if len(parts) > 4 else ''

    if action in ('list', 'back'):
        await _render(call, *overview_view(group_id, page))
        return
    if module not in modules:
        await bot.answer_callback_query(call.id, 'Unknown module.', show_alert=True)
        return

    if action == 'open':
        await _render(call, *detail_view(group_id, module, page))
    elif action == 'master':
        if module in UNSWITCHABLE_MODULES:
            await bot.answer_callback_query(call.id, 'This module cannot be disabled.', show_alert=True)
            return
        await _flip(call, module, page, is_module_enabled(group_id, module),
                    lambda v: set_module_enabled(group_id, module, v), f'{module} module')
    elif action == 'all':
        set_module_enabled(group_id, module, True)
        for command in modules.get(module, []):
            if command not in ALWAYS_ON:
                set_command_enabled(group_id, command, True)
        for event in module_events.get(module, []):
            set_event_enabled(group_id, event, True)
        await _answered(call, f'All components in {module} enabled',
                        detail_view(group_id, module, page))
    elif action == 'reset':
        clear_module_overrides(group_id, module)
        await _answered(call, f'Defaults restored for {module}',
                        detail_view(group_id, module, page))
    elif action == 'cmd':
        if component not in _COMMAND_MODULE:
            await bot.answer_callback_query(call.id, 'Unknown command.', show_alert=True)
            return
        if component in ALWAYS_ON:
            await bot.answer_callback_query(call.id, f'{component} is always on.', show_alert=True)
            return
        await _flip(call, module, page, command_flag(group_id, component),
                    lambda v: set_command_enabled(group_id, component, v), f'{component} command')
    elif action == 'evt':
        if component not in _EVENT_MODULE:
            await bot.answer_callback_query(call.id, 'Unknown event.', show_alert=True)
            return
        await _flip(call, module, page, event_flag(group_id, component),
                    lambda v: set_event_enabled(group_id, component, v), f'{component} event')
    else:
        await bot.answer_callback_query(call.id, "Invalid action.", show_alert=True)
