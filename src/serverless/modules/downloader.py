from info import bot
import re
from core.utils import log_error

async def download_instagram_reel(m):
    # Extract first URL from the message text
    match = re.search(r'https?://\S+', m.text)
    if not match:
        return

    try:
        insta_url = match.group()
        modified_url = re.sub(r'(https?://)(www\.)?instagram', r'\1\2ddinstagram', insta_url)
        await bot.send_video(m.chat.id, modified_url)
    except Exception as e:
        log_error(bot, e, m)
