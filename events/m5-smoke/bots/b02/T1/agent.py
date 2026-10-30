import random
R = "23456789TJQKA"

def pre(h):
    a, b = R.index(h[0][0]), R.index(h[1][0])
    hi, lo = max(a, b), min(a, b)
    s = 0.0
    if a == b:
        s = 0.5 + hi / 24.0 + 0.1
    else:
        s = (hi + lo * 0.5) / 30.0
        if h[0][1] == h[1][1]: s += 0.06
        if hi - lo <= 2: s += 0.04
    return s

def post(h, board):
    cs = [c[0] for c in h + board]
    cnt = {}
    for c in cs: cnt[c] = cnt.get(c, 0) + 1
    m = sorted(cnt.values(), reverse=True)
    bc = {}
    for c in board: bc[c[0]] = bc.get(c[0], 0) + 1
    bm = max(bc.values()) if bc else 1
    su = {}
    for c in h + board: su[c[1]] = su.get(c[1], 0) + 1
    flush = max(su.values()) >= 5
    idx = sorted(set(R.index(c) for c in cs))
    if 12 in idx: idx = [-1] + idx
    run = best = 1
    for i in range(1, len(idx)):
        run = run + 1 if idx[i] == idx[i-1] + 1 else 1
        best = max(best, run)
    if m[0] >= 4 or (m[0] == 3 and m[1] >= 2) or flush or best >= 5: return 0.95
    hr = max(R.index(h[0][0]), R.index(h[1][0]))
    if m[0] == 3 and bm < 3: return 0.85
    if m[0] == 2 and m[1] == 2 and bm < 2: return 0.75
    if m[0] == 2 and bm < 2:
        top = max(R.index(c) for c in [x[0] for x in board])
        pr = [R.index(c[0]) for c in h if cnt[c[0]] == 2]
        return 0.65 if pr and pr[0] >= top else 0.45
    if m[0] >= 2 and bm >= 2: return 0.25 + hr / 60.0 if m[0] > bm else 0.2
    fd = max(su.values()) == 4
    return 0.35 if (fd or best == 4) else 0.1 + hr / 80.0

class Agent:
    def __init__(self, config):
        self.rng = random.Random(config["seed"])

    def act(self, o):
        L = o["legal"]
        if o["phase"] == "discard":
            return {"action": "discard", "cards": o["hole"][:o["n_discard"]]}
        s = pre(o["hole"]) if not o["board"] else post(o["hole"], o["board"])
        tc = o["to_call"]; pot = o["pot"]
        me = o["stacks"][o["seat"]]
        canr = "raise" in L or "bet" in L
        def rz(f):
            amt = int(o["bets"][o["seat"]] + tc + pot * f) if tc else int(pot * f)
            amt = max(o["min_raise_to"], min(o["max_raise_to"], amt))
            return {"action": "raise", "amount": amt}
        pre_f = not o["board"]
        if tc == 0:
            if canr and s > (0.62 if pre_f else 0.55): return rz(0.7)
            if canr and s > 0.4 and self.rng.random() < 0.15: return rz(0.5)
            return {"action": "check"}
        odds = tc / (pot + tc)
        if s > 0.8 and canr: return rz(0.8) if tc < me else {"action": "allin"}
        if pre_f:
            if s > 0.66 and canr and tc <= o["bb"] * 4: return rz(0.8)
            need = 0.36 + min(0.3, tc / max(me, 1) * 0.6)
            return {"action": "call"} if s > need else {"action": "fold"}
        if s > odds + 0.2 or (s > 0.45 and tc < me * 0.3 and s > odds):
            return {"action": "call"}
        return {"action": "fold"}

    def observe(self, e):
        pass
