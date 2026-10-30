"""The field study (milestone 7): hand-log profiles calibrated on the house-bot zoo,
per-table points, the rank view's bootstrap, the report's new sections, the hand
printer, and the debrief with a mock analyst."""

import json
import os
import shutil
import subprocess
import sys

import pytest
import yaml

from arena.engine.spec import NLHE
from arena.house_bots import ZOO
from arena.referee.builders import SENTINEL_TOOL
from arena.referee.debrief import debrief_command, debrief_settings
from arena.referee.field import field_md, leaks
from arena.tournament import profile as pf
from arena.tournament import tables
from arena.tournament.hands import main as print_hands
from arena.tournament.play import Settings
from arena.tournament.pool import Entry
from arena.tournament.tournament import run_tournament
from arena.viz.results import event_results

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZOO_TEAMS = {"b01": "nit", "b02": "maniac", "b03": "pot_odds", "b04": "tag", "b05": "minraiser",
             "b06": "threshold", "b07": "montecarlo", "b08": "icm_pushfold"}


def _event_files(ev_dir, root) -> None:
    card = {"event": os.path.basename(ev_dir), "variant": NLHE.to_dict(), "points": [100, 60, 40, 25, 15, 10, 5, 0],
            "points_name": "standard", "blinds": [[10 * 2**k, 20 * 2**k, 0] for k in range(8)],
            "blinds_name": "doubling", "level_hands": 25, "hand_cap": 200, "seats": 8, "starting_stack": 2000,
            "iterations": 40, "tournaments": 1, "build_minutes": 20, "patch_minutes": 7, "seed": 7,
            "decision_limit_ms": 1.0, "timing": "thread_cpu", "hang_watchdog_ms": 50, "init_limit_s": 2,
            "import_limit_s": 30, "bot_size_limit_mb": 100, "allowed_packages": ["numpy"], "cooldown_seconds": 120,
            "localsim_max_tables": 1000, "localsim_max_seconds": 240}
    (ev_dir / "card.json").write_text(json.dumps(card))
    (ev_dir / "teams.json").write_text(json.dumps([{"team": t, "model": "opus", "archetype": None,
                                                     "workspace": str(root / t)} for t in ZOO_TEAMS]))
    (ev_dir / "config.yaml").write_text(yaml.safe_dump({"auth": {"mode": "subscription"}, "schedule": {}}))
    (ev_dir / "state.json").write_text(json.dumps({"phase": "done", "windows": [], "builders": {}, "frozen": {},
                                                   "mock": True}))


@pytest.fixture(scope="module")
def event(tmp_path_factory):
    """A one-tournament event whose teams are house bots, with real hand logs."""
    root = tmp_path_factory.mktemp("events")
    ev_dir = root / "zoo"
    out = ev_dir / "results" / "T1"
    entries = [Entry(team, ZOO[bot]["path"]) for team, bot in ZOO_TEAMS.items()]
    res = run_tournament(entries, Settings(spec=NLHE), iterations=40, seed=7, workers=2, log_dir=str(out))
    (out / "summary.json").write_text(json.dumps({"meta": res["meta"], "entries": res["entries"]}, default=str))
    _event_files(ev_dir, root)
    return str(ev_dir), res


def test_profile_matches_the_tables_counts_and_reads_the_zoo(event):
    ev_dir, res = event
    out = os.path.join(ev_dir, "results", "T1")
    prof = pf.load(out)
    assert os.path.exists(os.path.join(out, pf.FILE)) and pf.load(out) == prof  # saved, and read back the same
    rows = {r["name"]: r for r in res["entries"]}
    for team, b in prof["bots"].items():  # the replay sees the hands, VPIP and PFR the tables counted
        assert b["hands"] == rows[team]["hands"]
        assert sum(r[1] for r in b["stack"].values()) == round(rows[team]["vpip"] * rows[team]["hands"])
        assert sum(r[2] for r in b["dealt"].values()) == round(rows[team]["pfr"] * rows[team]["hands"])
    bots = prof["bots"]

    def fold_to_steal(t):
        return pf.rate(pf.spot(bots[t], "vs_steal"), pf.F)

    def river_call(t):
        return pf.rate(pf.spot(bots[t], "vs_river_bet"), pf.C)

    assert fold_to_steal("b01") > fold_to_steal("b02") + 0.15  # the nit gives up its blinds, the maniac doesn't
    assert river_call("b03") > river_call("b01") + 0.3           # pot_odds calls down, the nit doesn't
    size, share = pf.usual(bots["b05"]["open_bb"])  # the min-raiser opens to 2 bb, except all-in when shorter
    assert size == "2" and share > 0.95             # (a busy machine's timeouts change how often it's short)


