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

`run` also serves the live viewer (builders, then tables) on 127.0.0.1:8766
unless --no-viz. When the plan's five-hour usage limit stops the builders, it
waits for the reset and carries on with the time the window had left
(schedule.on_usage_limit: wait | stop), so an event can span several windows.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser

from ..tournament.wsstate import fmt_clock
from .commands import cleanup, enter, gauntlet, status
from .event import Event, Paused


def start_viewer(ev: Event) -> None:
    from ..viz.server import Source, serve
    try:
        server, url = serve(Source(event_dir=ev.dir), port=8766)
    except OSError:
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Live viewer: {url}", flush=True)
    if sys.stdout.isatty():
        webbrowser.open(url)


def run(ev: Event, mock: bool, time_scale: float) -> int:
    while True:
        if ev.state.get("paused"):
            print(f"resuming a paused event ({ev.state['paused']}); the window continues with the time it had left",
                  flush=True)
            ev.resume_paused()
        try:
            ev.run(mock=mock, time_scale=time_scale)
            return 0
        except Paused as e:
            if ev.state.get("pause_kind") != "usage_limit" or ev.cfg["schedule"].get("on_usage_limit") == "stop":
                print(f"PAUSED: {e}. Fix the cause (auth, usage limits), then run again.")
                return 2
            now = time.time()
            resume_at = max(now + 300, (ev.state.get("resets_at") or now + 1800) + 120)
            ev.state["resume_at"] = resume_at
            ev.save()
            print(f"PAUSED: {e}. Waiting for the plan's usage window to reset; resuming at {fmt_clock(resume_at)}. "
                  "Ctrl-C stops waiting; `run` again resumes.", flush=True)
            while time.time() < resume_at:
                time.sleep(min(30.0, max(0.0, resume_at - time.time())))


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
    p.add_argument("--no-viz", action="store_true", help="don't serve the live viewer")
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
        if not a.no_viz:
            start_viewer(ev)
        code = run(ev, a.mock, a.time_scale)
        if code:
            return code
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
