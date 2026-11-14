"""Per-group settings shared by bot commands and the web panel.

Every read/write of a group's notes, filters, stickers, greetings and captcha
settings goes through this module so the bot and the panel can never drift
into two different storage formats.
"""

from core.storage import group_db
from core.validation import validate_question, validate_template
from module_manager import (
    modules as MODULE_MAP, is_command_enabled, module_stats, read_module_states,
    set_command_enabled,
)

CAPTCHA_LEGACY_KEYS = ('captcha_q', 'captcha_opts', 'captcha_ans', 'user_attempts')


def _db(section, chat_id):
    return group_db(section, chat_id)


def drop_legacy_captcha(db) -> None:
    for key in CAPTCHA_LEGACY_KEYS:
        try:
            db.delete(key)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_message_template(text) -> str | None:
    if not text.strip():
        return "Message cannot be empty."
    if not validate_template(text):
        return "Only {firstname}, {lastname}, and {username} are allowed."
    return None


def validate_captcha(questions, tries) -> str | None:
    if not questions or len(questions) < 1:
        return "At least one question required."
    if len(questions) > 3:
        return "Maximum of 3 questions."
    for item in questions:
        if not isinstance(item, dict) or 'q' not in item or 'opts' not in item or 'ans' not in item:
            return "Each question must have q, opts, ans."
        err = validate_question(item.get('q'), item.get('opts'), item.get('ans'))
        if err:
            return err
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
# Captcha questions
# --------------------------------------------------------------------------

def get_captcha_questions(db):
    questions = db.get('captcha_questions')
    if questions and isinstance(questions, list) and len(questions) > 0:
        return questions
    # lazy legacy migration
    legacy_q = db.get('captcha_q')
    if legacy_q is not None and legacy_q != '':
        opts = db.get('captcha_opts', [])
        ans = db.get('captcha_ans')
        return [{"q": legacy_q, "opts": opts, "ans": ans}]
    return []


def read_captcha_questions(gid):
    return get_captcha_questions(_db("greetings", gid))


def save_captcha(gid, questions, tries) -> None:
    db = _db("greetings", gid)
    db.set('captcha_questions', questions)
    db.set('captcha_max_tries', int(tries))
    drop_legacy_captcha(db)


def set_captcha_enabled(gid, enabled) -> None:
    _db("greetings", gid).set("captcha_enabled", bool(enabled))


# --------------------------------------------------------------------------
# Greetings & farewells
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


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------

def read_filters(gid) -> dict:
    return _db("filters", gid).get("filters", {})


def add_filter(gid, keyword, body=None, media_type=None, media_id=None, reply=None) -> None:
    db = _db("filters", gid)
    filters = db.get("filters", {})
    if reply is None:
        if media_type and media_id:
            reply = {"type": media_type, "data": media_id}
            if body:
                reply["text"] = body
        else:
            reply = {"type": "text", "data": body}
    filters[keyword] = reply
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


def add_note(gid, name, body=None, media_type=None, media_id=None, reply=None) -> str:
    db = _db("notes", gid)
    notes = db.get("notes", {})
    next_id = max(map(int, notes.keys()), default=0) + 1
    if reply is None:
        if media_type and media_id:
            reply = {"type": media_type, "data": media_id}
            if body:
                reply["text"] = body
        else:
            reply = {"type": "text", "data": body}
    notes[str(next_id)] = {"name": name, "reply": reply}
    db.set("notes", notes)
    return str(next_id)


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


__all__ = [
    "MODULE_MAP", "add_filter", "add_note", "add_sticker", "clear_greeting_media",
    "delete_filter", "delete_note", "delete_sticker", "drop_legacy_captcha", "get_captcha_questions",
    "is_command_enabled", "module_stats", "read_captcha_questions", "read_filters",
    "read_greetings", "read_module_states", "read_notes", "read_stickers",
    "save_captcha", "save_greeting_messages", "set_captcha_enabled",
    "set_command_enabled", "set_greeting_media", "validate_captcha",
    "validate_message_template", "validate_named_text",
]
