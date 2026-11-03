"""Vectorized shortdeck equity: rank-count lookup + flush table, numpy."""
import numpy as np
from itertools import combinations

from .common import Ranker

RANKS = "6789TJQKA"
ORDER = ["high_card", "pair", "two_pair", "trips", "straight", "full_house", "flush", "quads", "straight_flush"]
# own card ids: 0..35 = r*4+s, r in 0..8 (6..A); common.py ids: 4*R+s with R in 0..12 (R = r+4)
_rk = Ranker(RANKS, {"order": ORDER, "ace_low": True})
P5 = [5 ** r for r in range(9)]


def _build():
    rv = np.zeros(2 * 5 ** 9, dtype=np.int32)

    def rec(r, left, cnts):
        if r == 9:
            if left == 0:
                cards = []
                g = 0
                for rr, c in enumerate(cnts):
                    for _ in range(c):
                        cards.append(4 * (rr + 4) + (g % 4))
                        g += 1
                key = sum(c * P5[rr] for rr, c in enumerate(cnts))
                rv[key] = _rk.value(cards)
            return
        for c in range(0, min(4, left) + 1):
            cnts.append(c)
            rec(r + 1, left - c, cnts)
            cnts.pop()

    for n in (5, 6, 7):
        rec(0, n, [])
    fv = np.zeros(512, dtype=np.int32)
    for m in range(512):
        bits = [r for r in range(9) if m >> r & 1]
        if len(bits) >= 5:
            best = 0
            for comb in combinations(bits, 5):
                v = _rk.value([4 * (r + 4) for r in comb])  # all suit 0 -> flush/sf
                if v > best:
                    best = v
            fv[m] = best
    return rv, fv


RV, FV = _build()
# all 630 two-card combos
_pairs = list(combinations(range(36), 2))
C1 = np.array([a for a, b in _pairs], dtype=np.int64)
C2 = np.array([b for a, b in _pairs], dtype=np.int64)
PK = np.array([P5[a >> 2] + P5[b >> 2] for a, b in _pairs], dtype=np.int64)
HB = np.zeros((4, len(_pairs)), dtype=np.int64)
for i, (a, b) in enumerate(_pairs):
    HB[a & 3, i] |= 1 << (a >> 2)
    HB[b & 3, i] |= 1 << (b >> 2)
INC = np.zeros((36, len(_pairs)), dtype=bool)
for i, (a, b) in enumerate(_pairs):
    INC[a, i] = True
    INC[b, i] = True
NP = len(_pairs)
# 45 distinct rank pairs: look up rank-part values per rank pair, then expand to combos (cache friendly)
_rp = sorted({(min(a >> 2, b >> 2), max(a >> 2, b >> 2)) for a, b in _pairs})
_rpi = {rp: i for i, rp in enumerate(_rp)}
PK45 = np.array([P5[x] + P5[y] for x, y in _rp], dtype=np.int64)
RPI = np.array([_rpi[(min(a >> 2, b >> 2), max(a >> 2, b >> 2))] for a, b in _pairs], dtype=np.int64)
CARDRANK = np.array([c >> 2 for c in range(36)], dtype=np.int64)
CARDSUIT = np.array([c & 3 for c in range(36)], dtype=np.int64)
CARDP5 = np.array([P5[c >> 2] for c in range(36)], dtype=np.int64)
CARDBIT = np.array([1 << (c >> 2) for c in range(36)], dtype=np.int64)
PAIRIDX = {}
for i, (a, b) in enumerate(_pairs):
    PAIRIDX[(a, b)] = i
    PAIRIDX[(b, a)] = i

# preflop class per combo (common.py convention: pair hi*9+hi, suited hi*9+lo, offsuit lo*9+hi)
CLS = np.zeros(NP, dtype=np.int64)
for i, (a, b) in enumerate(_pairs):
    ra, rb = a >> 2, b >> 2
    if ra == rb:
        CLS[i] = ra * 9 + ra
    else:
        hi, lo = max(ra, rb), min(ra, rb)
        CLS[i] = hi * 9 + lo if (a & 3) == (b & 3) else lo * 9 + hi


def conv(c):
    """common.py card id (4*R+s) -> own id."""
    return ((c >> 2) - 4) * 4 + (c & 3)


