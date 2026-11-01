import json
import os
import random

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre.json")))
VAL = _D["VAL"]
HU = _D["HU"]
MW = _D["MW"]
FE = {int(k): v for k, v in _D["FE"].items()}
CLS = [tuple(c) for c in _D["CLS"]]
CIDX = {c: i for i, c in enumerate(CLS)}
P5 = [1, 5, 25, 125, 625]
RANKS = "TJQKA"
BASE_COMBOS = [6 if a == b else 16 for a, b in CLS]
# strength order by HU equity vs random
HU_RAND = []
for i in range(15):
    s = w = 0.0
    for j in range(15):
        if HU[i][j] >= 0:
            s += HU[i][j] * BASE_COMBOS[j]
            w += BASE_COMBOS[j]
    HU_RAND.append(s / w)
ORDER = sorted(range(15), key=lambda i: -HU_RAND[i])
# percentile (fraction of combos stronger or equal), top = small
PCT = [0.0] * 15
_acc = 0
for i in ORDER:
    _acc += BASE_COMBOS[i]
    PCT[i] = _acc / 190.0


def top_range(f):
    """weights over classes for top fraction f of hands"""
    w = [0.0] * 15
    acc = 0.0
    tgt = max(0.03, min(1.0, f)) * 190.0
    for i in ORDER:
        c = BASE_COMBOS[i]
        if acc + c <= tgt:
            w[i] = 1.0
        elif acc < tgt:
            w[i] = (tgt - acc) / c
        acc += c
    return w


RANGE_CACHE = {}


def get_range(f):
    k = int(round(f * 40))
    r = RANGE_CACHE.get(k)
    if r is None:
        r = top_range(k / 40.0)
        RANGE_CACHE[k] = r
    return r


def eq_vs_range_pre(ci, w):
    """preflop HU equity of class ci vs range weights w, with card removal"""
    a, b = CLS[ci]
    cnt = [4] * 5
    cnt[a] -= 1
    cnt[b] -= 1
    s = t = 0.0
    for j in range(15):
        wj = w[j]
        if wj <= 0:
            continue
        c, d = CLS[j]
        if c == d:
            n = cnt[c] * (cnt[c] - 1) / 2
        else:
            n = cnt[c] * cnt[d]
        if n <= 0:
            continue
        x = n * wj
        s += x * HU[ci][j]
        t += x
    return s / t if t > 0 else 0.5


def post_equity(hole, board, w):
    """equity (win + tie/2) of hole ranks vs one opponent with class weights w,
    board 3 or 4 ranks."""
    cnt = [4] * 5
    for r in hole:
        cnt[r] -= 1
    bk = 0
    for r in board:
        cnt[r] -= 1
        bk += P5[r]
    hk = P5[hole[0]] + P5[hole[1]]
    s = t = 0.0
    if len(board) >= 4:
        mv = VAL[bk + hk]
        for j in range(15):
            wj = w[j]
            if wj <= 0:
                continue
            c, d = CLS[j]
            if c == d:
                n = cnt[c] * (cnt[c] - 1) / 2
            else:
                n = cnt[c] * cnt[d]
            if n <= 0:
                continue
            x = n * wj
            ov = VAL[bk + P5[c] + P5[d]]
            if mv > ov:
                s += x
            elif mv == ov:
                s += 0.5 * x
            t += x
        return s / t if t > 0 else 0.5
    for r in range(5):
        nr = cnt[r]
        if nr <= 0:
            continue
        cnt[r] -= 1
        bk2 = bk + P5[r]
        mv = VAL[bk2 + hk]
        for j in range(15):
            wj = w[j]
            if wj <= 0:
                continue
            c, d = CLS[j]
            if c == d:
                n = cnt[c] * (cnt[c] - 1) / 2
            else:
                n = cnt[c] * cnt[d]
            if n <= 0:
                continue
            x = n * wj * nr
            ov = VAL[bk2 + P5[c] + P5[d]]
            if mv > ov:
                s += x
            elif mv == ov:
                s += 0.5 * x
            t += x
        cnt[r] += 1
    return s / t if t > 0 else 0.5


