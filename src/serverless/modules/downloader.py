from info import (bot, Downloader, PAXSENIX_TOKENS)
from telebot.formatting import (hlink, hcite)
from telebot.util import user_link
import re
from core.utils import log_error
import aiohttp
import asyncio
from innertube import InnerTube
from yt_dlp import YoutubeDL
from telebot.types import InputMediaPhoto
import random

async def wait_until_ok(url, delay=1):
    PAXSENIX_TOKEN = random.choice(PAXSENIX_TOKENS)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {PAXSENIX_TOKEN}"
    }
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=headers) as response:

                if response.status == 429 or response.status == 504 or response.status == 500:
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
    
    elif "facebook.com" in url:
        await facebook_dl(m, url)

ig_opts = {
    "quiet": True,
    "no_warnings": True,
}

async def instagram_dl(m, url):
    try:
        with YoutubeDL(ig_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        username = f"Shared by @{m.from_user.username}" if m.from_user.username else f"Shared by {user_link(m.from_user)}"
        description = info.get('description', '') or info.get('title', '')
        caption = f"{hcite(description, expandable=True)}\n{username}\n{hlink('Source', url, escape=False)}"
        
        if len(caption) > 1024:
            caption = f"{username}\n{hlink('Source', url, escape=False)}"

        url = url.replace("instagram", "kkinstagram")
        await bot.send_video(m.chat.id, url, caption=caption, parse_mode="HTML")
    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def tiktok_dl(m, url):
    try:
        api=f"https://api.paxsenix.org/dl/tiktok?url={url}"
        data = await wait_until_ok(api)

        if data == 429 or data == 504:
            await bot.send_message(m.chat.id, f"API busy: {data}")
            return

        if data == 500:
            await bot.send_message(m.chat.id, f"API Error: {data}")
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

                if music:
                        await bot.send_audio(m.chat.id, music)

            else:
                photo = images[0]
                await bot.send_photo(m.chat.id, photo, caption=caption, parse_mode="HTML")

                if music:
                        await bot.send_audio(m.chat.id, music)

        elif post_type == 'video':
            link = links['video']
            await bot.send_video(m.chat.id, link, caption=caption, parse_mode="HTML")

    except Exception as error:

        if "wrong type" or "HTTP URL" in str(error):
            return

        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def facebook_dl(m, url):
    try:
        with YoutubeDL(ig_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        link = info.get('formats')[1].get('url')
        title = info.get('description')
        username = f"Shared by @{m.from_user.username}" if m.from_user.username else f"Shared by {user_link(m.from_user)}"
        source = hlink("Source", url, escape=False)
        caption = f"{hcite(title, expandable=True)}\n{username}\n{source}"

        if len(caption) > 1024:
            caption = source

        await bot.send_video(m.chat.id, video=link, caption=caption, parse_mode="HTML")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def download_yt_video(m, link):
    try:

        if len(m.text.split(" ", 1)) > 1 and m.text.split(" ", 1)[1] == "-audio":
            link = await download_yt_audio(m, link)
            await bot.send_audio(m.chat.id, audio=link, reply_to_message_id=m.id)
            return

        api=f"https://api.paxsenix.org/yt/savetube?url={link}&quality=360"
        source = hlink("Source", link, escape=False)
        data = await wait_until_ok(api)
        task_url = data['task_url']
        link, thumb, title = await check_yt_dl_status(task_url)
        caption = f"{title}\n{source}"
        await bot.send_video(m.chat.id, video=link, cover=thumb, caption=caption, parse_mode="HTML")

    except Exception as error:
        if "Too Large" in str(error):
            return
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def download_yt_audio(m, link):
    try:
        api=f"https://api.paxsenix.org/yt/savetube?url={link}&quality=mp3"
        data = await wait_until_ok(api)
        task_url = data['task_url']
        link = await check_yt_dl_status(task_url)
        return link[0]


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
    try:
        api = f"https://api.paxsenix.org/tools/songlink?url={yt_url}"
        data = await wait_until_ok(api)

        if data == 429 or data == 504:
            await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
            link = await download_yt_audio(m, yt_url)
            await bot.delete_message(m.chat.id, old.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)
            return

        if data == 500:
            await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
            link = await download_yt_audio(m, yt_url)
            await bot.delete_message(m.chat.id, old.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)
            return

        links = data.get('links')

        if links:
            spotify  = links[3].get('url') or "N/A"
            deezer   = links[5].get('url') or "N/A"

            if deezer != "N/A":
                await bot.edit_message_text("Fetching song from Deezer...", m.chat.id, old.id)
                link = await download_music(m, deezer, "deezer")

            elif spotify != "N/A":
                await bot.edit_message_text("Fetching song from Spotify...", m.chat.id, old.id)
                link = await download_music(m, spotify, "spotify")

            else:
                await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
                link = await download_yt_audio(m, yt_url)

        await bot.delete_message(m.chat.id, old.id)

        if link != "failed":
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)
        else:
            link = await download_yt_audio(m, yt_url)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=link, caption=caption, reply_to_message_id=m.id)

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def download_music(m, song, choice):
    try:
        URL="https://api.paxsenix.org/dl"

        if choice == "deezer":
            api = f"{URL}/{choice}?url={song}&quality=flac"
            data = await wait_until_ok(api)

            if data == 429 or data == 504:
                await bot.send_message(m.chat.id, f"API busy: {data}")
                return "failed"

            if data == 500:
                await bot.send_message(m.chat.id, f"API Error: {data}")
                return "failed"

            if data['message'] == "Failed to retrieve this content":
                return "failed"
            
            link = data['directUrl']
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as response:
                    song = await response.content.read()
                    return song

        elif choice == "spotify":
            api = f"{URL}/{choice}?url={song}&serv=spotdl"
            data = await wait_until_ok(api)

            if data == 429 or data == 504:
                await bot.send_message(m.chat.id, f"API busy: {data}")
                return "failed"

            if data == 500:
                await bot.send_message(m.chat.id, f"API Error: {data}")
                return "failed"

            if data['message'] == "Failed to retrieve this content":
                return "failed"
            
            link = data['directUrl']
            return link

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def check_yt_dl_status(task_url):
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(task_url) as response:
                data = await response.json()
                
                if data.get('status') == "done":
                    link = data.get('download')
                    thumb = data.get('thumbnail')
                    title = data.get('title')
                    return link, thumb, title

            await asyncio.sleep(0.2)