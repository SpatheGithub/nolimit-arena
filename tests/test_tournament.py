"""Tournament: seating, fillers, determinism across worker counts, hand logs."""

import json
import os
import zlib
from collections import Counter

import pytest

from arena.engine.spec import NLHE
from arena.tournament.handlog import bot_view, read_index, read_table
from arena.tournament.play import STAT_KEYS, Settings
from arena.tournament.pool import Entry
from arena.tournament.tournament import plan_tables, run_tournament

BOTS = os.path.join(os.path.dirname(__file__), "bots")
DETERMINISTIC = ["caller", "raiser", "checkfold", "seeded", "relimport"]


def field(n):
    return [Entry(f"{DETERMINISTIC[i % len(DETERMINISTIC)]}_{i}", os.path.join(BOTS, DETERMINISTIC[i % len(DETERMINISTIC)]))
            for i in range(n)]


def test_every_entry_sits_once_per_iteration_and_fillers_fill_the_rest():
    tasks = plan_tables(19, 5, 8, seed=3)
    assert len(tasks) == 5 * 3
    for it in range(5):
        seats = [(e, f) for t in tasks if t.iteration == it for e, f in zip(t.entries, t.fillers)]
        assert Counter(e for e, f in seats if not f) == Counter(range(19))
        assert sum(f for _, f in seats) == 24 - 19
    assert plan_tables(19, 5, 8, seed=3) == tasks
    assert plan_tables(19, 5, 8, seed=4) != tasks
    with pytest.raises(ValueError):
        plan_tables(1, 1, 8, seed=0)


def _deterministic_view(result, log_dir):
    timing = {"cpu_ns_sum", "cpu_ns_max", "wall_ns_max"}
    tables = {}
    for tid, r in sorted(result["tables"].items()):
        tables[tid] = (r["entries"], r["fillers"], r["hands"], r["places"], r["survivors"], r["stacks"],
                       r["points"], [{k: v for k, v in s.items() if k not in timing} for s in r["stats"]])
    logs = []
    for meta in read_index(log_dir):
        for h in read_table(log_dir, meta):
            for d in h[7]:
                d[10] = 0  # cpu_us
            logs.append(h)
    return tables, logs


def test_results_do_not_depend_on_the_number_of_workers(tmp_path):
    st = Settings(spec=NLHE, hand_cap=60)
    runs = []
    for workers in (1, 3):
        log_dir = str(tmp_path / f"w{workers}")
        res = run_tournament(field(13), st, iterations=4, seed=21, workers=workers, log_dir=log_dir)
        runs.append(_deterministic_view(res, log_dir))
    assert runs[0] == runs[1]
    assert len(runs[0][1]) > 100


def test_seed_changes_results_and_scores_add_up(tmp_path):
    st = Settings(spec=NLHE, hand_cap=60, hand_logs=False)
    a = run_tournament(field(8), st, iterations=3, seed=1, workers=2)
    b = run_tournament(field(8), st, iterations=3, seed=2, workers=2)
    assert [r["mean"] for r in a["entries"]] != [r["mean"] for r in b["entries"]]
    for r in a["tables"].values():
        assert sum(r["points"]) == pytest.approx(sum(st.points))
    assert all(row["tables"] == 3 for row in a["entries"])
    assert sorted(row["rank"] for row in a["entries"]) == list(range(1, 9))


def test_fillers_score_nothing_for_their_entry(tmp_path):
    st = Settings(spec=NLHE, hand_cap=30, hand_logs=False)
    res = run_tournament(field(3), st, iterations=2, seed=5, workers=1)
    assert all(row["tables"] == 2 for row in res["entries"])
    assert sum(sum(r["fillers"]) for r in res["tables"].values()) == 2 * 5


def test_bot_view_hides_other_hole_cards(tmp_path):
    st = Settings(spec=NLHE, hand_cap=40)
    log_dir = str(tmp_path / "logs")
    run_tournament(field(8), st, iterations=2, seed=9, workers=2, log_dir=log_dir)
    views = list(bot_view(log_dir, entry=0))
    assert len(views) == 2
    for v in views:
        for h in v["hands"]:
            assert v["seat"] in h["seats"] and len(h["hole"]) == 4
            assert v["seat"] not in h["shown"]
            assert set(h["shown"]) <= set(h["seats"])
    raw = open(os.path.join(log_dir, "hands.zlog"), "rb").read()
    assert len(raw) > 0 and json.loads(zlib.decompress(raw[:read_index(log_dir)[0]["size"]]))
