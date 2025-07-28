from info import bot
from core.imysdbMongo import IMYDB
from core.utils import log_error
import re

def validate_template(template):
    allowed = {"firstname", "lastname", "username"}
    found = set(re.findall(r"{(.*?)}", template))
    return found.issubset(allowed)


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
    except Exception as e:
        await bot.send_message(m.chat.id, "An error occurred")
        log_error(bot, e, m)


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
    except Exception as e:
        await bot.send_message(m.chat.id, "An error occurred.")
        print(e)

async def hello(m):
    old = m.old_chat_member
    new = m.new_chat_member
    
    chat_id = str(m.chat.id).lstrip('-')
    db = IMYDB(f'runtime/greetings/{chat_id}_greetings.json')
    greetings = db.data
    default_greeting = "Hello {firstname}, welcome to the chat!"

    if new.status == "member" and old.status in ["left", "kicked", "restricted"]:
        greeting_msg = greetings.get('greeting', default_greeting)

        personalized_greeting = greeting_msg.format(
            username=f"@{new.user.username}" if new.user.username else 'there',
            firstname=new.user.first_name,
            lastname=new.user.last_name if new.user.last_name else ''
        )

        media_type = greetings.get('greeting_media_type')
        media_id = greetings.get('greeting_media_id')

        if media_type and media_id:
            if media_type == 'photo':
                await bot.send_photo(m.chat.id, media_id, caption=personalized_greeting)
            elif media_type == 'video':
                await bot.send_video(m.chat.id, media_id, caption=personalized_greeting)
            elif media_type == 'audio':
                await bot.send_audio(m.chat.id, media_id, caption=personalized_greeting)
            elif media_type == 'sticker':
                await bot.send_sticker(m.chat.id, media_id)
                await bot.send_message(m.chat.id, personalized_greeting)
        else:
            await bot.send_message(m.chat.id, personalized_greeting)


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