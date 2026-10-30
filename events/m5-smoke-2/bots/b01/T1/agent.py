import random
R = "23456789TJQKA"

def pre_score(h):
    a, b = sorted((R.index(h[0][0]), R.index(h[1][0])), reverse=True)
    s = a * 1.0 + b * 0.5
    if a == b:
        s = 14 + a * 2.0
    if h[0][1] == h[1][1]:
        s += 3
    gap = a - b
    if a != b and gap <= 2:
        s += 2 - gap * 0.5
    return s  # ~ 0..40; pair 22=14, AA=38

def post_score(h, board):
    cards = h + board
    cnt = {}
    for c in cards:
        cnt[c[0]] = cnt.get(c[0], 0) + 1
    suits = {}
    for c in cards:
        suits[c[1]] = suits.get(c[1], 0) + 1
    mx = max(cnt.values())
    pairs = sum(1 for v in cnt.values() if v == 2)
    hr = [R.index(c[0]) for c in h]
    bc = {}
    for c in board:
        bc[c[0]] = bc.get(c[0], 0) + 1
    bmax = max(bc.values())
    if max(suits.values()) >= 5 and any(suits[c[1]] >= 5 for c in h):
        return 0.9
    idx = sorted(set(R.index(c[0]) for c in cards))
    if 12 in idx: idx = [-1] + idx
    run = best = 1
    for i in range(1, len(idx)):
        run = run + 1 if idx[i] == idx[i-1] + 1 else 1
        best = max(best, run)
    if best >= 5: return 0.85
    if mx >= 4 and mx > bmax: return 0.95
    if mx == 3 and pairs >= 1 or (mx == 3 and len([v for v in cnt.values() if v >= 2]) >= 2): return 0.9
    if mx == 3: return 0.75 if mx > bmax else 0.3
    if pairs >= 2 and bmax < 2: return 0.7
    if pairs >= 2: return 0.45 if max(hr) > 8 else 0.3
    if mx == 2 and bmax < 2:
        top = max(R.index(c[0]) for c in board)
        p = cnt[[c[0] for c in h if cnt[c[0]] == 2][0]] and R.index([c[0] for c in h if cnt[c[0]] == 2][0])
        return 0.65 if p >= top else 0.45
    draw = 0
    if max(suits.values()) == 4 and any(suits[c[1]] == 4 for c in h): draw = 0.35
    if best == 4: draw = max(draw, 0.25)
    return max(draw, 0.1 + max(hr) * 0.01)

class Agent:
    def __init__(self, config):
        self.rng = random.Random(config["seed"])

    def act(self, obs):
        legal = obs["legal"]
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        h = obs["hole"]; tc = obs["to_call"]; pot = obs["pot"]
        mine = obs["stacks"][obs["seat"]]
        can_raise = "raise" in legal or "bet" in legal
        def rz(frac):
            amt = int(obs["bets"][obs["seat"]] + tc + frac * (pot + tc))
            amt = max(obs["min_raise_to"], min(amt, obs["max_raise_to"]))
            return {"action": "raise", "amount": amt}
        if obs["street"] == "preflop":
            s = pre_score(h)
            bb = obs["bb"]
            if s >= 30 and can_raise:
                return {"action": "allin"} if tc > 8 * bb or mine < 12 * bb else rz(0.8)
            if s >= 22:
                if tc <= 6 * bb: 
                    if can_raise and tc <= bb and self.rng.random() < 0.6: return rz(0.8)
                    return {"action": "call"} if "call" in legal else {"action": "check"}
                return {"action": "fold"}
            if s >= 16 and tc <= 2.5 * bb:
                return {"action": "call"} if "call" in legal else {"action": "check"}
            if "check" in legal: return {"action": "check"}
            return {"action": "fold"}
        s = post_score(h, obs["board"])
        if tc == 0:
            if s >= 0.65 and can_raise: return rz(0.65)
            if s >= 0.45 and can_raise and self.rng.random() < 0.4: return rz(0.5)
            return {"action": "check"}
        odds = tc / (pot + tc)
        if s >= 0.85 and can_raise: return rz(0.8)
        if s >= 0.6 and odds < 0.4: return {"action": "call"}
        if s >= 0.4 and odds < 0.25: return {"action": "call"}
        if s >= 0.25 and odds < 0.15: return {"action": "call"}
        return {"action": "fold"}

    def observe(self, event):
        pass
