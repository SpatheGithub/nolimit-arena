"""Refresh the house bots' copies of the shared helpers.

    python -m arena.house_bots.sync [--check]

The sources are _common.py and its data file _common.json in this directory.
A bot package gets identical copies when one of its own modules imports
``_common``. With --check, nothing is written: stale or missing copies are
listed and the exit status is 1.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from . import HERE, ZOO

SHARED = ("_common.py", "_common.json")
_USES = re.compile(r"^\s*from\s+\.(_common\s+import|\s+import\s+.*\b_common\b)", re.M)


def users() -> list[str]:
    """Package directories whose own modules import _common."""
    out = []
    for info in ZOO.values():
        path = info["path"]
        for name in sorted(os.listdir(path)):
            if name.endswith(".py") and name not in SHARED:
                with open(os.path.join(path, name)) as f:
                    if _USES.search(f.read()):
                        out.append(path)
                        break
    return out


def _read(path: str) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def stale() -> list[str]:
    """Copies that are missing or differ from the sources."""
    sources = {name: _read(os.path.join(HERE, name)) for name in SHARED}
    return [os.path.join(pkg, name) for pkg in users() for name in SHARED
            if _read(os.path.join(pkg, name)) != sources[name]]


def sync() -> list[str]:
    """Write every stale copy; returns the paths written."""
    written = stale()
    for path in written:
        with open(os.path.join(HERE, os.path.basename(path)), "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Refresh the house bots' copies of _common.py and _common.json.")
    ap.add_argument("--check", action="store_true", help="only list stale copies; exit 1 if any")
    args = ap.parse_args(argv)
    paths = stale() if args.check else sync()
    for path in paths:
        print(("stale: " if args.check else "updated: ") + os.path.relpath(path, HERE))
    if not paths:
        print(f"{len(users())} packages up to date")
    return 1 if args.check and paths else 0


if __name__ == "__main__":
    sys.exit(main())
