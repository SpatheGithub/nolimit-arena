"""The live table viewer's API over a real tournament's hand logs."""

import json
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from arena.engine.spec import NLHE
from arena.tournament.play import Settings
from arena.tournament.pool import Entry
from arena.tournament.tournament import run_tournament
from arena.viz.server import Handler, Source

BOTS = os.path.join(os.path.dirname(__file__), "bots")


def test_viewer_api_serves_live_logs(tmp_path):
    log_dir = str(tmp_path / "T1")
    entries = [Entry(f"{n}_{i}", os.path.join(BOTS, n)) for i, n in enumerate(["caller", "raiser", "seeded"] * 3)]
    run_tournament(entries, Settings(spec=NLHE, hand_cap=40), iterations=3, seed=1, workers=2, log_dir=log_dir)
    Handler.source = Source(directory=log_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    get = lambda path: json.loads(urllib.request.urlopen(base + path).read())
    try:
        state = get("/api/state")
        assert state["meta"]["finished"] and state["tables_done"] == 6 and state["hands_done"] > 0
        assert state["meta"]["entries"][0] == "caller_0" and state["meta"]["variant"]["name"] == "nlhe"
        tables = get("/api/tables?since=4")
        assert tables["total"] == 6 and len(tables["tables"]) == 2
        task = tables["tables"][0]["task"]
        table = get(f"/api/table?task={task}")
        assert len(table["names"]) == 8 and len(table["hands"]) == table["table"]["hands"]
        assert b"Live Tables" in urllib.request.urlopen(base + "/").read()
    finally:
        server.shutdown()


def test_event_mode_follows_the_latest_tournament(tmp_path):
    ev = tmp_path / "event"
    for k in (1, 2):
        d = ev / "results" / f"T{k}"
        d.mkdir(parents=True)
        (d / "hands.meta.json").write_text("{}")
    assert Source(event_dir=str(ev)).current()[1] == "T2"
    assert Source(event_dir=str(tmp_path / "none")).current()[0] is None
