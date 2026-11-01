"""When the computer slept, from macOS's power log (`pmset -g log`).

    python -m arena.referee sleep <event>

The referee gives a window back the time the computer sleeps through
(Event._add_back). For events that ran before it did, this measures each
builder window's sleep afterwards and stores it as the window's ``asleep_s``,
which the report shows: the builders lost that time. The power log keeps only
the last few days, so windows it doesn't reach are left alone. Only real sleep
counts; in a dark wake the computer runs, if fitfully.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess

LINE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}) (Sleep|Wake|DarkWake)\s+(?:Entering Sleep|Wake from|DarkWake from)")
STAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}) ", re.M)


def power_log() -> str:
    return subprocess.run(["pmset", "-g", "log"], capture_output=True, text=True, timeout=300).stdout


def _time(stamp: str) -> float:
    return dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S %z").timestamp()


def asleep_intervals(log: str) -> tuple[float | None, list[tuple[float, float]]]:
    """(when the log starts, [(fell asleep, woke)]): any wake, dark or full, ends a sleep."""
    first = STAMP.search(log)
    out, start = [], None
    for line in log.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        t = _time(m.group(1))
        if m.group(2) == "Sleep":
            start = t if start is None else start
        elif start is not None:
            out.append((start, t))
            start = None
    return (_time(first.group(1)) if first else None), out


def overlap(intervals: list[tuple[float, float]], start: float, end: float) -> float:
    return sum(max(0.0, min(end, b) - max(start, a)) for a, b in intervals)


def annotate(ev, log: str | None = None) -> list[str]:
    """Store ``asleep_s`` on each window the log covers and the referee didn't already
    make up for (``slept_s``); returns a line per window."""
    begins, intervals = asleep_intervals(power_log() if log is None else log)
    lines = []
    for w in ev.state.get("windows", []):
        name = f"{w['kind']} {w['k']}"
        minutes = (w["end"] - w["start"]) / 60
        if "slept_s" in w:
            lines.append(f"{name}: the referee added back {w['slept_s'] / 60:.0f} min of sleep")
        elif begins is None or w["start"] < begins:
            lines.append(f"{name}: before the power log starts; not measured")
        else:
            w["asleep_s"] = round(overlap(intervals, w["start"], w["end"]))
            lines.append(f"{name}: asleep {w['asleep_s'] / 60:.0f} of {minutes:.0f} min")
    ev.save()
    return lines
