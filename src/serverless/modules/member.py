from info import bot
from telebot.util import user_link
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.formatting import hspoiler
import asyncio
import time
from core.utils import log_error

demoting_params = {
    'can_change_info': False,
    'can_post_messages': False,
    'can_edit_messages': False,
    'can_delete_messages': False,
    'can_invite_users': False,
    'can_restrict_members': False,
    'can_pin_messages': False,
    'can_promote_members': False,
    'is_anonymous': False,
    'can_manage_chat': False,
    'can_manage_video_chats': False,
    'can_manage_voice_chats': False,
    'can_manage_topics': False,
    'can_post_stories': False,
    'can_edit_stories': False,
    'can_delete_stories': False
}

promoting_params = {
    'can_change_info': False,
    'can_post_messages': True,
    'can_edit_messages': False,
    'can_delete_messages': True,
    'can_invite_users': True,
    'can_restrict_members': True,
    'can_pin_messages': True,
    'can_promote_members': False,
    'is_anonymous': False,
    'can_manage_chat': False,
    'can_manage_video_chats': True,
    'can_manage_voice_chats': True,
    'can_manage_topics': False,
    'can_post_stories': False,
    'can_edit_stories': False,
    'can_delete_stories': False
}

help_categories = {
    "General": """
    *General Commands:*

    - `/info`: Displays your or some other user's information.
    - `/start`: Starts the bot and provides a welcome message.
    - `/wallpaper`: Sends a wallpaper based on predefined sources.
    - `/ask [question]`: Ask a question and get an AI-generated response.
    - `/animewall`: Sends an anime-themed wallpaper.
    - `/sauce`: Reverse search engine for anime, give a picture and get the name of the anime.
    - `/music`: Music search and fetching.
    - `/spoiler`: Resends message with spoiler added.
    - `/notes`: Displays a list of saved notes.
    - `/runtime`: Test robot's liveness.
    """,
    
    "Admin": """
    *Admin Commands:*

    - `/purge`: Deletes messages starting from the one you replied to up to the message containing the `/purge` command.
    - `/filter [keyword]`: Set a filter keyword for automatic responses when triggered.
    - `/filters`: Lists all active filters in the chat.
    - `/stop [keyword]`: Removes a specific filter by keyword.
    - `/add [note]`: Adds a custom note to be recalled later.
    - `/remove [note_ID]`: Removes a specific note by ID.
    - `/promote [user]`: Promotes a user to admin status.
    - `/greeting [message]`: Sets a greeting message for new members, reply to media to attach it.
    - `/goodbye [message]`: Sets a farewell message for leaving members, reply to media to attach it.
    - `/demote [user]`: Demotes a user from admin status.
    - `/pin`: Pins the message you reply to.
    - `/ban [user]`: Bans a user from the chat.
    - `/unban [user]`: Unbans a user from the chat.
    - `/reset`: Resets the bot's memory.
    - `/modules`: Manages activation of different modules and their subcommands.
    - `/blockset`: Reply to a sticker to blacklist its set in the chat.
    - `/unblockset [set_name]`: Removes a sticker set from the blacklist.
    - `/blocklist`: Shows all currently blacklisted sticker sets.
    """
}

START_TIME = time.time()

def format_time(seconds):
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)                                                                     return f"{days}d {hrs}h {mins}m {secs}s"

async def promote(m):
    try:
        target_user = m.reply_to_message
        if m.reply_to_message != None:
            member_status, reply_status = await asyncio.gather(
                bot.get_chat_member(m.chat.id, m.from_user.id),
                bot.get_chat_member(m.chat.id, target_user.from_user.id)
            )
            if member_status.status == "member":
                await bot.reply_to(m, "Admins only.")
                return
            else:
                username = reply_status.user.username if reply_status.user.username else reply_status.user.first_name
                if reply_status.status == 'member':
                    await asyncio.gather(
                        bot.promote_chat_member(m.chat.id, target_user.from_user.id, **promoting_params),
                        bot.reply_to(m, f"Promoted @{username} to admin successfully.")
                    )
                    message_parts = m.text.lower().split(" ", 1)
                    if len(message_parts) > 1:
                        title = message_parts[1]
                        if title:
                            await bot.set_chat_administrator_custom_title(m.chat.id, target_user.from_user.id, title)
                        else:
                            pass
                    else:
                        pass
                elif reply_status.status == "kicked":
                    await bot.reply_to(m, f"@{username} is banned. Cannot promote.")
                else:
                    await bot.reply_to(m, f"@{username} is already an admin.")
        else:
            await bot.reply_to(m, "Reply to a message to promote its sender.")
    except Exception as error:
        if "not enough rights" in str(error):
            await bot.reply_to(m, "Not enough rights to promote.")
        else:
            await log_error(bot, error, m)
            await bot.reply_to(m, "An error occurred.")

