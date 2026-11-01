"""Exact equity tables for the royal variant (ranks T J Q K A, 4 suits).
Suits are ignored (flush impossible; straight flush ~0.16% handled at runtime).
Everything is computed at import from rank counts (fast: < 1 s)."""
from itertools import combinations_with_replacement as cwr

NR = 5
RIDX = {'T': 0, 'J': 1, 'Q': 2, 'K': 3, 'A': 4}


def val6(c):
    quad = -1
    trips = []
    pairs = []
    for r in range(4, -1, -1):
        n = c[r]
        if n >= 4:
            quad = r
        elif n == 3:
            trips.append(r)
        elif n == 2:
            pairs.append(r)
    if quad >= 0:
        ks = [r for r in range(5) if r != quad and c[r] > 0]
        return (7 << 12) | (quad << 4) | (max(ks) if ks else 0)
    if trips:
        t = trips[0]
        rest = trips[1:] + pairs
        if rest:
            return (6 << 12) | (t << 4) | max(rest)
    if all(c[r] >= 1 for r in range(5)):
        return 4 << 12
    if trips:
        t = trips[0]
        ks = sorted([r for r in range(5) if r != t and c[r] > 0], reverse=True)
        ks = (ks + [0, 0])[:2]
        return (3 << 12) | (t << 8) | (ks[0] << 4) | ks[1]
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        ks = [r for r in range(5) if r not in (p1, p2) and c[r] > 0]
        return (2 << 12) | (p1 << 8) | (p2 << 4) | (max(ks) if ks else 0)
    if len(pairs) == 1:
        p = pairs[0]
        ks = sorted([r for r in range(5) if r != p and c[r] > 0], reverse=True)
        ks = (ks + [0, 0, 0])[:3]
        return (1 << 12) | (p << 8) | (ks[0] << 4) | ks[1]
    return 0


def _counts(cards):
    c = [0] * 5
    for r in cards:
        c[r] += 1
    return c


VAL = {}
for _combo in cwr(range(5), 6):
    _c = _counts(_combo)
    if max(_c) <= 4:
        VAL[tuple(_c)] = val6(_c)

CLASSES = [(a, b) for a in range(5) for b in range(a, 5)]


def _c2(n):
    return n * (n - 1) // 2 if n >= 2 else 0


def _choose(n, k):
    if k == 0:
        return 1
    if k == 1:
        return n
    if k == 2:
        return _c2(n)
    if k == 3:
        return n * (n - 1) * (n - 2) // 6 if n >= 3 else 0
    if k == 4:
        return 1 if n == 4 else 0
    return 0


def _ms_weight(ms, rem):
    c = _counts(ms)
    w = 1
    for r in range(5):
        if c[r]:
            w *= _choose(rem[r], c[r])
            if w == 0:
                return 0
    return w


def _add(*vs):
    return tuple(sum(x) for x in zip(*vs))


def _feasible(*vs):
    s = _add(*vs)
    return max(s) <= 4


CC = {cl: tuple(_counts(cl)) for cl in CLASSES}
BOARDS3 = [b for b in cwr(range(5), 3)]
BOARDS4 = [b for b in cwr(range(5), 4)]
BC3 = {b: tuple(_counts(b)) for b in BOARDS3}
BC4 = {b: tuple(_counts(b)) for b in BOARDS4}
ZERO = (0, 0, 0, 0, 0)


def _opp_weight(o, rem):
    a, b = o
    if a == b:
        return _c2(rem[a])
    return rem[a] * rem[b]


def _rem(*vs):
    s = _add(*vs)
    return [4 - x for x in s]


# ---------------- turn (board complete: 4 cards) ----------------
EQT1 = {}
_TRAW = {}
for h in CLASSES:
    hc = CC[h]
    for b in BOARDS4:
        bc = BC4[b]
        if not _feasible(hc, bc):
            continue
        rem = _rem(hc, bc)
        vh = VAL[_add(hc, bc)]
        tot = 0
        acc = 0.0
        lst = []
        for o in CLASSES:
            w = _opp_weight(o, rem)
            if w <= 0:
                continue
            vo = VAL[_add(CC[o], bc)]
            r = 1.0 if vh > vo else (0.5 if vh == vo else 0.0)
            tot += w
            acc += w * r
            lst.append((o, w, r))
        EQT1[(h, b)] = acc / tot
        _TRAW[(h, b)] = lst
