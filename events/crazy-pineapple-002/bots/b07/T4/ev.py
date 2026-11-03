"""Fast hand evaluator (table lookups), value-identical to the engine."""
import os
import pickle

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)

RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
START = 0x3333
KEY = tuple((RANK_KEYS[c >> 2] + COUNT) << 16 | 1 << 4 * (c & 3) for c in range(52))
RBIT = tuple(1 << (c >> 2) for c in range(52))
FLUSHBIT_SUIT = {8 << 4 * s: s for s in range(4)}

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "evtab.pkl"), "rb") as _f:
    _d = pickle.load(_f)
RT = _d["rank"]
ST = _d["suited"]
del _d


def ev(cards):
    """Best five of 5..7 cards. Higher is better; category = value >> 20."""
    s = START
    for c in cards:
        s += KEY[c]
    fl = s & 0x8888
    if fl:
        su = FLUSHBIT_SUIT[fl]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= RBIT[c]
        f = ST[m]
        r = RT[s >> 16]
        return f if f > r else r
    return RT[s >> 16]


def ev_sum(s, cards):
    """Like ev, with s = START + sum(KEY) of all cards precomputed."""
    fl = s & 0x8888
    if fl:
        su = FLUSHBIT_SUIT[fl]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= RBIT[c]
        f = ST[m]
        r = RT[s >> 16]
        return f if f > r else r
    return RT[s >> 16]
