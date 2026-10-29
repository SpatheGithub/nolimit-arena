"""Bot validation, shared by kit/submit.py, kit/check_bot.py and the referee's freeze.

A bot passes when:
- static checks pass: bot/agent.py exists, every .py file compiles, the
  directory is within the size limit, and nothing imports the arena or kit
  packages (they aren't available at the real event);
- it imports and every Agent() starts within the limits;
- a smoke match against house bots, run by the real runner in its own process
  (timing, watchdog, guards), has no exceptions, hangs or illegal actions, and
  at most 2% timeouts.
Timeouts under 2% and a p99 near the limit are warnings, because timings on a
busy machine are noisy.
"""

from __future__ import annotations

import os
import py_compile
import re
import tempfile
from dataclasses import replace

from ..runner.loader import bot_hash, bot_size
from .play import Settings
from .pool import Entry
from .tournament import run_tournament

FORBIDDEN = re.compile(r"^\s*(?:from|import)\s+(arena|kit)\b", re.M)
MAX_TIMEOUT_SHARE = 0.02


def static_problems(bot_dir: str, size_limit_mb: float) -> list[str]:
    problems = []
    if not os.path.isfile(os.path.join(bot_dir, "agent.py")):
        return [f"{bot_dir}/agent.py is missing"]
    size = bot_size(bot_dir)
    if size > size_limit_mb * 2**20:
        problems.append(f"bot is {size / 2**20:.1f} MB; the limit is {size_limit_mb:g} MB")
    with tempfile.TemporaryDirectory() as tmp:
        for root, dirs, files in os.walk(bot_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                rel = os.path.relpath(path, bot_dir)
                try:
                    py_compile.compile(path, cfile=os.path.join(tmp, "x.pyc"), doraise=True)
                except py_compile.PyCompileError as e:
                    problems.append(f"{rel} doesn't compile: {str(e.exc_value)[:200]}")
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    m = FORBIDDEN.search(fh.read())
                if m:
                    problems.append(f"{rel} imports {m.group(1)!r}; copy what you need into bot/ instead")
    return problems


def house_opponents(house_dir: str | None, bot_dir: str, n: int) -> list[Entry]:
    """Up to ``n`` house bots (or copies of the bot itself if none are found)."""
    bots = []
    if house_dir and os.path.isdir(house_dir):
        bots = [os.path.join(house_dir, d) for d in sorted(os.listdir(house_dir))
                if not d.startswith(("_", ".")) and os.path.isfile(os.path.join(house_dir, d, "agent.py"))]
    if not bots:
        return [Entry(f"self_{i + 1}", bot_dir) for i in range(n)]
    return [Entry(os.path.basename(bots[i % len(bots)]) + ("" if i < len(bots) else f"_{i // len(bots) + 1}"),
                  bots[i % len(bots)]) for i in range(n)]


def validate(bot_dir: str, settings: Settings, house_dir: str | None = None, tables: int = 4,
             seed: int = 0, hand_cap: int = 60, extra_settings: Settings | None = None) -> dict:
    """Validate ``bot_dir``; returns {"ok", "reasons", "warnings", "hash", "stats", ...}."""
    bot_dir = os.path.abspath(bot_dir)
    out = {"ok": False, "reasons": [], "warnings": [], "hash": None, "stats": None, "events": []}
    problems = static_problems(bot_dir, settings.bot_size_limit_mb)
    if problems:
        out["reasons"] = problems
        return out
    out["hash"] = bot_hash(bot_dir)
    entries = [Entry("you", bot_dir)] + house_opponents(house_dir, bot_dir, settings.seats - 1)
    smoke = replace(extra_settings or settings, hand_cap=min(hand_cap, settings.hand_cap), hand_logs=False,
                    native_kill_s=max(3.0, settings.hang_watchdog_ms / 1000 * 20))
    res = run_tournament(entries, smoke, iterations=tables, seed=seed, workers=1)
    me = next(r for r in res["entries"] if r["name"] == "you")
    out["stats"] = me
    out["events"] = [e for e in res["meta"]["events"] if e.get("entry") == "you"]
    reasons, warnings = out["reasons"], out["warnings"]
    if "you" in res["meta"]["import_problems"]:
        reasons.append(res["meta"]["import_problems"]["you"])
    if me["import_failures"] or me["init_failures"]:
        reasons.append(f"Agent() failed to start at {me['init_failures'] + me['import_failures']} of "
                       f"{me['tables']} tables: " + " | ".join(me["output"][:3]))
    if out["events"]:
        reasons.append(f"bot stuck where the watchdog can't interrupt it ({len(out['events'])} times)")
    if me["errors"]:
        reasons.append(f"{me['errors']} exceptions in act(): " + " | ".join(
            l for l in me["output"] if l.startswith("["))[:300])
    if me["hangs"]:
        reasons.append(f"{me['hangs']} decisions ran past {settings.hang_watchdog_ms:g} ms and were interrupted")
    if me["illegal"]:
        reasons.append(f"{me['illegal']} illegal or malformed actions")
    decided = max(me["decisions"] - me["frozen"], 1)
    if me["timeouts"] > MAX_TIMEOUT_SHARE * decided:
        reasons.append(f"{me['timeouts']} of {decided} decisions over {settings.decision_limit_ms:g} ms")
    elif me["timeouts"]:
        warnings.append(f"{me['timeouts']} of {decided} decisions over the limit on this busy machine")
    if me["cpu_p99_us"] > 800 * settings.decision_limit_ms:
        warnings.append(f"p99 decision time ≈ {me['cpu_p99_us']:.0f} µs is close to the limit")
    if me["decisions"] == 0:
        reasons.append("the bot was never asked to act; check the smoke match settings")
    out["ok"] = not reasons
    return out


def describe(v: dict) -> list[str]:
    """A few lines for a terminal."""
    s = v.get("stats")
    lines = []
    if s:
        lines.append(f"smoke match: {s['tables']} tables, {s['decisions']} decisions, "
                     f"timing p50 {s['cpu_p50_us']:.0f} µs / p99 {s['cpu_p99_us']:.0f} µs / max {s['cpu_max_us']:.0f} µs; "
                     f"substitutions: {s['timeouts']} timeout, {s['errors']} error, {s['illegal']} illegal, "
                     f"{s['hangs']} hang")
    lines += [f"  problem: {r}" for r in v["reasons"]]
    lines += [f"  warning: {w}" for w in v["warnings"]]
    return lines
