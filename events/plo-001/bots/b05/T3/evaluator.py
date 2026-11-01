"""Vectorised Omaha hand evaluation (exactly 2 hole + 3 board) with numpy.

Values: category << 20 | tiebreak nibbles; higher wins. Standard ranking.
"""
from itertools import combinations, combinations_with_replacement

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)

HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, SFLUSH = range(9)


def _straight_top(distinct_desc):
    if len(distinct_desc) != 5:
        return -1
    if distinct_desc[0] - distinct_desc[4] == 4:
        return distinct_desc[0]
    if distinct_desc == [12, 3, 2, 1, 0]:
        return 3
    return -1


def _eval_ranks(rs):
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(cnt.items(), key=lambda x: (-x[1], -x[0]))
    distinct = sorted(cnt, reverse=True)
    if len(distinct) == 5:
        t = _straight_top(distinct)
        if t >= 0:
            return STRAIGHT << 20 | t << 16
        v = 0
        for r in distinct:
            v = v << 4 | r
        return HIGH << 20 | v
    c0, r0 = groups[0][1], groups[0][0]
    if c0 == 4:
        return QUADS << 20 | r0 << 16 | groups[1][0] << 12
    if c0 == 3:
        if groups[1][1] == 2:
            return FULL_HOUSE << 20 | r0 << 16 | groups[1][0] << 12
        ks = sorted([g[0] for g in groups[1:]], reverse=True)
        return TRIPS << 20 | r0 << 16 | ks[0] << 12 | ks[1] << 8
    if c0 == 2:
        if groups[1][1] == 2:
            p1, p2 = groups[0][0], groups[1][0]
            return TWO_PAIR << 20 | p1 << 16 | p2 << 12 | groups[2][0] << 8
        ks = sorted([g[0] for g in groups[1:]], reverse=True)
        return PAIR << 20 | r0 << 16 | ks[0] << 12 | ks[1] << 8 | ks[2] << 4
    raise ValueError


def _build():
    maxkey = 4 * RANK_KEYS[12] + RANK_KEYS[11] + 1
    uns = np.zeros(maxkey, dtype=np.int32)
    for combo in combinations_with_replacement(range(13), 5):
        if any(combo[i] == combo[i + 4] for i in range(1)):
            continue
        k = sum(RANK_KEYS[r] for r in combo)
        uns[k] = _eval_ranks(list(combo))
    suited = np.zeros(8192, dtype=np.int32)
    for combo in combinations(range(13), 5):
        m = sum(1 << r for r in combo)
        d = sorted(combo, reverse=True)
        t = _straight_top(d)
        if t >= 0:
            suited[m] = SFLUSH << 20 | t << 16
        else:
            v = 0
            for r in d:
                v = v << 4 | r
            suited[m] = FLUSH << 20 | v
    return uns, suited


UNS, SUITED = _build()
KEYC = np.array([RANK_KEYS[c >> 2] for c in range(52)], dtype=np.int64)
SUITC = np.array([c & 3 for c in range(52)], dtype=np.int64)
RBIT = np.array([1 << (c >> 2) for c in range(52)], dtype=np.int64)
KEYC_L = [RANK_KEYS[c >> 2] for c in range(52)]

# pair index tables for n unseen cards
_PAIRS = {}
for _n in range(30, 50):
    a, b = np.triu_indices(_n, 1)
    _PAIRS[_n] = (a.astype(np.int64), b.astype(np.int64))

HOLE_PAIRS = list(combinations(range(4), 2))


def triples(board):
    """(keys, masks, suit-or--1) arrays for every 3-card subset of board."""
    ts = list(combinations(board, 3))
    tk = np.array([KEYC_L[a] + KEYC_L[b] + KEYC_L[c] for a, b, c in ts], dtype=np.int64)
    tm = np.array([(1 << (a >> 2)) | (1 << (b >> 2)) | (1 << (c >> 2)) for a, b, c in ts], dtype=np.int64)
    tsu = [a & 3 if (a & 3) == (b & 3) == (c & 3) else -1 for a, b, c in ts]
    return tk, tm, tsu


def pair_values(P1, P2, tk, tm, tsu):
    """Best value per 2-card pair (P1[i], P2[i]) over all board triples."""
    k = KEYC[P1] + KEYC[P2]
    vals = UNS[k[None, :] + tk[:, None]]
    same = None
    for t, s in enumerate(tsu):
        if s < 0:
            continue
        if same is None:
            s1 = SUITC[P1]
            same = s1 == SUITC[P2]
        m = same & (s1 == s)
        if m.any():
            idx = np.nonzero(m)[0]
            vals[t, idx] = SUITED[RBIT[P1[idx]] | RBIT[P2[idx]] | tm[t]]
    return vals.max(axis=0)


def hand_value(hole, tri):
    tk, tm, tsu = tri
    P1 = np.array([hole[i] for i, _ in HOLE_PAIRS], dtype=np.int64)
    P2 = np.array([hole[j] for _, j in HOLE_PAIRS], dtype=np.int64)
    return int(pair_values(P1, P2, tk, tm, tsu).max())


def board_strength(hole, board):
    """Return (my value, frac of opp 2-card combos beating me, frac tying, unseen array, tri)."""
    tri = triples(board)
    mine = hand_value(hole, tri)
    used = set(hole) | set(board)
    unseen = np.array([c for c in range(52) if c not in used], dtype=np.int64)
    a, b = _PAIRS[len(unseen)]
    opp = pair_values(unseen[a], unseen[b], *tri)
    n = len(opp)
    beat = np.count_nonzero(opp > mine) / n
    tie = np.count_nonzero(opp == mine) / n
    return mine, beat, tie, unseen, tri


def improve_outs(hole, board, unseen):
    """Values of our best hand for each possible next card: (cards, values)."""
    res = []
    hp1 = np.array([hole[i] for i, _ in HOLE_PAIRS], dtype=np.int64)
    hp2 = np.array([hole[j] for _, j in HOLE_PAIRS], dtype=np.int64)
    # triples that include the new card: pairs of board + x
    bpairs = list(combinations(board, 2))
    bk = np.array([KEYC_L[a] + KEYC_L[b] for a, b in bpairs], dtype=np.int64)
    bm = np.array([(1 << (a >> 2)) | (1 << (b >> 2)) for a, b in bpairs], dtype=np.int64)
    bs = np.array([a & 3 if (a & 3) == (b & 3) else -1 for a, b in bpairs], dtype=np.int64)
    X = unseen
    # keys: (X, bpairs) -> triple key
    tk = KEYC[X][:, None] + bk[None, :]  # (nx, nb)
    hk = KEYC[hp1] + KEYC[hp2]  # (6,)
    vals = UNS[tk[:, :, None] + hk[None, None, :]]  # (nx, nb, 6)
    # flushes: triple suited (bs == suit of x) and hole pair suited same
    hs_same = (SUITC[hp1] == SUITC[hp2])
    if hs_same.any():
        xs = SUITC[X]
        trip_suited = (bs[None, :] == xs[:, None])  # (nx, nb)
        hsu = np.where(hs_same, SUITC[hp1], -9)
        fl = trip_suited[:, :, None] & (hsu[None, None, :] == xs[:, None, None])
        if fl.any():
            ii, jj, kk = np.nonzero(fl)
            m = RBIT[X[ii]] | bm[jj] | RBIT[hp1[kk]] | RBIT[hp2[kk]]
            vals[ii, jj, kk] = SUITED[m]
    return vals.reshape(len(X), -1).max(axis=1)
