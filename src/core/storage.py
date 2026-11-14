"""Single entry point for every runtime JSON store.

Anything that needs IMYDB asks this module for it. Keeping the paths in one
place is what stops a second implementation of "where do group notes live"
from appearing next to the first.
"""

from core.db import IMYDB

GROUP_FILES = {
    "greetings": "runtime/greetings/{key}_greetings.json",
    "filters": "runtime/filters/{key}_filters",
    "notes": "runtime/notes/{key}_notes.json",
    "stickers": "runtime/banned/{key}_stickers.json",
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


def group_db(section, chat_id) -> IMYDB:
    return IMYDB(GROUP_FILES[section].format(key=group_key(chat_id)))


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
