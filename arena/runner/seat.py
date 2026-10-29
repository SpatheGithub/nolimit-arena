"""Timed, guarded calls into bot code.

Every call into a bot (import, ``Agent(config)``, ``act``, ``observe``) goes
through ``BotRunner.call``:

- CPU time is measured with ``time.thread_time_ns`` (or wall time when the
  thread clock is coarser than 10 µs or ``timing="wall"``); wall time is
  always recorded too.
- A SIGALRM watchdog ticking every 5 ms raises ``BotHang`` inside the bot once
  its wall-clock deadline passes. BotHang derives from BaseException, so a
  bot's ``except Exception`` can't swallow it; it is re-raised on every tick
  until the call returns.
- A heartbeat slot (shared with the parent process) holds the call's start
  time and hard limit; the parent kills a worker stuck in native code, where
  signals can't reach it.
- stdout and stderr are redirected to the bot's Capture.

The watchdog uses signals, so a BotRunner must live in the main thread of a
worker process.
"""

from __future__ import annotations

import signal
import sys
import time
from collections.abc import Callable
from typing import Any

from .guard import Capture

TICK_S = 0.005


class BotHang(BaseException):
    """Raised inside bot code by the watchdog."""


def _probe_ns(loops: int = 2000) -> int:
    """Thread CPU time of a fixed pure-Python loop (about 20 µs on an M4
    performance core): a gauge of how fast the current core runs bot code."""
    t0 = time.thread_time_ns()
    for _ in range(loops):
        pass
    return time.thread_time_ns() - t0


def thread_clock_resolution_ns(samples: int = 2000) -> int:
    """Smallest observed step of time.thread_time_ns()."""
    best = 1 << 62
    for _ in range(samples):
        t0 = time.thread_time_ns()
        t1 = time.thread_time_ns()
        while t1 == t0:
            t1 = time.thread_time_ns()
        best = min(best, t1 - t0)
    return best


class Heartbeat:
    """Writes (task, seat, start, hard limit) into a shared int64 array slot."""

    def __init__(self, array=None, slot: int = 0):
        self.a = array
        self.base = slot * 4

    def task(self, task_id: int) -> None:
        if self.a is not None:
            self.a[self.base] = task_id

    def begin(self, seat: int, hard_limit_s: float) -> None:
        if self.a is not None:
            b = self.base
            self.a[b + 1] = seat
            self.a[b + 3] = int(hard_limit_s * 1e9)
            self.a[b + 2] = time.monotonic_ns()

    def end(self) -> None:
        if self.a is not None:
            self.a[self.base + 2] = 0


class BotRunner:
    def __init__(self, timing: str = "thread_cpu", heartbeat: Heartbeat | None = None,
                 native_kill_s: float = 10.0):
        self.notes: list[str] = []
        if timing == "thread_cpu":
            res = thread_clock_resolution_ns()
            if res > 10_000:
                timing = "wall"
                self.notes.append(f"thread clock resolution {res / 1000:.0f} µs; timing by wall clock")
        self.timing = timing
        self.heartbeat = heartbeat or Heartbeat()
        self.native_kill_s = native_kill_s
        self.probe_base_ns = min(_probe_ns() for _ in range(200)) or 1
        self._deadline = 0
        self._stdout, self._stderr = sys.stdout, sys.stderr
        signal.signal(signal.SIGALRM, self._on_alarm)
        signal.setitimer(signal.ITIMER_REAL, TICK_S, TICK_S)

    def close(self) -> None:
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)

    def core_adjusted(self, cpu_ns: int) -> int:
        """For a call that went over its limit: rescale its CPU time to this
        worker's fastest-core speed if the thread is on a slower core now.
        The reference loop runs right after the call, on the same thread, so
        it almost always measures the core the call ran on."""
        if self.timing != "thread_cpu":
            return cpu_ns
        probe = min(_probe_ns(), _probe_ns())
        self.probe_base_ns = min(self.probe_base_ns, probe)
        ratio = probe / self.probe_base_ns
        return int(cpu_ns / ratio) if ratio > 1.15 else cpu_ns

    def refresh_baseline(self, probes: int = 3) -> None:
        """Lower the fastest-core baseline if this core beats it (once per table)."""
        self.probe_base_ns = min(self.probe_base_ns, *(_probe_ns() for _ in range(probes)))

    def _on_alarm(self, signum, frame) -> None:
        d = self._deadline
        if d and time.monotonic_ns() > d:
            raise BotHang()

    def call(self, fn: Callable[[Any], Any], arg: Any, wall_limit_s: float, capture: Capture,
             seat: int = -1, hard_limit_s: float | None = None) -> tuple[Any, str | None, int, int]:
        """Run ``fn(arg)``. Returns (value, failure, cpu_ns, wall_ns) where
        failure is None, "error" (exception) or "hang" (watchdog). The caller
        compares cpu_ns with its own limit."""
        value, failure = None, None
        cpu = wall = 0
        hb = self.heartbeat
        try:
            hb.begin(seat, hard_limit_s if hard_limit_s is not None else max(self.native_kill_s, wall_limit_s + 5))
            sys.stdout = sys.stderr = capture
            self._deadline = time.monotonic_ns() + int(wall_limit_s * 1e9)
            w0 = time.perf_counter_ns()
            c0 = time.thread_time_ns()
            try:
                value = fn(arg)
            except BotHang:
                failure = "hang"
            except Exception as e:
                failure = "error"
                capture.write(f"[{type(e).__name__}: {str(e)[:200]}]\n")
            except BaseException as e:  # SystemExit and friends from bot code
                failure = "error"
                capture.write(f"[{type(e).__name__}]\n")
            finally:
                c1 = time.thread_time_ns()
                w1 = time.perf_counter_ns()
                self._deadline = 0
            cpu, wall = c1 - c0, w1 - w0
        except BotHang:  # the alarm landed in our own bookkeeping, after the deadline
            self._deadline = 0
            failure = failure or "hang"
            value = None
        finally:
            self._deadline = 0
            sys.stdout, sys.stderr = self._stdout, self._stderr
            hb.end()
        if self.timing == "wall":
            cpu = wall
        return value, failure, cpu, wall