def value(cards):
    """scalar best value of 5-7 own-id cards."""
    key = 0
    sm = [0, 0, 0, 0]
    for c in cards:
        key += P5[c >> 2]
        sm[c & 3] |= 1 << (c >> 2)
    v = int(RV[key])
    for m in sm:
        if m and bin(m).count("1") >= 5:
            f = int(FV[m])
            if f > v:
                v = f
    return v


def opp_values(board, alive_idx):
    """values of combos alive_idx on a complete (5 card) board."""
    bk = 0
    bsm = [0, 0, 0, 0]
    bcnt = [0, 0, 0, 0]
    for c in board:
        bk += P5[c >> 2]
        bsm[c & 3] |= 1 << (c >> 2)
        bcnt[c & 3] += 1
    vals = RV[bk + PK45][RPI[alive_idx]]
    for s in range(4):
        if bcnt[s] >= 3:
            fv = FV[bsm[s] | HB[s, alive_idx]]
            vals = np.maximum(vals, fv)
    return vals


def equity(hero, board, weights, rng, n_samples=40, n_river=40):
    """hero: 2 own ids; board: 3..5 own ids; weights: (NP,) float range weights
    for one opponent. Returns (equity, total weight)."""
    dead = list(hero) + list(board)
    alive = ~INC[dead].any(axis=0)
    nb = len(board)
    if nb == 5:
        idx = np.nonzero(alive)[0]
        w = weights[idx]
        ws = w.sum()
        if ws <= 0:
            w = np.ones(len(idx))
            ws = w.sum()
        hv = value(list(hero) + list(board))
        ov = opp_values(board, idx)
        return float((w * ((ov < hv) + 0.5 * (ov == hv))).sum() / ws)
    deck = [c for c in range(36) if c not in dead]
    if nb == 4:
        if n_river < len(deck):
            deck = rng.sample(deck, n_river)
        runs = np.array([[c] for c in deck], dtype=np.int64)
    else:
        smp = rng.sample
        runs = np.array([smp(deck, 2) for _ in range(n_samples)], dtype=np.int64)
    R = runs.shape[0]
    # board keys and suit masks per run
    bk0 = 0
    bsm0 = [0, 0, 0, 0]
    for c in board:
        bk0 += P5[c >> 2]
        bsm0[c & 3] |= 1 << (c >> 2)
    bk = bk0 + CARDP5[runs].sum(axis=1)  # (R,)
    hk = P5[hero[0] >> 2] + P5[hero[1] >> 2]
    hv = RV[bk + hk]  # (R,)
    ov = RV[bk[:, None] + PK45[None, :]][:, RPI]  # (R, NP)
    rs = CARDSUIT[runs]
    rb = CARDBIT[runs]
    hsm = [0, 0, 0, 0]
    for c in hero:
        hsm[c & 3] |= 1 << (c >> 2)
    for s in range(4):
        base = bsm0[s]
        bc = bin(base).count("1")
        if bc + runs.shape[1] < 3:
            continue
        ins = rs == s
        # a flush needs >= 3 board cards of the suit (each player holds only 2)
        if bc + int(ins.sum(axis=1).max()) < 3:
            continue
        add = (rb * ins).sum(axis=1)  # (R,)
        bm = base | add
        hv = np.maximum(hv, FV[bm | hsm[s]])
        ov = np.maximum(ov, FV[bm[:, None] | HB[s][None, :]])
    al = np.broadcast_to(alive, (R, NP)).copy()
    for j in range(runs.shape[1]):
        al &= ~INC[runs[:, j]]
    w = weights[None, :] * al
    ws = w.sum()
    if ws <= 0:
        w = al.astype(float)
        ws = w.sum()
    h = hv[:, None]
    return float((w * ((ov < h) + 0.5 * (ov == h))).sum() / ws)


def cur_values(board, idx):
    """values of combos idx on a 3-4 card board (current made hand)."""
    bk = 0
    bsm = [0, 0, 0, 0]
    bcnt = [0, 0, 0, 0]
    for c in board:
        bk += P5[c >> 2]
        bsm[c & 3] |= 1 << (c >> 2)
        bcnt[c & 3] += 1
    vals = RV[bk + PK45][RPI[idx]]
    for s in range(4):
        if bcnt[s] >= 3:
            vals = np.maximum(vals, FV[bsm[s] | HB[s, idx]])
    return vals
