from info import (bot, Downloader, PAXSENIX_TOKENS)
from telebot.formatting import (hlink, hcite)
from telebot.util import user_link
import re
from core.utils import (handle_errors, get_args)
import aiohttp
import asyncio
from yt_dlp import YoutubeDL
from innertube import InnerTube
from telebot.types import InputMediaPhoto, InputMediaVideo
import random
import os
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
                if response.status in [429, 500, 504]:
                    return response.status
                
                data = await response.json()
                if data.get('message') == "Failed to retrieve this content":
                    return data
                
                if data.get('ok') == True:
                    return data
                
                await asyncio.sleep(delay)

@handle_errors
async def extract_supported_url(m):
    if not Downloader or not m.text:
        return
    
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    url = match.group(0)

    if "youtube.com" in url or "youtu.be" in url:
        await download_yt_video(m, url)

    elif "instagram.com" in url:

        if "reel" in url:
            await instagram_dl(m, url.split("?", 1)[0], True)
            return

        await instagram_dl(m, url.split("?", 1)[0])

    elif "tiktok.com" in url:
        await tiktok_dl(m, url)

    elif "facebook.com" in url:
        await facebook_dl(m, url)

    elif "twitter.com" in url or "x.com" in url:
        await twitter_dl(m, url)

class loggerOutputs:
    def error(msg): pass
    def warning(msg): pass
    def debug(msg): pass

ytdl_opts = {"quiet": True, "logger": loggerOutputs}
if os.path.exists("cookies.txt"):
    ytdl_opts["cookiefile"] = "cookies.txt"

ig_opts = {
    "format": "best[ext=mp4]/best", 
    "quiet": True,
    "logger": loggerOutputs
}

def get_shared_caption(m, info, url):
    username = f"Shared by @{m.from_user.username}" if m.from_user.username else f"Shared by {user_link(m.from_user)}"
    description = info.get('description') or info.get('title', '')
    source = hlink('Source', url, escape=False)
    caption = f"{hcite(description, expandable=True)}\n{username}\n{source}"
    return caption if len(caption) <= 1024 else f"{username}\n{source}"

