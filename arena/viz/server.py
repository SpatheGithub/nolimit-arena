"""Live viewer: an event's builders while they work, and tournament tables
replayed in a browser as they finish.

    python -m arena.viz --demo                  # run a house-bot tournament and watch it
    python -m arena.viz --dir path/to/logs      # a tournament's hand-log directory
    python -m arena.viz --event mini-001        # one event: its builders, then its latest tournament
    python -m arena.viz --event latest          # whichever event a referee touched last

`python -m arena.referee run` starts one of these itself (port 8766).

Serves table.html and a small JSON API over the hand logs written live by
arena/tournament/handlog.py:
    /api/state                 meta, tables and hands so far, finished or live
    /api/tables?since=N        index entries after the first N (in finishing order)
    /api/table?task=T          one table's hands, with names per seat
    /api/event                 event mode: phase, clock, builders, leaderboard (arena/viz/status.py)
Standard library only; binds to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..tournament.handlog import read_meta, read_table
from .status import event_status

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EVENTS = os.environ.get("ARENA_EVENTS_ROOT") or os.path.join(REPO, "events")


def latest_event(root: str = EVENTS) -> str | None:
    """The event whose state.json a referee wrote last."""
    best, newest = None, -1.0
    try:
        names = os.listdir(root)
    except OSError:
        return None
    for name in names:
        try:
            mtime = os.stat(os.path.join(root, name, "state.json")).st_mtime
        except OSError:
            continue
        if mtime > newest:
            best, newest = os.path.join(root, name), mtime
    return best


class Source:
    """Where the logs are; in event mode, the latest tournament that has started.
    With ``events_root`` it follows whichever event is newest there."""

    def __init__(self, directory: str | None = None, event_dir: str | None = None, events_root: str | None = None):
        self.directory, self.event_dir, self.events_root = directory, event_dir, events_root

    def event(self) -> str | None:
        return latest_event(self.events_root) if self.events_root else self.event_dir

    def current(self) -> tuple[str | None, str]:
        if self.directory:
            return self.directory, os.path.basename(os.path.normpath(self.directory))
        ev = self.event()
        if ev is None:
            return None, "waiting for an event"
        results = os.path.join(ev, "results")
        best = None
        if os.path.isdir(results):
            for name in os.listdir(results):
                d = os.path.join(results, name)
                if name.startswith("T") and name[1:].isdigit() and os.path.isfile(os.path.join(d, "hands.meta.json")):
                    if best is None or int(name[1:]) > int(os.path.basename(best)[1:]):
                        best = d
        return best, (os.path.basename(best) if best else "waiting for the first tournament")

    @staticmethod
    def index_lines(d: str) -> list[dict]:
        out = []
        try:
            with open(os.path.join(d, "hands.index.jsonl")) as f:
                for line in f:
                    if line.endswith("\n"):
                        out.append(json.loads(line))
        except OSError:
            pass
        return out


class Handler(BaseHTTPRequestHandler):
    source: Source

    def log_message(self, *args) -> None:
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(json.dumps(obj, separators=(",", ":")).encode(), "application/json", code)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "table.html"), "rb") as f:
                return self._send(f.read(), "text/html; charset=utf-8")
        ev = None if self.source.directory else self.source.event()
        if url.path == "/api/event":
            if ev is None:
                return self._json({"error": "no event"}, 404)
            return self._json(event_status(ev))
        d, label = self.source.current()
        if url.path == "/api/state":
            # "source" changes when a new tournament or event starts, so the page can start over.
            base = {"label": label, "event": os.path.basename(ev) if ev else None, "source": d}
            if d is None:
                return self._json({**base, "meta": None, "tables_done": 0, "hands_done": 0})
            try:
                meta = read_meta(d)
            except (OSError, ValueError):
                return self._json({**base, "meta": None, "tables_done": 0, "hands_done": 0})
            lines = self.source.index_lines(d)
            end = meta.get("finished_at") or time.time()
            return self._json({**base, "meta": meta, "tables_done": len(lines),
                               "hands_done": sum(m.get("hands", 0) for m in lines),
                               "elapsed": max(end - meta["started"], 1e-6)})
        if url.path == "/api/tables":
            lines = self.source.index_lines(d) if d else []
            since = int(q.get("since", ["0"])[0])
            return self._json({"label": label, "total": len(lines),
                               "tables": [{k: m[k] for k in ("task", "iteration", "index", "entries", "fillers", "hands")}
                                          for m in lines[since:]]})
        if url.path == "/api/table":
            if d is None:
                return self._json({"error": "no tournament yet"}, 404)
            task = int(q.get("task", ["-1"])[0])
            line = next((m for m in self.source.index_lines(d) if m["task"] == task), None)
            if line is None:
                return self._json({"error": f"no table {task}"}, 404)
            meta = read_meta(d)
            names = [meta["entries"][e] for e in line["entries"]]
            return self._json({"table": line, "names": names, "hands": read_table(d, line)})
        self._json({"error": "not found"}, 404)


def demo_entries() -> list[str]:
    """--bot arguments for a demo tournament: the house bots, or the test bots."""
    for root in (os.path.join(REPO, "arena", "house_bots"), os.path.join(REPO, "tests", "bots")):
        if not os.path.isdir(root):
            continue
        bots = [d for d in sorted(os.listdir(root))
                if os.path.isfile(os.path.join(root, d, "agent.py")) and d not in
                {"crasher", "illegal", "slow", "hanger", "swallower", "native", "networker", "badinit",
                 "slowinit", "importerr", "printer"}]
        if bots:
            return [f"{bots[i % len(bots)]}_{i // len(bots) + 1}={os.path.join(root, bots[i % len(bots)])}"
                    for i in range(16)]
    raise SystemExit("no bots found for the demo")


def serve(source: Source, port: int = 8765) -> tuple[ThreadingHTTPServer, str]:
    """A server for ``source`` on the first free port from ``port``, bound to 127.0.0.1."""
    handler = type("SourceHandler", (Handler,), {"source": source})
    for p in range(port, port + 20):
        try:
            return ThreadingHTTPServer(("127.0.0.1", p), handler), f"http://127.0.0.1:{p}/"
        except OSError:
            continue
    raise OSError(f"no free port from {port}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live viewer for arena events and tournaments")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="run a house-bot tournament in the background and watch it")
    src.add_argument("--dir", help="a tournament hand-log directory")
    src.add_argument("--event", help="an event id under events/, or 'latest' to follow whichever event runs")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    proc = None
    if a.demo:
        log_dir = tempfile.mkdtemp(prefix="arena-viz-")
        cmd = [sys.executable, "-m", "arena.tournament", "--iterations", "3000", "--workers", "2",
               "--seed", str(int(time.time()) % 10_000), "--log", log_dir]
        for spec in demo_entries():
            cmd += ["--bot", spec]
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        source = Source(directory=log_dir)
    elif a.dir:
        source = Source(directory=os.path.abspath(a.dir))
    elif a.event == "latest":
        source = Source(events_root=EVENTS)
    else:
        source = Source(event_dir=os.path.join(EVENTS, a.event))
    try:
        server, url = serve(source, a.port)
    except OSError as e:
        raise SystemExit(str(e))
    print(f"Live viewer at {url}  (Ctrl-C to stop)", flush=True)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if proc and proc.poll() is None:
            proc.terminate()
    return 0
