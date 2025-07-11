from info import bot
from telebot.util import user_link
import asyncio
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

# Categorized help text
help_categories = {
    "General": """
    *General Commands:*

    - `/info`: Displays your or some other user's information.
    - `/start`: Starts the bot and provides a welcome message.
    - `/wallpaper`: Sends a wallpaper based on predefined sources.
    - `/ask [question]`: Ask a question and get an AI-generated response.
    - `/animewall`: Sends an anime-themed wallpaper.
    - `/sauce`: Reverse search engine for anime, give a picture and get the name of the anime.
    - `/imagine [prompt]`: Generate an AI image based on your prompt.
    """,
    
    "Admin": """
    *Admin Commands:*

    - `/purge`: Deletes messages starting from the one you replied to up to the message containing the `/purge` command.
    - `/nuke`: Deletes all messages in the chat.
    - `/filter [keyword]`: Set a filter keyword for automatic responses when triggered.
    - `/filters`: Lists all active filters in the chat.
    - `/stop [keyword]`: Removes a specific filter by keyword.
    - `/add [note]`: Adds a custom note to be recalled later.
    - `/notes`: Displays a list of saved notes.
    - `/remove [note_ID]`: Removes a specific note by ID.
    - `/promote [user]`: Promotes a user to admin status.
    - `/demote [user]`: Demotes a user from admin status.
    - `/pin`: Pins the message you reply to.
    - `/ban [user]`: Bans a user from the chat.
    - `/unban [user]`: Unbans a user from the chat.
    - `/mute [user]`: Mutes a user in the chat.
    - `/unmute [user]`: Unmutes a user in the chat.
    - `/kickme`: Kicks yourself from the chat.
    - `/reset`: Resets the bot's memory.
    """
}


async def promote(m):
    try:
        if m.reply_to_message:
            member_status, reply_status = await asyncio.gather(
                bot.get_chat_member(m.chat.id, m.from_user.id),
                bot.get_chat_member(m.chat.id, m.reply_to_message.from_user.id)
            )
            if member_status.status == "member":
                await bot.reply_to(m, "You lack admin rights.")
                return
            username = reply_status.user.username or "subject"
            if reply_status.status == "member":
                await bot.promote_chat_member(m.chat.id, m.reply_to_message.from_user.id, **promoting_params)
                await bot.reply_to(m, f"User @{username} promoted.")
                parts = m.text.split(" ", 1)
                if len(parts) > 1:
                    title = parts[1]
                    if title:
                        await bot.set_chat_administrator_custom_title(m.chat.id, m.reply_to_message.from_user.id, title)
            elif reply_status.status == "kicked":
                await bot.reply_to(m, f"User @{username} is banned. Operation aborted.")
            else:
                await bot.reply_to(m, "User is already an admin.")
        else:
            await bot.reply_to(m, "Reply to a user to promote.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")

async def demote(m):
    try:
        if m.reply_to_message:
            member_status, reply_status = await asyncio.gather(
                bot.get_chat_member(m.chat.id, m.from_user.id),
                bot.get_chat_member(m.chat.id, m.reply_to_message.from_user.id)
            )
            if member_status.status == "member":
                await bot.reply_to(m, "Access denied. Insufficient privileges.")
                return
            username = reply_status.user.username or "subject"
            if reply_status.status == "member":
                await bot.reply_to(m, f"User @{username} is not an administrator.")
            else:
                await bot.promote_chat_member(m.chat.id, m.reply_to_message.from_user.id, **demoting_params)
                await bot.reply_to(m, f"User @{username} demoted to standard user.")
        else:
            await bot.reply_to(m, "Command requires reply to target user's message.")
    except Exception as e:
        if "not enough rights" in str(e):
            await bot.reply_to(m, "Bot lacks permissions to execute command.")
        elif "CHAT_ADMIN_REQUIRED" in str(e):
            await bot.reply_to(m, "Cannot demote user promoted by another entity.")
        else:
            await log_error(bot, e, context_msg=m)
            await bot.reply_to(m, "An error occurred. Please try again later.")

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
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred. Please try again later.")

async def pin(m):
    try:
        if m.reply_to_message:
            rank = (await bot.get_chat_member(m.chat.id, m.from_user.id)).status
            if rank != "member":
                await bot.pin_chat_message(m.chat.id, m.reply_to_message.id)
                await bot.reply_to(m, "Message secured (pinned).")
            else:
                await bot.reply_to(m, "Access denied. Insufficient privileges.")
        else:
            await bot.reply_to(m, "Reply to target message to pin.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred. Please try again later.")

async def ban(m):
    try:
        if m.reply_to_message:
            rank = (await bot.get_chat_member(m.chat.id, m.from_user.id)).status
            username = m.reply_to_message.from_user.username or "subject"
            if rank != "member":
                await bot.ban_chat_member(m.chat.id, m.reply_to_message.from_user.id)
                await bot.reply_to(m, f"User @{username} has been banned.")
            else:
                await bot.reply_to(m, "Access denied. Insufficient privileges.")
        else:
            await bot.reply_to(m, "Reply to target user’s message to ban.")
    except Exception as e:
        if "bot can't ban itself" in str(e):
            await bot.reply_to(m, "Cannot self-terminate.")
        else:
            await log_error(bot, e, context_msg=m)
            await bot.reply_to(m, "An error occurred. Please try again later.")

async def unban(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            await bot.reply_to(m, "Specify user identifier to unban.")
            return
        user_to_unban = parts[1]
        try:
            user_id = int(user_to_unban)
        except ValueError:
            user_id = user_to_unban.lstrip("@")

        await bot.unban_chat_member(m.chat.id, user_id)
        await bot.reply_to(m, f"User {user_to_unban} has been reinstated.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred. Please try again later.")


async def help_command(m):
    args = m.text.split()
    if len(args) > 1 and args[1] in help_categories:
        await bot.reply_to(m, help_categories[args[1]], parse_mode="Markdown")
    else:
        general_help = "\n".join([f"- {cat}" for cat in help_categories.keys()])
        await bot.reply_to(m, f"Available help modules:\n{general_help}\nUse /help [module] for details.")
async def start(m):
    await bot.reply_to(m, "Welcome. Use /help for assistance and further understanding of the bot's functions.")
