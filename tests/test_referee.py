"""Referee: config draws, builder launch commands, and mock events end to end,
including a forced crash and resume."""

import json
import os
import random
import shutil
import signal
import stat
import subprocess
import sys
import time

import pytest
import yaml

from arena.referee.builders import (TOOLS, builder_env, builder_tmpdir, claude_command, read_stream, team_settings,
                                    write_env_file)
import arena.referee.__main__ as referee_main
import arena.referee.event as event_module
from arena.referee.commands import archived_bots, cleanup
from arena.referee.config import Team, assign_teams, draw_event, load_config
from arena.referee.event import Event, Paused
from arena.referee.prompts import render_nudge

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_ROOT = "/private/tmp/nlt"  # short like the real one, and apart from it so tests never touch a live event


@pytest.fixture(autouse=True, scope="module")
def _remove_test_temp_folders():
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def config(tmp_path, name, **over):
    cfg = {"event": {"name": name, "seed": 7},
           "builders": {"count": 8, "models": {"sonnet": 6, "opus": 2}, "archetypes": "assign_half",
                        "launch_stagger_seconds": 1},
           "auth": {"mode": "subscription"},
           "schedule": {"build_minutes": 20, "submit_cooldown_seconds": 120, "tournaments": 2, "patch_minutes": 7},
           "table": {"points": "standard", "blinds": {"schedule": "doubling"}},
           "variant": "nlhe", "tournament": {"iterations": 12, "workers": 2},
           "paths": {"workspaces_root": str(tmp_path / "workspaces"), "builder_tmp_root": TMP_ROOT}}
    for k, v in over.items():
        cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) else v
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return str(path)


def test_draw_is_deterministic_and_checks_counts(tmp_path):
    cfg = load_config(config(tmp_path, "d1", variant="random", table={"points": "random", "blinds": {"schedule": "random"}}))
    a, teams, _ = draw_event(cfg)
    b, _, _ = draw_event(cfg)
    assert a == b and a["seed"] == 7 and len(teams) == 8
    assert sum(t.archetype is not None for t in teams) == 4
    assert sorted(t.model for t in teams).count("opus") == 2
    cfg["builders"]["models"] = {"sonnet": 3}
    with pytest.raises(ValueError, match="sum to 3"):
        assign_teams(cfg, random.Random(0))


