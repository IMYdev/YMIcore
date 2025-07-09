from datetime import datetime
import json
import aiohttp
from info import bot
from modules.wallpapers import wallpaper
from modules.anime import anime
from modules.img import image_gen
from core.imysdbMongo import IMYDB
from core.utils import log_error

key = "bf55d4ef-3bc1-4110-9d48-da7fe8a4dfc4"
url = "https://api.awanllm.com/v1/chat/completions"

history = [
    {
        "role": "system",
        "content": (
            "Directive: Classify the user's request into one of the following sectors: "
            "'normal wallpaper', 'music', 'other', 'anime wallpaper', 'image making or generation'. "
            "Respond with only one of these classifications."
        )
    }
]


async def fetch_response(prompt):
    payload = json.dumps({
        "model": "Awanllm-Llama-3-8B-Cumulus",
        "messages": history + [{"role": "user", "content": f"{prompt}"}],
        "repetition_penalty": 1.1,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "max_tokens": 1024,
    })
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {key}"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=payload) as response:
            if response.status == 200:
                response_json = await response.json()
                if 'choices' in response_json and len(response_json['choices']) > 0:
                    content = response_json['choices'][0]['message'].get('content', '')
                    if content:
                        return content
            else:
                return f"Error: {response.status}"

# Store audit log using IMYDB
def log_to_db(chat_id, user_id, username, prompt, classification, flagged):
    db = IMYDB(f"logs/{chat_id}_audit")
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "username": username,
        "prompt": prompt,
        "classification": classification,
        "flagged": flagged,
    }
    db.set(f"log_{user_id}_{datetime.utcnow().timestamp()}", log_entry)

# Main do() logic
async def do(m):
    try:
        prompt = m.text.split(maxsplit=1)[1]
        classification = await fetch_response(prompt)

        user_id = m.from_user.id
        username = m.from_user.username
        chat_id = str(m.chat.id)

        flagged = False # Compliance logic removed
        log_to_db(chat_id, user_id, username, prompt, classification, flagged)

        if classification:
            match classification:
                case "normal wallpaper":
                    await wallpaper(m)
                case "anime wallpaper":
                    await anime(m)
                case "image making or generation":
                    await image_gen(m)
                case "music" | "other":
                    await bot.reply_to(m, "Request not supported.")
                case _:
                    await bot.reply_to(m, "Invalid classification.")
        else:
            await bot.reply_to(m, "No response.")

    except IndexError:
        await bot.reply_to(m, "Please specify your request.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")
