"""Importing from Rose and AstrakoBot exports (core.migrate, modules.migrate)."""

import asyncio
import json
import os
from pathlib import Path

import pytest

from core.db import clear_cache
from core.group_settings import (
    MAX_FILTERS_PER_CHAT, add_filter, add_note, read_blocked_words, read_filters,
    read_greetings, read_notes, save_greeting_messages, set_greeting_media,
)
from core.migrate import UNSUPPORTED, UnsupportedExport, chat_id_from_filename, load
from core.migrate import apply as importer
from core.migrate import snapshot
from core.migrate.convert import (
    buttons_to_links, file_kind, first_variant, greeting_length,
    map_greeting_placeholders, rendered_length, strip_placeholders,
)

GID = -1001234567890
ROSE_ID = 609517172
ASTRAKO_ID = 1376954911

# Shaped like real Bot API file_ids; only the first byte (the type) matters.
STICKER_ID = "CAACAgIAAyEFAASict6KAAI5F2iG58tO814tG7yNuKgVPg3gVt7_AAJvEgAC6NbiEqzaRJ6rzOTONgQ"
PHOTO_ID = "AgACAgQAAx0CZ4a0MQACdYFmr5X0iJwx6O0B93fDdAd5jk3AOQACsrQxG6oO9VIWCUJMvce95AEAAwIAA3kAAzUE"
DOCUMENT_ID = "BQACAgIAAx0CdpHrpQACGdNlqTRs0rWPHF1-md2tEFiPtlLkigAC4joAAuuTKEmo_wAB7f79Pe80BA"
ANIMATION_ID = "CgACAgUAAx0CdpHrpQACWxFn4ktKmuTBaXLrS8__ynUwWtu8sgACbxgAAk-3CVf6YdQ6RQp9uTYE"


def rose_export(**data):
    base = {
        "notes": {"notes": [], "private_notes": False},
        "filters": {"filters": []},
        "blocklists": {"action": "nothing", "filters": [], "should_delete": True},
        "greetings": {"welcome": {"text": "", "data_id": "", "type": 0},
                      "goodbye": {"text": "", "data_id": "", "type": 0}},
        "rules": {"content": ""},
        "antiflood": {"flood_limit": 12},
        "warns": {"warn_limit": 3},
    }
    base.update(data)
    return {"bot_id": ROSE_ID, "data": base, "version": 2}


def astrako_export(**extra):
    base = {
        "bot_id": ASTRAKO_ID,
        "chat": {"rules": "", "warn_limit": 3, "antiflood_limit": 10},
        "notes": [],
        "greetings": [],
        "locks": {"all": {"locked": False}},
        "warns": [{"user_id": 1, "warn_count": 2, "reasons": ["spam", "spam"]}],
    }
    base.update(extra)
    return base


def note(name, text="", data_id=""):
    return {"name": name, "text": text, "data_id": data_id, "type": 0}


def as_bytes(obj) -> bytes:
    return json.dumps(obj).encode()


@pytest.fixture(autouse=True)
def _workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_cache()
    yield
    clear_cache()


# --------------------------------------------------------------------------
# Buttons -> trailing links
# --------------------------------------------------------------------------

def test_buttons_move_to_end_in_order():
    text = "Intro [A](buttonurl:https://a.example) middle\nmore\n[B](buttonurl://https://b.example)"
    assert buttons_to_links(text) == (
        "Intro  middle\nmore\n[A](https://a.example)\n[B](https://b.example)")


def test_several_buttons_on_one_line_and_same_suffix():
    text = "Body\n[One](buttonurl:https://1.example)[Two](buttonurl:https://2.example:same)"
    assert buttons_to_links(text) == "Body\n[One](https://1.example)\n[Two](https://2.example)"


def test_button_without_scheme_gets_https_and_other_schemes_kept():
    text = "Hi\n\n[Rules](buttonurl://t.me/SomeBot?start=1)\n[X](buttonurl:tg://resolve?domain=x)"
    assert buttons_to_links(text) == (
        "Hi\n[Rules](https://t.me/SomeBot?start=1)\n[X](tg://resolve?domain=x)")


