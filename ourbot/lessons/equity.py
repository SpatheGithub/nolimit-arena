"""Monte Carlo equity against ranges, for any deck and hand ranking, in numpy.

Built once per variant and process (about 0.5 s for a 52-card deck):
- the best unsuited value of every rank multiset of five to seven cards, found
  with np.searchsorted over base-5 keys;
- the best suited value of every rank mask with five or more ranks.

A hand's value is the larger of its two lookups. That equals Variant.best for
"best five of any" whenever a suited five outranks the same ranks unsuited,
which holds for every ranking the variants use.

Ranges are the top share of two-card combos by preflop percentile, optionally
narrowed to the combos with the best made hands on the current board. A sample
deals each opponent a combo from its range and completes the board; samples
with clashing cards are dropped, which leaves the joint distribution exact.
Equity serves the hold'em family (two hole cards at showdown; with three,
as in crazy pineapple before its discard, hero keeps the best pair).
OmahaEquity serves "exactly k hole cards" variants such as PLO, with ranges
from a bank of random hands sorted by plo_strength.
"""

import random
from itertools import combinations

import numpy as np

from ._common import plo_strength, preflop_pct

_CACHE: dict[tuple, object] = {}


def for_variant(var):
    """The variant's Equity or OmahaEquity, built on first use; None when neither fits it."""
    key = (var.ranks, tuple(var.deck), var.board_count, var.hole_count, var.use_lo, var.use_hi,
           tuple(var.ranker.shift))
    if key not in _CACHE:
        if var.family == "holdem" and 5 <= 2 + var.board_count <= 7:
            _CACHE[key] = Equity(var)
        elif var.family == "omaha" and var.use_lo == var.use_hi and var.use_lo in (2, 3) \
                and 5 - var.use_lo <= var.board_count and var.use_lo <= var.hole_count <= 6:
            _CACHE[key] = OmahaEquity(var)
        else:
            _CACHE[key] = None
    return _CACHE[key]


def multiset_table(var, sizes) -> tuple[np.ndarray, np.ndarray]:
    """(sorted base-5 keys, best unsuited values) of every rank multiset of the given sizes."""
    value = var.ranker.value
    suits = sorted({c & 3 for c in var.deck})
    ranks = sorted({c >> 2 for c in var.deck})
    top = min(4, len(suits))
    keys, vals = [], []
    for size in sizes:
        counts = [0] * len(ranks)

        def rec(i: int, left: int) -> None:
            if i == len(ranks):
                if left == 0:
                    cards, g = [], 0
                    for r, n in zip(ranks, counts):
                        for _ in range(n):
                            cards.append(4 * r + suits[g % len(suits)])
                            g += 1
                    keys.append(sum(n * 5 ** r for r, n in zip(ranks, counts)))
                    vals.append(value(cards))
                return
            for n in range(min(top, left) + 1):
                counts[i] = n
                rec(i + 1, left - n)
            counts[i] = 0

        rec(0, size)
    order = np.argsort(np.array(keys, dtype=np.int64))
    return np.array(keys, dtype=np.int64)[order], np.array(vals, dtype=np.int64)[order]


def flush_table(var, max_len: int) -> np.ndarray:
    """Best suited value by 13-bit rank mask, for masks of 5 to ``max_len`` ranks (0 elsewhere)."""
    value = var.ranker.value
    suits = sorted({c & 3 for c in var.deck})
    ranks = sorted({c >> 2 for c in var.deck})
    out = np.zeros(8192, dtype=np.int64)
    for k in range(5, min(max_len, len(ranks)) + 1):
        for rs in combinations(ranks, k):
            out[sum(1 << r for r in rs)] = value([4 * r + suits[0] for r in rs])
    return out


