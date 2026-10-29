"""Scenario tests for the dealer rules in arena/engine/hand.py, one rule each."""

import random

import numpy as np
import pytest

from arena.engine.cards import cards
from arena.engine.hand import Hand, IllegalAction, Legal
from arena.engine.spec import NLHE, Street, VariantSpec
from arena.engine.xval import FLHE, PLO


def stacked(n, button, holes, board, spec=NLHE):
    """A deck that deals ``holes[i]`` to player i and then ``board``."""
    order = [(button + 1 + k) % n for k in range(n)]
    hl = [cards(h) for h in holes]
    seq = [hl[i][r] for r in range(len(hl[0])) for i in order] + cards(board)
    return seq + [c for c in spec.deck() if c not in seq]


def check_down(h):
    while h.to_act is not None:
        h.act("check" if h.legal().check else "call")


def test_heads_up_button_posts_sb_acts_first_then_last():
    h = Hand(NLHE, [1000, 1000], button=0, sb=10, bb=20, deck=stacked(2, 0, ["AsKs", "2c3d"], "7h8h9cTdJs"))
    assert (h.sb_index, h.bb_index, h.to_act) == (0, 1, 0)
    assert h.legal() == Legal(True, False, 10, 40, 1000)
    h.act("call")
    assert h.to_act == 1 and h.legal().check and h.legal().raise_min == 40
    h.act("check")
    assert h.street == 1 and h.to_act == 1  # big blind acts first after the first street


def test_three_handed_order_and_big_blind_option():
    h = Hand(NLHE, [1000] * 3, button=0, sb=10, bb=20, rng=random.Random(1))
    assert h.to_act == 0  # first left of the big blind is the button
    h.act("call")
    h.act("call")
    assert h.to_act == 2 and h.legal() == Legal(False, True, 0, 40, 1000)
    h.act("check")
    assert h.street == 1 and h.to_act == 1  # small blind first after the flop


def test_min_raise_is_the_largest_full_raise():
    h = Hand(NLHE, [1000] * 4, button=0, sb=10, bb=20, rng=random.Random(2))
    assert h.to_act == 3 and h.legal().raise_min == 40
    h.act("raise", 60)
    assert h.legal().raise_min == 100
    h.act("raise", 150)
    assert h.legal().raise_min == 240


def test_short_all_in_does_not_reopen_for_players_who_acted():
    # UTG raises to 100, button calls, SB shoves 170 (a 70 raise, less than the full 80).
    h = Hand(NLHE, [1000, 170, 1000, 1000], button=0, sb=10, bb=20, rng=random.Random(3))
    h.act("raise", 100)   # UTG (3)
    h.act("call")         # button (0)
    h.act("allin")        # SB (1) to 170
    assert h.to_act == 2  # BB hasn't acted: may raise, by at least the full 80
    assert h.legal().raise_min == 250
    h.act("call")
    assert h.to_act == 3 and h.legal() == Legal(True, False, 70, 0, 0)
    h.act("call")
    assert h.to_act == 0 and h.legal() == Legal(True, False, 70, 0, 0)


def test_short_all_ins_that_add_up_to_a_full_raise_reopen():
    h = Hand(NLHE, [200, 1000, 1000, 1000, 150], button=0, sb=10, bb=20, rng=random.Random(4))
    h.act("raise", 100)   # UTG (3), a full raise of 80
    h.act("allin")        # 4 to 150: +50
    h.act("allin")        # button (0) to 200: +50, 100 in total since UTG acted
    h.act("fold")         # SB
    h.act("call")         # BB stays in, so a raise could still be called
    assert h.to_act == 3
    assert h.legal() == Legal(True, False, 100, 280, 1000)


def test_short_all_in_below_the_big_blind_does_not_reopen():
    h = Hand(NLHE, [1000, 1000, 35], button=0, sb=10, bb=20, rng=random.Random(5))
    h.act("call")
    h.act("call")
    h.act("check")
    assert h.street == 1 and h.to_act == 1
    h.act("check")        # SB
    h.act("allin")        # BB bets its last 15, less than the big blind
    assert h.to_act == 0 and h.legal().raise_min == 35  # button hasn't acted: may raise
    h.act("call")
    assert h.to_act == 1 and h.legal() == Legal(True, False, 15, 0, 0)


