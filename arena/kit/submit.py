"""Validate bot/ and, if it passes, make it your active submission.

    python kit/submit.py

Runs the referee's validation (static checks, then a smoke match against
house bots in the real runner), enforces the cooldown and the window
deadline, snapshots bot/ read-only into .submissions/<id>/, logs the attempt
and prints ACCEPTED or REJECTED.
"""

import os
import shutil
import stat
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(KIT)
sys.path.insert(0, KIT)

from arena.tournament.card import load_card, settings_from_card  # noqa: E402
from arena.tournament.validate import describe, validate  # noqa: E402
from arena.tournament.wsstate import (append_log, fmt_clock, fmt_duration, next_allowed,  # noqa: E402
                                      read_windows, submissions, window_at)


def window_problem(now: float) -> str | None:
    windows = read_windows(WS)
    if not windows:
        return None
    current, upcoming = window_at(windows, now)
    if current and current.get("submit", True):
        return None
    if upcoming:
        return f"no submission window is open; the next opens at {fmt_clock(upcoming['start'])}"
    return "the submission windows are over"


def make_read_only(path: str) -> None:
    for root, dirs, files in os.walk(path):
        for name in files:
            p = os.path.join(root, name)
            os.chmod(p, os.stat(p).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def main() -> int:
    card = load_card(os.path.join(KIT, "event.json"))
    settings = settings_from_card(card)
    start = time.time()
    problem = window_problem(start)
    wait = next_allowed(WS, card["cooldown_seconds"]) - start
    if problem is None and wait > 0:
        problem = f"cooldown: the next submission is allowed in {fmt_duration(wait)}"
    if problem:
        append_log(WS, {"time": start, "status": "rejected", "reasons": [problem]})
        print(f"REJECTED: {problem}")
        return 1
    print("Validating (static checks, then a smoke match against house bots)...", flush=True)
    v = validate(os.path.join(WS, "bot"), settings, os.path.join(KIT, "house_bots"), tables=3,
                 seed=int(start) % 100_000)
    now = time.time()
    for line in describe(v):
        print(line)
    if v["ok"]:
        problem = window_problem(now)
        if problem:
            v["ok"], v["reasons"] = False, [f"the window closed during validation ({problem})"]
    record = {"time": now, "hash": v["hash"], "warnings": v["warnings"],
              "timing": {k: v["stats"][k] for k in ("cpu_p50_us", "cpu_p99_us", "cpu_max_us")} if v["stats"] else None}
    if not v["ok"]:
        append_log(WS, {**record, "status": "rejected", "reasons": v["reasons"]})
        print("REJECTED: " + "; ".join(v["reasons"]))
        return 1
    n = 1 + sum(1 for r in submissions(WS) if r.get("status") == "accepted")
    sid = f"{n:03d}-{v['hash'][:8]}"
    dst = os.path.join(WS, ".submissions", sid)
    shutil.copytree(os.path.join(WS, "bot"), dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    make_read_only(dst)
    append_log(WS, {**record, "status": "accepted", "id": sid})
    print(f"ACCEPTED: submission {sid}. Next submission allowed at "
          f"{fmt_clock(now + card['cooldown_seconds'])}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
