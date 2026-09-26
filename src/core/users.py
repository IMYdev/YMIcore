import time

from info import BOT_OWNER
from core.imysdb import IMYDB
from web.groups import banned_groups

PATH = "runtime/users/registry.json"

# The registry is rewritten as a whole on every save, so an already known user
# is only written back when their name, username or last seen date changed.
SEEN_REFRESH = 86400

SEGMENTS = ("both", "users", "groups")

GROUP_TYPES = ("group", "supergroup", "channel")


def _db() -> IMYDB:
    return IMYDB(PATH)


def record_user(user_id, name=None, username=None) -> None:
    """Remember a user who has interacted with the bot in private."""
    if user_id is None:
        return

    db = _db()
    users = db.get("users", {})
    uid = str(user_id)
    record = users.get(uid)
    now = time.time()

    if record is None:
        users[uid] = {
            "name": name,
            "username": username,
            "first_seen": now,
            "last_seen": now,
            "opted_out": False,
            "dead": False,
        }
    else:
        renamed = record.get("name") != name or record.get("username") != username
        stale = now - (record.get("last_seen") or 0) > SEEN_REFRESH
        if not (renamed or stale):
            return
        record["name"] = name
        record["username"] = username
        record["last_seen"] = now

    db.set("users", users)


def list_users() -> list:
    users = _db().get("users", {})
    result = [
        {
            "uid": uid,
            "name": info.get("name") or info.get("username") or uid,
            "username": info.get("username"),
            "opted_out": bool(info.get("opted_out")),
            "dead": bool(info.get("dead")),
            "last_seen": info.get("last_seen"),
        }
        for uid, info in users.items()
    ]
    result.sort(key=lambda u: u["name"].lower())
    return result


def get_user(user_id):
    if user_id is None:
        return None
    return _db().get(f"users.{user_id}")


def is_opted_out(user_id) -> bool:
    record = get_user(user_id)
    return bool(record and record.get("opted_out"))


def set_opt_out(user_id, value) -> bool:
    """Subscribe or unsubscribe a user. Returns True when the flag changed."""
    db = _db()
    users = db.get("users", {})
    uid = str(user_id)
    if uid not in users:
        return False
    if bool(users[uid].get("opted_out")) == bool(value):
        return False
    users[uid]["opted_out"] = bool(value)
    db.set("users", users)
    return True


def mark_dead(user_id) -> None:
    """Flag a user who blocked the bot or was deleted, so sends stop retrying."""
    db = _db()
    users = db.get("users", {})
    uid = str(user_id)
    if uid not in users or users[uid].get("dead"):
        return
    users[uid]["dead"] = True
    db.set("users", users)


def normalise_segment(segment) -> str:
    segment = (segment or "both").strip().lower()
    return segment if segment in SEGMENTS else "both"


def user_ids() -> list:
    users = _db().get("users", {})
    return [
        uid for uid, info in users.items()
        if not info.get("opted_out") and not info.get("dead")
    ]


def group_ids() -> list:
    """Chats the bot manages, skipping banned ones and any private chat that
    was picked up by the group registry before chat types were recorded."""
    banned = {str(entry["gid"]) for entry in banned_groups()}
    registry = IMYDB("runtime/groups/registry.json").get("groups", {})
    result = []
    for gid, info in registry.items():
        if str(gid) in banned:
            continue
        chat_type = info.get("type")
        if chat_type:
            if chat_type not in GROUP_TYPES:
                continue
        elif not (str(gid).startswith("-") and str(gid)[1:].isdigit()):
            continue
        result.append(gid)
    return result


def broadcast_targets(segment="both") -> list:
    segment = normalise_segment(segment)
    owner = str(BOT_OWNER) if BOT_OWNER else None
    candidates = []
    if segment in ("both", "users"):
        candidates.extend(user_ids())
    if segment in ("both", "groups"):
        candidates.extend(group_ids())

    targets, seen = [], set()
    for chat_id in candidates:
        key = str(chat_id)
        if key in seen or key == owner:
            continue
        seen.add(key)
        targets.append(int(chat_id))
    return targets


def audience_counts(segment="both") -> dict:
    segment = normalise_segment(segment)
    counts = {"users": 0, "groups": 0, "total": 0}
    if segment in ("both", "users"):
        counts["users"] = len(user_ids())
    if segment in ("both", "groups"):
        counts["groups"] = len(group_ids())
    counts["total"] = counts["users"] + counts["groups"]
    return counts


__all__ = [
    "PATH", "SEGMENTS", "audience_counts", "broadcast_targets", "get_user",
    "group_ids", "is_opted_out", "list_users", "mark_dead", "normalise_segment",
    "record_user", "set_opt_out", "user_ids",
]
