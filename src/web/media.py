import io
from aiohttp import web

from info import bot
from core.utils import get_media_info


def is_file_field(value) -> bool:
    return isinstance(value, web.FileField)


def classify_upload(file_field) -> str | None:
    content_type = (getattr(file_field, "content_type", None) or "").lower()
    kind = content_type.split("/", 1)[0] if "/" in content_type else ""
    if kind == "image":
        return "photo"
    if kind == "video":
        return "video"
    if kind == "audio":
        return "audio"
    return "document"


async def relay_to_telegram(file_field, chat_id, caption=None) -> dict | None:
    """Relay an upload through the bot and return the Telegram file handle.

    Returns {"type": ..., "file_id": ...} or None when the upload cannot be
    relayed. The returned file_id is stored and reused to send the same media
    to group chats later.
    """
    media_type = classify_upload(file_field)
    if media_type is None:
        return None
    data = file_field.file.read()
    send = getattr(bot, f"send_{media_type}")
    sent = await send(chat_id, data, caption=caption, disable_notification=True)
    mtype, file_id = get_media_info(sent)
    if mtype is None or file_id is None:
        return None
    return {"type": mtype, "file_id": file_id}