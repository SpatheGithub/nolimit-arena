"""Event lifecycle CLI.

    python -m arena.referee new configs/event.yaml [--card-from <event>] [--name <id>]
    python -m arena.referee run <event> [--mock] [--time-scale 0.05]
    python -m arena.referee chain <config> [<config> ...] [--after <event>] [--mock] [--time-scale 0.05]
    python -m arena.referee status <event>
    python -m arena.referee enter <event> <bot_dir> --team <name>
    python -m arena.referee report <event>
    python -m arena.referee debrief <event> [--mock] [--model opus] [--effort max] [--budget-usd 15]
    python -m arena.referee cleanup <event>
    python -m arena.referee gauntlet <bot_dir> [--field latest|all|event:<id>[,<id>...]]
                                     [--card-from <event>] [--iterations 200]

Run the referee from your own terminal (tmux or screen), not inside a Claude
Code session: it starts and stops many Claude Code processes.

`run` also serves the live viewer (builders, then tables) on 127.0.0.1:8766
unless --no-viz. When the plan's five-hour usage limit stops the builders, it
waits for the reset and carries on with the time the window had left
(schedule.on_usage_limit: wait | stop), so an event can span several windows.

`chain` runs events back to back: it waits for --after's referee to finish
(or resumes that event if its referee has died), then creates, isolation-proves
and runs each config's event in turn. Done events are skipped and unfinished
ones resumed, so the same command picks up where a stopped chain left off.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser

from ..tournament.wsstate import fmt_clock
from .commands import cleanup, enter, gauntlet, status
from .config import load_config
from .event import EVENTS_ROOT, Event, Paused


def start_viewer(event_dir: str | None = None, events_root: str | None = None) -> bool:
    """Serve the live viewer on 127.0.0.1:8766 for one event, or for the newest one under events_root."""
    from ..viz.server import Source, serve
    try:
        server, url = serve(Source(event_dir=event_dir, events_root=events_root), port=8766)
    except OSError:
        return False
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Live viewer: {url}", flush=True)
    if sys.stdout.isatty():
        webbrowser.open(url)
    return True


def run(ev: Event, mock: bool, time_scale: float) -> int:
    ev.state["referee_pid"] = os.getpid()  # the live viewer shows when the referee isn't running
    ev.save()
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


def referee_alive(pid) -> bool:
    """Whether ``pid`` is a running referee, not just any process that got the same pid later."""
    if not pid or pid == os.getpid():
        return False
    try:
        out = subprocess.run(["ps", "-p", str(int(pid)), "-o", "command="], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return "arena.referee" in out


def isolation_passed(ev: Event) -> bool:
    try:
        with open(ev.p("isolation.json")) as f:
            return bool(json.load(f).get("passed"))
    except (OSError, ValueError):
        return False


def finish(event_id: str, mock: bool, time_scale: float, poll_s: float) -> int:
    """Wait while another referee runs the event, or run it here if none does. 0 once it's done."""
    waiting = False
    while True:
        ev = Event(event_id)
        if ev.state["phase"] == "done":
            return 0
        if referee_alive(ev.state.get("referee_pid")):
            if not waiting:
                print(f"{event_id}: waiting for its referee (pid {ev.state['referee_pid']}) to finish", flush=True)
                waiting = True
            time.sleep(poll_s)
            continue
        print(f"{event_id}: running from phase {ev.state['phase']}", flush=True)
        return run(ev, mock, time_scale)


def chain(configs: list[str], after: str | None, mock: bool, time_scale: float, viz: bool) -> int:
    poll_s = min(60.0, max(0.5, 60.0 * time_scale))
    ids = [load_config(path)["event"]["name"] for path in configs]
    if len(set(ids)) != len(ids) or after in ids:
        print("chain: every event in a chain needs its own name: " + ", ".join(([after] if after else []) + ids))
        return 1
    if viz:  # follows the newest event; waits for the port while another referee still serves it
        def serve_when_free() -> None:
            while not start_viewer(events_root=EVENTS_ROOT):
                time.sleep(30)
        threading.Thread(target=serve_when_free, daemon=True).start()
    if after:
        code = finish(after, mock, time_scale, poll_s)
        if code:
            return code
    for path, event_id in zip(configs, ids):
        if not os.path.exists(os.path.join(EVENTS_ROOT, event_id)):
            ev = Event.new(path)
            print(f"{event_id}: created ({ev.card['variant']['name']}, {ev.card['points_name']} points)", flush=True)
        ev = Event(event_id)
        if ev.state["phase"] != "done" and not mock and not isolation_passed(ev):
            from .isolation import run_isolation_proof
            if not run_isolation_proof(ev, "b01", "haiku")["passed"]:
                print(f"{event_id}: the isolation proof FAILED, so the chain stops; see "
                      f"{ev.p('report', 'ISOLATION.md')}", flush=True)
                return 1
            print(f"{event_id}: isolation proof passed", flush=True)
        code = finish(event_id, mock, time_scale, poll_s)
        if code:
            print(f"{event_id}: stopped with exit {code}; the same chain command resumes it", flush=True)
            return code
        print(f"{event_id} done: report at {ev.p('report', 'REPORT.md')}", flush=True)
    print("chain done", flush=True)
    return 0


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
    p = sub.add_parser("chain", help="run events back to back, each from its config")
    p.add_argument("configs", nargs="+")
    p.add_argument("--after", metavar="EVENT", help="an existing event to finish first")
    p.add_argument("--mock", action="store_true", help="scripted builders instead of Claude (free)")
    p.add_argument("--time-scale", type=float, default=1.0)
    p.add_argument("--no-viz", action="store_true", help="don't serve the live viewer")
    for name in ("status", "report", "cleanup"):
        sub.add_parser(name).add_argument("event")
    p = sub.add_parser("debrief", help="one paid claude -p analyst run: report/DEBRIEF.md and LESSONS.md")
    p.add_argument("event")
    p.add_argument("--mock", action="store_true", help="a stub analyst instead of Claude (free, for tests)")
    p.add_argument("--model", default="opus")
    p.add_argument("--effort", default="max")
    p.add_argument("--budget-usd", type=float, default=15.0, help="cap on Claude Code's API-price estimate")
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
    if a.cmd == "chain":
        return chain(a.configs, a.after, a.mock, a.time_scale, not a.no_viz)
    ev = Event(a.event)
    if a.cmd == "run":
        if not a.no_viz:
            start_viewer(event_dir=ev.dir)
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
        from .debrief import run_debrief
        print(f"debrief of {ev.id}: {'mock analyst' if a.mock else f'{a.model} at {a.effort} effort'}; "
              f"stream in {ev.p('logs', 'debrief.jsonl')}", flush=True)
        r = run_debrief(ev, mock=a.mock, model=a.model, effort=a.effort, budget_usd=a.budget_usd)
        print(f"{r['result'] or 'no result'}: {r['debrief']} {'written' if r['wrote_debrief'] else 'NOT written'}, "
              f"{r['lessons_added']} lines added to {r['lessons']}, ${r['cost_usd']:.2f} (API-price estimate)")
        if r["errors"]:
            print("errors: " + ", ".join(r["errors"]))
        if not r["settings_loaded"]:
            print("warning: the debrief settings file didn't load, so its permission rules were not in force")
        return 0 if r["wrote_debrief"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