async def demote(m):
    try:
        if m.reply_to_message != None:
            member_status, reply_status = await asyncio.gather(
                bot.get_chat_member(m.chat.id, m.from_user.id),
                bot.get_chat_member(m.chat.id, m.reply_to_message.from_user.id)
            )
            username = reply_status.user.username if reply_status.user.username else reply_status.user.first_name
            if member_status.status == "member":
                await bot.reply_to(m, "Admins only.")
                return
            if reply_status.status == "member":
                await bot.reply_to(m, f"@{username} is already a regular member.")
            else:
                await bot.promote_chat_member(m.chat.id, m.reply_to_message.from_user.id, **demoting_params),
                await bot.reply_to(m, f"Demoted @{username} to regular member.")

        else:
            await bot.reply_to(m, "Reply to a message to demote its sender.")
    except Exception as error:
        if "not enough rights" in str(error):
            await bot.reply_to(m, "Not enough rights.")
            return
        if "CHAT_ADMIN_REQUIRED" in str(error):
            await bot.reply_to(m, "Cannot demote admins not promoted by me.")
            return
        if "can't remove chat owner" in str(error):
            await bot.reply_to(m, "Cannot demote the creator of the group!")
            return
        if "USER_ID_INVALID" in str(error):
            await bot.reply_to(m, "Cannot demote self.")
            return
        else:
            await log_error(bot, error, m)
            await bot.reply_to(m, "An error occurred.")

async def user_info(m):
    try:
        user = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        user_id = user.id
        permalink = user_link(user)
        user_info = await bot.get_chat_member(m.chat.id, user_id)
        user = user_info.user
        get_bio = await bot.get_chat(user_id)
        
        id = user.id
        first_name = user.first_name or "N/A"
        last_name = user.last_name or "N/A"
        username = f"@{user.username}" if user.username else "N/A"
        status = user_info.status
        bio_text = get_bio.bio or "N/A"

        caption = (
            f"-----\nID: {id}\n"
            f"First name: {first_name}\n"
            f"Last name: {last_name}\n"
            f"Username: {username}\n"
            f"Profile: {permalink}\n"
            f"Bio: {bio_text}\n"
            f"Status: {status}\n-----"
        )

        photos = await bot.get_user_profile_photos(user_id)
        if photos.photos:
            photo = photos.photos[0][0].file_id
            await bot.send_photo(m.chat.id, photo, caption=caption, parse_mode='HTML', reply_to_message_id=m.message_id)
        else:
            await bot.send_message(m.chat.id, caption + "\nNo profile image available.", parse_mode='HTML')
    except Exception as error:
        await log_error(bot, error, m)
        await bot.reply_to(m, "An error occurred.")

