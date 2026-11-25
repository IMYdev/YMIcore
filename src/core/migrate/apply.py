"""Write an ImportBundle into a group through the existing settings helpers.

``run(..., write=False)`` is the preview: the same decisions, nothing saved.
Limits are the bot's own (filter/word caps and lengths); the simulation keeps
its own counts so the preview matches what the write will do.
"""

from dataclasses import dataclass, field

from core.group_settings import (
    MAX_BLOCKED_WORD_LENGTH, MAX_BLOCKED_WORDS_PER_CHAT,
    MAX_FILTER_KEYWORD_LENGTH, MAX_FILTERS_PER_CHAT,
    add_blocked_word, add_filter, add_note, clear_greeting_media,
    normalize_blocked_word, normalize_filter_keyword,
    read_blocked_words, read_filters, read_greetings, read_notes,
    save_greeting_messages, update_note, validate_message_template,
)
from core.migrate.bundle import ImportBundle, Skip

MERGE = "merge"
REPLACE = "replace"


@dataclass
class Report:
    mode: str
    notes: list[tuple[str, str, bool]] = field(default_factory=list)  # name, id, replaced
    filters: list[tuple[str, bool]] = field(default_factory=list)     # keyword, replaced
    words: list[str] = field(default_factory=list)
    greetings: list[tuple[str, bool]] = field(default_factory=list)   # event, replaced
    changes: list[str] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.notes) + len(self.filters) + len(self.words) + len(self.greetings)

    @property
    def replaced(self) -> int:
        return (sum(r for *_, r in self.notes) + sum(r for _, r in self.filters)
                + sum(r for _, r in self.greetings))


def _reply(text) -> dict:
    # Same shape /add and /filter store for a plain text message.
    return {"type": "text", "data": text}


def _note_changes(report, section, entry) -> None:
    label = section if section == entry.name else f"{section} '{entry.name}'"
    for note in entry.notes:
        report.changes.append(f"{label}: {note}")


def _notes(bundle, gid, mode, write, report) -> None:
    existing = read_notes(gid)
    by_name = {}
    for note_id, note in existing.items():
        by_name.setdefault(note.get("name"), note_id)
    next_id = max(map(int, existing), default=0) + 1
    seen = set()
    for entry in bundle.notes:
        if entry.name in seen:
            report.skipped.append(Skip("notes", entry.name, "duplicate name in the export"))
            continue
        seen.add(entry.name)
        if entry.name in by_name:
            note_id = by_name[entry.name]
            if mode != REPLACE:
                report.skipped.append(Skip("notes", entry.name, f"a note with this name exists (#{note_id})"))
                continue
            if write:
                update_note(gid, note_id, entry.name, _reply(entry.text))
            report.notes.append((entry.name, note_id, True))
        else:
            if write:
                note_id = add_note(gid, entry.name, reply=_reply(entry.text))
            else:
                note_id = str(next_id)
            next_id += 1
            report.notes.append((entry.name, note_id, False))
        _note_changes(report, "note", entry)


def _filters(bundle, gid, mode, write, report) -> None:
    existing = set(read_filters(gid))
    count = len(existing)
    seen = set()
    for entry in bundle.filters:
        keyword = normalize_filter_keyword(entry.name)
        if keyword in seen:
            report.skipped.append(Skip("filters", entry.name, "duplicate keyword in the export"))
            continue
        seen.add(keyword)
        if not keyword or len(keyword) > MAX_FILTER_KEYWORD_LENGTH:
            report.skipped.append(Skip(
                "filters", entry.name, f"keyword must be 1-{MAX_FILTER_KEYWORD_LENGTH} characters"))
            continue
        replaced = keyword in existing
        if replaced and mode != REPLACE:
            report.skipped.append(Skip("filters", entry.name, "a filter with this keyword exists"))
            continue
        if not replaced and count >= MAX_FILTERS_PER_CHAT:
            report.skipped.append(Skip(
                "filters", entry.name, f"filter limit reached ({MAX_FILTERS_PER_CHAT})"))
            continue
        if write:
            try:
                add_filter(gid, keyword, reply=_reply(entry.text))
            except ValueError as e:
                report.skipped.append(Skip("filters", entry.name, str(e)))
                continue
        if not replaced:
            count += 1
        report.filters.append((keyword, replaced))
        _note_changes(report, "filter", entry)


def _words(bundle, gid, write, report) -> None:
    existing = set(read_blocked_words(gid))
    count = len(existing)
    for raw in bundle.blocked_words:
        word = normalize_blocked_word(raw)
        if not word or len(word) > MAX_BLOCKED_WORD_LENGTH:
            report.skipped.append(Skip(
                "blocked words", raw, f"must be 1-{MAX_BLOCKED_WORD_LENGTH} characters"))
            continue
        if word in existing:
            report.skipped.append(Skip("blocked words", raw, "already blocked"))
            continue
        if count >= MAX_BLOCKED_WORDS_PER_CHAT:
            report.skipped.append(Skip(
                "blocked words", raw, f"blocked word limit reached ({MAX_BLOCKED_WORDS_PER_CHAT})"))
            continue
        if write:
            try:
                add_blocked_word(gid, word)
            except ValueError as e:
                report.skipped.append(Skip("blocked words", raw, str(e)))
                continue
        existing.add(word)
        count += 1
        report.words.append(word)


def _greetings(bundle, gid, mode, write, report) -> None:
    current = read_greetings(gid)
    for event in ("greeting", "goodbye"):
        entry = getattr(bundle, event)
        if entry is None:
            continue
        err = validate_message_template(entry.text)
        if err:
            report.skipped.append(Skip("greetings", event, err))
            continue
        replaced = bool(current.get(event) or current.get(f"{event}_media_id"))
        if replaced and mode != REPLACE:
            report.skipped.append(Skip("greetings", event, f"a {event} message is already set"))
            continue
        if write:
            # Setting a text greeting by command also clears its media.
            clear_greeting_media(gid, event)
            save_greeting_messages(gid, **{event: entry.text})
        report.greetings.append((event, replaced))
        _note_changes(report, event, entry)


def run(bundle: ImportBundle, gid, mode=MERGE, *, write=False) -> Report:
    if mode not in (MERGE, REPLACE):
        raise ValueError(f"unknown import mode: {mode}")
    report = Report(mode=mode, skipped=list(bundle.skipped))
    _notes(bundle, gid, mode, write, report)
    _filters(bundle, gid, mode, write, report)
    _words(bundle, gid, write, report)
    _greetings(bundle, gid, mode, write, report)
    return report


def preview(bundle, gid, mode=MERGE) -> Report:
    return run(bundle, gid, mode, write=False)


def apply(bundle, gid, mode=MERGE) -> Report:
    return run(bundle, gid, mode, write=True)