def test_message_of_only_buttons():
    assert buttons_to_links("[A](buttonurl:https://a.example)") == "[A](https://a.example)"


def test_text_without_buttons_is_untouched():
    text = "plain [link](https://x.example)\n\n  indented"
    assert buttons_to_links(text) == text


# --------------------------------------------------------------------------
# Placeholders, random replies, media kinds
# --------------------------------------------------------------------------

def test_strip_placeholders_keeps_literal_braces():
    text, removed = strip_placeholders(
        '{replytag} Muted {mention} for 1 minute.\nBammed {mention}.\necho "${JAVA_HOME}"')
    assert text == 'Muted for 1 minute.\nBammed.\necho "${JAVA_HOME}"'
    assert removed == ["{replytag}", "{mention}"]


def test_greeting_placeholders_map_or_drop():
    text, removed = map_greeting_placeholders(
        "Hi {first} {last} aka {mention}, {fullname}! Welcome to {chatname}.")
    assert text == "Hi {firstname} {lastname} aka {username}, {firstname} {lastname}! Welcome to."
    assert removed == ["{chatname}"]


def test_first_variant():
    assert first_variant("one\n\n%%%\n\ntwo") == ("one", True)
    assert first_variant("only") == ("only", False)


@pytest.mark.parametrize("file_id,kind", [
    (STICKER_ID, "sticker"), (PHOTO_ID, "photo"), (DOCUMENT_ID, "document"),
    (ANIMATION_ID, "animation"), ("!!not-base64!!", "media"),
])
def test_file_kind(file_id, kind):
    assert file_kind(file_id) == kind


# --------------------------------------------------------------------------
# Length after conversion
# --------------------------------------------------------------------------

def test_link_counts_only_its_label():
    assert rendered_length("ab\n[label](https://very.long.example/" + "x" * 500 + ")") == 8


def test_note_pushed_over_limit_by_button_labels_is_skipped():
    button = "\n[abcdefghij](buttonurl:https://x.example)"  # adds 11 visible chars
    bundle = load(as_bytes(rose_export(notes={"notes": [
        note("fits", "a" * 4085 + button),
        note("over", "a" * 4086 + button),
    ]})))
    assert [e.name for e in bundle.notes] == ["fits"]
    (skip,) = [s for s in bundle.skipped if s.section == "notes"]
    assert skip.name == "over" and "4097/4096" in skip.reason


def test_length_is_counted_in_utf16():
    # 2047 emoji are 4094 UTF-16 units (but only 2047 Python characters).
    body = "😀" * 2047 + "\n[ab](buttonurl:https://x.example)"
    bundle = load(as_bytes(rose_export(notes={"notes": [note("emoji", body)]})))
    assert bundle.notes == []
    assert "4097/4096" in bundle.skipped[0].reason


def test_greeting_url_counts_because_greetings_are_plain_text():
    url = "https://x.example/" + "p" * 100
    text = "w" * 3990 + f"\n[Rules](buttonurl:{url})"
    assert rendered_length(buttons_to_links(text)) < 4096  # would fit as a note
    bundle = load(as_bytes(astrako_export(greetings=[note("welcome", text)])))
    assert bundle.greeting is None
    assert bundle.skipped[0].section == "greetings" and "/4096" in bundle.skipped[0].reason


def test_greeting_length_uses_longest_names():
    assert greeting_length("{firstname}") == 64
    assert greeting_length("{username}") == 33


# --------------------------------------------------------------------------
# Detection: Rose and AstrakoBot only
# --------------------------------------------------------------------------

def test_rose_export_in_a_txt_file():
    bundle = load(as_bytes(rose_export()), "-1001736881201_export.txt")
    assert bundle.source == "Rose"
    assert bundle.source_chat_id == -1001736881201


def test_astrako_export():
    bundle = load(as_bytes(astrako_export()), "export_-1001989274533.json")
    assert bundle.source == "AstrakoBot"
    assert bundle.source_chat_id == -1001989274533


def test_chat_id_from_filename_absent():
    assert chat_id_from_filename("export.json") is None


