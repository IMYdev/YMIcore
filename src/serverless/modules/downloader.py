from info import (bot, Downloader, PAXSENIX_TOKEN)
from telebot.formatting import mlink
import re
from core.utils import log_error
import aiohttp
from innertube import InnerTube
import asyncio
from telebot.types import InputMediaPhoto, InputMediaVideo


async def extract_supported_url(m):
    if not Downloader:
        return
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    url = match.group(0)

    if "youtube.com" in url or "youtu.be" in url:
        await download_yt_vid(m, url)
    elif "instagram.com" in url:
        await instagram_dl(m, url)
    elif "tiktok.com" in url:
        await tiktok_dl(m, url)

async def instagram_dl(m, url):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {PAXSENIX_TOKEN}"
        }
        api=f"https://api.paxsenix.biz.id/dl/ig?url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api, headers=headers) as response:
                data = await response.json()
                links = data['downloadUrls']
                media_list = []
                source = mlink("Source", url, escape=False)
                username = data['detail']['username']
                author = mlink(username, f"www.instagram.com/{username}", escape=False)
                author = author.replace("\\", "")
                description = data['detail']['title']
                caption = f"{description}\nPost by {author}\n{source}"
                media_count = 0

                if len(caption) > 1024:
                    caption = source

                if len(links) > 1:
                    for i in range(len(links)):
                        link = links[i]['url']
                        file_ext = links[i]['ext']

                        if file_ext == 'jpg':
                            if media_count == 0:
                                media = InputMediaPhoto(link, caption=caption, parse_mode="Markdown")

                            else:
                                media = InputMediaPhoto(link)

                            media_count += 1

                        elif file_ext == 'mp4':
                            if media_count == 0:
                                media = InputMediaVideo(link, caption=caption, parse_mode="Markdown")

                            else:
                                media = InputMediaVideo(link)

                            media_count += 1

                        media_list.append(media)
                    await bot.send_media_group(m.chat.id, media_list)

                else:
                    file_ext = links[0]['ext']
                    link = links[0]['url']

                    if file_ext == 'jpg':
                        await bot.send_photo(m.chat.id, link, caption=caption, parse_mode="Markdown")

                    elif file_ext == 'mp4':
                        await bot.send_video(m.chat.id, link, caption=caption, parse_mode="Markdown")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def tiktok_dl(m, url):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {PAXSENIX_TOKEN}"
        }
        api=f"https://api.paxsenix.biz.id/dl/tiktok?url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api, headers=headers) as response:
                data = await response.json()
                media_list = []
                source = mlink("Source", url, escape=False)
                author = mlink(data['detail']['author'], data['detail']['authorProfileLink'], escape=False)
                author = author.replace("\\", "")
                description = data['detail']['description']
                caption = f"{description}\nPost by {author}\n{source}"
                media_count = 0
                links = data['downloadUrls']
                post_type = data['detail']['type']

                if len(caption) > 1024:
                    caption = source

                if post_type == 'image':
                    images = links['images']
                    music = links['music']

                    if len(images) > 1:
                        for link in range(len(images)):
                            if media_count == 0:
                                media = InputMediaPhoto(link, caption=caption, parse_mode="Markdown")
                            else:
                                media = InputMediaPhoto(link)
                            media_count += 1
                            media_list.append(media)
                        await bot.send_media_group(m.chat.id, media_list)

                    else:
                        photo = images[0]
                        await bot.send_photo(m.chat.id, photo, caption=caption, parse_mode="Markdown")
                        await bot.send_audio(m.chat.id, music)

                elif post_type == 'video':
                    link = links['video']
                    await bot.send_video(m.chat.id, link, caption=caption, parse_mode="Markdown")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def download_yt_vid(m, link):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {PAXSENIX_TOKEN}"
        }
        url=f"https://api.paxsenix.biz.id/dl/ytmp4?url={link}&quality=360"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                task_url = data['task_url']
                link = await check_yt_dl_status(task_url)
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as response:
                        await bot.send_video(m.chat.id, response.content)

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def music_search(m):
    if not Downloader:
        return
    client = InnerTube("WEB")

    query = m.text.split(" ", 1)
    if len(query) > 1:
        query = query[1]
        old = await bot.reply_to(m, "Looking for song...")
    else:
        await bot.reply_to(m, "No song name provided.")
        return

    data = client.search(query=query)
    sections = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']

    for section in sections:
        items = section.get('itemSectionRenderer', {}).get('contents', [])
        for item in items:
            video = item.get('videoRenderer')
            if not video:
                continue
            video_id = video['videoId']
            title = video['title']['runs'][0]['text']
            if "[" in title:
                title = title.split("[", 1)[0]
            elif "(" in title:
                title = title.split("(", 1)[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
            await bot.edit_message_text("Fetching song...", m.chat.id, old.id)
            await fetch_music(m, url, old, title)
            # Stop after the first result.
            break

async def fetch_music(m, url, old, title):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {PAXSENIX_TOKEN}"
    }
    url = f"https://api.paxsenix.biz.id/tools/songlink?url={url}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            yt_music = data['links'][1].get('url') or "N/A"
            spotify  = data['links'][3].get('url') or "N/A"
            deezer   = data['links'][5].get('url') or "N/A"
            tidal    = data['links'][8].get('url') or "N/A"
            if tidal != "N/A":
                link = await download_music(m, headers, tidal, "tidal")
            elif deezer != "N/A":
                link = await download_music(m, headers, deezer, "deezer")
            elif spotify != "N/A":
                link = await download_music(m, headers, spotify, "spotify")
            else:
                link = await download_music(m, headers, yt_music, "ytmp3")

            await bot.delete_message(m.chat.id, old.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, link, caption=title)


async def download_music(m, headers, song, choice):
    try:
        URL="https://api.paxsenix.biz.id/dl"
        if choice == "tidal":
            # Not lossless because lossless is flac and TG servers won't fetch that.
            # We won't fetch that locally either, too much bandwidth.
            url = f"{URL}/{choice}?url={song}&quality=HIGH"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    link = data['directUrl']
                    return link
                    

        elif choice == "deezer":
            # Same as above situation, 320KBPS MP3 and not flac.
            url = f"{URL}/{choice}?url={song}&quality=320kbps"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    link = data['directUrl']
                    return link

        elif choice == "spotify":
            url = f"{URL}/{choice}?url={song}&serv=spotdl"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    link = data['directUrl']
                    return link

        elif choice =="ytmp3":
            url = f"{URL}/{choice}?url={song}&format=mp3"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    task_url = data['task_url']
                    link = await check_yt_dl_status(task_url)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(link) as response:
                            audio = await response.content.read()
                            return audio

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def check_yt_dl_status(task_url):
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(task_url) as response:
                data = await response.json()
                
                if data.get('status') == "done":
                    link = data.get('url')
                    return link

            await asyncio.sleep(0.2)