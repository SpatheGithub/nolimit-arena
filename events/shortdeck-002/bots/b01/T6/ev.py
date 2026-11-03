"""Fast shortdeck evaluator. Cards are ints 0..35: rank = c >> 2 (0='6'..8='A'), suit = c & 3."""
from itertools import combinations_with_replacement

from ._common import Ranker

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
_RANKING = {"order": ["high_card", "pair", "two_pair", "trips", "straight", "full_house", "flush",
                      "quads", "straight_flush"], "ace_low": True}
_RK = Ranker(RANKS, _RANKING)

K5 = [5 ** (c >> 2) for c in range(36)]
KS = [8 ** (c & 3) for c in range(36)]
KM = [1 << (9 * (c & 3) + (c >> 2)) for c in range(36)]


def _c52(r, s):
    return (r + 4) * 4 + s


NF = {}
for n in (5, 6, 7):
    for combo in combinations_with_replacement(range(9), n):
        ok = True
        for r in set(combo):
            if combo.count(r) > 4:
                ok = False
                break
        if not ok:
            continue
        cards = []
        cnt = {}
        for r in combo:
            k = cnt.get(r, 0)
            cnt[r] = k + 1
            cards.append(_c52(r, k))
        # suits assigned by multiplicity index -> at most 4 of a suit only if 4+ distinct ranks share
        # index 0; break flushes by rotating suits for singletons
        fixed = []
        rot = 0
        for r in combo:
            pass
        cards = []
        cnt = {}
        seen_single = 0
        for r in sorted(set(combo)):
            m = combo.count(r)
            for k in range(m):
                cards.append(_c52(r, (k + seen_single) % 4))
            seen_single += 1
        # ensure no suit has >= 5
        sc = [0, 0, 0, 0]
        for c in cards:
            sc[c & 3] += 1
        assert max(sc) < 5, combo
        NF[sum(5 ** r for r in combo)] = _RK.value(cards)

FS = [-1] * 4096
for key in range(4096):
    x = key
    for s in range(4):
        if x % 8 >= 5:
            FS[key] = s
        x //= 8

FLV = [0] * 512
for m in range(512):
    if bin(m).count("1") >= 5:
        FLV[m] = _RK.value([_c52(r, 0) for r in range(9) if m >> r & 1])

CAT_SHIFT = 20


def evaluate(cards):
    a = b = m = 0
    for c in cards:
        a += K5[c]
        b += KS[c]
        m += KM[c]
    s = FS[b]
    if s >= 0:
        return FLV[(m >> (9 * s)) & 511]
    return NF[a]


def category(v):
    return v >> 20
