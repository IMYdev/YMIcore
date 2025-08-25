from info import (bot, Downloader, PAXSENIX_TOKENS)
from telebot.formatting import (hlink, hcite)
import re
from core.utils import log_error
import aiohttp
import asyncio
from yt_dlp import YoutubeDL
from innertube import InnerTube
from telebot.types import InputMediaPhoto, InputMediaVideo
import random

async def wait_until_ok(url, headers=None, delay=1):
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=headers) as response:
                if response.status == 429 or response.status == 504:
                    return response.status
                data = await response.json()
                if data.get('message') == "Failed to retrieve this content":
                    return data
                if data.get('ok') == True:
                    return data
                await asyncio.sleep(delay)

async def extract_supported_url(m):
    if not Downloader:
        return
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    url = match.group(0)

    if "youtube.com" in url or "youtu.be" in url:
        await download_yt_video(m, url)
    elif "instagram.com" in url:
        url = url.split("?", 1)[0]
        await instagram_dl(m, url)
    elif "tiktok.com" in url:
        await tiktok_dl(m, url)

async def instagram_dl(m, url):
    try:
        PAXSENIX_TOKEN = random.choice(PAXSENIX_TOKENS)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {PAXSENIX_TOKEN}"
        }
        api=f"https://api.paxsenix.biz.id/dl/ig?url={url}"
        data = await wait_until_ok(m, api, headers)
        if data == 429 or data == 504:
            await bot.send_message(m.chat.id, f"API busy: {data}")
            return
        links = data['downloadUrls']
        media_list = []
        source = hlink("Source", url, escape=False)
        username = data['detail']['username']
        author = hlink(f"@{username}", f"www.instagram.com/{username}", escape=False)
        author = author.replace("\\", "")
        description = data['detail']['title']
        description = hcite(description, expandable=True)
        caption = f"{description}\n{author}\n{source}"
        media_count = 0

        if len(caption) > 1024:
            caption = f"{author}\n{source}"

        if len(links) > 1:
            for i in range(len(links)):
                link = links[i]['url']
                file_ext = links[i]['ext']

                if file_ext == 'mp4':
                    if media_count == 0:
                        media = InputMediaVideo(link, caption=caption, parse_mode="HTML")

                    else:
                        media = InputMediaVideo(link)

                    media_count += 1

                else:
                    if media_count == 0:
                        media = InputMediaPhoto(link, caption=caption, parse_mode="HTML")

                    else:
                        media = InputMediaPhoto(link)

                    media_count += 1

                media_list.append(media)
            await bot.send_media_group(m.chat.id, media_list)

        else:
            file_ext = links[0]['ext']
            link = links[0]['url']

            if file_ext == 'mp4':
                await bot.send_video(m.chat.id, link, caption=caption, parse_mode="HTML")
            else:
                await bot.send_photo(m.chat.id, link, caption=caption, parse_mode="HTML")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def tiktok_dl(m, url):
    try:
        PAXSENIX_TOKEN = random.choice(PAXSENIX_TOKENS)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {PAXSENIX_TOKEN}"
        }
        api=f"https://api.paxsenix.biz.id/dl/tiktok?url={url}"
        data = await wait_until_ok(m, api, headers)
        if data == 429 or data == 504:
            await bot.send_message(m.chat.id, f"API busy: {data}")
            return
        media_list = []
        source = hlink("Source", url, escape=False)
        username = data['detail']['author']
        author = hlink(f"@{username}", data['detail']['authorProfileLink'], escape=False)
        author = author.replace("\\", "")
        description = data['detail']['description']
        description = hcite(description, expandable=True)
        caption = f"{description}\n{author}\n{source}"
        media_count = 0
        links = data['downloadUrls']
        post_type = data['detail']['type']

        if len(caption) > 1024:
            caption = f"{author}\n{source}"

        if post_type == 'image':
            images = links['images']
            music = links['music']

            if len(images) > 1:
                for link in range(len(images)):
                    if media_count == 0:
                        media = InputMediaPhoto(link, caption=caption, parse_mode="HTML")
                    else:
                        media = InputMediaPhoto(link)
                    media_count += 1
                    media_list.append(media)
                await bot.send_media_group(m.chat.id, media_list)

            else:
                photo = images[0]
                await bot.send_photo(m.chat.id, photo, caption=caption, parse_mode="HTML")
                await bot.send_audio(m.chat.id, music)

        elif post_type == 'video':
            link = links['video']
            await bot.send_video(m.chat.id, link, caption=caption, parse_mode="HTML")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

vid_opts = {
    "quiet": True,
    "no_warnings": True,
    "format": "18",
}