def test_short_big_blind_sets_the_call_amount():
    h = Hand(NLHE, [1000, 1000, 5], button=0, sb=10, bb=20, rng=random.Random(6))
    assert h.to_act == 0
    assert h.legal() == Legal(True, False, 10, 30, 1000)


def test_side_pots_and_payouts():
    h = Hand(NLHE, [100, 300, 600], button=0, sb=10, bb=20,
             deck=stacked(3, 0, ["AsAd", "KsKd", "7c2h"], "3c8d9hJsQc"))
    h.act("allin")   # button 100
    h.act("allin")   # SB 300
    h.act("call")    # BB 300
    r = h.result
    assert r.showdown and h.board == cards("3c8d9hJsQc")
    assert sorted(h.live_pots()) == [(300, (0, 1, 2)), (400, (1, 2))]
    assert r.payoffs == [200, 100, -300]


def test_odd_chip_goes_to_the_first_winner_left_of_the_button():
    h = Hand(NLHE, [1000] * 3, button=0, sb=5, bb=10, ante=1,
             deck=stacked(3, 0, ["Tc6d", "Td6h", "AhKh"], "9c8d7h2s2c"))
    check_down(h)
    assert h.pot_total() == 33
    assert h.result.payoffs == [5, 6, -11]  # 33 splits 16/16; the odd chip goes to seat 1


def test_uncalled_chips_are_returned():
    h = Hand(NLHE, [1000, 1000], button=0, sb=10, bb=20, rng=random.Random(7))
    h.act("raise", 500)
    h.act("fold")
    assert h.result.payoffs == [20, -20] and not h.result.showdown
    assert (0, 0, "return", 480) in h.history


def test_action_validation_and_aliases():
    h = Hand(NLHE, [1000, 1000], button=0, sb=10, bb=20, rng=random.Random(8))
    with pytest.raises(IllegalAction):
        h.act("check")                 # facing the big blind
    with pytest.raises(IllegalAction):
        h.act("raise", 39)
    with pytest.raises(IllegalAction):
        h.act("raise", 40.5)
    h.act("raise", np.int64(40))       # numpy ints are fine
    h.act("call")
    with pytest.raises(IllegalAction):
        h.act("fold")                  # nothing to call
    h.act("bet", 20.0)                 # "bet" is a raise; integral floats are fine
    h.act("allin")
    assert h.history[-1] == (1, 0, "raise", 960)
    with pytest.raises(IllegalAction):
        h.act("raise", 2000)
    with pytest.raises(IllegalAction):
        h.act("shove")


def test_no_raise_when_nobody_could_call_it():
    h = Hand(NLHE, [300, 1000], button=0, sb=10, bb=20, rng=random.Random(9))
    h.act("allin")
    assert h.legal() == Legal(True, False, 280, 0, 0)


def test_pointless_decision_is_skipped():
    # Button calls all-in for less, SB folds: the big blind has nothing to decide.
    h = Hand(NLHE, [11, 171, 1616], button=0, sb=10, bb=20, rng=random.Random(10))
    h.act("call")
    h.act("fold")
    assert h.to_act is None and h.result.showdown and len(h.board) == 5
    assert sum(h.result.payoffs) == 0


def test_all_in_runs_the_board_out():
    h = Hand(NLHE, [500, 500], button=1, sb=10, bb=20, rng=random.Random(11))
    h.act("allin")
    h.act("call")
    assert h.to_act is None and len(h.board) == 5 and h.result.showdown


def test_antes_are_dead_money_and_short_ante_wins_only_the_main_pot():
    h = Hand(NLHE, [1000, 1000, 3], button=0, sb=10, bb=20, ante=5,
             deck=stacked(3, 0, ["KsKd", "7c2h", "AsAd"], "3c8d9hJsQc"))
    assert [e for e in h.history if e[2] == "ante"] == [(0, 1, "ante", 5), (0, 2, "ante", 3), (0, 0, "ante", 5)]
    assert h.legal().call == 10  # the big blind had nothing left after the ante
    check_down(h)
    assert sorted(h.live_pots()) == [(9, (0, 1, 2)), (24, (0, 1))]
    assert h.result.payoffs == [9, -15, 6]


