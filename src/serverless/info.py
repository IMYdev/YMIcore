from telebot.async_telebot import AsyncTeleBot
import os

# Load env variables from .env if found
if os.path.exists(".env"):
    # import is here for performance (what if someone hosted this code on a PS1? we need all the speed we could get)
    from dotenv import load_dotenv
    load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ERROR_LOG_CHAT_ID = os.getenv("LOG_ID")
AWAN_LLM_KEY = os.getenv("AWAN_LLM")
PAXSENIX_TOKEN= os.getenv("PAX")

Logs = True
AI = True
Downloader = True

if TOKEN is None:
    print("Critical error: BOT_TOKEN environment variable is missing.")
    print("Exiting...")
    exit()

if ERROR_LOG_CHAT_ID is None:
    print("Warning: LOG_ID environment variable is missing.")
    print("Continuing without logging capability.")
    Logs = False
else:
    try:
        ERROR_LOG_CHAT_ID = -int(ERROR_LOG_CHAT_ID)
    except ValueError:
        print("Invalid LOG_ID. Must be an integer.")
        Logs = False

if AWAN_LLM_KEY is None:
    print("Warning: AWAN_LLM environment variable is missing.")
    print("Continuing without AI functions.")
    AI = False

if PAXSENIX_TOKEN is None:
    print("Warning: Continuing without features reliant of PaxSenix API.")
    Downloader = False


bot = AsyncTeleBot(TOKEN)