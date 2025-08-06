from info import bot
from core.imysdbMongo import IMYDB
from core.utils import log_error

async def set_note(m):
    try:
        necessary_evil = await bot.get_chat_member(m.chat.id, m.from_user.id)
        rank = necessary_evil.status
        
        if rank != "member":
            note_name = m.text.split()[1]
            chat_id = str(m.chat.id).lstrip('-')
            db = IMYDB(f'runtime/notes/{chat_id}_notes.json')

            reply_with = {}
            if m.reply_to_message:
                if m.reply_to_message.text:
                    reply_with = {"type": "text", "data": str(m.reply_to_message.text)}
                elif m.reply_to_message.sticker:
                    reply_with = {"type": "sticker", "data": m.reply_to_message.sticker.file_id}
                elif m.reply_to_message.photo:
                    reply_with = {"type": "photo", "data": m.reply_to_message.photo[-1].file_id}
                elif m.reply_to_message.document:
                    reply_with = {"type": "document", "data": m.reply_to_message.document.file_id}
                elif m.reply_to_message.video:
                    reply_with = {"type": "video", "data": m.reply_to_message.video.file_id}
                else:
                    reply_with = {"type": "unknown", "data": None}

            notes = db.get('notes', {})
            next_id = max(map(int, notes.keys()), default=0) + 1
            notes[str(next_id)] = {"name": str(note_name), "reply": reply_with}
            db.set('notes', notes)

            await bot.reply_to(m, f"Note saved. ID: {next_id}.")
        else:
            await bot.reply_to(m, "Access denied.")
    except IndexError:
        await bot.reply_to(m, "Please provide a note name.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")



async def get_notes(m):
    chat_id = str(m.chat.id).lstrip('-')
    if "#" in m.text:
        try:
            parts = m.text.split("#")
            if len(parts) > 1:
                note_id = parts[1].strip()

                if note_id.isdigit():
                    db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
                    notes = db.get('notes', {})

                    if note_id in notes:
                        note = notes[note_id]
                        reply_type = note['reply']['type']
                        reply_data = note['reply']['data']

                        if reply_type == "text":
                            await bot.send_message(m.chat.id, reply_data)
                        elif reply_type == "sticker":
                            await bot.send_sticker(m.chat.id, reply_data)
                        elif reply_type == "photo":
                            await bot.send_photo(m.chat.id, reply_data)
                        elif reply_type == "document":
                            await bot.send_document(m.chat.id, reply_data)
                        elif reply_type == "video":
                            await bot.send_video(m.chat.id, reply_data)
                        else:
                            await bot.send_message(m.chat.id, "Note is unreadable.")
                    else:
                        await bot.send_message(m.chat.id, f"No note with ID {note_id}.")
                else:
                    pass
            else:
                await bot.send_message(m.chat.id, "No note ID after '#'.")
        except (IndexError, ValueError):
            await bot.reply_to(m, "Invalid note ID.")
        except Exception as error:
            await log_error(bot, error, context_msg=m)
            await bot.reply_to(m, "An error occurred.")
    else:
        pass



async def notes_list(m):
    chat_id = str(m.chat.id).lstrip('-')
    try:
        db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
        notes = db.get('notes', {})

        formatted_notes = '\n'.join([f"`{note_id}.` {note['name']}" for note_id, note in notes.items()])
        formatted_notes = formatted_notes.replace("_", "\\_").replace("*", "\\*")

        if formatted_notes:
            await bot.send_message(m.chat.id, f"_Catalog of notes:_\n{formatted_notes}\nRetrieve notes via '#note_number'.", parse_mode="Markdown")
        else:
            await bot.send_message(m.chat.id, "Catalog empty. No notes registered.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")





async def remove_note(m):
    chat_id = str(m.chat.id).lstrip('-')
    try:
        note_key = m.text.split()[1]
    except IndexError:
        await bot.reply_to(m, "Command error: Note ID required for removal.")
        return
    
    try:
        db = IMYDB(f'runtime/notes/{chat_id}_notes.json')
        notes = db.get('notes', {})
        
        if note_key in notes:
            del notes[note_key]

            # Renumber remaining notes strictly
            notes = {str(i+1): v for i, (k, v) in enumerate(notes.items())}
            db.set('notes', notes)

            await bot.send_message(m.chat.id, f"Note ID {note_key} eradicated. Operation successful.")
        else:
            await bot.send_message(m.chat.id, f"No note matching ID {note_key} found.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "An error occurred.")