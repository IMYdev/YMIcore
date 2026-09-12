from info import bot
from telebot.util import user_link
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton)
from telebot.formatting import hbold, hcode, format_text, hspoiler
from telebot.util import user_link
from core.utils import (handle_errors, is_user_admin, get_target_user)

demoting_params = {
    'can_change_info': False, 'can_post_messages': False, 'can_edit_messages': False,
    'can_delete_messages': False, 'can_invite_users': False, 'can_restrict_members': False,
    'can_pin_messages': False, 'can_promote_members': False, 'is_anonymous': False,
    'can_manage_chat': False, 'can_manage_video_chats': False, 'can_manage_voice_chats': False,
    'can_manage_topics': False, 'can_post_stories': False, 'can_edit_stories': False,
    'can_delete_stories': False
}

promoting_params = {
    'can_change_info': False, 'can_post_messages': True, 'can_edit_messages': False,
    'can_delete_messages': True, 'can_invite_users': True, 'can_restrict_members': True,
    'can_pin_messages': True, 'can_promote_members': False, 'is_anonymous': False,
    'can_manage_chat': False, 'can_manage_video_chats': True, 'can_manage_voice_chats': True,
    'can_manage_topics': False, 'can_post_stories': False, 'can_edit_stories': False,
    'can_delete_stories': False
}

help_categories = {
    "General": """
    *General Commands:*
    - `/info`: Displays user information.
    - `/start`: Starts the bot.
    - `/wallpaper`: Sends a wallpaper.
    - `/animewall`: Sends an anime wallpaper.
    - `/sauce`: Reverse search anime from image.
    - `/music`: Music search.
    - `/spoiler`: Resends message with spoiler.
    - `/notes`: Lists saved notes.
    """,
    "Admin": """
    *Admin Commands:*
    - `/purge`: Delete messages.
    - `/filter [keyword]`: Set automatic response.
    - `/filters`: List active filters.
    - `/stop [keyword]`: Remove filter.
    - `/add [note]`: Save a note.
    - `/remove [note_ID]`: Delete a note.
    - `/promote`: Promote user to admin.
    - `/demote`: Demote admin to member.
    - `/pin`: Pin a message.
    - `/ban`: Ban a user.
    - `/unban`: Unban a user.
    - `/greeting`: Set welcome message.
    - `/goodbye`: Set farewell message.
    - `/reset`: Reset bot memory.
    - `/modules`: Manage modules.
    - `/blockset`: Blacklist sticker set.
    - `/blocklist`: List blacklisted sets.
    - `/setcaptcha`: Set captcha question.
    - `/captcha`: Toggle captcha feature.
    """
}

@handle_errors
async def promote(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to promote.")

    try:
        reply_status = await bot.get_chat_member(m.chat.id, target_user.id)
        if reply_status.status in ['administrator', 'creator']:
            return await bot.reply_to(m, f"{target_user.first_name} is already an admin.")
        
        await bot.promote_chat_member(m.chat.id, target_user.id, **promoting_params)
        
        args = m.text.split(None, 1)
        if len(args) > 1:
            await bot.set_chat_administrator_custom_title(m.chat.id, target_user.id, args[1])
            
        await bot.reply_to(m, f"Promoted {target_user.first_name} to admin successfully.")
    except Exception as e:
        if "not enough rights" in str(e).lower():
            await bot.reply_to(m, "I don't have enough rights to promote.")
        else:
            raise e

@handle_errors
async def demote(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to demote.")

    try:
        reply_status = await bot.get_chat_member(m.chat.id, target_user.id)
        if reply_status.status not in ['administrator', 'creator']:
            return await bot.reply_to(m, f"{target_user.first_name} is already a regular member.")
        
        await bot.promote_chat_member(m.chat.id, target_user.id, **demoting_params)
        await bot.reply_to(m, f"Demoted {target_user.first_name} to regular member.")
    except Exception as e:
        if "not enough rights" in str(e).lower():
            await bot.reply_to(m, "I don't have enough rights to demote.")
        elif "CHAT_ADMIN_REQUIRED" in str(e):
             await bot.reply_to(m, "Cannot demote admins not promoted by me.")
        else:
            raise e

@handle_errors
async def ban(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to ban.")

    await bot.ban_chat_member(m.chat.id, target_user.id)
    await bot.reply_to(m, f"Banned {target_user.first_name} from the chat.")

@handle_errors
async def unban(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to unban.")

    await bot.unban_chat_member(m.chat.id, target_user.id)
    await bot.reply_to(m, f"Unbanned {target_user.first_name}.")

@handle_errors
async def pin(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to pin it.")

    await bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)


@handle_errors
async def user_info(m):
    target = await get_target_user(m) or m.from_user

    info = format_text(
        f"{hbold('User Info')}",
        f"{hbold('Name:')} {target.first_name}",
        f"{hbold('ID:')} {hcode(str(target.id))}",
        f"{hbold('Username:')} @{target.username if target.username else 'N/A'}",
        f"{hbold('Link:')} {user_link(target)}"
    )

    try:
        photos = await bot.get_user_profile_photos(target.id, limit=1)
        if photos.total_count > 0:
            await bot.send_photo(m.chat.id, photos.photos[0][-1].file_id, caption=info, parse_mode="HTML")
        else:
            await bot.reply_to(m, info, parse_mode="HTML")
    except Exception:
        await bot.reply_to(m, info, parse_mode="HTML")


@handle_errors
async def group_id(m):
    await bot.reply_to(m, f"Chat ID: {hcode(str(m.chat.id))}", parse_mode="HTML")



@handle_errors
async def help_command(m):
    markup = InlineKeyboardMarkup()
    buttons = [
        InlineKeyboardButton("General", callback_data="help_General"),
        InlineKeyboardButton("Admin", callback_data="help_Admin"),
    ]
    markup.add(*buttons)
    await bot.reply_to(m, "Please select a category for help:", reply_markup=markup)

@handle_errors
async def start(m):
    await bot.reply_to(m, "Hello! I am YMIcore bot. Use /help to see what I can do.")

@handle_errors
async def spoiler(m):
    if not m.reply_to_message or not m.reply_to_message.text:
        return await bot.reply_to(m, "Reply to a text message to make it a spoiler.")
    
    await bot.delete_message(m.chat.id, m.message_id)
    await bot.send_message(m.chat.id, hspoiler(m.reply_to_message.text), parse_mode="HTML")
