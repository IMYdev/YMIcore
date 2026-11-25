"""IMYDB with a shared, stat-validated read cache.

Every store goes through this subclass (via core.storage). Upstream IMYDB
re-reads and parses the whole file on every construction; on the message hot
path that is the dominant cost, so parsed files are kept in memory and reused
while the file on disk is unchanged.

Invalidation
    A cached copy is reused only when the file's (dev, inode, mtime, size)
    stamp still matches. Atomic replaces (IMYDB, the web panel, another bot
    process) get a new inode, and in-place edits change mtime/size, so every
    writer is seen. To survive coarse filesystem timestamps, a copy is only
    trusted once the file's mtime is older than the moment it was read by more
    than RACY_NS ("racy git" rule); a freshly written file is simply re-read.

Contract for callers
    Instances of the same path share one ``data`` dict. Never mutate a value
    returned by ``get()`` (or ``.data``) unless you then call ``set()`` /
    ``delete()`` on the same instance; a mutation that is not saved would be
    visible to other readers until the file next changes. If a save fails, the
    cached copy is dropped so the next reader goes back to disk.
"""

import json
import os
import tempfile
import time
from collections import OrderedDict
from pathlib import Path

from core.imysdb.imydb import IMYDB as _IMYDB

# A stamp match is trusted once the copy was read this long after the file's
# mtime. Linux file timestamps tick at most every ~10ms (coarse clock), so
# 50ms covers them while costing at most about one extra parse per write.
# Atomic writers are always detected (new inode); this window only matters
# for in-place edits on filesystems with coarser timestamps.
RACY_NS = 50_000_000
# Bound memory on hosts with many groups; least recently used files go first.
MAX_CACHED_FILES = 4096
# Separators used when indent=None (compact files for large stores).
COMPACT_SEPARATORS = (",", ":")

# abspath -> (stamp, read_started_ns, data)
_CACHE: "OrderedDict[str, tuple[tuple, int, dict]]" = OrderedDict()


def _stamp(st) -> tuple:
    return (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)


def _remember(key, stamp, read_started_ns, data) -> None:
    _CACHE[key] = (stamp, read_started_ns, data)
    _CACHE.move_to_end(key)
    while len(_CACHE) > MAX_CACHED_FILES:
        _CACHE.popitem(last=False)


def clear_cache() -> None:
    """Drop every cached file (tests; never needed for correctness)."""
    _CACHE.clear()


class IMYDB(_IMYDB):
    """IMYDB + read cache + quarantine of unreadable files.

    ``indent`` controls the on-disk format: 4 (default, hand-editable, same as
    upstream) or None for compact JSON. Both load in any IMYDB version.
    """

    def __init__(self, file_path, indent=4):
        self.indent = indent
        super().__init__(file_path)

    def _key(self) -> str:
        return os.path.abspath(self.file_path)

    def load_data(self) -> None:
        key = self._key()
        try:
            st = os.stat(self.file_path)
        except OSError:
            st = None

        if st is not None:
            entry = _CACHE.get(key)
            if (entry is not None and entry[0] == _stamp(st)
                    and st.st_mtime_ns < entry[1] - RACY_NS):
                _CACHE.move_to_end(key)
                self.data = entry[2]
                return

        read_started = time.time_ns()
        self._load_from_disk()
        if st is not None and self.file_path.exists():
            try:
                now_st = os.stat(self.file_path)
            except OSError:
                return
            # Only cache what we read if nothing replaced the file meanwhile;
            # a missing/quarantined file is cached by save_data() instead.
            if _stamp(now_st) == _stamp(st):
                _remember(key, _stamp(st), read_started, self.data)

    def _load_from_disk(self) -> None:
        try:
            super().load_data()
        except (ValueError, TypeError) as exc:
            self.file_path = Path(self.file_path)
            backup = self.file_path.with_name(
                f"{self.file_path.name}.corrupt-{int(time.time())}"
            )
            self.file_path.replace(backup)
            print(f"Warning: {self.file_path} is unreadable ({exc}); moved to {backup}, starting empty.")
            self.data = {}
            self.save_data()

    def save_data(self) -> None:
        """Atomically save to disk (same procedure as upstream) and cache."""
        key = self._key()
        write_started = time.time_ns()
        try:
            self._write()
            st = os.stat(self.file_path)
        except BaseException:
            _CACHE.pop(key, None)
            raise
        _remember(key, _stamp(st), write_started, self.data)

    def _write(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        dump_kwargs = {"ensure_ascii": False}
        if self.indent is None:
            dump_kwargs["separators"] = COMPACT_SEPARATORS
        else:
            dump_kwargs["indent"] = self.indent
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.file_path.parent,
                prefix=f".{self.file_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temp_path = Path(file.name)
                json.dump(self.data, file, **dump_kwargs)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, self.file_path)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()
