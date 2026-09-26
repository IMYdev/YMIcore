import asyncio
import secrets
import time
from datetime import date

from info import bot
from telebot.asyncio_helper import ApiTelegramException
from telebot.types import (InlineKeyboardButton, InlineKeyboardMarkup)
from telebot.util import smart_split

from core.activity import log_event
from core.formatting import markdown_to_html
from core.imysdb import IMYDB
from core.users import broadcast_targets, mark_dead, normalise_segment

PENDING_PATH = "runtime/broadcasts/pending.json"
REGISTRY_PATH = "runtime/broadcasts/registry.json"

# How long a staged broadcast stays confirmable before it is discarded.
PENDING_TTL = 600

# Sent broadcasts are forgotten after this many days. Telegram only allows
# deleting messages up to ~48h old, so the recall window is never the limit here.
RETENTION_DAYS = 7

# Telegram allows roughly 30 messages a second globally, so sends go out in
# small batches with a pause between them.
BATCH_SIZE = 20
BATCH_PAUSE = 0.5

# Telegram truncates longer messages. The raw text is split before it is
# converted to HTML, so tags are never cut in half, and the limits leave
# headroom for HTML escaping to grow the text.
MESSAGE_LIMIT = 3500
CAPTION_LIMIT = 900

DEAD_MARKERS = (
    "bot was blocked",
    "bot is blocked",
    "user is deactivated",
    "user_deactivated",
    "bot can't initiate conversation",
    "bot can’t initiate conversation",
)

_active: dict = {}
_last_pruned = None


def chunk_list(items, chunk_size=BATCH_SIZE):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

def _registry() -> IMYDB:
    return IMYDB(REGISTRY_PATH)


def _pending_db() -> IMYDB:
    return IMYDB(PENDING_PATH)


def prune() -> None:
    """Forget broadcasts older than the retention window, at most once a day."""
    global _last_pruned
    today = date.today()
    if _last_pruned == today:
        return
    _last_pruned = today

    db = _registry()
    records = db.get("broadcasts", {})
    cutoff = time.time() - RETENTION_DAYS * 86400
    kept = {
        bid: record for bid, record in records.items()
        if (record.get("created_at") or 0) >= cutoff
    }
    if len(kept) != len(records):
        db.set("broadcasts", kept)


def _update_record(broadcast_id, changes) -> dict:
    db = _registry()
    records = db.get("broadcasts", {})
    key = str(broadcast_id)
    record = records.get(key)
    if record is None:
        return {}
    record.update(changes)
    records[key] = record
    db.set("broadcasts", records)
    return record


def list_broadcasts(limit=None) -> list:
    prune()
    records = _registry().get("broadcasts", {})
    result = [records[key] for key in sorted(records, key=int, reverse=True)]
    return result[:limit] if limit else result


def get_broadcast(broadcast_id) -> dict | None:
    prune()
    if broadcast_id is None:
        return None
    # Ids arrive from the panel and from inline buttons, so they are not
    # trusted - IMYDB reads "." as a path separator.
    try:
        key = str(int(broadcast_id))
    except (TypeError, ValueError):
        return None
    return _registry().get(f"broadcasts.{key}")


# --------------------------------------------------------------------------
# Staging, so nothing is sent before the owner confirms the preview
# --------------------------------------------------------------------------

def _drop_expired(pending: dict) -> dict:
    cutoff = time.time() - PENDING_TTL
    return {
        token: item for token, item in pending.items()
        if (item.get("created_at") or 0) >= cutoff
    }


def stage_pending(text, media=None, segment="both", button=None, preview=True) -> str:
    db = _pending_db()
    pending = _drop_expired(db.get("pending", {}))
    token = secrets.token_hex(6)
    pending[token] = {
        "text": text,
        "media": media,
        "segment": normalise_segment(segment),
        "button": button,
        "preview": bool(preview),
        "created_at": time.time(),
    }
    db.set("pending", pending)
    return token


