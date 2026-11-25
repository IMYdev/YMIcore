"""Pre-import copies of a group's files, for /importundo.

One snapshot per group: the latest import. After the import, each file's
hash is recorded, so undo can tell whether anything changed since and
refuse to discard that work unless forced.
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from core.storage import group_path, import_snapshot_dir

SECTIONS = ("notes", "filters", "words", "greetings")
UNDO_WINDOW_SECONDS = 24 * 3600
_MANIFEST = "manifest.json"

NONE, EXPIRED, CHANGED, RESTORED = "none", "expired", "changed", "restored"


def _hash(path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _write_json(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def _read_manifest(directory: Path) -> dict | None:
    try:
        return json.loads((directory / _MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def take(gid) -> None:
    """Copy the group's files before an import, replacing any older snapshot."""
    directory = Path(import_snapshot_dir(gid))
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    existed = {}
    for section in SECTIONS:
        source = Path(group_path(section, gid))
        existed[section] = source.exists()
        if existed[section]:
            shutil.copyfile(source, directory / section)
    _write_json(directory / _MANIFEST, {"ts": time.time(), "existed": existed, "after": {}})


def seal(gid) -> None:
    """Record each file's state right after the import."""
    directory = Path(import_snapshot_dir(gid))
    manifest = _read_manifest(directory)
    if manifest is None:
        return
    manifest["after"] = {s: _hash(group_path(s, gid)) for s in SECTIONS}
    _write_json(directory / _MANIFEST, manifest)


def discard(gid) -> None:
    shutil.rmtree(import_snapshot_dir(gid), ignore_errors=True)


def _replace_atomically(source: Path, target: Path) -> None:
    # A new inode, so the stat-validated read cache sees the change.
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    os.close(fd)
    try:
        shutil.copyfile(source, tmp)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def restore(gid, *, force=False, now=None) -> tuple[str, list[str]]:
    """Undo the last import. Returns (status, changed sections)."""
    directory = Path(import_snapshot_dir(gid))
    manifest = _read_manifest(directory)
    if manifest is None:
        return NONE, []
    now = time.time() if now is None else now
    if now - manifest.get("ts", 0) > UNDO_WINDOW_SECONDS:
        discard(gid)
        return EXPIRED, []
    after = manifest.get("after") or {}
    changed = [s for s in SECTIONS if s in after and _hash(group_path(s, gid)) != after[s]]
    if changed and not force:
        return CHANGED, changed
    for section in SECTIONS:
        target = Path(group_path(section, gid))
        if manifest["existed"].get(section):
            _replace_atomically(directory / section, target)
        elif target.exists():
            target.unlink()
    discard(gid)
    return RESTORED, changed
