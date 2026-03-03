from info import bot
from core.imysdb import IMYDB
from core.utils import handle_errors, is_user_admin, get_media_info, get_args
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
    db.set('captcha_q', question)
    db.set('captcha_opts', options)
    db.set('captcha_ans', correct)
    db.set('captcha_max_tries', max_attempts)
    db.set('captcha_enabled', True)
    
    await bot.reply_to(m, f"Captcha enabled!\n{hbold(f'Attempts allowed: {max_attempts}')}", parse_mode="HTML")

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
    chat_id_raw = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id_raw}_greetings.json')

    if new.status == "member" and old.status in ["left", "kicked", "restricted"]:
        if db.get('captcha_enabled', False):
            await bot.restrict_chat_member(m.chat.id, new.user.id, permissions=ChatPermissions(can_send_messages=False))
            
            attempts = db.get('user_attempts', {})
            attempts[str(new.user.id)] = 0
            db.set('user_attempts', attempts)

            markup = InlineKeyboardMarkup()
            for opt in db.get('captcha_opts', ["Yes", "No"]):
                markup.add(InlineKeyboardButton(opt, callback_data=f"v_cap:{opt}:{new.user.id}"))
            
            await bot.send_message(m.chat.id, f"Welcome {new.user.first_name}! Solve to chat:\n\n{hbold(f'{db.get('captcha_q', 'Are you human?')}')}", reply_markup=markup, parse_mode="HTML")
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
            await bot.send_media_group(chat_id, [getattr(bot, f"send_{m_type}")(chat_id, m_id, caption=personalized)])
            send_func = getattr(bot, f"send_{m_type}")
            await send_func(chat_id, m_id, caption=personalized)
    else:
        await bot.send_message(chat_id, personalized)

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
