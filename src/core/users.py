import json
import os
import time

from info import BOT_OWNER
from core.groups import banned_ids, registry_groups
from core.storage import (
    USERS_MERGE_MARKER, USERS_REGISTRY as PATH,
    iter_user_shards, user_shard_db, user_shard_index, users_merge_marker_db,
)

# A shard is rewritten as a whole on every save, so an already known user is
# only written back when their name, username or last seen date changed.
SEEN_REFRESH = 86400

SEGMENTS = ("both", "users", "groups")

GROUP_TYPES = ("group", "supergroup", "channel")


# --------------------------------------------------------------------------
# Legacy registry.json -> shards
#
# Older versions kept every user in one registry.json. It is merged into the
# shards whenever it changed since the last merge (first upgrade, or after a
# rollback ran the old code), and it is never renamed or deleted, so rolling
# back still finds the users it knew. The marker is written only after every
# shard is saved, so an interrupted merge simply runs again.
# --------------------------------------------------------------------------

_merge_checked = set()


def _legacy_stamp():
    try:
        st = os.stat(PATH)
    except OSError:
        return None
    return [st.st_ino, st.st_mtime_ns, st.st_size]


def _merged_stamp():
    try:
        with open(USERS_MERGE_MARKER, encoding="utf-8") as f:
            return json.load(f).get("stamp")
    except (OSError, ValueError, AttributeError):
        return None


def _merge_record(current, incoming):
    """Newer last_seen wins. On a tie, keep the shard copy but never lose an
    opt-out or a dead flag recorded by either side."""
    if current is None:
        return incoming
    if (incoming.get("last_seen") or 0) > (current.get("last_seen") or 0):
        merged = dict(incoming)
    else:
        merged = dict(current)
        if (incoming.get("last_seen") or 0) == (current.get("last_seen") or 0):
            merged["opted_out"] = bool(current.get("opted_out") or incoming.get("opted_out"))
    merged["dead"] = bool(current.get("dead") or incoming.get("dead"))
    return merged


def migrate_users_registry() -> int:
    """Merge registry.json into the shards if it changed. Returns users merged."""
    stamp = _legacy_stamp()
    if stamp is None or stamp == _merged_stamp():
        return 0
    try:
        with open(PATH, encoding="utf-8") as f:
            legacy = (json.load(f) or {}).get("users") or {}
    except (OSError, ValueError, AttributeError) as exc:
        print(f"[!] users: could not read {PATH} for merging ({exc}); left untouched.")
        return 0
    if not isinstance(legacy, dict):
        legacy = {}

    by_shard = {}
    for uid, record in legacy.items():
        if isinstance(record, dict):
            by_shard.setdefault(user_shard_index(uid), {})[str(uid)] = record
    for records in by_shard.values():
        db = user_shard_db(next(iter(records)))
        users = dict(db.get("users", {}) or {})
        changed = False
        for uid, record in records.items():
            merged = _merge_record(users.get(uid), record)
            if merged != users.get(uid):
                users[uid] = merged
                changed = True
        if changed:
            db.set("users", users)

    if _legacy_stamp() == stamp:  # unchanged while we merged
        users_merge_marker_db().set("stamp", stamp)
    print(f"[+] users: merged {len(legacy)} users from {PATH} into shards.")
    return len(legacy)


def _ensure_merged() -> None:
    key = os.path.abspath(PATH)
    if key in _merge_checked:
        return
    migrate_users_registry()
    _merge_checked.add(key)


def _db(user_id):
    _ensure_merged()
    return user_shard_db(user_id)


def _all_users() -> dict:
    _ensure_merged()
    merged = {}
    for shard in iter_user_shards():
        merged.update(shard.get("users", {}) or {})
    return merged


def _by_first_seen(users: dict) -> list:
    """Users in the order the single registry kept them (first seen first)."""
    def key(item):
        uid, info = item
        try:
            num = int(uid)
        except ValueError:
            num = 0
        return (info.get("first_seen") or 0, num, uid)
    return sorted(users.items(), key=key)


def record_user(user_id, name=None, username=None) -> None:
    """Remember a user who has interacted with the bot in private."""
    if user_id is None:
        return

    db = _db(user_id)
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
    users = _all_users()
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
    return _db(user_id).get(f"users.{user_id}")


def is_opted_out(user_id) -> bool:
    record = get_user(user_id)
    return bool(record and record.get("opted_out"))


def set_opt_out(user_id, value) -> bool:
    """Subscribe or unsubscribe a user. Returns True when the flag changed."""
    db = _db(user_id)
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
    db = _db(user_id)
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
    return [
        uid for uid, info in _by_first_seen(_all_users())
        if not info.get("opted_out") and not info.get("dead")
    ]


def group_ids() -> list:
    """Chats the bot manages, skipping banned ones and any private chat that
    was picked up by the group registry before chat types were recorded."""
    banned = banned_ids()
    registry = registry_groups()
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
    "group_ids", "is_opted_out", "list_users", "mark_dead", "migrate_users_registry",
    "normalise_segment",
    "record_user", "set_opt_out", "user_ids",
]
