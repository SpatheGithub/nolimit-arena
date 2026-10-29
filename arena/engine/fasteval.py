"""Table-driven hand evaluation, value-identical to GenericEvaluator.

Each card id has an additive key

    KEY[c] = (RANK_KEYS[rank] + 2**23) << 16 | 1 << 4 * suit

Summed from 0x3333, a hand's keys hold, above bit 16, the card count times
2**23 plus a rank-key sum that is unique for every rank multiset of at most
seven cards; the low 16 bits hold one 4-bit counter per suit whose top bit is
set exactly when that suit has five or more cards (``s & 0x8888``). For up to
seven cards:

- ``Tables.rank[s >> 16]`` is the best value of any five of them scored
  unsuited (one dict serves 5, 6 and 7 cards);
- ``Tables.suited[mask]`` is the best value of five ranks of one suit, by the
  suit's 13-bit rank mask.

Both are built per rank list and ranking from GenericEvaluator.eval5 (the
definition): five cards directly, more by dynamic programming. A hand without
five cards of a suit is one rank lookup. With them, the larger of the two
lookups is exact when a suited five always outranks the same five ranks
unsuited (straight flush above straight, flush above high card); for other
orders the hand's five-card subsets are enumerated.

Card-use rules, decided per (hole, board) size from ``spec.hole_splits()``:

- any five of at most seven cards: one lookup, in code generated for the
  sizes; ``showdown`` sums the board once;
- any five of more cards: the best seven-card subset (or every five);
- exactly k hole cards (Omaha): per board rank multiset a cached row maps
  each hole k-subset to its best unsuited value; the suited part is added
  only when the board has 5 - k cards of a suit (other orders: enumeration);
- at most k: "any five" over each k-subset of the hole;
- at least k: "any five", unless fewer hole cards reach the same value;
- otherwise: every allowed five-card subset.

Every spec that passes ``validate()`` is served this way; none falls back to
GenericEvaluator.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement
from typing import Any

from .cards import RANKS
from .evaluate import GenericEvaluator
from .spec import VariantSpec

Eval = Callable[[Sequence[int], Sequence[int]], int]
Showdown = Callable[[Sequence[Sequence[int]], Sequence[int]], list[int]]

RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
START = 0x3333
FLUSH = 0x8888

RANK_KEY: tuple[int, ...] = tuple(RANK_KEYS[c >> 2] + COUNT for c in range(52))
KEY: tuple[int, ...] = tuple(RANK_KEY[c] << 16 | 1 << 4 * (c & 3) for c in range(52))
RANK_BIT: tuple[int, ...] = tuple(1 << (c >> 2) for c in range(52))
SUITED_BITS: dict[int, tuple[int, ...]] = {
    8 << 4 * s: tuple(RANK_BIT[c] if c & 3 == s else 0 for c in range(52)) for s in range(4)
}


@dataclass(frozen=True, eq=False)
class Tables:
    """Lookup tables for one rank list, suit count and ranking.

    ``rank``: ``n * COUNT + rank-key sum`` -> best unsuited five, n = 5..7.
    ``suited``: rank mask -> best suited five of those ranks, -1 under five.
    ``suited_above``: a suited five beats the same ranks unsuited."""

    rank: dict[int, int]
    suited: list[int]
    suited_above: bool


_TABLES: dict[tuple[Any, ...], Tables] = {}


def tables_for(spec: VariantSpec) -> Tables:
    """Tables for ``spec``, built on first use and shared by specs that
    differ only in streets, card use or betting."""
    key = (spec.ranks, min(len(spec.suits), 4), spec.ranking.order, spec.ranking.ace_low)
    t = _TABLES.get(key)
    if t is None:
        t = _TABLES[key] = _build(GenericEvaluator(spec), key[1])
    return t


def _build(ref: GenericEvaluator, cap: int) -> Tables:
    """Score every five-card rank multiset (unsuited, with suits 0, 1, 2, 3, 0)
    and every five-rank suit with ``ref.eval5``, then grow both by keeping the
    best value over each one-card-smaller subset. ``cap``: cards per rank."""
    ranks = sorted(RANKS.index(r) for r in ref.spec.ranks)
    steps = [(5 ** r, COUNT + RANK_KEYS[r]) for r in ranks]
    rank: dict[int, int] = {}
    level: dict[int, int] = {}
    for combo in combinations_with_replacement(ranks, 5):
        if any(combo[i] == combo[i + cap] for i in range(5 - cap)):
            continue
        key = sum(RANK_KEY[r * 4] for r in combo)
        level[key] = sum(5 ** r for r in combo)
        rank[key] = ref.eval5([r * 4 + i % 4 for i, r in enumerate(combo)])
    get = rank.get
    for _ in range(2):
        grown: dict[int, int] = {}
        for key, code in level.items():
            v = rank[key]
            for p, d in steps:
                if code // p % 5 < cap:
                    k = key + d
                    grown[k] = code + p
                    if v > get(k, -1):
                        rank[k] = v
        level = grown

    suited = [-1] * 8192
    for combo in combinations(ranks, 5):
        suited[sum(1 << r for r in combo)] = ref.eval5([r * 4 for r in combo])
    deck = sum(1 << r for r in ranks)
    for m in range(8192):
        if (m & ~deck) == 0 and m.bit_count() > 5:
            suited[m] = max(suited[m & ~(1 << r)] for r in ranks if m >> r & 1)

    s = {c: i for i, c in enumerate(ref.order)}
    above = s["straight_flush"] > s["straight"] and s["flush"] > s["high_card"]
    return Tables(rank, suited, above)


_ANY_SOURCE = """\
def evaluate(hole, board):
    try:
        [{h}] = hole
        [{b}] = board
    except ValueError:
        return other(hole, board)
    s = {total}
    if s & 0x8888:
{flush_return}
    return T[s >> 16]


