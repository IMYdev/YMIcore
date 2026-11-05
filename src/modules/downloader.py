from info import (bot, Downloader)
from telebot.formatting import (hlink, hcite)
from telebot.util import user_link
import re
import asyncio
from urllib.parse import urlparse, unquote
import html
from core.utils import handle_errors, topic_kwargs
import aiohttp
from telebot.types import InputMediaPhoto, InputMediaVideo

@handle_errors
async def extract_supported_url(m):
    if not Downloader or not m.text:
        return
    
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    url = match.group(0)

    platform = supported_platform(url)
    if platform == "instagram":
        await instagram_dl(m, url.split("?", 1)[0])

    elif platform == "twitter":
        await twitter_dl(m, url)

def supported_platform(url):
    host = (urlparse(url).hostname or "").lower()
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"
    if host in ("twitter.com", "x.com") or host.endswith((".twitter.com", ".x.com")):
        return "twitter"
    return None

def is_download_url(text):
    match = re.search(r'https?://\S+', text or "")
    return bool(match and supported_platform(match.group(0)))

def get_shared_caption(m, info, url):
    username = f"Shared by @{m.from_user.username}" if m.from_user.username else f"Shared by {user_link(m.from_user)}"
    description = info.get('description') or info.get('title', '')
    source = hlink('Source', url, escape=False)
    body = f"{hcite(description, expandable=True)}\n{username}" if description else username
    caption = f"{body}\n{source}"
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
    if _instagram_shortcode(url) and not await instagram_dl_og(m, url) and not await instagram_dl_vx(m, url):
        await bot.reply_to(m, "Couldn't download this Instagram media.", **topic_kwargs(m))

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
            await bot.send_video(m.chat.id, video=media_url, caption=caption, parse_mode="HTML", **topic_kwargs(m))
        else:
            await bot.send_photo(m.chat.id, photo=media_url, caption=caption, parse_mode="HTML", **topic_kwargs(m))
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
            await bot.send_video(m.chat.id, video=media.media, caption=caption, parse_mode="HTML", **topic_kwargs(m))
        else:
            await bot.send_photo(m.chat.id, photo=media.media, caption=caption, parse_mode="HTML", **topic_kwargs(m))
        return True

    for chunk in [media_list[i:i + 10] for i in range(0, len(media_list), 10)]:
        await bot.send_media_group(m.chat.id, chunk, **topic_kwargs(m))
    return True

def _vx_media(page):
    video = re.search(r'<meta property="og:video" content="([^"]+)"', page)
    if not video:
        return None
    description = re.search(r'<meta property="og:description" content="([^"]*)"', page)
    return html.unescape(video.group(1)), html.unescape(description.group(1)) if description else ""

async def instagram_dl_vx(m, url):
    route = _instagram_shortcode(url)
    if not route or not route["reel"]:
        return False
    video = f"https://vxinstagram.com/offload/{route['shortcode']}/0.mp4"
    description = ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(f"https://vxinstagram.com/reel/{route['shortcode']}/", headers={"User-Agent": "YMIcoreBot/1.0"}) as resp:
                if resp.status == 200:
                    media = _vx_media(await resp.text())
                    if media:
                        video, description = media
    except Exception:
        pass
    caption = get_shared_caption(m, {"description": description}, url)
    await bot.send_video(m.chat.id, video=video, caption=caption, parse_mode="HTML", **topic_kwargs(m))
    return True

def _tweet_video_url(data):
    tweet = data.get("tweet") or data.get("status") or data
    media = tweet.get("media") or {}
    for item in media.get("videos") or []:
        if item.get("url"):
            return item["url"]
    for item in media.get("all") or []:
        if item.get("type") in ("video", "gif") and item.get("url"):
            return item["url"]
    return None

@handle_errors
async def twitter_dl(m, url):
    status = re.search(r'/status/(\d+)', url)
    if not status:
        return
    try:
        api_url = f"https://api.fxtwitter.com/status/{status.group(1)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers={"User-Agent": "YMIcoreBot/1.0"}) as resp:
                if resp.status != 200:
                    raise Exception(f"FxTwitter returned {resp.status}")
                data = await resp.json()
        link = _tweet_video_url(data)
        if not link:
            raise Exception("No video")
        tweet = data.get("tweet") or data.get("status") or data
        caption = get_shared_caption(m, {"description": tweet.get("text") or ""}, url)
        await bot.send_video(m.chat.id, video=link, caption=caption, parse_mode="HTML", **topic_kwargs(m))
    except Exception as e:
        if "No video" in str(e):
            fix_url = url.replace("x.com", "d.fixupx.com") if "x.com" in url else url.replace("twitter.com", "d.fxtwitter.com")
            await bot.send_photo(m.chat.id, photo=fix_url, **topic_kwargs(m))
        else:
            raise e
