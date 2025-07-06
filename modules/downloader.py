import aiohttp
from info import *
import re
from core.utils import log_error

async def download_instagram_reel(m):
    url = "https://api.paxsenix.biz.id/dl/ig"

    # Extract first URL from the message text
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    insta_url = match.group()
    params = {"url": insta_url}

    headers = {
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                try:
                    reel_url = data["url"][0]["url"]
                    username = data["meta"]["username"]
                    title = data["meta"]["title"]
                    thumb_url = data["thumb"]

                    await bot.send_video(
                        chat_id=m.chat.id,
                        video=reel_url,
                        cover=thumb_url,
                        caption=f"👤 Username: `{username}`\n"
                                f"📄 Title: `{title}`",
                        parse_mode="Markdown"
                    )
                    print("Reel URL:", reel_url)
                except (KeyError, IndexError):
                    await log_error(bot, "unable to find reel URL in response", context_msg=m)
                except Exception as error:
                    await log_error(bot, error, context_msg=m)
                    await bot.reply_to(m, "An error occurred.")
            else:
                text = await resp.text()
                print(f"Error {resp.status}: {text}")
                await log_error(bot, "unable to download reel", context_msg=m)
                await bot.reply_to(m, "An error occurred.")

async def download_spotify_song(m):
    url = "https://api.paxsenix.biz.id/dl/spotify"
    metadata_url = "https://api.paxsenix.biz.id/spotify/track"

    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    spotify_url = match.group()
    song_id = spotify_url.split("track/")[1]
    params = {"url": spotify_url, "serv": "spotify"}
    metadata_params = {"id": song_id}

    headers = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        # Get metadata first
        async with session.get(metadata_url, headers=headers, params=metadata_params) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"Metadata Error {resp.status}: {text}")
                await bot.reply_to(m, "Unable to retrieve song metadata. Please verify the link and try again.")
                return
            data = await resp.json()

            try:
                title = data["name"]
                artists = ", ".join([a["name"] for a in data["album"]["artists"]])
                thumbnail = data["album"]["images"][1]["url"]
            except (KeyError, IndexError):
                print("Failed to extract metadata.")
                await bot.reply_to(m, "Metadata extraction failed. Please provide a valid Spotify track link.")
                return
            except Exception as error:
                await log_error(bot, error, context_msg=m)
                await bot.reply_to(m, "An error occurred.")
            

        # Get the actual audio URL
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"Audio Download Error {resp.status}: {text}")
                await bot.reply_to(m, "Audio not found.")
                return

            data = await resp.json()

            try:
                song_url = data["directUrl"]
                await bot.send_audio(
                    m.chat.id,
                    audio=song_url,
                    caption=f"🎵 Title: `{title}`\n"
                            f"🎤 Artists: `{artists}`",
                    thumbnail=thumbnail
                )
            except (KeyError, IndexError) as e:
                print("Failed to extract or send audio:", e)
                await bot.reply_to(m, "Audio not found.")
            except Exception as error:
                await log_error(bot, error, context_msg=m)
                await bot.reply_to(m, "An error occurred.")
