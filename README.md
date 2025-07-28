# YMI Bot Core

A modular, extensible core for building Telegram bots in Python.
It's also a ready-to-use general group management bot.

## Features
- Modular architecture: add or remove features as modules
- Async support (uses `pyTelegramBotAPI` async interface)
- Uses [IMY'sDB](https://github.com/IMYdev/IMY-sDB/) for file-based JSON storage (or MongoDB,) check the project repo for more details.
- Easy to extend and maintain

## Quick Start

### 1. Clone the repository
```zsh
git clone https://github.com/IMYdev/YMIcore
cd "YMIcore"
```

### 2. Install dependencies (only if self-hosting)
```zsh
python3 -m venv venv
source venv/bin/activate
cd src/regular
pip install -r requirements.txt
```

### 3. Set up your environment
Create a `.env` file or set the following environment variables:
```
BOT_TOKEN=your_telegram_bot_token
LOG_ID=logs_channel_id_without_the_minus
```
For serverless, add those as well:
```
DB_NAME=mongoDB_database_name
WEBHOOK_URL=vercel_deployment_url
MONGO_URL=mongoDB_connection_string
```


### 4. Run the bot
If self-hosting:
```zsh
python main.py
```
Else, just initiate a deployment on vercel.

## Project Structure
```
core/           # Core framework logic (database, utils.)
modules/        # All feature modules (filters, notes, chat, etc.)
botcommands.py  # Command router.
main.py         # Entry point.
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
- **Fast startup:** No database migrations (optional), no slow boot.
- **No external DB:** Uses simple file-based JSON for all storage. (optional)
- **Easy to hack:** All logic is in plain Python, no magic, no framework lock-in.
- **Robust command router:** Handles all commands in one place for easy auditing and debugging.
- **Async and modern:** Built on `pyTelegramBotAPI` async interface for high performance.
- **Extensible:** Add or remove features by editing `botcommands.py` and dropping files in `modules/`.

## Note:
**Vercel** + **MongoDB** for serverless is just my own personal preference, you can use whatever you like with minimal changes.


## License
This code is licensed under GPLv3 copyleft.

---
Made with ❤️
