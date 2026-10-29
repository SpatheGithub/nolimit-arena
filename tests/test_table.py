"""Table rules: button movement, blind levels, elimination places, hand cap."""

import random

import pytest

from arena.engine.spec import NLHE
from arena.engine.table import Table
from tests.test_hand_rules import stacked


def call_station(table, hand):
    hand.act("call" if hand.legal().call else "check")


def random_bot(rng):
    def decide(table, hand):
        lg = hand.legal()
        r = rng.random()
        if lg.raise_max and r < 0.2:
            hand.act("raise", rng.choice([lg.raise_min, lg.raise_max]))
        elif lg.fold and r < 0.45:
            hand.act("fold")
        else:
            hand.act("call" if lg.call else "check")
    return decide


def test_button_moves_to_the_next_seat_with_chips():
    t = Table(NLHE, n_seats=4, stacks=[1000, 0, 1000, 1000], button=0, rng=random.Random(1))
    t.start_hand()
    assert t.button == 0 and t.seats == [0, 2, 3]
    t.hand.act("fold")
    t.hand.act("fold")
    t.finish_hand()
    t.start_hand()
    assert t.button == 2


def test_blind_levels_follow_hands_played_and_repeat_the_last():
    t = Table(NLHE, n_seats=2, blinds=[(10, 20), (20, 40, 5)], level_hands=2, rng=random.Random(2))
    seen = []
    for _ in range(5):
        h = t.start_hand()
        seen.append((h.sb_amount, h.bb_amount, h.ante))
        h.act("fold")
        t.finish_hand()
    assert seen == [(10, 20, 0), (10, 20, 0), (20, 40, 5), (20, 40, 5), (20, 40, 5)]


def test_simultaneous_busts_place_by_starting_stack_and_share_ties():
    t = Table(NLHE, n_seats=4, stacks=[1000, 100, 200, 100], button=0, rng=random.Random(3))
    t.start_hand(deck=stacked(4, 0, ["AsAd", "7c2h", "8d3s", "9h4c"], "KsQd5h6c2s"))
    h = t.hand
    h.act("allin")    # seat 3 (UTG) for 100
    h.act("allin")    # button for 1000
    h.act("call")     # SB all-in for 100
    h.act("call")     # BB all-in for 200
    out = t.finish_hand()
    assert t.over() and t.places == {2: (2, 2), 1: (3, 4), 3: (3, 4), 0: (1, 1)}
    assert sorted(out) == [(1, (3, 4)), (2, (2, 2)), (3, (3, 4))]
    assert t.stacks == [1400, 0, 0, 0]


def test_hand_cap_leaves_survivors_unplaced():
    t = Table(NLHE, hand_cap=3, rng=random.Random(4))
    t.play(lambda table, hand: hand.act("check" if hand.legal().check else "fold"))
    assert t.hands_played == 3 and t.over()
    assert len(t.survivors()) >= 2 and all(s not in t.places for s in t.survivors())


def test_full_tables_conserve_chips_and_place_everyone():
    for seed in range(30):
        rng = random.Random(seed)
        t = Table(NLHE, rng=rng)
        t.play(random_bot(rng))
        assert sum(t.stacks) == 8 * 2000
        placed = {s for s, _ in t.places.items()}
        assert placed | set(t.survivors()) == set(range(8))
        if len(t.survivors()) == 1:
            assert t.places[t.survivors()[0]] == (1, 1)


def test_tables_are_reproducible_from_the_seed():
    def run(seed):
        rng = random.Random(seed)
        t = Table(NLHE, rng=rng)
        t.play(random_bot(rng))
        return t.hands_played, t.stacks, t.places
    assert run(7) == run(7)
    assert run(7) != run(8)


def test_unplayable_variant_is_rejected():
    from arena.engine.spec import VariantSpec
    with pytest.raises(ValueError):
        Table(VariantSpec("royal", NLHE.streets, ranks="TJQKA"))
