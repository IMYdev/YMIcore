"""Import a group's notes, filters, blocked words, greetings and rules from
a Rose or AstrakoBot export. Any other file is rejected.

The importer is limited to what the bot already offers: it writes only
through the existing group_settings helpers and skips, with a reason,
whatever the bot can't represent.
"""

import json
import re

from core.migrate.bundle import Entry, ImportBundle, Skip
from core.migrate.formats import FORMATS

MAX_EXPORT_BYTES = 1024 * 1024

UNSUPPORTED = "Unsupported export format. Only Rose and AstrakoBot exports can be imported."

_CHAT_ID_IN_NAME = re.compile(r"-100\d{5,}")


class UnsupportedExport(ValueError):
    pass


def chat_id_from_filename(filename) -> int | None:
    match = _CHAT_ID_IN_NAME.search(filename or "")
    return int(match.group(0)) if match else None


def load(content: bytes, filename: str = "") -> ImportBundle:
    """Parse an export file. Raises UnsupportedExport for anything else."""
    if len(content) > MAX_EXPORT_BYTES:
        raise UnsupportedExport("That file is too large to be an export (limit 1 MB).")
    try:
        raw = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise UnsupportedExport(UNSUPPORTED) from None
    for fmt in FORMATS:
        if fmt.matches(raw):
            bundle = fmt.parse(raw)
            bundle.source_chat_id = chat_id_from_filename(filename)
            return bundle
    raise UnsupportedExport(UNSUPPORTED)


__all__ = [
    "Entry", "ImportBundle", "MAX_EXPORT_BYTES", "Skip", "UNSUPPORTED",
    "UnsupportedExport", "chat_id_from_filename", "load",
]
