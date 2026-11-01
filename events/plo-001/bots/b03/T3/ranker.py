"""Copied hand ranker (engine-equal values)."""
RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)
CATEGORIES = ("high_card", "pair", "two_pair", "trips", "straight",
              "flush", "full_house", "quads", "straight_flush")
HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)
ROLES = ("other", "SB", "BB")


def _top_ranks(k: int) -> tuple[int, ...]:
    """Rank mask -> its k highest ranks packed 4 bits each, highest first."""
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


def _straight_tops(ranks: str, ace_low: bool) -> tuple[int, ...]:
    """Rank mask -> top rank of the best straight it contains, or -1."""
    dr = sorted(RANKS.index(r) for r in ranks)
    tops: dict[int, int] = {}
    for i in range(len(dr) - 4):
        tops[sum(1 << r for r in dr[i:i + 5])] = dr[i + 4]
    if ace_low and 12 in dr and len(dr) >= 5 and 12 not in dr[:4]:
        tops.setdefault((1 << 12) | sum(1 << r for r in dr[:4]), dr[3])
    ordered = sorted(tops.items(), key=lambda t: -t[1])
    out = [-1] * 8192
    for m in range(8192):
        for sm, t in ordered:
            if m & sm == sm:
                out[m] = t
                break
    return tuple(out)


_STRAIGHTS = {(r, True): _straight_tops(r, True) for r in (RANKS, "6789TJQKA", "TJQKA")}


class Ranker:
    """Best-hand values for one deck and ranking, equal to the engine's:
    ``strength << 20 | tiebreak ranks``, higher wins. Fewer than five cards
    give the best partial hand (pairs, trips, high cards)."""

    def __init__(self, ranks: str = RANKS, ranking: dict | None = None):
        ranking = ranking or {}
        order = list(ranking.get("order") or CATEGORIES)
        ace_low = bool(ranking.get("ace_low", True))
        self.shift = [order.index(c) << 20 for c in CATEGORIES]
        self.cat_of = [CATEGORIES.index(c) for c in order]
        self.stop = _STRAIGHTS.get((ranks, ace_low)) or _straight_tops(ranks, ace_low)

    def value(self, cards) -> int:
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
        s = self.shift
        stop = self.stop
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
        t = stop[m1]
        if t >= 0:
            v = s[4] | t << 16
            if v > best:
                best = v
        for f in sm:
            if f.bit_count() >= 5:
                t = stop[f]
                v = s[8] | t << 16 if t >= 0 else s[5] | TOP5[f]
                if v > best:
                    best = v
        return best

    def category(self, value: int) -> int:
        return self.cat_of[value >> 20]