async def pin(m):
    try:
        if m.reply_to_message:
            rank = (await bot.get_chat_member(m.chat.id, m.from_user.id)).status
            if rank != "member":
                await bot.pin_chat_message(m.chat.id, m.reply_to_message.id)
                await bot.reply_to(m, "Message pinned.")
            else:
                await bot.reply_to(m, "Access denied. Insufficient privileges.")
        else:
            await bot.reply_to(m, "Reply to target message to pin.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

async def ban(m):
    try:
        if m.reply_to_message != None:
            necessary_evil = await bot.get_chat_member(m.chat.id, m.from_user.id)
            rank = necessary_evil.status
            username = m.reply_to_message.from_user.username
            firstname = m.reply_to_message.from_user.first_name
            if rank != "member":   
                ban = await bot.ban_chat_member(m.chat.id, m.reply_to_message.from_user.id)
                if ban:
                    await bot.reply_to(m, f"Banned @{username if username else firstname}")
            else:
                await bot.reply_to(m, "Admins only.")
        else:
            await bot.reply_to(m, "Reply to a message to ban its sender.")
    except Exception as error:
        if "can't restrict self" in str(error):
            await bot.reply_to(m, "Cannot ban self.")
        if "can't remove chat owner" in str(error):
            await bot.reply_to(m, "Cannot ban the creator of the group.")
        if "user is an administrator" in str(error):
            await bot.reply_to(m, "Cannot ban an admin.")
        else:
            await bot.reply_to(m, "An error occurred.")
            await log_error(bot, error, m)

async def unban(m):
    try:
        if m.reply_to_message != None:
            target_user = m.reply_to_message.from_user
            target_user_status = await bot.get_chat_member(m.chat.id, target_user.id)
            bot_id = await bot.get_me()
            bot_id = bot_id.id
            if target_user.id == bot_id:
                await bot.reply_to(m, "Very funny...")
                return
            if target_user_status != "kicked":
                await bot.reply_to(m, "This user is not banned.")
                return
            username = target_user.username if target_user.username else target_user.first_name
            initiator = await bot.get_chat_member(m.chat.id, m.from_user.id)
            rank = initiator.status
            if rank != "member":
                unban = await bot.unban_chat_member(m.chat.id, m.reply_to_message.from_user.id, True)
                if unban:
                    await bot.reply_to(m, f"Unbanned @{username}.")
            else:
                await bot.reply_to(m, "Admins only.")
        else:
            await bot.reply_to(m, "Reply to a message to unban its sender.")
    except Exception as error:
        await log_error(bot, error, m)


async def help_command(m, category="General"):
    markup = InlineKeyboardMarkup()
    buttons = [
        InlineKeyboardButton("General", callback_data="help_General"),
        InlineKeyboardButton("Admin", callback_data="help_Admin"),
    ]
    markup.add(*buttons)

    await bot.reply_to(m, help_categories[category], parse_mode="Markdown", reply_markup=markup)

async def start(m):
    await bot.reply_to(m, "Welcome. Use /help for assistance and further understanding of the bot's functions.")

async def runtime(m):
    running_time = time.time() - START_TIME                                                         await bot.reply_to(m, f"Bot runtime:\n⏱ {format_time(running_time)}")

async def group_id(m):
    try:
        chat_id = m.chat.id
        if chat_id < 0:
            chat_id_str = str(chat_id).lstrip('-')
            await bot.reply_to(m, f"Group ID: `{chat_id_str}`", parse_mode='Markdown')
    except Exception as error:
        await log_error(bot, error, m)

async def is_user_admin(chat_id, user_id):
    chat_admins = await bot.get_chat_administrators(chat_id)
    for admin in chat_admins:

        if admin.user.id == user_id:
            return True

    return False

async def spoiler(m):
    try:
        delete_og = True

        if not is_user_admin:
            delete_og = False

        user = await bot.get_chat_member(m.chat.id, m.from_user.id)
        user_can_delete = user.can_delete_messages
        original_message = m.reply_to_message
        self = await bot.get_me()
        self = await bot.get_chat_member(m.chat.id, self.id)

        if not user_can_delete and user.status != "creator":
            delete_og = False

        if not self.can_delete_messages:
            delete_og = False

        if delete_og:
            await bot.delete_message(m.chat.id, original_message.id)

        spoiler_text = None
        
        if not m.reply_to_message:
            await bot.reply_to(m, "Reply to a message to apply spoiler.")
            return

        if m.reply_to_message.photo:
            media = m.reply_to_message.photo[0]
            media = media.file_id

            if m.reply_to_message.caption:
                spoiler_text = hspoiler(m.reply_to_message.caption)
        
            await bot.send_photo(m.chat.id, photo=media, has_spoiler=True, reply_to_message_id=m.id, caption=spoiler_text, parse_mode='HTML')
            return

        elif m.reply_to_message.video:
            media = m.reply_to_message.video
            media = media.file_id

            if m.reply_to_message.caption:
                spoiler_text = hspoiler(m.reply_to_message.caption)

            await bot.send_video(m.chat.id, video=media, has_spoiler=True, reply_to_message_id=m.id, caption=spoiler_text, parse_mode='HTML')
            return

        elif m.reply_to_message.text:
            spoiler_text = hspoiler(m.reply_to_message.text)
            await bot.reply_to(m, spoiler_text, parse_mode="HTML")

    except Exception as error:
        await bot.send_message(m.chat.id, "An error occurred.")
        await log_error(bot, error, m)
