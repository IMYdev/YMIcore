from info import bot
from modules.captcha import (validate_question, add_question, remove_question, get_captcha_questions)
from core.imysdb import IMYDB
from core.utils import (handle_errors, is_user_admin, get_media_info, get_args)
from core.activity import (log_event, user_label)
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions)
from telebot.formatting import (hbold, hitalic)
import re

def validate_template(template):
    allowed = {"firstname", "lastname", "username"}
    found = set(re.findall(r"{(.*?)}", template))
    return found.issubset(allowed)

@handle_errors
async def set_captcha(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    args = get_args(m)
    if not args or '|' not in " ".join(args):
        await bot.reply_to(m, f"Usage: {hitalic('/setcaptcha Question | Opt1 | Opt2 | CorrectAnswer | 1')}", parse_mode="HTML")
        return

    parts = [p.strip() for p in " ".join(args).split('|')]
    if len(parts) < 4:
        await bot.reply_to(m, "Provide at least: Question, two options, and the correct answer.")
        return

    question = parts[0]
    options = parts[1:-2] if len(parts) > 4 else parts[1:-1]
    correct = parts[-2] if len(parts) > 4 else parts[-1]
    max_attempts = int(parts[-1]) if len(parts) > 4 else 1

    if correct not in options:
        return await bot.reply_to(m, f"The correct answer '{correct}' must be one of the choices.")

    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    db.set('captcha_enabled', True)
    db.set('captcha_max_tries', max_attempts)
    # replace with single question (legacy migration handled by get_captcha_questions readers)
    db.set('captcha_questions', [{"q": question, "opts": options, "ans": correct}])
    for k in ('captcha_q', 'captcha_opts', 'captcha_ans', 'user_attempts'):
        try:
            db.delete(k)
        except Exception:
            pass

    await bot.reply_to(m, f"Captcha enabled!\n{hbold(f'Attempts allowed: {max_attempts}')}\n{hbold('Use /addcaptcha for additional questions.')}", parse_mode="HTML")

@handle_errors
async def captcha_toggle(m):
    if not await is_user_admin(m.chat.id, m.from_user.id): return
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    current = db.get('captcha_enabled', False)
    db.set('captcha_enabled', not current)
    await bot.reply_to(m, f"Captcha is now {'Disabled' if current else 'Enabled'}.")

async def hello(m):
    old, new = m.old_chat_member, m.new_chat_member
    if (getattr(new, 'user', None) and getattr(new.user, 'is_bot', False)):
        return
    # skip admin/creator
    try:
        if new.status == "member" and (old.status in ("left","kicked") or (old.status == "restricted" and getattr(old, "is_member", False) is False)):
            admin_ids = [a.user.id for a in await bot.get_chat_administrators(m.chat.id)]
            if new.user.id in admin_ids:
                chat_id_raw = str(m.chat.id).lstrip('-')
                db = IMYDB(f'runtime/greetings/{chat_id_raw}_greetings.json')
                await send_standard_greeting(m.chat.id, new.user, db)
                return
    except Exception:
        pass
    chat_id_raw = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id_raw}_greetings.json')
    qualifies = False
    if new.status == "member" and old.status in ("left", "kicked"):
        qualifies = True
    elif new.status == "member" and old.status == "restricted" and getattr(old, "is_member", False) is False:
        qualifies = True
    if not qualifies:
        return
    # skip duplicate updates
    from modules.captcha import get_session
    if get_session(m.chat.id, new.user.id) is not None:
        return
    if db.get('captcha_enabled', False):
        questions = get_captcha_questions(db)
        if not questions:
            await send_standard_greeting(m.chat.id, new.user, db)
            return
        from modules.captcha import start_verification
        await start_verification(m.chat, new.user, db)
        return
    await send_standard_greeting(m.chat.id, new.user, db)

async def send_standard_greeting(chat_id, user, db):
    greetings = db.data
    greeting_msg = greetings.get('greeting', "Hello {firstname}, welcome!")
    personalized = greeting_msg.format(
        username=f"@{user.username}" if user.username else 'there',
        firstname=user.first_name,
        lastname=user.last_name or ''
    )
    m_type, m_id = greetings.get('greeting_media_type'), greetings.get('greeting_media_id')
    if m_type and m_id:
        if m_type == 'sticker': 
            await bot.send_sticker(chat_id, m_id)
            await bot.send_message(chat_id, personalized)
        else:
            send_func = getattr(bot, f"send_{m_type}")
            await send_func(chat_id, m_id, caption=personalized)
    else:
        await bot.send_message(chat_id, personalized)
    log_event(
        "greeting",
        chat_id=chat_id,
        user_id=getattr(user, "id", None),
        user_name=user_label(user),
    )

