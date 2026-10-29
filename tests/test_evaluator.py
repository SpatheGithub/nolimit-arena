"""FastEvaluator against GenericEvaluator, published counts and pokerkit.

Heavy checks fan out over a process pool; the full seven-card census
(133,784,560 hands) is marked slow.
"""

from __future__ import annotations

import os
import random
from collections import Counter
from collections.abc import Callable, Iterator
from itertools import combinations, combinations_with_replacement, repeat
from multiprocessing import get_context
from multiprocessing.pool import Pool
from typing import Any

import pytest

from arena.engine.cards import CARD_STR
from arena.engine.evaluate import GenericEvaluator, get_evaluator
from arena.engine.fasteval import COUNT, RANK_KEYS, FastEvaluator
from arena.engine.spec import (NLHE, STANDARD_ORDER, Betting, CardUse, Ranking, Street,
                               VariantSpec)


def _spec(name: str, hole: int = 2, boards: tuple[int, ...] = (3, 1, 1), **kw: Any) -> VariantSpec:
    streets = (Street("preflop", hole=hole),) + tuple(
        Street(f"street{i + 2}", board=n) for i, n in enumerate(boards))
    spec = VariantSpec(name=name, streets=streets, **kw)
    spec.validate()
    return spec


def _swap(a: str, b: str) -> tuple[str, ...]:
    order = list(STANDARD_ORDER)
    i, j = order.index(a), order.index(b)
    order[i], order[j] = order[j], order[i]
    return tuple(order)


REVERSED = tuple(reversed(STANDARD_ORDER))
SHORT = _spec("short_deck", ranks="6789TJQKA", ranking=Ranking(_swap("flush", "full_house")))
ROYAL = _spec("royal", ranks="TJQKA")
DECK40 = _spec("deck40", ranks="56789TJQKA")
SUITS3 = _spec("three_suits", suits="cdh")
STRAIGHT_OVER_FLUSH = _spec("straight_over_flush", ranking=Ranking(_swap("straight", "flush")))
PLO = _spec("plo", hole=4, card_use=CardUse(2, 2), betting=Betting("pot_limit"))
AT_LEAST_ONE = _spec("at_least_one", card_use=CardUse(1, 5))
ONE_OF_THREE = _spec("one_of_three", hole=3, card_use=CardUse(1, 1))
BOARD4 = _spec("board4", boards=(3, 1))
# Orders where a suited five can lose to the same ranks unsuited: exercises
# the enumeration paths. Two suits make five-card suits common.
REVERSED_ANY = _spec("reversed_two_suits", suits="hs", ranking=Ranking(REVERSED))
REVERSED_PLO = _spec("reversed_plo", hole=4, suits="hs", card_use=CardUse(2, 2),
                     ranking=Ranking(REVERSED))
REVERSED_EIGHT = _spec("reversed_three_hole", hole=3, ranking=Ranking(REVERSED, ace_low=False))

SPECS = {s.name: s for s in (NLHE, SHORT, ROYAL, DECK40, SUITS3, STRAIGHT_OVER_FLUSH, PLO,
                             AT_LEAST_ONE, ONE_OF_THREE, BOARD4, REVERSED_ANY, REVERSED_PLO,
                             REVERSED_EIGHT)}

STANDARD_5 = {"straight_flush": 40, "quads": 624, "full_house": 3_744, "flush": 5_108,
              "straight": 10_200, "trips": 54_912, "two_pair": 123_552, "pair": 1_098_240,
              "high_card": 1_302_540}
STANDARD_7 = {"straight_flush": 41_584, "quads": 224_848, "full_house": 3_473_184,
              "flush": 4_047_644, "straight": 6_180_020, "trips": 6_461_620,
              "two_pair": 31_433_400, "pair": 58_627_800, "high_card": 23_294_460}
SHORT_5 = {"straight_flush": 24, "quads": 288, "full_house": 1_728, "flush": 480,
           "straight": 6_120, "trips": 16_128, "two_pair": 36_288, "pair": 193_536,
           "high_card": 122_400}
ROYAL_5 = {"straight_flush": 4, "quads": 80, "full_house": 480, "straight": 1_020,
           "trips": 1_920, "two_pair": 4_320, "pair": 7_680}


@pytest.fixture(scope="module")
def pool() -> Iterator[Pool]:
    with get_context("spawn").Pool(min(8, os.cpu_count() or 1)) as p:
        yield p


def _deal(rng: random.Random, spec: VariantSpec, players: int) -> tuple[list[list[int]], list[int]]:
    h, b = spec.hole_count, spec.board_count
    cards = rng.sample(spec.deck(), b + h * players)
    return [cards[b + h * i:b + h * (i + 1)] for i in range(players)], cards[:b]


