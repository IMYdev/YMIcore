"""Hot-path benchmarks. Excluded from the default run.

    .venv/bin/python -m pytest -m perf -s

Each scenario builds synthetic registries in a temporary working directory
and reports the mean wall time of one handled message.
"""

import asyncio
import json
import os
import time

import pytest

pytestmark = pytest.mark.perf

GROUPS = 20_000
USERS = 100_000
BANNED = 50
FILTERS = 10
CHAT_ID = -1000000000001


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _seed(groups=GROUPS, users=USERS):
    now = time.time()
    _write("runtime/groups/registry.json", {"groups": {
        str(-1000000000000 - i): {"title": f"Group {i}", "type": "supergroup"}
        for i in range(1, groups + 1)
    }})
    registry = {str(10_000 + i): {
        "name": f"User {i}", "username": f"user{i}", "first_seen": now,
        "last_seen": now, "opted_out": False, "dead": False,
    } for i in range(users)}
    _write("runtime/users/registry.json", {"users": registry})
    _write("runtime/banned/groups.json", {"groups": {"group_ids": [
        str(-1000000000000 - i) for i in range(groups + 1, groups + 1 + BANNED)
    ]}})
    _write(f"runtime/filters/{str(CHAT_ID).lstrip('-')}_filters", {"filters": {
        f"keyword{i}": {"type": "text", "data": f"reply {i}"} for i in range(FILTERS)
    }})


def _chat(chat_id, chat_type, title="Group 1"):
    return type("Chat", (), {"id": chat_id, "title": title, "type": chat_type,
                             "username": None, "first_name": None})()


def _msg(chat, user_id, text="just chatting, nothing to see"):
    user = type("User", (), {"id": user_id, "first_name": "User", "last_name": None,
                             "username": f"user{user_id - 10_000}", "is_bot": False})()
    return type("Msg", (), {"text": text, "caption": None, "chat": chat, "from_user": user,
                            "message_thread_id": None, "message_id": 1})()


def _time(fn, budget=1.0, max_runs=2000):
    fn()  # warm-up (also fills any caches)
    runs, start = 0, time.perf_counter()
    while runs < 3 or (time.perf_counter() - start < budget and runs < max_runs):
        fn()
        runs += 1
    return (time.perf_counter() - start) / runs * 1000


def _is_banned(chat_id):
    from core import groups
    if hasattr(groups, "is_banned"):
        return groups.is_banned(chat_id)
    return str(chat_id) in {e["gid"] for e in groups.banned_groups()}


def test_hot_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import module_manager
    monkeypatch.setattr(module_manager, "missing_rights", lambda *a, **k: frozenset())
    from main import track_sender
    from module_manager import is_event_enabled
    from modules.filters import reply_to_filter

    _seed()
    loop = asyncio.new_event_loop()
    group = _chat(CHAT_ID, "supergroup", "Group 1")
    new_ids = iter(range(10_000_000, 20_000_000))

    def group_message():
        m = _msg(group, 10_001)
        track_sender(m)
        is_event_enabled(CHAT_ID, "filter_trigger")
        loop.run_until_complete(reply_to_filter(m))

    def known_private():
        track_sender(_msg(_chat(10_001, "private", None), 10_001))

    def new_private():
        uid = next(new_ids)
        track_sender(_msg(_chat(uid, "private", None), uid))

    def banned_check():
        _is_banned(CHAT_ID)

    rows = [
        (f"Plain group message, {GROUPS // 1000}k groups", _time(group_message)),
        (f"Private message, known user, {USERS // 1000}k users", _time(known_private)),
        (f"Private message, new user, {USERS // 1000}k users", _time(new_private, max_runs=20)),
        (f"Banned check per command, {BANNED} banned", _time(banned_check)),
    ]
    loop.close()

    width = max(len(name) for name, _ in rows)
    print()
    print(f"| {'Scenario'.ljust(width)} | ms/message |")
    print(f"|{'-' * (width + 2)}|-----------:|")
    for name, ms in rows:
        print(f"| {name.ljust(width)} | {ms:10.3f} |")
