"""Live table viewer: replays tournament tables in a browser as they finish.

    python -m arena.viz --demo                  # run a house-bot tournament and watch it
    python -m arena.viz --dir path/to/logs      # a tournament's hand-log directory
    python -m arena.viz --event mini-001        # follows the event's latest tournament

Serves table.html and a small JSON API over the hand logs written live by
arena/tournament/handlog.py:
    /api/state                 meta, tables and hands so far, finished or live
    /api/tables?since=N        index entries after the first N (in finishing order)
    /api/table?task=T          one table's hands, with names per seat
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


class Source:
    """Where the logs are; in event mode, the latest tournament that has started."""

    def __init__(self, directory: str | None = None, event_dir: str | None = None):
        self.directory, self.event_dir = directory, event_dir

    def current(self) -> tuple[str | None, str]:
        if self.directory:
            return self.directory, os.path.basename(os.path.normpath(self.directory))
        results = os.path.join(self.event_dir, "results")
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
        d, label = self.source.current()
        if url.path == "/api/state":
            if d is None:
                return self._json({"label": label, "meta": None, "tables_done": 0, "hands_done": 0})
            try:
                meta = read_meta(d)
            except (OSError, ValueError):
                return self._json({"label": label, "meta": None, "tables_done": 0, "hands_done": 0})
            lines = self.source.index_lines(d)
            end = meta.get("finished_at") or time.time()
            return self._json({"label": label, "meta": meta, "tables_done": len(lines),
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live table viewer for arena tournaments")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="run a house-bot tournament in the background and watch it")
    src.add_argument("--dir", help="a tournament hand-log directory")
    src.add_argument("--event", help="an event id under events/; follows its latest tournament")
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
    else:
        source = Source(event_dir=os.path.join(REPO, "events", a.event))
    Handler.source = source
    server = None
    for port in range(a.port, a.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(f"no free port from {a.port}")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Table viewer at {url}  (Ctrl-C to stop)", flush=True)
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
