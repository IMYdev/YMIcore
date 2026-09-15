from info import (bot, Downloader)
from telebot.formatting import (hlink, hcite)
from telebot.util import user_link
import re
import asyncio
from urllib.parse import urlparse, unquote
import html
from core.utils import handle_errors
import aiohttp
from yt_dlp import YoutubeDL
from telebot.types import InputMediaPhoto, InputMediaVideo
import os

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
        await instagram_dl(m, url.split("?", 1)[0])

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

def _instagram_shortcode(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != "instagram.com" and not host.endswith(".instagram.com"):
        return None
    segments = [unquote(s) for s in parsed.path.strip("/").split("/") if s]
    post_type = shortcode = None
    if len(segments) >= 2 and segments[0] in ("p", "reel", "reels"):
        post_type, shortcode = segments[0], segments[1]
    elif len(segments) >= 3 and segments[1] in ("p", "reel", "reels"):
        post_type, shortcode = segments[1], segments[2]
    if post_type is None or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', shortcode):
        return None
    return {"shortcode": shortcode, "reel": post_type in ("reel", "reels")}

def _post_snowcode(shortcode, reel, idx=None):
    payload = f'"i":"{shortcode}"'
    if reel:
        payload += ',"p":"reel"'
    if idx is not None:
        payload += f',"n":{idx}'
    return str(int.from_bytes(payload.encode(), "big"))

def _og_caption(content):
    content = re.sub(r'<p[^>]*><b>.*?</b></p>', '', content, flags=re.S)
    return html.unescape(re.sub(r'<[^>]+>', '', content)).strip()

def _og_total(content):
    m = re.search(r'🖼\ufe0f?\s*(\d+)(?:\s*/\s*(\d+))?', content)
    if not m:
        return None
    return int(m.group(2) or m.group(1))

async def _fetch_og_items(shortcode, reel, start, end):
    results = []
    async with aiohttp.ClientSession() as session:
        async def fetch(idx):
            api = f"https://oginstagram.com/api/v1/statuses/{_post_snowcode(shortcode, reel, idx)}"
            try:
                async with session.get(api, headers={"User-Agent": "YMIcoreBot/1.0"}) as resp:
                    if resp.status != 200:
                        return None
                    if not resp.headers.get("Content-Type", "").startswith("application/json"):
                        return None
                    data = await resp.json()
            except Exception:
                return None
            atts = data.get("media_attachments") if isinstance(data, dict) else None
            if not atts or not atts[0].get("url"):
                return None
            return atts[0]
        results = await asyncio.gather(*(fetch(i) for i in range(start, end + 1)))
    return [r for r in results if r]

@handle_errors
async def instagram_dl(m, url):
    route = _instagram_shortcode(url)
    if route and await instagram_dl_og(m, url):
        return
    if route and route["reel"]:
        await instagram_dl_ytdlp(m, url)

async def instagram_dl_og(m, url):
    route = _instagram_shortcode(url)
    api = f"https://oginstagram.com/api/v1/statuses/{_post_snowcode(route['shortcode'], route['reel'])}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api, headers={"User-Agent": "YMIcoreBot/1.0"}) as resp:
                if resp.status != 200:
                    return False
                if not resp.headers.get("Content-Type", "").startswith("application/json"):
                    return False
                data = await resp.json()
    except Exception:
        return False

    attachments = data.get("media_attachments") if isinstance(data, dict) else None
    if not attachments:
        return False

    total = _og_total(data.get("content") or "") or len(attachments)
    if total > len(attachments):
        missing = await _fetch_og_items(route["shortcode"], route["reel"], len(attachments) + 1, total)
        if missing:
            attachments = list(attachments) + missing

    account = data.get("account") or {}
    username = account.get("username")
    caption_lines = []
    if caption_text := _og_caption(data.get("content") or ""):
        caption_lines.append(hcite(caption_text, expandable=True))
    author = None
    if username:
        author = hlink(f"@{username}", f"https://www.instagram.com/{username}", escape=False)
        caption_lines.append(author)
    source = hlink("Source", url, escape=False)
    caption_lines.append(source)
    caption = "\n".join(caption_lines)
    if len(caption) > 1024:
        caption = "\n".join([x for x in (author, source) if x])

    if len(attachments) == 1:
        media_url = attachments[0].get("url")
        if not media_url:
            return False
        if attachments[0].get("type") == "video":
            await bot.send_video(m.chat.id, video=media_url, caption=caption, parse_mode="HTML")
        else:
            await bot.send_photo(m.chat.id, photo=media_url, caption=caption, parse_mode="HTML")
        return True

    media_list = []
    for i, media in enumerate(attachments):
        media_url = media.get("url")
        if not media_url:
            continue
        item_caption = caption if i == 0 else ""
        if media.get("type") == "video":
            media_list.append(InputMediaVideo(media=media_url, caption=item_caption, parse_mode="HTML"))
        else:
            media_list.append(InputMediaPhoto(media=media_url, caption=item_caption, parse_mode="HTML"))

    if not media_list:
        return False
    if len(media_list) == 1:
        media = media_list[0]
        if isinstance(media, InputMediaVideo):
            await bot.send_video(m.chat.id, video=media.media, caption=caption, parse_mode="HTML")
        else:
            await bot.send_photo(m.chat.id, photo=media.media, caption=caption, parse_mode="HTML")
        return True

    for chunk in [media_list[i:i + 10] for i in range(0, len(media_list), 10)]:
        await bot.send_media_group(m.chat.id, chunk)
    return True

async def instagram_dl_ytdlp(m, url):
    with YoutubeDL(ig_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    dl_url = info.get('url')
    if not dl_url:
        raise Exception("Could not extract media from reel.")
    caption = get_shared_caption(m, info, url)
    await bot.send_video(m.chat.id, dl_url, caption=caption, parse_mode="HTML")

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
