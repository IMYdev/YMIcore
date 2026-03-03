from info import bot
from core.imysdb import IMYDB
from core.utils import log_error
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions)
from telebot.formatting import (hbold, hitalic)
import re

def validate_template(template):
    allowed = {"firstname", "lastname", "username"}
    found = set(re.findall(r"{(.*?)}", template))
    return found.issubset(allowed)

async def is_admin(chat_id, user_id):
    user = await bot.get_chat_member(chat_id, user_id)
    return user.status in ["creator", "administrator"]

async def set_captcha(m):
    if not await is_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    try:
        args = m.text.split(' ', 1)
        if len(args) < 2 or '|' not in args[1]:
            await bot.reply_to(m, f"Usage: {hitalic("/setcaptcha Question | Opt1 | Opt2 | CorrectAnswer | 1")}", parse_mode="HTML")
            return

        parts = [p.strip() for p in args[1].split('|')]
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
        
        await bot.reply_to(m, f"Captcha enabled!\n{hbold(f"Attempts allowed: {max_attempts}")}", parse_mode="HTML")
    except Exception as e:
        await log_error(bot, e, m)

async def captcha_toggle(m):
    if not await is_admin(m.chat.id, m.from_user.id): return
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
            
            await bot.send_message(m.chat.id, f"Welcome {new.user.first_name}! Solve to chat:\n\n{hbold(f"{db.get('captcha_q', 'Are you human?')}")}", reply_markup=markup, parse_mode="HTML")
            return
        
        await send_standard_greeting(m, db, new)

async def send_standard_greeting(m, db, new):
    greetings = db.data
    greeting_msg = greetings.get('greeting', "Hello {firstname}, welcome!")
    personalized = greeting_msg.format(
        username=f"@{new.user.username}" if new.user.username else 'there',
        firstname=new.user.first_name,
        lastname=new.user.last_name or ''
    )
    m_type, m_id = greetings.get('greeting_media_type'), greetings.get('greeting_media_id')
    if m_type and m_id:
        if m_type == 'photo': await bot.send_photo(m.chat.id, m_id, caption=personalized)
        elif m_type == 'video': await bot.send_video(m.chat.id, m_id, caption=personalized)
        elif m_type == 'audio': await bot.send_audio(m.chat.id, m_id, caption=personalized)
        elif m_type == 'sticker': 
            await bot.send_sticker(m.chat.id, m_id)
            await bot.send_message(m.chat.id, personalized)
    else:
        await bot.send_message(m.chat.id, personalized)

async def set_greeting(m):
    try:
        necessary_evil = await bot.get_chat_member(m.chat.id, m.from_user.id)
        rank = necessary_evil.status
        if rank != "member":
            chat_id = str(m.chat.id).lstrip('-')
            db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
            if m.reply_to_message:
                if m.reply_to_message.photo:
                    media_type = 'photo'
                    media_id = m.reply_to_message.photo[-1].file_id
                elif m.reply_to_message.video:
                    media_type = 'video'
                    media_id = m.reply_to_message.video.file_id
                elif m.reply_to_message.audio:
                    media_type = 'audio'
                    media_id = m.reply_to_message.audio.file_id
                elif m.reply_to_message.sticker:
                    media_type = 'sticker'
                    media_id = m.reply_to_message.sticker.file_id
                else:
                    await bot.reply_to(m, "Reply to a photo, video, audio, or sticker.")
                    return

                greeting_msg = m.text.split(' ', 1)
                greeting_msg = greeting_msg[1] if len(greeting_msg) > 1 else ""
                db.set('greeting_media_type', media_type)
                db.set('greeting_media_id', media_id)
                if not validate_template(greeting_msg):
                    await bot.reply_to(m, "Only {firstname}, {lastname}, and {username} are allowed.")
                    return
                db.set('greeting', greeting_msg)

                await bot.reply_to(m, f"Greeting {media_type} set with caption.")
            else:
                greeting_msg = m.text.split(' ', 1)
                if len(greeting_msg) > 1:
                    greeting_msg = greeting_msg[1]
                else:
                    await bot.reply_to(m, "Give me a greeting message!")
                    return

                if not validate_template(greeting_msg):
                    await bot.reply_to(m, "Only {firstname}, {lastname}, and {username} are allowed.")
                    return
                db.set('greeting', greeting_msg)
                db.set('greeting_media_type', None)
                db.set('greeting_media_id', None)

                await bot.reply_to(m, "Greeting message set.")
        else:
            await bot.reply_to(m, "Admins only.")
    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred")
        await log_error(bot, error, m)


