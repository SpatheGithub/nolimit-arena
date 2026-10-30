"""Vectorized 7-card evaluation and equity estimation (numpy)."""
import os

import numpy as np

_D = os.path.dirname(os.path.abspath(__file__))
NF = np.load(os.path.join(_D, "nf.npy"))
FL = np.load(os.path.join(_D, "fl.npy"))
_pre = np.load(os.path.join(_D, "pre.npz"))
PCT = _pre["pct"]            # (169,) percentile vs 1 random hand, 0 = best
EQM = _pre["eqm"]            # (169, 7) equity vs k random hands
try:
    CVC = np.load(os.path.join(_D, "cvc.npy"))   # (169,169) class vs class equity
except Exception:
    CVC = None

try:
    ICMF = np.load(os.path.join(_D, "icm.npy")).tolist()
except Exception:
    ICMF = None
POINTS = [100, 60, 40, 25, 15, 10, 5, 0]


def icmv(n, chips, total):
    """Expected points holding chips of total with n players left (others equal)."""
    if n <= 1:
        return 100.0
    if n > 8:
        n = 8
    if chips <= 0:
        return float(POINTS[n - 1])
    x = chips / total
    if x >= 1:
        return 100.0
    row = ICMF[n]
    f = x * 200.0
    i = int(f)
    t = f - i
    return row[i] * (1 - t) + row[i + 1] * t


RKEY = np.array([0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181], dtype=np.int64)
_c = np.arange(52)
_AR = np.arange(52, dtype=np.int64)
CK = RKEY[_c >> 2]
SBIT = np.zeros((4, 52), dtype=np.int64)
SBIT[_c & 3, _c] = 1 << (_c >> 2)

SBF = SBIT.ravel().copy()
CSIG = (1 << ((_c & 3) * 4)).astype(np.int64)
_CKL = CK.tolist()
_CSIGL = CSIG.tolist()
_fsl = []
for _sig in range(1 << 15):
    _cn = [(_sig >> (4 * _s)) & 15 for _s in range(4)]
    _fsl.append(_cn.index(max(_cn)) * 52)
FSUIT52 = np.array(_fsl, dtype=np.int64)

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}


def cls_of(c1, c2):
    a, b = c1 >> 2, c2 >> 2
    if a == b:
        return a * 13 + a
    hi, lo = (a, b) if a > b else (b, a)
    return hi * 13 + lo if (c1 & 3) == (c2 & 3) else lo * 13 + hi


CLS52 = np.zeros((52, 52), dtype=np.int64)
for _i in range(52):
    for _j in range(52):
        if _i != _j:
            CLS52[_i, _j] = cls_of(_i, _j)
PCT52 = PCT[CLS52]
# combos per class
NCOMBO = np.zeros(169)
for _a in range(13):
    for _b in range(13):
        NCOMBO[_a * 13 + _b] = 6 if _a == _b else (4 if _a > _b else 12)
# classes sorted by strength (pct ascending) and cumulative combo fraction
ORDER = np.argsort(PCT)
CUMFRAC = np.cumsum(NCOMBO[ORDER]) / 1326.0

NS = 140
_rng = np.random.default_rng(987654321)
IDX = {}
for _D2 in (45, 46, 47):
    IDX[_D2] = np.argsort(_rng.random((NS, _D2)), axis=1)[:, :8]
PAIRS = {}
for _D2 in (45,):
    _p = [(i, j) for i in range(_D2) for j in range(i + 1, _D2)]
    PAIRS[_D2] = np.array(_p, dtype=np.int64)


def _vals(c1, c2, bkey, bm, suits):
    v = NF[bkey + CK[c1] + CK[c2]]
    for s in suits:
        sb = SBIT[s]
        v = np.maximum(v, FL[bm[s] + sb[c1] + sb[c2]])
    return v


