from info import bot
from time import perf_counter
import asyncio
from core.utils import (handle_errors, chunk_list, is_privileged, topic_kwargs)

# Telegram deletes at most 100 messages per call; this bounds one /purge to
# 10 calls, and at most PURGE_CONCURRENCY of them run at once.
MAX_PURGE_MESSAGES = 1000
PURGE_CONCURRENCY = 3


@handle_errors
async def purge(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to start purging from it.")

    start_time = perf_counter()
    start_id = m.reply_to_message.message_id
    end_id = m.message_id

    # Newest first, so a truncated purge clears the most recent messages.
    first_id = max(start_id, end_id - MAX_PURGE_MESSAGES + 1)
    truncated = first_id > start_id
    message_ids = list(range(end_id, first_id - 1, -1))

    limit = asyncio.Semaphore(PURGE_CONCURRENCY)

    async def delete(chunk):
        async with limit:
            return await bot.delete_messages(m.chat.id, chunk)

    await asyncio.gather(*(delete(chunk) for chunk in chunk_list(message_ids)),
                         return_exceptions=True)

    time_taken = perf_counter() - start_time
    text = f"Messages purged in {round(time_taken, 2)}s."
    if truncated:
        text += f" Only the latest {MAX_PURGE_MESSAGES} messages were purged; run it again for older ones."
    await bot.send_message(m.chat.id, text, **topic_kwargs(m))
