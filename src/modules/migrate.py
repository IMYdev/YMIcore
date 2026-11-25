"""/import and /importundo: bring a group over from Rose or AstrakoBot.

/import (as a reply to the export file) shows a preview with Merge /
Replace / Cancel buttons; nothing is written until one is pressed.
"""

import time

from telebot.formatting import escape_html, hbold, hcode
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import bot
from core.migrate import MAX_EXPORT_BYTES, UnsupportedExport, load
from core.migrate import apply as importer
from core.migrate import snapshot
from core.utils import get_args, handle_errors, is_privileged, log_error, topic_kwargs

PENDING_TTL_SECONDS = 600
MAX_CHUNK = 4000
PREVIEW_SKIP_LINES = 15

# (chat_id, user_id) -> {"bundle", "expires"}
_PENDING = {}


# --------------------------------------------------------------------------
# Rendering (pure, so it can be tested without Telegram)
# --------------------------------------------------------------------------

def _counts(report) -> str:
    parts = []
    if report.notes:
        parts.append(f"{len(report.notes)} notes")
    if report.filters:
        parts.append(f"{len(report.filters)} filters")
    if report.words:
        parts.append(f"{len(report.words)} blocked words")
    for event, _ in report.greetings:
        parts.append(event)
    return ", ".join(parts) or "nothing"


MAX_SHOWN_NAME = 64


def _short(text, limit=MAX_SHOWN_NAME) -> str:
    """Bound anything taken from the export, so no report line can outgrow a message."""
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _skip_line(skip) -> str:
    return f"• {escape_html(skip.section)} {hcode(_short(skip.name))}: {escape_html(skip.reason)}"


def _footer(bundle) -> list[str]:
    lines = []
    if bundle.not_imported:
        lines += ["", hbold("Not imported (no equivalent here):"),
                  escape_html(", ".join(bundle.not_imported))]
    if bundle.warnings:
        lines += [""] + [f"⚠️ {escape_html(w)}" for w in bundle.warnings]
    return lines


def render_preview(bundle, merge, replace, chat_id) -> str:
    lines = [hbold(f"{bundle.source} export"), ""]
    if bundle.source_chat_id and bundle.source_chat_id != chat_id:
        lines += [f"⚠️ This export is from chat {hcode(str(bundle.source_chat_id))}, "
                  f"not this one ({hcode(str(chat_id))}).", ""]
    lines.append(f"{hbold('Merge')} (keep what's here): {escape_html(_counts(merge))}")
    if replace.replaced:
        lines.append(f"{hbold('Replace')} (overwrite {replace.replaced} with the same name): "
                     f"{escape_html(_counts(replace))}")
    skipped = [s for s in merge.skipped]
    if skipped:
        lines += ["", hbold(f"Skipped in merge ({len(skipped)}):")]
        lines += [_skip_line(s) for s in skipped[:PREVIEW_SKIP_LINES]]
        if len(skipped) > PREVIEW_SKIP_LINES:
            lines.append(f"…and {len(skipped) - PREVIEW_SKIP_LINES} more, listed after the import.")
    lines += _footer(bundle)
    return "\n".join(lines)


def render_report(bundle, report) -> list[str]:
    """The full post-import report, split into Telegram-sized messages."""
    lines = [hbold(f"Imported from {bundle.source}") + f" ({report.mode}): "
             + escape_html(_counts(report))]
    if report.notes:
        lines += ["", hbold("Notes") + " (fetch with #number):"]
        lines += [f"• {hcode(_short(name))} → #{nid}" + (" (replaced)" if replaced else "")
                  for name, nid, replaced in report.notes]
    if report.filters:
        lines += ["", hbold("Filters:")]
        lines += [f"• {hcode(_short(k))}" + (" (replaced)" if replaced else "")
                  for k, replaced in report.filters]
    if report.words:
        lines += ["", hbold("Blocked words:")]
        lines += [f"• {hcode(w)}" for w in report.words]
    if report.greetings:
        lines += ["", hbold("Greetings:")]
        lines += [f"• {e}" + (" (replaced)" if replaced else "") for e, replaced in report.greetings]
    if report.changes:
        lines += ["", hbold("Changed while converting:")]
        lines += [f"• {escape_html(_short(c, 300))}" for c in report.changes]
    if report.skipped:
        lines += ["", hbold(f"Skipped ({len(report.skipped)}):")]
        lines += [_skip_line(s) for s in report.skipped]
    lines += _footer(bundle)
    lines += ["", "Undo with /importundo within 24 hours."]
    return chunk_lines(lines)


