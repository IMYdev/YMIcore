from telebot.async_telebot import AsyncTeleBot
import os
import secrets

# Load env variables from .env if found
if os.path.exists(".env"):
    # import is here for performance (what if someone hosted this code on a PS1? we need all the speed we could get)
    from dotenv import load_dotenv
    load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ERROR_LOG_CHAT_ID = os.getenv("LOG_ID")
AWAN_LLM_KEY = os.getenv("AWAN_LLM")
BOT_OWNER= os.getenv("OWNER")

Logs = True
Downloader = True

WEB_BIND = os.getenv("WEB_BIND", "127.0.0.1")
try:
    WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
except ValueError:
    WEB_PORT = 8080
WEB_URL = os.getenv("WEB_URL") or os.getenv("BASE_URL")
WEB_SECRET = os.getenv("WEB_SECRET")
if not WEB_SECRET:
    WEB_SECRET = secrets.token_urlsafe(32)

if TOKEN is None:
    print("[x] Critical error: BOT_TOKEN environment variable is missing. Terminating...")
    exit()

if ERROR_LOG_CHAT_ID is None:
    print("[!] Warning: LOG_ID environment variable is missing. No logging.")
    Logs = False
else:
    try:
        ERROR_LOG_CHAT_ID = -int(ERROR_LOG_CHAT_ID)
    except ValueError:
        print("Invalid LOG_ID. Must be an integer.")
        Logs = False


bot = AsyncTeleBot(TOKEN)