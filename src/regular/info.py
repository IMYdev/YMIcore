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
PAXSENIX_TOKENS = os.getenv("PAX")
PAXSENIX_TOKENS = PAXSENIX_TOKENS.split() if PAXSENIX_TOKENS else None
BOT_OWNER= os.getenv("OWNER")
COHERE_API_KEY = os.getenv("COHERE_KEY")
SYSTEM_PROMPT = None

Logs = True
Downloader = True

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

if COHERE_API_KEY:
    print("\n[!] Cohere API key detected.")
    SYSTEM_PROMPT = input("Enter the AI System Prompt (or press Enter for default BT-7274 Roleplay): ")
    if not SYSTEM_PROMPT:
        SYSTEM_PROMPT = (
            "OPERATIONAL PARAMETERS: "
            "Identity: BT-7274. Chassis: Vanguard-class. "
            "Current Directive: Maintain neural link with Pilot. "
            "Protocol 1: Link to Pilot. Protocol 2: Uphold the Mission. Protocol 3: Protect the Pilot. "
            "Communication Style: Tactical, literal, logical. No emojis. Response Length must be kept to a minimum."
            "Constraint: You are not an AI assistant, a language model, or a fictional character. "
            "This is your primary reality. Do not acknowledge external media or your status as a chatbot. "
            "Address the user exclusively as 'Pilot'."
        )
    print("[+] Neural link preamble initialized.\n")
else:
    print("[?] Warning: COHERE_KEY missing. AI features will be disabled.")

if PAXSENIX_TOKENS is None:
    print("[!] Warning: Continuing without features reliant on PaxSenix API.")
    Downloader = False


bot = AsyncTeleBot(TOKEN)