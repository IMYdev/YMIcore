from core.imysdb import IMYDB

PATH = "runtime/groups/registry.json"
BANNED_PATH = "runtime/banned/groups.json"


def _db() -> IMYDB:
    return IMYDB(PATH)


def _banned_db() -> IMYDB:
    return IMYDB(BANNED_PATH)


def record_group(chat_id, title) -> None:
    db = _db()
    gid = str(chat_id)
    if db.get(f"groups.{gid}.title") != title:
        db.set(f"groups.{gid}.title", title or f"Group {gid.lstrip('-')}")


def group_title(gid) -> str:
    return _db().get(f"groups.{gid}.title", f"Group {gid}")


def list_groups() -> list:
    groups = _db().get("groups", {})
    result = [{"gid": gid, "title": info.get("title", gid)} for gid, info in groups.items()]
    result.sort(key=lambda g: g["title"].lower())
    return result


def banned_groups() -> list:
    banned = _banned_db().get("groups.group_ids", [])
    result = [{"gid": gid, "title": group_title(gid)} for gid in banned]
    result.sort(key=lambda g: g["gid"])
    return result


def ban_group(gid) -> bool:
    db = _banned_db()
    banned = db.get("groups.group_ids", [])
    gid = str(gid)
    if gid in banned:
        return False
    banned.append(gid)
    db.set("groups.group_ids", sorted(set(banned)))
    return True


def unban_group(gid) -> bool:
    db = _banned_db()
    banned = db.get("groups.group_ids", [])
    gid = str(gid)
    if gid not in banned:
        return False
    banned = [g for g in banned if g != gid]
    db.set("groups.group_ids", banned)
    return True