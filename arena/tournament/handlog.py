"""Compressed hand logs: one zlib block of JSON per table, plus an index.

    <dir>/hands.zlog          concatenated blocks, in task order
    <dir>/hands.index.json    [{"task", "iteration", "index", "entries", "fillers", "offset", "size"}]

A table's JSON is a list of hands:
    [hand, button, [sb, bb, ante], seats, start_stacks, holes, board, decisions, payoffs, shown]
with holes, start_stacks and payoffs aligned with seats, and decisions as
described in play.py. ``bot_view`` gives one entry's hands with the other
seats anonymous and their cards hidden unless shown at showdown.
"""

from __future__ import annotations

import json
import os
import zlib
from collections.abc import Iterable, Iterator


def write_hand_log(directory: str, results: Iterable[dict]) -> int:
    """Write tables (results in task order, each with a "log" block); return bytes written."""
    os.makedirs(directory, exist_ok=True)
    index = []
    offset = 0
    with open(os.path.join(directory, "hands.zlog"), "wb") as f:
        for r in results:
            block = r.get("log")
            if not block:
                continue
            f.write(block)
            index.append({"task": r["task_id"], "iteration": r["iteration"], "index": r["index"],
                          "entries": r["entries"], "fillers": r["fillers"], "offset": offset,
                          "size": len(block)})
            offset += len(block)
    with open(os.path.join(directory, "hands.index.json"), "w") as f:
        json.dump(index, f)
    return offset


def read_index(directory: str) -> list[dict]:
    with open(os.path.join(directory, "hands.index.json")) as f:
        return json.load(f)


def read_table(directory: str, meta: dict) -> list:
    with open(os.path.join(directory, "hands.zlog"), "rb") as f:
        f.seek(meta["offset"])
        return json.loads(zlib.decompress(f.read(meta["size"])))


def bot_view(directory: str, entry: int, include_fillers: bool = False) -> Iterator[dict]:
    """Yield {"iteration", "table", "seat", "hands"} for every table ``entry``
    played, from its own seat's point of view."""
    for meta in read_index(directory):
        seats = [s for s, (e, filler) in enumerate(zip(meta["entries"], meta["fillers"]))
                 if e == entry and (include_fillers or not filler)]
        if not seats:
            continue
        hands = read_table(directory, meta)
        for me in seats:
            yield {"iteration": meta["iteration"], "table": meta["index"], "seat": me,
                   "hands": [_anonymize(h, me) for h in hands if me in h[3]]}


def _anonymize(h: list, me: int) -> dict:
    hand, button, blinds, seats, stacks, holes, board, decisions, payoffs, shown = h
    shown_set = set(shown)
    return {
        "hand": hand, "button": button, "blinds": blinds, "seats": seats,
        "stacks": dict(zip(seats, stacks)),
        "hole": holes[seats.index(me)],
        "shown": {s: holes[i] for i, s in enumerate(seats) if s in shown_set and s != me},
        "board": board, "decisions": decisions, "payoffs": dict(zip(seats, payoffs)),
    }
