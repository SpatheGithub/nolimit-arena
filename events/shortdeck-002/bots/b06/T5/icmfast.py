"""Fast Malmuth-Harville equity of one player (top places only)."""


def icm_me(stacks, i, pay):
    """stacks: list of chip counts (zeros allowed), i: index, pay: points by place."""
    x = stacks[i]
    others = [s for j, s in enumerate(stacks) if j != i and s > 0]
    if x <= 0:
        k = len(others)
        return pay[k] if k < len(pay) else 0.0
    S = x + sum(others)
    n = len(others)
    p0 = pay[0] if len(pay) > 0 else 0.0
    p1 = pay[1] if len(pay) > 1 else 0.0
    p2 = pay[2] if len(pay) > 2 else 0.0
    p3 = pay[3] if len(pay) > 3 else 0.0
    e = p0 * x / S
    if n == 0:
        return p0
    for a in range(n):
        sa = others[a]
        pa = sa / S
        S1 = S - sa
        e += p1 * pa * x / S1
        if n < 2 or (p2 == 0 and p3 == 0):
            continue
        for b in range(n):
            if b == a:
                continue
            sb = others[b]
            pb = pa * sb / S1
            S2 = S1 - sb
            e += p2 * pb * x / S2
            if n < 3 or p3 == 0 or n >= 6:
                continue
            for c in range(n):
                if c == a or c == b:
                    continue
                sc = others[c]
                S3 = S2 - sc
                e += p3 * pb * sc / S2 * x / S3
    return e
