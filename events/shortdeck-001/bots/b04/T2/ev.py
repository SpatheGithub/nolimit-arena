"""Shortdeck hand evaluator: lookup tables built at import (fast)."""
from itertools import combinations, combinations_with_replacement

RANKS = "6789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = [r + s for r in RANKS for s in SUITS]

# categories (shortdeck order)
HIGH, PAIR, TWOPAIR, TRIPS, STRAIGHT, FULL, FLUSH, QUADS, SFLUSH = range(9)

START = 0x3333
RK = [5 ** r for r in range(9)]
KEY = [(RK[c >> 2] << 16) | (1 << (4 * (c & 3))) for c in range(36)]
RBIT = [1 << (c >> 2) for c in range(36)]


def _straight_top(rset):
    best = -1
    for top in range(4, 9):
        if all((top - k) in rset for k in range(5)):
            best = top
    if best < 0 and {8, 0, 1, 2, 3} <= rset:
        best = 3
    return best


def _eval5_unsuited(rs):
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(cnt.items(), key=lambda t: (-t[1], -t[0]))
    shape = [g[1] for g in groups]
    ranks = [g[0] for g in groups]
    if len(cnt) == 5:
        st = _straight_top(set(rs))
        if st >= 0:
            return (STRAIGHT << 20) | (st << 16)
    if shape[0] == 4:
        cat = QUADS
    elif shape[0] == 3 and shape[1] == 2:
        cat = FULL
    elif shape[0] == 3:
        cat = TRIPS
    elif shape[0] == 2 and shape[1] == 2:
        cat = TWOPAIR
    elif shape[0] == 2:
        cat = PAIR
    else:
        cat = HIGH
    v = cat << 20
    sh = 16
    for r in ranks:
        v |= r << sh
        sh -= 4
    return v


def _build():
    T = {}
    level = {}
    for combo in combinations_with_replacement(range(9), 5):
        if any(combo.count(r) > 4 for r in combo):
            continue
        key = sum(RK[r] for r in combo)
        T[key] = _eval5_unsuited(combo)
        level[key] = combo
    for _ in range(2):
        grown = {}
        for key, combo in level.items():
            v = T[key]
            for r in range(9):
                if combo.count(r) >= 4:
                    continue
                k = key + RK[r]
                if k not in grown:
                    grown[k] = tuple(sorted(combo + (r,)))
                if v > T.get(k, -1):
                    T[k] = v
        level = grown
    # small hands (<5 cards) for partial evaluation: pairs/trips/high
    for n in (1, 2, 3, 4):
        for combo in combinations_with_replacement(range(9), n):
            if any(combo.count(r) > 4 for r in combo):
                continue
            key = sum(RK[r] for r in combo)
            cnt = {}
            for r in combo:
                cnt[r] = cnt.get(r, 0) + 1
            groups = sorted(cnt.items(), key=lambda t: (-t[1], -t[0]))
            shape = [g[1] for g in groups]
            if shape[0] == 4:
                cat = QUADS
            elif shape[0] == 3:
                cat = TRIPS
            elif shape[0] == 2 and len(shape) > 1 and shape[1] == 2:
                cat = TWOPAIR
            elif shape[0] == 2:
                cat = PAIR
            else:
                cat = HIGH
            v = cat << 20
            sh = 16
            for g in groups:
                v |= g[0] << sh
                sh -= 4
            T[key] = v
    S = [-1] * 512
    for m in range(512):
        if bin(m).count("1") < 5:
            continue
        rs = {r for r in range(9) if m >> r & 1}
        st = _straight_top(rs)
        if st >= 0:
            S[m] = (SFLUSH << 20) | (st << 16)
        else:
            top = sorted(rs, reverse=True)[:5]
            v = FLUSH << 20
            sh = 16
            for r in top:
                v |= r << sh
                sh -= 4
            S[m] = v
    return T, S


T, S = _build()


def ev(cards):
    s = START
    for c in cards:
        s += KEY[c]
    if s & 0x8888:
        for su in range(4):
            if (s >> (4 * su)) & 8:
                m = 0
                for c in cards:
                    if c & 3 == su:
                        m |= RBIT[c]
                return S[m]
    return T[s >> 16]


def ev_sum(s, cards):
    """s = START + sum KEY of all cards; cards needed only for flush."""
    if s & 0x8888:
        for su in range(4):
            if (s >> (4 * su)) & 8:
                m = 0
                for c in cards:
                    if c & 3 == su:
                        m |= RBIT[c]
                return S[m]
    return T[s >> 16]


def cls_of(c1, c2):
    """preflop class index 0..80: pairs r*9+r; suited hi*9+lo; offsuit lo*9+hi."""
    a, b = c1 >> 2, c2 >> 2
    if a == b:
        return a * 9 + a
    hi, lo = (a, b) if a > b else (b, a)
    return hi * 9 + lo if (c1 & 3) == (c2 & 3) else lo * 9 + hi


ALL_COMBOS = list(combinations(range(36), 2))