def showdown(holes, board):
    try:
        [{b}] = board
    except ValueError:
        return [other(hole, board) for hole in holes]
    bs = {board_total}
    try:
        if not ((bs & 0xFFFF) + {hole_reach}) & 0x8888:
            return [T[(bs + {hole_total}) >> 16] for [{h}] in holes]
        out = []
        for [{h}] in holes:
            s = bs + {hole_total}
            if s & 0x8888:
{flush_append}
            else:
                out.append(T[s >> 16])
        return out
    except ValueError:
        return [evaluate(hole, board) for hole in holes]
"""

_SUITED_SOURCE = """\
F = SUITED_BITS[s & 0x8888]
f = FS[{mask}]
r = T[s >> 16]
"""


def _generate_any(ev: FastEvaluator, n_hole: int, n_board: int) -> tuple[Eval, Showdown]:
    """evaluate/showdown for "best five of any" of n_hole + n_board <= 7 cards,
    with the cards unpacked into locals; other sizes go to ``ev``'s dispatch."""
    hs = [f"h{i}" for i in range(n_hole)]
    bs = [f"b{i}" for i in range(n_board)]
    cards = hs + bs

    def keys(names: list[str], start: str = "") -> str:
        return " + ".join(([start] if start else []) + [f"K[{x}]" for x in names]) or "0"

    if ev.tables.suited_above:
        suited = _SUITED_SOURCE.format(mask=" + ".join(f"F[{x}]" for x in cards))
        flush_return = suited + "return f if f > r else r"
        flush_append = suited + "out.append(f if f > r else r)"
    else:
        flush_return = f"return fives(({', '.join(cards)},))"
        flush_append = f"out.append(fives(({', '.join(cards)},)))"
    source = _ANY_SOURCE.format(
        h=", ".join(hs), b=", ".join(bs),
        total=keys(cards, str(START)), board_total=keys(bs, str(START)),
        hole_total=keys(hs), hole_reach=n_hole * 0x1111,
        flush_return=_indent(flush_return, 8), flush_append=_indent(flush_append, 16),
    )
    env = {"K": KEY, "T": ev.tables.rank, "FS": ev.tables.suited, "SUITED_BITS": SUITED_BITS,
           "fives": ev.fives, "other": ev._dispatch}
    exec(compile(source, f"<fasteval any {n_hole}+{n_board}>", "exec"), env)
    return env["evaluate"], env["showdown"]


def _indent(text: str, n: int) -> str:
    return "\n".join(" " * n + line for line in text.strip().splitlines())


