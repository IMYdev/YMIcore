from modules.wallpapers import wallpaper
from modules.img import image_gen
from modules.chat import chat, reset_memory
from modules.anime import anime, search, spice
from modules.purge import purge
from modules.filters import set_filter, get_filters, remove_filter
from modules.notes import set_note, notes_list, remove_note
from modules.member import (
    user_info, start, promote, demote, pin,
    ban, unban, help_command, group_id
)
from module_manager import send_module_keyboard
from modules.quotes import quote_handler
from modules.greetings import set_greeting, set_goodbye
from modules.downloader import fetch_music

COMMANDS = {
    "/info": user_info,
    "/start": start,
    "/greeting": set_greeting,
    "/goodbye": set_goodbye,
    "/wallpaper": wallpaper,
    "/ask": chat,
    "/id": group_id,
    "/animewall": anime,
    "/sauce": search,
    "/imagine": image_gen,
    "/purge": purge,
    "/nuke": purge,
    "/filter": set_filter,
    "/filters": get_filters,
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
    "/horny": spice,
    "/music": fetch_music,
}


async def handle_command(message, text):
    """ Recive command and call associated module"""
    for cmd, func in COMMANDS.items():
        if text.split(" ", 1)[0] == cmd:
            await func(message)
            break