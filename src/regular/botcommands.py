from modules.wallpapers import wallpaper
from modules.anime import (anime, search)
from modules.purge import purge
from modules.filters import (set_filter, get_filters, remove_filter)
from modules.notes import (set_note, notes_list, remove_note)
from modules.member import (
    user_info, start, promote, demote, pin,
    ban, unban, help_command, group_id, spoiler)
from module_manager import send_module_keyboard
from modules.greetings import (set_greeting, set_goodbye, set_captcha, captcha_toggle)
from modules.downloader import music_search
from modules.blocklist import (block_set, unblock_set, get_blacklist)

COMMANDS = {
    "info": user_info,
    "start": start,
    "greeting": set_greeting,
    "goodbye": set_goodbye,
    "wallpaper": wallpaper,
    "id": group_id,
    "animewall": anime,
    "sauce": search,
    "purge": purge,
    "nuke": purge,
    "filter": set_filter,
    "filist": get_filters,
    "stop": remove_filter,
    "add": set_note,
    "notes": notes_list,
    "remove": remove_note,
    "promote": promote,
    "demote": demote,
    "pin": pin,
    "ban": ban,
    "unban": unban,
    "help": help_command,
    "modules": send_module_keyboard,
    "music": music_search,
    "spoiler": spoiler,
    "blockset": block_set,
    "blocklist": get_blacklist,
    "unblockset": unblock_set,
    "setcaptcha": set_captcha,
    "captcha": captcha_toggle
}

async def handle_command(message):
    """ Receive command and call associated module"""
    text = message.text or message.caption
    if not text or not text.startswith('/'):
        return

    command = text.split()[0][1:].lower().split('@')[0]
    
    func = COMMANDS.get(command)
    if func:
        await func(message)