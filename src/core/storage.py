"""Single entry point for every runtime JSON store.

Anything that needs IMYDB asks this module for it. Keeping the paths in one
place is what stops a second implementation of "where do group notes live"
from appearing next to the first.
"""

import time

from core.db import IMYDB

GROUP_FILES = {
    "greetings": "runtime/greetings/{key}_greetings.json",
    "filters": "runtime/filters/{key}_filters",
    "notes": "runtime/notes/{key}_notes.json",
    "stickers": "runtime/banned/{key}_stickers.json",
    "words": "runtime/banned/{key}_words.json",
    "word_mutes": "runtime/banned/{key}_word_mutes.json",
    "warns": "runtime/warns/{key}_warns.json",
}

MODULE_CONTROLLER = "runtime/modules/module_controller.json"
GROUPS_REGISTRY = "runtime/groups/registry.json"
BANNED_GROUPS = "runtime/banned/groups.json"
USERS_REGISTRY = "runtime/users/registry.json"
BROADCAST_REGISTRY = "runtime/broadcasts/registry.json"
BROADCAST_PENDING = "runtime/broadcasts/pending.json"
WEB_TOKENS = "runtime/web/tokens.json"

CAPTCHA_FILES = {
    "pending": "runtime/captcha/pending.json",
    "join_msgs": "runtime/captcha/join_msgs.json",
    "kicks": "runtime/captcha/kicks.json",
}

def group_key(chat_id) -> str:
    """Chat id as used in per-group file names (no leading minus)."""
    return str(chat_id).lstrip("-")


def group_path(section, chat_id) -> str:
    """Raw path of a per-group store, for stat-based cache invalidation."""
    return GROUP_FILES[section].format(key=group_key(chat_id))


def group_db(section, chat_id) -> IMYDB:
    return IMYDB(GROUP_FILES[section].format(key=group_key(chat_id)))


def warn_db(chat_id) -> IMYDB:
    return IMYDB(GROUP_FILES["warns"].format(key=group_key(chat_id)))


def warn_counts(chat_id) -> dict:
    """Per-user warn counts and latest warn for a chat."""
    db = warn_db(chat_id)
    data = db.get('warns') or {}
    result = {}
    for uid_str, entries in (data or {}).items():
        recent = entries[-5:] if len(entries) > 5 else entries
        latest = recent[-1] if recent else None
        result[uid_str] = {
            "count": len(recent),
            "latest": {
                "reason": latest.get("reason", "") if latest else "",
                "by": latest.get("by", None) if latest else None,
                "ts": latest.get("ts", 0) if latest else 0,
            } if latest else None,
        }
    return result


def add_warn(chat_id, user_id, reason, by_user_id) -> dict:
    """Append a warn and return the updated per-user state."""
    db = warn_db(chat_id)
    data = db.get('warns') or {}

    key = str(user_id)
    entry = {"reason": reason, "by": by_user_id, "ts": int(time.time())}

    if key in data:
        data[key].append(entry)
        if len(data[key]) > 5:
            data[key] = data[key][-5:]
    else:
        data[key] = [entry]

    db.set('warns', data)
    return warn_counts(chat_id)


def clear_warns(chat_id, user_id=None) -> dict:
    """Remove all warns for a user, or all warns in the chat if user_id is None."""
    db = warn_db(chat_id)
    data = db.get('warns') or {}

    if user_id is not None:
        key = str(user_id)
        if key in data:
            del data[key]
    else:
        data.clear()

    # If data becomes empty, delete the file to avoid stale empty JSON
    if not data:
        try:
            db.delete('warns')
        except Exception:
            pass
        return {}

    db.set('warns', data)
    return warn_counts(chat_id)


def module_db() -> IMYDB:
    return IMYDB(MODULE_CONTROLLER)


def groups_db() -> IMYDB:
    return IMYDB(GROUPS_REGISTRY)


def banned_db() -> IMYDB:
    return IMYDB(BANNED_GROUPS)


def users_db() -> IMYDB:
    return IMYDB(USERS_REGISTRY)


def broadcast_db(kind="registry") -> IMYDB:
    return IMYDB(BROADCAST_REGISTRY if kind == "registry" else BROADCAST_PENDING)


def web_db() -> IMYDB:
    return IMYDB(WEB_TOKENS)


def captcha_db(kind) -> IMYDB:
    return IMYDB(CAPTCHA_FILES[kind])