import aiohttp
from info import *
import asyncio
from core.utils import log_error

async def fetch_task_status(task_url):
    """Fetch the task status and return the image URL if the task is done."""
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(task_url) as response:
                result = await response.json()
                if result['status'] == 'done':
                    return result['url']
                # Wait before polling again if the status is pending
                await asyncio.sleep(1)

async def generate_image(api_url, prompt):
    """Request image generation and get the task_url."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{api_url}?text={prompt}") as response:
            return await response.json()

async def image_gen(m):
    # Define the API endpoint
    api_url = "https://api.paxsenix.biz.id/ai-image/magicstudio"
    
    # Generate image
    try:
        prompt = m.text.split()[1]
        
        wait_message = await bot.send_message(m.chat.id, "Generating your image...")
        # Request image generation and get task URL
        job_response = await generate_image(api_url, prompt)
        task_url = job_response['task_url']

        # Poll the task status
        image_url = await fetch_task_status(task_url)

        # Delete the wait message and send the image
        await bot.delete_message(m.chat.id, wait_message.message_id)
        await bot.send_chat_action(m.chat.id, "upload_photo")
        await bot.send_photo(m.chat.id, photo=image_url, reply_to_message_id=m.message_id)
        
    except IndexError:
        await bot.reply_to(m, "Input missing. Clarify your request.")
    except Exception as error:
        await log_error(bot, error, context_msg=m)
        await bot.reply_to(m, "Error, developer has been notified.")
