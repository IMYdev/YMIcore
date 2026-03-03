import random
import aiohttp
from info import bot
from core.utils import handle_errors
from telebot.formatting import hlink, hbold, format_text

@handle_errors
async def wallpaper(m):
    page_number = random.randint(0, 100)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://picsum.photos/v2/list?page={page_number}&limit=10') as response:
            if response.status != 200:
                return await bot.reply_to(m, "Failed to fetch wallpapers.")
            data = await response.json()
            if not data:
                return await bot.reply_to(m, "No wallpapers found.")
                
            img = random.choice(data)
            image_url = img['download_url']
            author = img['author']
            res = f"{img['width']}x{img['height']}"
            
            caption = format_text(
                f"Author: {hbold(author)}",
                f"Resolution: {hbold(res)}",
                hlink("HQ Download", image_url)
            )
            
            await bot.send_photo(
                chat_id=m.chat.id, 
                photo=image_url, 
                caption=caption, 
                reply_to_message_id=m.message_id, 
                parse_mode="HTML"
            )
