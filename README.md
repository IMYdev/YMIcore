# YMI Bot Core

A modular, extensible core for building Telegram bots in Python.
It's also a ready-to-use general group management bot.

## Features (developers)
- Modular architecture: add or remove features as modules.
- Async support (uses `pyTelegramBotAPI` async interface.)
- Uses [IMY'sDB](https://github.com/IMYdev/IMY-sDB/) for file-based JSON storage (or MongoDB,) check the project repo for more details.
- Easy to extend and maintain/

## Features (end users)
- Show info about users or yourself anytime.
- Custom greetings and farewell messages when a member joins or leaves (can attach pics or videos.)
- Grab and send wallpapers from various sources, including anime-themed ones.
- Reverse search anime pictures to identify the anime.
- Save, list, and remove notes inside the chat.
- Set up automatic keyword triggers that reply with custom messages.
- Manage chat admins. Promote, demote, ban, or unban users.
- Pin important messages.
- Clean up chats by deleting batches of messages at once.
- Toggle and control various bot modules for extra features or disabling unwanted ones.
- Grab media content from Instagram and YouTube links.
- Ability to add spoilers to media and text.
- Block sticker sets that are unwanted in the group chat.

## Quick Start

### 1. Clone the repository
```zsh
git clone https://github.com/IMYdev/YMIcore
cd "YMIcore"
git submodule update --init   # pulls the LECP-CSS stylesheet for the web panel
```

### 2. Install dependencies
```zsh
python3 -m venv venv
source venv/bin/activate
cd src/
pip install -r requirements.txt
```

### 3. Set up your environment
Create a `.env` file or set the following environment variables:
```
BOT_TOKEN=your_telegram_bot_token
LOG_ID=logs_channel_id_without_the_minus
OWNER=your_telegram_id
```
Optional web panel settings:
```
WEB_BIND=127.0.0.1   # panel bind address
WEB_PORT=8080        # panel port
WEB_URL=https://your.host  # public panel URL (used in /panel login links)
WEB_SECRET=random_secret   # optional; a fresh random secret is generated per boot if unset
```

### 4. Run the bot
If self-hosting:
```zsh
python main.py
```

## Settings Web Panel

YMIcore ships with a browser-based control panel for customizing the bot.

[YMIcore Control Panel Instruction Manual](src/web/README.md)

## Project Structure
```
core/            # Core framework logic (database, utils.)
modules/         # All feature modules (filters, notes, etc.)
web/             # Settings web panel (aiohttp server, auth, templates).
botcommands.py   # Command router.
main.py          # Entry point (bot + web panel).
requirements.txt # Project dependencies.
```
 
## Creating Your Own Bot
1. **Add needed environment variables to `.env` or your environment.**

2. **Enable/disable features:**
   - To add a feature, drop a new Python file in `modules/` then add a handler call in `botcommands.py`, and don't forget to allow the new command in the commands filter in `main.py`.
   - To remove a feature, remove or comment out the relevant handler in `botcommands.py` or the module file.
3. **Write your own modules:**
   - See `modules/filters.py` or `modules/notes.py` for examples.


## Why YMI Bot Core?
- The code is dead simple, written by a simple guy, for people that like simplicity.
- It's fast, trust.
- Does what you need it to do and doesn't get in your way. (hopefully)


## Demo instances
- **[YMI](https://t.me/youmnairisbot)** for self-hosted.


## License
This code is licensed under GPLv3 copyleft.

---
Made with ❤️ by IMYdev.
