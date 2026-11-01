"""Short-deck (6..A) 5-7 card evaluator. Card id = rank*4 + suit, rank 0..8 = 6..A.
Order (high to low): SF, quads, flush, full house, straight, trips, two pair, pair, high."""
from itertools import combinations_with_replacement, combinations

RANKS = "6789TJQKA"
SUITS = "cdhs"
CARD = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}

HC, PAIR, TWOPAIR, TRIPS, STRAIGHT, FULL, FLUSH, QUADS, SF = range(9)

KEY = [((5 ** (c >> 2)) << 16) | (1 << (4 * (c & 3))) for c in range(36)]
START = 0x3333
SUITOF = {0x8: 0, 0x80: 1, 0x800: 2, 0x8000: 3}


def _straight_top(mask):
    for top in range(8, 3, -1):
        m = 0b11111 << (top - 4)
        if mask & m == m:
            return top
    if mask & 0b100001111 == 0b100001111:
        return 3
    return -1


def _eval_counts(counts):
    desc = [r for r in range(8, -1, -1) if counts[r]]
    mask = 0
    for r in desc:
        mask |= 1 << r
    quads = [r for r in desc if counts[r] == 4]
    trips = [r for r in desc if counts[r] == 3]
    pairs = [r for r in desc if counts[r] == 2]
    if quads:
        q = quads[0]
        k = max(r for r in desc if r != q)
        return QUADS << 20 | q << 16 | k << 12
    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        p = max(trips[1:] + pairs)
        return FULL << 20 | t << 16 | p << 12
    st = _straight_top(mask)
    if st >= 0:
        return STRAIGHT << 20 | st << 16
    if trips:
        t = trips[0]
        ks = [r for r in desc if r != t][:2]
        return TRIPS << 20 | t << 16 | ks[0] << 12 | ks[1] << 8
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        k = max(r for r in desc if r != p1 and r != p2)
        return TWOPAIR << 20 | p1 << 16 | p2 << 12 | k << 8
    if pairs:
        p = pairs[0]
        ks = [r for r in desc if r != p][:3]
        return PAIR << 20 | p << 16 | ks[0] << 12 | ks[1] << 8 | ks[2] << 4
    ks = desc[:5]
    return HC << 20 | ks[0] << 16 | ks[1] << 12 | ks[2] << 8 | ks[3] << 4 | ks[4]


def _build():
    rt = {}
    for n in (5, 6, 7):
        for combo in combinations_with_replacement(range(9), n):
            counts = [0] * 9
            ok = True
            for r in combo:
                counts[r] += 1
                if counts[r] > 4:
                    ok = False
            if not ok:
                continue
            code = sum(5 ** r for r in combo)
            rt[code] = _eval_counts(counts)
    st = [-1] * 512
    for m in range(512):
        if bin(m).count("1") >= 5:
            top = _straight_top(m)
            if top >= 0:
                st[m] = SF << 20 | top << 16
            else:
                ks = [r for r in range(8, -1, -1) if m >> r & 1][:5]
                st[m] = FLUSH << 20 | ks[0] << 16 | ks[1] << 12 | ks[2] << 8 | ks[3] << 4 | ks[4]
    return rt, st


RT, ST = _build()


def evaluate(cards):
    """cards: list of 5..7 card ids."""
    s = START
    for c in cards:
        s += KEY[c]
    r = RT[s >> 16]
    if s & 0x8888:
        su = SUITOF[s & 0x8888]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= 1 << (c >> 2)
        f = ST[m]
        return f if f > r else r
    return r


def evaluate_s(s, cards):
    """s: precomputed START + sum KEY over cards."""
    r = RT[s >> 16]
    if s & 0x8888:
        su = SUITOF[s & 0x8888]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= 1 << (c >> 2)
        f = ST[m]
        return f if f > r else r
    return r


def hand_class(c1, c2):
    """0..80 index: pairs 0..8, suited 9..44, offsuit 45..80 (hi>lo)."""
    r1, r2 = c1 >> 2, c2 >> 2
    if r1 < r2:
        r1, r2 = r2, r1
    if r1 == r2:
        return r1
    idx = r1 * (r1 - 1) // 2 + r2  # 0..35
    if (c1 & 3) == (c2 & 3):
        return 9 + idx
    return 45 + idx


def class_combos(k):
    """list of (c1, c2) card-id combos of class k."""
    out = []
    for a, b in combinations(range(36), 2):
        if hand_class(a, b) == k:
            out.append((a, b))
    return out
