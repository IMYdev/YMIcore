import json
import aiohttp
from info import bot
from modules.do import do
from core.imysdb import IMYDB
from core.utils import log_error

key = "bf55d4ef-3bc1-4110-9d48-da7fe8a4dfc4"
url = "https://api.awanllm.com/v1/chat/completions"


# AwanLLM response fetcher
async def fetch_response(prompt, history, username):
    payload = json.dumps({
        "model": "Awanllm-Llama-3-8B-Cumulus",
        "messages": history + [{"role": "user", "content": f"{username}: {prompt}"}],
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
            return "Error: Unable to fetch response."


# Main chat handler
async def chat(m):
    try:
        prompt = m.text.split(maxsplit=1)[1]
        chat_id = str(m.chat.id).lstrip('-')  # Normalize chat ID

        get_info = await bot.get_chat(m.from_user.id)
        username = get_info.username or f"User_{m.from_user.id}"

        db = IMYDB(f"history/{chat_id}_history.json")
        history = db.get("chat_history", [])

        response_content = await fetch_response(prompt, history, username)

        if response_content:
            history.append({"role": "assistant", "content": response_content})
            db.set("chat_history", history)
            await bot.reply_to(m, response_content)
        else:
            await bot.reply_to(m, "No response from server.")

    except IndexError:
        await bot.reply_to(m, "Please provide a prompt.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")


# Admin-only memory reset
async def reset_memory(m):
    if m.chat.type != 'private':
        if not await is_user_admin(m.chat.id, m.from_user.id):
            await bot.reply_to(m, "Admins only.")
            return

    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f"history/{chat_id}_history.json")
    db.set("chat_history", [])
    await bot.reply_to(m, "Chat history cleared.")


async def is_user_admin(chat_id, user_id):
    chat_admins = await bot.get_chat_administrators(chat_id)
    for admin in chat_admins:
        if admin.user.id == user_id:
            return True
    return False
