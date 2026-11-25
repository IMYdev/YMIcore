"""Rose (@MissRose_bot) export, version 2."""

from core.migrate.bundle import ImportBundle, convert_greeting, convert_reply

BOT_ID = 609517172
NAME = "Rose"

_USED = {"notes", "filters", "blocklists", "greetings", "rules"}


def matches(raw) -> bool:
    return (
        isinstance(raw, dict)
        and raw.get("bot_id") == BOT_ID
        and raw.get("version") == 2
        and isinstance(raw.get("data"), dict)
    )


def _items(section, key):
    items = (section or {}).get(key) if isinstance(section, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def parse(raw) -> ImportBundle:
    data = raw["data"]
    bundle = ImportBundle(source=NAME)

    for item in _items(data.get("notes"), "notes"):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        entry = convert_reply(bundle, "notes", name, item.get("text"), item.get("data_id"))
        if entry:
            bundle.notes.append(entry)

    for item in _items(data.get("filters"), "filters"):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        entry = convert_reply(bundle, "filters", name, item.get("text"), item.get("data_id"))
        if entry:
            bundle.filters.append(entry)

    blocklists = data.get("blocklists") if isinstance(data.get("blocklists"), dict) else {}
    for item in _items(blocklists, "filters"):
        word = str(item.get("name") or "").strip()
        if not word:
            continue
        if "*" in word:
            bundle.skip("blocked words", word, "wildcard patterns aren't supported")
            continue
        bundle.blocked_words.append(word)
    if bundle.blocked_words:
        action = blocklists.get("action") or "nothing"
        bundle.warnings.append(
            f"Rose's blocklist action ('{action}') isn't imported: blocked words here "
            "delete the message and mute the sender for escalating lengths."
        )

    greetings = data.get("greetings") if isinstance(data.get("greetings"), dict) else {}
    for event, key in (("greeting", "welcome"), ("goodbye", "goodbye")):
        msg = greetings.get(key)
        if isinstance(msg, dict):
            entry = convert_greeting(bundle, event, msg.get("text"), msg.get("data_id"))
            setattr(bundle, event, entry)
    if greetings:
        bundle.not_imported.append("greeting settings (on/off, mute/kick on join, cleanup)")

    rules = data.get("rules") if isinstance(data.get("rules"), dict) else {}
    content = rules.get("content")
    if isinstance(content, str) and content.strip():
        entry = convert_reply(bundle, "notes", "rules", content)
        if entry:
            bundle.notes.append(entry)

    bundle.not_imported.extend(sorted(k for k in data if k not in _USED))
    return bundle