def _gather(pool: Pool, fn: Callable[[Any], tuple[int, list]], jobs: list) -> tuple[int, list]:
    total, bad = 0, []
    for n, b in pool.imap_unordered(fn, jobs):
        total += n
        bad += b
    return total, bad


# -- pool workers ------------------------------------------------------------

def _random_deals(job: tuple[str, int, int, int]) -> tuple[int, list]:
    """Random deals: fast evaluate and showdown against the reference."""
    name, seed, deals, players = job
    spec = SPECS[name]
    fast, ref = get_evaluator(spec), GenericEvaluator(spec)
    rng = random.Random(seed)
    hands, bad = 0, []
    for _ in range(deals):
        holes, board = _deal(rng, spec, players)
        for hole, value in zip(holes, fast.showdown(holes, board)):
            want = ref.evaluate(hole, board)
            hands += 1
            if value != want or fast.evaluate(hole, board) != want:
                bad.append((name, hole, board, want, value))
    return hands, bad[:5]


def _five_card_census(job: tuple[str, int]) -> tuple[Counter, list]:
    """Every five-card hand of the deck whose lowest card is ``first``, split
    two hole + three board: fast categories, and hands where the reference differs."""
    name, first = job
    spec = SPECS[name]
    fast, ref = get_evaluator(spec), GenericEvaluator(spec)
    deck = spec.deck()
    counts: Counter = Counter()
    bad = []
    for rest in combinations(deck[deck.index(first) + 1:], 4):
        hole, board = (first, rest[0]), rest[1:]
        v = fast.evaluate(hole, board)
        counts[fast.category(v)] += 1
        if v != ref.evaluate(hole, board):
            bad.append((hole, board))
    return counts, bad[:5]


def _seven_card_census(pair: tuple[int, int]) -> Counter:
    """Categories of every seven-card hand whose two lowest cards are ``pair``."""
    ev = get_evaluator(NLHE)
    values = Counter(map(ev.evaluate, repeat(pair), combinations(range(pair[1] + 1, 52), 5)))
    counts: Counter = Counter()
    for v, n in values.items():
        counts[ev.category(v)] += n
    return counts


def _pokerkit_pairs(job: tuple[str, int, int]) -> tuple[int, list]:
    """Eight-handed random deals: every pair of hands must order the same way
    as pokerkit's (better, worse or tied)."""
    from pokerkit import OmahaHoldemHand, ShortDeckHoldemHand, StandardHighHand

    name, seed, deals = job
    hand_type = {"nlhe": StandardHighHand, "short_deck": ShortDeckHoldemHand,
                 "plo": OmahaHoldemHand}[name]
    spec = SPECS[name]
    ev = get_evaluator(spec)
    rng = random.Random(seed)
    pairs, bad = 0, []
    for _ in range(deals):
        holes, board = _deal(rng, spec, 8)
        ours = ev.showdown(holes, board)
        on_board = "".join(CARD_STR[c] for c in board)
        theirs = [hand_type.from_game("".join(CARD_STR[c] for c in h), on_board) for h in holes]
        for i, j in combinations(range(8), 2):
            pairs += 1
            if (ours[i] > ours[j]) - (ours[i] < ours[j]) != (theirs[i] > theirs[j]) - (theirs[i] < theirs[j]):
                bad.append((holes[i], holes[j], board, ours[i], ours[j], theirs[i], theirs[j]))
    return pairs, bad[:5]


# -- tables --------------------------------------------------------------------

def test_rank_keys_are_unique_up_to_seven_cards():
    for n in range(1, 8):
        multisets = [m for m in combinations_with_replacement(range(13), n)
                     if max(map(m.count, m)) <= 4]
        sums = {sum(RANK_KEYS[r] for r in m) for m in multisets}
        assert len(sums) == len(multisets)
        assert max(sums) < COUNT


def test_get_evaluator_is_fast_and_cached():
    ev = get_evaluator(NLHE)
    assert isinstance(ev, FastEvaluator)
    assert get_evaluator(NLHE) is ev
    assert ev.tables is get_evaluator(PLO).tables


# -- against the reference ---------------------------------------------------

def test_all_five_card_hands(pool: Pool):
    counts: Counter = Counter()
    bad = []
    for c, b in pool.imap_unordered(_five_card_census, [("nlhe", c) for c in range(48)]):
        counts.update(c)
        bad += b
    assert not bad
    assert sum(counts.values()) == 2_598_960
    assert counts == Counter(STANDARD_5)


