"""Vectorized shortdeck evaluator. Card id = r*4 + s, r in 0..8 (6..A), s in 0..3.
Value = cat << 20 | tiebreak ranks (4 bits each). Cats: 0 high,1 pair,2 2pair,
3 trips,4 straight,5 full house,6 flush,7 quads,8 straight flush."""
import numpy as np
from itertools import combinations_with_replacement

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}

# straights over 9 ranks: top index t means ranks t-4..t; wheel A6789 top = 3 (9)
_STRAIGHTS = []
for t in range(8, 3, -1):
    _STRAIGHTS.append((sum(1 << r for r in range(t - 4, t + 1)), t))
_STRAIGHTS.append(((1 << 8) | 0b1111, 3))


def _straight_top(mask):
    for m, t in _STRAIGHTS:
        if mask & m == m:
            return t
    return -1


def _pack(cat, tb):
    v = cat
    for i in range(5):
        v = (v << 4) | (tb[i] if i < len(tb) else 0)
    return v


def _eval_counts(cnt):
    """Best non-flush value of rank count vector (len 9)."""
    ranks_desc = [r for r in range(8, -1, -1) if cnt[r] > 0]
    quads = [r for r in range(8, -1, -1) if cnt[r] >= 4]
    trips = [r for r in range(8, -1, -1) if cnt[r] >= 3]
    pairs = [r for r in range(8, -1, -1) if cnt[r] >= 2]
    mask = sum(1 << r for r in ranks_desc)
    n = sum(cnt)
    if quads:
        q = quads[0]
        k = [r for r in ranks_desc if r != q][:1]
        return _pack(7, [q] + k)
    if trips:
        t = trips[0]
        others = [r for r in pairs if r != t]
        if others:
            return _pack(5, [t, others[0]])
    st = _straight_top(mask)
    if st >= 0:
        return _pack(4, [st])
    if trips:
        t = trips[0]
        k = [r for r in ranks_desc if r != t][:2]
        return _pack(3, [t] + k)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        k = [r for r in ranks_desc if r != p1 and r != p2][:1]
        return _pack(2, [p1, p2] + k)
    if pairs:
        p = pairs[0]
        k = [r for r in ranks_desc if r != p][:3]
        return _pack(1, [p] + k)
    return _pack(0, ranks_desc[:5])


def build_tables():
    rank = np.zeros(5 ** 9, dtype=np.int32)
    for n in range(2, 8):
        for combo in combinations_with_replacement(range(9), n):
            cnt = [0] * 9
            for r in combo:
                cnt[r] += 1
            if max(cnt) > 4:
                continue
            code = sum(cnt[r] * 5 ** r for r in range(9))
            rank[code] = _eval_counts(cnt)
    flush = np.full(512, -1, dtype=np.int32)
    for m in range(512):
        if bin(m).count("1") >= 5:
            st = _straight_top(m)
            if st >= 0:
                flush[m] = _pack(8, [st])
            else:
                rd = [r for r in range(8, -1, -1) if m >> r & 1][:5]
                flush[m] = _pack(6, rd)
    return rank, flush


RANKTAB, FLUSHTAB = build_tables()
POW5 = np.array([5 ** (c >> 2) for c in range(36)], dtype=np.int64)
SKEY = np.array([1 << (4 * (c & 3)) for c in range(36)], dtype=np.int64)
SUIT = np.array([c & 3 for c in range(36)], dtype=np.int64)
RBIT = np.array([1 << (c >> 2) for c in range(36)], dtype=np.int64)


def eval_cards(cards):
    """cards: int array (N, k) with 5 <= k <= 7 -> values (N,)."""
    code = POW5[cards].sum(axis=1)
    v = RANKTAB[code]
    sk = SKEY[cards].sum(axis=1) + 0x3333
    fl = sk & 0x8888
    rows = np.nonzero(fl)[0]
    if rows.size:
        f = fl[rows]
        fs = (f > 0x8).astype(np.int64) + (f > 0x80) + (f > 0x800)
        sub = cards[rows]
        m = (RBIT[sub] * (SUIT[sub] == fs[:, None])).sum(axis=1)
        fv = FLUSHTAB[m]
        v[rows] = np.maximum(v[rows], fv)
    return v


def eval_partial(code_base, sk_base, cards):
    """Evaluate with precomputed sums for fixed cards. cards (N,k) extra."""
    code = code_base + POW5[cards].sum(axis=1)
    v = RANKTAB[code]
    return v
