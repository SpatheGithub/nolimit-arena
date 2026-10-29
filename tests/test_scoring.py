"""ICM (arena/kit/icm.py) and table scoring."""

import itertools
import random

import pytest

from arena.kit.icm import icm_equity
from arena.tournament.scoring import mean_ci, table_points

STANDARD = (100, 60, 40, 25, 15, 10, 5, 0)


def brute_icm(stacks, payouts):
    """Malmuth-Harville by enumerating every finishing order."""
    n = len(stacks)
    pay = list(payouts) + [0] * n
    eq = [0.0] * n
    for order in itertools.permutations(range(n)):
        p, left = 1.0, sum(stacks)
        for i in order:
            p *= stacks[i] / left
            left -= stacks[i]
        for place, i in enumerate(order):
            eq[i] += p * pay[place]
    return eq


def test_icm_hand_checked_example():
    assert icm_equity([5000, 3000, 2000], [100, 60, 40]) == pytest.approx([76.786, 65.5, 57.714], abs=1e-3)


def test_icm_matches_brute_force_and_conserves_points():
    rng = random.Random(1)
    for _ in range(200):
        n = rng.randint(2, 6)
        stacks = [rng.randint(1, 5000) for _ in range(n)]
        payouts = sorted((rng.choice([0, 1, 5, 20, 100]) for _ in range(rng.randint(1, n))), reverse=True)
        got = icm_equity(stacks, payouts)
        assert got == pytest.approx(brute_icm(stacks, payouts))
        assert sum(got) == pytest.approx(sum(payouts[:n]))


def test_icm_edge_cases():
    assert icm_equity([], [100]) == []
    assert icm_equity([10, 10], [100, 0]) == pytest.approx([50, 50])
    assert icm_equity([10, 0], [100, 60]) == pytest.approx([100, 60])  # no chips: last
    assert icm_equity([3, 4], [0, 0]) == [0.0, 0.0]
    eq = icm_equity([8000, 4000, 2000, 2000], STANDARD)
    assert eq[0] < 8000 / 16000 * sum(STANDARD[:4])  # chip leader is compressed
    assert eq[2] == pytest.approx(eq[3])


def test_table_points_places_ties_and_cap():
    places = {7: (8, 8), 2: (6, 7), 5: (6, 7), 0: (5, 5), 6: (4, 4)}
    stacks = [0, 6000, 0, 6000, 4000, 0, 0, 0]
    pts = table_points(places, [1, 3, 4], stacks, STANDARD)
    assert pts[7] == 0 and pts[0] == 15 and pts[6] == 25 and pts[2] == pts[5] == 7.5
    assert pts[1] == pytest.approx(pts[3]) and pts[4] < pts[1]
    assert sum(pts) == pytest.approx(sum(STANDARD))
    assert table_points({0: (1, 1), 1: (2, 2)}, [0], [3000, 0], (10, 1)) == [10, 1]


def test_mean_ci():
    m, se, lo, hi = mean_ci([1, 2, 3, 4])
    assert m == 2.5 and se == pytest.approx(0.6455, abs=1e-4) and lo < m < hi
    assert mean_ci([]) == (0.0, 0.0, 0.0, 0.0)
    assert mean_ci([7]) == (7, 0.0, 7, 7)
