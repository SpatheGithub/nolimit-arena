"""Vectorised PLO evaluation: a 5-card hand = hole pair + board triple.

Tables (built at import, read-only afterwards):
  LUT2[pair_ms * 455 + triple_ms]  unsuited value of the 5 ranks
  FLV[mask13]                      flush / straight-flush value of 5 ranks
  P2I[c1, c2]  pair multiset index * 455     T3I[a, b, c] triple multiset index
  PSU / TSU    suit when suited / monotone (4 / 5 otherwise)
  PMK / TMK    13-bit rank masks
"""
from itertools import combinations, combinations_with_replacement

import numpy as np

from .ranker import Ranker

_R = Ranker()

_pairs_ms = list(combinations_with_replacement(range(13), 2))   # 91
_trip_ms = list(combinations_with_replacement(range(13), 3))    # 455
_PIDX = {m: i for i, m in enumerate(_pairs_ms)}
_TIDX = {m: i for i, m in enumerate(_trip_ms)}
NT = len(_trip_ms)

LUT2 = np.zeros(len(_pairs_ms) * NT, dtype=np.int32)
for pi, pm in enumerate(_pairs_ms):
    for ti, tm in enumerate(_trip_ms):
        rs = sorted(pm + tm)
        ok = True
        for r in set(rs):
            if rs.count(r) > 4:
                ok = False
        if not ok:
            continue
        cards = [4 * r + (i % 4) for i, r in enumerate(rs)]
        LUT2[pi * NT + ti] = _R.value(cards)

FLV = np.zeros(8192, dtype=np.int32)
for combo in combinations(range(13), 5):
    m = 0
    for r in combo:
        m |= 1 << r
    FLV[m] = _R.value([4 * r for r in combo])

P2I = np.zeros((52, 52), dtype=np.int32)
PSU = np.full((52, 52), 4, dtype=np.int8)
PMK = np.zeros((52, 52), dtype=np.int32)
for a in range(52):
    for b in range(52):
        ra, rb = a >> 2, b >> 2
        P2I[a, b] = _PIDX[tuple(sorted((ra, rb)))] * NT
        if a != b and (a & 3) == (b & 3):
            PSU[a, b] = a & 3
        PMK[a, b] = (1 << ra) | (1 << rb)

_r = np.arange(52) >> 2
_s = np.arange(52) & 3
_ra, _rb, _rc = np.meshgrid(_r, _r, _r, indexing="ij")
_srt = np.sort(np.stack([_ra, _rb, _rc], -1), axis=-1)
_code = _srt[..., 0] * 169 + _srt[..., 1] * 13 + _srt[..., 2]
_map = np.zeros(13 * 169, dtype=np.int32)
for i, (x, y, z) in enumerate(_trip_ms):
    _map[x * 169 + y * 13 + z] = i
T3I = _map[_code].astype(np.int32)
_sa, _sb, _sc = np.meshgrid(_s, _s, _s, indexing="ij")
TSU = np.where((_sa == _sb) & (_sb == _sc), _sa, 5).astype(np.int8)
TMK = ((1 << _ra) | (1 << _rb) | (1 << _rc)).astype(np.int32)
del _ra, _rb, _rc, _srt, _code, _sa, _sb, _sc

HP = np.array(list(combinations(range(4), 2)), dtype=np.intp)      # 6 hole pairs
BT = np.array(list(combinations(range(5), 3)), dtype=np.intp)      # 10 board triples
BT3 = np.array(list(combinations(range(3), 3)), dtype=np.intp)
BT4 = np.array(list(combinations(range(4), 3)), dtype=np.intp)

# permutation banks of unseen-card indices
_brng = np.random.default_rng(987654321)
NBANK = 2048
BANK = {}
for n in (43, 44, 45, 48):
    cols = min(n, 30)
    BANK[n] = np.argsort(_brng.random((NBANK, n)), axis=1)[:, :cols].astype(np.intp)


def best_value(hole, board):
    """Exact best PLO value (python ints) for hole (4) + board (3..5)."""
    best = -1
    for a, b in combinations(hole, 2):
        pi = int(P2I[a, b])
        ps = int(PSU[a, b])
        pm = int(PMK[a, b])
        for x, y, z in combinations(board, 3):
            if ps < 4 and int(TSU[x, y, z]) == ps:
                v = int(FLV[pm | int(TMK[x, y, z])])
            else:
                v = int(LUT2[pi + int(T3I[x, y, z])])
            if v > best:
                best = v
    return best


def equity(hole, board, k, S, off):
    """Monte-Carlo equity of hole vs k random hands; off = bank row offset.
    Returns (equity, my values array, opp max values array)."""
    nb = len(board)
    msk = np.ones(52, dtype=bool)
    msk[hole] = False
    if nb:
        msk[board] = False
    unseen = np.flatnonzero(msk)
    n = len(unseen)
    bank = BANK[n]
    need = 5 - nb
    rows = bank[off:off + S, :need + 4 * k]
    cards = unseen[rows]
    if need:
        B = np.empty((S, 5), dtype=np.intp)
        if nb:
            B[:, :nb] = board
        B[:, nb:] = cards[:, :need]
    else:
        B = np.broadcast_to(np.array(board, dtype=np.intp), (S, 5))
    ta = B[:, BT[:, 0]]
    tb = B[:, BT[:, 1]]
    tc = B[:, BT[:, 2]]
    ti = T3I[ta, tb, tc]            # (S,10)
    ts = TSU[ta, tb, tc]
    tm = TMK[ta, tb, tc]
    h = np.array(hole, dtype=np.intp)
    ha, hb = h[HP[:, 0]], h[HP[:, 1]]
    mi, ms, mm = P2I[ha, hb], PSU[ha, hb], PMK[ha, hb]
    v = LUT2[mi[None, :, None] + ti[:, None, :]]
    fl = ms[None, :, None] == ts[:, None, :]
    if fl.any():
        v = np.where(fl, FLV[mm[None, :, None] | tm[:, None, :]], v)
    mine = v.reshape(S, -1).max(1)
    O = cards[:, need:need + 4 * k].reshape(S, k, 4)
    oa, ob = O[:, :, HP[:, 0]], O[:, :, HP[:, 1]]   # (S,k,6)
    oi, osu, om = P2I[oa, ob], PSU[oa, ob], PMK[oa, ob]
    w = LUT2[oi[..., None] + ti[:, None, None, :]]   # (S,k,6,10)
    fo = osu[..., None] == ts[:, None, None, :]
    if fo.any():
        w = np.where(fo, FLV[om[..., None] | tm[:, None, None, :]], w)
    opp = w.reshape(S, -1).max(1)
    eq = float(((mine > opp) + 0.5 * (mine == opp)).mean())
    cur = None
    if 3 <= nb < 5:
        bt = BT3 if nb == 3 else BT4
        bb_ = np.array(board, dtype=np.intp)
        xa, xb, xc = bb_[bt[:, 0]], bb_[bt[:, 1]], bb_[bt[:, 2]]
        ci, cs, cm = T3I[xa, xb, xc], TSU[xa, xb, xc], TMK[xa, xb, xc]
        u = LUT2[oi[..., None] + ci]
        fu = osu[..., None] == cs
        if fu.any():
            u = np.where(fu, FLV[om[..., None] | cm], u)
        cur = u.reshape(S, -1).max(1)
    return eq, mine, opp, cur
