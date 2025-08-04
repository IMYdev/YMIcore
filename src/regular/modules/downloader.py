from info import bot
from telebot.formatting import mlink
import re
from core.utils import log_error
import aiohttp
from yt_dlp import YoutubeDL

async def extract_supported_url(m):
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    url = match.group(0)

    if "youtube.com" in url or "youtu.be" in url:
        await download_yt_vid(m, url)
    elif "instagram.com" in url:
        await download_instagram_reel(m, url)



async def download_instagram_reel(m, url):
    try:
        modified_url = re.sub(r'(https?://)(www\.)?instagram', r'\1\2kkinstagram', url)
        link = mlink("Source", url, escape=False)
        await bot.send_video(m.chat.id, modified_url, caption=link, parse_mode="Markdown")
    except Exception as e:
        await log_error(bot, e, m)

opts = {
    "quiet": "True"
}
async def download_yt_vid(m, link):
    try:
        with YoutubeDL(params=opts) as ydl:
            info = ydl.extract_info(link, download=False)
            title = info.get("title")
            link = mlink("Source", link, escape=False)
            vid_cap = f"{title}\n{link}"
            url = next(item for item in info['formats'] if item['format_id'] == '18')['url']
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                await bot.send_video(m.chat.id, video=resp.content, caption=vid_cap, parse_mode="Markdown")
    except Exception as error:
        await log_error(bot, m, error)