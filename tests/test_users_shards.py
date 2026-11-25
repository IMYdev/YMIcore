"""Users sharding: legacy registry merge, rollback safety, unchanged results."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core import storage, users
from core.db import IMYDB

TOOL = Path(__file__).resolve().parents[1] / "tools" / "unshard_users.py"
LEGACY = "runtime/users/registry.json"


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    users._merge_checked.clear()
    yield
    users._merge_checked.clear()


def _legacy(n=300, **overrides):
    now = time.time()
    data = {str(1000 + i): {
        "name": f"U{i}", "username": f"u{i}", "first_seen": now - 10_000 + i, "last_seen": now - 10_000 + i,
        "opted_out": i % 7 == 0, "dead": i % 11 == 0,
    } for i in range(n)}
    data.update(overrides)
    os.makedirs("runtime/users", exist_ok=True)
    with open(LEGACY, "w") as f:
        json.dump({"users": data}, f, indent=4)
    return data


def _old_user_ids(data):
    """What the single-file code returned."""
    return [uid for uid, info in data.items() if not info.get("opted_out") and not info.get("dead")]


def _restart():
    """A new process: the merge check runs again on first access."""
    users._merge_checked.clear()


def test_existing_registry_is_merged_and_results_match_old_code():
    data = _legacy()
    assert users.user_ids() == _old_user_ids(data)
    assert users.audience_counts("users")["users"] == len(_old_user_ids(data))
    assert {u["uid"] for u in users.list_users()} == set(data)
    assert users.get_user(1003)["name"] == "U3"
    assert os.path.exists(LEGACY)  # left in place for rollbacks
    assert len(list(storage.iter_user_shards())) == storage.USER_SHARDS


def test_merge_is_idempotent_and_skipped_when_unchanged(monkeypatch):
    _legacy()
    assert users.migrate_users_registry() == 300
    assert users.migrate_users_registry() == 0
    _restart()
    calls = []
    monkeypatch.setattr(users, "user_shard_db", lambda uid: calls.append(uid))
    users.migrate_users_registry()
    assert calls == []


def test_interrupted_merge_is_completed_on_next_start(monkeypatch):
    data = _legacy()
    real_set, writes = IMYDB.set, []

    def crash_after_ten(self, key, value):
        if "shard_" in str(self.file_path):
            if len(writes) >= 10:
                raise KeyboardInterrupt("power cut")
            writes.append(1)
        return real_set(self, key, value)

    with monkeypatch.context() as mp:
        mp.setattr(IMYDB, "set", crash_after_ten)
        with pytest.raises(KeyboardInterrupt):
            users.migrate_users_registry()
    assert not os.path.exists(storage.USERS_MERGE_MARKER)
    _restart()
    assert users.user_ids() == _old_user_ids(data)
    assert os.path.exists(storage.USERS_MERGE_MARKER)


def test_rollback_changes_are_merged_on_reupgrade():
    _legacy(n=20)
    users.record_user(5555, "New", "new")  # first seen after the upgrade
    assert "5555" in users.user_ids()

    # Old code runs: it rewrites registry.json, adds a user, and unsubscribes one.
    with open(LEGACY) as f:
        legacy = json.load(f)
    legacy["users"]["7777"] = {"name": "Rollback", "username": "rb", "first_seen": time.time(),
                               "last_seen": time.time(), "opted_out": False, "dead": False}
    legacy["users"]["1001"]["opted_out"] = True
    tmp = LEGACY + ".tmp"
    with open(tmp, "w") as f:
        json.dump(legacy, f, indent=4)
    os.replace(tmp, LEGACY)

    _restart()
    ids = users.user_ids()
    assert "7777" in ids        # added during the rollback
    assert "5555" in ids        # added before the rollback, kept
    assert "1001" not in ids    # opt-out made during the rollback survives
    assert users.is_opted_out(1001)


def test_newer_shard_record_wins_over_stale_legacy():
    _legacy(n=5)
    users.migrate_users_registry()
    users.record_user(1002, "Renamed", "u2")
    # Legacy changes for an unrelated reason; its copy of 1002 is older.
    with open(LEGACY) as f:
        legacy = json.load(f)
    legacy["users"]["9999"] = {"name": "X", "first_seen": 1, "last_seen": 1}
    with open(LEGACY, "w") as f:
        json.dump(legacy, f)
    _restart()
    assert users.get_user(1002)["name"] == "Renamed"
    assert users.get_user(9999)["name"] == "X"


def test_unreadable_legacy_registry_left_alone():
    os.makedirs("runtime/users", exist_ok=True)
    with open(LEGACY, "w") as f:
        f.write("{broken")
    users.record_user(1, "A", "a")
    assert users.user_ids() == ["1"]
    with open(LEGACY) as f:
        assert f.read() == "{broken"


def test_fresh_install_needs_no_legacy_file():
    users.record_user(42, "A", "a")
    assert users.user_ids() == ["42"]
    assert not os.path.exists(LEGACY)


def test_record_user_writes_one_small_compact_shard():
    _legacy(n=640)
    users.migrate_users_registry()
    before = {p: os.stat(p).st_mtime_ns for p in Path("runtime/users").glob("shard_*.json")}
    time.sleep(0.01)
    users.record_user(123456, "New", "new")
    after = {p: os.stat(p).st_mtime_ns for p in Path("runtime/users").glob("shard_*.json")}
    changed = [p for p in after if after[p] != before.get(p)]
    assert [p.name for p in changed] == [f"shard_{123456 % 64:02d}.json"]
    assert "\n    " not in changed[0].read_text()


def test_unshard_tool_round_trip(tmp_path):
    data = _legacy(n=50)
    users.record_user(5555, "New", "new")
    result = subprocess.run([sys.executable, "-I", str(TOOL), "--runtime", "runtime"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with open(LEGACY) as f:
        rebuilt = json.load(f)["users"]
    assert set(rebuilt) == set(data) | {"5555"}
    assert os.path.exists(LEGACY + ".before-unshard")
    # The new version recognises the rebuilt file: no needless merge.
    _restart()
    assert users.migrate_users_registry() == 0