class FastEvaluator:
    """Table-driven evaluator for one spec, value-identical to GenericEvaluator.

    ``evaluate(hole, board)`` and ``showdown(holes, board)`` (one value per
    hole, aligned) are generated for the spec's hole and board sizes; other
    sizes are handled too. Cards must come from the spec's deck."""

    evaluate: Eval
    showdown: Showdown

    def __init__(self, spec: VariantSpec):
        self.spec = spec
        self.order = spec.ranking.order
        self.tables = tables_for(spec)
        self._rules: dict[tuple[int, int], tuple[Eval, Showdown]] = {}
        self.evaluate, self.showdown = self._rule(spec.hole_count, spec.board_count)

    def category(self, value: int) -> str:
        return self.order[value >> 20]

    def any5(self, cards: Sequence[int]) -> int:
        """Best five of any of ``cards`` (at least five)."""
        t = self.tables
        n = len(cards)
        if n <= 7:
            s = START
            for c in cards:
                s += KEY[c]
            if s & FLUSH:
                if not t.suited_above:
                    return self.fives(cards)
                bits = SUITED_BITS[s & FLUSH]
                f = t.suited[sum([bits[c] for c in cards])]
                r = t.rank[s >> 16]
                return f if f > r else r
            return t.rank[s >> 16]
        if not t.suited_above or n >= 12:
            return self.fives(cards)
        keys = [KEY[c] for c in cards]
        total = sum(keys, START)
        best = max([t.rank[(total - sum(d)) >> 16] for d in combinations(keys, n - 7)])
        masks = [0, 0, 0, 0]
        for c in cards:
            masks[c & 3] |= RANK_BIT[c]
        return max(best, *[t.suited[m] for m in masks])

    def fives(self, cards: Sequence[int]) -> int:
        """Best five of ``cards`` by enumeration, exact for every order."""
        return self.splits([], cards, (0,))

    def splits(self, hole: Sequence[int], board: Sequence[int], ks: Sequence[int]) -> int:
        """Best five using k hole cards and 5 - k board cards, k in ``ks``."""
        rank, suited = self.tables.rank, self.tables.suited
        best = -1
        for k in ks:
            hs = [(sum([KEY[c] for c in p]), sum([RANK_BIT[c] for c in p]))
                  for p in combinations(hole, k)]
            for q in combinations(board, 5 - k):
                qk = sum([KEY[c] for c in q], START)
                qm = sum([RANK_BIT[c] for c in q])
                for pk, pm in hs:
                    s = pk + qk
                    v = suited[pm | qm] if s & FLUSH else rank[s >> 16]
                    if v > best:
                        best = v
        if best < 0:
            raise ValueError("no legal five-card hand")
        return best

    def _dispatch(self, hole: Sequence[int], board: Sequence[int]) -> int:
        return self._rule(len(hole), len(board))[0](hole, board)

    def _rule(self, n_hole: int, n_board: int) -> tuple[Eval, Showdown]:
        rule = self._rules.get((n_hole, n_board))
        if rule is None:
            rule = self._rules[n_hole, n_board] = self._make_rule(n_hole, n_board)
        return rule

    def _make_rule(self, n_hole: int, n_board: int) -> tuple[Eval, Showdown]:
        ks = [k for k, _ in self.spec.hole_splits() if k <= n_hole and 5 - k <= n_board]
        lo, hi = max(0, 5 - n_board), min(5, n_hole)
        if not ks:
            return self._sized(n_hole, n_board, _identity, _no_hand)
        if (ks[0], ks[-1]) == (lo, hi):
            if n_hole + n_board <= 7:
                return _generate_any(self, n_hole, n_board)
            prepare, value = list, self._value_any
        elif ks[0] == ks[-1] and self.tables.suited_above:
            prepare, value = _Exactly(self.tables, ks[0]).pair()
        elif ks[0] == lo:
            prepare, value = list, self._value_at_most(ks[-1])
        elif ks[-1] == hi:
            prepare, value = self._prepare_at_least(ks[0]), self._value_at_least(ks)
        else:
            prepare, value = _identity, self._value_splits(ks)
        return self._sized(n_hole, n_board, prepare, value)

    def _value_any(self, board: list[int], hole: Sequence[int]) -> int:
        return self.any5([*hole, *board])

    def _value_at_most(self, k: int) -> Callable[[list[int], Sequence[int]], int]:
        def value(board: list[int], hole: Sequence[int]) -> int:
            return max([self.any5([*p, *board]) for p in combinations(hole, k)])
        return value

    def _prepare_at_least(self, k: int) -> Callable[[Sequence[int]], tuple[list[int], int]]:
        def prepare(board: Sequence[int]) -> tuple[list[int], int]:
            return list(board), (self.any5(board) if k == 1 else -1)
        return prepare

    def _value_at_least(self, ks: list[int]) -> Callable[[tuple[list[int], int], Sequence[int]], int]:
        fewer = self._value_at_most(ks[0] - 1)

        def value(ctx: tuple[list[int], int], hole: Sequence[int]) -> int:
            board, board_only = ctx
            v = self.any5([*hole, *board])
            if v > (board_only if ks[0] == 1 else fewer(board, hole)):
                return v
            return self.splits(hole, board, ks)
        return value

    def _value_splits(self, ks: list[int]) -> Callable[[Sequence[int], Sequence[int]], int]:
        def value(board: Sequence[int], hole: Sequence[int]) -> int:
            return self.splits(hole, board, ks)
        return value

    def _sized(self, n_hole: int, n_board: int, prepare: Callable[[Sequence[int]], Any],
               value: Callable[[Any, Sequence[int]], int]) -> tuple[Eval, Showdown]:
        """evaluate/showdown from a per-board ``prepare`` and a per-hole
        ``value``, for these sizes only; other sizes go to the dispatch."""
        other = self._dispatch

        def evaluate(hole: Sequence[int], board: Sequence[int]) -> int:
            if len(hole) != n_hole or len(board) != n_board:
                return other(hole, board)
            return value(prepare(board), hole)

        def showdown(holes: Sequence[Sequence[int]], board: Sequence[int]) -> list[int]:
            if len(board) != n_board or any(len(h) != n_hole for h in holes):
                return [other(h, board) for h in holes]
            ctx = prepare(board)
            return [value(ctx, h) for h in holes]
        return evaluate, showdown


