import random
R = "23456789TJQKA"
V = {c: i for i, c in enumerate(R)}


def pre(h):
    a, b = V[h[0][0]], V[h[1][0]]
    hi, lo = max(a, b), min(a, b)
    s = hi * 1.0 + lo * 0.5
    if a == b:
        s = 14 + hi * 2.0
    if h[0][1] == h[1][1]:
        s += 3
    g = hi - lo
    if g == 1: s += 2
    elif g == 2: s += 1
    return s  # ~ 6..40


def post(h, board):
    cards = h + board
    rc = {}
    sc = {}
    for c in cards:
        rc[c[0]] = rc.get(c[0], 0) + 1
        sc[c[1]] = sc.get(c[1], 0) + 1
    cnt = sorted(rc.values(), reverse=True)
    flush = max(sc.values()) >= 5
    vs = sorted({V[c[0]] for c in cards})
    if 12 in vs: vs.append(-1)
    vs.sort()
    run = best = 1
    for i in range(1, len(vs)):
        run = run + 1 if vs[i] == vs[i-1] + 1 else 1
        best = max(best, run)
    if flush or best >= 5 or cnt[0] >= 4 or (cnt[0] == 3 and cnt[1] >= 2):
        return 4
    if cnt[0] == 3 or cnt[:2] == [2, 2] or (len(cnt) > 2 and cnt[:3] == [2, 2, 2]):
        return 3
    if cnt[0] == 2:
        hv = {V[c[0]] for c in h}
        pair = [r for r, n in rc.items() if n == 2][0]
        top = max(V[c[0]] for c in board)
        if V[pair] in hv and V[pair] >= top:
            return 2.5
        if V[pair] in hv:
            return 2
        return 1
    return 0


class Agent:
    def __init__(self, config):
        self.rng = random.Random(config["seed"])

    def act(self, o):
        L = o["legal"]
        h = o["hole"]
        tc = o["to_call"]
        pot = o["pot"]
        bb = o["bb"]
        if o["street"] == "preflop":
            s = pre(h)
            st = 0
            if s >= 30: st = 3
            elif s >= 22: st = 2
            elif s >= 17: st = 1
        else:
            p = post(h, o["board"])
            st = 3 if p >= 3 else 2 if p >= 2.5 else 1 if p >= 2 else 0
            if p == 1 and tc <= pot * 0.2: st = 1
            if p == 0 and tc == 0 and self.rng.random() < 0.2: st = 2
        big = tc > 0.5 * max(pot - tc, 1) and tc > 4 * bb
        if "raise" in L and (st == 3 or (st == 2 and tc <= 3 * bb and self.rng.random() < 0.6)):
            amt = int(max(o["min_raise_to"], min(o["max_raise_to"], o["bets"][o["seat"]] + tc + pot * 0.7)))
            if st == 3 and amt >= o["max_raise_to"] * 0.4:
                return {"action": "allin"}
            return {"action": "raise", "amount": amt}
        if tc == 0:
            return {"action": "check"}
        if st >= 3 or (st == 2 and not big) or (st == 1 and tc <= 3 * bb and not big):
            return {"action": "call"}
        return {"action": "fold"}

    def observe(self, e):
        pass