def test_builder_command_and_settings(tmp_path):
    teams = [Team(f"b0{i}", "sonnet", None, str(tmp_path / f"ws/b0{i}")) for i in (1, 2, 3)]
    s = team_settings(teams[0], teams, "/ev/mini", REPO, "/venv", ("/python",))
    deny = s["permissions"]["deny"]
    assert "WebFetch" in deny and "Agent" in deny and "Workflow" in deny and "mcp__*" in deny
    assert f"Read(/{teams[1].workspace}/**)" in deny and "Read(//ev/mini/**)" in deny
    assert s["sandbox"]["filesystem"]["allowRead"] == [teams[0].workspace, "/venv", "/python"]
    assert f"/private/tmp/claude-{os.getuid()}" in s["sandbox"]["filesystem"]["denyRead"]  # the operator's temp folder
    assert str(tmp_path) in s["sandbox"]["filesystem"]["denyRead"]  # every event's workspaces, not only this one's
    fs = team_settings(teams[0], teams, "/ev/mini", REPO, "/venv", (), "/private/tmp/nl", "/private/tmp/nl/a1b2c3/b01"
                       )["sandbox"]["filesystem"]
    assert fs["allowRead"][-1] == "/private/tmp/nl/a1b2c3/b01" and fs["denyRead"][-1] == "/private/tmp/nl"
    with pytest.raises(ValueError, match="longer than 30 bytes"):
        builder_tmpdir("/private/tmp/nolimit-arena", "/ev/mini", "b01")
    assert s["permissions"]["allow"] == ["Bash"]
    assert s["sandbox"]["network"] == {"allowedDomains": [], "strictAllowlist": True}
    assert s["permissions"]["blockReadsOutsideWorkingDirectories"] and s["crossSessionInbound"] == "refuse"
    sub = claude_command("go", model="sonnet", brief_file="/b.md", settings_file="/s.json", session_id="u1",
                         auth_mode="subscription")
    assert "--restricted" in sub and "--bare" not in sub and sub[sub.index("--tools") + 1] == TOOLS
    assert sub[sub.index("--session-id") + 1] == "u1" and "--append-system-prompt-file" in sub
    for flag in ("--permission-prompts", "--strict-mcp-config", "--disable-slash-commands", "--verbose"):
        assert flag in sub
    api = claude_command("go", model="opus", brief_file="/b.md", settings_file="/s.json", session_id="u1",
                         auth_mode="api_key", resume=True, budget_usd=3)
    assert "--bare" in api and api[api.index("--resume") + 1] == "u1" and "--session-id" not in api
    assert api[api.index("--append-system-prompt-file") + 1] == "/b.md"  # resumed runs get the brief too
    assert "--effort" not in api
    strong = claude_command("go", model="opus", brief_file="/b.md", settings_file="/s.json", session_id="u1",
                            auth_mode="subscription", resume=True, effort="max")
    assert strong[strong.index("--effort") + 1] == "max"  # on every run: settings files can't hold "max"
    nudge = render_nudge(125, "12:34:56", "003-abc")
    assert "2m 05s left" in nudge and "12:34:56" in nudge and "003-abc" in nudge
    assert "no accepted submission" in render_nudge(60, "12:34:56", None)
    assert api[api.index("--max-budget-usd") + 1] == "3"
    env = builder_env(REPO)
    assert env["PATH"].startswith(os.path.join(REPO, ".venv", "bin"))
    assert not any(k.startswith(("CLAUDECODE", "ANTHROPIC")) for k in env)
    assert env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"
    assert "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB" not in env  # forces permission mode "default" on 2.1.300
    venv = tmp_path / "venv"
    venv.mkdir()
    path = write_env_file(str(venv))
    assert os.path.dirname(path) == str(venv)  # outside every workspace, so builders can't edit it
    assert f'export PATH="{venv}/bin:$PATH"' in open(path).read()
    assert builder_env(REPO, builder_venv=str(venv), env_file=path)["CLAUDE_ENV_FILE"] == path


def test_read_stream_tells_interrupts_and_idle_runs_from_failures(tmp_path):
    def init():
        return {"type": "system", "subtype": "init", "session_id": "s1", "tools": ["Bash"], "model": "claude-opus-5-5"}

    def result(cost, **kw):
        return {"type": "result", "subtype": "success", "is_error": False, "session_id": "s1",
                "total_cost_usd": cost, **kw}

    tool = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}
    talk = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Still my final bot."}]}}
    # Shapes seen on 2.1.300: a working run, a run stopped by the deadline SIGINT mid-command, two idle replies.
    rows = [init(), tool, result(0.10),
            init(), tool, result(0.12, subtype="error_during_execution", is_error=True, terminal_reason="aborted_tools"),
            init(), talk, result(0.13), init(), talk, result(0.14)]
    log = tmp_path / "b01.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")
    s = read_stream(str(log))
    assert s["errors"] == [] and s["interrupted"] == 1 and s["results"] == 4
    assert s["idle_streak"] == 2 and s["run_calls"] == 0 and s["cost_usd"] == 0.14  # cost is cumulative
    size = log.stat().st_size
    retry = {"type": "system", "subtype": "api_retry", "attempt": 1, "error_status": 429, "error": "rate_limit"}
    meter = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "unifiedWindows": {
        "five_hour": {"utilization": 1.0, "resetsAt": 1793260200}}}}
    with open(log, "a") as f:
        for row in (init(), retry, meter, result(0.15, subtype="error_during_execution", is_error=True,
                                                 terminal_reason="api_error")):
            f.write(json.dumps(row) + "\n")
    s = read_stream(str(log))
    assert s["errors"] == ["usage_limit", "error_during_execution"] and s["retries"] == 1  # a retry alone isn't fatal
    assert s["idle_streak"] == 3 and s["usage"] == 1.0 and s["resets_at"] == 1793260200
    assert s["model"] == "claude-opus-5-5"
    s = read_stream(str(log), errors_from=log.stat().st_size)  # after a resume, old errors don't count
    assert s["errors"] == [] and s["events_since"] == 0 and s["results"] == 5
    assert read_stream(str(log), errors_from=size)["events_since"] == 4