def chunk_lines(lines, limit=MAX_CHUNK) -> list[str]:
    chunks, current, size = [], [], 0
    for line in lines:
        if current and size + len(line) + 1 > limit:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def _keyboard(user_id, offer_replace) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton("Merge", callback_data=f"imp:merge:{user_id}")]
    if offer_replace:
        buttons.append(InlineKeyboardButton("Replace", callback_data=f"imp:replace:{user_id}"))
    buttons.append(InlineKeyboardButton("Cancel", callback_data=f"imp:cancel:{user_id}"))
    markup.add(*buttons)
    return markup


def _drop_expired(now) -> None:
    for key in [k for k, v in _PENDING.items() if v["expires"] <= now]:
        del _PENDING[key]


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@handle_errors
async def import_command(m):
    if m.chat.type == "private":
        return await bot.reply_to(m, "Use /import in the group you want to import into.")
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    doc = getattr(m.reply_to_message, "document", None) if m.reply_to_message else None
    if not doc:
        return await bot.reply_to(m, "Reply to a Rose or AstrakoBot export file with /import.")
    if (doc.file_size or 0) > MAX_EXPORT_BYTES:
        return await bot.reply_to(m, "That file is too large to be an export (limit 1 MB).")

    file_info = await bot.get_file(doc.file_id)
    content = await bot.download_file(file_info.file_path)
    try:
        bundle = load(content, doc.file_name or "")
    except UnsupportedExport as e:
        return await bot.reply_to(m, str(e))

    merge = importer.preview(bundle, m.chat.id, importer.MERGE)
    replace = importer.preview(bundle, m.chat.id, importer.REPLACE)

    sent = await bot.reply_to(
        m, render_preview(bundle, merge, replace, m.chat.id), parse_mode="HTML",
        reply_markup=_keyboard(m.from_user.id, replace.replaced > 0),
    )
    now = time.time()
    _drop_expired(now)
    # A newer /import replaces this admin's pending one; old buttons go stale.
    _PENDING[(m.chat.id, m.from_user.id)] = {
        "bundle": bundle, "message_id": sent.message_id, "expires": now + PENDING_TTL_SECONDS,
    }


async def handle_import_callback(call):
    try:
        await _import_callback(call)
    except Exception as e:
        await log_error(bot, e, call)


async def _import_callback(call):
    try:
        _, action, owner = call.data.split(":", 2)
        owner = int(owner)
    except ValueError:
        return await bot.answer_callback_query(call.id)
    chat_id, message_id = call.message.chat.id, call.message.message_id

    if call.from_user.id != owner:
        return await bot.answer_callback_query(
            call.id, "Only the admin who started this import can use these buttons.", show_alert=True)

    _drop_expired(time.time())
    key = (chat_id, owner)
    pending = _PENDING.get(key)
    if pending is None or pending["message_id"] != message_id:
        # Expired, already used, or superseded by a newer /import.
        return await bot.answer_callback_query(
            call.id, "This import is no longer pending. Reply to the file with /import again.",
            show_alert=True)
    del _PENDING[key]
    await bot.answer_callback_query(call.id)

    if action == "cancel":
        return await bot.edit_message_text("Import cancelled.", chat_id, message_id)
    if action not in (importer.MERGE, importer.REPLACE):
        return
    if not await is_privileged(chat_id, owner):
        return await bot.edit_message_text("Admins only.", chat_id, message_id)

    bundle = pending["bundle"]
    snapshot.take(chat_id)
    try:
        report = importer.apply(bundle, chat_id, action)
    except Exception as e:
        snapshot.restore(chat_id, force=True)
        await log_error(bot, e, call)
        return await bot.edit_message_text(
            "The import failed and nothing was changed. The error has been logged.",
            chat_id, message_id)
    snapshot.seal(chat_id)

    chunks = render_report(bundle, report)
    await bot.edit_message_text(chunks[0], chat_id, message_id, parse_mode="HTML")
    kwargs = topic_kwargs(call.message)
    for chunk in chunks[1:]:
        await bot.send_message(chat_id, chunk, parse_mode="HTML", **kwargs)


@handle_errors
async def import_undo(m):
    if m.chat.type == "private":
        return await bot.reply_to(m, "Use /importundo in the group the import went into.")
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    force = "force" in [a.lower() for a in get_args(m)]
    status, changed = snapshot.restore(m.chat.id, force=force)
    if status == snapshot.NONE:
        return await bot.reply_to(m, "There's no import to undo here.")
    if status == snapshot.EXPIRED:
        return await bot.reply_to(m, "The last import is more than 24 hours old and can't be undone.")
    if status == snapshot.CHANGED:
        return await bot.reply_to(
            m, f"{', '.join(changed).capitalize()} changed since the import. Undoing would also "
               "discard those changes. Send /importundo force to undo anyway.")
    await bot.reply_to(m, "Import undone. Notes, filters, blocked words and greetings are back "
                          "to how they were before it.")