@pytest.mark.parametrize("content", [
    b"not json",
    b"\xff\xfe garbage",
    as_bytes([1, 2, 3]),
    as_bytes({"-1001665932227": {"bot": 1, "hashes": {"extra": {"#a": "b"}}}}),
    as_bytes({**rose_export(), "bot_id": 123}),
    as_bytes({**astrako_export(), "bot_id": 123}),
    as_bytes({"bot_id": ROSE_ID, "data": {}, "version": 1}),
    as_bytes({"bot_id": ASTRAKO_ID, "chat": {}}),
    b"[" * 100000 + b"]" * 100000,
])
def test_anything_else_is_rejected(content):
    with pytest.raises(UnsupportedExport) as exc:
        load(content)
    assert str(exc.value) == UNSUPPORTED


def test_oversized_file_is_rejected():
    with pytest.raises(UnsupportedExport, match="too large"):
        load(b" " * (1024 * 1024 + 1))


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def test_rose_sections():
    bundle = load(as_bytes(rose_export(
        notes={"notes": [note("docs", "See\n[Wiki](buttonurl:https://w.example)"),
                         note("pic", "\n", PHOTO_ID)]},
        filters={"filters": [note("hi", "{replytag} hello"), note("st", "\n", STICKER_ID)]},
        blocklists={"action": "tmute", "filters": [{"name": "spam"}, {"name": "*.ru"}]},
        greetings={"welcome": {"text": "Hey {first}!", "data_id": ""},
                   "goodbye": {"text": "", "data_id": ""}},
        rules={"content": "Be nice"},
    )))
    assert [(e.name, e.text) for e in bundle.notes] == [
        ("docs", "See\n[Wiki](https://w.example)"), ("rules", "Be nice")]
    assert [(e.name, e.text) for e in bundle.filters] == [("hi", "hello")]
    assert bundle.blocked_words == ["spam"]
    assert bundle.greeting.text == "Hey {firstname}!"
    assert bundle.goodbye is None
    reasons = {(s.section, s.name): s.reason for s in bundle.skipped}
    assert "photo" in reasons[("notes", "pic")]
    assert "sticker" in reasons[("filters", "st")]
    assert "wildcard" in reasons[("blocked words", "*.ru")]
    assert "empty" in reasons[("greetings", "goodbye")]
    assert "antiflood" in bundle.not_imported and "warns" in bundle.not_imported
    assert any("tmute" in w for w in bundle.warnings)


def test_astrako_sections():
    bundle = load(as_bytes(astrako_export(
        chat={"rules": "1) No spam"},
        notes=[note("guide", "Steps"), note("tool", "", DOCUMENT_ID)],
        greetings=[note("welcome", "Hi {mention}\n\n[Rules](buttonurl://t.me/AstrakoBot?start=1)"),
                   note("goodbye", "Bye")],
    )))
    assert [(e.name, e.text) for e in bundle.notes] == [("guide", "Steps"), ("rules", "1) No spam")]
    assert bundle.greeting.text == "Hi {username}\n[Rules](https://t.me/AstrakoBot?start=1)"
    assert any("plain text" in n for n in bundle.greeting.notes)
    assert bundle.goodbye.text == "Bye"
    assert "document" in bundle.skipped[0].reason
    assert "warns" in bundle.not_imported and "locks" in bundle.not_imported


def test_greeting_with_unsupported_braces_is_skipped():
    bundle = load(as_bytes(astrako_export(greetings=[note("welcome", "Hi {nickname}")])))
    assert bundle.greeting is None
    assert "braces" in bundle.skipped[0].reason


# --------------------------------------------------------------------------
# Applying
# --------------------------------------------------------------------------

def _bundle():
    return load(as_bytes(rose_export(
        notes={"notes": [note("a", "A"), note("b", "B")]},
        filters={"filters": [note("hello", "hi there")]},
        blocklists={"filters": [{"name": "Spam  Word"}, {"name": "x" * 65}]},
        greetings={"welcome": {"text": "Hi {first}", "data_id": ""},
                   "goodbye": {"text": "Bye", "data_id": ""}},
        rules={"content": "Rules here"},
    )))


