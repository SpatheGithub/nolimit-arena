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


# The equity engines (ourbot/lessons/equity.py)

def _variant(name):
    from ourbot.lessons._common import Variant
    return Variant(None if name == "nlhe" else VARIANTS[name].to_dict())


@pytest.mark.parametrize("name", ["nlhe", "shortdeck", "royal", "crazy_pineapple", "plo"])
def test_equity_engine_values_match_the_engine_rules(name):
    import random as pyrandom
    import numpy as np
    from ourbot.lessons import equity
    var = _variant(name)
    eq = equity.for_variant(var)
    rng = pyrandom.Random(7)
    hole = var.hole_count if var.family == "omaha" else 2
    for _ in range(300):
        nb = rng.randint(max(3, 5 - hole), var.board_count)
        cards = rng.sample(var.deck, hole + nb)
        want = var.best(cards[:hole], cards[hole:])
        if var.family == "omaha":
            got = eq.values(np.array([cards[:hole]]), np.array([cards[hole:]]))[0]
        else:
            got = eq.values(np.array([cards]))[0]
        assert int(got) == want


@pytest.mark.parametrize("name", ["nlhe", "plo"])
def test_monte_carlo_equity_matches_enumeration_on_the_turn(name):
    import random as pyrandom
    import numpy as np
    from ourbot.lessons import equity
    var = _variant(name)
    eq = equity.for_variant(var)
    rng = pyrandom.Random(11)
    hole = var.hole_count if var.family == "omaha" else 2
    hero = rng.sample(var.deck, hole)
    board = rng.sample([c for c in var.deck if c not in hero], var.board_count - 1)
    rg = eq.range_idx(0.3, eq.dead_mask(hero + board))[:40]
    hands = [[int(c) for c in eq.bank[i]] for i in rg] if var.family == "omaha" else \
        [[int(eq.A[i]), int(eq.B[i])] for i in rg]
    tot = cnt = 0.0
    for vh in hands:
        for c in var.deck:
            if c not in hero and c not in board and c not in vh:
                a, b = var.best(hero, board + [c]), var.best(vh, board + [c])
                tot += (a > b) + 0.5 * (a == b)
                cnt += 1
    mc = eq.equity(hero, board, [rg], np.random.default_rng(3), n=20000)
    assert mc == pytest.approx(tot / cnt, abs=0.015)


@pytest.mark.parametrize("variant,switch", [("royal", "eqpost"), ("crazy_pineapple", "eqdisc"), ("plo", "eqplo"),
                                            ("shortdeck", "wide")])
def test_the_equity_and_wide_switches_pass_validation(tmp_path, variant, switch):
    copy = tmp_path / "bot"
    shutil.copytree(BOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
    on = {**DEFAULTS, switch: True, "eqpost": switch in ("eqpost", "eqdisc")}
    (copy / "switches.json").write_text(json.dumps(on))
    card = make_card(event="test", spec=VARIANTS[variant], points=POINTS["standard"], blinds=BLINDS["doubling"])
    v = validate(str(copy), settings_from_card(card), HOUSE, tables=2, seed=3)
    assert v["ok"], v["reasons"]


def test_actions_size_each_bet_by_the_pot_it_faced():
    from types import SimpleNamespace
    from ourbot.lessons.agent import Agent
    hist = [[0, 6, "sb", 10], [0, 7, "bb", 20], [0, 3, "raise", 60], [0, 6, "fold", 0], [0, 7, "call", 40],
            [1, 7, "check", 0], [1, 3, "raise", 65], [1, 7, "raise", 200]]
    acts = Agent.actions(SimpleNamespace(hist=hist))
    assert acts[3] == [(0, "raise", pytest.approx(0.8), 0), (1, "raise", pytest.approx(0.5), 0)]
    assert acts[7] == [(0, "call", 0.0, 1), (1, "check", 0.0, 0), (1, "raise", pytest.approx(135 / 260), 1)]
