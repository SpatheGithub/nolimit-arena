"""Who is winning an event: the data behind the live viewer's Results view.

Per finished tournament: each team's points per table (mean, 95% interval,
rank), its finishing places and the share of tables it won. Over the event so
far: the weighted score (1·T1 + 2·T2 + ...), its 95% interval, the rank after
each tournament, and each team's chance of finishing first and of making the
regional cut (top 5 advance). Those chances come from normal draws around each
team's weighted score, using each tournament's standard error: the summaries
don't keep per-table points, so a bootstrap isn't possible, and the draws
ignore that one team's points are another's loss. They are seeded, so they
don't flicker between refreshes.

It reads the referee's files only, and redoes the work only when a summary
changes, so polling it costs the tournaments' workers nothing.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

CUTOFF = 5  # top 5 per regional advance (docs/OFFICIAL_FORMAT.md)
DRAWS = 20_000
_cache: dict[str, tuple[tuple, dict]] = {}


def _load(path: str):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def event_results(ev_dir: str, cutoff: int = CUTOFF) -> dict:
    card = _load(os.path.join(ev_dir, "card.json")) or {}
    total = int(card.get("tournaments") or 0)
    paths = [os.path.join(ev_dir, "results", f"T{k}", "summary.json") for k in range(1, total + 1)]
    key = (cutoff, *(os.path.getmtime(p) if os.path.exists(p) else 0.0 for p in paths))
    hit = _cache.get(ev_dir)
    if hit is None or hit[0] != key:
        hit = (key, _standings(ev_dir, total, paths, cutoff))
        _cache[ev_dir] = hit
    phase = (_load(os.path.join(ev_dir, "state.json")) or {}).get("phase", "")
    kind, _, k = phase.partition(":")
    playing = int(k) if kind in ("freeze", "tournament") and k.isdigit() else None
    return {**hit[1], "key": "-".join(f"{x:.0f}" for x in key[1:]), "phase": phase, "playing": playing}


def _standings(ev_dir: str, total: int, paths: list[str], cutoff: int) -> dict:
    teams = {t["team"]: t for t in _load(os.path.join(ev_dir, "teams.json")) or []}
    done, per = [], {}
    for k, path in enumerate(paths, 1):
        summary = _load(path)
        if not summary or not summary.get("entries"):
            continue
        done.append(k)
        for e in summary["entries"]:
            places = e.get("places") or []
            tables = e.get("tables") or sum(places) or 1
            per.setdefault(e["name"], {})[k] = {
                "mean": e["mean"], "se": e.get("se", 0.0), "lo": e.get("lo", e["mean"]), "hi": e.get("hi", e["mean"]),
                "rank": e.get("rank"), "tables": tables, "places": places}
    names = sorted(per)
    base = {"event": os.path.basename(ev_dir), "total": total, "done": done, "cutoff": cutoff,
            "absent": [t for t in teams if t not in per], "rows": []}
    if not names:
        return base
    w = np.array([sum(k * r["mean"] for k, r in per[t].items()) for t in names])
    sd = np.array([math.sqrt(sum((k * r["se"]) ** 2 for k, r in per[t].items())) for t in names])
    draws = np.random.default_rng(0).normal(w, sd, size=(DRAWS, len(names)))
    pos = (-draws).argsort(1).argsort(1)  # 0 = first place in that draw
    p_top, p_first = (pos < cutoff).mean(0), (pos == 0).mean(0)
    history = {t: [] for t in names}  # rank after each finished tournament, by the weighted score so far
    for k in done:
        so_far = {t: sum(j * r["mean"] for j, r in per[t].items() if j <= k) for t in names if min(per[t]) <= k}
        ranked = sorted(so_far, key=lambda t: -so_far[t])
        for t in names:
            history[t].append(ranked.index(t) + 1 if t in so_far else None)
    for rank, i in enumerate(np.argsort(-w, kind="stable"), 1):
        t = names[i]
        width = max(len(r["places"]) for r in per[t].values())
        places = [sum(r["places"][j] for r in per[t].values() if j < len(r["places"])) for j in range(width)]
        tables = sum(r["tables"] for r in per[t].values())
        info = teams.get(t, {})
        base["rows"].append({
            "rank": rank, "team": t, "model": info.get("model"), "archetype": info.get("archetype"),
            "weighted": round(float(w[i]), 2), "ci": round(1.96 * float(sd[i]), 2),
            "p_top": round(float(p_top[i]), 3), "p_first": round(float(p_first[i]), 3),
            "won": round(places[0] / tables, 3) if places else None,
            "avg_place": round(sum((j + 1) * p for j, p in enumerate(places)) / sum(places), 2) if sum(places) else None,
            "history": history[t],
            "per": {str(k): {"mean": round(r["mean"], 2), "lo": round(r["lo"], 2), "hi": round(r["hi"], 2),
                             "rank": r["rank"], "tables": r["tables"], "places": [round(p, 1) for p in r["places"]]}
                    for k, r in sorted(per[t].items())}})
    return base
