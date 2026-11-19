from info import bot
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions)
from telebot.formatting import hbold, hcode, format_text, hspoiler
from telebot.util import user_link
from core.utils import (handle_errors, is_privileged, get_target_user, get_args, topic_kwargs, mute_permissions, open_permissions)
from core.storage import warn_db, warn_counts, add_warn, clear_warns
from core.activity import log_event

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

WARN_LIMIT = 3


help_categories = {
    "General": """
    *General Commands:*
    - `/info`: Displays user information.
    - `/start`: Starts the bot.
    - `/id`: Shows chat ID.
    - `/wallpaper`: Sends a wallpaper.
    - `/animewall`: Sends an anime wallpaper.
    - `/sauce`: Reverse search anime from image.
    - `/spoiler`: Resends message with spoiler.
    - `/notes`: Lists saved notes.
    """,
    "Admin": """
    *Admin Commands:*
    - `/purge`: Delete messages.
    - `/filter [keyword]`: Set automatic response.
    - `/filist`: List active filters.
    - `/stop [keyword]`: Remove filter.
    - `/add [note]`: Save a note.
    - `/remove [note_ID]`: Delete a note.
    - `/promote`: Promote user to admin.
    - `/demote`: Demote admin to member.
    - `/pin`: Pin a message.
    - `/ban`: Ban a user.
    - `/unban`: Unban a user.
    - `/warn [reason]`: Warn a user (auto-kicks at 3 warns).
    - `/warnings`: Show warns for a user.
    - `/unwarn [all]`: Remove latest warn, or all with `all`.
    - `/mute [10m|1h|1d] [reason]`: Mute a user (no duration = indefinite).
    - `/unmute`: Unmute a user.
    - `/kick [reason]`: Kick a user (ban + immediate unban).
    - `/greeting`: Set welcome message.
    - `/goodbye`: Set farewell message.
    - `/modules`: Manage modules.
    - `/blockset`: Blacklist sticker set.
    - `/blocklist`: List blacklisted sets.
    - `/unblockset`: Remove sticker set from blacklist.
    - `/blockword <word>`: Add a word/phrase to blocklist.
    - `/unblockword <word>`: Remove a word/phrase from blocklist.
    - `/blockwords`: List all blocked words.
    - `/setcaptcha`: Replace captcha question (one question per set).
    - `/addcaptcha`: Add a captcha question.
    - `/delcaptcha <n>`: Remove a captcha question.
    - `/captchalist`: List captcha questions and settings.
    - `/captchatries <n>`: Set max wrong attempts.
    - `/captcha`: Toggle captcha feature.
    - `/panel`: Open the settings web panel.
    - `/devgroup`: Developer group commands.
    - `/broadcast [users|groups] <message>`: Send an update to everyone (owner).
    - `/bcast_list`: List recent broadcasts (owner).
    - `/bcast_delete <id>`: Delete a broadcast from every chat (owner).
    - `/unsub`: Stop receiving broadcasts.
    - `/sub`: Resume receiving broadcasts.
    """
}


