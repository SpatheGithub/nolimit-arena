import random
from collections import Counter
R = "23456789TJQKA"

def pre(h):
    a, b = sorted((R.index(h[0][0]), R.index(h[1][0])), reverse=True)
    s = h[0][1] == h[1][1]
    v = (a + 2) * 1.0
    if a == b:
        return 10 + a * 1.5
    v = a * 1.0 + b * 0.5
    if s: v += 2
    if a - b == 1: v += 1.5
    return v

def post(h, bd):
    cs = Counter(c[0] for c in h + bd)
    m = sorted(cs.values(), reverse=True)
    sc = Counter(c[1] for c in h + bd)
    hr = [R.index(c[0]) for c in h]
    if m[0] >= 4: return 5
    if m[0] == 3 and m[1] >= 2: return 5
    if max(sc.values()) >= 5: return 4
    if m[0] == 3: return 3.5
    if m[0] == 2 and m[1] == 2: return 3
    if m[0] == 2:
        pr = [r for r in cs if cs[r] == 2][0]
        if pr in (c[0] for c in h):
            top = max(R.index(c[0]) for c in bd)
            return 2 if R.index(pr) >= top else 1.5
        return 0.5
    return 0.3 + max(hr) / 40

class Agent:
    def __init__(self, config):
        self.rng = random.Random(config["seed"])

    def act(self, o):
        L = o["legal"]
        if o["phase"] == "discard":
            return {"action": "discard", "cards": o["hole"][:o["n_discard"]]}
        tc = o["to_call"]; pot = o["pot"]
        if o["street_index"] == 0:
            s = pre(o["hole"])
            strong = s >= 16; ok = s >= 15
            if strong:
                if "raise" in L:
                    return {"action": "raise", "amount": min(o["max_raise_to"], max(o["min_raise_to"], o["bb"] * 3 + tc))}
                return {"action": "call"}
            if ok and tc <= o["bb"] * 4:
                return {"action": "call"} if tc else {"action": "check"}
        else:
            s = post(o["hole"], o["board"])
            if s >= 3 and "raise" in L:
                return {"action": "raise", "amount": min(o["max_raise_to"], max(o["min_raise_to"], int(o["bets"][o["seat"]] + tc + pot * 0.7)))}
            if s >= 3 and tc: return {"action": "call"}
            if s >= 1.5:
                if tc <= pot * 0.6: return {"action": "call"} if tc else {"action": "check"}
        if "check" in L: return {"action": "check"}
        return {"action": "fold"}

    def observe(self, e):
        pass
