"""Our bot (ourbot/lessons): it passes the referee's validation in every variant
family, its switches load, and its new read counts folds to 3-bets."""

import importlib
import importlib.util
import json
import os
import shutil
import sys

import pytest

from arena.engine.spec import NLHE
from arena.tournament.card import make_card, settings_from_card
from arena.tournament.validate import validate
from arena.variants.library import BLINDS, POINTS, VARIANTS
from ourbot.lessons.agent import DEFAULTS, SWITCHES, LessonReads, load_switches

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(REPO, "ourbot", "lessons")
HOUSE = os.path.join(REPO, "arena", "house_bots")


@pytest.mark.parametrize("variant", ["nlhe", "shortdeck", "plo"])
def test_lessons_bot_passes_validation(variant):
    spec = NLHE if variant == "nlhe" else VARIANTS[variant]
    card = make_card(event="test", spec=spec, points=POINTS["standard"], blinds=BLINDS["doubling"])
    v = validate(BOT, settings_from_card(card), HOUSE, tables=2, seed=3)
    assert v["ok"], v["reasons"]


def test_switches_load_from_the_package_over_the_defaults(tmp_path):
    assert set(load_switches()) == set(SWITCHES)
    assert load_switches() == DEFAULTS  # the shipped switches.json matches the code's defaults
    copy = tmp_path / "bot"
    shutil.copytree(BOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "switches.json").write_text(json.dumps({"resteal": False, "bogus": True}))
    spec = importlib.util.spec_from_file_location("ourbot_copy", copy / "__init__.py",
                                                  submodule_search_locations=[str(copy)])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["ourbot_copy"] = pkg
    spec.loader.exec_module(pkg)
    agent = importlib.import_module("ourbot_copy.agent")
    assert agent.load_switches() == {**DEFAULTS, "resteal": False}  # unknown keys are ignored


def test_the_blinds_can_face_a_single_open():
    # 2026-11-03 bug: the blinds' own "sb"/"bb" posts counted as acting, so resteal and noflat
    # never fired from the blinds, the main spot for defending against steals
    from types import SimpleNamespace
    from ourbot.lessons.agent import Agent
    hist = [[0, 6, "sb", 10], [0, 7, "bb", 20], [0, 3, "fold", 0], [0, 5, "raise", 50]]
    bb = SimpleNamespace(raises=1, callers=0, raiser=5, me=7, stacks=[2000] * 8, hist=hist)
    assert Agent.single_open(None, bb)
    limped = SimpleNamespace(**{**vars(bb), "hist": [[0, 6, "sb", 10], [0, 7, "bb", 20], [0, 7, "check", 0],
                                                     [0, 5, "raise", 50]]})
    assert not Agent.single_open(None, limped)  # hero acted voluntarily before the raise


def test_reads_count_an_openers_fold_to_a_three_bet():
    r = LessonReads(4)
    payoffs = {"0": 0, "1": -10, "2": -60, "3": 70}
    r.update({"payoffs": payoffs, "history": [(0, 2, "raise", 60), (0, 3, "raise", 200), (0, 0, "fold", 0),
                                               (0, 1, "fold", 0), (0, 2, "fold", 0)]})
    r.update({"payoffs": payoffs, "history": [(0, 2, "raise", 60), (0, 3, "raise", 200), (0, 0, "fold", 0),
                                               (0, 1, "fold", 0), (0, 2, "call", 140), (1, 2, "check", 0)]})
    r.update({"payoffs": payoffs, "history": [(0, 2, "raise", 60), (0, 3, "call", 60)]})  # no 3-bet
    assert (r.faced3[2], r.folded3[2]) == (2, 1)
    assert r.fold3_rate(2) == pytest.approx((1 + 3) / (2 + 4))
    assert r.loose(3) == pytest.approx((3 + 2) / (3 + 8))  # VPIP 3 of 3 hands, prior 0.25 with weight 8
