from time import time
from info import (bot, Downloader, PAXSENIX_TOKENS)
from telebot.formatting import (hlink, hcite)
from telebot.util import user_link
import re
from core.utils import log_error
import aiohttp
import asyncio
from yt_dlp import YoutubeDL
from innertube import InnerTube
from telebot.types import InputMediaPhoto
import random
import os
import json
import tempfile
import subprocess

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

    elif "instagram.com/reel" in url:
        url = url.split("?", 1)[0]
        await instagram_dl(m, url)
    
    elif "tiktok.com" in url:
        await tiktok_dl(m, url)
    
    elif "facebook.com" in url:
        await facebook_dl(m, url)

    elif "twitter.com" in url:
        await twitter_dl(m, url)

    elif "x.com" in url:
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

vid_opts = {
    "quiet": True,
    "format": "18",
    "logger": loggerOutputs
}

cookie_file = "cookies.txt"

if os.path.exists(cookie_file):
    vid_opts["cookiefile"] = cookie_file

async def download_yt_video(m, link):
    try:
        if len(m.text.split(" ", 1)) > 1 and m.text.split(" ", 1)[1] == "-audio":
            link = await download_yt_audio(m, link)
            await bot.send_audio(m.chat.id, audio=link, reply_to_message_id=m.id)
            return

        with YoutubeDL(params=vid_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            file_size = info.get("filesize") or info.get("filesize_approx")
            if not file_size:
                return
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
    "format": "bestaudio/best",
    "logger": loggerOutputs
}

cookie_file = "cookies.txt"

if os.path.exists(cookie_file):
    audio_opts["cookiefile"] = cookie_file

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


async def embed_metadata(audio_data, title, artist):
    try:
        with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as input_file:
            input_file.write(audio_data)
            input_path = input_file.name

        probe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            input_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_result.returncode != 0:
            raise Exception(f"FFprobe error: {probe_result.stderr}")

        probe_data = json.loads(probe_result.stdout)
        audio_stream = next((s for s in probe_data['streams'] if s['codec_type'] == 'audio'), None)
        if not audio_stream:
            raise Exception("No audio stream found")

        output_extension = '.mp3'
        output_format = 'mp3'
        with tempfile.NamedTemporaryFile(suffix=output_extension, delete=False) as output_file:
            output_path = output_file.name

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:a', 'libmp3lame',
            '-b:a', '320k',
            '-metadata', f'title={title}',
            '-metadata', f'artist={artist}',
            '-f', output_format,
            '-y',
            output_path
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
            return audio_data

        os.unlink(input_path)
        return output_path

    except Exception as e:
        try:
            if 'input_path' in locals():
                os.unlink(input_path)
            if 'output_path' in locals():
                os.unlink(output_path)
        except:
            pass
        return audio_data

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

            await fetch_music(m, url, old, caption, title, author, cover_url)
            break  # stop after first result


async def fetch_music(m, yt_url, old, caption, title, artist, cover):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(cover, timeout=10) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
                        img_file.write(img_data)
                        cover_path = img_file.name
        api = f"https://api.paxsenix.org/tools/songlink?url={yt_url}"
        data = await wait_until_ok(api)

        if data == 429 or data == 504:
            await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
            link = await download_yt_audio(m, yt_url)
            link = await embed_metadata(link, title, artist)
            await bot.delete_message(m.chat.id, old.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=open(link, 'rb'), caption=caption, thumbnail=open(cover_path, 'rb'), reply_to_message_id=m.id)
            return

        if data == 500:
            await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
            link = await download_yt_audio(m, yt_url)
            link = await embed_metadata(link, title, artist)
            await bot.delete_message(m.chat.id, old.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=open(link, 'rb'), caption=caption, thumbnail=open(cover_path, 'rb'), reply_to_message_id=m.id)
            return

        links = data.get('links')

        if links:
            spotify  = links[3].get('url') or "N/A"
            deezer   = links[5].get('url') or "N/A"

            if deezer != "N/A":
                await bot.edit_message_text("Fetching song from Deezer...", m.chat.id, old.id)
                link = await download_music(m, deezer, "deezer")
                if link != "failed":
                    link = await embed_metadata(link, title, artist)

            elif spotify != "N/A":
                await bot.edit_message_text("Fetching song from Spotify...", m.chat.id, old.id)
                link = await download_music(m, spotify, "spotify")

            else:
                await bot.edit_message_text("Fetching song from YT...", m.chat.id, old.id)
                link = await download_yt_audio(m, yt_url)
                link = await embed_metadata(link, title, artist)

        await bot.delete_message(m.chat.id, old.id)

        if link != "failed":
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=open(link, 'rb'), caption=caption, thumbnail=open(cover_path, 'rb'), reply_to_message_id=m.id)
        else:
            link = await download_yt_audio(m, yt_url)
            link = await embed_metadata(link, title, artist)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            await bot.send_audio(m.chat.id, audio=open(link, 'rb'), caption=caption, thumbnail=open(cover_path, 'rb'), reply_to_message_id=m.id)

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)

async def download_music(m, song, choice):
    try:
        URL="https://api.paxsenix.org/dl"

        if choice == "deezer":
            api = f"{URL}/{choice}?url={song}&quality=320kbps"
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
            if link and link != "failed":
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as response:
                        if response.status == 200:
                            return await response.content.read()
            return "failed"

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)