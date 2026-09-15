## YMIcore Control Panel Instruction Manual

- Each admin has a **permanent panel token**. Send `/panel` to the bot in Telegram to get yours (every `/panel` rotates the previous token). Paste it at the panel URL, or use the one-click login link the bot sends.
- Your token is saved in your browser (`localStorage`) so the session persists across cookie expiry — handy when the panel is hosted on a public domain.
- Once an admin has a token, they're signed in for good. No re-fetching one-time links; the token works only as long as it isn't revoked.
- The **bot owner** can mint, revoke, re-activate, or delete tokens from **Admin tokens** in the panel. Revoking a token immediately ends every session it was used for. The owner is also handed a token on first boot (printed to the console, or via `/panel`).
- The **owner** sees a dashboard with every registered group plus read-only global settings. A group admin only sees groups they manage.
- From a group page you can toggle its modules and commands, edit greeting/farewell messages and captcha, manage keyword filters, notes, and the sticker blocklist.
- The UI uses the [LECP design system](https://github.com/IMYdev/LECP-CSS), pulled in as a git submodule at `src/web/static/vendor/lecp-css`.