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
from ourbot.lessons.agent import SWITCHES, LessonReads, load_switches

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(REPO, "ourbot", "lessons")
HOUSE = os.path.join(REPO, "arena", "house_bots")


@pytest.mark.parametrize("variant", ["nlhe", "shortdeck", "plo"])
def test_lessons_bot_passes_validation(variant):
    spec = NLHE if variant == "nlhe" else VARIANTS[variant]
    card = make_card(event="test", spec=spec, points=POINTS["standard"], blinds=BLINDS["doubling"])
    v = validate(BOT, settings_from_card(card), HOUSE, tables=2, seed=3)
    assert v["ok"], v["reasons"]


def test_switches_default_on_and_load_from_the_package(tmp_path):
    assert load_switches() == {k: True for k in SWITCHES}  # the shipped switches.json
    copy = tmp_path / "bot"
    shutil.copytree(BOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "switches.json").write_text(json.dumps({"resteal": False, "bogus": True}))
    spec = importlib.util.spec_from_file_location("ourbot_copy", copy / "__init__.py",
                                                  submodule_search_locations=[str(copy)])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["ourbot_copy"] = pkg
    spec.loader.exec_module(pkg)
    agent = importlib.import_module("ourbot_copy.agent")
    assert agent.load_switches() == {"resteal": False, "shove20": True, "noflat": True, "respect": True}


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
