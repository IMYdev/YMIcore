from info import bot
from telebot.formatting import (format_text, hbold, hcode, hitalic)
from telebot.types import (InlineKeyboardButton, InlineKeyboardMarkup)

from core import broadcast
from core.activity import log_event, user_label
from core.formatting import markdown_to_html
from core.utils import handle_errors, get_media_info
from core.users import audience_counts, record_user, set_opt_out
from web.auth import is_owner

SEGMENT_FLAGS = ("users", "groups")

BROADCAST_HELP = format_text(
    hbold("Broadcast"),
    hitalic("Send an update to everyone who has interacted with the bot."),
    "",
    f"{hbold('/broadcast')} [users|groups] {hcode('<message>')}",
    f"{hbold('/bcast_list')} List recent broadcasts.",
    f"{hbold('/bcast_delete')} {hcode('<id>')} Delete a broadcast from every chat.",
    f"{hbold('/unsub')} Stop receiving broadcasts.",
    f"{hbold('/sub')} Resume receiving broadcasts.",
)


def _media_from(message):
    if not message:
        return None
    media_type, file_id = get_media_info(message)
    if media_type is None:
        return None
    return {"type": media_type, "file_id": file_id}


def _audience_line(segment) -> str:
    counts = audience_counts(segment)
    return f"{counts['users']} users, {counts['groups']} groups"


def _remember(m) -> None:
    """Make sure the sender has a registry entry before touching their flags."""
    record_user(
        getattr(m.from_user, "id", None),
        user_label(m.from_user), getattr(m.from_user, "username", None),
    )


def _preview_markup(token) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Send now", callback_data=f"bc_send:{token}"),
        InlineKeyboardButton("Cancel", callback_data=f"bc_cancel:{token}"),
    )
    return markup


def _link_markup(button):
    if not button:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(button["text"], url=button["url"]))
    return markup


async def _show_preview(m, pending, token):
    """Show the owner what the recipients will actually receive."""
    counts = audience_counts(pending.get("segment"))
    header = [
        hbold("Preview — not sent yet"),
        f"{hitalic('Audience:')} {_audience_line(pending.get('segment'))}",
        f"{hitalic('Recipients:')} {hcode(str(counts['total']))}",
        f"{hitalic('Expires in:')} {broadcast.PENDING_TTL // 60} minutes",
    ]
    button = pending.get("button")
    body = markdown_to_html(pending.get("text") or "")
    media = pending.get("media")
    sender = getattr(bot, f"send_{media['type']}", None) if media else None

    if sender is None and not body:
        return await bot.send_message(m.chat.id, format_text(*header), parse_mode="HTML",
                                      reply_markup=_preview_markup(token))

    if sender is not None:
        if button:
            header.append(f"{hitalic('Button:')} {hcode(button['url'])}")
        caption = format_text(*header, "", body) if body else format_text(*header)
        sent = await sender(m.chat.id, media["file_id"], caption=caption, parse_mode="HTML")
    else:
        extra = {} if pending.get("preview", True) else {"disable_web_page_preview": True}
        sent = await bot.send_message(m.chat.id, format_text(*header, "", body),
                                      parse_mode="HTML", reply_markup=_link_markup(button), **extra)

    return await bot.edit_message_reply_markup(sent.chat.id, sent.message_id,
                                               reply_markup=_preview_markup(token))


@handle_errors
async def broadcast_command(m):
    if not is_owner(m.from_user.id):
        return await bot.reply_to(m, "Owner only.")

    if m.chat.type != "private":
        return await bot.reply_to(m, "Broadcasts are sent from a private chat with me.")

    if broadcast.is_running():
        return await bot.reply_to(m, "A broadcast is already running.")

    text = m.text or m.caption or ""
    # Drop the command itself, then an optional audience flag.
    parts = text.split(maxsplit=1)
    body = parts[1] if len(parts) > 1 else ""
    segment = "both"
    flag = body.split(maxsplit=1)
    if flag and flag[0].lower() in SEGMENT_FLAGS:
        segment = flag[0].lower()
        body = flag[1] if len(flag) > 1 else ""
    text = body

    source = m.reply_to_message
    media = _media_from(source)
    if not text.strip() and source is not None:
        text = source.caption or ""

    if not text.strip() and not media:
        return await bot.send_message(m.chat.id, BROADCAST_HELP, parse_mode="HTML")

    if not audience_counts(segment)["total"]:
        return await bot.reply_to(m, "Nobody to broadcast to yet.")

    token = broadcast.stage_pending(text, media=media, segment=segment)
    await _show_preview(m, broadcast.get_pending(token), token)

    log_event(
        "broadcast",
        chat_id=m.chat.id, user_id=m.from_user.id,
        detail=f"staged {segment}: {_audience_line(segment)}",
    )


