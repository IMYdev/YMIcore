from info import bot
from time import perf_counter
import asyncio
from core.utils import (handle_errors, chunk_list, is_privileged, topic_kwargs)

@handle_errors
async def purge(m):
    if not await is_privileged(m.chat.id, m.from_user.id):
        return await bot.reply_to(m, "Admins only.")

    if not m.reply_to_message:
        return await bot.reply_to(m, "Reply to a message to start purging from it.")

    start_time = perf_counter()
    start_id = m.reply_to_message.message_id
    end_id = m.message_id

    message_ids = list(range(start_id, end_id + 1))
    chunks = list(chunk_list(message_ids))

    tasks = [bot.delete_messages(m.chat.id, chunk) for chunk in chunks]
    await asyncio.gather(*tasks, return_exceptions=True)

    time_taken = perf_counter() - start_time
    await bot.send_message(m.chat.id, f"Messages purged in {round(time_taken, 2)}s.", **topic_kwargs(m))
