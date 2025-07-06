from info import bot
from telebot.util import user_link

async def hello(m):
    await bot.reply_to(m, f"Greetings, {user_link(m.from_user)}.")

async def bye(m):
    await bot.reply_to(m, f"Farewell, {user_link(m.from_user)}.")