"""AstrakoBot (@AstrakoBot) export."""

from core.migrate.bundle import ImportBundle, convert_greeting, convert_reply

BOT_ID = 1376954911
NAME = "AstrakoBot"

_USED = {"bot_id", "chat", "notes", "greetings"}


def matches(raw) -> bool:
    return (
        isinstance(raw, dict)
        and raw.get("bot_id") == BOT_ID
        and isinstance(raw.get("chat"), dict)
        and isinstance(raw.get("notes"), list)
    )


def parse(raw) -> ImportBundle:
    bundle = ImportBundle(source=NAME)

    for item in raw["notes"]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        entry = convert_reply(bundle, "notes", name, item.get("text"), item.get("data_id"))
        if entry:
            bundle.notes.append(entry)

    greetings = raw.get("greetings") if isinstance(raw.get("greetings"), list) else []
    for item in greetings:
        if not isinstance(item, dict):
            continue
        event = {"welcome": "greeting", "goodbye": "goodbye"}.get(item.get("name"))
        if event:
            entry = convert_greeting(bundle, event, item.get("text"), item.get("data_id"))
            setattr(bundle, event, entry)

    rules = raw["chat"].get("rules")
    if isinstance(rules, str) and rules.strip():
        entry = convert_reply(bundle, "notes", "rules", rules)
        if entry:
            bundle.notes.append(entry)

    bundle.not_imported.append("chat settings (antiflood, antiraid, captcha, warn limits, ...)")
    bundle.not_imported.extend(sorted(k for k in raw if k not in _USED))
    return bundle
