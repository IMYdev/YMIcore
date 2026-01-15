from modules.wallpapers import wallpaper
from modules.chat import chat, reset_memory
from modules.anime import anime, search
from modules.purge import purge
from modules.filters import set_filter, get_filters, remove_filter
from modules.notes import set_note, notes_list, remove_note
from modules.member import (
    user_info, start, promote, demote, pin,
    ban, unban, help_command, group_id, spoiler, runtime)
from module_manager import send_module_keyboard
from modules.quotes import quote_handler
from modules.greetings import set_greeting, set_goodbye
from modules.downloader import music_search
from modules.blocklist import (block_set, unblock_set, get_blacklist)

COMMANDS = {
    "/info": user_info,
    "/start": start,
    "/runtime": runtime,
    "/greeting": set_greeting,
    "/goodbye": set_goodbye,
    "/wallpaper": wallpaper,
    "/ask": chat,
    "/id": group_id,
    "/animewall": anime,
    "/sauce": search,
    "/purge": purge,
    "/nuke": purge,
    "/filter": set_filter,
    "/filist": get_filters,
    "/stop": remove_filter,
    "/add": set_note,
    "/notes": notes_list,
    "/remove": remove_note,
    "/promote": promote,
    "/demote": demote,
    "/pin": pin,
    "/ban": ban,
    "/unban": unban,
    "/help": help_command,
    "/reset": reset_memory,
    "/modules": send_module_keyboard,
    "/q": quote_handler,
    "/music": music_search,
    "/spoiler": spoiler,
    "/blockset": block_set,
    "/blocklist": get_blacklist,
    "/unblockset": unblock_set
}

async def handle_command(message, text):
    """ Recive command and call associated module"""
    for cmd, func in COMMANDS.items():
        if text.startswith(cmd):
            await func(message)
            break
