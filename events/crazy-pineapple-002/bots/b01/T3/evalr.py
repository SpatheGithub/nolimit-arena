"""Fast additive-key hand evaluator (same values as the engine)."""
import json
import os

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)

RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
START = 0x3333
RANK_KEY = tuple(RANK_KEYS[c >> 2] + COUNT for c in range(52))
KEY = tuple(RANK_KEY[c] << 16 | 1 << 4 * (c & 3) for c in range(52))
RANK_BIT = tuple(1 << (c >> 2) for c in range(52))
SUITED_BITS = {8 << 4 * s: tuple(RANK_BIT[c] if c & 3 == s else 0 for c in range(52)) for s in range(4)}

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "evtables.json")) as _f:
    _d = json.load(_f)
T = {k: v for k, v in _d["rank"]}
FS = _d["suited"]
del _d


def ev(cards):
    """Best five of 5..7 cards (list of ints)."""
    s = START
    for c in cards:
        s += KEY[c]
    if s & 0x8888:
        F = SUITED_BITS[s & 0x8888]
        m = 0
        for c in cards:
            m += F[c]
        f = FS[m]
        r = T[s >> 16]
        return f if f > r else r
    return T[s >> 16]


def ev_key(s, cards):
    """s = START + sum KEY over cards (precomputed)."""
    if s & 0x8888:
        F = SUITED_BITS[s & 0x8888]
        m = 0
        for c in cards:
            m += F[c]
        f = FS[m]
        r = T[s >> 16]
        return f if f > r else r
    return T[s >> 16]
