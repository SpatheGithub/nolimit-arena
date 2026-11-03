"""The lab: paired A/B tests of our bot's switches against archived builder bots.

    python -m ourbot.lab run [--experiment switches|bases] [--fields nlhe,shortdeck,royal]
                             [--blocks 40] [--tables 50] [--workers 2]
    python -m ourbot.lab report

Experiments:
- switches: our bot's configs (below) on every field.
- bases: candidate starting points on the hold'em field without the two event
  winners. The candidates are our bot's base and best configs, the house tag,
  and each winner's final bot, so no candidate meets its own copy.

A field is one variant's archived builder bots, played on that variant's event
card. A block seats the candidate with 7 opponents drawn from the field and
plays ``--tables`` tables. Every config plays the same blocks with the same
seeds, so the comparison is paired: same cards, same opponents, and only our
decisions differ.

Configs (ourbot/lessons/agent.py's switches):
- base: every switch off, which is exactly the house icm_pushfold;
- all: every switch on;
- only_<switch> and no_<switch> for each switch.

It never plays while a live event's referee is freezing bots or running a
tournament, and it starts a block only with ``LIVE_MARGIN_S`` or more left in
the live window. That way the event's CPU-timed decisions aren't disturbed.
Per-table results are appended to ourbot/runs/results.jsonl. A rerun skips
blocks already recorded for the same bot code, so a stopped run resumes.
``report`` writes ourbot/LAB.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from arena.referee.__main__ import referee_alive  # noqa: E402
from arena.referee.commands import archived_bots  # noqa: E402
from arena.referee.event import EVENTS_ROOT  # noqa: E402
from arena.tournament.card import load_card, settings_from_card  # noqa: E402
from arena.tournament.play import derive  # noqa: E402
from arena.tournament.tournament import Entry, run_tournament  # noqa: E402

BOT = os.path.join(HERE, "lessons")
RUNS = os.path.join(HERE, "runs")
RESULTS = os.path.join(RUNS, "results.jsonl")
LAB_MD = os.path.join(HERE, "LAB.md")
SWITCHES = ("resteal", "shove20", "noflat", "respect")
LIVE_MARGIN_S = 150
# field: (events whose latest bots make the field, event whose card is played, bots left out)
WINNERS = ("full-opus-001/b06/", "full-opus-002/b06/")
FIELDS = {
    "nlhe": (["full-opus-001", "full-opus-002"], "full-opus-002", ()),
    "nlhe-x": (["full-opus-001", "full-opus-002"], "full-opus-002", WINNERS),
    "shortdeck": (["shortdeck-001", "shortdeck-002"], "shortdeck-002", ()),
    "royal": (["royal-001"], "royal-001", ()),
}


def configs() -> dict[str, dict[str, bool]]:
    out = {"base": {k: False for k in SWITCHES}, "all": {k: True for k in SWITCHES}}
    for k in SWITCHES:
        out[f"only_{k}"] = {s: s == k for s in SWITCHES}
        out[f"no_{k}"] = {s: s != k for s in SWITCHES}
    return out


def candidates(experiment: str) -> tuple[dict[str, str], list[str]]:
    """({config: bot dir}, default fields) for an experiment."""
    if experiment == "switches":
        return prepare(configs()), ["nlhe", "shortdeck", "royal"]
    if experiment == "bases":
        ours = prepare({"base": {k: False for k in SWITCHES},
                        "best": {k: k != "shove20" for k in SWITCHES}})
        bots = os.path.join(EVENTS_ROOT, "{}", "bots", "b06", "T6")
        return {**ours, "house_tag": os.path.join(REPO, "arena", "house_bots", "tag"),
                "winner_e1": bots.format("full-opus-001"), "winner_e2": bots.format("full-opus-002")}, ["nlhe-x"]
    raise SystemExit(f"unknown experiment {experiment!r}")


def code_hash() -> str:
    h = hashlib.sha256()
    for name in sorted(os.listdir(BOT)):
        if name.endswith((".py", ".json")) and name != "switches.json":
            with open(os.path.join(BOT, name), "rb") as f:
                h.update(name.encode() + f.read())
    return h.hexdigest()[:12]


def prepare(cfgs: dict[str, dict[str, bool]]) -> dict[str, str]:
    """One copy of the bot per config, each with its own switches.json."""
    dirs = {}
    for name, sw in cfgs.items():
        d = os.path.join(RUNS, "bots", "-".join(f"{k}{int(v)}" for k, v in sorted(sw.items())))
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(BOT, d, ignore=shutil.ignore_patterns("__pycache__", "switches.json"))
        with open(os.path.join(d, "switches.json"), "w") as f:
            json.dump(sw, f)
        dirs[name] = d
    return dirs


def live_wait() -> str | None:
    """Why a live event makes this a bad moment to play, or None."""
    for ev in sorted(os.listdir(EVENTS_ROOT)):
        try:
            with open(os.path.join(EVENTS_ROOT, ev, "state.json")) as f:
                st = json.load(f)
        except (OSError, ValueError):
            continue
        if st.get("phase") == "done" or not referee_alive(st.get("referee_pid")):
            continue
        if st.get("paused"):
            continue  # waiting out a usage limit: nothing is timed
        phase = st["phase"]
        if phase.startswith(("build", "patch")) and st.get("windows"):
            left = st["windows"][-1]["end"] - time.time()
            if left < LIVE_MARGIN_S:
                return f"{ev} {phase} closes in {left:.0f}s"
            continue
        if phase != "created":
            return f"{ev} {phase}"
    return None


def done_keys() -> set[tuple]:
    keys = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            for line in f:
                r = json.loads(line)
                keys.add((r.get("experiment", "switches"), r["field"], r["config"], r["block"], r["tables_n"],
                          r["code"]))
    return keys


def run(experiment: str, fields: list[str] | None, blocks: int, n_tables: int, workers: int) -> None:
    dirs, default_fields = candidates(experiment)
    code = code_hash()
    names = list(dirs)
    seen = done_keys()
    os.makedirs(RUNS, exist_ok=True)
    for field in fields or default_fields:
        events, card_event, left_out = FIELDS[field]
        pool = [e for e in archived_bots("event:" + ",".join(events)) if not e.name.startswith(left_out)]
        card = load_card(os.path.join(EVENTS_ROOT, card_event, "card.json"))
        settings = settings_from_card(card, hand_logs=False)
        print(f"{field}: {len(pool)} archived bots from {', '.join(events)}; card {card_event}", flush=True)
        for b in range(blocks):
            opps = random.Random(derive(field, "opponents", b)).sample(pool, 7)
            seed = derive(field, "block", b)
            for name in names[b % len(names):] + names[:b % len(names)]:  # rotate the order across blocks
                if (experiment, field, name, b, n_tables, code) in seen:
                    continue
                while (why := live_wait()) is not None:
                    print(f"  waiting: {why}", flush=True)
                    time.sleep(20)
                t0 = time.time()
                res = run_tournament([Entry("candidate", dirs[name])] + opps, settings, n_tables, seed, workers)
                rows = []
                for tid, r in sorted(res["tables"].items()):
                    if "crash" in r:
                        continue
                    me = r["entries"].index(0)
                    pts = r["points"]
                    rows.append([tid, round(pts[me], 3), int(pts[me] >= max(pts) - 1e-9)])
                cand = next(e for e in res["entries"] if e["name"] == "candidate")
                rec = {"experiment": experiment, "field": field, "config": name, "block": b, "tables_n": n_tables,
                       "code": code,
                       "seed": seed, "opponents": [o.name for o in opps], "tables": rows,
                       "subs": {k: cand.get(k, 0) for k in ("timeouts", "errors", "illegal", "hangs")},
                       "secs": round(time.time() - t0, 1), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
                with open(RESULTS, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                mean = sum(x[1] for x in rows) / max(1, len(rows))
                print(f"  {field} block {b} {name}: {mean:.1f} pts/table over {len(rows)} ({rec['secs']}s)", flush=True)
        report()


def report() -> str:
    if not os.path.exists(RESULTS):
        return "no results yet"
    data: dict[tuple, dict[str, dict[tuple, tuple]]] = {}
    with open(RESULTS) as f:
        for line in f:
            r = json.loads(line)
            group = (r.get("experiment", "switches"), r["field"], r["code"])
            cell = data.setdefault(group, {}).setdefault(r["config"], {})
            for tid, pts, won in r["tables"]:
                cell[(r["block"], r["tables_n"], tid)] = (pts, won)
    lines = ["# Lab results", "",
             f"Written by `python -m ourbot.lab report` at {time.strftime('%Y-%m-%d %H:%M')}; "
             f"our bot's code is now {code_hash()}.",
             "Δ is the paired difference from `base` (our bot with every switch off, which is the house "
             "icm_pushfold) over the same tables, with a 95% interval. Points are per table, under each field's "
             "points table; a win is 1st at the table.", ""]
    for (experiment, field, code), by_cfg in data.items():
        base = by_cfg.get("base", {})
        lines += [f"## {experiment}: {field} (bot code {code})", "",
                  "| Config | Tables | Points | Δ vs base | Win % | Δ win % |", "| :- | -: | -: | -: | -: | -: |"]
        rows = []
        for name, cell in by_cfg.items():
            n = len(cell)
            mean = sum(p for p, _ in cell.values()) / n
            win = 100 * sum(w for _, w in cell.values()) / n
            common = [k for k in cell if k in base]
            if name != "base" and len(common) > 1:
                d = [cell[k][0] - base[k][0] for k in common]
                dw = [100 * (cell[k][1] - base[k][1]) for k in common]
                md = sum(d) / len(d)
                sd = math.sqrt(sum((x - md) ** 2 for x in d) / (len(d) - 1))
                mdw = sum(dw) / len(dw)
                delta = f"{md:+.2f} ± {1.96 * sd / math.sqrt(len(d)):.2f}"
                dwin = f"{mdw:+.1f}"
            else:
                md, delta, dwin = 0.0, "·", "·"
            rows.append((md, f"| {name} | {n} | {mean:.2f} | {delta} | {win:.1f} | {dwin} |"))
        lines += [r for _, r in sorted(rows, key=lambda x: -x[0])] + [""]
    text = "\n".join(lines)
    with open(LAB_MD, "w") as f:
        f.write(text + "\n")
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ourbot.lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--experiment", default="switches", choices=("switches", "bases"))
    p.add_argument("--fields", help="comma-separated; default: the experiment's own")
    p.add_argument("--blocks", type=int, default=40)
    p.add_argument("--tables", type=int, default=50)
    p.add_argument("--workers", type=int, default=2)
    sub.add_parser("report")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.experiment, a.fields.split(",") if a.fields else None, a.blocks, a.tables, a.workers)
    else:
        print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