async def set_goodbye(m):
    try:
        necessary_evil = await bot.get_chat_member(m.chat.id, m.from_user.id)
        rank = necessary_evil.status
        if rank != "member":
            chat_id = str(m.chat.id).lstrip('-')
            db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')

            if m.reply_to_message:
                if m.reply_to_message.photo:
                    media_type = 'photo'
                    media_id = m.reply_to_message.photo[-1].file_id
                elif m.reply_to_message.video:
                    media_type = 'video'
                    media_id = m.reply_to_message.video.file_id
                elif m.reply_to_message.audio:
                    media_type = 'audio'
                    media_id = m.reply_to_message.audio.file_id
                elif m.reply_to_message.sticker:
                    media_type = 'sticker'
                    media_id = m.reply_to_message.sticker.file_id
                else:
                    await bot.reply_to(m, "Reply to a photo, video, audio, or sticker.")
                    return

                goodbye_msg = m.text.split(' ', 1)
                goodbye_msg = goodbye_msg[1] if len(goodbye_msg) > 1 else ""
                db.set('goodbye_media_type', media_type)
                db.set('goodbye_media_id', media_id)
                if not validate_template(goodbye_msg):
                    await bot.reply_to(m, "Only {firstname}, {lastname}, and {username} are allowed.")
                    return
                db.set('goodbye', goodbye_msg)

                await bot.reply_to(m, f"Goodbye {media_type} set with caption.")
            else:
                goodbye_msg = m.text.split(' ', 1)
                if len(goodbye_msg) > 1:
                    goodbye_msg = goodbye_msg[1]
                else:
                    await bot.reply_to(m, "Give me a goodbye message!")
                    return

                if not validate_template(goodbye_msg):
                    await bot.reply_to(m, "Only {firstname}, {lastname}, and {username} are allowed.")
                    return
                db.set('goodbye', goodbye_msg)
                db.set('goodbye_media_type', None)
                db.set('goodbye_media_id', None)

                await bot.reply_to(m, "Goodbye message set.")
        else:
            await bot.reply_to(m, "Admins only.")
    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)


async def bye(m):
    old = m.old_chat_member
    new = m.new_chat_member
    
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    greetings = db.data
    default_goodbye = "Goodbye {firstname}, we will miss you!"
    
    if new.status in ["left", "kicked"] and old.status == "member":
        goodbye_msg = greetings.get('goodbye', default_goodbye)
        
        personalized_goodbye = goodbye_msg.format(
            username=f"@{new.user.username}" if new.user.username else 'there',
            firstname=new.user.first_name,
            lastname=new.user.last_name if new.user.last_name else ''
        )

        if greetings.get('goodbye_media_type') and greetings.get('goodbye_media_id'):
            media_type = greetings['goodbye_media_type']
            media_id = greetings['goodbye_media_id']

            if media_type == 'photo':
                await bot.send_photo(m.chat.id, media_id, caption=personalized_goodbye)
            elif media_type == 'video':
                await bot.send_video(m.chat.id, media_id, caption=personalized_goodbye)
            elif media_type == 'audio':
                await bot.send_audio(m.chat.id, media_id, caption=personalized_goodbye)
            elif media_type == 'sticker':
                await bot.send_sticker(m.chat.id, media_id)
                await bot.send_message(m.chat.id, personalized_goodbye)
        else:
            await bot.send_message(m.chat.id, personalized_goodbye)