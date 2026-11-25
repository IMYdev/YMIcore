"""Text conversions from other bots' formats into what YMIcore already stores.

Nothing here adds a feature to the bot: every conversion either maps onto
something the bot already renders or drops what it can't, and says so.
"""

import base64
import binascii
import html
import re

from core.formatting import markdown_to_html

# Telegram's limit on a message's text, counted after entity parsing in
# UTF-16 code units.
MAX_MESSAGE_LENGTH = 4096

# Longest values the greeting placeholders can expand to (Telegram limits).
_WORST_CASE_FIELDS = {
    "firstname": "x" * 64,
    "lastname": "x" * 64,
    "username": "@" + "x" * 32,
}

# --------------------------------------------------------------------------
# Buttons
# --------------------------------------------------------------------------

# [label](buttonurl:URL), [label](buttonurl://URL), optionally ending in :same
_BUTTON = re.compile(r"\[([^\]\n]+)\]\(buttonurl:(?://)?([^)\s]+?)(?::same)?\)")
_HAS_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _button_url(url: str) -> str:
    return url if _HAS_SCHEME.match(url) else f"https://{url}"


def buttons_to_links(text: str) -> str:
    """Move every button to the end of the message as a [label](url) link.

    Buttons are taken out of the body in their original order and appended
    one per line. A line that held nothing but buttons is dropped.
    """
    links = []
    kept = []
    for line in text.split("\n"):
        found = _BUTTON.findall(line)
        if not found:
            kept.append(line)
            continue
        links.extend(f"[{label}]({_button_url(url)})" for label, url in found)
        rest = _BUTTON.sub("", line)
        if rest.strip():
            kept.append(rest.rstrip())
    if not links:
        return text
    body = "\n".join(kept).rstrip()
    return f"{body}\n" + "\n".join(links) if body else "\n".join(links)


# --------------------------------------------------------------------------
# Placeholders
# --------------------------------------------------------------------------

# Fillings Rose and Marie-based bots understand. Only these are touched, so
# literal braces in notes (shell snippets like ${JAVA_HOME}) survive.
KNOWN_PLACEHOLDERS = {
    "first", "last", "fullname", "username", "mention", "id", "chatname",
    "rules", "preview", "nonotif", "protect", "mediaspoiler", "replytag",
    "admin", "user", "count", "chat", "firstname", "lastname",
}
_GREETING_MAP = {
    "first": "{firstname}",
    "firstname": "{firstname}",
    "last": "{lastname}",
    "lastname": "{lastname}",
    "fullname": "{firstname} {lastname}",
    "username": "{username}",
    "mention": "{username}",
}
_PLACEHOLDER = re.compile(r"\{(\w+)(?::\w+)?\}")
# Take the space before a placeholder that ends a clause, otherwise the space after.
_TRAILING_PUNCT = ".,!?;:)"


def _remove_placeholder(text: str, token: str) -> str:
    escaped = re.escape(token)
    text = re.sub(rf"[ \t]?{escaped}(?=[{re.escape(_TRAILING_PUNCT)}]|$)", "", text, flags=re.M)
    return re.sub(rf"{escaped}[ \t]?", "", text)


def _known_tokens(text: str) -> list[tuple[str, str]]:
    """(token, name) for each distinct known placeholder, in order."""
    seen = {}
    for match in _PLACEHOLDER.finditer(text):
        if match.group(1).lower() in KNOWN_PLACEHOLDERS:
            seen.setdefault(match.group(0), match.group(1).lower())
    return list(seen.items())


def strip_placeholders(text: str) -> tuple[str, list[str]]:
    """Notes and filters send their text as-is, so every filling goes."""
    removed = []
    for token, _ in _known_tokens(text):
        text = _remove_placeholder(text, token)
        removed.append(token)
    return text, removed


def map_greeting_placeholders(text: str) -> tuple[str, list[str]]:
    """Map fillings onto {firstname}/{lastname}/{username}; drop the rest."""
    removed = []
    for token, name in _known_tokens(text):
        if token == f"{{{name}}}" and name in _GREETING_MAP:
            text = text.replace(token, _GREETING_MAP[name])
        else:
            text = _remove_placeholder(text, token)
            removed.append(token)
    return text, removed


# --------------------------------------------------------------------------
# Random replies
# --------------------------------------------------------------------------

_RANDOM_SEPARATOR = re.compile(r"\s*%%%\s*")


def first_variant(text: str) -> tuple[str, bool]:
    """Keep the first of several %%%-separated replies."""
    parts = _RANDOM_SEPARATOR.split(text)
    if len(parts) < 2:
        return text, False
    return parts[0], True


# --------------------------------------------------------------------------
# Media
# --------------------------------------------------------------------------

# TDLib FileType ids, which are the first byte of a Bot API file_id.
_FILE_TYPES = {
    0: "thumbnail", 1: "profile photo", 2: "photo", 3: "voice message",
    4: "video", 5: "document", 8: "sticker", 9: "audio", 10: "animation",
    13: "video note",
}


def file_kind(file_id: str) -> str:
    """Human name of a file_id's media type, or "media" if unreadable."""
    try:
        padded = file_id + "=" * (-len(file_id) % 4)
        first = base64.urlsafe_b64decode(padded)[0]
    except (binascii.Error, ValueError, IndexError, TypeError):
        return "media"
    return _FILE_TYPES.get(first, "media")


# --------------------------------------------------------------------------
# Length
# --------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def rendered_length(text: str) -> int:
    """Visible length of a note/filter once the bot renders its markdown."""
    return utf16_length(html.unescape(_TAG.sub("", markdown_to_html(text))))


def greeting_length(template: str) -> int:
    """Worst-case length of a greeting after its fields are filled in."""
    return utf16_length(template.format(**_WORST_CASE_FIELDS))


__all__ = [
    "KNOWN_PLACEHOLDERS", "MAX_MESSAGE_LENGTH", "buttons_to_links", "file_kind",
    "first_variant", "greeting_length", "map_greeting_placeholders",
    "rendered_length", "strip_placeholders", "utf16_length",
]
