import re

from telebot.formatting import (
    escape_html, hbold, hcode, hitalic, hlink, hpre, hspoiler, hstrikethrough,
)

_NULL = "\x00"

_EMPHASIS = [
    (r"\*\*(.+?)\*\*", lambda m: hbold(m.group(1))),
    (r"\*([^\s*][^*]*)\*", lambda m: hitalic(m.group(1))),
    (r"(?<![A-Za-z0-9_])_([^\s_][^_]*?)_(?![A-Za-z0-9_])", lambda m: hitalic(m.group(1))),
    (r"~~(.+?)~~", lambda m: hstrikethrough(m.group(1))),
    (r"\|\|(.+?)\|\|", lambda m: hspoiler(m.group(1))),
]


def markdown_to_html(text: str) -> str:
    """Convert a light markdown string into Telegram-compatible HTML.

    Supports fenced code blocks, inline code, links, bold, italic,
    strikethrough, spoilers, and # headings. Raw text is HTML-escaped so
    notes never leak markup into the bot's messages.
    """
    if not text:
        return ""

    placeholders = []

    def stash(part: str) -> str:
        token = f"{_NULL}{len(placeholders)}{_NULL}"
        placeholders.append(part)
        return token

    def fence(m):
        return stash(hpre(m.group(2), language=m.group(1) or ""))

    text = re.sub(r"```(\w+)?\n?(.*?)```", fence, text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", lambda m: stash(hcode(m.group(1))), text)
    text = re.sub(r"\[([^\]]+)\]\((\S+)\)", lambda m: stash(hlink(m.group(1), m.group(2))), text)
    text = re.sub(r"(?m)^#{1,6}\s+(.+)$", lambda m: stash(hbold(m.group(1))), text)

    for pattern, builder in _EMPHASIS:
        text = re.sub(pattern, lambda m: stash(builder(m)), text)

    text = escape_html(text)
    for i, part in enumerate(placeholders):
        text = text.replace(f"{_NULL}{i}{_NULL}", part)
    return text