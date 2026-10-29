"""Compressed hand logs, written live as tables finish.

    <dir>/hands.meta.json     names, variant and table rules (written at the start, updated at the end)
    <dir>/hands.zlog          one zlib block of JSON per table, in the order tables finished
    <dir>/hands.index.jsonl   one line per table: {"task", "iteration", "index", "entries", "fillers",
                              "offset", "size", "hands"}

A table's JSON is a list of hands:
    [hand, button, [sb, bb, ante], seats, start_stacks, holes, board, decisions, payoffs, shown]
with holes, start_stacks and payoffs aligned with seats, and decisions as
described in play.py. ``bot_view`` gives one entry's hands with the other
seats anonymous and their cards hidden unless shown at showdown.
"""

from __future__ import annotations

import json
import os
import time
import zlib
from collections.abc import Iterator


class HandLogWriter:
    def __init__(self, directory: str, meta: dict):
        os.makedirs(directory, exist_ok=True)
        self.dir = directory
        self.meta = {**meta, "started": time.time(), "finished": False}
        self._write_meta()
        self.data = open(os.path.join(directory, "hands.zlog"), "wb")
        self.index = open(os.path.join(directory, "hands.index.jsonl"), "w")
        self.offset = 0

    def _write_meta(self) -> None:
        tmp = os.path.join(self.dir, "hands.meta.json.tmp")
        with open(tmp, "w") as f:
            json.dump(self.meta, f)
        os.replace(tmp, os.path.join(self.dir, "hands.meta.json"))

    def add(self, result: dict) -> None:
        block = result.get("log")
        if not block:
            return
        self.data.write(block)
        self.data.flush()
        self.index.write(json.dumps({
            "task": result["task_id"], "iteration": result["iteration"], "index": result["index"],
            "entries": result["entries"], "fillers": result["fillers"], "offset": self.offset,
            "size": len(block), "hands": result.get("hands", 0)}) + "\n")
        self.index.flush()
        self.offset += len(block)

    def close(self, **extra) -> int:
        self.data.close()
        self.index.close()
        self.meta.update(finished=True, finished_at=time.time(), **extra)
        self._write_meta()
        return self.offset


def read_meta(directory: str) -> dict:
    with open(os.path.join(directory, "hands.meta.json")) as f:
        return json.load(f)


def read_index(directory: str) -> list[dict]:
    """Index entries in task order (only complete lines, so safe while writing)."""
    out = []
    with open(os.path.join(directory, "hands.index.jsonl")) as f:
        for line in f:
            if line.endswith("\n"):
                out.append(json.loads(line))
    return sorted(out, key=lambda m: m["task"])


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
