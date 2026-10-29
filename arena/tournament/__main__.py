"""Run one tournament from the command line.

    python -m arena.tournament --zoo 40 --iterations 400 [--workers 4] [--seed 1]
    python -m arena.tournament --bot mine=path/to/bot --zoo 11 --iterations 200 --log out/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from ..engine.spec import NLHE
from .play import Settings
from .pool import Entry
from .tournament import format_leaderboard, run_tournament, zoo_entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zoo", type=int, default=0, help="add this many house-bot entries (cycling the zoo)")
    ap.add_argument("--bot", action="append", default=[], metavar="NAME=DIR", help="add a bot directory")
    ap.add_argument("--iterations", type=int, default=400)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", metavar="DIR", help="write compressed hand logs here")
    ap.add_argument("--json", metavar="FILE", help="write the full summary as JSON")
    ap.add_argument("--timing", choices=("thread_cpu", "wall"), default="thread_cpu")
    a = ap.parse_args(argv)
    entries = []
    for spec in a.bot:
        name, _, path = spec.partition("=")
        if not path:
            ap.error(f"--bot needs NAME=DIR, got {spec!r}")
        entries.append(Entry(name, os.path.abspath(path)))
    if a.zoo:
        entries += zoo_entries(a.zoo)
    if len(entries) < 2:
        ap.error("need at least two entries (--zoo and/or --bot)")
    settings = Settings(spec=NLHE, timing=a.timing, hand_logs=bool(a.log))
    last = [0.0]

    def progress(done: int, total: int) -> None:
        now = time.perf_counter()
        if now - last[0] > 2 or done == total:
            last[0] = now
            print(f"\r  {done}/{total} tables", end="", file=sys.stderr, flush=True)

    result = run_tournament(entries, settings, a.iterations, a.seed, a.workers, a.log, progress)
    print(file=sys.stderr)
    print(format_leaderboard(result))
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"meta": result["meta"], "entries": result["entries"]}, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