def test_clock_check_resumes_finished_builders_with_backoff(tmp_path, monkeypatch):
    ev = Event.new(config(tmp_path, "nudge", builders={"count": 2, "models": {"sonnet": 2}, "archetypes": "none"}),
                   root=str(tmp_path / "events"))
    launched = []
    monkeypatch.setattr(ev, "_alive", lambda team: False)
    monkeypatch.setattr(ev, "_launch", lambda t, kind, k, end, prompt, resume=None: launched.append((t.team, prompt, resume)))
    os.makedirs(ev.p("logs"))
    init = {"type": "system", "subtype": "init", "session_id": "s"}
    done = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.1}
    tool = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}
    for team, rows in (("b01", [init, tool, done]), ("b02", [init, done])):  # b02's last run was an idle reply
        with open(ev.p("logs", f"{team}.jsonl"), "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        ev.state["builders"][team] = {"phase": "build:0", "launches": 1, "session_id": "s"}
    end = time.time() + 200
    ev._nudge_finished("build", 0, end)
    assert [(t, r) for t, _, r in launched] == [("b01", True)] and "left" in launched[0][1]
    ev.state["builders"]["b02"]["ended"] -= 61  # the backoff after one idle reply has passed
    ev._nudge_finished("build", 0, end)
    assert [t for t, _, _ in launched] == ["b01", "b01", "b02"]  # b01's stub launch never "ended"
    launched.clear()
    ev._nudge_finished("build", 0, time.time() + 30)  # too close to the deadline
    assert launched == []


def test_each_builder_gets_its_own_temp_folder(tmp_path):
    # Without CLAUDE_CODE_TMPDIR every builder's Claude Code shares /private/tmp/claude-<uid> with the operator's.
    ev = Event.new(config(tmp_path, "tmp", builders={"count": 2, "models": {"sonnet": 2}, "archetypes": "none"}),
                   root=str(tmp_path / "events"))
    a, b = (ev.tmpdir(t.team) for t in ev.teams)
    assert a != b and os.path.dirname(a) == os.path.dirname(b) and len(a.encode()) <= 30
    assert all(stat.S_IMODE(os.stat(p).st_mode) == 0o700 for p in (a, os.path.dirname(a), TMP_ROOT))
    fs = json.load(open(ev.p("settings", "b01.json")))["sandbox"]["filesystem"]
    assert a in fs["allowRead"] and b not in fs["allowRead"] and TMP_ROOT in fs["denyRead"]
    env = ev.builder_env("b01")
    assert env["CLAUDE_CODE_TMPDIR"] == env["TMPDIR"] == a and "CLAUDE_CODE_TMPDIR" not in ev.builder_env()
    cleanup(ev)
    assert not os.path.exists(os.path.dirname(a))


def test_gauntlet_field_can_pool_events(tmp_path):
    for event, team, t in (("e1", "b01", "T1"), ("e1", "b01", "T6"), ("e2", "b01", "T6"), ("e3", "b01", "T6")):
        os.makedirs(tmp_path / event / "bots" / team / t)
    names = [e.name for e in archived_bots("event:e1,e2", root=str(tmp_path))]
    assert names == ["e1/b01/T6", "e2/b01/T6"]


def test_builders_never_inherit_the_referees_stdin(tmp_path, monkeypatch):
    # `claude -p` appends piped stdin to its prompt (seen on 2.1.300), so an inherited stdin would reach every builder.
    ev = Event.new(config(tmp_path, "stdin", builders={"count": 2, "models": {"sonnet": 2}, "archetypes": "none"}),
                   root=str(tmp_path / "events"))
    seen = []
    monkeypatch.setattr(event_module.subprocess, "Popen",
                        lambda cmd, **kw: seen.append(kw) or type("P", (), {"pid": 1, "poll": lambda self: None})())
    for mock in (True, False):
        ev.state["mock"] = mock
        ev._launch(ev.teams[0], "build", 0, time.time() + 60, None)
    assert [kw["stdin"] for kw in seen] == [subprocess.DEVNULL] * 2
    assert seen[1]["env"]["CLAUDE_CODE_TMPDIR"] == ev.tmpdir(ev.teams[0].team)


def test_usage_limit_pause_waits_for_the_reset_and_keeps_the_time_left(tmp_path, monkeypatch):
    ev = Event.new(config(tmp_path, "limit", builders={"count": 2, "models": {"sonnet": 2}, "archetypes": "none"}),
                   root=str(tmp_path / "events"))
    now = [1_000_000.0]
    clock = type("Clock", (), {"time": staticmethod(lambda: now[0]),
                               "sleep": staticmethod(lambda s: now.__setitem__(0, now[0] + s))})
    monkeypatch.setattr(referee_main, "time", clock)
    monkeypatch.setattr(event_module.time, "time", lambda: now[0])
    ev.state["windows"] = [{"kind": "build", "k": 0, "start": now[0] - 600, "end": now[0] + 1200}]
    calls = []

    def fake_run(mock, time_scale):
        calls.append(now[0])
        if len(calls) == 1:  # the plan's limit stops everyone 10 minutes into a 30-minute window
            ev.state.update(paused="usage limit", paused_at=now[0], pause_kind="usage_limit", resets_at=now[0] + 3600)
            raise Paused("usage limit")

    monkeypatch.setattr(ev, "run", fake_run)
    monkeypatch.setattr(ev, "save", lambda: None)
    assert referee_main.run(ev, mock=False, time_scale=1.0) == 0
    assert calls[1] - calls[0] >= 3600 + 120  # waited for the reset, plus a margin
    w = ev.state["windows"][-1]
    assert w["end"] - w["start"] == 1200 and not ev.state["paused"]  # the 20 minutes it had left
    ev.cfg["schedule"]["on_usage_limit"] = "stop"
    calls.clear()
    assert referee_main.run(ev, mock=False, time_scale=1.0) == 2


def run_referee(args, events_root, **kw):
    env = {**os.environ, "ARENA_EVENTS_ROOT": events_root, "PYTHONPATH": REPO}
    return subprocess.Popen([sys.executable, "-m", "arena.referee", *args], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)


@pytest.mark.slow
def test_mock_event_survives_a_crash_and_resumes(tmp_path):
    events = str(tmp_path / "events")
    p = run_referee(["new", config(tmp_path, "crashy")], events)
    assert p.wait(120) == 0, p.stdout.read()
    state_path = os.path.join(events, "crashy", "state.json")
    p = run_referee(["run", "crashy", "--mock", "--time-scale", "0.01", "--no-viz"], events, start_new_session=True)
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            phase = json.load(open(state_path))["phase"]
        except (OSError, ValueError):
            continue
        if phase.startswith("patch"):
            break
    os.killpg(p.pid, signal.SIGKILL)   # the referee dies mid patch window
    p.wait(30)
    assert json.load(open(state_path))["phase"].startswith("patch")
    p = run_referee(["run", "crashy", "--no-viz"], events)
    out, _ = p.communicate(timeout=600)
    assert p.returncode == 0, out
    state = json.load(open(state_path))
    assert state["phase"] == "done"
    for k in (1, 2):
        summary = json.load(open(os.path.join(events, "crashy", "results", f"T{k}", "summary.json")))
        assert summary["entries"], f"T{k} had no entries"
    report = open(os.path.join(events, "crashy", "report", "REPORT.md")).read()
    for heading in ("Final weighted leaderboard", "T1 (weight 1)", "T2 (weight 2)", "By archetype",
                    "Substitutions", "Submission timeline", "Builder failures", "Cost"):
        assert heading in report
    p = run_referee(["status", "crashy"], events)
    assert "phase done" in p.communicate(timeout=60)[0]
    p = run_referee(["cleanup", "crashy"], events)
    assert p.wait(120) == 0
    assert os.path.exists(os.path.join(events, "crashy", "workspaces.tar.gz"))
    assert not os.path.exists(str(tmp_path / "workspaces" / "crashy"))
