from info import bot
from core.group_settings import add_note, delete_note, read_notes
from core.replies import build_reply, send_reply
from core.utils import (handle_errors, is_user_owner, get_args, is_privileged, topic_kwargs)
from core.activity import (log_event, user_label, chat_label)
from core.groups import set_developer_group
from telebot.formatting import (format_text, hbold, hitalic, hcode)


@handle_errors
async def set_note(m):
    if not await is_privileged(m.chat.id, m.from_user.id, allow_devgroup=True):
        return await bot.reply_to(m, "Admins only")

    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Please provide a note name.")

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to save as a note.")

    note_id = add_note(m.chat.id, args[0], reply=build_reply(m.reply_to_message))
    await bot.reply_to(m, f"Note saved. ID: {note_id}.")

@handle_errors
async def get_notes(m):
    if not m.text or not m.text.startswith("#") or not m.text[1:].isdigit():
        return

    note_id = m.text[1:]
    notes = read_notes(m.chat.id)

    if note_id in notes:
        note = notes[note_id]
        await send_reply(m.chat.id, note["reply"], fallback="Note is unreadable.", **topic_kwargs(m))
        log_event(
            "note_fetch",
            chat_id=m.chat.id, chat_name=chat_label(m.chat),
            user_id=getattr(m.from_user, "id", None), user_name=user_label(m.from_user),
            detail=note.get("name") or f"#{note_id}",
        )
    else:
        await bot.send_message(m.chat.id, f"No note with ID {note_id}.", **topic_kwargs(m))

@handle_errors
async def notes_list(m):
    notes = read_notes(m.chat.id)

    if not notes:
        return await bot.send_message(m.chat.id, "Catalog empty. No notes registered.", **topic_kwargs(m))

    formatted_notes = '\n'.join([f"{hcode(str(nid))}. {n['name']}" for nid, n in notes.items()])
    formatted_reply = format_text(
        hitalic("Catalog of notes:"),
        formatted_notes,
        hbold("Retrieve notes via #note_number")
    )
    await bot.send_message(m.chat.id, formatted_reply, parse_mode="HTML", **topic_kwargs(m))

@handle_errors
async def remove_note(m):
    if not await is_privileged(m.chat.id, m.from_user.id, allow_devgroup=True):
        return await bot.reply_to(m, "Admins only")

    args = get_args(m)
    if not args:
        return await bot.reply_to(m, "Command error: Note ID required for removal.")

    note_key = args[0]

    if note_key in read_notes(m.chat.id):
        delete_note(m.chat.id, note_key)
        await bot.send_message(m.chat.id, f"Note ID {note_key} removed.", **topic_kwargs(m))
    else:
        await bot.send_message(m.chat.id, f"No note matching ID {note_key} found.", **topic_kwargs(m))


async def devgroup_command(message):
    args = get_args(message)
    if not args or args[0] not in ("on", "off"):
        return await bot.reply_to(message, "Usage: /devgroup on|off")
    chat_id = message.chat.id
    if not await is_user_owner(chat_id, message.from_user.id):
        return await bot.reply_to(message, "Only the group owner can toggle developer mode.")
    enabled = args[0] == "on"
    set_developer_group(chat_id, enabled)
    await bot.reply_to(message, f"Developer group mode {'enabled' if enabled else 'disabled'}.")
