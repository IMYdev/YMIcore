from info import bot
from core.storage import banned_db, groups_db


def _db():
    return groups_db()


def _banned_db():
    return banned_db()


def registry_groups() -> dict:
    """Raw {gid: {...}} map of every chat the bot has seen."""
    return _db().get("groups", {})


def record_group(chat_id, title, chat_type=None) -> None:
    db = _db()
    gid = str(chat_id)
    current = db.get(f"groups.{gid}")
    current = current if isinstance(current, dict) else {}
    changes = {}
    title = title or f"Group {gid.lstrip('-')}"
    if current.get("title") != title:
        changes["title"] = title
    if chat_type and current.get("type") != chat_type:
        changes["type"] = chat_type
    if changes:
        # One rewrite of the registry, even for a brand-new group.
        db.set(f"groups.{gid}", {**current, **changes})


def group_title(gid) -> str:
    return _db().get(f"groups.{gid}.title", f"Group {gid}")


def list_groups() -> list:
    groups = _db().get("groups", {})
    result = [
        {"gid": gid, "title": info.get("title", gid)}
        for gid, info in groups.items()
        if info.get("type") != "private"
    ]
    result.sort(key=lambda g: g["title"].lower())
    return result


def banned_groups() -> list:
    banned = _banned_db().get("groups.group_ids", [])
    result = [{"gid": gid, "title": group_title(gid)} for gid in banned]
    result.sort(key=lambda g: g["gid"])
    return result


def banned_ids() -> set:
    """Banned chat ids as strings. Reads only the banned list (no titles)."""
    return {str(gid) for gid in _banned_db().get("groups.group_ids", []) or []}


def is_banned(gid) -> bool:
    return str(gid) in banned_ids()


def ban_group(gid) -> bool:
    db = _banned_db()
    banned = db.get("groups.group_ids", [])
    gid = str(gid)
    if gid in banned:
        return False
    banned.append(gid)
    db.set("groups.group_ids", sorted(set(banned)))
    return True


async def ban_group_and_leave(gid) -> bool:
    """Ban a chat and make the bot leave it. Returns whether it was newly banned."""
    added = ban_group(gid)
    if added:
        try:
            await bot.leave_chat(int(gid))
        except Exception:
            pass
    return added


def unban_group(gid) -> bool:
    db = _banned_db()
    banned = db.get("groups.group_ids", [])
    gid = str(gid)
    if gid not in banned:
        return False
    banned = [g for g in banned if g != gid]
    db.set("groups.group_ids", banned)
    return True


def is_developer_group(gid) -> bool:
    """Return True if group is marked as developer group."""
    gid = str(gid)
    return bool(_db().get(f"groups.{gid}.developer", False))


def set_developer_group(gid, enabled: bool) -> None:
    """Enable or disable developer mode for a group."""
    gid = str(gid)
    _db().set(f"groups.{gid}.developer", bool(enabled))


__all__ = [
    "ban_group", "ban_group_and_leave",
    "banned_groups", "banned_ids", "is_banned", "group_title", "is_developer_group", "list_groups",
    "record_group", "registry_groups", "set_developer_group", "unban_group",
]
