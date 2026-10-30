"""Who is winning an event: the data behind the live viewer's Results view.

Per finished tournament: each team's points per table (mean, 95% interval,
rank), its finishing places and the share of tables it won. Over the event so
far: the weighted score (1·T1 + 2·T2 + ...), its 95% interval, the rank after
each tournament, and each team's chance of every final rank, of finishing
first and of making the regional cut (top 5 advance). Those chances come from
a bootstrap over whole tables (results/T<k>/tables.json, rebuilt from the hand
log for tournaments played before it existed): each resample redraws every
finished tournament's tables with replacement, so one team's points stay
another's loss. Without the tables or a hand log to rebuild them from, they
fall back to normal draws around each team's weighted score, using each
tournament's standard error. Draws are seeded, so they don't flicker between
refreshes.

How each team played, pooled over its tournaments: how often it finished 1st,
2nd, in the top 3 and in the last two places, the share of its heads-up
finishes it won, VPIP and PFR weighted by hands, and postflop aggression (bets
and raises per call). A written analysis in report/strategies.json (a summary,
and per team its strategy, outcome and lesson) rides along when it exists.

It reads the referee's files only, and redoes the work only when a summary,
the tables or the analysis changes, so polling it costs the tournaments'
workers nothing.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from ..tournament.tables import FILE as TABLES, load as load_tables

CUTOFF = 5  # top 5 per regional advance (docs/OFFICIAL_FORMAT.md)
DRAWS = 20_000  # normal draws, when there are no tables to resample
BOOT = 2_000    # bootstrap resamples of the tables
ANALYSIS = os.path.join("report", "strategies.json")
STYLE = ("hands", "vpip", "pfr", "post_aggr", "post_calls")
_cache: dict[str, tuple[tuple, dict]] = {}


def _load(path: str):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _mtime(path: str) -> float:
    return os.path.getmtime(path) if os.path.exists(path) else 0.0


def _share(places: list[float], tables: float) -> float | None:
    return round(sum(places) / tables, 3) if places else None


def _style(rows: list[dict]) -> dict:
    """VPIP and PFR weighted by hands, and postflop aggression: bets and raises per call."""
    out = {}
    for f in ("vpip", "pfr"):
        got = [(r[f], r.get("hands") or 1) for r in rows if r.get(f) is not None]
        out[f] = round(sum(v * n for v, n in got) / sum(n for _, n in got), 3) if got else None
    calls = sum(r.get("post_calls") or 0 for r in rows)
    out["af"] = round(sum(r.get("post_aggr") or 0 for r in rows) / calls, 3) if calls else None  # shown to 1 place
    return out


def event_results(ev_dir: str, cutoff: int = CUTOFF) -> dict:
    card = _load(os.path.join(ev_dir, "card.json")) or {}
    total = int(card.get("tournaments") or 0)
    paths = [os.path.join(ev_dir, "results", f"T{k}", "summary.json") for k in range(1, total + 1)]
    analysis = os.path.join(ev_dir, ANALYSIS)
    tabs = [os.path.join(os.path.dirname(p), TABLES) for p in paths]
    key = (cutoff, *map(_mtime, paths), *map(_mtime, tabs), _mtime(analysis))
    hit = _cache.get(ev_dir)
    if hit is None or hit[0] != key:
        hit = (key, _standings(ev_dir, total, paths, cutoff, _load(analysis) or {}))
        _cache[ev_dir] = hit
    phase = (_load(os.path.join(ev_dir, "state.json")) or {}).get("phase", "")
    kind, _, k = phase.partition(":")
    playing = int(k) if kind in ("freeze", "tournament") and k.isdigit() else None
    return {**hit[1], "key": "-".join(f"{x:.0f}" for x in key[1:]), "phase": phase, "playing": playing}


def _draws(ev_dir: str, names: list[str], done: list[int], w: np.ndarray, sd: np.ndarray) -> tuple[np.ndarray, str]:
    """Weighted-score draws, one row per draw and one column per team: a bootstrap over
    whole tables when every finished tournament has them, else normal draws around ``w``."""
    col = {t: j for j, t in enumerate(names)}
    rng = np.random.default_rng(0)
    total = np.zeros((BOOT, len(names)))
    for k in done:
        got = load_tables(os.path.join(ev_dir, "results", f"T{k}"))
        if not got or not got["tables"]:
            return np.random.default_rng(0).normal(w, sd, size=(DRAWS, len(names))), "normal"
        cols = [col.get(name) for name in got["entries"]]
        pts = np.zeros((len(got["tables"]), len(names)))
        seated = np.zeros_like(pts)
        for r, (_, entries, fillers, points) in enumerate(got["tables"]):
            for e, filler, p in zip(entries, fillers, points):
                if not filler and cols[e] is not None:
                    pts[r, cols[e]] += p
                    seated[r, cols[e]] += 1
        n, played = len(pts), seated.sum(0)
        weights = rng.multinomial(n, np.full(n, 1 / n), size=BOOT)
        sums, counts = weights @ pts, weights @ seated
        observed = np.divide(pts.sum(0), played, out=np.zeros(len(names)), where=played > 0)
        total += k * np.where(counts > 0, sums / np.maximum(counts, 1), observed) * (played > 0)
    return total, "bootstrap"


def _standings(ev_dir: str, total: int, paths: list[str], cutoff: int, analysis: dict) -> dict:
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
                "rank": e.get("rank"), "tables": tables, "places": places, "style": {f: e.get(f) for f in STYLE}}
    names = sorted(per)
    notes = analysis.get("teams") or {}
    base = {"event": os.path.basename(ev_dir), "total": total, "done": done, "cutoff": cutoff,
            "absent": [t for t in teams if t not in per], "rows": [],
            "analysis": {k: v for k, v in analysis.items() if k != "teams"} or None}
    if not names:
        return base
    w = np.array([sum(k * r["mean"] for k, r in per[t].items()) for t in names])
    sd = np.array([math.sqrt(sum((k * r["se"]) ** 2 for k, r in per[t].items())) for t in names])
    draws, base["rank_method"] = _draws(ev_dir, names, done, w, sd)
    pos = (-draws).argsort(1).argsort(1)  # 0 = first place in that draw
    p_top, p_first = (pos < cutoff).mean(0), (pos == 0).mean(0)
    spread = draws.std(0) if base["rank_method"] == "bootstrap" else sd
    rank_pct = np.percentile(pos + 1, [5, 50, 95], axis=0, method="nearest")
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
            "weighted": round(float(w[i]), 2), "ci": round(1.96 * float(spread[i]), 2),
            "p_top": round(float(p_top[i]), 3), "p_first": round(float(p_first[i]), 3),
            "ranks": [round(float((pos[:, i] == r).mean()), 3) for r in range(len(names))],
            "rank_range": [int(rank_pct[0, i]), int(rank_pct[2, i])], "rank_median": int(rank_pct[1, i]),
            "won": _share(places[:1], tables), "second": _share(places[1:2], tables),
            "top3": _share(places[:3], tables), "bottom2": _share(places[-2:], tables) if width > 3 else None,
            "hu": round(places[0] / (places[0] + places[1]), 3) if width > 1 and places[0] + places[1] else None,
            "avg_place": round(sum((j + 1) * p for j, p in enumerate(places)) / sum(places), 2) if sum(places) else None,
            **_style([r["style"] for r in per[t].values()]), "notes": notes.get(t),
            "history": history[t],
            "per": {str(k): {"mean": round(r["mean"], 2), "lo": round(r["lo"], 2), "hi": round(r["hi"], 2),
                             "rank": r["rank"], "tables": r["tables"], "places": [round(p, 1) for p in r["places"]]}
                    for k, r in sorted(per[t].items())}})
    return base
