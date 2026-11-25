# YMI Bot Core

A modular core for building Telegram bots in Python. It's also a ready-to-use group management bot, so you get both. (definitely an original concept.)

## What it does
- **Group management.** Ban, kick, mute, warn, promote, demote, pin, purge.
- **Greetings.** Welcome and goodbye messages, with pics or videos if you want.
- **Captcha.** New members prove they're human in PM before they can talk.
- **Notes and filters.** Save stuff, or auto-reply when someone says a keyword.
- **Blocklists.** Block sticker sets, words or phrases.
- **Broadcasts.** Send news to everyone who used the bot. (owner only.)
- **Extras.** User info, wallpapers, anime sauce, spoilers.
- **Modules.** Turn any of the above on or off per group. The bot also notices which admin rights it has and hides what it can't do.

Storage is plain JSON files through [IMY'sDB](https://github.com/IMYdev/IMY-sDB/). No database server, no setup.

## Quick start
```zsh
git clone https://github.com/IMYdev/YMIcore
cd YMIcore
git submodule update --init
python3 -m venv venv && source venv/bin/activate
cd src/
pip install -r requirements.txt
```

Make a `.env`:
```
BOT_TOKEN=your_telegram_bot_token
LOG_ID=logs_channel_id_without_the_minus
OWNER=your_telegram_id
```

Optional, for the web panel:
```
WEB_BIND=127.0.0.1
WEB_PORT=8080
WEB_URL=https://your.host
WEB_SECRET=random_secret   # a random one is made per boot if unset
```

Then:
```zsh
python main.py
```

That's it.

## Web panel
There's a browser panel for tweaking everything without typing commands. See the [panel manual](src/web/README.md).

## Making it yours
- **Add a feature:** drop a file in `modules/`, hook it up in `botcommands.py`, and allow the command in `main.py`.
- **Remove a feature:** comment out its handler in `botcommands.py`.
- **Examples:** `modules/filters.py` and `modules/notes.py`.

One rule: every `runtime/...` path lives in `core/storage.py`, and per-group settings go through `core/group_settings.py`. `tests/test_structure.py` will yell at you otherwise. Tests run with `pytest`. Benchmarks run with `pytest -m perf -s`.

## Why YMI Bot Core?
- The code is dead simple, written by a simple guy, for people that like simplicity.
- It's fast. (trust me.)
- Does what you need and stays out of your way. (hopefully.)

## Demo
- **[YMI](https://t.me/youmnairisbot)**, self-hosted.

## License
GPLv3.

---
Made with ❤️ by IMYdev.
