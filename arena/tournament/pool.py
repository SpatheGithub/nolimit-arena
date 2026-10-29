"""Worker processes that play tables, recovering from bots stuck in native code.

The parent hands tasks to idle workers over per-worker pipes (no shared queue
a killed worker could leave locked) and watches each worker's heartbeat. A
worker whose current bot call has run past its hard limit (stuck where the
SIGALRM watchdog can't reach, e.g. inside a C extension) is killed and
replaced; its table is replayed from the start with that seat forced to
fold/check, and the event is reported. A worker that dies is replaced and its
table retried, up to twice.
"""

from __future__ import annotations

import collections
import multiprocessing as mp
import sys
import time
import traceback
from dataclasses import dataclass, replace
from multiprocessing.connection import wait

from ..runner.guard import Capture, install_guards
from ..runner.loader import bot_size, load_bot
from ..runner.seat import BotRunner, Heartbeat
from .play import Settings, TableTask, play_table

IMPORT_SEAT = -1000  # heartbeat seat for importing entry e is IMPORT_SEAT - e


@dataclass(frozen=True)
class Entry:
    name: str
    path: str


def prefer_performance_cores() -> None:
    """On macOS, ask the scheduler to keep this thread on performance cores."""
    if sys.platform == "darwin":
        try:
            import ctypes
            fn = ctypes.CDLL("/usr/lib/libSystem.dylib").pthread_set_qos_class_self_np
            fn.argtypes, fn.restype = [ctypes.c_uint, ctypes.c_int], ctypes.c_int
            fn(0x21, 0)  # QOS_CLASS_USER_INTERACTIVE
        except Exception:
            pass


def _worker_main(slot: int, entries: list[Entry], st: Settings, conn, hb_array) -> None:
    prefer_performance_cores()
    notes = install_guards(st.memory_mb)
    hb = Heartbeat(hb_array, slot)
    runner = BotRunner(st.timing, hb, st.native_kill_s)
    classes: dict[str, type | None] = {}
    problems: dict[str, str] = {}

    def agent_class(entry_index: int) -> type | None:
        path = entries[entry_index].path
        if path not in classes:
            if bot_size(path) > st.bot_size_limit_mb * 2**20:
                classes[path], problems[path] = None, f"bot larger than {st.bot_size_limit_mb} MB"
            else:
                cap = Capture(keep=5)
                cls, failure, _, _ = runner.call(load_bot, path, st.import_limit_s, cap,
                                                 IMPORT_SEAT - entry_index, hard_limit_s=st.import_limit_s + 10)
                classes[path] = cls if failure is None else None
                if failure:
                    problems[path] = f"import {failure}: " + " | ".join(cap.lines)[:300]
        return classes[path]

    conn.send(("ready", notes + runner.notes))
    while True:
        task = conn.recv()
        if task is None:
            break
        hb.task(task.task_id)
        try:
            result = play_table(task, st, runner, agent_class)
            result["import_problems"] = {entries[e].name: problems[entries[e].path]
                                         for e in set(task.entries) if entries[e].path in problems}
        except Exception:
            result = {"task_id": task.task_id, "crash": traceback.format_exc()[-2000:]}
        conn.send(("result", result))
    runner.close()


class TablePool:
    def __init__(self, entries: list[Entry], settings: Settings, workers: int):
        self.ctx = mp.get_context("spawn")
        self.entries, self.settings, self.workers = entries, settings, workers
        self.hb = self.ctx.RawArray("q", 4 * workers)
        self.procs: list = [None] * workers
        self.conns: list = [None] * workers
        self.busy: dict[int, TableTask | None] = {}
        self.notes: list[str] = []
        self.events: list[dict] = []
        self.bad_paths: set[str] = set()  # bots whose import hung in native code
        for slot in range(workers):
            self._start(slot)

    def _start(self, slot: int) -> None:
        for k in range(4):
            self.hb[4 * slot + k] = 0
        parent, child = self.ctx.Pipe()
        p = self.ctx.Process(target=_worker_main, args=(slot, self.entries, self.settings, child, self.hb),
                             daemon=True)
        p.start()
        child.close()
        self.procs[slot], self.conns[slot] = p, parent
        self.busy[slot] = None
        kind, notes = parent.recv()
        for note in notes:
            if note not in self.notes:
                self.notes.append(note)

    def _kill(self, slot: int) -> None:
        p = self.procs[slot]
        if p.is_alive():
            p.kill()
        p.join(5)
        self.conns[slot].close()

    def run(self, tasks: list[TableTask], progress=None, deadline: float | None = None) -> dict[int, dict]:
        """Play ``tasks``; with ``deadline`` (time.monotonic()), stop handing out
        tasks once it passes and return the tables finished by then."""
        queue = collections.deque(tasks)
        retries: collections.Counter = collections.Counter()
        results: dict[int, dict] = {}
        total = len(tasks)
        while len(results) < total:
            if deadline is not None and time.monotonic() > deadline:
                queue.clear()
                if all(t is None for t in self.busy.values()):
                    break
            for slot in range(self.workers):
                if self.busy[slot] is None and queue:
                    task = queue.popleft()
                    if self.bad_paths:
                        bad = {s for s, e in enumerate(task.entries) if self.entries[e].path in self.bad_paths}
                        if not bad <= set(task.frozen):
                            task = replace(task, frozen=tuple(sorted(set(task.frozen) | bad)))
                    self.busy[slot] = task
                    self.conns[slot].send(task)
            ready = wait([c for s, c in enumerate(self.conns) if self.busy[s] is not None], timeout=0.2)
            for conn in ready:
                slot = self.conns.index(conn)
                try:
                    kind, result = conn.recv()
                except (EOFError, OSError):
                    continue  # handled below as a dead worker
                task = self.busy[slot]
                self.busy[slot] = None
                if "crash" in result and retries[task.task_id] < 2:
                    retries[task.task_id] += 1
                    self.events.append({"kind": "table_crash", "task": task.task_id, "detail": result["crash"]})
                    queue.appendleft(task)
                    continue
                results[result["task_id"]] = result
                if progress:
                    progress(len(results), total)
            now = time.monotonic_ns()
            for slot in range(self.workers):
                task = self.busy[slot]
                if task is None:
                    continue
                b = 4 * slot
                seat, start, limit = self.hb[b + 1], self.hb[b + 2], self.hb[b + 3]
                stuck = start and now - start > limit
                if not stuck and self.procs[slot].is_alive():
                    continue
                self._kill(slot)
                if stuck and seat >= 0:
                    entry = self.entries[task.entries[seat]].name
                    self.events.append({"kind": "native_hang", "task": task.task_id, "seat": seat,
                                        "entry": entry})
                    queue.appendleft(replace(task, frozen=tuple(sorted(set(task.frozen) | {seat}))))
                elif stuck and seat <= IMPORT_SEAT:
                    entry = self.entries[IMPORT_SEAT - seat]
                    self.bad_paths.add(entry.path)
                    self.events.append({"kind": "import_hang", "task": task.task_id, "entry": entry.name})
                    queue.appendleft(task)
                elif retries[task.task_id] < 2:
                    retries[task.task_id] += 1
                    self.events.append({"kind": "worker_died", "task": task.task_id})
                    queue.appendleft(task)
                else:
                    results[task.task_id] = {"task_id": task.task_id, "crash": "worker died three times"}
                self._start(slot)
        return results

    def close(self) -> None:
        for slot in range(self.workers):
            try:
                self.conns[slot].send(None)
            except (OSError, BrokenPipeError):
                pass
        for p in self.procs:
            p.join(5)
            if p.is_alive():
                p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