def _stored():
    return (read_notes(GID), read_filters(GID), read_blocked_words(GID),
            {k: v for k, v in read_greetings(GID).items() if v})


def test_preview_writes_nothing():
    report = importer.preview(_bundle(), GID)
    assert report.total == 7
    assert _stored() == ({}, {}, [], {})


def test_apply_writes_through_existing_stores():
    report = importer.apply(_bundle(), GID)
    notes = read_notes(GID)
    assert {n["name"]: n["reply"] for n in notes.values()} == {
        "a": {"type": "text", "data": "A"},
        "b": {"type": "text", "data": "B"},
        "rules": {"type": "text", "data": "Rules here"},
    }
    assert [(name, nid) for name, nid, _ in report.notes] == [("a", "1"), ("b", "2"), ("rules", "3")]
    assert read_filters(GID) == {"hello": {"type": "text", "data": "hi there"}}
    assert read_blocked_words(GID) == ["spam word"]
    assert read_greetings(GID)["greeting"] == "Hi {firstname}"
    assert read_greetings(GID)["goodbye"] == "Bye"
    assert any(s.section == "blocked words" and "1-64" in s.reason for s in report.skipped)


def test_only_existing_stores_are_written():
    importer.apply(_bundle(), GID)
    files = sorted(str(p) for p in Path("runtime").rglob("*") if p.is_file())
    key = str(GID).lstrip("-")
    assert files == sorted([
        f"runtime/filters/{key}_filters",
        f"runtime/notes/{key}_notes.json",
        f"runtime/banned/{key}_words.json",
        f"runtime/greetings/{key}_greetings.json",
    ])


def test_warns_are_never_imported():
    importer.apply(load(as_bytes(astrako_export(notes=[note("n", "x")]))), GID)
    assert not Path("runtime/warns").exists()


def test_merge_keeps_existing_and_preview_matches_apply():
    add_note(GID, "a", reply={"type": "text", "data": "mine"})
    add_filter(GID, "hello", reply={"type": "text", "data": "mine"})
    save_greeting_messages(GID, greeting="Mine")
    preview = importer.preview(_bundle(), GID)
    report = importer.apply(_bundle(), GID)
    assert preview == report
    assert read_notes(GID)["1"]["reply"]["data"] == "mine"
    assert read_filters(GID)["hello"]["data"] == "mine"
    assert read_greetings(GID)["greeting"] == "Mine"
    skipped = {(s.section, s.name) for s in report.skipped}
    assert {("notes", "a"), ("filters", "hello"), ("greetings", "greeting")} <= skipped


def test_replace_overwrites_in_place_keeping_ids():
    add_note(GID, "first", reply={"type": "text", "data": "1"})
    add_note(GID, "a", reply={"type": "text", "data": "mine"})
    add_note(GID, "last", reply={"type": "text", "data": "3"})
    add_filter(GID, "hello", reply={"type": "text", "data": "mine"})
    set_greeting_media(GID, "greeting", "photo", PHOTO_ID)
    report = importer.apply(_bundle(), GID, importer.REPLACE)
    notes = read_notes(GID)
    assert [(k, v["name"], v["reply"]["data"]) for k, v in notes.items()] == [
        ("1", "first", "1"), ("2", "a", "A"), ("3", "last", "3"), ("4", "b", "B"), ("5", "rules", "Rules here")]
    assert ("a", "2", True) in report.notes
    assert read_filters(GID)["hello"]["data"] == "hi there"
    greetings = read_greetings(GID)
    assert greetings["greeting"] == "Hi {firstname}" and greetings["greeting_media_id"] is None


def test_filter_limit_is_the_bots_own():
    for i in range(MAX_FILTERS_PER_CHAT - 1):
        add_filter(GID, f"k{i}", reply={"type": "text", "data": "x"})
    bundle = load(as_bytes(rose_export(filters={"filters": [
        note("new1", "x"), note("new2", "x"), note("new3", "x")]})))
    preview = importer.preview(bundle, GID)
    report = importer.apply(bundle, GID)
    assert preview == report
    assert [k for k, _ in report.filters] == ["new1"]
    assert [s.name for s in report.skipped if "limit" in s.reason] == ["new2", "new3"]
    assert len(read_filters(GID)) == MAX_FILTERS_PER_CHAT


