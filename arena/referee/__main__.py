"""Event lifecycle CLI.

    python -m arena.referee new configs/event.yaml [--card-from <event>] [--name <id>]
    python -m arena.referee run <event> [--mock] [--time-scale 0.05]
    python -m arena.referee status <event>
    python -m arena.referee enter <event> <bot_dir> --team <name>
    python -m arena.referee report <event>
    python -m arena.referee debrief <event>
    python -m arena.referee cleanup <event>
    python -m arena.referee gauntlet <bot_dir> [--field latest|all|event:<id>] [--card-from <event>] [--iterations 200]

Run the referee from your own terminal (tmux or screen), not inside a Claude
Code session: it starts and stops many Claude Code processes.
"""

from __future__ import annotations

import argparse
import sys

from .commands import cleanup, enter, gauntlet, status
from .event import Event, Paused


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m arena.referee", description="No Limit arena referee")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("config")
    p.add_argument("--card-from")
    p.add_argument("--name")
    p = sub.add_parser("run")
    p.add_argument("event")
    p.add_argument("--mock", action="store_true", help="scripted builders instead of Claude (free)")
    p.add_argument("--time-scale", type=float, default=1.0)
    for name in ("status", "report", "debrief", "cleanup"):
        sub.add_parser(name).add_argument("event")
    p = sub.add_parser("enter")
    p.add_argument("event")
    p.add_argument("bot_dir")
    p.add_argument("--team", required=True)
    p = sub.add_parser("isolation", help="scripted claude -p run proving builder isolation (costs a little usage)")
    p.add_argument("event")
    p.add_argument("--team", default="b01")
    p.add_argument("--model", default="haiku")
    p = sub.add_parser("gauntlet")
    p.add_argument("bot_dir")
    p.add_argument("--field", default="latest")
    p.add_argument("--card-from")
    p.add_argument("--iterations", type=int, default=200)
    p.add_argument("--workers", type=int, default=0)
    a = ap.parse_args(argv)

    if a.cmd == "new":
        ev = Event.new(a.config, a.card_from, event_name=a.name)
        print(f"created {ev.id}: {len(ev.teams)} workspaces under {ev.teams[0].workspace.rsplit('/', 1)[0]}; "
              f"nothing is revealed until `run`")
        return 0
    if a.cmd == "gauntlet":
        print(gauntlet(a.bot_dir, a.field, a.card_from, a.iterations, workers=a.workers))
        return 0
    ev = Event(a.event)
    if a.cmd == "run":
        if ev.state.get("paused"):
            print(f"resuming a paused event ({ev.state['paused']}); the current window restarts")
            ev.resume_paused()
        try:
            ev.run(mock=a.mock, time_scale=a.time_scale)
        except Paused as e:
            print(f"PAUSED: {e}. Fix the cause (auth, usage limits), then run again.")
            return 2
        print(f"{ev.id} done: report at {ev.p('report', 'REPORT.md')}")
    elif a.cmd == "status":
        print(status(ev))
    elif a.cmd == "report":
        from .report import write_report
        write_report(ev)
        print(ev.p("report", "REPORT.md"))
    elif a.cmd == "enter":
        print(enter(ev, a.bot_dir, a.team))
    elif a.cmd == "cleanup":
        print(cleanup(ev))
    elif a.cmd == "isolation":
        from .isolation import run_isolation_proof
        r = run_isolation_proof(ev, a.team, a.model)
        for c in r["checks"]:
            print(f"  {'pass' if c['ok'] else 'FAIL'}  {c['check']}")
        print(("PASSED" if r["passed"] else "FAILED") + f": see {ev.p('report', 'ISOLATION.md')}")
        return 0 if r["passed"] else 1
    elif a.cmd == "debrief":
        print("debrief arrives with milestone 7 (it makes one paid claude -p call, only when you ask)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
