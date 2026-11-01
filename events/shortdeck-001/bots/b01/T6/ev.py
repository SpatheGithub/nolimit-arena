"""Shortdeck hand evaluator (36 cards, 6..A). Card id = rank*4 + suit, rank 0..8 (6..A).
Category order: high 0, pair 1, two pair 2, trips 3, straight 4, full house 5, flush 6, quads 7, SF 8.
Value = cat<<20 | tiebreak nibbles. Higher wins."""
from itertools import combinations_with_replacement

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}

# straight windows: (mask, top)
_STR = [(sum(1 << (r + k) for k in range(5)), r + 4) for r in range(4, -1, -1)]
_STR.append(((1 << 8) | 1 | 2 | 4 | 8, 3))  # A-6-7-8-9, top 9


def _straight_top(mask):
    for m, t in _STR:
        if mask & m == m:
            return t
    return -1


def _topn(mask, n):
    v = 0
    k = 0
    for r in range(8, -1, -1):
        if mask >> r & 1:
            v = v << 4 | r
            k += 1
            if k == n:
                break
    return v << 4 * (n - k)


def _nonflush(counts):
    present = 0
    for r in range(9):
        if counts[r]:
            present |= 1 << r
    quads = [r for r in range(8, -1, -1) if counts[r] >= 4]
    trips = [r for r in range(8, -1, -1) if counts[r] >= 3]
    pairs = [r for r in range(8, -1, -1) if counts[r] >= 2]
    if quads:
        q = quads[0]
        k = _topn(present & ~(1 << q), 1)
        return 7 << 20 | q << 16 | k << 12
    if trips:
        t = trips[0]
        rest = [p for p in pairs if p != t]
        if rest:
            return 5 << 20 | t << 16 | rest[0] << 12
    st = _straight_top(present)
    if st >= 0:
        return 4 << 20 | st << 16
    if trips:
        t = trips[0]
        return 3 << 20 | t << 16 | _topn(present & ~(1 << t), 2) << 8
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return 2 << 20 | p1 << 16 | p2 << 12 | _topn(present & ~(1 << p1) & ~(1 << p2), 1) << 8
    if pairs:
        p = pairs[0]
        return 1 << 20 | p << 16 | _topn(present & ~(1 << p), 3) << 4
    return _topn(present, 5)


RKEY = [5 ** r for r in range(9)]
NF = {}
for n in (5, 6, 7):
    for combo in combinations_with_replacement(range(9), n):
        c = [0] * 9
        for r in combo:
            c[r] += 1
        if max(c) > 4:
            continue
        NF[sum(RKEY[r] for r in combo)] = _nonflush(c)

FS = [-1] * 512
for m in range(512):
    if bin(m).count("1") >= 5:
        st = _straight_top(m)
        FS[m] = (8 << 20 | st << 16) if st >= 0 else (6 << 20 | _topn(m, 5))

# combined key: rank key << 16 | suit nibble counters (start 0x3333, flush when bit 3 set)
KEY = [RKEY[c >> 2] << 16 | 1 << 4 * (c & 3) for c in range(36)]
SB = {}
for s in range(4):
    SB[8 << 4 * s] = [(1 << (c >> 2)) if (c & 3) == s else 0 for c in range(36)]
START = 0x3333


def ev(cards):
    s = START
    for c in cards:
        s += KEY[c]
    if s & 0x8888:
        F = SB[s & 0x8888]
        m = 0
        for c in cards:
            m |= F[c]
        return FS[m]
    return NF[s >> 16]


def ev_key(s, cards):
    """s = START + sum of KEY over cards (precomputed); cards for flush mask."""
    if s & 0x8888:
        F = SB[s & 0x8888]
        m = 0
        for c in cards:
            m |= F[c]
        return FS[m]
    return NF[s >> 16]
