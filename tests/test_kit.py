"""The starter kit, exercised the way a builder uses it: inside a fresh
workspace, as separate processes, and (on macOS) under a Seatbelt profile
modelled on the builder sandbox."""

import json
import os
import shutil
import stat
import subprocess
import sys
import time

import pytest

from arena.engine.spec import NLHE
from arena.engine.table import DOUBLING
from arena.house_bots import KIT_BOTS
from arena.referee.workspace import build_workspace, write_clock
from arena.tournament.card import make_card
from arena.variants.render import render_event_md

BOTS = os.path.join(os.path.dirname(__file__), "bots")
PY = sys.executable


@pytest.fixture
def ws(tmp_path):
    path = str(tmp_path / "ws-b01")
    card = make_card(event="kit-test", team="b01", spec=NLHE, points=[100, 60, 40, 25, 15, 10, 5, 0],
                     blinds=DOUBLING, cooldown_seconds=120, localsim_max_tables=12, localsim_max_seconds=30)
    build_workspace(path, card, render_event_md(card, samples=20_000), brief_md="brief")
    return path


def run(ws, script, *args, sandbox=None):
    cmd = [PY, f"kit/{script}", *args]
    if sandbox:
        cmd = ["sandbox-exec", "-f", sandbox] + cmd
    p = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, timeout=240)
    return p.returncode, p.stdout + p.stderr


def put_bot(ws, name):
    shutil.rmtree(os.path.join(ws, "bot"))
    shutil.copytree(os.path.join(BOTS, name), os.path.join(ws, "bot"))


def test_workspace_layout(ws):
    for rel in ("EVENT.md", "NOTES.md", "bot/agent.py", "bot/__init__.py", ".brief/BRIEF.md", ".clock.json",
                "kit/RULES.md", "kit/icm.py", "kit/event.json", "kit/arena/engine/hand.py",
                "kit/arena/tournament/validate.py", "kit/arena/kit/icm.py"):
        assert os.path.exists(os.path.join(ws, rel)), rel
    card = json.load(open(os.path.join(ws, "kit", "event.json")))
    assert card["variant"]["name"] == "nlhe" and "nlhe" in open(os.path.join(ws, "EVENT.md")).read()


def test_kit_has_practice_opponents_but_no_strong_strategy(ws):
    assert sorted(os.listdir(os.path.join(ws, "kit", "house_bots"))) == sorted(KIT_BOTS)
    markers = ("TagCore", "push_ok", "call_range", "icm_hero", "eq_top", "_strategy")
    for root, _, files in os.walk(ws):
        for fn in files:
            path = os.path.join(root, fn)
            assert not fn.startswith("_strategy"), path
            if fn.endswith((".py", ".json", ".md")):
                text = open(path, errors="replace").read()
                assert not [m for m in markers if m in text], path
    for name in KIT_BOTS:
        decks = json.load(open(os.path.join(ws, "kit", "house_bots", name, "_common.json")))["decks"]
        assert all(set(d) == {"ranks", "pct", "eq_multi"} for d in decks.values()), name


def test_clock(ws):
    code, out = run(ws, "clock.py")
    assert code == 0 and "Practice mode" in out
    now = time.time()
    write_clock(ws, [{"name": "Build window", "start": now - 60, "end": now + 600, "then": "T1 starts.", "submit": True}])
    code, out = run(ws, "clock.py")
    assert ("Build window: 9m" in out or "Build window: 10m" in out) and "left" in out and "T1 starts." in out
    write_clock(ws, [{"name": "Build window", "start": now - 600, "end": now - 60, "then": "", "submit": True}])
    assert "over" in run(ws, "clock.py")[1]


