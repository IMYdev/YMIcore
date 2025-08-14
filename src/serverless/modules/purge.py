from info import bot
from time import perf_counter
import asyncio
from core.utils import log_error

# Function to split the message IDs into chunks of 100
def chunk_list(lst, chunk_size=100):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

async def purge(m):
    beginning = perf_counter()
    user = await bot.get_chat_member(m.chat.id, m.from_user.id)
    can_delete = user.can_delete_messages

    if can_delete or user.status == "creator":
        if m.reply_to_message is None:
            await bot.reply_to(m, "Reply to a message to start purging from it.")
            return
        start = m.reply_to_message.message_id
        end = m.id
    
        message_ids = [message_id for message_id in range(start, end + 1)]
        chunks = list(chunk_list(message_ids))

        tasks = [bot.delete_messages(m.chat.id, chunk) for chunk in chunks]

        try:
            await asyncio.gather(*tasks)
        except Exception as error:
            await log_error(bot, error, context_msg=m)
            await bot.reply_to(m, "An error occurred.")

        end_time = perf_counter()
        time_taken = end_time - beginning
        await bot.send_message(m.chat.id, f"Messages purged in {round(time_taken, 2)}s.")
    else:
        await bot.reply_to(m, "You lack permission to delete messages.")
