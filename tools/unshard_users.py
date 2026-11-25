#!/usr/bin/env python3
"""Rebuild runtime/users/registry.json from the users shards (rollback aid).

Newer YMIcore versions keep users in runtime/users/shard_NN.json and leave the
old registry.json untouched, so a downgraded bot only knows the users it had
before the upgrade. Run this before downgrading to give the old version every
user, including ones first seen after the upgrade:

    cd src && python ../tools/unshard_users.py          # same dir as the bot
    python tools/unshard_users.py --runtime src/runtime  # or point at it

The shards are not modified. Upgrading again later merges any changes the old
version made to registry.json back into the shards automatically.
Stdlib only: it does not import the bot or need its token.
"""

import argparse
import glob
import json
import os
import sys
import tempfile


def _atomic_write(path, data, indent):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runtime", default="runtime", help="the bot's runtime directory (default: ./runtime)")
    args = parser.parse_args(argv)

    users_dir = os.path.join(args.runtime, "users")
    shards = sorted(glob.glob(os.path.join(users_dir, "shard_*.json")))
    if not shards:
        print(f"No shards in {users_dir}; nothing to do.")
        return 1

    users = {}
    for path in shards:
        with open(path, encoding="utf-8") as f:
            users.update((json.load(f) or {}).get("users") or {})
    ordered = dict(sorted(users.items(), key=lambda kv: ((kv[1] or {}).get("first_seen") or 0, kv[0])))

    registry = os.path.join(users_dir, "registry.json")
    if os.path.exists(registry):
        backup = registry + ".before-unshard"
        with open(registry, "rb") as src, open(backup, "wb") as dst:
            dst.write(src.read())
        print(f"Backed up the existing registry to {backup}")
    _atomic_write(registry, {"users": ordered}, indent=4)

    # Tell the new version this registry already matches the shards, so it is
    # only merged again if the old version changes it.
    st = os.stat(registry)
    _atomic_write(os.path.join(users_dir, "registry.merged.json"),
                  {"stamp": [st.st_ino, st.st_mtime_ns, st.st_size]}, indent=4)
    print(f"Wrote {len(ordered)} users from {len(shards)} shards to {registry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
