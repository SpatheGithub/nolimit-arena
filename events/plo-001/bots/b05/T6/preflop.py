"""Heuristic PLO starting-hand score, calibrated to a percentile (0 = best)."""
import bisect
import random


def pre_score(hole):
    rs = [c >> 2 for c in hole]
    ss = [c & 3 for c in hole]
    score = 0.0
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    for r, n in cnt.items():
        if n == 2:
            score += 2.0 + 0.6 * r + (6.0 if r == 12 else 3.0 if r == 11 else 1.5 if r == 10 else 0.0)
        elif n == 3:
            score += 1.0 + 0.3 * r
        elif n == 4:
            score -= 2.0
    for s in range(4):
        cs = [rs[i] for i in range(4) if ss[i] == s]
        k = len(cs)
        if k >= 2:
            hi = max(cs)
            b = 3.0 + (3.0 if hi == 12 else 1.5 if hi == 11 else 1.0 if hi == 10 else 0.5 if hi >= 8 else 0.0)
            if k == 3:
                b *= 0.6
            elif k == 4:
                b *= 0.25
            score += b
    d = sorted(cnt, reverse=True)
    conn = 0
    nd = len(d)
    for i in range(nd):
        for j in range(i + 1, nd):
            g = d[i] - d[j]
            if g <= 4:
                conn += 5 - g
            elif d[i] == 12 and d[j] <= 3:
                g2 = d[j] + 1
                conn += max(0, 5 - g2) * 0.5
    score += 0.55 * conn
    score += 0.45 * sum(max(0, r - 7) for r in rs)
    return score


def _calibrate():
    rng = random.Random(987654)
    deck = list(range(52))
    scores = []
    for _ in range(30000):
        scores.append(pre_score(rng.sample(deck, 4)))
    scores.sort()
    return scores


_SORTED = _calibrate()
_N = len(_SORTED)


def pre_pct(hole):
    """Fraction of random hands scoring strictly better (0 = best)."""
    s = pre_score(hole)
    i = bisect.bisect_right(_SORTED, s)
    return 1.0 - i / _N