async def instagram_dl(m, url, reel=False):
    try:
        with YoutubeDL(ig_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if reel:
            caption = get_shared_caption(m, info, url)
            dl_url = info.get('url')
            await bot.send_video(m.chat.id, dl_url, caption=caption, parse_mode="HTML")
            return

        api=f"https://api.paxsenix.org/dl/ig?url={url}"
        data = await wait_until_ok(api)

        if data == 429 or data == 504:
            await bot.send_message(m.chat.id, f"API busy: {data}")
            return

        if data == 500:
            await bot.send_message(m.chat.id, f"API Error: {data}")
            return

        links = data['downloadUrls']
        media_list = []
        caption = get_shared_caption(m, info, url)
        media_count = 0

        if len(links) > 1:
            for i in range(len(links)):
                link = links[i]['url']
                file_ext = links[i]['ext']

                if file_ext == 'mp4':

                    if media_count == 0:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(link) as response:
                                link = await response.content.read()
                                media = InputMediaVideo(link, caption=caption, parse_mode="HTML")

                    else:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(link) as response:
                                link = await response.content.read()
                                media = InputMediaVideo(link)

                    media_count += 1

                else:
                    if media_count == 0:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(link) as response:
                                link = await response.content.read()
                                media = InputMediaPhoto(link, caption=caption, parse_mode="HTML")

                    else:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(link) as response:
                                link = await response.content.read()
                                media = InputMediaPhoto(link)

                    media_count += 1

                media_list.append(media)

            if len(media_list) > 10:
                new_list = media_list[10:]
                media_list = media_list[:10]
                await bot.send_media_group(m.chat.id, media_list)
                await bot.send_media_group(m.chat.id, new_list)
                return

            await bot.send_media_group(m.chat.id, media_list)

        else:
            file_ext = links[0]['ext']
            link = links[0]['url']

            if file_ext == 'mp4':
                await bot.send_video(m.chat.id, link, caption=caption, parse_mode="HTML")
            else:
                await bot.send_photo(m.chat.id, link, caption=caption, parse_mode="HTML")

    except Exception as error:
        if "HTTP URL" in str(error):
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as response:
                    await bot.send_video(m.chat.id, response.content, caption=caption, parse_mode="HTML")
                    return

        if "Too Many Requests" in str(error):
            parts = str(error).split()
            wait_time = None
            for part in parts:

                if part.isdigit() and part != "429":
                    wait_time = int(part)
                    break

            if wait_time:
                await asyncio.sleep(wait_time)
                return await bot.send_media_group(m.chat.id, new_list)
        else:
            await bot.reply_to(m, error)

@handle_errors
async def tiktok_dl(m, url):
    api = f"https://api.paxsenix.org/dl/tiktok?url={url}"
    data = await wait_until_ok(api)

    if isinstance(data, int):
        return await bot.send_message(m.chat.id, f"API Error: {data}")

    source = hlink("Source", url, escape=False)
    username = data['detail']['author']
    author = hlink(f"@{username}", data['detail']['authorProfileLink'].replace("\\", ""), escape=False)
    description = hcite(data['detail']['description'], expandable=True)
    caption = f"{description}\n{author}\n{source}"
    if len(caption) > 1024: caption = f"{author}\n{source}"

    links = data['downloadUrls']
    if data['detail']['type'] == 'image':
        images, music = links['images'], links.get('music')
        if len(images) > 1:
            media_list = [InputMediaPhoto(img, caption=caption if i == 0 else "", parse_mode="HTML") for i, img in enumerate(images)]
            await bot.send_media_group(m.chat.id, media_list)
            if music: await bot.send_audio(m.chat.id, music)
        else:
            await bot.send_photo(m.chat.id, images[0], caption=caption, parse_mode="HTML")
            if music: await bot.send_audio(m.chat.id, music)
    else:
        await bot.send_video(m.chat.id, links['video'], caption=caption, parse_mode="HTML")

@handle_errors
async def facebook_dl(m, url):
    with YoutubeDL(ytdl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    link = info.get('formats')[1].get('url')
    caption = get_shared_caption(m, info, url)
    await bot.send_video(m.chat.id, video=link, caption=caption, parse_mode="HTML")

@handle_errors
async def twitter_dl(m, url):
    try:
        with YoutubeDL(ytdl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        link = next((f['url'] for f in info.get('formats', []) if f.get('ext') == 'mp4' and f.get('protocol') == 'https'), None)
        caption = get_shared_caption(m, info, url)
        if link:
            await bot.send_video(m.chat.id, video=link, caption=caption, parse_mode="HTML")
        else:
            raise Exception("No video")
    except Exception as e:
        if "No video" in str(e):
            fix_url = url.replace("x.com", "d.fixupx.com") if "x.com" in url else url.replace("twitter.com", "d.fxtwitter.com")
            await bot.send_photo(m.chat.id, photo=fix_url)
        else:
            raise e

@handle_errors
async def download_yt_video(m, link):
    if "-audio" in m.text:
        audio_data = await download_yt_audio(m, link)
        if audio_data: await bot.send_audio(m.chat.id, audio=audio_data, reply_to_message_id=m.message_id)
        return

    opts = ytdl_opts.copy()
    opts["format"] = "18"
    with YoutubeDL(params=opts) as ydl:
        info = ydl.extract_info(link, download=False)
        file_size = info.get("filesize") or info.get("filesize_approx")
        if file_size and file_size > 52428800: return
        vid_cap = f"{info.get('title')}\n{hlink('Source', link, escape=False)}"
        url = info.get("url")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            await bot.send_video(m.chat.id, video=await response.read(), caption=vid_cap, parse_mode="HTML")

async def download_yt_audio(m, link):
    opts = ytdl_opts.copy()
    opts["format"] = "bestaudio/best"
    with YoutubeDL(params=opts) as ydl:
        info = ydl.extract_info(link, download=False)
        audio_url = info['url']
    async with aiohttp.ClientSession() as session:
        async with session.get(audio_url) as response:
            return await response.read()

async def embed_metadata(audio_data, title, artist):
    try:
        with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as f:
            f.write(audio_data)
            in_path = f.name

        out_path = in_path + ".mp3"
        cmd = ['ffmpeg', '-i', in_path, '-c:a', 'libmp3lame', '-b:a', '320k', '-metadata', f'title={title}', '-metadata', f'artist={artist}', '-y', out_path]
        
        if subprocess.run(cmd, capture_output=True).returncode == 0:
            os.unlink(in_path)
            return out_path
        os.unlink(in_path)
    except: pass
    return audio_data

@handle_errors
async def music_search(m):
    if not Downloader: return
    args = get_args(m)
    if not args: return await bot.reply_to(m, "No song name provided.")

    query = " ".join(args)
    old = await bot.reply_to(m, "Looking for song...")
    
    client = InnerTube("WEB")
    data = client.search(query=query, params="EgWKAQwI")
    sections = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']

    for section in sections:
        items = section.get('itemSectionRenderer', {}).get('contents', [])
        for item in items:
            video = item.get('videoRenderer')
            if not video: continue
            
            url = f"https://www.youtube.com/watch?v={video['videoId']}"
            title = video.get("title", {}).get("runs", [{}])[0].get("text")
            artist = video.get("ownerText", {}).get("runs", [{}])[0].get("text")
            cover = video.get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url")
            
            await fetch_music(m, url, old, f"{artist} - {title}", title, artist, cover)
            return

async def fetch_music(m, yt_url, status_msg, caption, title, artist, cover):
    cover_path = None
    try:
        if cover:
            async with aiohttp.ClientSession() as session:
                async with session.get(cover) as resp:
                    if resp.status == 200:
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                            f.write(await resp.read())
                            cover_path = f.name

        api_url = f"https://api.paxsenix.org/tools/songlink?url={yt_url}"
        data = await wait_until_ok(api_url)
        song_data = None
        
        if isinstance(data, dict) and data.get('links'):
            links = data['links']
            for choice in [('deezer', 5), ('spotify', 3)]:
                if len(links) > choice[1]:
                    await bot.edit_message_text(f"Fetching from {choice[0].capitalize()}...", m.chat.id, status_msg.id)
                    res = await download_music_api(m, links[choice[1]]['url'], choice[0])
                    if res:
                        song_data = res
                        break

        if not song_data:
            await bot.edit_message_text("Fetching from YT...", m.chat.id, status_msg.id)
            song_data = await download_yt_audio(m, yt_url)

        if song_data:
            await bot.delete_message(m.chat.id, status_msg.id)
            await bot.send_chat_action(m.chat.id, "upload_voice")
            
            processed = await embed_metadata(song_data, title, artist)
            thumb = open(cover_path, 'rb') if cover_path else None
            
            audio_arg = open(processed, 'rb') if isinstance(processed, str) else processed
            await bot.send_audio(m.chat.id, audio=audio_arg, caption=caption, thumbnail=thumb, reply_to_message_id=m.message_id)
            if isinstance(processed, str): os.unlink(processed)
            if thumb: thumb.close()
        else:
            await bot.edit_message_text("Failed to download.", m.chat.id, status_msg.id)

    finally:
        if cover_path: os.unlink(cover_path)

async def download_music_api(m, url, choice):
    api = f"https://api.paxsenix.org/dl/{choice}?url={url}"
    if choice == "deezer": api += "&quality=320kbps"
    else: api += "&serv=spotdl"
    
    data = await wait_until_ok(api)
    if isinstance(data, dict) and data.get('directUrl'):
        async with aiohttp.ClientSession() as session:
            async with session.get(data['directUrl']) as resp:
                if resp.status == 200: return await resp.read()
    return None