def get_pending(token):
    if not token:
        return None
    return _drop_expired(_pending_db().get("pending", {})).get(token)


def clear_pending(token) -> None:
    db = _pending_db()
    pending = db.get("pending", {})
    if token in pending:
        del pending[token]
        db.set("pending", pending)


def create_broadcast(text, media=None, segment="both", button=None, preview=True) -> dict:
    prune()
    db = _registry()
    records = db.get("broadcasts", {})
    next_id = max((int(key) for key in records), default=0) + 1
    record = {
        "id": next_id,
        "created_at": time.time(),
        "text": text,
        "media": media,
        "segment": normalise_segment(segment),
        "button": button,
        "preview": bool(preview),
        "deliveries": {},
        "sent": 0,
        "failed": 0,
        "dead": 0,
        "recalled": False,
    }
    records[str(next_id)] = record
    db.set("broadcasts", records)
    return record


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------

def is_running() -> bool:
    return bool(_active)


def active_broadcast() -> dict:
    return {k: v for k, v in _active.items() if k != "task"}


def _build_markup(button) -> InlineKeyboardMarkup | None:
    if not button:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(button["text"], url=button["url"]))
    return markup


def _parts(record, limit) -> list:
    """Split the raw text, then render each part, so escaping cannot push a
    part past the limit and tags are never split across messages."""
    raw = record.get("text") or ""
    if not raw.strip():
        return []
    return [markdown_to_html(chunk) for chunk in smart_split(raw, limit)]


async def _send_one(chat_id, record):
    common = {"disable_notification": True}
    markup = _build_markup(record.get("button"))
    if markup:
        common["reply_markup"] = markup

    media = record.get("media")
    sender = getattr(bot, f"send_{media['type']}", None) if media else None
    parts = _parts(record, CAPTION_LIMIT if sender else MESSAGE_LIMIT)

    if sender is not None:
        sent = await sender(
            chat_id, media["file_id"],
            caption=parts[0] if parts else None,
            parse_mode="HTML" if parts else None,
            **common,
        )
        for part in parts[1:]:
            await bot.send_message(chat_id, part, parse_mode="HTML", disable_notification=True)
        return sent

    if not parts:
        return await bot.send_message(chat_id, " ", **common)

    extra = {} if record.get("preview", True) else {"disable_web_page_preview": True}
    sent = await bot.send_message(chat_id, parts[0], parse_mode="HTML", **common, **extra)
    for part in parts[1:]:
        await bot.send_message(chat_id, part, parse_mode="HTML", disable_notification=True)
    return sent


def _classify_error(exc) -> str:
    """Bucket a send failure as retryable, unreachable, or simply failed."""
    if not isinstance(exc, ApiTelegramException):
        return "failed"
    if exc.error_code == 429:
        return "retry"
    if any(marker in (exc.description or "").lower() for marker in DEAD_MARKERS):
        return "dead"
    return "failed"


def _retry_after(exc, default=5.0) -> float:
    params = (getattr(exc, "result_json", None) or {}).get("parameters") or {}
    try:
        return float(params.get("retry_after", default))
    except (TypeError, ValueError):
        return default


async def _deliver_to(chat_id, record):
    try:
        return await _send_one(chat_id, record)
    except ApiTelegramException as exc:
        if exc.error_code != 429:
            raise
        await asyncio.sleep(_retry_after(exc))
        return await _send_one(chat_id, record)


def _progress_text(record, total, done, sent, failed, dead, finished=False) -> str:
    header = "Broadcast sent" if finished else "Broadcast running"
    lines = [
        f"<b>{header}</b>  #{record['id']}",
        f"Audience: {done}/{total} chats",
        f"Sent: {sent}",
        f"Failed: {failed}",
        f"Unreachable: {dead}",
    ]
    if finished:
        lines.append("Use /bcast_delete to remove these messages.")
    return "\n".join(lines)


