import json
import os
import time

from core.db import IMYDB


def _corrupt_backups(path):
    prefix = os.path.basename(path) + ".corrupt-"
    return [p for p in os.listdir(os.path.dirname(path)) if p.startswith(prefix)]


def test_corrupt_file_is_quarantined(tmp_path):
    path = str(tmp_path / "data.json")
    with open(path, "w") as f:
        f.write("{not json")

    db = IMYDB(path)

    assert db.data == {}
    backups = _corrupt_backups(path)
    assert len(backups) == 1
    with open(tmp_path / backups[0]) as f:
        assert f.read() == "{not json"
    db.set("ok", True)
    assert json.load(open(path)) == {"ok": True}


def test_empty_and_non_dict_files_are_quarantined(tmp_path):
    for content in ("", "[]"):
        path = str(tmp_path / f"data-{time.time_ns()}.json")
        with open(path, "w") as f:
            f.write(content)
        assert IMYDB(path).data == {}
        assert len(_corrupt_backups(path)) == 1


def test_valid_file_and_missing_file(tmp_path):
    path = str(tmp_path / "data.json")
    with open(path, "w") as f:
        json.dump({"a": {"b": 1}}, f)
    db = IMYDB(path)
    assert db.get("a.b") == 1
    assert _corrupt_backups(path) == []

    missing = str(tmp_path / "new.json")
    IMYDB(missing).set("x", None)
    assert json.load(open(missing)) == {"x": None}
