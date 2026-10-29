"""status, enter, cleanup and gauntlet."""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import time

from ..tournament.card import load_card, settings_from_card
from ..tournament.pool import Entry
from ..tournament.tournament import format_leaderboard, run_tournament
from ..tournament.validate import validate
from ..tournament.wsstate import fmt_clock
from .builders import read_stream
from .event import EVENTS_ROOT, HOUSE, Event


def status(ev: Event) -> str:
    st = ev.state
    lines = [f"{ev.id}: phase {st['phase']}" + (f" (PAUSED: {st['paused']})" if st.get("paused") else "")
             + ("; mock builders" if ev.mock else "") + f"; time scale {ev.scale:g}"]
    if st["windows"]:
        w = st["windows"][-1]
        left = w["end"] - time.time()
        lines.append(f"current window: {w['kind']} {w['k'] or ''} ends {fmt_clock(w['end'])}"
                     + (f" ({left:.0f}s left)" if left > 0 else " (closed)"))
    lines.append(f"{'team':<6} {'model':<8} {'state':<10} {'last accepted':<22} {'subs':>4} {'errors':<16} {'cost':>7}")
    total = 0.0
    for t in ev.teams:
        b = st["builders"].get(t.team, {})
        s = read_stream(ev.p("logs", f"{t.team}.jsonl"))
        subs = ev.submissions(t.team)
        last = f"{subs[-1]['sid']} {fmt_clock(subs[-1]['observed'])}" if subs else "none"
        state = "running" if ev._alive(t.team) else (f"exit {b.get('exit')}" if b else "not started")
        total += s["cost_usd"]
        lines.append(f"{t.team:<6} {t.model:<8} {state:<10} {last:<22} {len(subs):>4} "
                     f"{(','.join(s['errors']) or '-')[:16]:<16} ${s['cost_usd']:>6.2f}")
    lines.append(f"total cost so far ${total:.2f}")
    return "\n".join(lines)


def enter(ev: Event, bot_dir: str, name: str) -> str:
    """Validate an external bot (e.g. one your team built by hand) and add it
    to every tournament of this event that hasn't started yet."""
    v = validate(bot_dir, settings_from_card(ev.card), HOUSE, tables=2)
    if not v["ok"]:
        raise ValueError("bot rejected: " + "; ".join(v["reasons"]))
    dst = ev.p("entered", name)
    if os.path.exists(dst) or name in {t.team for t in ev.teams}:
        raise FileExistsError(f"an entry named {name!r} already exists")
    shutil.copytree(bot_dir, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    ev.note("entered", name=name, hash=v["hash"])
    return f"entered {name} ({v['hash'][:12]}); it plays from the next tournament"


def cleanup(ev: Event) -> str:
    out = ev.p("workspaces.tar.gz")
    with tarfile.open(out, "w:gz") as tar:
        for t in ev.teams:
            if os.path.isdir(t.workspace):
                tar.add(t.workspace, arcname=t.team,
                        filter=lambda ti: None if "/kit/arena" in ti.name or "__pycache__" in ti.name else ti)
    for t in ev.teams:
        shutil.rmtree(t.workspace, ignore_errors=True)
    parent = os.path.dirname(ev.teams[0].workspace) if ev.teams else None
    if parent and os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
    ev.note("cleanup", archive=out)
    return f"archived workspaces to {out} and removed them"


def archived_bots(selector: str = "latest", root: str = EVENTS_ROOT) -> list[Entry]:
    """Frozen bots from past events. ``latest``: each team's last frozen bot;
    ``all``: every frozen bot; ``event:<id>``: that event's latest per team."""
    out = []
    events = sorted(os.listdir(root)) if os.path.isdir(root) else []
    if selector.startswith("event:"):
        events = [selector.split(":", 1)[1]]
    for e in events:
        bots = os.path.join(root, e, "bots")
        if not os.path.isdir(bots):
            continue
        for team in sorted(os.listdir(bots)):
            ts = sorted((d for d in os.listdir(os.path.join(bots, team)) if d.startswith("T") and d[1:].isdigit()),
                        key=lambda d: int(d[1:]))
            if not ts:
                continue
            chosen = ts if selector == "all" else ts[-1:]
            out += [Entry(f"{e}/{team}/{d}", os.path.join(bots, team, d)) for d in chosen]
    return out


def gauntlet(bot_dir: str, selector: str = "latest", card_from: str | None = None, iterations: int = 200,
             max_field: int = 39, seed: int = 0, workers: int = 0) -> str:
    """Score a candidate bot against archived builder bots, for free."""
    field = archived_bots(selector)
    if not field:
        from ..tournament.tournament import zoo_entries
        field = zoo_entries(max_field)
        note = "no archived bots yet: the field is the house-bot zoo"
    else:
        note = f"{len(field)} archived bots ({selector})"
    field = field[:max_field]
    if card_from:
        card = load_card(os.path.join(EVENTS_ROOT, card_from, "card.json"))
    else:
        from ..engine.spec import NLHE
        from ..tournament.card import make_card
        from ..variants.library import BLINDS, POINTS
        card = make_card(event="gauntlet", spec=NLHE, points=POINTS["standard"], blinds=BLINDS["doubling"])
    entries = [Entry("candidate", os.path.abspath(bot_dir))] + field
    res = run_tournament(entries, settings_from_card(card, hand_logs=False), iterations, seed, workers)
    me = next(r for r in res["entries"] if r["name"] == "candidate")
    head = (f"gauntlet: {note}; variant {card['variant']['name']}; candidate ranked {me['rank']} of "
            f"{len(entries)} with {me['mean']:.2f} ± {1.96 * me['se']:.2f} points/table")
    return head + "\n" + format_leaderboard(res)


def summary_json(ev: Event) -> str:
    return json.dumps({"state": ev.state, "card": {k: v for k, v in ev.card.items() if k != "variant"}},
                      indent=1, default=str)