async def _edit_status(chat_id, message_id, html) -> None:
    if not message_id:
        return
    try:
        await bot.edit_message_text(html, chat_id=chat_id, message_id=message_id, parse_mode="HTML")
    except Exception as exc:
        if "message is not modified" not in str(exc):
            print(f"[!] Broadcast status update failed: {exc}")


async def _deliver(broadcast_id, status_chat_id, status_message_id):
    record = get_broadcast(broadcast_id)
    if record is None:
        _active.clear()
        return

    targets = broadcast_targets(record.get("segment"))
    total = len(targets)
    _active["total"] = total

    if not total:
        await bot.send_message(status_chat_id, "No recipients for this broadcast.")
        _active.clear()
        return

    try:
        sent = failed = dead = 0
        deliveries = {}
        for batch in chunk_list(targets):
            results = await asyncio.gather(
                *(_deliver_to(chat_id, record) for chat_id in batch),
                return_exceptions=True,
            )
            for chat_id, result in zip(batch, results):
                if isinstance(result, BaseException):
                    if _classify_error(result) == "dead":
                        dead += 1
                        mark_dead(chat_id)
                    else:
                        failed += 1
                    continue
                deliveries[str(chat_id)] = result.message_id
                sent += 1

            done = sent + failed + dead
            _active.update({"done": done, "sent": sent, "failed": failed, "dead": dead})
            await _edit_status(
                status_chat_id, status_message_id,
                _progress_text(record, total, done, sent, failed, dead),
            )
            await asyncio.sleep(BATCH_PAUSE)

        _update_record(broadcast_id, {
            "deliveries": deliveries, "sent": sent, "failed": failed, "dead": dead,
        })
        log_event(
            "broadcast",
            user_id=_active.get("owner_id"),
            detail=f"#{record['id']} {sent} sent, {failed} failed, {dead} unreachable",
        )
        await _edit_status(
            status_chat_id, status_message_id,
            _progress_text(record, total, total, sent, failed, dead, finished=True),
        )
    finally:
        _active.clear()


def start_delivery(broadcast_id, status_chat_id, status_message_id=None, owner_id=None):
    """Deliver in the background so polling and the panel keep running."""
    if _active:
        return None
    _active.update({
        "id": int(broadcast_id),
        "chat_id": status_chat_id,
        "message_id": status_message_id,
        "owner_id": owner_id,
        "total": 0, "done": 0, "sent": 0, "failed": 0, "dead": 0,
    })
    _active["task"] = asyncio.create_task(
        _deliver(broadcast_id, status_chat_id, status_message_id)
    )
    return _active["task"]


# --------------------------------------------------------------------------
# Recall
# --------------------------------------------------------------------------

async def recall(broadcast_id) -> dict:
    """Delete every message a broadcast delivered, chat by chat."""
    record = get_broadcast(broadcast_id)
    if record is None:
        return {"deleted": 0, "failed": 0, "total": 0}

    pairs = [(int(chat_id), message_id) for chat_id, message_id in (record.get("deliveries") or {}).items()]
    deleted = failed = 0
    for batch in chunk_list(pairs):
        results = await asyncio.gather(
            *(bot.delete_message(chat_id, message_id) for chat_id, message_id in batch),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                failed += 1
            else:
                deleted += 1
        await asyncio.sleep(BATCH_PAUSE)

    _update_record(broadcast_id, {
        "recalled": True, "deleted": deleted, "delete_failed": failed,
    })
    return {"deleted": deleted, "failed": failed, "total": len(pairs)}


__all__ = [
    "BATCH_PAUSE", "BATCH_SIZE", "PENDING_PATH", "PENDING_TTL", "REGISTRY_PATH",
    "RETENTION_DAYS", "active_broadcast", "chunk_list", "clear_pending",
    "create_broadcast", "get_broadcast", "get_pending", "is_running",
    "list_broadcasts", "prune", "recall", "stage_pending", "start_delivery",
]
