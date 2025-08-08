import aiohttp
import urllib.parse
from info import bot
from core.utils import log_error
from telebot.formatting import escape_markdown, mlink
import random

async def anime(m):
    URL = "https://pic.re/image"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(URL) as response:
            data = await response.json()
            tags = data.get('tags', [])
            tag_str = ' '.join([escape_markdown('#' + tag) for tag in tags])
            author = escape_markdown(data.get('author', 'Unknown'))
            width = data.get('width')
            height = data.get('height')
            image_url = f"https://{data.get('file_url')}"
            # Cursed but proper utilization of telebot's built-in formatting features.
            dl_string = mlink("HQ Download",image_url, escape=False)
            caption = f"Tags: {tag_str}\nAuthor: {author}\nResolution: {width}x{height}"
            caption = escape_markdown(caption)
            caption = f"{caption}\n{dl_string}"
            await bot.send_photo(chat_id=m.chat.id, photo=image_url, caption=caption, reply_to_message_id=m.message_id, parse_mode="Markdown")

async def fetch_anime_name(anilist_id):
    QUERY = '''
    query ($id: Int) {
        Media(id: $id) {
            title {
                romaji
                english
                native
            }
        }
    }
    '''
    variables = {'id': anilist_id}
    URL = 'https://graphql.anilist.co'

    async with aiohttp.ClientSession() as session:
        async with session.post(URL, json={'query': QUERY, 'variables': variables}) as response:
            response_json = await response.json()
            return response_json['data']['Media']['title']

async def search(m):
    try:
        # Check if the message is a reply and contains a photo
        if m.reply_to_message and m.reply_to_message.photo:
            image = m.reply_to_message.photo[-1].file_id  # Get the highest resolution photo
            url = await bot.get_file_url(image)
            api_url = f"https://api.trace.moe/search?url={urllib.parse.quote_plus(url)}"
            wait_message = await bot.send_message(m.chat.id, "Searching...")

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    response_json = await response.json()

            # Handle possible error in the response
            if response_json.get('error'):
                await bot.reply_to(m, f"Error: {response_json['error']}")
                return

            # Extract first match details safely
            first_match = response_json['result'][0]
            anime_title = await fetch_anime_name(first_match['anilist'])
            title = f"{anime_title.get('romaji', 'Unknown')} (Romaji), {anime_title.get('english', 'Unknown')} (English), {anime_title.get('native', 'Unknown')} (Native)"
            episode = first_match.get('episode', 'Unknown')
            video = first_match.get('video')

            await bot.delete_message(m.chat.id, wait_message.message_id)
            await bot.send_chat_action(m.chat.id, "upload_video")
            await bot.send_video(chat_id=m.chat.id, video=video, caption=f"Title: {title}\nEpisode: {episode}", reply_to_message_id=m.message_id)
        else:
            await bot.reply_to(m, "Reply with a photo to search.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

# Disclaimer: NSFW below.
TYPES = ["hass", "hmidriff", "hentai", "hneko", "hkitsune", "hthigh", "hboobs", "yaoi"]

async def spice(m):
    if len(m.text.split()) < 2:
        category = random.choices(TYPES)[0]
    else:
        category = m.text.split()[1]
    if "-list" in m.text:
        await bot.reply_to(m, TYPES)
        return
    if category not in TYPES:
        await bot.reply_to(m, "Invalid category.")
        return
    else:
        url = f"https://nekobot.xyz/api/image?type={category}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                image_url = data.get("message")
                caption = f"[HQ Download]({image_url})"
                await bot.send_photo(chat_id=m.chat.id, photo=image_url, reply_to_message_id=m.message_id, caption=caption, parse_mode="Markdown")