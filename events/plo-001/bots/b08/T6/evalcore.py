"""Hand values identical to the engine's (standard order): cat << 20 | tiebreak."""

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}


def _top_ranks(k):
    out = [0] * 8192
    for m in range(8192):
        v = n = 0
        x = m
        while x and n < k:
            r = x.bit_length() - 1
            v = v << 4 | r
            x ^= 1 << r
            n += 1
        out[m] = v << 4 * (k - n)
    return tuple(out)


TOP1, TOP2, TOP3, TOP5 = _top_ranks(1), _top_ranks(2), _top_ranks(3), _top_ranks(5)


def _straight_tops():
    tops = {}
    for lo in range(9):
        tops[sum(1 << r for r in range(lo, lo + 5))] = lo + 4
    tops[(1 << 12) | 0b1111] = 3
    ordered = sorted(tops.items(), key=lambda t: -t[1])
    out = [-1] * 8192
    for m in range(8192):
        for sm, t in ordered:
            if m & sm == sm:
                out[m] = t
                break
    return tuple(out)


STOP = _straight_tops()
STRAIGHT_MASKS = [sum(1 << r for r in range(lo, lo + 5)) for lo in range(9)] + [(1 << 12) | 0b1111]
SH = [c << 20 for c in range(9)]


def value(cards):
    m1 = m2 = m3 = m4 = 0
    sm = [0, 0, 0, 0]
    for c in cards:
        b = 1 << (c >> 2)
        sm[c & 3] |= b
        if m1 & b:
            if m2 & b:
                if m3 & b:
                    m4 |= b
                else:
                    m3 |= b
            else:
                m2 |= b
        else:
            m1 |= b
    s = SH
    best = s[0] | TOP5[m1]
    if m2:
        if m4:
            q = m4.bit_length() - 1
            v = s[7] | q << 16 | TOP1[m1 & ~(1 << q)] << 12
            if v > best:
                best = v
        if m3:
            t = m3.bit_length() - 1
            rest = m2 & ~(1 << t)
            if rest:
                v = s[6] | t << 16 | (rest.bit_length() - 1) << 12
                if v > best:
                    best = v
            v = s[3] | t << 16 | TOP2[m1 & ~(1 << t)] << 8
            if v > best:
                best = v
        p = m2.bit_length() - 1
        rest = m2 & ~(1 << p)
        if rest:
            p2 = rest.bit_length() - 1
            v = s[2] | p << 16 | p2 << 12 | TOP1[m1 & ~(1 << p | 1 << p2)] << 8
            if v > best:
                best = v
        v = s[1] | p << 16 | TOP3[m1 & ~(1 << p)] << 4
        if v > best:
            best = v
    t = STOP[m1]
    if t >= 0:
        v = s[4] | t << 16
        if v > best:
            best = v
    for f in sm:
        if f.bit_count() >= 5:
            t = STOP[f]
            v = s[8] | t << 16 if t >= 0 else s[5] | TOP5[f]
            if v > best:
                best = v
    return best