def narrow_turn(hole, board, w, g):
    """keep the top-g fraction (by final hand value, or flop equity on a
    3-card board) of range w"""
    cnt = [4] * 5
    for r in hole:
        cnt[r] -= 1
    bk = 0
    for r in board:
        cnt[r] -= 1
        bk += P5[r]
    fe = FE.get(bk) if len(board) == 3 else None
    items = []
    tot = 0.0
    for j in range(15):
        wj = w[j]
        if wj <= 0:
            continue
        c, d = CLS[j]
        if c == d:
            n = cnt[c] * (cnt[c] - 1) / 2
        else:
            n = cnt[c] * cnt[d]
        if n <= 0:
            continue
        x = n * wj
        items.append((fe[j] if fe is not None else VAL[bk + P5[c] + P5[d]], j, x))
        tot += x
    if tot <= 0:
        return w
    items.sort(reverse=True)
    tgt = g * tot
    acc = 0.0
    out = [0.0] * 15
    for v, j, x in items:
        if acc >= tgt:
            break
        take = min(x, tgt - acc)
        out[j] = w[j] * take / x
        acc += take
    return out


def cls_of(hole):
    a, b = hole
    if a > b:
        a, b = b, a
    return CIDX[(a, b)]


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.nseats = config.get("seats", 8)
        self.st = {}  # seat -> stats dict

    def stat(self, s):
        d = self.st.get(s)
        if d is None:
            d = {"h": 0, "vpip": 0, "pfr": 0, "agg": 0, "pas": 0}
            self.st[s] = d
        return d

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for h in hist:
                si, s, a = h[0], h[1], h[2]
                if a in ("ante", "return"):
                    continue
                seen.add(s)
                if si == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        self.stat(s)["agg"] += 1
                    elif a == "call":
                        self.stat(s)["pas"] += 1
            for s in seen:
                d = self.stat(s)
                d["h"] += 1
                if s in vp:
                    d["vpip"] += 1
                if s in pr:
                    d["pfr"] += 1
        except Exception:
            pass

    def pfr(self, s):
        d = self.st.get(s)
        prior_n, prior = 6.0, 0.22
        if d is None:
            return prior
        return (d["pfr"] + prior * prior_n) / (d["h"] + prior_n)

    def vpip(self, s):
        d = self.st.get(s)
        prior_n, prior = 6.0, 0.4
        if d is None:
            return prior
        return (d["vpip"] + prior * prior_n) / (d["h"] + prior_n)

    def aggr(self, s):
        d = self.st.get(s)
        if d is None:
            return 0.5
        return (d["agg"] + 1.0) / (d["agg"] + d["pas"] + 2.0)

    # ------------------------------------------------------------------
    def act(self, obs):
        try:
            a = self.decide(obs)
            return self.legalize(obs, a)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def legalize(self, obs, a):
        legal = obs["legal"]
        act = a["action"]
        if act == "raise":
            if "raise" not in legal and "bet" not in legal:
                return {"action": "call"} if "call" in legal else {"action": "check"}
            amt = int(a["amount"])
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if amt >= hi * 0.85:
                amt = hi
            amt = max(lo, min(hi, amt))
            return {"action": "raise", "amount": amt}
        if act == "allin":
            return {"action": "allin"}
        if act == "call":
            if "call" in legal:
                return {"action": "call"}
            return {"action": "check"}
        if act == "fold":
            if "check" in legal:
                return {"action": "check"}
            return {"action": "fold"}
        if act == "check":
            if "check" in legal:
                return {"action": "check"}
            return {"action": "fold"}
        return a

    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [RANKS.index(c[0]) for c in obs["hole"]]
        board = [RANKS.index(c[0]) for c in obs["board"]]
        if obs["street_index"] == 0:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    # ------------------------------------------------------------------
    def seat_order(self, obs):
        alive = sorted(obs["alive"])
        return alive

    def preflop(self, obs, hole):
        me = obs["seat"]
        bb = obs["bb"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_stack = stacks[me]
        ci = cls_of(hole)
        in_hand = [s for s in obs["in_hand"] if s != me]
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        callers = [h for h in hist if h[0] == 0 and h[2] == "call"]
        # players yet to act behind me (not folded, haven't acted voluntarily)
        acted = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise", "fold", "check"))
        alive = sorted(obs["alive"])
        n = len(alive)
        # order preflop: from left of BB around to BB
        bbs = obs["bb_seat"]
        if bbs in alive:
            k = alive.index(bbs)
        else:
            k = 0
        order = [alive[(k + 1 + i) % n] for i in range(n)]
        if me in order:
            my_idx = order.index(me)
        else:
            my_idx = 0
        behind = [s for s in order[my_idx + 1:] if s in obs["in_hand"] and s not in acted]
        n_behind = len(behind)
        others_stack = max([stacks[s] + bets[s] for s in in_hand] or [0])
        eff = min(my_stack + bets[me], others_stack)
        eff_bb = eff / float(bb)
        my_bb = (my_stack + bets[me]) / float(bb)
        strength = HU_RAND[ci]
        pct = PCT[ci]  # fraction of hands at least as strong

        if not raises:
            # first in (maybe limpers)
            n_limp = len(callers)
            if eff_bb <= 14:
                # push / fold
                ev = self.push_ev(ci, obs, behind, eff, pot)
                if ev > 0:
                    return {"action": "allin"}
                if to_call == 0:
                    return {"action": "check"}
                return {"action": "fold"}
            # open raise ranges by players behind
            if n_behind >= 5:
                thr = 0.40
            elif n_behind >= 3:
                thr = 0.50
            elif n_behind == 2:
                thr = 0.60
            else:
                thr = 0.75
            if n <= 2:
                thr = 0.8 if n_behind == 1 else 0.6
            elif n == 3:
                thr += 0.08
            if n_limp:
                thr -= 0.08
            if pct <= thr:
                size = bb * (2.5 + n_limp) if n_behind > 1 else bb * 2.5
                if self.rng.random() < 0.05 and pct > 0.15:
                    size = bb * 2.5
                return {"action": "raise", "amount": size}
            if to_call == 0:
                return {"action": "check"}
            # complete small blind cheaply with decent hands
            if to_call <= bb * 0.5 and (pct <= 0.75 or n <= 2) and n_behind <= 1:
                return {"action": "call"}
            return {"action": "fold"}

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        raise_to = last[3]
        n_raises = len(raises)
        rstack = stacks[raiser] + bets[raiser]
        allin = stacks[raiser] == 0
        # estimate raiser's range
        f = self.pfr(raiser)
        if allin:
            f = max(f, min(1.0, 0.2 + 3.0 / max(1.0, rstack / float(bb))))
        f = f * (0.6 ** (n_raises - 1))
        # big raises relative to stacks are a bit stronger unless loose
        f = max(0.06, min(1.0, f))
        w = get_range(f)
        eq = eq_vs_range_pre(ci, w)
        # other players already in (callers after raise) reduce equity
        n_extra = 0
        for h in hist:
            if h[0] == 0 and h[2] == "call":
                n_extra += 1
        n_extra = min(n_extra, 3)
        eq_m = eq * (0.82 ** n_extra) if n_extra else eq
        call_amt = min(to_call, my_stack)
        final_pot = pot + call_amt
        need = call_amt / float(final_pot + 0.0)
        # when calling commits most of my stack treat as all-in decision
        commit = call_amt >= 0.4 * (my_stack + bets[me]) or allin
        # strong: reraise
        if eq_m > 0.62 or (pct <= 0.08):
            if my_bb <= 30 or n_raises >= 2:
                return {"action": "allin"}
            return {"action": "raise", "amount": raise_to * 3 + sum(h[3] for h in callers) * 0}
        if commit:
            if eq_m > need + 0.015:
                return {"action": "allin"}
            return {"action": "fold"}
        # non-commit call: need equity plus postflop disadvantage margin
        if eq_m > need + 0.04 and eq_m > 0.35:
            # occasionally shove short-ish stacks as resteal
            if my_bb <= 25 and eq_m > 0.47:
                return {"action": "allin"}
            return {"action": "call"}
        if to_call == 0:
            return {"action": "check"}
        return {"action": "fold"}

    def push_ev(self, ci, obs, behind, eff, pot):
        stacks = obs["stacks"]
        bets = obs["bets"]
        bb = obs["bb"]
        me = obs["seat"]
        risk = min(stacks[me], eff)
        pf = 1.0
        ev_called = 0.0
        p_called_tot = 0.0
        for s in behind:
            sbb = (stacks[s] + bets[s]) / float(bb)
            # calling range: wider when my shove is small relative to their stack
            my_bb = (stacks[me] + bets[me]) / float(bb)
            c = 0.18 + 0.12 * min(1.0, 8.0 / max(my_bb, 1.0))
            c *= (self.vpip(s) / 0.4) ** 0.5
            c = max(0.08, min(0.8, c))
            w = get_range(c)
            eq = eq_vs_range_pre(ci, w)
            r = min(risk, stacks[s] + bets[s] - bets[me]) if stacks[s] + bets[s] > bets[me] else risk
            r = max(0, min(risk, r))
            win = eq * (pot + r + (r + bets[me] - bets[s])) - r
            ev_called += pf * c * win
            p_called_tot += pf * c
            pf *= (1 - c)
        return pf * pot + ev_called

    # ------------------------------------------------------------------
    def opp_range(self, obs, s):
        hist = obs["history"]
        raised = False
        called = False
        for h in hist:
            if h[0] == 0 and h[1] == s:
                if h[2] == "raise":
                    raised = True
                elif h[2] == "call":
                    called = True
        if raised:
            return get_range(max(0.15, min(1.0, self.pfr(s) * 1.1)))
        if called:
            return get_range(max(0.3, min(1.0, self.vpip(s) * 1.1)))
        return get_range(1.0)

    def postflop(self, obs, hole, board):
        me = obs["seat"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks = obs["stacks"]
        my_stack = stacks[me]
        opps = [s for s in obs["in_hand"] if s != me]
        nopp = max(1, len(opps))
        street = obs["street_index"]
        # straight flush check for me
        if self.has_sf(obs):
            eq = 1.0
        else:
            # equity vs the tightest opponent range, raised to power for multiway
            eqs = []
            for s in opps[:3]:
                eqs.append(post_equity(hole, board, self.opp_range(obs, s)))
            eqs.sort()
            eq = eqs[0] if eqs else 0.5
            if nopp > 1:
                rest = 1.0
                for e in eqs[1:]:
                    rest *= e
                for _ in range(nopp - len(eqs)):
                    rest *= eqs[-1] if eqs else 0.5
                eq = eq * rest
        hist = obs["history"]
        st_actions = [h for h in hist if h[0] == street]
        bettor = None
        for h in st_actions:
            if h[2] == "raise":
                bettor = h[1]
        eff = max([stacks[s] for s in opps] or [0])
        eff = min(eff, my_stack)
        if to_call == 0:
            # bet for value / semi-bluff
            if eq > 0.62 or (nopp == 1 and eq > 0.55):
                frac = 0.7 if eq < 0.75 else 1.0
                amt = pot * frac
                if amt >= eff * 0.6:
                    return {"action": "allin"}
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(amt))}
            # bluff: heads-up, I was preflop raiser, sometimes
            if nopp == 1 and street == 1 and self.was_pf_raiser(obs) and eq > 0.33 and self.rng.random() < 0.4:
                amt = pot * 0.5
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(amt))}
            if nopp == 1 and street == 2 and eq > 0.4 and self.rng.random() < 0.15:
                amt = pot * 0.6
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(amt))}
            return {"action": "check"}
        call_amt = min(to_call, my_stack)
        need = call_amt / float(pot + call_amt)
        # facing a bet: opponent's range is stronger than modelled
        bet_frac = to_call / float(max(1, pot - to_call))
        ag = self.aggr(bettor) if bettor is not None else 0.5
        margin = (0.04 + 0.10 * min(1.5, bet_frac)) * (1.3 - ag)
        if street >= 1 and bettor is not None and not self.has_sf(obs):
            n_r = sum(1 for h in st_actions if h[2] == "raise")
            g = 0.2 + 0.6 * ag - 0.12 * min(bet_frac, 1.5) + 0.2
            if street == 1:
                g += 0.1
            if n_r >= 2:
                g *= 0.6
            g = max(0.12, min(0.9, g))
            wr = narrow_turn(hole, board, self.opp_range(obs, bettor), g)
            eqb = post_equity(hole, board, wr)
            for s in opps:
                if s != bettor:
                    eqb *= post_equity(hole, board, self.opp_range(obs, s)) if len(opps) <= 3 else 0.85
            eq = eqb
            margin = 0.02
        if eq > 0.85 or (eq > 0.75 and nopp == 1):
            if my_stack <= call_amt:
                return {"action": "call"}
            amt = obs["bets"][bettor if bettor is not None else me] * 3 + (pot - to_call) * 0
            if amt >= my_stack * 0.5 or eq > 0.92:
                return {"action": "allin"}
            return {"action": "raise", "amount": int(max(amt, obs["min_raise_to"]))}
        if eq > need + margin:
            return {"action": "call"}
        return {"action": "fold"}

    def was_pf_raiser(self, obs):
        me = obs["seat"]
        last = None
        for h in obs["history"]:
            if h[0] == 0 and h[2] == "raise":
                last = h[1]
        return last == me

    def has_sf(self, obs):
        cards = obs["hole"] + obs["board"]
        if len(cards) < 5:
            return False
        sc = {}
        for c in cards:
            sc[c[1]] = sc.get(c[1], 0) + 1
        for v in sc.values():
            if v >= 5:
                return True
        return False
