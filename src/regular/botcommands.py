from modules.wallpapers import wallpaper
from modules.img import image_gen
from modules.chat import chat, reset_memory
from modules.anime import anime, search, spice
from modules.purge import purge
from modules.filters import set_filter, get_filters, remove_filter
from modules.notes import set_note, notes_list, remove_note
from modules.member import user_info, start, promote, demote, pin, ban, unban, help_command, group_id
from module_manager import send_module_keyboard
from modules.quotes import quote_handler
from modules.greetings import set_greeting, set_goodbye
from modules.downloader import fetch_music

async def my_comd(m):
    if m.text.lower().startswith("/info"):
        await user_info(m)
    if m.text.lower().startswith("/start"):
        await start(m)
    if m.text.lower().startswith("/greeting"):
        await set_greeting(m)
    if m.text.lower().startswith("/goodbye"):
        await set_goodbye(m)
    if m.text.lower().startswith("/wallpaper"):
        await wallpaper(m)
    if m.text.lower().startswith("/ask"):
        await chat(m)
    if m.text.lower().startswith("/id"):
        await group_id(m)
    if m.text.lower().startswith("/animewall"):
        await anime(m)
    if m.text.lower().startswith("/sauce"):
        await search(m)
    if m.text.lower().startswith("/imagine"):
        await image_gen(m)
    if m.text.lower().startswith("/purge") or m.text.lower().startswith("/nuke"):
        await purge(m)
    if m.text.lower().startswith("/filter") and not m.text.lower().startswith("/filters"):
        await set_filter(m)
    if m.text.lower().startswith("/filters"):
        await get_filters(m)
    if m.text.lower().startswith("/stop"):
        await remove_filter(m)
    if m.text.lower().startswith("/add"):
        await set_note(m)
    if m.text.lower().startswith("/notes"):
        await notes_list(m)
    if m.text.lower().startswith("/remove"):
        await remove_note(m)
    if m.text.lower().startswith("/promote"):
        await promote(m)
    if m.text.lower().startswith("/demote"):
        await demote(m)
    if m.text.lower().startswith("/pin"):
        await pin(m)
    if m.text.lower().startswith("/ban"):
        await ban(m)
    if m.text.lower().startswith("/unban"):
        await unban(m)
    if m.text.lower().startswith("/help"):
        await help_command(m)
    if m.text.lower().startswith("/reset"):
        await reset_memory(m)
    # if m.text.lower().startswith("/create_fed"):
    #     response = await create_federation(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/join_fed"):
    #     response = await join_federation(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/leave_fed"):
    #     response = await leave_federation(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/fban"):
    #     response = await fban(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/funban"):
    #     response = await funban(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/feds"):
    #     response = list_federations()
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/fpromote"):
    #     response = await promote_fed_admin(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/fdemote"):
    #     response = await demote_fed_admin(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    # if m.text.lower().startswith("/delete_fed"):
    #     response = await delete_federation(m)
    #     await bot.reply_to(m, response, parse_mode='HTML')
    if m.text.lower().startswith("/modules"):
        await send_module_keyboard(m)
    if m.text.lower().startswith("/q"):
        await quote_handler(m)
    if m.text.lower().startswith("/horny"):
        await spice(m)
    if m.text.lower().startswith("/music"):
        await fetch_music(m)