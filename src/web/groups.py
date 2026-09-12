from core.imysdb import IMYDB

PATH = "runtime/groups/registry.json"


def _db() -> IMYDB:
    return IMYDB(PATH)


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