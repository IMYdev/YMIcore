"""Bot Telegram rights detection: per-chat snapshot with a short TTL.

Maps Telegram admin flags (delete / restrict / promote / pin) onto the
commands and events that need them.  A small in-memory per-chat snapshot is
kept so the sync module gates read it without an API call; the async handlers
in main.py refresh it on ``my_chat_member`` updates and lazily on first
message activity.  Missing rights *veto* features without rewriting saved
toggles.
"""

import asyncio

# ---------------------------------------------------------------------------
# What each command / event requires.  A missing entry means the feature
# needs no special right.  Flag names are short forms; they map to the
# ChatMemberAdministrator.can_* attributes in _rights_from_member().
# ---------------------------------------------------------------------------

REQUIRED_RIGHTS: dict[str, set[str]] = {
    # Delete messages
    "purge": {"delete"},
    "sticker_block": {"delete"},
    # Restrict members (ban, kick, mute)
    "ban": {"restrict"},
    "unban": {"restrict"},
    "mute": {"restrict"},
    "unmute": {"restrict"},
    "kick": {"restrict"},
    "warn": {"restrict"},
    "captcha_verification": {"restrict", "delete"},
    "word_block": {"delete", "restrict"},
    # Promote/demote admins
    "promote": {"promote"},
    "demote": {"promote"},
    # Pin messages
    "pin": {"pin"},
}

_SNAPSHOTS: dict[int, dict[str, bool]] = {}
_STAMPS: dict[int, float] = {}
_LOCKS: dict[int, asyncio.Lock] = {}

TTL_SECONDS = 300  # 5 minutes


def _lock_for(gid: int) -> asyncio.Lock:
    lock = _LOCKS.get(gid)
    if lock is None:
        lock = _LOCKS[gid] = asyncio.Lock()
    return lock


def _rights_from_member(member) -> dict[str, bool]:
    """Extract the four rights from a ChatMember object returned by Telegram.

    ChatMemberAdministrator carries can_* flags directly (snake_case); the
    creator has all rights implicitly; a plain member has none.
    """
    is_creator = getattr(member, "status", None) == "creator"
    return {
        "delete": is_creator or bool(getattr(member, "can_delete_messages", False)),
        "restrict": is_creator or bool(getattr(member, "can_restrict_members", False)),
        "promote": is_creator or bool(getattr(member, "can_promote_members", False)),
        "pin": is_creator or bool(getattr(member, "can_pin_messages", False)),
    }


async def refresh_permissions(gid: int, *, force: bool = False) -> None:
    """Fetch the bot's own rights in *gid* into the in-memory snapshot.

    TTL-gated unless ``force``.  On failure the snapshot is left as-is when
    one exists; when none exists an empty (fail-closed) snapshot is stored
    but marked already-expired so the next call retries immediately.
    """
    from info import bot
    from core.utils import bot_me

    gid = int(gid)
    async with _lock_for(gid):
        now = asyncio.get_running_loop().time() * 1000
        stamp = _STAMPS.get(gid)
        if not force and stamp is not None and (now - stamp) < TTL_SECONDS * 1000:
            return
        try:
            member = await bot.get_chat_member(gid, (await bot_me()).id)
        except Exception as e:
            print(f"[!] permissions: could not fetch rights for {gid}: {e}")
            if gid not in _SNAPSHOTS:
                _SNAPSHOTS[gid] = {}
                _STAMPS[gid] = now - TTL_SECONDS * 1000  # already expired -> retry next call
            return
        _SNAPSHOTS[gid] = _rights_from_member(member)
        _STAMPS[gid] = now


def missing_rights(gid: int, kind: str, name: str) -> frozenset[str]:
    """Flags still missing for *name* (command or event), or empty if none needed.

    No snapshot yet means fail-closed: everything the feature needs is
    reported missing (it unblocks once the first refresh succeeds).
    """
    needed = REQUIRED_RIGHTS.get(name, set())
    if not needed:
        return frozenset()
    snapshot = _SNAPSHOTS.get(int(gid), {})
    return frozenset(f for f in needed if not snapshot.get(f))


def right_label(missing: frozenset[str]) -> str:
    """Human-readable description, e.g. ``'delete messages'`` or
    ``'delete messages and restrict members'``."""
    if not missing:
        return ""
    labels = {
        "delete": "delete messages",
        "restrict": "restrict members",
        "promote": "promote members",
        "pin": "pin messages",
    }
    parts = [labels.get(f, f) for f in sorted(missing, key=labels.get)]
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


async def apply_chat_member_update(update) -> None:
    """Handle a ``my_chat_member`` update: drop the snapshot when the bot is
    removed, otherwise use the new ChatMember in the update directly — no API
    call needed.
    """
    gid = update.chat.id
    new_member = update.new_chat_member
    status = getattr(new_member, "status", None)
    if status in ("left", "kicked"):
        _SNAPSHOTS.pop(gid, None)
        _STAMPS.pop(gid, None)
        return
    _SNAPSHOTS[gid] = _rights_from_member(new_member)
    _STAMPS[gid] = asyncio.get_running_loop().time() * 1000


__all__ = [
    "REQUIRED_RIGHTS",
    "missing_rights",
    "right_label",
    "refresh_permissions",
    "apply_chat_member_update",
]
