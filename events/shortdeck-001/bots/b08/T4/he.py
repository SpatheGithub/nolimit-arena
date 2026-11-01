"""Shortdeck hand evaluation tables (numpy) and Monte Carlo equity helpers."""
import numpy as np

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NC = 36
P5 = [5 ** i for i in range(9)]

# category ids (shortdeck order, low -> high)
HIGH, PAIR, TWOPAIR, TRIPS, STRAIGHT, FULL, FLUSH, QUADS, SFLUSH = range(9)

_STR = []
for _t in range(8, 3, -1):
    _STR.append((_t, sum(1 << r for r in range(_t - 4, _t + 1))))
_STR.append((3, (1 << 8) | 0b1111))


def straight_top(mask):
    for t, m in _STR:
        if mask & m == m:
            return t
    return -1


def _pack(rs, k):
    v = 0
    for i in range(k):
        v = v << 4 | (rs[i] if i < len(rs) else 0)
    return v


def unsuited_value(cnt):
    present = [r for r in range(8, -1, -1) if cnt[r] > 0]
    mask = sum(1 << r for r in present)
    quads = [r for r in present if cnt[r] == 4]
    trips = [r for r in present if cnt[r] == 3]
    pairs = [r for r in present if cnt[r] >= 2]
    best = HIGH << 20 | _pack(present, 5)
    if quads:
        q = quads[0]
        k = [r for r in present if r != q]
        best = max(best, QUADS << 20 | q << 16 | (k[0] if k else 0) << 12)
    if trips or quads:
        tr = [r for r in present if cnt[r] >= 3]
        t = tr[0]
        rest = [r for r in pairs if r != t]
        if rest:
            best = max(best, FULL << 20 | t << 16 | rest[0] << 12)
        k = [r for r in present if r != t]
        best = max(best, TRIPS << 20 | t << 16 | _pack(k, 2) << 8)
    st = straight_top(mask)
    if st >= 0:
        best = max(best, STRAIGHT << 20 | st << 16)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        k = [r for r in present if r != p1 and r != p2]
        best = max(best, TWOPAIR << 20 | p1 << 16 | p2 << 12 | (k[0] if k else 0) << 8)
    if pairs:
        p = pairs[0]
        k = [r for r in present if r != p]
        best = max(best, PAIR << 20 | p << 16 | _pack(k, 3) << 4)
    return best


def _build_rt():
    rt = np.zeros(5 ** 9, dtype=np.int32)
    cnt = [0] * 9

    def rec(r, n, idx):
        if r == 9:
            if 5 <= n <= 7:
                rt[idx] = unsuited_value(cnt)
            return
        for c in range(0, min(4, 7 - n) + 1):
            cnt[r] = c
            rec(r + 1, n + c, idx + c * P5[r])
        cnt[r] = 0

    rec(0, 0, 0)
    return rt


def _build_ft():
    ft = np.full(512, -1, dtype=np.int32)
    for m in range(512):
        if bin(m).count("1") >= 5:
            st = straight_top(m)
            if st >= 0:
                ft[m] = SFLUSH << 20 | st << 16
            else:
                rs = [r for r in range(8, -1, -1) if m >> r & 1]
                ft[m] = FLUSH << 20 | _pack(rs, 5)
    return ft


RT = _build_rt()
FT = _build_ft()
RKEY = np.array([P5[c // 4] for c in range(NC)], dtype=np.int64)
SMASK = [np.array([(1 << (c // 4)) if c % 4 == s else 0 for c in range(NC)], dtype=np.int64)
         for s in range(4)]
RKEY_L = [P5[c // 4] for c in range(NC)]
RT_L = None  # python list view built lazily is too big; use numpy scalar indexing
FT_L = FT.tolist()


def value_py(cards):
    """Exact value of 5..7 cards (python scalars)."""
    idx = 0
    sm = [0, 0, 0, 0]
    for c in cards:
        idx += RKEY_L[c]
        sm[c & 3] |= 1 << (c >> 2)
    v = int(RT[idx])
    for m in sm:
        f = FT_L[m]
        if f > v:
            v = f
    return v


def eval_mat(C, suits=(0, 1, 2, 3)):
    """C: int array (S, k) of card ids, k in 5..7 -> values (S,)"""
    v = RT[RKEY[C].sum(axis=1)]
    for s in suits:
        f = FT[SMASK[s][C].sum(axis=1)]
        v = np.maximum(v, f)
    return v


# permutation pools for sampling unknown cards: pool[n] -> (P, 16) indices into a deck of n
_prng = np.random.default_rng(12345)
POOL = {}
POOL_P = 6000
for _n in (27, 28, 29, 30, 31, 32, 33, 34):
    POOL[_n] = np.argsort(_prng.random((POOL_P, _n)), axis=1)[:, :16].astype(np.int64)
