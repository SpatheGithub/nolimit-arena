import os
import random

import numpy as np

_D = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.npz"))
EQT = _D["EQT"].astype(np.float32)
EQT50 = _D["EQT50"].astype(np.float32)
EQT25 = _D["EQT25"].astype(np.float32)
EQF = _D["EQF"].astype(np.float32)
EQF50 = _D["EQF50"].astype(np.float32)
PRE1 = _D["PRE1"].tolist()
PCT = _D["PCT"].tolist()
PREX = _D["PREX"].tolist()
PREK = _D["PREK"].tolist()

DEBUG = False
RANKS = "TJQKA"
SUITS = "cdhs"
CID = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}


def _comb(n, k):
    if k > n:
        return 0
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


C = [[_comb(n, k) for k in range(6)] for n in range(21)]


def pidx(a, b):
    if a > b:
        a, b = b, a
    return C[b][2] + a


def bidx(cs):
    cs = sorted(cs)
    s = 0
    for i, c in enumerate(cs):
        s += C[c][i + 1]
    return s


def steal_spot(hist, rs):
    folds = 0
    for _, s, a, _ in hist:
        if a == "fold":
            folds += 1
        elif a == "call":
            return False
        elif a == "raise":
            return s == rs and folds >= 3
    return False


def prex(g, q):
    j = int(round(q * 20)) - 1
    if j < 0:
        j = 0
    elif j > 19:
        j = 19
    return PREX[g][j]


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 25, 5, 0, 0, 0, 0, 0])
        self.n = {}      # hands observed per seat
        self.vpip = {}
        self.pfr = {}
        self.agg = {}    # postflop bets/raises
        self.pcall = {}  # postflop calls
        self.pfold = {}  # postflop folds facing bet

    # ------------------------------------------------------------------
    def act(self, obs):
        try:
            a = self._act(obs)
            if a is None:
                raise ValueError
            return a
        except Exception:
            if DEBUG:
                raise
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event["history"]
            seen = set()
            vp = set()
            pr = set()
            for st, s, a, amt in hist:
                seen.add(s)
                if st == 0:
                    if a == "call" or a == "raise":
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        self.agg[s] = self.agg.get(s, 0) + 1
                    elif a == "call":
                        self.pcall[s] = self.pcall.get(s, 0) + 1
                    elif a == "fold":
                        self.pfold[s] = self.pfold.get(s, 0) + 1
            for s in seen:
                self.n[s] = self.n.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
            for s in pr:
                self.pfr[s] = self.pfr.get(s, 0) + 1
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _rate(self, d, s, prior, w=8.0):
        n = self.n.get(s, 0)
        return (d.get(s, 0) + prior * w) / (n + w)

    def _raise(self, obs, amount):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0 or not ("raise" in obs["legal"] or "bet" in obs["legal"]):
            if "call" in obs["legal"]:
                return {"action": "call"}
            return {"action": "check"}
        amount = int(amount)
        if amount >= hi * 0.75:
            amount = hi
        if amount < lo:
            amount = lo
        if amount > hi:
            amount = hi
        return {"action": "raise", "amount": amount}

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def _fold(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        me = obs["seat"]
        hole = [CID[c] for c in obs["hole"]]
        g = pidx(hole[0], hole[1])
        board = [CID[c] for c in obs["board"]]
        st = obs["street_index"]
        if st == 0:
            return self._preflop(obs, me, g)
        return self._postflop(obs, me, g, board, st)

    # ------------------------------------------------------------------
    def _preflop(self, obs, me, g):
        bb = max(obs["bb"], 1)
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_total = stacks[me] + bets[me]
        opps = [s for s in in_hand if s != me]
        opp_max = max((stacks[s] + bets[s]) for s in opps) if opps else 0
        eff = min(my_total, opp_max)
        eff_bb = eff / bb
        pct = PCT[g]

        hist = [h for h in obs["history"] if h[0] == 0]
        acted = set()
        raises = []
        for _, s, a, amt in hist:
            if a in ("fold", "call", "raise", "check"):
                acted.add(s)
            if a == "raise":
                raises.append((s, amt))
        n_behind = len([s for s in opps if s not in acted])
        n_raises = len(raises)

        if n_raises == 0:
            # unopened (maybe limpers)
            limpers = len([1 for _, s, a, _ in hist if a == "call"])
            if eff_bb <= 14:
                return self._shove_or_fold(obs, me, g, eff, pot, n_behind, opps)
            # open raise ranges by players behind
            rng_w = {0: 0.6, 1: 0.55, 2: 0.42, 3: 0.34, 4: 0.28, 5: 0.24, 6: 0.2, 7: 0.17}.get(n_behind, 0.17)
            if len(obs["alive"]) == 2 and n_behind == 1:
                rng_w = 0.7
            if limpers:
                rng_w *= 0.8 if limpers == 1 else 0.6
            if pct <= rng_w:
                size = bb * (2.5 + limpers) + (bb if n_behind <= 1 else 0)
                return self._raise(obs, size)
            if to_call == 0:
                return {"action": "check"}
            # SB completing
            if to_call <= bb * 0.5 and pct <= 0.6:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        rs, ramt = raises[-1]
        raiser_total = stacks[rs] + bets[rs]
        allin_raiser = stacks[rs] == 0
        commit = to_call / max(my_total, 1)
        # estimate raiser's range width
        pfr = self._rate(self.pfr, rs, 0.18)
        if n_raises >= 2:
            q = max(0.04, min(0.5, pfr * 0.5))
        else:
            q = max(0.06, min(0.8, pfr * 1.1))
        if allin_raiser and raiser_total < 15 * bb:
            q = max(q, 0.35)
        if len(obs["alive"]) == 2:
            q = max(q, 0.5 if n_raises == 1 else 0.3)
        elif n_raises == 1 and steal_spot(hist, rs):
            # late-position open: likely a steal
            q = max(q, 0.3)
        e = prex(g, q)
        # extra opponents (callers) reduce equity
        n_others = len(opps) - 1
        callers = len([1 for _, s, a, _ in hist if a == "call" and s != me])
        e_m = e * (0.85 ** min(callers, 3))
        po = to_call / (pot + to_call)

        if allin_raiser or commit >= 0.35 or eff_bb <= 14:
            # big decision: call (or shove) by equity
            if e_m >= po + 0.02:
                if commit < 0.5 and stacks[me] > to_call and e_m > 0.55:
                    return self._raise(obs, obs["max_raise_to"])
                return self._call(obs)
            return self._fold(obs)

        # deep, normal raise
        if pct <= 0.04 or (n_raises == 1 and pct <= 0.07):
            size = ramt * 3 + callers * (ramt)
            return self._raise(obs, size)
        call_cut = 0.3 if n_raises == 1 else 0.1
        if to_call <= 0.08 * my_total and pct <= call_cut:
            return self._call(obs)
        if e_m >= po + 0.12 and to_call <= 0.15 * my_total:
            return self._call(obs)
        return self._fold(obs)

    def _shove_or_fold(self, obs, me, g, eff, pot, n_behind, opps):
        # EV of shoving vs folding, chip-based
        if n_behind == 0:
            if obs["to_call"] == 0:
                # BB with only limpers: raise strong
                if PCT[g] <= 0.3:
                    return self._raise(obs, obs["max_raise_to"])
                return {"action": "check"}
        R = eff - obs["bets"][me]
        bb = max(obs["bb"], 1)
        rbb = R / bb
        depth = 1.4 if rbb <= 5 else (1.0 if rbb <= 10 else 0.8)
        acted = set(h[1] for h in obs["history"] if h[0] == 0 and h[2] in ("fold", "call", "raise", "check"))
        behind = [s for s in opps if s not in acted]
        q = 0.22
        e = prex(g, q)
        pf = (1 - q) ** max(n_behind, 1)
        ev = pf * pot + (1 - pf) * (e * (pot + 2 * R) - R)
        if ev > 0:
            return self._raise(obs, obs["max_raise_to"])
        if obs["to_call"] == 0:
            return {"action": "check"}
        if obs["to_call"] <= obs["bb"] * 0.5 and PCT[g] <= 0.5 and eff / max(obs["bb"], 1) > 8:
            return self._call(obs)
        return self._fold(obs)

    # ------------------------------------------------------------------
    def _postflop(self, obs, me, g, board, st):
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        opps = [s for s in in_hand if s != me]
        n_opp = max(1, len(opps))
        if st == 1:
            b = bidx(board[:3])
            e_all = float(EQF[b, g])
            e_str = float(EQF50[b, g])
            e_vs = max(0.0, e_str - (e_all - e_str) * 0.8)
        else:
            b = bidx(board[:4])
            e_all = float(EQT[b, g])
            e_str = float(EQT50[b, g])
            e_vs = float(EQT25[b, g])
        my_stack = stacks[me]
        hist = [h for h in obs["history"] if h[0] == st]
        n_raises = len([1 for h in hist if h[2] == "raise"])

        if to_call == 0:
            v = e_str ** n_opp
            # calling stations: value bet thinner
            fr = 0.0
            for s in opps:
                f = self._rate(self.pfold, s, 0.3, 6)
                c = self._rate(self.pcall, s, 0.4, 6)
                fr += f / max(0.05, f + c)
            fr /= n_opp
            vt = 0.57 if st == 1 else 0.54
            if fr < 0.3:
                vt -= 0.04
            if v >= vt:
                frac = 0.75 if e_vs ** n_opp > 0.6 else 0.6
                return self._raise(obs, pot * frac)
            # bluff / semibluff heads-up
            if n_opp == 1:
                fold_rate = self._rate(self.pfold, opps[0], 0.3, 6) / max(
                    0.2, self._rate(self.pfold, opps[0], 0.3, 6) + self._rate(self.pcall, opps[0], 0.4, 6))
                bluff_p = 0.15 + 0.3 * (fold_rate - 0.4)
                if st == 1 and e_all >= 0.5 and self.rng.random() < 0.5:
                    return self._raise(obs, pot * 0.5)
                if e_all < 0.4 and self.rng.random() < bluff_p:
                    return self._raise(obs, pot * 0.55)
            return {"action": "check"}

        # facing a bet
        po = to_call / (pot + to_call)
        prev_pot = max(1, pot - to_call)
        bf = to_call / prev_pot
        bettor = None
        for h in reversed(hist):
            if h[2] == "raise":
                bettor = h[1]
                break
        agg = 0.3
        if bettor is not None:
            nb = self.n.get(bettor, 0)
            agg = (self.agg.get(bettor, 0) + 2.0) / (nb + 6.0)
        if n_raises >= 2:
            e = 0.5 * (e_vs + e_str)
        elif bf >= 0.9:
            e = 0.7 * e_str + 0.3 * e_all
        elif bf >= 0.45:
            e = 0.5 * (e_str + e_all)
        else:
            e = 0.3 * e_str + 0.7 * e_all
        # maniac adjustment: if bettor bets very often, widen
        if agg > 0.6:
            e = 0.5 * (e + e_all)
        e_m = e * (e_all ** (n_opp - 1)) if n_opp > 1 else e
        if e_vs ** n_opp >= 0.72 and n_raises < 3:
            return self._raise(obs, obs["bets"][me] + to_call + (pot + to_call) * 0.8)
        if e_m >= po:
            return self._call(obs)
        return self._fold(obs)