async def download_yt_video(m, link):
    try:

        if len(m.text.split(" ", 1)) > 1 and m.text.split(" ", 1)[1] == "-audio":
            link = await download_yt_audio(m, link)
            await bot.send_audio(m.chat.id, audio=link, reply_to_message_id=m.id)
            return

        with YoutubeDL(params=vid_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            file_size = info.get("filesize") or info.get("filesize_approx")
            if file_size > 52428800:
                return
            title = info.get("title")
            link = hlink("Source", link, escape=False)
            vid_cap = f"{title}\n{link}"
            url = info.get("url")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                await bot.send_video(m.chat.id, video=response.content, caption=vid_cap, parse_mode="HTML")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

audio_opts = {
    "quiet": True,
    "no_warnings": True,
    "format": "bestaudio/best"
}

async def download_yt_audio(m, link):
    try:
        with YoutubeDL(params=audio_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            audio_url = info['url']
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url) as response:
                link = await response.content.read()
                return link

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

    data = client.search(query=query, params="EgWKAQwI") # *params* are the music filter here
    sections = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']

    for section in sections:
        items = section.get('itemSectionRenderer', {}).get('contents', [])

        for item in items:
            video = item.get('videoRenderer')

            if not video:
                continue

            video_id = video['videoId']
            url = f"https://www.youtube.com/watch?v={video_id}"

            title = video.get("title", {}).get("runs", [{}])[0].get("text")
            author = video.get("ownerText", {}).get("runs", [{}])[0].get("text")
            caption = f"{author} - {title}"

            await fetch_music(m, url, old, caption)
            break  # stop after first result

async def fetch_music(m, yt_url, old, caption):
    PAXSENIX_TOKEN = random.choice(PAXSENIX_TOKENS)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {PAXSENIX_TOKEN}"
    }
    api = f"https://api.paxsenix.biz.id/tools/songlink?url={yt_url}"
    data = await wait_until_ok(m, api, headers)

    if data == 429 or data == 504:
        link = await download_yt_audio(m, yt_url)
        await bot.send_chat_action(m.chat.id, "upload_voice")
        await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)
        return

    links = data.get('links')

    await bot.edit_message_text("Fetching song...", m.chat.id, old.id)
    
    if links:
        spotify  = links[3].get('url') or "N/A"
        deezer   = links[5].get('url') or "N/A"
        tidal    = links[8].get('url') or "N/A"

        if tidal != "N/A":
            link = await download_music(m, headers, tidal, "tidal")

        elif deezer != "N/A":
            link = await download_music(m, headers, deezer, "deezer")

        elif spotify != "N/A":
            link = await download_music(m, headers, spotify, "spotify")
    else:
        link = await download_yt_audio(m, yt_url)

    await bot.delete_message(m.chat.id, old.id)

    if link != "failed":
        await bot.send_chat_action(m.chat.id, "upload_voice")
        await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)
    else:
        link = await download_yt_audio(m, yt_url)
        await bot.send_chat_action(m.chat.id, "upload_voice")
        await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)

async def download_music(m, headers, song, choice):
    try:
        URL="https://api.paxsenix.biz.id/dl"
        if choice == "tidal":
            api = f"{URL}/{choice}?url={song}&quality=LOSSLESS"
            data = await wait_until_ok(m, api, headers)

            if data == 429 or data == 504:
                await bot.send_message(m.chat.id, f"API busy: {data}")
                return "failed"

            if data['message'] == "Failed to retrieve this content":
                return "failed"

            link = data['directUrl']
            async with aiohttp.ClientSession() as session:
                async with session.get(link, headers=headers) as response:
                    song = await response.content.read()
                    return song

        elif choice == "deezer":
            api = f"{URL}/{choice}?url={song}&quality=flac"
            data = await wait_until_ok(m, api, headers)

            if data == 429 or data == 504:
                await bot.send_message(m.chat.id, f"API busy: {data}")
                return "failed"

            if data['message'] == "Failed to retrieve this content":
                return "failed"
            
            link = data['directUrl']
            async with aiohttp.ClientSession() as session:
                async with session.get(link, headers=headers) as response:
                    song = await response.content.read()
                    return song

        elif choice == "spotify":
            api = f"{URL}/{choice}?url={song}&serv=spotdl"
            data = await wait_until_ok(m, api, headers)

            if data == 429 or data == 504:
                await bot.send_message(m.chat.id, f"API busy: {data}")
                return "failed"
    
            if data['message'] == "Failed to retrieve this content":
                return "failed"
            
            link = data['directUrl']
            return link

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)