@handle_errors
async def promote(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to promote.")
    
    if not await is_moderatable(m.chat.id, target_user.id):
        return await bot.reply_to(m, f"Cannot promote {target_user.first_name} - they are an admin/creator.")
    
    try:
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
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to demote.")
    
    if not await is_moderatable(m.chat.id, target_user.id, require_admin=True):
        return await bot.reply_to(m, f"Cannot demote {target_user.first_name} - they are a regular member or creator.")
    
    try:
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
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to ban.")
    
    if not await is_moderatable(m.chat.id, target_user.id):
        return await bot.reply_to(m, f"Cannot ban {target_user.first_name} - they are an admin/creator.")
    
    await bot.ban_chat_member(m.chat.id, target_user.id)
    await bot.reply_to(m, f"Banned {target_user.first_name} from the chat.")


@handle_errors
async def unban(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to unban.")
    
    await bot.unban_chat_member(m.chat.id, target_user.id)
    from modules.captcha import reset_kicks
    reset_kicks(m.chat.id, target_user.id)
    await bot.reply_to(m, f"Unbanned {target_user.first_name}.")


@handle_errors
async def pin(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
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
            await bot.send_photo(m.chat.id, photos.photos[0][-1].file_id, caption=info, parse_mode="HTML", **topic_kwargs(m))
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
    if m.chat.type == "private" and get_args(m) and get_args(m)[0].startswith("cap_"):
        from modules.captcha import handle_start_payload
        await handle_start_payload(m)
        return
    await bot.reply_to(m, "Hello! I am YMIcore bot. Use /help to see what I can do.")


@handle_errors
async def spoiler(m):
    if not m.reply_to_message or not m.reply_to_message.text:
        return await bot.reply_to(m, "Reply to a text message to make it a spoiler.")
    
    await bot.delete_message(m.chat.id, m.message_id)
    await bot.send_message(m.chat.id, hspoiler(m.reply_to_message.text), parse_mode="HTML", **topic_kwargs(m))


@handle_errors
async def warn(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to warn.")
    
    if not await is_moderatable(m.chat.id, target_user.id):
        return await bot.reply_to(m, f"Cannot warn {target_user.first_name} - they are an admin/creator.")
    
    reason = m.text.split(None, 1)[1] if len(m.text.split(None, 1)) > 1 else "No reason provided"
    if len(reason) > 500:
        return await bot.reply_to(m, "Reason too long (max 500 chars).")
    
    # Add the warn and get updated counts
    result = add_warn(m.chat.id, target_user.id, reason, m.from_user.id)
    current_count = result[str(target_user.id)]["count"]
    
    # Check if we need to kick at the warning limit
    if current_count >= WARN_LIMIT:
        try:
            await bot.ban_chat_member(m.chat.id, target_user.id)
            await bot.unban_chat_member(m.chat.id, target_user.id, only_if_banned=True)
            # Reset kick count after successful kick
            from modules.captcha import reset_kicks
            reset_kicks(m.chat.id, target_user.id)
        except Exception as e:
            await bot.reply_to(m, f"Warn added but kick failed: {e}")
    
    await bot.reply_to(m, f"Warned {target_user.first_name}. Total warns: {current_count}")
    log_event("warn", chat_id=m.chat.id, user_id=m.from_user.id, detail=f"reason: {reason}")


@handle_errors
async def warnings(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to view warns.")
    
    warn_data = warn_counts(m.chat.id)
    user_warns = warn_data.get(str(target_user.id), {"count": 0, "latest": None})
    
    if user_warns['count'] == 0:
        await bot.reply_to(m, f"{target_user.first_name} has no warns.")
    else:
        latest = user_warns['latest']
        if latest:
            await bot.reply_to(m, f"{target_user.first_name} has {user_warns['count']} warns. Latest: {latest['reason']} (by admin)")
        else:
            await bot.reply_to(m, f"{target_user.first_name} has {user_warns['count']} warns.")


@handle_errors
async def unwarn(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    args = m.text.split(None, 2)
    clear_all = len(args) > 1 and args[1].lower() == "all"
    
    if m.reply_to_message:
        target_user = m.reply_to_message.from_user
        clear_warns(m.chat.id, target_user.id)
        await bot.reply_to(m, f"Unwarned {target_user.first_name}.")
    else:
        target_user = await get_target_user(m)
        if not target_user:
            return await bot.reply_to(m, "Reply to a user or provide their ID to unwarn.")
        clear_warns(m.chat.id, target_user.id)
        await bot.reply_to(m, f"Unwarned {target_user.first_name}.")
    
    log_event("unwarn", chat_id=m.chat.id, user_id=m.from_user.id, detail="unwarned")


@handle_errors
async def mute(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    # Parse duration and target
    args = m.text.split(None, 2)
    if len(args) < 2:
        return await bot.reply_to(m, "Usage: /mute [10m|1h|1d] [reason]")
    
    duration_str = args[1]
    reason = args[2] if len(args) > 2 else None
    
    # Parse duration
    duration_seconds = None
    if duration_str.endswith('m'):
        try:
            duration_seconds = int(duration_str[:-1]) * 60
        except ValueError:
            return await bot.reply_to(m, "Invalid mute duration.")
    elif duration_str.endswith('h'):
        try:
            duration_seconds = int(duration_str[:-1]) * 3600
        except ValueError:
            return await bot.reply_to(m, "Invalid mute duration.")
    elif duration_str.endswith('d'):
        try:
            duration_seconds = int(duration_str[:-1]) * 86400
        except ValueError:
            return await bot.reply_to(m, "Invalid mute duration.")
    else:
        if duration_str == "":
            # No duration = indefinite
            pass
        else:
            return await bot.reply_to(m, "Specify duration as 10m, 1h, or 1d, or omit for indefinite.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to mute.")
    
    if not await is_moderatable(m.chat.id, target_user.id):
        return await bot.reply_to(m, f"Cannot mute {target_user.first_name} - they are an admin/creator.")
    
    if duration_seconds is None:
        # Indefinite mute
        try:
            await bot.restrict_chat_member(m.chat.id, target_user.id, permissions=mute_permissions())
        except Exception as e:
            return await bot.reply_to(m, f"Failed to mute: {e}")
        await bot.reply_to(m, f"Muted {target_user.first_name} (indefinitely).")
        log_event("mute", chat_id=m.chat.id, user_id=target_user.id, detail="indefinite")
    else:
        # Duration mute
        from datetime import timedelta, datetime
        until_date = datetime.now() + timedelta(seconds=duration_seconds)
        try:
            await bot.restrict_chat_member(m.chat.id, target_user.id, permissions=mute_permissions(), until_date=until_date)
            hours = duration_seconds // 3600
            await bot.reply_to(m, f"Muted {target_user.first_name} for {hours}h (until {until_date.strftime('%Y-%m-%d %H:%M')}).")
            log_event("mute", chat_id=m.chat.id, user_id=target_user.id, detail=f"until_date: {until_date}")
        except Exception as e:
            return await bot.reply_to(m, f"Failed to mute: {e}")


@handle_errors
async def unmute(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to unmute.")
    
    # unmute is safe on anyone (even admins), so no permission guard needed
    try:
        await bot.restrict_chat_member(m.chat.id, target_user.id, permissions=open_permissions())
    except Exception as e:
        return await bot.reply_to(m, f"Failed to unmute: {e}")
    
    await bot.reply_to(m, f"Unmuted {target_user.first_name}.")
    log_event("unmute", chat_id=m.chat.id, user_id=target_user.id, detail="unmuted")


@handle_errors
async def kick(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")
    
    target_user = await get_target_user(m)
    if not target_user:
        return await bot.reply_to(m, "Reply to a user or provide their ID to kick.")
    
    if not await is_moderatable(m.chat.id, target_user.id):
        return await bot.reply_to(m, f"Cannot kick {target_user.first_name} - they are an admin/creator.")
    
    # Use the captcha kick mechanism: ban + immediate unban, reset kick count
    from modules.captcha import increment_kicks, reset_kicks
    current_kicks = increment_kicks(m.chat.id, target_user.id)
    try:
        await bot.ban_chat_member(m.chat.id, target_user.id)
        await bot.unban_chat_member(m.chat.id, target_user.id, only_if_banned=True)
        reset_kicks(m.chat.id, target_user.id)
    except Exception as e:
        await bot.reply_to(m, f"Failed to kick: {e}")
        return
    
    kick_msg = f"You were removed from the chat."
    try:
        await bot.send_message(target_user.id, kick_msg)
    except:
        pass
    
    await bot.reply_to(m, f"Kicked {target_user.first_name}.")
    log_event("kick", chat_id=m.chat.id, user_id=target_user.id, detail="kicked")