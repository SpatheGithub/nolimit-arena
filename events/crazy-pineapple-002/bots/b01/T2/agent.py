"""b01 crazy pineapple bot: precomputed 3-card preflop equities, push/fold EV,
fast Monte Carlo postflop equity with range discounting, opponent stats."""
import json
import os
import random
import time
from itertools import combinations

from .evalr import CARD, KEY, START, SUITED_BITS, T, FS

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "pre3.json")) as _f:
    _P = json.load(_f)
PEQ = _P["eq"]
PPCT = _P["pct"]
PREQ = _P["req"]
RX = _P["rx"]
PMAP = {cb: ci for cb, ci in zip(combinations(range(52), 3), _P["map"])}
del _P

_R = random.Random(0xB01)
PERMS = []
for _i in range(512):
    _p = list(range(52))
    _R.shuffle(_p)
    PERMS.append(tuple(_p))
del _R, _p, _i

P = {"open": 0.9, "lam": 0.0, "g": 1.8, "cbet": 1.0, "push": 14, "three": 0.60, "callm": 0.08, "vthr": 0.0, "cfloor": 0.46, "sh": 1.0, "rs": 0.45, "sbf": 0, "mg": 0.8, "gf": 0.0, "rv": 1.0, "ac": 0.10, "osz": 2.5, "icm": 1, "gt": 0.4, "mt": 0.0, "lo": 1.0, "bbd": 0.06, "hux": 0.7, "hug": 0.0, "hup": 14}


def req_at(ci, w):
    r = PREQ[ci]
    if w <= RX[0]:
        return r[0]
    for j in range(1, len(RX)):
        if w <= RX[j]:
            t = (w - RX[j - 1]) / (RX[j] - RX[j - 1])
            return r[j - 1] + t * (r[j] - r[j - 1])
    t = min(1.0, (w - RX[-1]) / (1.0 - RX[-1]))
    return r[-1] + t * (PEQ[ci][0] - r[-1])


def icm_equity(stacks, payouts):
    n = len(stacks)
    if n == 0:
        return []
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    paid = max((k + 1 for k, p in enumerate(pay) if p), default=0)
    if paid == 0:
        return [0.0] * n
    memo = {}

    def rest(mask):
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < paid:
            total = sum(stacks[i] for i in members)
            for i in members:
                p = stacks[i] / total if total > 0 else 1 / len(members)
                if p <= 0:
                    continue
                res[i] += p * pay[place]
                sub = rest(mask & ~(1 << i))
                for j in members:
                    if j != i:
                        res[j] += p * sub[j]
        memo[mask] = res
        return res

    return rest((1 << n) - 1)


def hv(s, cards):
    """value from key sum s of the given card list"""
    if s & 0x8888:
        F = SUITED_BITS[s & 0x8888]
        m = 0
        for c in cards:
            m += F[c]
        f = FS[m]
        r = T[s >> 16]
        return f if f > r else r
    return T[s >> 16]