def test_duplicates_inside_the_export():
    bundle = load(as_bytes(rose_export(
        notes={"notes": [note("a", "1"), note("a", "2")]},
        filters={"filters": [note("Hi", "1"), note("hi", "2")]},
        blocklists={"filters": [{"name": "x"}, {"name": "X"}]},
    )))
    report = importer.apply(bundle, GID)
    assert len(report.notes) == 1 and len(report.filters) == 1 and report.words == ["x"]
    assert [(s.section, s.name) for s in report.skipped if s.section != "greetings"] == [
        ("notes", "a"), ("filters", "hi"), ("blocked words", "X")]


# --------------------------------------------------------------------------
# Snapshot / undo
# --------------------------------------------------------------------------

def _import_with_snapshot(bundle, mode=importer.MERGE):
    snapshot.take(GID)
    report = importer.apply(bundle, GID, mode)
    snapshot.seal(GID)
    return report


def test_undo_restores_previous_state():
    add_note(GID, "a", reply={"type": "text", "data": "mine"})
    read_notes(GID)  # warm the read cache
    _import_with_snapshot(_bundle(), importer.REPLACE)
    assert read_notes(GID)["1"]["reply"]["data"] == "A"
    assert snapshot.restore(GID) == (snapshot.RESTORED, [])
    assert read_notes(GID) == {"1": {"name": "a", "reply": {"type": "text", "data": "mine"}}}
    # Stores that didn't exist before the import are gone again.
    assert read_filters(GID) == {} and read_blocked_words(GID) == []
    assert not Path(f"runtime/imports/{str(GID).lstrip('-')}").exists()


def test_undo_refuses_after_later_changes_unless_forced():
    _import_with_snapshot(_bundle())
    add_filter(GID, "later", reply={"type": "text", "data": "x"})
    assert snapshot.restore(GID) == (snapshot.CHANGED, ["filters"])
    assert "later" in read_filters(GID)
    assert snapshot.restore(GID, force=True)[0] == snapshot.RESTORED
    assert read_filters(GID) == {}


def test_undo_window_and_nothing_to_undo():
    assert snapshot.restore(GID) == (snapshot.NONE, [])
    _import_with_snapshot(_bundle())
    import time
    assert snapshot.restore(GID, now=time.time() + 24 * 3600 + 1) == (snapshot.EXPIRED, [])
    assert snapshot.restore(GID) == (snapshot.NONE, [])
    assert read_notes(GID)  # import kept


# --------------------------------------------------------------------------
# Telegram flow
# --------------------------------------------------------------------------

class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeBot:
    def __init__(self, content):
        self.content = content
        self.replies, self.edits, self.sent, self.answers = [], [], [], []
        self._next_id = 500

    async def reply_to(self, m, text, **kw):
        self._next_id += 1
        self.replies.append((text, kw))
        return _Obj(message_id=self._next_id)

    async def get_file(self, file_id):
        return _Obj(file_path="documents/file.json")

    async def download_file(self, path):
        return self.content

    async def answer_callback_query(self, cid, text=None, show_alert=False):
        self.answers.append(text)

    async def edit_message_text(self, text, chat_id, message_id, **kw):
        self.edits.append(text)

    async def send_message(self, chat_id, text, **kw):
        self.sent.append(text)


@pytest.fixture
def flow(monkeypatch):
    from modules import migrate as mod

    async def admin(chat_id, user_id, **kw):
        return user_id == 7

    def make(content):
        fake = FakeBot(content)
        for name in ("reply_to", "get_file", "download_file", "answer_callback_query",
                     "edit_message_text", "send_message"):
            monkeypatch.setattr(mod.bot, name, getattr(fake, name))
        monkeypatch.setattr(mod, "is_privileged", admin)
        mod._PENDING.clear()
        return fake

    yield mod, make
    mod._PENDING.clear()


