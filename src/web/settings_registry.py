from itertools import chain

from core.imysdb import IMYDB
from modules.greetings import validate_template
from module_manager import modules as MODULE_MAP, default_disabled

GROUP_FILES = {
    "greetings": "runtime/greetings/{key}_greetings.json",
    "filters": "runtime/filters/{key}_filters",
    "notes": "runtime/notes/{key}_notes.json",
    "stickers": "runtime/banned/{key}_stickers.json",
}


def group_key(chat_id) -> str:
    return str(chat_id).lstrip("-")


def _db(section, chat_id) -> IMYDB:
    return IMYDB(GROUP_FILES[section].format(key=group_key(chat_id)))


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_message_template(text) -> str | None:
    if not text.strip():
        return "Message cannot be empty."
    if not validate_template(text):
        return "Only {firstname}, {lastname}, and {username} are allowed."
    return None


def validate_captcha(question, options, answer, tries) -> str | None:
    if not question.strip():
        return "Question is required."
    if len(options) < 2:
        return "Provide at least two options."
    if not answer.strip() or answer not in options:
        return "Correct answer must be one of the options."
    try:
        tries_value = int(tries)
    except (TypeError, ValueError):
        return "Max tries must be a number."
    if tries_value < 1:
        return "Max tries must be at least 1."
    return None


def validate_named_text(name, body) -> str | None:
    if not name.strip():
        return "Name/keyword is required."
    if not body.strip():
        return "Text is required."
    return None


# --------------------------------------------------------------------------
# Modules & commands
# --------------------------------------------------------------------------

def read_module_states(gid) -> dict:
    db = IMYDB("runtime/modules/module_controller.json")
    saved = db.get(f"groups.{gid}", {})
    states = {}
    for command in chain(*MODULE_MAP.values()):
        states[command] = saved.get(f"{command}_enabled", default_disabled.get(command, True))
    return states


def set_module_enabled(gid, command, enabled) -> None:
    db = IMYDB("runtime/modules/module_controller.json")
    db.set(f"groups.{gid}.{command}_enabled", bool(enabled))


def module_stats(gid):
    states = read_module_states(gid)
    enabled = sum(1 for v in states.values() if v)
    return enabled, len(states)


# --------------------------------------------------------------------------
# Greetings & captcha
# --------------------------------------------------------------------------

def read_greetings(gid) -> dict:
    return _db("greetings", gid).data


def save_greeting_messages(gid, greeting=None, goodbye=None) -> None:
    db = _db("greetings", gid)
    if greeting is not None:
        db.set("greeting", greeting)
    if goodbye is not None:
        db.set("goodbye", goodbye)


def clear_greeting_media(gid, event) -> None:
    db = _db("greetings", gid)
    db.set(f"{event}_media_type", None)
    db.set(f"{event}_media_id", None)


def set_greeting_media(gid, event, media_type, media_id) -> None:
    db = _db("greetings", gid)
    db.set(f"{event}_media_type", media_type)
    db.set(f"{event}_media_id", media_id)


def save_captcha(gid, question, options, answer, tries) -> None:
    db = _db("greetings", gid)
    db.set("captcha_q", question)
    db.set("captcha_opts", options)
    db.set("captcha_ans", answer)
    db.set("captcha_max_tries", int(tries))


def set_captcha_enabled(gid, enabled) -> None:
    db = _db("greetings", gid)
    db.set("captcha_enabled", bool(enabled))


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------

def read_filters(gid) -> dict:
    return _db("filters", gid).get("filters", {})


def add_filter(gid, keyword, body, media_type=None, media_id=None) -> None:
    db = _db("filters", gid)
    filters = db.get("filters", {})
    if media_type and media_id:
        filters[keyword] = {"type": media_type, "data": media_id}
    else:
        filters[keyword] = {"type": "text", "data": body}
    db.set("filters", filters)


def delete_filter(gid, keyword) -> None:
    db = _db("filters", gid)
    filters = db.get("filters", {})
    if keyword in filters:
        del filters[keyword]
        db.set("filters", filters)


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------

def read_notes(gid) -> dict:
    return _db("notes", gid).get("notes", {})


def add_note(gid, name, body, media_type=None, media_id=None) -> None:
    db = _db("notes", gid)
    notes = db.get("notes", {})
    next_id = max(map(int, notes.keys()), default=0) + 1
    if media_type and media_id:
        reply = {"type": media_type, "data": media_id}
    else:
        reply = {"type": "text", "data": body}
    notes[str(next_id)] = {"name": name, "reply": reply}
    db.set("notes", notes)


def delete_note(gid, note_id) -> None:
    db = _db("notes", gid)
    notes = db.get("notes", {})
    if note_id in notes:
        del notes[note_id]
        notes = {str(i + 1): v for i, (k, v) in enumerate(notes.items())}
        db.set("notes", notes)


# --------------------------------------------------------------------------
# Sticker blocklist
# --------------------------------------------------------------------------

def read_stickers(gid) -> list:
    return _db("stickers", gid).get("stickers", [])


def add_sticker(gid, set_name) -> bool:
    db = _db("stickers", gid)
    stickers = db.get("stickers", [])
    if set_name in stickers:
        return False
    stickers.append(set_name)
    db.set("stickers", stickers)
    return True


def delete_sticker(gid, set_name) -> None:
    db = _db("stickers", gid)
    stickers = db.get("stickers", [])
    if set_name in stickers:
        stickers.remove(set_name)
        db.set("stickers", stickers)