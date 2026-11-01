"""Fast PLO evaluation: 5-card tables (python dict + dense numpy) built at import."""
from itertools import combinations, combinations_with_replacement

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)

RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
RKEY = tuple(RANK_KEYS[c >> 2] for c in range(52))
RBIT = tuple(1 << (c >> 2) for c in range(52))
SUIT = tuple(c & 3 for c in range(52))

# category order (engine): high_card, pair, two_pair, trips, straight, flush, full_house, quads, straight_flush
HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)


def _straight_top(mask):
    # top rank of straight in 5 distinct ranks mask, or -1
    for top in range(12, 3, -1):
        m = 0x1F << (top - 4)
        if mask == m:
            return top
    if mask == (1 << 12) | 0xF:
        return 3
    return -1


def _eval5(ranks, flush):
    """ranks: list of 5 rank ints. Returns engine-compatible value."""
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    mask = 0
    for r in ranks:
        mask |= 1 << r
    groups = sorted(cnt.items(), key=lambda t: (-t[1], -t[0]))
    if len(cnt) == 5:
        st = _straight_top(mask)
        srt = sorted(ranks, reverse=True)
        if flush:
            if st >= 0:
                return pack(STRAIGHT_FLUSH, [st])
            return pack(FLUSH, srt)
        if st >= 0:
            return pack(STRAIGHT, [st])
        return pack(HIGH, srt)
    c0 = groups[0][1]
    if c0 == 4:
        return pack(QUADS, [groups[0][0], groups[1][0]])
    if c0 == 3:
        if groups[1][1] == 2:
            return pack(FULL_HOUSE, [groups[0][0], groups[1][0]])
        return pack(TRIPS, [groups[0][0], groups[1][0], groups[2][0]])
    if c0 == 2:
        if groups[1][1] == 2:
            return pack(TWO_PAIR, [groups[0][0], groups[1][0], groups[2][0]])
        return pack(PAIR, [groups[0][0], groups[1][0], groups[2][0], groups[3][0]])
    raise ValueError


def pack(cat, tb):
    v = cat
    for i in range(5):
        v = (v << 4) | (tb[i] if i < len(tb) else 0)
    return v


RK5 = {}
for combo in combinations_with_replacement(range(13), 5):
    if any(combo[i] == combo[i + 4] for i in range(1)):
        continue
    RK5[sum(RANK_KEYS[r] for r in combo)] = _eval5(list(combo), False)
FL5 = [0] * 8192
for combo in combinations(range(13), 5):
    FL5[sum(1 << r for r in combo)] = _eval5(list(combo), True)

_maxkey = max(RK5)
RK5_NP = np.zeros(5 * RANK_KEYS[12] + 1, dtype=np.int32)
_ks = np.fromiter(RK5.keys(), dtype=np.int64)
_vs = np.fromiter(RK5.values(), dtype=np.int64)
RK5_NP[_ks] = _vs
FL5_NP = np.array(FL5, dtype=np.int32)

# all 1326 two-card pairs
_pairs = list(combinations(range(52), 2))
P1 = np.array([a for a, b in _pairs], dtype=np.int64)
P2 = np.array([b for a, b in _pairs], dtype=np.int64)
RKEY_NP = np.array(RKEY, dtype=np.int64)
RBIT_NP = np.array(RBIT, dtype=np.int64)
PAIR_RK = RKEY_NP[P1] + RKEY_NP[P2]
PAIR_MASK = RBIT_NP[P1] | RBIT_NP[P2]
SUIT_PAIRS = [np.nonzero((P1 & 3 == s) & (P2 & 3 == s))[0] for s in range(4)]
SUIT_PAIR_MASK = [PAIR_MASK[ix] for ix in SUIT_PAIRS]


def omaha_value(hole, board):
    """Best value using exactly 2 hole + 3 board cards (board has 3..5 cards)."""
    best = 0
    trip = []
    for x, y, z in combinations(board, 3):
        s = SUIT[x]
        fs = s if (SUIT[y] == s and SUIT[z] == s) else -1
        trip.append((RKEY[x] + RKEY[y] + RKEY[z], fs, RBIT[x] | RBIT[y] | RBIT[z]))
    for a, b in combinations(hole, 2):
        ka = RKEY[a] + RKEY[b]
        sa = SUIT[a] if SUIT[a] == SUIT[b] else -2
        for tk, fs, tm in trip:
            v = RK5[ka + tk]
            if fs == sa:
                f = FL5[RBIT[a] | RBIT[b] | tm]
                if f > v:
                    v = f
            if v > best:
                best = v
    return best


def opp_pair_values(board, dead):
    """Best value for each of the 1326 two-card holdings on this board, plus a
    validity mask (no dead cards)."""
    trips = list(combinations(board, 3))
    tk = np.array([RKEY[x] + RKEY[y] + RKEY[z] for x, y, z in trips], dtype=np.int64)
    vals = RK5_NP[tk[:, None] + PAIR_RK[None, :]]
    for i, (x, y, z) in enumerate(trips):
        s = SUIT[x]
        if SUIT[y] == s and SUIT[z] == s:
            ix = SUIT_PAIRS[s]
            fv = FL5_NP[SUIT_PAIR_MASK[s] | (RBIT[x] | RBIT[y] | RBIT[z])]
            vals[i, ix] = np.maximum(vals[i, ix], fv)
    best = vals.max(axis=0)
    d = np.zeros(52, dtype=bool)
    d[list(dead)] = True
    valid = ~(d[P1] | d[P2])
    return best, valid


def next_card_values(hole, board, cands, base=0):
    """Best value on board+[c] for each candidate card c (numpy array of ints)."""
    hp = list(combinations(hole, 2))
    bp = list(combinations(board, 2))
    ck = np.array([RKEY[a] + RKEY[b] + RKEY[x] + RKEY[y] for a, b in hp for x, y in bp], dtype=np.int64)
    vals = RK5_NP[ck[:, None] + RKEY_NP[cands][None, :]]
    best = vals.max(axis=0)
    csuit = cands & 3
    for a, b in hp:
        s = SUIT[a]
        if SUIT[b] != s:
            continue
        for x, y in bp:
            if SUIT[x] == s and SUIT[y] == s:
                sel = np.nonzero(csuit == s)[0]
                if sel.size:
                    m = RBIT[a] | RBIT[b] | RBIT[x] | RBIT[y]
                    fv = FL5_NP[m | RBIT_NP[cands[sel]]]
                    best[sel] = np.maximum(best[sel], fv)
    return np.maximum(best, base)
