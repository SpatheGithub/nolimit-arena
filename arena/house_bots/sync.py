"""Refresh the house bots' copies of the shared helpers.

    python -m arena.house_bots.sync [--check]

The shared modules are _common (with _common.json) and _strategy (with
_strategy.json; it builds on _common) in this directory. A bot package gets
identical copies of each shared module its own modules import, plus what
those build on, and no others: builders' kits carry the quick-build
packages, so _strategy must not end up in them. With --check, nothing is
written: stale, missing or extra copies are listed and the exit status is 1.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from . import HERE, ZOO

SHARED = {"_common": ("_common.py", "_common.json"), "_strategy": ("_strategy.py", "_strategy.json")}
NEEDS = {"_strategy": ("_common",)}
FILES = tuple(name for files in SHARED.values() for name in files)


def _imports(text: str, module: str) -> bool:
    return re.search(rf"^\s*from\s+\.({module}\s+import|\s+import\s+.*\b{module}\b)", text, re.M) is not None


def needs(path: str) -> list[str]:
    """Shared modules the package's own modules import, plus what those build on."""
    found = set()
    for name in sorted(os.listdir(path)):
        if name.endswith(".py") and name not in FILES:
            with open(os.path.join(path, name)) as f:
                text = f.read()
            found.update(m for m in SHARED if _imports(text, m))
    for m in sorted(found):
        found.update(NEEDS.get(m, ()))
    return sorted(found)


def users() -> list[str]:
    """Package directories that use at least one shared module."""
    return [info["path"] for info in ZOO.values() if needs(info["path"])]


def _read(path: str) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def wanted() -> list[str]:
    """Every copy that should exist."""
    return [os.path.join(info["path"], name) for info in ZOO.values()
            for m in needs(info["path"]) for name in SHARED[m]]


def stale() -> list[str]:
    """Copies that are missing or differ from the sources."""
    return [path for path in wanted() if _read(path) != _read(os.path.join(HERE, os.path.basename(path)))]


def extra() -> list[str]:
    """Copies of shared files in packages that don't use them."""
    keep = set(wanted())
    return [os.path.join(info["path"], name) for info in ZOO.values() for name in FILES
            if os.path.exists(os.path.join(info["path"], name)) and os.path.join(info["path"], name) not in keep]


def sync() -> tuple[list[str], list[str]]:
    """Write every stale copy and delete every extra one; returns (written, deleted)."""
    written, deleted = stale(), extra()
    for path in written:
        with open(os.path.join(HERE, os.path.basename(path)), "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
    for path in deleted:
        os.remove(path)
    return written, deleted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Refresh the house bots' copies of the shared helpers.")
    ap.add_argument("--check", action="store_true", help="only list stale or extra copies; exit 1 if any")
    args = ap.parse_args(argv)
    changed = (stale(), extra()) if args.check else sync()
    for label, paths in zip(("stale: " if args.check else "updated: ", "extra: " if args.check else "deleted: "),
                            changed):
        for path in paths:
            print(label + os.path.relpath(path, HERE))
    if not any(changed):
        print(f"{len(users())} packages up to date")
    return 1 if args.check and any(changed) else 0


if __name__ == "__main__":
    sys.exit(main())
