"""One scored tournament: every iteration seats every entry once.

Each iteration shuffles the entries into tables of ``seats``; when the field
isn't a multiple of the table size, the empty seats get random copies of
submitted bots that score nothing. Tables are independent tasks with seeds
derived from the tournament seed, so results don't depend on the number of
workers. Per entry the summary has mean points per table with a standard
error and 95% interval, the finishing-place distribution, VPIP, PFR,
aggression, showdown rates, cap share, substitutions and decision CPU times.
"""

from __future__ import annotations

import math
import os
import platform
import random
import subprocess
import time
from collections import Counter
from dataclasses import asdict

from ..runner.loader import bot_hash
from .handlog import HandLogWriter
from .play import HIST_EDGES_US, STAT_KEYS, Settings, TableTask, derive
from .pool import Entry, TablePool
from .scoring import mean_ci


def default_workers(timing: str = "thread_cpu") -> int:
    """Performance cores on Apple Silicon when timing by thread CPU (efficiency
    cores run bot code about half as fast, which would distort the 1 ms rule);
    otherwise all cores but one."""
    if platform.system() == "Darwin" and platform.machine() == "arm64" and timing == "thread_cpu":
        try:
            out = subprocess.run(["sysctl", "-n", "hw.perflevel0.physicalcpu"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            return max(1, int(out))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return max(1, (os.cpu_count() or 2) - 1)


def plan_tables(n_entries: int, iterations: int, seats: int, seed: int) -> list[TableTask]:
    if n_entries < 2:
        raise ValueError("a tournament needs at least two entries")
    n_tables = math.ceil(n_entries / seats)
    tasks = []
    for it in range(iterations):
        r = random.Random(derive(seed, "iteration", it))
        seating = [(e, False) for e in range(n_entries)]
        seating += [(r.randrange(n_entries), True) for _ in range(n_tables * seats - n_entries)]
        r.shuffle(seating)
        for t in range(n_tables):
            chunk = seating[t * seats:(t + 1) * seats]
            tasks.append(TableTask(task_id=len(tasks), iteration=it, index=t,
                                   seed=derive(seed, "table", it, t),
                                   entries=[e for e, _ in chunk], fillers=[f for _, f in chunk]))
    return tasks


def _percentile_us(hist: list[int], q: float) -> float:
    total = sum(hist)
    if not total:
        return 0.0
    need, acc = q * total, 0
    for i, c in enumerate(hist):
        acc += c
        if acc >= need:
            return float(HIST_EDGES_US[i]) if i < len(HIST_EDGES_US) else float("inf")
    return float("inf")


def summarize(entries: list[Entry], results: dict[int, dict], st: Settings) -> list[dict]:
    n = len(entries)
    points = [[] for _ in range(n)]
    places = [[0.0] * st.seats for _ in range(n)]
    cap = [0] * n
    stats = [Counter() for _ in range(n)]
    hist = [[0] * (len(HIST_EDGES_US) + 1) for _ in range(n)]
    output: list[list[str]] = [[] for _ in range(n)]
    for tid in sorted(results):
        r = results[tid]
        if "crash" in r:
            continue
        survivors = set(r["survivors"])
        for seat, (e, filler) in enumerate(zip(r["entries"], r["fillers"])):
            if filler:
                continue
            points[e].append(r["points"][seat])
            span = r["places"].get(seat)
            if span is not None:
                best, worst = span
                for pl in range(best, worst + 1):
                    places[e][pl - 1] += 1 / (worst - best + 1)
            elif seat in survivors:
                cap[e] += 1
            for k, v in r["stats"][seat].items():
                if k in ("cpu_ns_max", "wall_ns_max"):
                    stats[e][k] = max(stats[e][k], v)
                else:
                    stats[e][k] += v
            for i, c in enumerate(r["hist"][seat]):
                hist[e][i] += c
            if seat in r["output"] and len(output[e]) < 20:
                output[e].extend(r["output"][seat][: 20 - len(output[e])])
    rows = []
    for e, entry in enumerate(entries):
        s = stats[e]
        m, se, lo, hi = mean_ci(points[e])
        hands = max(s["hands"], 1)
        decided = max(s["decisions"] - s["frozen"], 1)
        rows.append({
            "name": entry.name, "path": entry.path, "tables": len(points[e]),
            "mean": m, "se": se, "lo": lo, "hi": hi,
            "places": places[e], "cap_survivals": cap[e],
            "vpip": s["vpip"] / hands, "pfr": s["pfr"] / hands,
            "aggression": s["post_aggr"] / max(s["post_calls"], 1),
            "wtsd": s["showdowns"] / hands, "showdown_win": s["showdown_wins"] / max(s["showdowns"], 1),
            **{k: s[k] for k in STAT_KEYS if k not in ("vpip", "pfr", "cpu_ns_sum", "cpu_ns_max", "wall_ns_max")},
            "cpu_mean_us": s["cpu_ns_sum"] / decided / 1000,
            "cpu_p50_us": min(_percentile_us(hist[e], 0.5), s["cpu_ns_max"] / 1000),
            "cpu_p99_us": min(_percentile_us(hist[e], 0.99), s["cpu_ns_max"] / 1000),
            "cpu_max_us": s["cpu_ns_max"] / 1000, "wall_max_us": s["wall_ns_max"] / 1000,
            "output": output[e],
        })
    order = sorted(range(n), key=lambda i: -rows[i]["mean"])
    for rank, i in enumerate(order, 1):
        rows[i]["rank"] = rank
    return rows


def run_tournament(entries: list[Entry], settings: Settings, iterations: int = 400, seed: int = 0,
                   workers: int = 0, log_dir: str | None = None, progress=None,
                   time_budget_s: float | None = None) -> dict:
    """Play the tournament. With ``time_budget_s``, tables still unplayed when
    the budget runs out are skipped (for local practice runs)."""
    workers = workers or default_workers(settings.timing)
    tasks = plan_tables(len(entries), iterations, settings.seats, seed)
    writer = None
    if log_dir and settings.hand_logs:
        writer = HandLogWriter(log_dir, {
            "entries": [e.name for e in entries], "variant": settings.spec.to_dict(),
            "points": list(settings.points), "blinds": [list(b) for b in settings.blinds],
            "level_hands": settings.level_hands, "hand_cap": settings.hand_cap, "seats": settings.seats,
            "starting_stack": settings.starting_stack, "iterations": iterations, "seed": seed,
            "tables_total": len(tasks)})

    def on_result(r: dict) -> None:
        if writer is not None:
            writer.add(r)
        r.pop("log", None)

    t0 = time.perf_counter()
    with TablePool(entries, settings, workers) as pool:
        t1 = time.perf_counter()
        deadline = time.monotonic() + time_budget_s if time_budget_s else None
        results = pool.run(tasks, progress, deadline, on_result)
        notes, events = pool.notes, pool.events
    if len(results) < len(tasks):
        tasks = [t for t in tasks if t.task_id in results]
    elapsed = time.perf_counter() - t1
    log_bytes = writer.close(elapsed_s=elapsed, tables_done=len(results)) if writer is not None else 0
    crashed = sorted(t for t, r in results.items() if "crash" in r)
    import_problems: dict[str, str] = {}
    for r in results.values():
        import_problems.update(r.get("import_problems", {}))
    rows = summarize(entries, results, settings)
    for row in rows:
        row["hash"] = bot_hash(row["path"])
    meta = {
        "seed": seed, "iterations": iterations, "workers": workers, "tables": len(tasks),
        "hands": sum(r.get("hands", 0) for r in results.values()),
        "capped_tables": sum(1 for r in results.values() if r.get("capped")),
        "startup_s": t1 - t0, "elapsed_s": elapsed, "log_bytes": log_bytes,
        "settings": {**asdict(settings), "spec": settings.spec.to_dict()},
        "notes": notes, "events": events, "crashed_tables": crashed, "import_problems": import_problems,
    }
    return {"meta": meta, "entries": rows, "tables": results}


def zoo_entries(count: int | None = None, names: list[str] | None = None) -> list[Entry]:
    """House bots as entries; with ``count``, cycle through them to that many."""
    from ..house_bots import ZOO
    pool = names or sorted(ZOO)
    count = count or len(pool)
    return [Entry(f"{pool[i % len(pool)]}_{i // len(pool) + 1:02d}" if count > len(pool) else pool[i],
                  ZOO[pool[i % len(pool)]]["path"]) for i in range(count)]


def format_leaderboard(result: dict) -> str:
    rows = sorted(result["entries"], key=lambda r: r["rank"])
    meta = result["meta"]
    lines = [f"{meta['tables']} tables, {meta['hands']:,} hands, {meta['workers']} workers, "
             f"{meta['elapsed_s']:.1f}s ({meta['capped_tables']} tables hit the cap)"]
    width = max(len(r["name"]) for r in rows)
    for r in rows:
        subs = r["timeouts"] + r["errors"] + r["illegal"] + r["hangs"]
        lines.append(f"{r['rank']:>3}. {r['name']:<{width}}  {r['mean']:7.2f} ± {1.96 * r['se']:5.2f}"
                     f"   vpip {r['vpip']:4.0%} pfr {r['pfr']:4.0%}  subs {subs:<5d}"
                     f" p99 {r['cpu_p99_us']:>5.0f}µs")
    for ev in meta["events"]:
        lines.append(f"  event: {ev}")
    for note in meta["notes"]:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
