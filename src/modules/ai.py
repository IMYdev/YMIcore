import cohere
from info import bot, COHERE_API_KEY, SYSTEM_PROMPT
from core.imysdb import IMYDB
from core.utils import handle_errors

# Initialize client only if key exists
co = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
db = IMYDB('runtime/ai/sessions.json')

@handle_errors
async def manage_session(m):
    if not co:
        await bot.reply_to(m, "AI features are currently offline.")
        return

    chat_id = str(m.chat.id)
    args = m.text.split()

    if len(args) > 1 and args[1].lower() == "stop":
        db.delete(f"sessions.{chat_id}")
        await bot.reply_to(m, "Neural link severed. Data purged.")
        return

    db.set(f"sessions.{chat_id}", {"active": True, "history": []})
    await bot.reply_to(m, "Neural link established. Protocol 1 initiated. Monitoring communication logs.")

async def process_ai_message(m):
    if not co: return
    
    chat_id = str(m.chat.id)
    session = db.get(f"sessions.{chat_id}")
    if not session or not session.get("active"):
        return

    history = session.get("history", [])
    bot_info = await bot.get_me()
    
    is_pm = m.chat.type == 'private'
    is_tagged = f"@{bot_info.username}" in (m.text or "")
    is_reply_to_bot = m.reply_to_message and m.reply_to_message.from_user.id == bot_info.id

    history.append({"role": "USER", "message": m.text})

    if is_pm or is_tagged or is_reply_to_bot:
        response = co.chat(
            chat_history=history[:-1],
            message=m.text,
            preamble=SYSTEM_PROMPT,
            model="command-r7b-12-2024"
        )
        bot_reply = response.text
        history.append({"role": "CHATBOT", "message": bot_reply})
        await bot.reply_to(m, bot_reply)

    db.set(f"sessions.{chat_id}.history", history[-15:])