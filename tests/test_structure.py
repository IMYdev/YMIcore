"""Guardrails: one home per concern.

Each test fails when a second copy of a shared implementation appears. They
are deliberately source-text checks: cheap, no imports, no side effects.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
PY_FILES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _lines_matching(pattern, allowed=()):
    allowed = set(allowed)
    hits = []
    for path in PY_FILES:
        relative = path.relative_to(SRC).as_posix()
        if relative in allowed:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(pattern, line):
                hits.append(f"{relative}:{lineno}: {line.strip()}")
    return hits


def test_runtime_paths_only_in_storage():
    assert _lines_matching(r"\bIMYDB\(", {"core/db.py", "core/storage.py"}) == []


def test_group_key_translation_only_in_storage():
    # modules/captcha.py parses a chat id from text; core/groups.py strips the
    # minus for a display title. Neither is a storage key.
    assert _lines_matching(
        r"\.lstrip\(['\"]-['\"]\)",
        {"core/storage.py", "core/groups.py", "modules/captcha.py"},
    ) == []


def test_shared_helpers_have_one_definition():
    for name in ("chunk_list", "_entities"):
        assert len(_lines_matching(rf"^def {name}\(")) == 1, name


def test_old_homes_stay_deleted():
    assert not (SRC / "web/groups.py").exists()
    assert not (SRC / "web/settings_registry.py").exists()
