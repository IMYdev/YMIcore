from info import bot
from time import perf_counter
import asyncio
from core.utils import (handle_errors, is_user_admin)

def chunk_list(lst, chunk_size=100):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

@handle_errors
async def purge(m):
    if not await is_user_admin(m.chat.id, m.from_user.id):
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
    await bot.send_message(m.chat.id, f"Messages purged in {round(time_taken, 2)}s.")