class Agent:
    def __init__(self, config):
        self.seat = config.get("seat", 0)
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        self.n_seats = config.get("seats", 8)
        # opponent stats: seat -> [hands, vpip, pfr, post_aggr, post_pass, shown_weak]
        self.st = {}
        self.pf_raiser = -1
        self.cur_hand = -1

    # ------------------------------------------------------------------ utils
    def stat(self, s):
        x = self.st.get(s)
        if x is None:
            x = self.st[s] = [0, 0, 0, 0, 0, 0, 0]
        return x

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for h in hist:
                st_i, s, a = h[0], h[1], h[2]
                if s == self.seat or s is None:
                    continue
                if a in ("sb", "bb", "ante"):
                    seen.add(s)
                    continue
                seen.add(s)
                x = self.stat(s)
                if st_i == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        x[3] += 1
                    elif a == "call":
                        x[4] += 1
                    elif a == "fold":
                        x[5] += 1
            for s in seen:
                x = self.stat(s)
                x[0] += 1
                if s in vp:
                    x[1] += 1
                if s in pr:
                    x[2] += 1
        except Exception:
            pass

    def act(self, obs):
        t0 = time.perf_counter()
        try:
            if obs.get("phase") == "discard":
                return self.discard(obs, t0)
            if obs["street_index"] == 0:
                a = self.preflop(obs)
            else:
                a = self.postflop(obs, t0)
            return self.legalize(obs, a)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def legalize(self, o, a):
        legal = o["legal"]
        act = a["action"]
        if act in ("raise", "bet"):
            if ("raise" in legal or "bet" in legal) and o["max_raise_to"] > 0:
                amt = int(a["amount"])
                lo, hi = o["min_raise_to"], o["max_raise_to"]
                if amt < lo:
                    amt = lo
                if amt > hi:
                    amt = hi
                # if raise leaves tiny stack, just shove
                return {"action": "raise" if "raise" in legal else "bet", "amount": amt}
            act = "call"
        if act == "allin":
            if ("raise" in legal or "bet" in legal) and o["max_raise_to"] > 0:
                return {"action": "raise" if "raise" in legal else "bet", "amount": o["max_raise_to"]}
            act = "call"
        if act == "call":
            if o["to_call"] == 0 or "call" not in legal:
                return {"action": "check"} if "check" in legal else {"action": "fold"}
            return {"action": "call"}
        if act == "fold":
            return {"action": "check"} if "check" in legal else {"action": "fold"}
        return {"action": "check"} if "check" in legal else {"action": "fold"}

    def risk(self, o):
        """loss aversion factor from ICM-ish pressure"""
        n = len(o["alive"])
        me = o["seat"]
        bb = o["bb"] or 1
        my = o["stacks"][me] + o["bets"][me]
        tot = sum(o["stacks"]) + sum(o["bets"])
        avg = tot / max(1, n)
        if n <= 2:
            lam = 1.0
        elif n == 3:
            lam = 1.18
        elif n <= 5:
            lam = 1.12
        else:
            lam = 1.06
        lam += P["lam"]
        if my < 8 * bb:
            lam = 1.0 + (lam - 1.0) * 0.3
        elif my > 2.0 * avg:
            lam = 1.0 + (lam - 1.0) * 0.6
        return lam

    def call_width(self, s, shove_bb):
        """estimated fraction of hands seat s calls an all-in of shove_bb with"""
        if shove_bb <= 6:
            w = 0.35
        elif shove_bb <= 10:
            w = 0.25
        elif shove_bb <= 16:
            w = 0.18
        elif shove_bb <= 30:
            w = 0.12
        else:
            w = 0.08
        x = self.st.get(s)
        if x and x[0] >= 8:
            vpip = x[1] / x[0]
            w *= max(0.6, min(2.2, vpip / 0.28))
        return max(0.04, min(0.85, w))

    def open_width(self, s):
        x = self.st.get(s)
        if x and x[0] >= 8:
            return max(0.05, min(0.8, (x[2] + 0.5) / (x[0] + 2) * 1.1))
        return 0.22

    # --------------------------------------------------------------- preflop
    def preflop(self, o):
        me = o["seat"]
        hole = tuple(sorted(CARD[c] for c in o["hole"]))
        ci = PMAP[hole]
        pct = PPCT[ci]
        eq1, eq2, eq3 = PEQ[ci]
        bb = o["bb"] or 1
        stacks, bets = o["stacks"], o["bets"]
        stack = stacks[me]
        mybet = bets[me]
        to_call = o["to_call"]
        pot = o["pot"]
        hist = o["history"]
        in_hand = o["in_hand"]
        alive = o["alive"]
        others = [s for s in in_hand if s != me]
        live_others = [s for s in others if stacks[s] > 0]
        n = len(alive)
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        nr = len(raises)
        limpers = sum(1 for h in hist if h[0] == 0 and h[2] == "call")
        # order
        bi = alive.index(o["button"]) if o["button"] in alive else 0
        if n == 2:
            order = [alive[bi], alive[1 - bi]]
        else:
            bbs = o["bb_seat"]
            j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
            order = alive[j:] + alive[:j]
        idx = order.index(me) if me in order else 0
        behind = [s for s in order[idx + 1:] if s in in_hand and stacks[s] > 0]
        nb = len(behind)
        eff = min(stack + mybet, max([stacks[s] + bets[s] for s in others] or [0]))
        eff_bb = eff / bb
        lam = self.risk(o)
        cur = mybet + to_call  # current bet level
        can_raise = ("raise" in o["legal"] or "bet" in o["legal"]) and o["max_raise_to"] > 0

        if nr == 0:
            # unopened (maybe limpers)
            if eff_bb <= (P["hup"] if n == 2 else P["push"]) and can_raise:
                if P["icm"] and 3 <= n <= 4 and 0 < len(live_others) <= 2:
                    sev = self.icm_shove(o, ci, live_others)
                else:
                    sev = self.shove_ev(o, ci, live_others, stack, pot, lam, bb)
                if sev > 0:
                    return {"action": "allin"}
                if to_call == 0:
                    return {"action": "check"}
                # SB complete with strong-ish when cheap? keep simple
                return {"action": "fold"}
            # position based open widths
            ow = {0: 0.5, 1: 0.48, 2: 0.38, 3: 0.30, 4: 0.25, 5: 0.21, 6: 0.18, 7: 0.16}.get(nb, 0.16)
            ow *= P["open"]
            if nb <= 2:
                ow *= P["lo"]
            if limpers:
                ow *= 0.75
            if P["sh"]:
                if n == 2:
                    ow = max(ow, 0.78)
                elif n == 3:
                    ow = max(ow, 0.5 if nb <= 1 else 0.42)
                elif n == 4:
                    ow = max(ow, 0.36 if nb <= 2 else 0.3)
            elif n <= 4:
                ow *= 1.25
            if behind and not limpers:
                tight = 0
                for s in behind:
                    x = self.st.get(s)
                    if x and x[0] >= 12 and x[1] / x[0] < 0.2:
                        tight += 1
                if tight == len(behind):
                    ow = min(0.75, ow * 1.6)
            if pct <= ow and can_raise:
                size = (P["osz"] + limpers) * bb if nb > 1 else (P["osz"] + 0.5 + limpers) * bb
                if eff_bb < 25:
                    size = (2.2 + limpers) * bb
                if size >= 0.4 * (stack + mybet):
                    return {"action": "allin"}
                self.pf_raiser = me
                return {"action": "raise", "amount": size}
            if to_call == 0:
                return {"action": "check"}
            # SB / cheap limp-call with decent hands
            if to_call <= 0.5 * bb and pct <= 0.55:
                return {"action": "call"}
            return {"action": "fold"}

        # facing raise(s)
        raiser = raises[-1][1]
        rstack = stacks[raiser] + bets[raiser]
        raise_to = cur
        allin_r = stacks[raiser] == 0
        big = allin_r or raise_to >= 0.45 * rstack
        if nr == 1:
            w = self.open_width(raiser)
            if big:
                rbb = rstack / bb
                base = 0.45 if rbb <= 6 else 0.32 if rbb <= 10 else 0.22 if rbb <= 18 else 0.13
                if P["hux"] and n == 2:
                    base = max(base, (0.75 if rbb <= 6 else 0.58 if rbb <= 10 else 0.45 if rbb <= 15 else 0.35 if rbb <= 20 else 0.25) * P["hux"])
                elif P["hux"] and n == 3:
                    base *= 1.3
                w = max(w, base)
            elif P["hux"] and n == 2:
                w = max(w, 0.6 * P["hux"])
        elif nr == 2:
            w = self.open_width(raiser) * 0.45
            if big:
                w = max(w, 0.1)
        else:
            w = 0.06
        w = max(0.03, min(0.9, w))
        e = req_at(ci, w)
        ncall = sum(1 for h in hist if h[0] == 0 and h[2] == "call" and h[1] != me)
        if ncall:
            e *= (eq2 / max(eq1, 1e-6)) ** min(ncall, 3)
        price = to_call / (pot + to_call)
        commit = to_call >= 0.35 * stack or eff_bb <= P["push"]
        if P["rs"] and eff_bb <= P["push"] and not big and to_call < 0.35 * stack:
            # short stack vs a normal raise: reshove or fold
            if can_raise and e >= P["rs"]:
                return {"action": "allin"}
            if me == o["bb_seat"] and e >= price * lam + 0.12 and to_call <= 2.5 * bb:
                return {"action": "call"}
            return {"action": "fold"}
        if commit or big:
            # all-in-ish decision
            win = pot  # chips we gain if win (approx)
            lose = min(to_call, stack)
            acx = P["ac"]
            if P["hux"]:
                acx *= 0.0 if n == 2 else 0.5 if n == 3 else 1.0
            need = lam * lose / (win + lam * lose) + acx
            if P["icm"] and 3 <= n <= 4 and ncall == 0 and allin_r:
                d = self.icm_call(o, raiser, e - acx * 0.5)
                return {"action": "call"} if d > 0 else {"action": "fold"}
            if can_raise and e > need + 0.06 and nr <= 2 and not allin_r:
                return {"action": "allin"}
            if e >= need:
                return {"action": "call"} if to_call < stack else {"action": "allin"}
            return {"action": "fold"}
        # normal deep decision
        th = P["three"]
        if can_raise and ((nr == 1 and e >= th) or (nr == 2 and e >= th + 0.02) or (nr >= 3 and e >= th + 0.06)):
            size = 3.0 * raise_to + ncall * raise_to
            if size >= 0.38 * (stack + mybet):
                return {"action": "allin"}
            self.pf_raiser = me
            return {"action": "raise", "amount": size}
        # call with implied odds
        need = price * lam + P["callm"]
        floor = P["cfloor"]
        if me == o["bb_seat"] and nr == 1:
            floor -= P["bbd"]
        if n == 2:
            floor -= 0.06
        if e >= need and e >= floor:
            return {"action": "call"}
        return {"action": "fold"}

    def icm_me(self, o, tot):
        """tot: dict seat->chips after hand for alive seats; returns my ICM points"""
        alive = o["alive"]
        st = [max(0, tot[s]) for s in alive]
        eqs = icm_equity(st, self.points[:len(alive)])
        return eqs[alive.index(o["seat"])]

    def icm_base(self, o):
        stacks, bets = o["stacks"], o["bets"]
        return {s: stacks[s] for s in o["alive"]}

    def icm_call(self, o, R, e):
        """EV(call all-in vs R) - EV(fold) in points; heads-up confrontation"""
        me = o["seat"]
        stacks, bets = o["stacks"], o["bets"]
        pot = o["pot"]
        Sm = stacks[me] + bets[me]
        Sr = stacks[R] + bets[R]
        A = min(Sm, Sr)
        dead = pot - bets[me] - bets[R]
        base = self.icm_base(o)
        f = dict(base)
        f[me] = Sm - bets[me]
        f[R] = Sr + pot - bets[R]
        w = dict(base)
        w[me] = Sm + A + dead
        w[R] = Sr - A
        l = dict(base)
        l[me] = Sm - A
        l[R] = Sr + A + dead
        return e * self.icm_me(o, w) + (1 - e) * self.icm_me(o, l) - self.icm_me(o, f)

    def icm_shove(self, o, ci, opps):
        me = o["seat"]
        stacks, bets = o["stacks"], o["bets"]
        pot = o["pot"]
        bb = o["bb"] or 1
        Sm = stacks[me] + bets[me]
        base = self.icm_base(o)
        f = dict(base)
        f[me] = Sm - bets[me]
        ev_fold = self.icm_me(o, f)
        ws = []
        for s in opps:
            ws.append(self.call_width(s, min(Sm, stacks[s] + bets[s]) / bb))
        pf = 1.0
        for w_ in ws:
            pf *= (1.0 - w_)
        steal = dict(base)
        steal[me] = Sm - bets[me] + pot
        ev = pf * self.icm_me(o, steal)
        sw = sum(ws) or 1.0
        for s, w_ in zip(opps, ws):
            pi = (1.0 - pf) * w_ / sw
            e = req_at(ci, w_)
            Sr = stacks[s] + bets[s]
            A = min(Sm, Sr)
            dead = pot - bets[me] - bets[s]
            wn = dict(base)
            wn[me] = Sm + A + dead
            wn[s] = Sr - A
            ls = dict(base)
            ls[me] = Sm - A
            ls[s] = Sr + A + dead
            ev += pi * (e * self.icm_me(o, wn) + (1 - e) * self.icm_me(o, ls))
        return ev - ev_fold

    def shove_ev(self, o, ci, opps, stack, pot, lam, bb):
        me = o["seat"]
        stacks, bets = o["stacks"], o["bets"]
        S = stack
        pf = 1.0
        ev = 0.0
        tot_call = 0.0
        for s in opps:
            cover = stacks[s] + bets[s]
            sb = min(S + bets[me], cover) / bb
            w = self.call_width(s, sb)
            pf *= (1.0 - w)
        # when called, assume one caller with representative width
        if not opps:
            return 1.0
        wsum = sum(self.call_width(s, min(S + bets[me], stacks[s] + bets[s]) / bb) for s in opps)
        wavg = wsum / len(opps)
        e = req_at(ci, wavg)
        cover = max(stacks[s] + bets[s] for s in opps)
        risk_amt = min(S, cover - bets[me]) if cover > bets[me] else 0
        gain = pot + risk_amt
        ev_called = e * gain - lam * (1 - e) * risk_amt
        return pf * pot + (1 - pf) * ev_called

    # -------------------------------------------------------------- postflop
    def mc(self, hole, board, n_opp, budget, t0, opp3):
        known = [False] * 52
        for c in hole:
            known[c] = True
        for c in board:
            known[c] = True
        need = 5 - len(board)
        sim = 1 if n_opp <= 1 else 2
        per = 3 if opp3 else 2
        draw = need + per * sim
        if len(hole) == 3:
            keeps = [(hole[0], hole[1]), (hole[0], hole[2]), (hole[1], hole[2])]
        else:
            keeps = [(hole[0], hole[1])]
        nk = len(keeps)
        wins = [0.0] * nk
        bkey = START
        for c in board:
            bkey += KEY[c]
        K = KEY
        clock = time.perf_counter
        off = self.rng.randrange(512)
        it = 0
        n = 0
        while True:
            p = PERMS[(off + it) & 511]
            it += 1
            cs = []
            for c in p:
                if not known[c]:
                    cs.append(c)
                    if len(cs) == draw:
                        break
            b = board + cs[:need]
            bk = bkey
            for c in cs[:need]:
                bk += K[c]
            top = -1
            for k in range(sim):
                base = need + per * k
                if per == 3:
                    x, y, z = cs[base], cs[base + 1], cs[base + 2]
                    v = hv(bk + K[x] + K[y], b + [x, y])
                    v2 = hv(bk + K[x] + K[z], b + [x, z])
                    if v2 > v:
                        v = v2
                    v2 = hv(bk + K[y] + K[z], b + [y, z])
                    if v2 > v:
                        v = v2
                else:
                    x, y = cs[base], cs[base + 1]
                    v = hv(bk + K[x] + K[y], b + [x, y])
                if v > top:
                    top = v
            for i in range(nk):
                x, y = keeps[i]
                v = hv(bk + K[x] + K[y], b + [x, y])
                if v > top:
                    wins[i] += 1.0
                elif v == top:
                    wins[i] += 0.5
            n += 1
            if n >= 400 or (n >= 12 and clock() - t0 > budget):
                break
        eqs = [w / n for w in wins]
        if n_opp > sim:
            eqs = [e ** (n_opp / sim) for e in eqs]
        return eqs, keeps

    def discard(self, o, t0):
        hole = [CARD[c] for c in o["hole"]]
        board = [CARD[c] for c in o["board"]]
        n_opp = max(1, len(o["in_hand"]) - 1)
        nd = o.get("n_discard") or 1
        if len(hole) != 3 or nd != 1 or len(board) < 3:
            return {"action": "discard", "cards": list(o["hole"][:nd])}
        eqs, keeps = self.mc(hole, board, n_opp, 0.00042, t0, False)
        bi = max(range(len(keeps)), key=lambda i: eqs[i])
        kp = keeps[bi]
        out = [c for c in hole if c not in kp]
        names = [o["hole"][hole.index(c)] for c in out]
        return {"action": "discard", "cards": names}

    def postflop(self, o, t0):
        me = o["seat"]
        hole = [CARD[c] for c in o["hole"]]
        board = [CARD[c] for c in o["board"]]
        st = o["street_index"]
        stacks, bets = o["stacks"], o["bets"]
        stack = stacks[me]
        mybet = bets[me]
        to_call = o["to_call"]
        pot = o["pot"]
        bb = o["bb"] or 1
        in_hand = o["in_hand"]
        others = [s for s in in_hand if s != me]
        n_opp = max(1, len(others))
        hist = o["history"]
        legal = o["legal"]
        can_raise = ("raise" in legal or "bet" in legal) and o["max_raise_to"] > 0
        opp3 = len(hole) == 3  # flop: opponents still hold 3 cards
        eqs, _ = self.mc(hole, board, n_opp, 0.00038, t0, opp3)
        eq = max(eqs)
        lam = self.risk(o)
        river = len(board) >= 5
        # aggression this street
        sr = [h for h in hist if h[0] == st and h[2] == "raise"]
        nr = len(sr)
        # preflop raiser
        pre_r = [h[1] for h in hist if h[0] == 0 and h[2] == "raise"]
        i_was_aggr = bool(pre_r) and pre_r[-1] == me
        prev_aggr = [h[1] for h in hist if 0 < h[0] < st and h[2] == "raise"]
        eff = min(stack + mybet, max([stacks[s] + bets[s] for s in others] or [0]))
        spr = (stack) / max(1, pot)
        r = self.rng.random()

        if to_call > 0:
            aggr = sr[-1][1] if sr else others[0]
            x = self.st.get(aggr)
            af = 1.0
            if x and x[3] + x[4] >= 5:
                af = (x[3] + 0.5) / (x[4] + 1.0)
            # range strength discount exponent
            bet_frac = to_call / max(1, pot - to_call)
            g = 1.25 + 0.35 * min(nr, 3) + 0.35 * min(bet_frac, 1.5)
            if river:
                g += 0.2
            elif st == 2:
                g += P["gt"]
            if af > 4.0:
                g -= P["mg"] * 1.5
            elif af > 2.5:
                g -= P["mg"]
            elif af < 0.6:
                g += 0.25
            if stacks[aggr] == 0 and bets[aggr] > 0:
                g -= 0.1
            g = max(1.0, g + P["g"] - (P["gf"] if st == 1 else 0.0) - (P["hug"] if len(o["alive"]) == 2 else 0.0))
            e = eq ** g
            price = to_call / (pot + to_call)
            all_in_call = to_call >= stack
            if can_raise and e >= 0.72 and nr < 4:
                if spr < 2.5 or e >= 0.85 and spr < 4:
                    return {"action": "allin"}
                size = mybet + to_call + 0.8 * (pot + to_call)
                if size >= 0.45 * (stack + mybet):
                    return {"action": "allin"}
                return {"action": "raise", "amount": size}
            m = 0.0 if river else (-0.03 if st == 1 else P["mt"])  # implied odds on draws
            if all_in_call or to_call > 0.4 * stack:
                need = lam * price / (1 + (lam - 1) * price)
                if e >= need + 0.02:
                    return {"action": "call"}
                return {"action": "fold"}
            if e >= price + m:
                return {"action": "call"}
            return {"action": "fold"}

        # no bet facing
        if not can_raise:
            return {"action": "check"}
        # opponent postflop fold tendency (heads-up target)
        bf = 1.0
        if n_opp == 1:
            x = self.st.get(others[0])
            if x:
                tot_a = x[3] + x[4] + x[5]
                if tot_a >= 6:
                    fr = x[5] / tot_a
                    if fr < 0.25:
                        bf = 0.35
                    elif fr < 0.35:
                        bf = 0.7
                    elif fr > 0.55:
                        bf = 1.5
                    elif fr > 0.45:
                        bf = 1.2
        # value bet
        thr = (0.60 if n_opp == 1 else 0.66) + P["vthr"]
        if bf < 0.5:
            thr -= 0.04
        if eq >= thr:
            frac = 0.75 if eq < 0.8 else 0.66
            if eq >= 0.85 and r < 0.25 and not river:
                frac = 0.5
            if river:
                frac *= P["rv"]
                if bf < 0.5 and eq >= 0.8:
                    frac = max(frac, 1.0)
            size = mybet + frac * pot
            if spr < 1.6 or size >= 0.5 * stack:
                return {"action": "allin"}
            return {"action": "raise", "amount": size}
        # c-bet / bluff
        heads = n_opp == 1
        if st == 1 and i_was_aggr and (heads and r < 0.55 * P["cbet"] * bf or n_opp == 2 and r < 0.3 * P["cbet"]) and eq >= 0.25:
            return {"action": "raise", "amount": mybet + 0.5 * pot}
        if (st == 1 or not P["sbf"]) and not river and eq >= 0.42 and heads and r < 0.35 * bf:
            return {"action": "raise", "amount": mybet + 0.55 * pot}
        if river and heads and eq < 0.2 and r < 0.12 * bf:
            return {"action": "raise", "amount": mybet + 0.6 * pot}
        return {"action": "check"}
