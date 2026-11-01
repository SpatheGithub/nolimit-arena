"""Fast shortdeck hand evaluator (36 cards, ranks 6..A, flush > full house)."""
from array import array
from itertools import combinations_with_replacement

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
P5 = [5 ** i for i in range(9)]
KEY = [(P5[c >> 2] << 16) | (1 << 4 * (c & 3)) for c in range(36)]
RBIT = [1 << (c >> 2) for c in range(36)]
START = 0x3333
FL = 0x8888

# category codes (shortdeck order)
HIGH, PAIR, TWOP, TRIPS, STRAIGHT, FULL, FLUSH, QUADS, SFLUSH = range(9)

_STR = [(sum(1 << r for r in range(t - 4, t + 1)), t) for t in range(8, 3, -1)] + [((1 << 8) | 0b1111, 3)]


def straight_top(mask):
    for m, t in _STR:
        if mask & m == m:
            return t
    return -1


def _pack(ks, shift):
    v = 0
    for k in ks:
        v |= k << shift
        shift -= 4
    return v


def _unsuited(cnt):
    desc = [r for r in range(8, -1, -1) if cnt[r] > 0]
    quads = [r for r in desc if cnt[r] >= 4]
    trips = [r for r in desc if cnt[r] >= 3]
    pairs = [r for r in desc if cnt[r] >= 2]
    mask = 0
    for r in desc:
        mask |= 1 << r
    if quads:
        q = quads[0]
        k = [r for r in desc if r != q][:1]
        return QUADS << 20 | q << 16 | _pack(k, 12)
    if trips:
        t = trips[0]
        others = [r for r in pairs if r != t]
        if others:
            return FULL << 20 | t << 16 | others[0] << 12
    st = straight_top(mask)
    if st >= 0:
        return STRAIGHT << 20 | st << 16
    if trips:
        t = trips[0]
        return TRIPS << 20 | t << 16 | _pack([r for r in desc if r != t][:2], 12)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return TWOP << 20 | p1 << 16 | p2 << 12 | _pack([r for r in desc if r != p1 and r != p2][:1], 8)
    if pairs:
        p = pairs[0]
        return PAIR << 20 | p << 16 | _pack([r for r in desc if r != p][:3], 12)
    return _pack(desc[:5], 16)


def _suited(mask):
    st = straight_top(mask)
    if st >= 0:
        return SFLUSH << 20 | st << 16
    desc = [r for r in range(8, -1, -1) if mask >> r & 1]
    return FLUSH << 20 | _pack(desc[:5], 16)


_T = [0] * (5 ** 9)
for _n in (2, 3, 4, 5, 6, 7):
    for _combo in combinations_with_replacement(range(9), _n):
        _cnt = [0] * 9
        for _r in _combo:
            _cnt[_r] += 1
        if max(_cnt) > 4:
            continue
        _code = 0
        for _r in _combo:
            _code += P5[_r]
        _T[_code] = _unsuited(_cnt)
T = {i: v for i, v in enumerate(_T) if v}
del _T
FS = [-1] * 512
for _m in range(512):
    if bin(_m).count("1") >= 5:
        FS[_m] = _suited(_m)
SUIT_OF_FLAG = {8 << 4 * s: s for s in range(4)}


def evaluate(cards):
    s = START
    for c in cards:
        s += KEY[c]
    v = T[s >> 16]
    if s & FL:
        su = SUIT_OF_FLAG[s & FL]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= RBIT[c]
        f = FS[m]
        if f > v:
            v = f
    return v


def parse(cards):
    return [CID[c] for c in cards]
