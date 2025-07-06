from telebot.async_telebot import AsyncTeleBot
import os
TOKEN = os.getenv("BOT_TOKEN")
bot = AsyncTeleBot(TOKEN)