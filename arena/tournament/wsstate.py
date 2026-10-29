"""Workspace state files shared by the kit scripts and the referee.

    .clock.json              {"windows": [{"name", "start", "end", "then", "submit"}]}, epoch seconds
    .submissions/log.jsonl   one record per submit attempt
    .submissions/<id>/       read-only snapshot of each accepted bot

With no windows (practice), submissions are always open.
"""

from __future__ import annotations

import json
import os
import time


def read_windows(ws: str) -> list[dict]:
    try:
        with open(os.path.join(ws, ".clock.json")) as f:
            return sorted(json.load(f).get("windows", []), key=lambda w: w["start"])
    except (OSError, ValueError):
        return []


def window_at(windows: list[dict], now: float) -> tuple[dict | None, dict | None]:
    """(open window, next window) at ``now``."""
    current = next((w for w in windows if w["start"] <= now < w["end"]), None)
    upcoming = next((w for w in windows if w["start"] > now), None)
    return current, upcoming


def submissions(ws: str) -> list[dict]:
    path = os.path.join(ws, ".submissions", "log.jsonl")
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def last_accepted(ws: str) -> dict | None:
    return next((r for r in reversed(submissions(ws)) if r.get("status") == "accepted"), None)


def append_log(ws: str, record: dict) -> None:
    os.makedirs(os.path.join(ws, ".submissions"), exist_ok=True)
    with open(os.path.join(ws, ".submissions", "log.jsonl"), "a") as f:
        f.write(json.dumps(record) + "\n")


def next_allowed(ws: str, cooldown_s: float) -> float:
    last = last_accepted(ws)
    return last["time"] + cooldown_s if last else 0.0


def write_json_atomic(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, default=str)
    os.replace(tmp, path)


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def fmt_clock(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts))