TURN = {}
for key, lst in _TRAW.items():
    b = key[1]
    srt = sorted(lst, key=lambda x: -EQT1[(x[0], b)])
    tot = float(sum(x[1] for x in srt))
    TURN[key] = (EQT1[key], tuple((x[1] / tot, x[2]) for x in srt))
del _TRAW

# ---------------- flop (3 board cards, one to come) ----------------
EQF1 = {}
_FRAW = {}
for h in CLASSES:
    hc = CC[h]
    for f in BOARDS3:
        fc = BC3[f]
        if not _feasible(hc, fc):
            continue
        rem = _rem(hc, fc)
        hf = _add(hc, fc)
        tot = 0
        acc = 0.0
        lst = []
        for o in CLASSES:
            w = _opp_weight(o, rem)
            if w <= 0:
                continue
            oc = CC[o]
            of = _add(oc, fc)
            rem2 = list(rem)
            rem2[o[0]] -= 1
            rem2[o[1]] -= 1
            tw = 0
            ta = 0.0
            for t in range(5):
                n = rem2[t]
                if n <= 0:
                    continue
                tc = [0, 0, 0, 0, 0]
                tc[t] = 1
                tc = tuple(tc)
                vh = VAL[_add(hf, tc)]
                vo = VAL[_add(of, tc)]
                ta += n * (1.0 if vh > vo else (0.5 if vh == vo else 0.0))
                tw += n
            r = ta / tw
            tot += w
            acc += w * r
            lst.append((o, w, r))
        EQF1[(h, f)] = acc / tot
        _FRAW[(h, f)] = lst
FLOP = {}
for key, lst in _FRAW.items():
    f = key[1]
    srt = sorted(lst, key=lambda x: -EQF1[(x[0], f)])
    tot = float(sum(x[1] for x in srt))
    FLOP[key] = (EQF1[key], tuple((x[1] / tot, x[2]) for x in srt))
del _FRAW

# ---------------- preflop (heads-up, exact) ----------------
PRE = {}
for h in CLASSES:
    hc = CC[h]
    for o in CLASSES:
        oc = CC[o]
        if not _feasible(hc, oc):
            continue
        rem = _rem(hc, oc)
        ho = _add(hc, oc)
        tw = 0
        ta = 0.0
        for b in BOARDS4:
            w = _ms_weight(b, rem)
            if w <= 0:
                continue
            bc = BC4[b]
            vh = VAL[_add(hc, bc)]
            vo = VAL[_add(oc, bc)]
            ta += w * (1.0 if vh > vo else (0.5 if vh == vo else 0.0))
            tw += w
        PRE[(h, o)] = ta / tw

CLASS_W = {cl: (6 if cl[0] == cl[1] else 16) for cl in CLASSES}
PRE1 = {}
for h in CLASSES:
    rem = _rem(CC[h])
    tot = 0
    acc = 0.0
    for o in CLASSES:
        w = _opp_weight(o, rem)
        if w <= 0 or (h, o) not in PRE:
            continue
        tot += w
        acc += w * PRE[(h, o)]
    PRE1[h] = acc / tot

# order of classes by strength, and percentile (0 = best)
PRE_ORDER = sorted(CLASSES, key=lambda c: -PRE1[c])
PRE_PCT = {}
_acc = 0
for _c in PRE_ORDER:
    w = CLASS_W[_c]
    PRE_PCT[_c] = (_acc + w / 2.0) / 190.0
    _acc += w
PRE_TOP = {}
_acc = 0
for _c in PRE_ORDER:
    _acc += CLASS_W[_c]
    PRE_TOP[_c] = _acc / 190.0  # fraction of hands at least this strong

PRELIST = {}
for h in CLASSES:
    rem = _rem(CC[h])
    lst = []
    for o in PRE_ORDER:
        w = _opp_weight(o, rem)
        if w <= 0 or (h, o) not in PRE:
            continue
        lst.append((w, PRE[(h, o)]))
    tot = float(sum(x[0] for x in lst))
    PRELIST[h] = tuple((x[0] / tot, x[1]) for x in lst)


def eq_vs_top(lst, frac):
    """lst: ((weight_frac, eq), ...) sorted strongest opp first; equity vs top frac."""
    if frac >= 0.999:
        frac = 1.0
    if frac < 0.02:
        frac = 0.02
    acc_w = 0.0
    acc_e = 0.0
    for w, e in lst:
        if acc_w + w >= frac:
            part = frac - acc_w
            acc_e += part * e
            acc_w = frac
            break
        acc_w += w
        acc_e += w * e
    if acc_w <= 0:
        return 0.5
    return acc_e / acc_w