async def _set_event_msg(m, event_type):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    
    args = get_args(m)
    msg_text = " ".join(args)
    
    if not msg_text and not m.reply_to_message:
        return await bot.reply_to(m, f"Give me a {event_type} message or reply to media!")

    if m.reply_to_message:
        m_type, m_id = get_media_info(m.reply_to_message)
        if not m_type:
            return await bot.reply_to(m, "Reply to a photo, video, audio, or sticker.")
        db.set(f'{event_type}_media_type', m_type)
        db.set(f'{event_type}_media_id', m_id)
    else:
        db.set(f'{event_type}_media_type', None)
        db.set(f'{event_type}_media_id', None)

    if msg_text and not validate_template(msg_text):
        return await bot.reply_to(m, "Only {firstname}, {lastname}, and {username} are allowed.")
    
    db.set(event_type, msg_text)
    await bot.reply_to(m, f"{event_type.capitalize()} message updated!")

@handle_errors
async def set_greeting(m):
    await _set_event_msg(m, 'greeting')

@handle_errors
async def set_goodbye(m):
    await _set_event_msg(m, 'goodbye')

async def bye(m):
    old, new = m.old_chat_member, m.new_chat_member
    if not (new.status in ["left", "kicked"] and old.status == "member"):
        return
    chat_id_raw = str(m.chat.id).lstrip('-')
    from modules.captcha import get_session, forget_user, SILENT_EXITS, session_key
    key = session_key(m.chat.id, new.user.id)
    if key in SILENT_EXITS:
        SILENT_EXITS.remove(key)
        return
    if get_session(m.chat.id, new.user.id) is not None:
        await forget_user(m.chat.id, new.user.id)
        return

    chat_id_raw = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id_raw}_greetings.json')
    greetings = db.data
    goodbye_msg = greetings.get('goodbye', "Goodbye {firstname}, we will miss you!")
    
    personalized = goodbye_msg.format(
        username=f"@{new.user.username}" if new.user.username else 'there',
        firstname=new.user.first_name,
        lastname=new.user.last_name or ''
    )

    m_type, m_id = greetings.get('goodbye_media_type'), greetings.get('goodbye_media_id')
    if m_type and m_id:
        if m_type == 'sticker':
            await bot.send_sticker(m.chat.id, m_id)
            await bot.send_message(m.chat.id, personalized)
        else:
            send_func = getattr(bot, f"send_{m_type}")
            await send_func(m.chat.id, m_id, caption=personalized)
    else:
        await bot.send_message(m.chat.id, personalized)
    log_event(
        "farewell",
        chat_id=m.chat.id,
        user_id=getattr(new.user, "id", None),
        user_name=user_label(new.user),
    )

@handle_errors
async def add_captcha(m):
    if not await is_user_admin(m.chat.id, m.from_user.id): return await bot.reply_to(m, "Admins only.")
    args = get_args(m)
    if not args or '|' not in " ".join(args):
        return await bot.reply_to(m, "Usage: /addcaptcha Question | Opt1 | Opt2 | ... | Correct")
    parts = [p.strip() for p in " ".join(args).split('|')]
    if len(parts) < 4:
        return await bot.reply_to(m, "Provide at least two options and a correct answer.")
    question = parts[0]
    correct = parts[-1]
    options = parts[1:-1]
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    err = validate_question(question, options, correct)
    if err:
        return await bot.reply_to(m, err)
    res = add_question(db, question, options, correct)
    if res:
        return await bot.reply_to(m, res)
    await bot.reply_to(m, "Question added.")

@handle_errors
async def del_captcha(m):
    if not await is_user_admin(m.chat.id, m.from_user.id): return await bot.reply_to(m, "Admins only.")
    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Usage: /delcaptcha <number>")
    try:
        index = int(args[0])
    except ValueError:
        return await bot.reply_to(m, "Provide a number.")
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    if not remove_question(db, index):
        return await bot.reply_to(m, "Invalid question number.")
    await bot.reply_to(m, "Question removed.")

@handle_errors
async def captcha_list(m):
    if not await is_user_admin(m.chat.id, m.from_user.id): return await bot.reply_to(m, "Admins only.")
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    questions = get_captcha_questions(db)
    max_tries = db.get('captcha_max_tries', 1)
    enabled = db.get('captcha_enabled', False)
    lines = [f"Captcha: {'ON' if enabled else 'OFF'} | Tries: {max_tries} | Timeout: 3 min"]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q['q']} | Options: {', '.join(q['opts'])} | Correct: {q['ans']}")
    if not questions:
        lines.append("No questions set.")
    await bot.reply_to(m, "\n".join(lines))

@handle_errors
async def captcha_tries(m):
    if not await is_user_admin(m.chat.id, m.from_user.id): return await bot.reply_to(m, "Admins only.")
    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Usage: /captchatries <n>")
    try:
        n = int(args[0])
        if n < 1:
            raise ValueError()
    except ValueError:
        return await bot.reply_to(m, "Max tries must be a number >= 1.")
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    db.set('captcha_max_tries', n)
    await bot.reply_to(m, f"Max tries set to {n}.")
