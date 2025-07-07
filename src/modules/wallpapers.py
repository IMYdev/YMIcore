import random
import aiohttp
from info import bot

async def wallpaper(m):
    page_number = random.randint(0, 100)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://picsum.photos/v2/list?page={page_number}&limit=10') as response:
            data = await response.json()
            image_url = data[0]['download_url']
            author = data[0]['author']
            resolution = f"{data[0]['width']}x{data[0]['height']}"
            caption = f"Author: {author}\nResolution: {resolution}\n[HQ Download]({image_url})"
            await bot.send_photo(chat_id=m.chat.id, photo=image_url, caption=caption, reply_to_message_id=m.message_id, parse_mode="Markdown")