def test_random_seven_card_holdem(pool: Pool):
    hands, bad = _gather(pool, _random_deals, [("nlhe", 100 + i, 5_000, 2) for i in range(20)])
    assert hands == 200_000
    assert not bad


@pytest.mark.parametrize("name", [s.name for s in (
    SHORT, ROYAL, DECK40, SUITS3, STRAIGHT_OVER_FLUSH, PLO, AT_LEAST_ONE, ONE_OF_THREE, BOARD4,
    REVERSED_ANY, REVERSED_PLO, REVERSED_EIGHT)])
def test_variant_random_deals(pool: Pool, name: str):
    spec = SPECS[name]
    players = min(3, (spec.deck_size - spec.board_count) // spec.hole_count)
    jobs = [(name, 1_000 * i + len(name), 1_000, players) for i in range(8)]
    hands, bad = _gather(pool, _random_deals, jobs)
    assert hands == 8_000 * players
    assert not bad


@pytest.mark.parametrize(("name", "want"), [("short_deck", SHORT_5), ("royal", ROYAL_5)])
def test_small_deck_five_card_census(pool: Pool, name: str, want: dict[str, int]):
    deck = SPECS[name].deck()
    counts: Counter = Counter()
    bad = []
    for c, b in pool.imap_unordered(_five_card_census, [(name, c) for c in deck[:-4]]):
        counts.update(c)
        bad += b
    assert not bad
    assert counts == Counter(want)


def test_reversed_orders_take_the_exact_paths():
    for spec in (REVERSED_ANY, REVERSED_PLO, REVERSED_EIGHT):
        assert not get_evaluator(spec).tables.suited_above
    for spec in (NLHE, SHORT, STRAIGHT_OVER_FLUSH):
        assert get_evaluator(spec).tables.suited_above


@pytest.mark.slow
def test_seven_card_census(pool: Pool):
    pairs = sorted(((c1, c2) for c2 in range(1, 47) for c1 in range(c2)), key=lambda p: p[1])
    counts: Counter = Counter()
    for c in pool.imap_unordered(_seven_card_census, pairs, chunksize=4):
        counts.update(c)
    assert sum(counts.values()) == 133_784_560
    assert counts == Counter(STANDARD_7)


# -- partial boards, errors, inputs ------------------------------------------

@pytest.mark.parametrize("name", ["nlhe", "plo", "at_least_one", "one_of_three", "board4"])
def test_partial_boards_match_reference(name: str):
    spec = SPECS[name]
    fast, ref = get_evaluator(spec), GenericEvaluator(spec)
    rng = random.Random(7)
    for _ in range(300):
        (hole,), board = _deal(rng, spec, 1)
        for n in range(len(board) + 1):
            try:
                want: int | str = ref.evaluate(hole, board[:n])
            except ValueError:
                want = "no hand"
            try:
                got: int | str = fast.evaluate(hole, board[:n])
            except ValueError:
                got = "no hand"
            assert got == want, (hole, board[:n])


def test_inputs_are_not_mutated():
    ev = get_evaluator(PLO)
    holes = [[51, 47, 2, 9], [50, 46, 13, 30]]
    board = [48, 44, 40, 3, 7]
    ev.showdown(holes, board)
    ev.evaluate(tuple(holes[0]), tuple(board))
    assert holes == [[51, 47, 2, 9], [50, 46, 13, 30]] and board == [48, 44, 40, 3, 7]


# -- pokerkit ------------------------------------------------------------------

@pytest.mark.parametrize("name", ["nlhe", "short_deck", "plo"])
def test_order_matches_pokerkit(pool: Pool, name: str):
    pytest.importorskip("pokerkit")
    jobs = [(name, 500 + i, 450) for i in range(8)]
    pairs, bad = _gather(pool, _pokerkit_pairs, jobs)
    assert pairs == 100_800
    assert not bad


# -- properties ----------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(SPECS))
def test_suit_relabelling_and_card_order(name: str):
    spec = SPECS[name]
    ev = get_evaluator(spec)
    suits = sorted({c & 3 for c in spec.deck()})
    players = min(4, (spec.deck_size - spec.board_count) // spec.hole_count)
    rng = random.Random(11)
    for _ in range(500):
        holes, board = _deal(rng, spec, players)
        values = ev.showdown(holes, board)
        relabel = dict(zip(suits, rng.sample(suits, len(suits))))

        def moved(cs: list[int]) -> list[int]:
            out = [c & ~3 | relabel[c & 3] for c in cs]
            rng.shuffle(out)
            return out
        assert [ev.evaluate(moved(h), moved(board)) for h in holes] == values
        assert values == [ev.evaluate(h, board) for h in holes]
