"""Hand evaluation for any VariantSpec.

``get_evaluator(spec).evaluate(hole, board)`` returns a canonical int for the
best five-card hand the spec's card-use rule allows; ``showdown(holes, board)``
returns one per hole, aligned. Values are comparable within one spec only:
higher wins, equal values tie.

    value = strength << 20 | t0 << 16 | t1 << 12 | t2 << 8 | t3 << 4 | t4

``strength`` is the category's index in ``spec.ranking.order`` (0 = weakest).
``t0..t4`` are rank indices (2 = 0 ... A = 12) that break ties within the
category, most significant first, zero-padded:

    high_card, flush           the five ranks, high to low
    pair                       pair rank, then three kickers high to low
    two_pair                   high pair, low pair, kicker
    trips                      trips rank, then two kickers
    straight, straight_flush   top card (an ace-low straight's top is its highest non-ace)
    full_house                 trips rank, pair rank
    quads                      quads rank, kicker

GenericEvaluator is the slow reference: it enumerates five-card hands, works
for every spec and defines the values. get_evaluator returns the table-driven
FastEvaluator (fasteval.py), which is tested to return the same values.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations
from typing import TYPE_CHECKING

from .cards import RANKS
from .spec import VariantSpec

if TYPE_CHECKING:
    from .fasteval import FastEvaluator


def straight_tops(ranks: str, ace_low: bool) -> dict[int, int]:
    """Map the 13-bit rank mask of each straight in this deck to its top rank."""
    dr = sorted(RANKS.index(r) for r in ranks)
    tops: dict[int, int] = {}
    for i in range(len(dr) - 4):
        mask = 0
        for r in dr[i:i + 5]:
            mask |= 1 << r
        tops[mask] = dr[i + 4]
    if ace_low and 12 in dr and len(dr) >= 5 and 12 not in dr[:4]:
        mask = 1 << 12
        for r in dr[:4]:
            mask |= 1 << r
        tops.setdefault(mask, dr[3])
    return tops


def pack(strength: int, tiebreak: Sequence[int]) -> int:
    v = strength
    for i in range(5):
        v = (v << 4) | (tiebreak[i] if i < len(tiebreak) else 0)
    return v


class GenericEvaluator:
    """Reference evaluator: enumerates every allowed five-card combination."""

    def __init__(self, spec: VariantSpec):
        self.spec = spec
        self.order = spec.ranking.order
        self._strength = {c: i for i, c in enumerate(self.order)}
        self._tops = straight_tops(spec.ranks, spec.ranking.ace_low)
        self._splits = spec.hole_splits()

    def evaluate(self, hole: Sequence[int], board: Sequence[int]) -> int:
        best = -1
        for k, b in self._splits:
            if k > len(hole) or b > len(board):
                continue
            for hs in combinations(hole, k):
                for bs in combinations(board, b):
                    v = self.eval5(hs + bs)
                    if v > best:
                        best = v
        if best < 0:
            raise ValueError("no legal five-card hand")
        return best

    def showdown(self, holes: Sequence[Sequence[int]], board: Sequence[int]) -> list[int]:
        return [self.evaluate(h, board) for h in holes]

    def eval5(self, five: Sequence[int]) -> int:
        ranks = sorted((c >> 2 for c in five), reverse=True)
        flush = len({c & 3 for c in five}) == 1
        mask = 0
        for r in ranks:
            mask |= 1 << r
        top = self._tops.get(mask)
        counts: dict[int, int] = {}
        for r in ranks:
            counts[r] = counts.get(r, 0) + 1
        groups = sorted(counts.items(), key=lambda rc: (rc[1], rc[0]), reverse=True)
        shape = tuple(c for _, c in groups)
        by_group = [r for r, _ in groups]
        if top is not None:
            cat, tb = ("straight_flush" if flush else "straight"), (top,)
        elif shape == (4, 1):
            cat, tb = "quads", by_group
        elif shape == (3, 2):
            cat, tb = "full_house", by_group
        elif flush:
            cat, tb = "flush", ranks
        elif shape == (3, 1, 1):
            cat, tb = "trips", by_group
        elif shape == (2, 2, 1):
            cat, tb = "two_pair", by_group
        elif shape == (2, 1, 1, 1):
            cat, tb = "pair", by_group
        else:
            cat, tb = "high_card", ranks
        return pack(self._strength[cat], tb)

    def category(self, value: int) -> str:
        return self.order[value >> 20]


_CACHE: dict[VariantSpec, FastEvaluator] = {}


def get_evaluator(spec: VariantSpec) -> FastEvaluator:
    """The fast evaluator for ``spec``, built on first use and cached per spec."""
    ev = _CACHE.get(spec)
    if ev is None:
        from .fasteval import FastEvaluator
        ev = _CACHE[spec] = FastEvaluator(spec)
    return ev