class Equity:
    def __init__(self, var):
        self.var = var
        deck = self.deck = list(var.deck)
        ranks = sorted({c >> 2 for c in deck})
        self.board_count = var.board_count
        self.p5 = np.array([5 ** (c >> 2) for c in range(52)], dtype=np.int64)
        self.bit = np.array([1 << (c >> 2) for c in range(52)], dtype=np.int64)
        self.suit = np.array([c & 3 for c in range(52)], dtype=np.int64)
        self.skey = np.array([1 << 4 * (c & 3) for c in range(52)], dtype=np.int64)  # a 4-bit count per suit
        self.keys, self.vals = multiset_table(var, range(5, 2 + var.board_count + 1))
        self.last = len(self.keys) - 1
        self.can_flush = len(ranks) >= 5
        self.flush = flush_table(var, 7)
        combos = list(combinations(deck, 2))
        self.A = np.array([a for a, _ in combos], dtype=np.int64)
        self.B = np.array([b for _, b in combos], dtype=np.int64)
        pct = np.array([preflop_pct(var, [a, b]) for a, b in combos])
        self.by_pct = np.argsort(pct, kind="stable")
        self.pct_sorted = pct[self.by_pct]
        self.has = np.zeros((52, len(combos)), dtype=bool)
        idx = np.arange(len(combos))
        self.has[self.A, idx] = True
        self.has[self.B, idx] = True
        self._cur: tuple = ((), None)
        # Warm up: numpy's first calls of each kind are slow, and would land in a timed decision.
        rng = np.random.default_rng(0)
        hero, board = deck[:3], deck[3:3 + min(3, var.board_count)]
        rg = self.range_idx(0.5, self.dead_mask(hero + board), board, keep=0.5)
        self.shares(hero, board, [rg, rg], rng, 40)
        self._cur = ((), None)

    # hand values

    def values(self, cards: np.ndarray) -> np.ndarray:
        """Best value of each row of distinct card ids (5 to 7 cards per row)."""
        v = self.vals[np.minimum(np.searchsorted(self.keys, self.p5[cards].sum(axis=1)), self.last)]
        if self.can_flush:
            fl = (self.skey[cards].sum(axis=1) + 0x3333) & 0x8888  # a suit's bit is set at 5+ cards
            rows = np.flatnonzero(fl)
            if rows.size:
                f = fl[rows]
                su = np.where(f & 0x8, 0, np.where(f & 0x80, 1, np.where(f & 0x800, 2, 3)))
                sub = cards[rows]
                m = np.where(self.suit[sub] == su[:, None], self.bit[sub], 0).sum(axis=1)
                v[rows] = np.maximum(v[rows], self.flush[m])
        return v

    def current(self, board: list[int]) -> np.ndarray:
        """Made-hand value of every combo on this board (-1 if it holds a board card), cached."""
        key = tuple(board)
        if self._cur[0] != key:
            live = np.flatnonzero(~self.has[list(board)].any(axis=0))
            cards = np.empty((len(live), 2 + len(board)), dtype=np.int64)
            cards[:, 0], cards[:, 1] = self.A[live], self.B[live]
            cards[:, 2:] = board
            cur = np.full(len(self.A), -1, dtype=np.int64)
            cur[live] = self.values(cards)
            self._cur = (key, cur)
        return self._cur[1]

    # ranges

    def dead_mask(self, dead) -> np.ndarray:
        """Which combos hold any of these cards."""
        return self.has[list(dead)].any(axis=0)

    def range_idx(self, q: float, dead: np.ndarray | None = None, board: list[int] | None = None,
                  keep: float = 1.0, rng=None, budget: int = 0, min_combos: int = 6) -> np.ndarray:
        """Combo indices of the top q by preflop percentile, minus combos in the ``dead`` mask, then
        the top ``keep`` of those by made hand on ``board`` (ties kept)."""
        m = int(np.searchsorted(self.pct_sorted, q, side="right"))
        idx = self.by_pct[:max(m, min_combos)]
        if dead is not None:
            idx = idx[~dead[idx]]
        if keep < 1.0 and board and len(idx) > min_combos:
            cur = self.current(board)[idx]
            j = min(len(idx) - min_combos, int((1.0 - keep) * len(idx)))
            idx = idx[cur >= np.partition(cur, j)[j]]
        if not len(idx):
            idx = self.by_pct if dead is None else self.by_pct[~dead[self.by_pct]]
        return idx

    # equity

    def equity(self, hero: list[int], board: list[int], ranges: list[np.ndarray], rng, n: int = 200) -> float:
        """Hero's share of the pot at showdown against one hand from each range (the best
        pair's, with more than two hole cards)."""
        return max(share for _, share in self.shares(hero, board, ranges, rng, n))

    def shares(self, hero: list[int], board: list[int], ranges: list[np.ndarray], rng,
               n: int = 200) -> list[tuple[tuple[int, int], float]]:
        """(pair, share of the pot) for each pair of hero's hole cards, from the same samples.
        The ranges must exclude hero's and the board's cards."""
        dead = set(hero) | set(board)
        left = self.board_count - len(board)
        k = len(ranges)
        pairs = list(combinations(hero, 2))
        parts = []
        for idx in ranges:
            pick = idx[rng.integers(0, len(idx), n)]
            parts.append(self.A[pick])
            parts.append(self.B[pick])
        if left:
            rem = np.array([c for c in self.deck if c not in dead], dtype=np.int64)
            parts.extend(rem[rng.integers(0, len(rem), (left, n))])
        dealt = np.stack(parts, axis=1)
        if dealt.shape[1] > 1:
            srt = np.sort(dealt, axis=1)
            dealt = dealt[(srt[:, 1:] != srt[:, :-1]).all(axis=1)]
        rows = len(dealt)
        if rows == 0:
            return [(pair, 0.5) for pair in pairs]
        bc = self.board_count
        full = np.empty((rows, bc), dtype=np.int64)
        full[:, :len(board)] = board
        full[:, len(board):] = dealt[:, 2 * k:]
        hands = np.empty(((k + len(pairs)) * rows, 2 + bc), dtype=np.int64)
        hands[:, 2:] = np.tile(full, (k + len(pairs), 1))
        hands[:k * rows, 0] = dealt[:, 0:2 * k:2].T.ravel()
        hands[:k * rows, 1] = dealt[:, 1:2 * k:2].T.ravel()
        hands[k * rows:, 0] = np.repeat([a for a, _ in pairs], rows)
        hands[k * rows:, 1] = np.repeat([b for _, b in pairs], rows)
        v = self.values(hands).reshape(k + len(pairs), rows)
        best_opp = v[:k].max(axis=0)
        return [(pair, float(((v[k + i] > best_opp) + 0.5 * (v[k + i] == best_opp)).mean()))
                for i, pair in enumerate(pairs)]


