from info import bot
from telebot.formatting import mlink
import re
from core.utils import log_error
import aiohttp
from yt_dlp import YoutubeDL
from innertube import InnerTube


async def extract_supported_url(m):
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    url = match.group(0)

    if "youtube.com" in url or "youtu.be" in url:
        await download_yt_audio(m, url)
    elif "instagram.com" in url:
        await instagram_dl(m, url)
    elif "tiktok.com" in url:
        await tiktok_dl(m, url)



async def instagram_dl(m, url):
    try:
        modified_url = re.sub(r'(https?://)(www\.)?instagram', r'\1\2kkinstagram', url)
        if "?" in modified_url:
            modified_url = modified_url.split("?")[0]
        link = mlink("Source", url, escape=False)
        if "reel" in url:
            await bot.send_video(m.chat.id, modified_url, caption=link, parse_mode="Markdown")
        else:
            await bot.send_photo(m.chat.id, modified_url, caption=link, parse_mode="Markdown")
    except Exception as error:
        # In case the embed service doesn't work
        if "wrong type" or "HTTP URL" in str(error):
            await bot.send_message(m.chat.id, "Couldn't fetch post.")
        await log_error(bot, error, m)

async def tiktok_dl(m, url):
    try:
        modified_url = re.sub(r'(https?://)([^/]*\.)?tiktok', r'\1\2kktiktok', url)
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

async def fetch_music(m):
    client = InnerTube("WEB")

    query = m.text.split(" ", 1)
    if len(query) > 1:
        query = query[1]
        old = await bot.reply_to(m, "Looking for song...")
    else:
        await bot.reply_to(m, "nope")

    data = client.search(query=query)
    sections = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']

    for section in sections:
        items = section.get('itemSectionRenderer', {}).get('contents', [])
        for item in items:
            video = item.get('videoRenderer')
            if not video:
                continue
            video_id = video['videoId']
            url = f"https://www.youtube.com/watch?v={video_id}"
            await bot.edit_message_text("Fetching song...", m.chat.id, old.id)
            await download_yt_audio(m, url, old)
            # Stop after the first result.
            break

async def download_yt_audio(m, link, old):
    try:
        with YoutubeDL(params=opts) as ydl:
            info = ydl.extract_info(link, download=False)
            title = info.get("title")
            audio_cap = f"{title}"
            audio_url = next(item for item in info['formats'] if item['format_id'] == '18')['url']
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url) as resp:
                await bot.send_audio(
                    m.chat.id,
                    audio=resp.content,
                    caption=audio_cap,
                    parse_mode="Markdown",
                    reply_to_message_id=m.id
                )
        await bot.delete_message(m.chat.id, old.id)
    except Exception as error:
        await log_error(bot, m, error)