def _cmd(user_id=7, document=True, text="/import"):
    doc = _Obj(file_id="F", file_size=100, file_name=f"export_{GID}.json") if document else None
    return _Obj(
        text=text, caption=None, message_id=10, message_thread_id=None,
        chat=_Obj(id=GID, type="supergroup"), from_user=_Obj(id=user_id),
        reply_to_message=_Obj(document=doc) if document else None,
    )


def _call(action, owner=7, presser=7, message_id=501):
    return _Obj(id="c", data=f"imp:{action}:{owner}", from_user=_Obj(id=presser),
                message=_Obj(chat=_Obj(id=GID), message_id=message_id, message_thread_id=None))


def test_import_flow_merge(flow):
    mod, make = flow
    fake = make(as_bytes(_bundle_export()))
    asyncio.run(mod.import_command(_cmd()))
    assert "Rose export" in fake.replies[0][0]
    assert read_notes(GID) == {}  # preview only

    asyncio.run(mod.handle_import_callback(_call("merge", presser=8)))
    assert "Only the admin" in fake.answers[-1]
    assert read_notes(GID) == {}

    asyncio.run(mod.handle_import_callback(_call("merge")))
    assert "Imported from Rose" in fake.edits[-1]
    assert {n["name"] for n in read_notes(GID).values()} == {"a", "b", "rules"}

    # A second press finds nothing pending and leaves the report alone.
    asyncio.run(mod.handle_import_callback(_call("merge")))
    assert "no longer pending" in fake.answers[-1]
    assert len(fake.edits) == 1


def test_superseded_preview_buttons_are_stale(flow):
    mod, make = flow
    fake = make(as_bytes(_bundle_export()))
    asyncio.run(mod.import_command(_cmd()))
    asyncio.run(mod.import_command(_cmd()))
    asyncio.run(mod.handle_import_callback(_call("merge", message_id=501)))
    assert "no longer pending" in fake.answers[-1]
    asyncio.run(mod.handle_import_callback(_call("cancel", message_id=502)))
    assert fake.edits == ["Import cancelled."]
    assert read_notes(GID) == {}


def test_import_rejections(flow):
    mod, make = flow
    fake = make(b'{"some": "other bot"}')
    asyncio.run(mod.import_command(_cmd()))
    asyncio.run(mod.import_command(_cmd(document=False)))
    asyncio.run(mod.import_command(_cmd(user_id=8)))
    assert [r[0] for r in fake.replies] == [
        UNSUPPORTED, "Reply to a Rose or AstrakoBot export file with /import.", "Admins only."]
    assert mod._PENDING == {}


def test_importundo_command(flow):
    mod, make = flow
    fake = make(as_bytes(_bundle_export()))
    asyncio.run(mod.import_undo(_cmd(text="/importundo")))
    asyncio.run(mod.import_command(_cmd()))  # preview is message 502
    asyncio.run(mod.handle_import_callback(_call("merge", message_id=502)))
    asyncio.run(mod.import_undo(_cmd(text="/importundo")))
    assert fake.replies[0][0] == "There's no import to undo here."
    assert fake.replies[-1][0].startswith("Import undone.")
    assert read_notes(GID) == {}


def test_report_is_split_into_telegram_sized_messages():
    from modules.migrate import render_report
    bundle = load(as_bytes(rose_export(
        notes={"notes": [note(f"note_{i:03}_" + "n" * 40, "x") for i in range(300)]})))
    chunks = render_report(bundle, importer.preview(bundle, GID))
    assert len(chunks) > 1 and all(len(c) <= 4000 for c in chunks)


def test_report_lines_stay_short_with_hostile_names():
    from modules.migrate import render_report
    bundle = load(as_bytes(rose_export(
        notes={"notes": [note("n" * 5000, "x")]},
        blocklists={"filters": [{"name": f"w{i:02}" + "w" * 60} for i in range(200)]},
    )))
    chunks = render_report(bundle, importer.preview(bundle, GID))
    assert all(len(c) <= 4000 for c in chunks)
    assert all(len(line) < 400 for c in chunks for line in c.split("\n"))


def _bundle_export():
    return rose_export(
        notes={"notes": [note("a", "A"), note("b", "B")]},
        rules={"content": "Rules here"},
    )