class OmahaEquity:
    """Monte Carlo equity when a hand uses exactly k hole cards and 5 - k board cards (PLO: 2 of
    4 and 3 of 5; k is 2 or 3). Unsuited values come from one table indexed by the hole part's and
    the board part's rank multisets. Opponents' ranges are the top share of a fixed bank of random
    hands, sorted by plo_strength, minus hands holding dead cards, optionally narrowed to a sample
    of the best made hands on the current board."""

    BANK = 20000

    def __init__(self, var):
        value = var.ranker.value
        self.var = var
        deck = self.deck = list(var.deck)
        suits = sorted({c & 3 for c in deck})
        self.board_count = var.board_count
        self.k = k = var.use_lo
        self.n_hole = var.hole_count
        self.bit = np.array([1 << (c >> 2) for c in range(52)], dtype=np.int64)
        self.suit = np.array([c & 3 for c in range(52)], dtype=np.int64)
        self.flush = flush_table(var, 5)
        ranks = sorted({c >> 2 for c in deck})
        cls = {}
        for m in (k, 5 - k):
            ms = sorted({tuple(sorted(t)) for t in combinations([r for r in ranks for _ in range(min(4, len(suits)))],
                                                                 m)})
            index = {t: i for i, t in enumerate(ms)}
            grid = np.stack(np.meshgrid(*[np.arange(52) >> 2] * m, indexing="ij"), axis=-1).reshape(-1, m)
            grid = np.sort(grid, axis=1)
            cls[m] = (ms, np.array([index.get(tuple(row), 0) for row in grid.tolist()],
                                   dtype=np.int64).reshape((52,) * m))
        (hms, self.hcls), (bms, self.bcls) = cls[k], cls[5 - k]
        table = np.zeros((len(hms), len(bms)), dtype=np.int64)
        for i, h in enumerate(hms):
            for j, b in enumerate(bms):
                rs = h + b
                if max(rs.count(r) for r in rs) <= min(4, len(suits)):
                    table[i, j] = value([4 * r + suits[g % len(suits)] for g, r in enumerate(sorted(rs))])
        self.nb_cls = table.shape[1]
        self.table = table.ravel()
        self.skey = np.array([1 << 4 * (c & 3) for c in range(52)], dtype=np.int64)  # a 4-bit count per suit
        self.hole_flush = 8 - k        # + a suit's count sets its nibble's top bit at k or more hole cards
        self.board_flush = 3 + k       # ... and at 5 - k or more board cards
        self.PI = np.array(list(combinations(range(self.n_hole), k)), dtype=np.int64)
        self.TI = {nb: np.array(list(combinations(range(nb), 5 - k)), dtype=np.int64)
                   for nb in range(5 - k, var.board_count + 1)}
        rng = random.Random(20261103)
        hands = [rng.sample(deck, self.n_hole) for _ in range(self.BANK)]
        score = [plo_strength(h) for h in hands]
        order = sorted(range(self.BANK), key=lambda i: -score[i])
        self.bank = np.array([hands[i] for i in order], dtype=np.int64)
        self.has = np.zeros((52, self.BANK), dtype=bool)
        for col in range(self.n_hole):
            self.has[self.bank[:, col], np.arange(self.BANK)] = True
        warm = np.random.default_rng(0)
        hero, board = deck[:self.n_hole], deck[self.n_hole:self.n_hole + min(3, var.board_count)]
        rg = self.range_idx(0.5, hero + board, board, keep=0.5, rng=warm)
        self.equity(hero, board, [rg, rg], warm, 30)

    def values(self, hole: np.ndarray, board: np.ndarray) -> np.ndarray:
        """Best value of each row: hole (R, n_hole) and board (R, nb) card ids."""
        hp = hole[:, self.PI]                                    # (R, P, k)
        tb = board[:, self.TI[board.shape[1]]]                   # (R, T, 5 - k)
        hc = self.hcls[tuple(hp[:, :, j] for j in range(hp.shape[2]))]
        bc = self.bcls[tuple(tb[:, :, j] for j in range(tb.shape[2]))]
        v = self.table.take(hc[:, :, None] * self.nb_cls + bc[:, None, :])
        nib = 0x1111
        hcnt = (self.skey[hole].sum(axis=1) + self.hole_flush * nib) & 0x8888
        bcnt = (self.skey[board].sum(axis=1) + self.board_flush * nib) & 0x8888
        rows = np.flatnonzero(hcnt & bcnt)                       # some suit has enough of both
        if rows.size:
            hs, bs = self.suit[hp[rows]], self.suit[tb[rows]]
            hsuit = np.where((hs == hs[:, :, :1]).all(axis=2), hs[:, :, 0], -1)
            bsuit = np.where((bs == bs[:, :, :1]).all(axis=2), bs[:, :, 0], -2)
            ri, pi, ti = np.nonzero(hsuit[:, :, None] == bsuit[:, None, :])
            ri = rows[ri]
            f = self.flush[self.bit[hp[ri, pi]].sum(axis=1) + self.bit[tb[ri, ti]].sum(axis=1)]
            v[ri, pi, ti] = np.maximum(v[ri, pi, ti], f)
        return v.reshape(len(hole), -1).max(axis=1)

    def dead_mask(self, dead) -> list[int]:
        """The dead cards, as range_idx takes them here."""
        return list(dead)

    def range_idx(self, q: float, dead: list[int], board: list[int] | None = None, keep: float = 1.0, rng=None,
                  budget: int = 2000, min_hands: int = 30) -> np.ndarray:
        """Bank rows in the top q without the ``dead`` cards; with keep < 1, a sample of them
        narrowed to the top ``keep`` by made hand on ``board``, evaluating about ``budget``
        five-card hands."""
        m = max(min_hands, int(q * self.BANK))
        idx = np.flatnonzero(~self.has[list(dead)][:, :m].any(axis=0))
        if keep < 1.0 and board and len(board) >= 5 - self.k and len(idx) > min_hands:
            cap = max(40, budget // (len(self.PI) * len(self.TI[len(board)])))
            if len(idx) > cap:
                idx = idx[rng.choice(len(idx), cap, replace=False)] if rng is not None else idx[:cap]
            cur = self.values(self.bank[idx], np.broadcast_to(np.array(board, dtype=np.int64),
                                                              (len(idx), len(board))))
            j = min(len(idx) - min(min_hands, len(idx) // 2), int((1.0 - keep) * len(idx)))
            idx = idx[cur >= np.partition(cur, j)[j]]
        if not len(idx):
            idx = np.flatnonzero(~self.has[list(dead)].any(axis=0))
        return idx

    def equity(self, hero: list[int], board: list[int], ranges: list[np.ndarray], rng, n: int = 100) -> float:
        """Hero's share of the pot at showdown against one hand from each range."""
        dead = set(hero) | set(board)
        left = self.board_count - len(board)
        k = len(ranges)
        parts = [self.bank[idx[rng.integers(0, len(idx), n)]] for idx in ranges]
        if left:
            rem = np.array([c for c in self.deck if c not in dead], dtype=np.int64)
            parts.append(rem[rng.integers(0, len(rem), (n, left))])
        dealt = np.concatenate(parts, axis=1)
        srt = np.sort(dealt, axis=1)
        dealt = dealt[(srt[:, 1:] != srt[:, :-1]).all(axis=1)]
        rows = len(dealt)
        if rows == 0:
            return 0.5
        h = self.n_hole
        full = np.empty((rows, self.board_count), dtype=np.int64)
        full[:, :len(board)] = board
        full[:, len(board):] = dealt[:, k * h:]
        holes = np.empty(((k + 1) * rows, h), dtype=np.int64)
        holes[:rows] = hero
        for i in range(k):
            holes[(i + 1) * rows:(i + 2) * rows] = dealt[:, i * h:(i + 1) * h]
        v = self.values(holes, np.tile(full, (k + 1, 1))).reshape(k + 1, rows)
        best = v[1:].max(axis=0)
        return float(((v[0] > best) + 0.5 * (v[0] == best)).mean())
