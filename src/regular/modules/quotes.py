from info import bot
import aiohttp
from core.utils import log_error

async def quote_handler(m):
    if not m.reply_to_message:
        await bot.reply_to(m, "Please reply to a message.")
        return

    base = m.reply_to_message
    if not m.reply_to_message.text:
        return
    collected = [base]


    messages = []

    for msg in collected:
        user = msg.from_user
        text = msg.text or msg.caption or "<no text>"

        avatar_url = None
        try:
            photos = await bot.get_user_profile_photos(user.id)
            if photos.total_count > 0:
                file_id = photos.photos[0][0].file_id
                avatar_url = await bot.get_file_url(file_id)
        except Exception:
            pass

        qmsg = {
            "entities": ["string"],
            "avatar": bool(avatar_url),
            "from": {
                "id": user.id,
                "name": user.first_name,
                "photo": {"url": avatar_url} if avatar_url else {}
            },
            "text": text
        }


        messages.append(qmsg)

    payload = {
        "type": "quote",
        "format": "webp",
        "backgroundColor": "#000000",
        "width": 512,
        "height": 768,
        "scale": 3,
        "messages": messages
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.paxsenix.org/maker/quotly", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        image = data["url"]
                        await bot.send_sticker(m.chat.id, image, reply_to_message_id=m.message_id)
                    except (KeyError, IndexError):
                        await bot.reply_to(m, "Failed to create quote.")
                else:
                    await bot.reply_to(m, f"API error: {resp.status}")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")