@handle_errors
async def broadcast_list(m):
    if not is_owner(m.from_user.id):
        return await bot.reply_to(m, "Owner only.")

    records = broadcast.list_broadcasts(limit=15)
    if not records:
        return await bot.reply_to(m, "No broadcasts sent yet.")

    lines = []
    for record in records:
        flags = [record.get("segment", "both")]
        if record.get("recalled"):
            flags.append("recalled")
        lines.append(
            f"{hcode('#' + str(record['id']))} {hitalic(' | '.join(flags))} — "
            f"{record.get('sent', 0)} sent, "
            f"{record.get('failed', 0)} failed, "
            f"{record.get('dead', 0)} unreachable"
        )
    await bot.send_message(
        m.chat.id, format_text(hbold("Recent broadcasts"), *lines), parse_mode="HTML",
    )


@handle_errors
async def broadcast_delete(m):
    if not is_owner(m.from_user.id):
        return await bot.reply_to(m, "Owner only.")

    args = m.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        return await bot.reply_to(m, "Usage: /bcast_delete <id>")

    broadcast_id = int(args[1].strip())
    if broadcast.get_broadcast(broadcast_id) is None:
        return await bot.reply_to(m, f"No broadcast with ID {broadcast_id}.")

    result = await broadcast.recall(broadcast_id)
    await bot.reply_to(
        m,
        f"Deleted {result['deleted']} of {result['total']} messages "
        f"from broadcast #{broadcast_id}."
        + (f" {result['failed']} could not be removed." if result["failed"] else ""),
    )


@handle_errors
async def unsubscribe(m):
    if m.chat.type != "private":
        return await bot.reply_to(m, "Use this in a private chat with me.")
    _remember(m)
    if set_opt_out(m.from_user.id, True):
        return await bot.reply_to(m, "You will no longer receive broadcasts.")
    await bot.reply_to(m, "You are already unsubscribed.")


@handle_errors
async def subscribe(m):
    if m.chat.type != "private":
        return await bot.reply_to(m, "Use this in a private chat with me.")
    _remember(m)
    if set_opt_out(m.from_user.id, False):
        return await bot.reply_to(m, "You will receive broadcasts again.")
    await bot.reply_to(m, "You are already subscribed.")


async def handle_broadcast_callback(call):
    """Confirm or discard a staged broadcast from its inline buttons."""
    action, _, token = call.data.partition(":")
    if not is_owner(call.from_user.id):
        return await bot.answer_callback_query(call.id, "Owner only.", show_alert=True)

    pending = broadcast.get_pending(token)
    if pending is None:
        broadcast.clear_pending(token)
        await bot.answer_callback_query(call.id, "This preview expired.", show_alert=True)
        return await bot.edit_message_text("Preview expired.", call.message.chat.id,
                                           call.message.message_id)

    if action == "bc_cancel":
        broadcast.clear_pending(token)
        await bot.answer_callback_query(call.id, "Cancelled.")
        return await bot.edit_message_text("Broadcast cancelled.", call.message.chat.id,
                                           call.message.message_id)

    if broadcast.is_running():
        return await bot.answer_callback_query(call.id, "A broadcast is already running.",
                                               show_alert=True)

    record = broadcast.create_broadcast(
        pending.get("text"), media=pending.get("media"), segment=pending.get("segment"),
        button=pending.get("button"), preview=pending.get("preview", True),
    )
    broadcast.clear_pending(token)
    broadcast.start_delivery(record["id"], call.message.chat.id, call.message.message_id,
                             owner_id=call.from_user.id)
    await bot.answer_callback_query(call.id, f"Broadcast #{record['id']} started.")
    await bot.edit_message_text(
        format_text(hbold("Broadcast started"), hitalic("Delivering in the background...")),
        call.message.chat.id, call.message.message_id, parse_mode="HTML",
    )


__all__ = [
    "broadcast_command", "broadcast_delete", "broadcast_list", "handle_broadcast_callback",
    "subscribe", "unsubscribe",
]