def test_check_submit_and_cooldown(ws):
    code, out = run(ws, "check_bot.py", "--tables", "2")
    assert code == 0 and "OK:" in out, out
    code, out = run(ws, "submit.py")
    assert code == 0 and "ACCEPTED" in out, out
    snaps = [d for d in os.listdir(os.path.join(ws, ".submissions")) if d[0].isdigit()]
    assert len(snaps) == 1
    agent = os.path.join(ws, ".submissions", snaps[0], "agent.py")
    assert not os.stat(agent).st_mode & stat.S_IWUSR
    code, out = run(ws, "submit.py")
    assert code == 1 and "cooldown" in out
    log = [json.loads(l) for l in open(os.path.join(ws, ".submissions", "log.jsonl"))]
    assert [r["status"] for r in log] == ["accepted", "rejected"]
    code, out = run(ws, "clock.py")
    assert snaps[0] in out


@pytest.mark.parametrize("bot,expect", [("crasher", "exceptions"), ("illegal", "illegal"), ("badinit", "failed to start")])
def test_submit_rejects_broken_bots(ws, bot, expect):
    put_bot(ws, bot)
    code, out = run(ws, "submit.py")
    assert code == 1 and "REJECTED" in out and expect in out, out


def test_submit_rejects_static_problems_and_closed_windows(ws):
    agent = os.path.join(ws, "bot", "agent.py")
    original = open(agent).read()
    with open(agent, "w") as f:
        f.write("from arena.engine import hand\n" + original)
    code, out = run(ws, "submit.py")
    assert code == 1 and "imports 'arena'" in out
    with open(agent, "w") as f:
        f.write(original + "\ndef broken(:\n")
    code, out = run(ws, "submit.py")
    assert code == 1 and "doesn't compile" in out
    with open(agent, "w") as f:
        f.write(original)
    now = time.time()
    write_clock(ws, [{"name": "Patch window", "start": now + 300, "end": now + 700, "then": "", "submit": True}])
    code, out = run(ws, "submit.py")
    assert code == 1 and "next opens" in out


def test_localsim_respects_the_table_cap(ws):
    code, out = run(ws, "localsim.py", "--tables", "100", "--opponents", "self")
    assert code == 0, out
    assert out.splitlines()[0].startswith("12 tables") and "<- you" in out


def test_localsim_plays_earlier_versions(ws):
    old = os.path.join(ws, ".submissions", "001-0a1b2c3d")
    shutil.copytree(os.path.join(ws, "bot"), old)
    code, out = run(ws, "localsim.py", "--tables", "2", "--opponents", ".submissions/001-0a1b2c3d/,nit")
    assert code == 0, out
    assert "001-0a1b2c3d_1" in out and "nit_2" in out and "<- you" in out
    code, out = run(ws, "localsim.py", "--opponents", "tag")
    assert code == 2 and "not found: tag" in out


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("sandbox-exec"), reason="needs macOS sandbox-exec")
def test_kit_works_inside_a_builder_like_sandbox(ws, tmp_path):
    sibling, events = tmp_path / "ws-b02", tmp_path / "events"
    for d in (sibling, events):
        d.mkdir()
        (d / "canary.txt").write_text("secret")
    real = lambda p: os.path.realpath(str(p))
    profile = tmp_path / "builder.sb"
    profile.write_text(f"""(version 1)
(allow default)
(deny network*)
(deny file-write* (require-all (require-not (subpath "{real(ws)}")) (require-not (subpath "/private/var/folders")) (require-not (subpath "/dev"))))
(deny file-read* (subpath "{real(sibling)}"))
(deny file-read* (subpath "{real(events)}"))
""")
    for target in (sibling, events):
        p = subprocess.run(["sandbox-exec", "-f", str(profile), "/bin/cat", str(target / "canary.txt")],
                           capture_output=True, text=True)
        assert p.returncode != 0 and "secret" not in p.stdout
    code, out = run(ws, "check_bot.py", "--tables", "2", sandbox=str(profile))
    assert code == 0 and "OK:" in out, out
    code, out = run(ws, "submit.py", sandbox=str(profile))
    assert code == 0 and "ACCEPTED" in out, out
    code, out = run(ws, "localsim.py", "--tables", "3", "--opponents", "self", sandbox=str(profile))
    assert code == 0 and "<- you" in out, out