def equity(hole, board, n_opp, ranges, gam=None):
    """Equity of hole vs n_opp opponents (capped at 3) holding hands weighted by
    their percentile ranges (list of (p, floor) per opponent). Returns equity
    vs those opponents."""
    msk = np.ones(52, dtype=bool)
    msk[hole] = False
    msk[board] = False
    rem = _AR[msk]
    D = len(rem)
    nb = len(board)
    need = 5 - nb
    n = max(1, min(3, n_opp))
    ranges = (list(ranges) + [(1.0, 1.0)] * 3)[:n]
    if need == 0 and n == 1:
        pr = rem[PAIRS[D]]
        N = pr.shape[0]
        b = np.array(board, dtype=np.int64)
        bkey = int(CK[b].sum())
        bm = [int(SBIT[s][b].sum()) for s in range(4)]
        cnt = [sum(1 for c in board if (c & 3) == s) for s in range(4)]
        suits = [s for s in range(4) if cnt[s] >= 3]
        my = int(NF[bkey + CK[hole[0]] + CK[hole[1]]])
        for s in suits:
            my = max(my, int(FL[bm[s] + SBIT[s][hole[0]] + SBIT[s][hole[1]]]))
        o1, o2 = pr[:, 0], pr[:, 1]
        ov = _vals(o1, o2, bkey, bm, suits)
        p, fl = ranges[0]
        w = np.where(PCT52[o1, o2] <= p, 1.0, fl)
        if gam and gam[0] > 0:
            w = w * (ov.argsort().argsort() * (1.0 / N) + 0.05) ** gam[0]
        share = (my > ov) + 0.5 * (my == ov)
        return float((w * share).sum() / w.sum())
    idx = IDX[D][:, :need + 2 * n]
    dr = rem[idx]
    N = dr.shape[0]
    bkey0 = 0
    sig0 = 0
    for c in board:
        bkey0 += _CKL[c]
        sig0 += _CSIGL[c]
    if need:
        bvar = dr[:, :need]
        bkey = bkey0 + CK[bvar].sum(1)
        fs52 = FSUIT52[sig0 + CSIG[bvar].sum(1)]
        bmask = SBF[fs52[:, None] + bvar].sum(1)
        for c in board:
            bmask = bmask + SBF[fs52 + c]
    else:
        bkey = bkey0
        fs52 = int(FSUIT52[sig0])
        bmask = 0
        for c in board:
            bmask += int(SBF[fs52 + c])
    h1, h2 = hole[0], hole[1]
    my = np.maximum(NF[bkey + (_CKL[h1] + _CKL[h2])], FL[bmask + SBF[fs52 + h1] + SBF[fs52 + h2]])
    top = None
    ties = None
    w = None
    for j in range(n):
        o1 = dr[:, need + 2 * j]
        o2 = dr[:, need + 2 * j + 1]
        ov = np.maximum(NF[bkey + CK[o1] + CK[o2]], FL[bmask + SBF[fs52 + o1] + SBF[fs52 + o2]])
        p, fl = ranges[j]
        wj = np.where(PCT52[o1, o2] <= p, 1.0, fl) if p < 1.0 else None
        if gam and j < len(gam) and gam[j] > 0:
            gj = (ov.argsort().argsort() * (1.0 / N) + 0.05) ** gam[j]
            wj = gj if wj is None else wj * gj
        if wj is not None:
            w = wj if w is None else w * wj
        if top is None:
            top = ov
            ties = (ov == my) * 1.0
        else:
            ties = ties + (ov == my)
            top = np.maximum(top, ov)
    share = np.where(my > top, 1.0, np.where(my == top, 1.0 / (1.0 + ties), 0.0))
    if w is None:
        e = float(share.mean())
    else:
        e = float((w * share).sum() / max(w.sum(), 1e-9))
    if n_opp > n:
        e = e ** (n_opp / n)
    return e


import bisect as _bisect
_CUML = CUMFRAC.tolist()
if CVC is not None:
    _wv = NCOMBO[ORDER]
    _RE = (np.cumsum(CVC[:, ORDER] * _wv[None, :], axis=1) / np.cumsum(_wv)[None, :]).tolist()
else:
    _RE = None


def range_equity(c, p):
    """Equity of class c vs the top-p fraction of hands (by combos)."""
    if _RE is None:
        return None
    k = _bisect.bisect_left(_CUML, p)
    if k > 168:
        k = 168
    return _RE[c][k]
