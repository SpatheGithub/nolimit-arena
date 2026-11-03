"""Shortdeck evaluator (flush > full house) + numpy Monte Carlo equity."""
import numpy as np

RANKS = "6789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
DECK = list(range(36))
HC, PAIR, TP, TRIPS, STR, FH, FL, QUADS, SF = range(9)

_STRAIGHTS = [(sum(1 << (i + k) for k in range(5)), i + 4) for i in range(5)]
_STRAIGHTS.append(((1 << 8) | 0b1111, 3))
_STRAIGHTS.sort(key=lambda t: -t[1])


def straight_top(mask):
    for sm, t in _STRAIGHTS:
        if mask & sm == sm:
            return t
    return -1


def _pack(rs):
    v = 0
    for r in rs:
        v = (v << 4) | r
    return v << (4 * (5 - len(rs)))


def value_counts(cnt):
    desc = [r for r in range(8, -1, -1) if cnt[r]]
    mask = 0
    for r in desc:
        mask |= 1 << r
    quads = [r for r in desc if cnt[r] >= 4]
    trips = [r for r in desc if cnt[r] == 3]
    pairs = [r for r in desc if cnt[r] == 2]
    if quads:
        q = quads[0]
        ks = [r for r in desc if r != q][:1]
        return QUADS << 20 | _pack([q] + ks)
    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        p = max(trips[1:] + pairs)
        return FH << 20 | _pack([t, p])
    st = straight_top(mask)
    if st >= 0:
        return STR << 20 | st << 16
    if trips:
        t = trips[0]
        return TRIPS << 20 | _pack([t] + [r for r in desc if r != t][:2])
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return TP << 20 | _pack([p1, p2] + [r for r in desc if r not in (p1, p2)][:1])
    if pairs:
        p = pairs[0]
        return PAIR << 20 | _pack([p] + [r for r in desc if r != p][:3])
    return HC << 20 | _pack(desc[:5])


def value_suited(mask):
    if bin(mask).count("1") < 5:
        return -1
    st = straight_top(mask)
    if st >= 0:
        return SF << 20 | st << 16
    desc = [r for r in range(8, -1, -1) if mask >> r & 1]
    return FL << 20 | _pack(desc[:5])


POW5 = [5 ** r for r in range(9)]
START = 0x3333
KEY = [(POW5[c >> 2] << 16) | (1 << (4 * (c & 3))) for c in range(36)]
RBIT = [1 << (c >> 2) for c in range(36)]

RT = np.full(5 ** 9, -1, dtype=np.int32)
RTD = {}


def _build():
    cnt = [0] * 9

    def rec(r, n, code):
        if r == 9:
            if n >= 5:
                v = value_counts(cnt)
                RT[code] = v
                RTD[code] = v
            return
        for k in range(0, min(4, 7 - n) + 1):
            cnt[r] = k
            rec(r + 1, n + k, code + k * POW5[r])
        cnt[r] = 0
    rec(0, 0, 0)


_build()
SUITED = np.array([value_suited(m) for m in range(512)], dtype=np.int32)
SUITEDL = SUITED.tolist()
# low 16 bits of key sum -> flush suit or -1
FSUIT = np.full(1 << 16, -1, dtype=np.int64)
for _x in range(1 << 16):
    _f = _x & 0x8888
    if _f:
        FSUIT[_x] = (_f.bit_length() - 4) // 4
KEY_NP = np.array(KEY, dtype=np.int64)
RBIT_NP = np.array(RBIT, dtype=np.int64)
SUIT_NP = np.array([c & 3 for c in range(36)], dtype=np.int64)


def ev_cards(cards):
    """Best value of 5..7 cards (python)."""
    s = START
    for c in cards:
        s += KEY[c]
    v = RTD[s >> 16]
    f = s & 0x8888
    if f:
        suit = (f.bit_length() - 4) // 4
        m = 0
        for c in cards:
            if c & 3 == suit:
                m |= 1 << (c >> 2)
        fv = SUITEDL[m]
        if fv > v:
            v = fv
    return v


def ev_np(keysum, cards):
    """Vectorized: keysum (M,) int64 sums from START, cards (M,k) int ids."""
    v = RT[keysum >> 16]
    fs = FSUIT[keysum & 0xFFFF]
    fl = fs >= 0
    if fl.any():
        idx = np.nonzero(fl)[0]
        cs = cards[idx]
        m = ((SUIT_NP[cs] == fs[idx, None]) * RBIT_NP[cs]).sum(axis=1)
        sv = SUITED[m]
        v = v.copy()
        v[idx] = np.maximum(v[idx], sv)
    return v


# preflop class: pair hi*9+hi, suited hi*9+lo, offsuit lo*9+hi
def cls_of(a, b):
    ra, rb = a >> 2, b >> 2
    if ra == rb:
        return ra * 9 + ra
    hi, lo = (ra, rb) if ra > rb else (rb, ra)
    return hi * 9 + lo if (a & 3) == (b & 3) else lo * 9 + hi


CLS = np.zeros((36, 36), dtype=np.int64)
for _a in range(36):
    for _b in range(36):
        if _a != _b:
            CLS[_a, _b] = cls_of(_a, _b)


def mc_equity(rng, hole, board, opp_w, M=200):
    """Equity of hole vs len(opp_w) opponents. opp_w: list of (81,) class weight
    arrays (or None = uniform) used as importance weights; plus postflop made
    hand weights handled by caller via board. Returns (equity, n_eff)."""
    known = set(hole) | set(board)
    rem = np.array([c for c in DECK if c not in known], dtype=np.int64)
    n_opp = len(opp_w)
    need = 5 - len(board)
    k = 2 * n_opp + need
    R = len(rem)
    perm = rng.random((M, R)).argsort(axis=1)[:, :k]
    drawn = rem[perm]
    bk = START + sum(KEY[c] for c in board)
    if need:
        bcards = drawn[:, 2 * n_opp:]
        bsum = bk + KEY_NP[bcards].sum(axis=1)
    else:
        bcards = np.zeros((M, 0), dtype=np.int64)
        bsum = np.full(M, bk, dtype=np.int64)
    board_arr = np.array(board, dtype=np.int64)
    if len(board):
        ball = np.concatenate([np.broadcast_to(board_arr, (M, len(board))), bcards], axis=1)
    else:
        ball = bcards
    hk = KEY[hole[0]] + KEY[hole[1]]
    hcards = np.concatenate([np.broadcast_to(np.array(hole, dtype=np.int64), (M, 2)), ball], axis=1)
    hv = ev_np(bsum + hk, hcards)
    w = np.ones(M)
    best = np.full(M, -2, dtype=np.int64)
    nbest = np.zeros(M)
    for i in range(n_opp):
        o = drawn[:, 2 * i:2 * i + 2]
        ow = opp_w[i]
        if ow is not None:
            w = w * ow[CLS[o[:, 0], o[:, 1]]]
        ov = ev_np(bsum + KEY_NP[o].sum(axis=1), np.concatenate([o, ball], axis=1))
        gt = ov > best
        eq = ov == best
        nbest = np.where(gt, 1, np.where(eq, nbest + 1, nbest))
        best = np.maximum(best, ov)
    win = np.where(hv > best, 1.0, np.where(hv == best, 1.0 / (nbest + 1), 0.0))
    sw = w.sum()
    if sw <= 1e-9:
        return float(win.mean()), M
    return float((win * w).sum() / sw), float(sw * sw / (w * w).sum())
