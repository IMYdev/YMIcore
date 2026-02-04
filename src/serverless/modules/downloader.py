from info import (bot, Downloader, PAXSENIX_TOKENS)
from telebot.formatting import (hlink, hcite)
from telebot.util import user_link
import re
from core.utils import log_error
import aiohttp
import asyncio
from innertube import InnerTube
from yt_dlp import YoutubeDL
from telebot.types import InputMediaPhoto, InputMediaVideo
import random
import os
import tempfile

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

    elif url.startswith("https://www.instagram.com") or url.startswith("https://instagram.com"):
        url = url.split("?", 1)[0]
        await instagram_dl(m, url)
    
    elif "tiktok.com" in url:
        await tiktok_dl(m, url)
    
    elif "facebook.com" in url:
        await facebook_dl(m, url)

    elif url.startswith("https://twitter.com") or url.startswith("https://www.twitter.com"):
        await twitter_dl(m, url)

    elif url.startswith("https://x.com") or url.startswith("https://www.x.com"):
        await twitter_dl(m, url)

class loggerOutputs:
    def error(msg):
        pass
    def warning(msg):
        pass
    def debug(msg):
        pass

ig_opts = {
    "quiet": True,
    "logger": loggerOutputs
}

async def instagram_dl(m, url):
    try:
        api = f"https://delirius-apiofc.vercel.app/download/instagram?url={url}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api) as response:
                if response.status != 200:
                    await bot.send_message("An error occurred")
                data_json = await response.json()

        if not data_json.get("status") or not data_json.get("data"):
            await bot.send_message("An error occurred")
        
        items = data_json.get("data", [])

        description = ""
        try:
            with YoutubeDL(ig_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                description = info.get('description') or info.get('title') or ""
        except Exception:
            description = ""

        username = f"Shared by @{m.from_user.username}" if m.from_user.username else f"Shared by {user_link(m.from_user)}"
        
        if description:
            caption = f"{hcite(description, expandable=True)}\n{username}\n{hlink('Source', url, escape=False)}"
        else:
            caption = f"{username}\n{hlink('Source', url, escape=False)}"
        
        if len(caption) > 1024:
            caption = f"{username}\n{hlink('Source', url, escape=False)}"

        media_list = []
        for i, item in enumerate(items):
            media_type = item.get("type")
            media_url = item.get("url")
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url) as response:
                    media_url = await response.content.read()
            
            current_caption = caption if i == 0 else None
            
            if media_type == "image":
                media_list.append(InputMediaPhoto(media_url, caption=current_caption, parse_mode="HTML"))
            else:
                media_list.append(InputMediaVideo(media_url, caption=current_caption, parse_mode="HTML"))

        if len(media_list) == 1:
            if items[0]["type"] == "image":
                media_url = items[0]["url"]
                async with aiohttp.ClientSession() as session:
                    async with session.get(media_url) as response:
                        media_url = await response.content.read()
                await bot.send_photo(m.chat.id, media_url, caption=caption, parse_mode="HTML")
            else:
                await bot.send_video(m.chat.id, media_url, caption=caption, parse_mode="HTML")
        else:
            for i in range(0, len(media_list), 10):
                await bot.send_media_group(m.chat.id, media_list[i:i+10])

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

async def twitter_dl(m, url):
    try:
        with YoutubeDL(ig_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        for fmt in info.get('formats', []):
            if fmt.get('ext') == 'mp4' and fmt.get('protocol') == 'https':
                link = fmt.get('url')
                break

        title = info.get('title')
        username = f"Shared by @{m.from_user.username}" if m.from_user.username else f"Shared by {user_link(m.from_user)}"
        source = hlink("Source", url, escape=False)
        caption = f"{hcite(title, expandable=True)}\n{username}\n{source}"

        if len(caption) > 1024:
            caption = source

        if info.get('ext') == 'mp4':
            await bot.send_video(m.chat.id, video=link, caption=caption, parse_mode="HTML")

    except Exception as error:
        if "No video" in str(error):
            url = url.replace("x.com", "d.fixupx.com") if "x.com" in url else url.replace("twitter.com", "d.fxtwitter.com")
            await bot.send_photo(m.chat.id, photo=url)
            return
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

    data = client.search(query=query, params="EgWKAQwI")  # *params* are the music filter
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

            thumbnails = video.get("thumbnail", {}).get("thumbnails", [])
            cover_url = thumbnails[-1]["url"] if thumbnails else None

            await fetch_music(m, url, old, caption, cover_url)
            break  # stop after first result

async def fetch_music(m, yt_url, old, caption, cover):
    cover_path = None
    song = None
    is_file_path = True # whether we'll use open() or not

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(cover, timeout=10) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
                        img_file.write(img_data)
                        cover_path = img_file.name

        api_url = f"https://api.paxsenix.org/tools/songlink?url={yt_url}"
        data = await wait_until_ok(api_url)

        if isinstance(data, dict) and data.get('links'):
            links = data['links']
            
            spotify_url = links[3].get('url') if len(links) > 3 else None
            deezer_url  = links[5].get('url') if len(links) > 5 else None

            if deezer_url:
                await bot.edit_message_text("Fetching song from Deezer...", m.chat.id, old.id)
                link = await download_music(m, deezer_url, "deezer")
                if link and link != "failed":
                    song = link
                    is_file_path = True 

            if not song and spotify_url:
                await bot.edit_message_text("Fetching song from Spotify...", m.chat.id, old.id)
                link = await download_music(m, spotify_url, "spotify")
                if link and link != "failed":
                    song = link
                    is_file_path = False

        if not song:
            await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
            link = await download_yt_audio(m, yt_url)
            if link and link != "failed":
                song = link
                is_file_path = True

        if song:
            await bot.delete_message(m.chat.id, old.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")

            with open(cover_path, 'rb') as thumb:
                if is_file_path:
                    with open(song, 'rb') as audio:
                        await bot.send_audio(
                            m.chat.id, 
                            audio=audio, 
                            caption=caption, 
                            thumbnail=thumb, 
                            reply_to_message_id=m.id
                        )
                else:
                    await bot.send_audio(
                        m.chat.id, 
                        audio=song, 
                        caption=caption, 
                        thumbnail=thumb, 
                        reply_to_message_id=m.id
                    )
        else:
            await bot.send_message(m.chat.id, "Failed to download audio from all sources.")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

    finally:
        if cover_path and os.path.exists(cover_path):
            try:
                os.remove(cover_path)
            except Exception:
                pass

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