_Board = tuple[dict[int, int], Sequence[int], list[tuple[tuple[int, ...], list[int]]]]


class _Exactly:
    """Exactly k hole cards and 5 - k board cards, for orders where a suited
    five beats the same ranks unsuited.

    The unsuited part comes from a row per board rank multiset, filled on
    demand: hole k-subset rank key -> best unsuited five. The suited part is
    only looked at for suits with 5 - k board cards."""

    def __init__(self, t: Tables, k: int):
        self.t = t
        self.k = k
        self.reach = (3 + k) * 0x1111
        self.rows: dict[Any, dict[int, int]] = {}

    def pair(self) -> tuple[Callable[[Sequence[int]], _Board], Callable[[_Board, Sequence[int]], int]]:
        return self.prepare, self.value

    def prepare(self, board: Sequence[int]) -> _Board:
        need = 5 - self.k
        s = sum([KEY[c] for c in board])
        small = len(board) <= 7
        bk = s >> 16 if small else tuple(sorted(c >> 2 for c in board))
        row = self.rows.get(bk)
        if row is None:
            row = self.rows[bk] = {}
        flags = ((s & 0xFFFF) + self.reach) & FLUSH if small else FLUSH
        flush = []
        if flags:
            for flag, bits in SUITED_BITS.items():
                if flags & flag:
                    mine = [b for b in map(bits.__getitem__, board) if b]
                    if len(mine) >= need:
                        flush.append((bits, list(map(sum, combinations(mine, need)))))
        return row, board, flush

    def value(self, ctx: _Board, hole: Sequence[int]) -> int:
        row, board, flush = ctx
        k = self.k
        pks = list(map(sum, combinations([RANK_KEY[c] for c in hole], k)))
        vals = list(map(row.get, pks))
        if None in vals:
            rank = self.t.rank
            qks = list(map(sum, combinations([RANK_KEY[c] for c in board], 5 - k)))
            for i, pk in enumerate(pks):
                if vals[i] is None:
                    vals[i] = row[pk] = max([rank[pk + q] for q in qks])
        best = max(vals)
        for bits, board_masks in flush:
            mine = [b for b in map(bits.__getitem__, hole) if b]
            if len(mine) >= k:
                suited = self.t.suited
                for pm in map(sum, combinations(mine, k)):
                    for qm in board_masks:
                        if suited[pm | qm] > best:
                            best = suited[pm | qm]
        return best


def _identity(board: Sequence[int]) -> Sequence[int]:
    return board


def _no_hand(ctx: Any, hole: Sequence[int]) -> int:
    raise ValueError("no legal five-card hand")
