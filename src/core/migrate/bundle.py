"""The neutral shape every supported export is parsed into."""

from dataclasses import dataclass, field

from core.migrate.convert import (
    MAX_MESSAGE_LENGTH, buttons_to_links, file_kind, first_variant,
    greeting_length, map_greeting_placeholders, rendered_length, strip_placeholders,
)
from core.validation import validate_template


@dataclass
class Entry:
    name: str
    text: str
    notes: list[str] = field(default_factory=list)  # what the conversion changed


@dataclass
class Skip:
    section: str
    name: str
    reason: str


@dataclass
class ImportBundle:
    source: str
    source_chat_id: int | None = None
    notes: list[Entry] = field(default_factory=list)
    filters: list[Entry] = field(default_factory=list)
    blocked_words: list[str] = field(default_factory=list)
    greeting: Entry | None = None
    goodbye: Entry | None = None
    skipped: list[Skip] = field(default_factory=list)
    not_imported: list[str] = field(default_factory=list)  # whole sections/settings
    warnings: list[str] = field(default_factory=list)

    def skip(self, section, name, reason) -> None:
        self.skipped.append(Skip(section, name, reason))


def _too_long(length: int) -> str:
    return f"{length}/{MAX_MESSAGE_LENGTH} characters after conversion; shorten it and re-save"


def convert_reply(bundle, section, name, text, data_id="") -> Entry | None:
    """Convert a note/filter/rules body, or record why it can't be imported."""
    if data_id:
        bundle.skip(section, name,
                    f"contains media ({file_kind(data_id)}), which can't move between bots; re-save it")
        return None
    text, multiple = first_variant(text or "")
    text, removed = strip_placeholders(text)
    text = buttons_to_links(text).strip()
    if not text:
        bundle.skip(section, name, "empty after conversion")
        return None
    length = rendered_length(text)
    if length > MAX_MESSAGE_LENGTH:
        bundle.skip(section, name, _too_long(length))
        return None
    notes = []
    if multiple:
        notes.append("kept the first of several random replies")
    if removed:
        notes.append("removed " + ", ".join(removed))
    return Entry(name, text, notes)


def convert_greeting(bundle, event, text, data_id="") -> Entry | None:
    """Convert a welcome/goodbye template, or record why it can't be imported."""
    if data_id:
        bundle.skip("greetings", event,
                    f"contains media ({file_kind(data_id)}), which can't move between bots; set it again")
        return None
    text, multiple = first_variant(text or "")
    text, removed = map_greeting_placeholders(text)
    text = buttons_to_links(text).strip()
    if not text:
        bundle.skip("greetings", event, "empty (the old bot's default isn't exported)")
        return None
    if not validate_template(text):
        bundle.skip("greetings", event,
                    "uses braces other than {firstname}, {lastname}, {username}")
        return None
    length = greeting_length(text)
    if length > MAX_MESSAGE_LENGTH:
        bundle.skip("greetings", event, _too_long(length))
        return None
    notes = []
    if multiple:
        notes.append("kept the first of several random replies")
    if removed:
        notes.append("removed " + ", ".join(removed))
    if "](" in text:
        notes.append("greetings are sent as plain text, so links show as [name](url)")
    return Entry(event, text, notes)
