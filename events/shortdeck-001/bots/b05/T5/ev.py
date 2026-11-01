"""Shortdeck hand evaluator (36 cards, ranks 6..A, flush > full house,
A-6-7-8-9 straight). Values: cat << 20 | tiebreak ranks, higher wins.
Rank indices here are 0..8 (6..A). Only relative comparison matters."""

import numpy as np

RANKS = "6789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NR = 9
P5 = [5 ** r for r in range(NR)]
KEY = [P5[c >> 2] << 16 | 1 << 4 * (c & 3) for c in range(36)]
START = 0x3333

# categories (shortdeck order)
HIGH, PAIR, TWOP, TRIPS, STRAIGHT, FULL, FLUSH, QUADS, SFLUSH = range(9)


def _pack(cat, tb):
    v = cat
    for i in range(5):
        v = (v << 4) | (tb[i] if i < len(tb) else 0)
    return v


def _straight_top(mask):
    for top in range(8, 3, -1):
        m = 0x1F << (top - 4)
        if mask & m == m:
            return top
    # wheel A-6-7-8-9: ranks 8,0,1,2,3
    w = (1 << 8) | 0xF
    if mask & w == w:
        return 3
    return -1


def _nonflush(counts):
    ranks_desc = [r for r in range(NR - 1, -1, -1) if counts[r]]
    quads = [r for r in ranks_desc if counts[r] == 4]
    trips = [r for r in ranks_desc if counts[r] == 3]
    pairs = [r for r in ranks_desc if counts[r] == 2]
    best = _pack(HIGH, ranks_desc[:5])
    if quads:
        q = quads[0]
        k = [r for r in ranks_desc if r != q][:1]
        best = max(best, _pack(QUADS, [q] + k))
    if trips:
        t = trips[0]
        rest = [r for r in ranks_desc if r != t and counts[r] >= 2]
        if rest:
            best = max(best, _pack(FULL, [t, rest[0]]))
        k = [r for r in ranks_desc if r != t][:2]
        best = max(best, _pack(TRIPS, [t] + k))
    mask = 0
    for r in ranks_desc:
        mask |= 1 << r
    st = _straight_top(mask)
    if st >= 0:
        best = max(best, _pack(STRAIGHT, [st]))
    allp = sorted([r for r in ranks_desc if counts[r] >= 2], reverse=True)
    if len(allp) >= 2:
        p1, p2 = allp[0], allp[1]
        k = [r for r in ranks_desc if r != p1 and r != p2][:1]
        best = max(best, _pack(TWOP, [p1, p2] + k))
    if allp:
        p = allp[0]
        k = [r for r in ranks_desc if r != p][:3]
        best = max(best, _pack(PAIR, [p] + k))
    return best


def _build():
    T = {}
    T_np = np.zeros(5 ** NR, dtype=np.int32)

    def rec(r, counts, n):
        if r == NR:
            if 2 <= n <= 7:
                key = sum(counts[i] * P5[i] for i in range(NR))
                v = _nonflush(counts)
                T[key] = v
                T_np[key] = v
            return
        for c in range(0, 5):
            if n + c > 7:
                break
            counts[r] = c
            rec(r + 1, counts, n + c)
        counts[r] = 0

    rec(0, [0] * NR, 0)
    FL = [0] * 512
    for m in range(512):
        if bin(m).count("1") >= 5:
            st = _straight_top(m)
            if st >= 0:
                FL[m] = _pack(SFLUSH, [st])
            else:
                rd = [r for r in range(NR - 1, -1, -1) if m >> r & 1][:5]
                FL[m] = _pack(FLUSH, rd)
    return T, T_np, FL


T, T_NP, FL = _build()
FL_NP = np.array(FL, dtype=np.int32)


def value(cards):
    """cards: list of ints (5..7). Best hand value."""
    s = START
    for c in cards:
        s += KEY[c]
    v = T[s >> 16]
    if s & 0x8888:
        for su in range(4):
            if s >> (4 * su + 3) & 1:
                m = 0
                for c in cards:
                    if c & 3 == su:
                        m |= 1 << (c >> 2)
                f = FL[m]
                if f > v:
                    v = f
                break
    return v


def category(v):
    return v >> 20


# numpy helpers
RK_NP = np.array([P5[c >> 2] for c in range(36)] + [0], dtype=np.int64)  # index 36 = no card
SK_NP = np.array([1 << 4 * (c & 3) for c in range(36)] + [0], dtype=np.int64)
RB_NP = np.array([1 << (c >> 2) for c in range(36)] + [0], dtype=np.int64)
SU_NP = np.array([c & 3 for c in range(36)] + [9], dtype=np.int64)


def value_np(cards):
    """cards: int array (n, k) of card ids. Returns int array (n,) of values."""
    rk = RK_NP[cards].sum(axis=1)
    v = T_NP[rk]
    s = SK_NP[cards].sum(axis=1) + 0x3333
    fl = np.nonzero(s & 0x8888)[0]
    if fl.size:
        sub = cards[fl]
        su = SU_NP[sub]
        rb = RB_NP[sub]
        best = np.zeros(fl.size, dtype=np.int64)
        for k in range(4):
            m = np.where(su == k, rb, 0).sum(axis=1)
            best = np.maximum(best, FL_NP[m])
        v = v.copy()
        v[fl] = np.maximum(v[fl], best)
    return v
