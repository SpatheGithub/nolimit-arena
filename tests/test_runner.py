"""Bot runner: loading, substitutions, fault injection and native-hang recovery."""

import os
import shutil

import pytest

from arena.engine.spec import NLHE
from arena.runner.guard import Capture
from arena.runner.loader import bot_hash, load_bot
from arena.runner.obs import BadAction, parse_action
from arena.tournament.play import Settings
from arena.tournament.pool import Entry
from arena.tournament.tournament import run_tournament

BOTS = os.path.join(os.path.dirname(__file__), "bots")


def entries(*names):
    return [Entry(n, os.path.join(BOTS, n)) for n in names]


def by_name(result):
    return {r["name"]: r for r in result["entries"]}


def test_loader_unique_names_relative_imports_and_namespace_packages():
    a = load_bot(os.path.join(BOTS, "relimport"), "bot_test_a")  # no __init__.py
    b = load_bot(os.path.join(BOTS, "relimport"), "bot_test_b")
    assert a is not b and a.__module__ == "bot_test_a.agent"
    with pytest.raises(ImportError):
        load_bot(os.path.join(BOTS, "importerr"), "bot_test_c")


def test_bot_hash_tracks_content(tmp_path):
    src = os.path.join(BOTS, "caller")
    dst = tmp_path / "caller"
    shutil.copytree(src, dst)
    assert bot_hash(str(dst)) == bot_hash(src)
    (dst / "agent.py").write_text((dst / "agent.py").read_text() + "\n# changed\n")
    assert bot_hash(str(dst)) != bot_hash(src)


def test_parse_action():
    assert parse_action({"action": "RAISE", "amount": 40.0}) == ("raise", 40, None)
    assert parse_action({"action": "discard", "cards": ["As"]}) == ("discard", 0, [51])
    for bad in ("call", {"action": "shove"}, {"action": "raise"}, {"action": "discard", "cards": ["Xx"]}):
        with pytest.raises(BadAction):
            parse_action(bad)


def test_capture_keeps_first_lines():
    c = Capture(keep=2, width=5)
    c.write("abcdefgh\nsecond\nthird\nfourth")
    assert c.lines == ["abcde", "secon"] and c.dropped == 1


def test_slow_core_adjustment(monkeypatch):
    from arena.runner import seat as seat_mod
    runner = seat_mod.BotRunner("thread_cpu")
    try:
        runner.probe_base_ns = 20_000
        monkeypatch.setattr(seat_mod, "_probe_ns", lambda loops=2000: 40_000)   # a core half as fast
        assert runner.core_adjusted(1_600_000) == 800_000
        monkeypatch.setattr(seat_mod, "_probe_ns", lambda loops=2000: 21_000)   # within 15%: no change
        assert runner.core_adjusted(1_600_000) == 1_600_000
        monkeypatch.setattr(seat_mod, "_probe_ns", lambda loops=2000: 15_000)   # faster: baseline tightens
        assert runner.core_adjusted(1_600_000) == 1_600_000 and runner.probe_base_ns == 15_000
    finally:
        runner.close()


def test_substitutions_are_counted_by_type():
    st = Settings(spec=NLHE, hand_cap=40, native_kill_s=3.0)
    res = run_tournament(entries("crasher", "illegal", "slow", "networker", "printer", "hanger",
                                 "badinit", "slowinit", "importerr", "caller", "raiser", "checkfold"),
                         st, iterations=3, seed=11, workers=2)
    r = by_name(res)
    assert res["meta"]["crashed_tables"] == []
    assert r["crasher"]["errors"] > 0 and r["crasher"]["errors"] == pytest.approx(r["crasher"]["decisions"] / 3, rel=0.2)
    assert r["illegal"]["illegal"] == r["illegal"]["decisions"] > 0
    assert r["slow"]["timeouts"] > 0 and r["slow"]["cpu_max_us"] > 1000
    assert r["networker"]["errors"] == r["networker"]["decisions"] > 0
    assert any("network" in line for line in r["networker"]["output"])
    assert "hello from init" in r["printer"]["output"]
    assert r["hanger"]["hangs"] == r["hanger"]["tables"] == 3   # one interrupted loop per table
    assert r["badinit"]["init_failures"] == r["slowinit"]["init_failures"] == 3
    assert r["importerr"]["import_failures"] == 3 and "importerr" in res["meta"]["import_problems"]
    for name in ("badinit", "slowinit", "importerr"):
        assert r[name]["frozen"] == r[name]["decisions"]
    for name in ("caller", "raiser", "checkfold"):
        row = r[name]
        assert row["errors"] + row["illegal"] + row["timeouts"] + row["hangs"] + row["frozen"] == 0


def test_native_hangs_kill_the_worker_and_replay_the_table():
    st = Settings(spec=NLHE, hand_cap=15, native_kill_s=1.5)
    res = run_tournament(entries("native", "swallower", "caller", "raiser", "checkfold"),
                         st, iterations=1, seed=2, workers=2)
    r = by_name(res)
    kinds = {(e["kind"], e["entry"]) for e in res["meta"]["events"]}
    assert ("native_hang", "native") in kinds and ("native_hang", "swallower") in kinds
    assert res["meta"]["crashed_tables"] == []
    for name in ("native", "swallower"):
        assert r[name]["frozen"] == r[name]["decisions"] > 0   # replayed with the bot folding
    assert r["caller"]["decisions"] > 0 and r["caller"]["frozen"] == 0
