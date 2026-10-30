"""Per-table points: results/T<k>/tables.json.

Summaries keep each entry's mean and finishing places. The rank view's
bootstrap needs every table's points instead, because resampling whole tables
keeps what happens inside one (a bot's points are another's loss).
Tournaments write the file as they finish; for older ones it is rebuilt from
the hand log by replaying the bust order and the cap's ICM split the way the
table did, then saved.

    {"entries": [name, ...], "tables": [[task, entries per seat, filler flags, points per seat], ...]}
"""

from __future__ import annotations

import json
import os

from .handlog import read_index, read_meta, read_table
from .scoring import table_points

FILE = "tables.json"


def rows(results: dict[int, dict]) -> list[list]:
    """Compact rows from run_tournament's per-table results, in task order; crashed tables are left out."""
    return [[tid, r["entries"], [int(f) for f in r["fillers"]], [round(p, 4) for p in r["points"]]]
            for tid, r in sorted(results.items()) if "crash" not in r]


def write(directory: str, names: list[str], table_rows: list[list]) -> None:
    tmp = os.path.join(directory, FILE + ".tmp")
    with open(tmp, "w") as f:
        json.dump({"entries": names, "tables": table_rows}, f, separators=(",", ":"))
    os.replace(tmp, os.path.join(directory, FILE))


def replay_points(hands: list, seats: int, starting_stack: int, points) -> list[float]:
    """A table's points per seat from its logged hands: busts in one hand place by
    starting stack (larger higher, exact ties share), survivors at the cap split by ICM."""
    stacks = [starting_stack] * seats
    places: dict[int, tuple[int, int]] = {}
    for h in hands:
        dealt, start, pay = h[3], h[4], h[8]
        before = dict(zip(dealt, start))
        for s, a, p in zip(dealt, start, pay):
            stacks[s] = a + p
        alive = [s for s in range(seats) if stacks[s] > 0]
        busted = sorted((s for s in dealt if stacks[s] == 0), key=lambda s: -before[s])
        place, k = len(alive) + 1, 0
        while k < len(busted):
            group = [s for s in busted[k:] if before[s] == before[busted[k]]]
            for s in group:
                places[s] = (place, place + len(group) - 1)
            place += len(group)
            k += len(group)
        if len(alive) == 1:
            places[alive[0]] = (1, 1)
    return table_points(places, [s for s in range(seats) if stacks[s] > 0], stacks, points)


def from_log(directory: str) -> dict:
    meta = read_meta(directory)
    out = []
    for m in read_index(directory):
        pts = replay_points(read_table(directory, m), meta["seats"], meta["starting_stack"], meta["points"])
        out.append([m["task"], m["entries"], [int(f) for f in m["fillers"]], [round(p, 4) for p in pts]])
    return {"entries": meta["entries"], "tables": out}


def load(directory: str) -> dict | None:
    """tables.json, rebuilt from a finished hand log (and saved) when it's missing; None without either."""
    path = os.path.join(directory, FILE)
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        pass
    try:
        if not read_meta(directory).get("finished"):
            return None
        got = from_log(directory)
    except (OSError, ValueError, KeyError):
        return None
    write(directory, got["entries"], got["tables"])
    return got
