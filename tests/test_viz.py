"""The live table viewer's API over a real tournament's hand logs."""

import json
import os
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from arena.engine.spec import NLHE
from arena.tournament.play import Settings
from arena.tournament.pool import Entry
from arena.tournament.tournament import run_tournament
from arena.viz.results import event_results
from arena.viz.server import Handler, Source, latest_event, serve
from arena.viz.status import event_status

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


def test_event_status_shows_builders_between_tournaments(tmp_path):
    ev = tmp_path / "events" / "ev1"
    (ev / "logs").mkdir(parents=True)
    (ev / "submissions" / "b01").mkdir(parents=True)
    now = time.time()
    (ev / "card.json").write_text(json.dumps({"tournaments": 2, "variant": {"name": "nlhe"}}))
    (ev / "teams.json").write_text(json.dumps([{"team": "b01", "model": "opus", "archetype": None},
                                               {"team": "b02", "model": "opus", "archetype": "survival"}]))
    (ev / "state.json").write_text(json.dumps({
        "phase": "build", "windows": [{"kind": "build", "k": 0, "start": now - 60, "end": now + 600}],
        "builders": {"b01": {"pid": os.getpid(), "launches": 2, "nudges": {"build:0": 1}},
                     "b02": {"pid": 0, "launches": 1}}}))
    (ev / "submissions" / "b01" / "index.jsonl").write_text('{"sid": "001-a"}\n{"sid": "002-b"}\n')
    call = {"type": "tool_use", "name": "Bash", "input": {"command": "python kit/localsim.py",
                                                           "description": "Play 200 tables against the zoo"}}
    meter = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "unifiedWindows": {
        "five_hour": {"utilization": 0.42, "resetsAt": now + 3600}}}}
    (ev / "logs" / "b01.jsonl").write_text("not json\n" + json.dumps(meter) + "\n" + json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Testing."}, call]}}) + "\n")
    st = event_status(str(ev))
    assert st["label"] == "Build window" and st["tournaments"] == {"done": 0, "total": 2}
    b1, b2 = st["builders"]
    assert b1["status"] == "working" and b1["subs"] == 2 and b1["checks"] == 1  # this test's pid is alive
    assert b1["last"] == "Bash: Play 200 tables against the zoo" and b2["status"] == "idle"
    assert st["meter"]["used"] == 0.42 and st["leaderboard"] is None
    (ev / "results" / "T1").mkdir(parents=True)
    (ev / "results" / "T1" / "summary.json").write_text(json.dumps({"meta": {}, "entries": [
        {"name": "b02", "mean": 30.0, "lo": 28.0, "hi": 32.0}, {"name": "b01", "mean": 35.0, "lo": 33.0, "hi": 37.0}]}))
    state = json.loads((ev / "state.json").read_text())
    (ev / "state.json").write_text(json.dumps({**state, "phase": "patch:1"}))
    st = event_status(str(ev))
    assert st["label"] == "Patch window before T2" and [r["team"] for r in st["leaderboard"]["rows"]] == ["b01", "b02"]
    (tmp_path / "events" / "older").mkdir()
    (tmp_path / "events" / "older" / "state.json").write_text("{}")
    os.utime(tmp_path / "events" / "older" / "state.json", (now - 999, now - 999))
    assert latest_event(str(tmp_path / "events")) == str(ev)
    server, url = serve(Source(events_root=str(tmp_path / "events")), port=18765)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        got = json.loads(urllib.request.urlopen(url + "api/event").read())
        assert got["id"] == "ev1" and got["builders"][0]["team"] == "b01"
        assert json.loads(urllib.request.urlopen(url + "api/state").read())["event"] == "ev1"
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


def test_results_rank_weighted_scores_and_top_five_chances(tmp_path):
    ev = tmp_path / "events" / "ev2"
    teams = [f"b0{i}" for i in range(1, 8)]
    (ev / "results").mkdir(parents=True)
    (ev / "card.json").write_text(json.dumps({"tournaments": 3}))
    (ev / "state.json").write_text(json.dumps({"phase": "tournament:3"}))
    (ev / "teams.json").write_text(json.dumps([{"team": t, "model": "opus", "archetype": None} for t in teams]))

    def write(k, means):  # b07 never has an accepted bot
        (ev / "results" / f"T{k}").mkdir()
        entries = [{"name": t, "mean": m, "se": 1.0, "lo": m - 2, "hi": m + 2, "rank": None, "tables": 100,
                    "places": [m / 2, 100 - m / 2, 0, 0, 0, 0, 0, 0]} for t, m in zip(teams, means)]
        (ev / "results" / f"T{k}" / "summary.json").write_text(json.dumps({"meta": {}, "entries": entries}))

    write(1, [50, 40, 35, 30, 25, 20])
    write(2, [30, 45, 35, 30, 25, 20])
    r = event_results(str(ev))
    rows = {x["team"]: x for x in r["rows"]}
    assert r["done"] == [1, 2] and r["playing"] == 3 and r["absent"] == ["b07"] and r["cutoff"] == 5
    assert [x["team"] for x in r["rows"]] == ["b02", "b01", "b03", "b04", "b05", "b06"]  # 1·T1 + 2·T2
    assert rows["b02"]["weighted"] == 130 and rows["b01"]["history"] == [1, 2] and rows["b02"]["history"] == [2, 1]
    assert abs(sum(x["p_top"] for x in r["rows"]) - 5) < 0.01 and rows["b02"]["p_first"] > 0.99
    assert rows["b06"]["p_top"] < 0.01 and rows["b01"]["won"] == 0.2 and rows["b01"]["per"]["2"]["mean"] == 30
    write(3, [0, 0, 0, 0, 0, 100])  # a new summary invalidates the cache
    assert event_results(str(ev))["rows"][0]["team"] == "b06"
    server, url = serve(Source(event_dir=str(ev)), port=18767)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        got = json.loads(urllib.request.urlopen(url + "api/results").read())
        assert got["done"] == [1, 2, 3] and got["rows"][0]["team"] == "b06"
    finally:
        server.shutdown()
