# YMI Bot Core

A modular, extensible core for building Telegram bots in Python.
It's also a ready-to-use general group management bot.

## Features
- Modular architecture: add or remove features as modules
- Async support (uses `pyTelegramBotAPI` async interface)
- Uses [IMY'sDB](https://github.com/IMYdev/IMY-sDB/) for file-based JSON storage (no external DB required)
- Easy to extend and maintain

## Quick Start

### 1. Clone the repository
```zsh
git clone https://github.com/IMYdev/YMIcore
cd "YMIcore"
```

### 2. Install dependencies
```zsh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up your environment
Create a `.env` file or set the following environment variable:
```
BOT_TOKEN=your_telegram_bot_token
```

### 4. Run the bot
```zsh
python main.py
```

## Project Structure
```
core/           # Core framework logic (database, utils.)
modules/        # All feature modules (filters, notes, chat, etc.)
botcommands.py  # Command router.
main.py         # Entry point.
requirements.txt
```

## Creating Your Own Bot
1. **Add your bot token to `.env` or your environment.**
2. **Enable/disable features:**
   - To add a feature, drop a new Python file in `modules/` and add a handler call in `botcommands.py`.
   - To remove a feature, remove or comment out the relevant handler in `botcommands.py` or the module file.
3. **Write your own modules:**
   - See `modules/filters.py` or `modules/notes.py` for examples.
   - Each module is a regular Python file; just import and call its handler from `botcommands.py`.

## Why YMI Bot Core?
- **Fast startup:** No database migrations, no ORM, no slow boot.
- **No external DB:** Uses simple file-based JSON for all storage.
- **Easy to hack:** All logic is in plain Python, no magic, no framework lock-in.
- **Robust command router:** Handles all commands in one place for easy auditing and debugging.
- **Async and modern:** Built on `pyTelegramBotAPI` async interface for high performance.
- **Extensible:** Add or remove features by editing `botcommands.py` and dropping files in `modules/`.

## License
This code is licensed under GPLv3 copyleft.

---
Made with ❤️