def test_pot_limit_raise_cap():
    h = Hand(PLO, [1000] * 3, button=0, sb=10, bb=20, rng=random.Random(12))
    assert h.legal() == Legal(True, False, 20, 40, 70)
    h.act("raise", 70)
    assert h.legal().raise_max == 70 + 100 + 60  # current bet + pot (100) + the 60 to call


def test_fixed_limit_sizes_and_cap():
    h = Hand(FLHE, [1000] * 3, button=0, sb=10, bb=20, rng=random.Random(13))
    assert h.legal() == Legal(True, False, 20, 40, 40)
    for to in (40, 60, 80, 100):     # four raises; the blinds don't count toward the cap
        h.act("raise", to)
    assert h.legal().raise_max == 0
    check_down(h)
    h2 = Hand(FLHE, [1000] * 2, button=0, sb=10, bb=20, rng=random.Random(14))
    h2.act("call")
    h2.act("check")
    h2.act("check")
    h2.act("check")
    assert h2.street == 2 and h2.legal().raise_min == h2.legal().raise_max == 40  # big bet on the turn


PINEAPPLE = VariantSpec("pineapple", (Street("preflop", hole=3), Street("flop", discard=1, board=3),
                                      Street("turn", board=1), Street("river", board=1)))


def test_discard_phase():
    PINEAPPLE.validate(8)
    h = Hand(PINEAPPLE, [1000] * 3, button=0, sb=10, bb=20, rng=random.Random(15))
    for _ in range(3):
        h.act("call" if h.legal().call else "check")
    assert h.phase == "discard" and h.to_act == 1 and h.legal() == Legal(False, False, 0, 0, 0, 1)
    assert len(h.board) == 0
    with pytest.raises(IllegalAction):
        h.act("check")
    with pytest.raises(IllegalAction):
        h.act("discard", cards=[h.hole[2][0]])  # not this player's card
    first = h.hole[1][0]
    h.act("discard", cards=[first])
    h.act_default()                              # player 2 discards its first card
    h.act("discard", cards=h.hole[0][1:2])
    assert h.phase == "bet" and len(h.board) == 3 and all(len(c) == 2 for c in h.hole)
    assert first not in h.hole[1]
    check_down(h)
    assert sum(h.result.payoffs) == 0


def test_streets_without_betting_and_late_hole_cards():
    spec = VariantSpec("twist", (Street("preflop", hole=2), Street("flop", board=3),
                                 Street("bonus", hole=1, board=1, bet=False), Street("river", board=1)))
    spec.validate(8)
    h = Hand(spec, [1000] * 3, button=0, sb=10, bb=20, rng=random.Random(17))
    h.act("call")
    h.act("fold")         # SB folds before the late hole card
    h.act("check")
    assert h.street == 1 and len(h.board) == 3
    h.act("check")
    h.act("check")
    assert h.street == 3 and len(h.board) == 5   # the bonus street dealt and moved on
    assert [len(c) for c in h.hole] == [3, 2, 3]  # only players still in get the late card
    check_down(h)
    assert h.result.showdown and sum(h.result.payoffs) == 0


def test_spec_validation():
    with pytest.raises(ValueError, match="need 21 cards"):
        VariantSpec("royal", NLHE.streets, ranks="TJQKA").validate(8)
    VariantSpec("royal", NLHE.streets, ranks="TJQKA").validate(7)
    with pytest.raises(ValueError, match="first street"):
        VariantSpec("x", (Street("deal", hole=2, bet=False),) + NLHE.streets[1:]).validate()
    assert VariantSpec.from_dict(NLHE.to_dict()) == NLHE


def test_random_hands_conserve_chips():
    rng = random.Random(16)
    for _ in range(3000):
        n = rng.randint(2, 8)
        stacks = [rng.choice([rng.randint(1, 50), rng.randint(100, 5000)]) for _ in range(n)]
        h = Hand(NLHE, stacks, rng.randrange(n), 10, 20, ante=rng.choice([0, 2]), rng=rng)
        while h.to_act is not None:
            lg = h.legal()
            r = rng.random()
            if lg.raise_max and r < 0.3:
                h.act("raise", rng.randint(lg.raise_min, lg.raise_max))
            elif lg.fold and r < 0.5:
                h.act("fold")
            else:
                h.act("call" if lg.call else "check")
        res = h.result
        assert sum(res.payoffs) == 0 and min(res.stacks) >= 0
        assert sum(p.amount for p in res.pots) == h.pot_total()