def test_per_table_points_rebuild_from_the_hand_log(event):
    ev_dir, res = event
    out = os.path.join(ev_dir, "results", "T1")
    assert tables.from_log(out)["tables"] == tables.rows(res["tables"])
    assert tables.load(out)["tables"] == tables.rows(res["tables"]) and os.path.exists(os.path.join(out, tables.FILE))


def test_rank_view_bootstraps_whole_tables_and_falls_back_without_them(event, tmp_path):
    ev_dir, _ = event
    r = event_results(ev_dir)
    assert r["rank_method"] == "bootstrap"
    assert abs(sum(x["p_top"] for x in r["rows"]) - 5) < 0.01
    for x in r["rows"]:
        assert abs(sum(x["ranks"]) - 1) < 0.01 and x["rank_range"][0] <= x["rank_median"] <= x["rank_range"][1]
    bare = tmp_path / "bare"  # the summaries alone: no tables.json and no hand log to rebuild it from
    (bare / "results" / "T1").mkdir(parents=True)
    for name in ("card.json", "teams.json"):
        shutil.copy(os.path.join(ev_dir, name), bare / name)
    shutil.copy(os.path.join(ev_dir, "results", "T1", "summary.json"), bare / "results" / "T1" / "summary.json")
    normal = event_results(str(bare))
    assert normal["rank_method"] == "normal" and [x["team"] for x in normal["rows"]] == [x["team"] for x in r["rows"]]


def test_report_sections_cover_every_bot_and_price_leaks(event):
    ev_dir, _ = event
    md = "\n".join(field_md(ev_dir))
    for heading in ("## Rank view", "## Field profile", "### Biggest leaks per bot", "## Exploit board"):
        assert heading in md
    for team in ZOO_TEAMS:
        assert f"| {team} |" in md
    for label, _, _ in pf.BOARD:
        assert f"| {label} |" in md
    bots = pf.merge([pf.load(os.path.join(ev_dir, "results", "T1"))])
    got = leaks(bots, "b02")
    assert got and all(c < 0 for _, c, _, _ in got)


def test_hand_printer_shows_a_teams_tables(event, capsys):
    ev_dir, _ = event
    assert print_hands([os.path.join(ev_dir, "results", "T1"), "--team", "b01", "--tables", "1", "--hands", "2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("=== table") and "b01" in out and "result:" in out and "preflop" in out


def test_debrief_mock_and_the_real_runs_guard_rails(event):
    ev_dir, _ = event
    env = {**os.environ, "ARENA_EVENTS_ROOT": os.path.dirname(ev_dir), "PYTHONPATH": REPO}
    had_lessons = os.path.exists(os.path.join(REPO, "LESSONS.md"))
    p = subprocess.run([sys.executable, "-m", "arena.referee", "debrief", "zoo", "--mock"], cwd=REPO, env=env,
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    report = os.path.join(ev_dir, "report")
    assert "## 6. Where the field leaks points" in open(os.path.join(report, "DEBRIEF.mock.md")).read()
    assert not os.path.exists(os.path.join(report, "DEBRIEF.md"))  # a mock never overwrites a real debrief
    assert "mock debrief" in open(os.path.join(report, "LESSONS.mock.md")).read()
    assert os.path.exists(os.path.join(REPO, "LESSONS.md")) == had_lessons  # a mock never touches the real one
    info = json.load(open(os.path.join(report, "debrief.json")))
    assert info["wrote_debrief"] and info["lessons_added"] >= 1 and info["settings_loaded"] and info["cost_usd"] == 0
    assert "## Exploit board" in open(os.path.join(report, "REPORT.md")).read()
    assert os.path.exists(os.path.join(ev_dir, "event_card.md"))

    debrief_md = os.path.join(REPO, "events", "x", "report", "DEBRIEF.md")
    s = debrief_settings(debrief_md, os.path.join(REPO, "LESSONS.md"))
    assert s["permissions"]["allow"][:2] == ["Edit(./events/x/report/DEBRIEF.md)", "Edit(./LESSONS.md)"]
    assert debrief_settings(debrief_md, "/elsewhere/LESSONS.md")["permissions"]["allow"][1] == "Edit(//elsewhere/LESSONS.md)"
    assert SENTINEL_TOOL in s["permissions"]["deny"]
    cmd = debrief_command("prompt", model="opus", settings_file="/s.json", session_id="sid", auth_mode="subscription",
                          effort="max", budget_usd=15)
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk" and "--restricted" in cmd and "--bare" not in cmd
    assert cmd[cmd.index("--tools") + 1].endswith(SENTINEL_TOOL) and cmd[cmd.index("--max-budget-usd") + 1] == "15"
