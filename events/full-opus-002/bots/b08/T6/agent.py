import os
import pickle
import random
import time

import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "evtab.pkl"), "rb") as _f:
    _T = pickle.load(_f)
RANKT = _T["rank"]
SUITED = _T["suited"]
KEY = _T["KEY"]
SBITS = _T["SUITED_BITS"]
PF = np.load(os.path.join(_DIR, "pf_eq.npy")).astype(np.float64)
MW = np.load(os.path.join(_DIR, "pf_mw.npy")).astype(np.float64)
W_LIN = 0.0
DISC_MULT = 1.5
_PTS = [100, 60, 40, 25, 15, 10, 5, 0]
_ICM0 = np.load(os.path.join(_DIR, "icm_tab.npy"))
for _n in range(2, 9):
    _lo, _hi = _PTS[_n - 1], _PTS[0]
    _x = np.linspace(0, 1, _ICM0.shape[1])
    # chip-linear value: each chip worth the same share of the remaining prize money
    _lin = _lo + _x * (sum(_PTS[:_n]) - _n * _lo)
    _lin = np.minimum(_lin, _hi)
    _ICM0[_n] = (1 - W_LIN) * _ICM0[_n] + W_LIN * _lin
ICM = _ICM0.tolist()

RS = "23456789TJQKA"
SS = "cdhs"
CID = {r + s: i * 4 + j for i, r in enumerate(RS) for j, s in enumerate(SS)}


def cls_of(c1, c2):
    a, b = c1 >> 2, c2 >> 2
    if a < b:
        a, b = b, a
    if a == b:
        return a * 13 + a
    if (c1 & 3) == (c2 & 3):
        return a * 13 + b
    return b * 13 + a


def _combos(ci):
    a, b = divmod(ci, 13)
    out = []
    if a == b:
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                out.append((a * 4 + s1, a * 4 + s2))
    elif a > b:
        for s in range(4):
            out.append((a * 4 + s, b * 4 + s))
    else:
        for s1 in range(4):
            for s2 in range(4):
                if s1 != s2:
                    out.append((b * 4 + s1, a * 4 + s2))
    return out


COMBOS = [_combos(i) for i in range(169)]
NCOMB = np.array([len(c) for c in COMBOS], dtype=np.float64)
# strength ordering: blend of HU equity vs random and 3-way equity
_STR = 0.6 * MW[:, 1] + 0.4 * MW[:, 3] * 2.0
_ORDER = np.argsort(-_STR)
_cum = np.cumsum(NCOMB[_ORDER]) / 1326.0
PCT = np.zeros(169)  # top-x fraction including this class
for _k, _ci in enumerate(_ORDER):
    PCT[_ci] = _cum[_k]
# equity vs top-x ranges, x in 1..100 percent
_GRID = 100
_W = np.zeros((169, _GRID))
for _g in range(_GRID):
    x = (_g + 1) / _GRID
    m = PCT <= x + 1e-9
    if not m.any():
        m[_ORDER[0]] = True
    _W[:, _g] = m * NCOMB
_W /= _W.sum(axis=0, keepdims=True)
EQR = PF @ _W  # EQR[ci, g] = equity of ci vs top (g+1)% range
EQR_L = EQR.tolist()
# combo lists for postflop sampling, per 5% band
RANGE_COMBOS = []
for _g in range(20):
    x = (_g + 1) * 0.05
    lst = []
    for ci in range(169):
        if PCT[ci] <= x + 1e-9:
            lst.extend(COMBOS[ci])
    if not lst:
        lst = list(COMBOS[_ORDER[0]])
    RANGE_COMBOS.append(lst)


def eqr(ci, x):
    g = int(round(x * _GRID)) - 1
    if g < 0:
        g = 0
    elif g >= _GRID:
        g = _GRID - 1
    return EQR_L[ci][g]


def icmf(n, x):
    if n < 2:
        return 100.0
    if n > 8:
        n = 8
    row = ICM[n]
    if x <= 0:
        return row[0]
    if x >= 1:
        return row[-1]
    g = x * 200
    i = int(g)
    fr = g - i
    return row[i] * (1 - fr) + row[i + 1] * fr


def icm_exact(st, me, pay):
    n = len(st)
    memo = {}
    npay = len(pay)

    def rec(mask, place):
        v = memo.get(mask)
        if v is not None:
            return v
        tot = 0
        for i in range(n):
            if mask >> i & 1:
                tot += st[i]
        res = 0.0
        if tot > 0 and place < npay:
            for i in range(n):
                if mask >> i & 1:
                    p = st[i] / tot
                    if i == me:
                        res += p * pay[place]
                    else:
                        res += p * rec(mask & ~(1 << i), place + 1)
        memo[mask] = res
        return res

    return rec((1 << n) - 1, 0)


def ev7(cards):
    s = 0x3333
    for c in cards:
        s += KEY[c]
    if s & 0x8888:
        bits = SBITS[s & 0x8888]
        f = SUITED[sum([bits[c] for c in cards])]
        r = RANKT[s >> 16]
        return f if f > r else r
    return RANKT[s >> 16]


class Opp:
    __slots__ = ("hands", "vpip", "pfr", "agg", "pas", "shove", "fold_flop", "cbet_faced",
                 "fi_opp", "fi_shove", "va", "va_call", "fb_faced", "fb_fold")

    def __init__(self):
        self.fb_faced = 0
        self.fb_fold = 0
        self.fi_opp = 0
        self.fi_shove = 0
        self.va = 0
        self.va_call = 0
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.agg = 0
        self.pas = 0
        self.shove = 0
        self.fold_flop = 0
        self.cbet_faced = 0

    def shove_est(self, prior):
        return (self.fi_shove + prior * 5) / (self.fi_opp + 5)

    def vcall_est(self, prior):
        return (self.va_call + prior * 4) / (self.va + 4)

    def ftb_est(self):
        return (self.fb_fold + 0.42 * 5) / (self.fb_faced + 5)

    def pfr_est(self):
        return (self.pfr + 0.17 * 8) / (self.hands + 8)

    def vpip_est(self):
        return (self.vpip + 0.28 * 8) / (self.hands + 8)

    def agg_est(self):
        return (self.agg + 1.0 * 3) / (self.agg + self.pas + 6)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        self.opp = {}
        self.hand_id = None
        self.pf_aggr = False
        self.last_bb = 0

    def O(self, s):
        o = self.opp.get(s)
        if o is None:
            o = self.opp[s] = Opp()
        return o

    # ------------------------------------------------------------ observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            stacks_start = {}
            for h in hist:
                st, s, a, amt = h[0], h[1], h[2], h[3]
                if s == self.seat:
                    continue
                o = self.O(s)
                if st == 0:
                    seen.add(s)
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        o.agg += 1
                    elif a == "call":
                        o.pas += 1
            # fold-to-bet reads (postflop)
            cur = -1
            open_bet = False
            for h in hist:
                if h[0] == 0:
                    continue
                if h[0] != cur:
                    cur = h[0]
                    open_bet = False
                sx, a = h[1], h[2]
                if sx != self.seat and open_bet and a in ("fold", "call", "raise"):
                    o = self.O(sx)
                    o.fb_faced += 1
                    if a == "fold":
                        o.fb_fold += 1
                if a == "raise":
                    open_bet = True
            # shove / call-vs-allin reads
            stk = event.get("stacks")
            pay = event.get("payoffs") or {}
            bb = self.last_bb
            if stk is not None and bb:
                def st0(x):
                    p = pay.get(x, pay.get(str(x), 0))
                    try:
                        return stk[x] - p
                    except Exception:
                        return 0
                opened = False
                allin_open = False
                for h in hist:
                    if h[0] != 0:
                        break
                    sx, a, amt = h[1], h[2], h[3]
                    if a in ("sb", "bb", "ante", "return"):
                        continue
                    s0 = st0(sx)
                    if sx != self.seat:
                        o = self.O(sx)
                        if not opened:
                            if 0 < s0 <= 20 * bb:
                                o.fi_opp += 1
                                if a == "raise" and amt >= 0.6 * s0:
                                    o.fi_shove += 1
                        elif allin_open:
                            o.va += 1
                            if a in ("call", "raise"):
                                o.va_call += 1
                    if a == "raise":
                        if not opened and amt >= 0.6 * s0:
                            allin_open = True
                        elif opened and amt >= 0.6 * s0:
                            allin_open = True
                        opened = True
            for s in seen:
                o = self.O(s)
                o.hands += 1
                if s in vp:
                    o.vpip += 1
                if s in pr:
                    o.pfr += 1
        except Exception:
            pass

    # ------------------------------------------------------------ helpers
    def act(self, obs):
        t0 = time.perf_counter()
        try:
            a = self.decide(obs, t0)
        except Exception:
            a = None
        if a is None:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return a

    def fold_or_check(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def raise_to(self, obs, amt):
        legal = obs["legal"]
        if "raise" not in legal and "bet" not in legal:
            return self.call(obs)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0:
            return self.call(obs)
        amt = int(amt)
        me = obs["seat"]
        mybet = obs["bets"][me]
        # if the raise commits most of the stack, just go all in
        if amt >= hi or (amt - mybet) >= 0.7 * (hi - mybet):
            amt = hi
        if amt < lo:
            amt = lo
        if amt > hi:
            amt = hi
        return {"action": "raise" if "raise" in legal else "bet", "amount": amt}

    def allin(self, obs):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            return {"action": "raise" if "raise" in legal else "bet", "amount": obs["max_raise_to"]}
        return self.call(obs)

    # ------------------------------------------------------------ decide
    def decide(self, obs, t0):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        self.last_bb = obs["bb"]
        if obs["hand_id"] != self.hand_id:
            self.hand_id = obs["hand_id"]
            self.pf_aggr = False
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        if obs["street_index"] == 0:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board, t0)

    def seats_after(self, obs, start):
        """alive seats clockwise after start (exclusive)."""
        alive = sorted(obs["alive"])
        out = []
        n = len(alive)
        if start in alive:
            i = alive.index(start)
        else:
            i = 0
            for k, s in enumerate(alive):
                if s > start:
                    i = k - 1
                    break
            else:
                i = n - 1
        for k in range(1, n + 1):
            out.append(alive[(i + k) % n])
        return out

    def risk_lambda(self, obs):
        n = len(obs["alive"])
        if n <= 2:
            return 0.0
        if n == 3:
            return 0.06
        if n <= 5:
            return 0.08
        return 0.06

    # ------------------------------------------------------------ preflop
    def preflop(self, obs, hole):
        me = obs["seat"]
        bb = max(obs["bb"], 1)
        stacks = obs["stacks"]
        bets = obs["bets"]
        mystack = stacks[me]
        mybet = bets[me]
        mytot = mystack + mybet
        pot = obs["pot"]
        to_call = obs["to_call"]
        ci = cls_of(hole[0], hole[1])
        pct = PCT[ci]
        in_hand = obs["in_hand"]
        others = [s for s in in_hand if s != me]
        hist = [h for h in obs["history"] if h[0] == 0]
        raises = [h for h in hist if h[2] == "raise"]
        nraise = len(raises)
        # effective stack vs the biggest other stack
        maxother = max([stacks[s] + bets[s] for s in others] or [0])
        eff = min(mytot, maxother)
        effbb = eff / bb
        lam = self.risk_lambda(obs)

        if nraise == 0:
            limpers = [h[1] for h in hist if h[2] == "call" and h[1] != me]
            # players yet to act after me (up to bb)
            order = self.seats_after(obs, me)
            behind = []
            for s in order:
                if s == me:
                    break
                if s in in_hand:
                    behind.append(s)
                if s == obs["bb_seat"]:
                    break
            if me == obs["bb_seat"]:
                behind = []
            nb = len(behind)
            if effbb <= 18:
                ev = self.shove_icm(obs, ci, behind + limpers, mytot, pot, mybet)
                if ev > 0.0:
                    return self.allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                return self.fold_or_check(obs)
            # deeper: open-raise ranges by players behind
            table = {0: 0.14, 1: 0.42, 2: 0.45, 3: 0.33, 4: 0.24, 5: 0.19, 6: 0.15, 7: 0.13}
            op = table.get(nb, 0.13) * 1.0
            na = len(obs["alive"])
            if na == 2:
                op = 0.8
            elif na == 3 and nb == 2:
                op = 0.45
            elif na <= 4 and nb == 1:
                op = 0.5
            if limpers:
                op *= 0.7
            if me == obs["bb_seat"] and to_call == 0:
                if pct <= 0.12:
                    return self.raise_to(obs, (3 + len(limpers)) * bb + mybet)
                return {"action": "check"}
            if pct <= op:
                size = (2.5 if effbb > 25 else 2.2) * bb + len(limpers) * bb
                if effbb <= 18:
                    # raise-shove territory: shove strong-ish, small raise otherwise
                    return self.allin(obs)
                self.pf_aggr = True
                return self.raise_to(obs, size)
            # SB completes cheap with decent hands vs passive BB
            if me == obs["sb_seat"] and to_call <= bb / 2 and pct <= 0.55 and nb == 1:
                return self.call(obs)
            if to_call == 0:
                return {"action": "check"}
            return self.fold_or_check(obs)

        # facing raise(s)
        last = raises[-1]
        rs = last[1]
        ro = self.O(rs)
        r_to = last[3]
        r_stack_total = stacks[rs] + bets[rs]
        r_allin = stacks[rs] == 0
        rbb = r_stack_total / bb
        if nraise == 1:
            base = ro.pfr_est() * 1.0
            if r_allin or r_to >= 0.5 * r_stack_total:
                # shove range depends on stack depth
                sbase = 0.45 if rbb <= 8 else (0.32 if rbb <= 12 else (0.22 if rbb <= 20 else 0.12))
                if rbb <= 20 and len(raises) == 1:
                    rng_r = max(0.06, min(0.8, ro.shove_est(sbase)))
                else:
                    rng_r = max(sbase, min(0.7, base * 1.1))
                if len(obs["alive"]) == 2 and len(raises) == 1:
                    # heads-up shoves are wide (near-equilibrium ~55% at 10bb)
                    rng_r = max(rng_r, 0.55 if rbb <= 10 else (0.45 if rbb <= 15 else 0.35))
            else:
                rng_r = max(0.08, min(0.6, base))
                if r_to > 4 * bb:
                    rng_r *= 0.75
        elif nraise == 2:
            rng_r = max(0.035, min(0.35, ro.pfr_est() * 0.35))
            if r_allin and rbb <= 15:
                rng_r = max(rng_r, 0.12)
        else:
            rng_r = max(0.025, min(0.25, ro.pfr_est() * 0.2))
        eq = eqr(ci, rng_r)
        # extra players in the pot reduce equity
        callers = 0
        for h in hist:
            if h[2] == "call" and h[1] != me:
                callers += 1
        extra = max(0, len(others) - 1)
        if callers:
            eq = eq ** (1.0 + 0.6 * min(callers, 3))
        po = to_call / (pot + to_call)
        commit = to_call >= 0.4 * mystack or r_allin or effbb <= 15
        if commit:
            # shove or fold decision (calling an all-in, or jam over)
            if r_allin or to_call >= mystack:
                if self.call_ok(obs, eq, others):
                    return self.call(obs)
                return self.fold_or_check(obs)
            # jam over a raise: fold equity estimate
            S = mytot
            q = 0.65 if nraise == 1 else 0.8
            if (S - r_to) <= 0.35 * (pot + S - mybet):
                q = 0.95
            eqc = eqr(ci, rng_r * q)
            if callers:
                eqc = eqc ** (1.0 + 0.6 * min(callers, 3))
            n, T = self.icm_ctx(obs)
            S0 = mystack
            E = min(S, r_stack_total)
            potf = pot + (E - mybet) + (E - r_to)
            lose = S0 - (E - mybet)
            win = lose + potf
            bust = 1 if r_stack_total <= S else 0
            vf = self.V(n, T, S0)
            ev = (1 - q) * self.V(n, T, S0 + pot) + q * (eqc * self.V(n, T, win, bust) + (1 - eqc) * self.V(n, T, lose))
            if ev > vf:
                return self.allin(obs)
            if eq >= po + 0.02 and to_call <= 0.2 * mystack:
                return self.call(obs)
            return self.fold_or_check(obs)
        # deep stacks
        if nraise == 1:
            if pct <= max(0.025, rng_r * 0.35) or eq >= 0.60:
                self.pf_aggr = True
                return self.raise_to(obs, 3.2 * r_to + callers * r_to)
            if to_call <= 0.08 * mystack and eq >= po + 0.08:
                return self.call(obs)
            if (ci // 13 == ci % 13) and to_call <= 0.05 * mystack:
                return self.call(obs)  # set mining
            return self.fold_or_check(obs)
        # facing 3bet+
        if pct <= 0.03 or eq >= 0.6:
            return self.allin(obs)
        if eq >= po + 0.05 and to_call <= 0.15 * mystack:
            return self.call(obs)
        return self.fold_or_check(obs)

    def icm_ctx(self, obs):
        n = len(obs["alive"])
        T = sum(obs["stacks"]) + obs["pot"]
        return n, max(T, 1)

    def V(self, n, T, chips, busts=0):
        if chips <= 0:
            return float(self.points[n - 1]) if 0 < n <= len(self.points) else 0.0
        return icmf(n - busts, chips / T)

    def vstate(self, obs, ch):
        """exact ICM value of the stack vector after a hand (alive seats; ch overrides stacks)."""
        alive = obs["alive"]
        me = obs["seat"]
        st = []
        mi = -1
        for x in alive:
            v = ch.get(x, obs["stacks"][x])
            if v > 0:
                if x == me:
                    mi = len(st)
                st.append(v)
        if mi < 0:
            n = len(alive)
            return float(self.points[n - 1]) if n <= len(self.points) else 0.0
        if len(st) == 1:
            return float(self.points[0])
        return icm_exact(st, mi, self.points[:len(st)])

    def call_ok(self, obs, eq, opp_seats, margin=0.0):
        if len(obs["alive"]) >= 5:
            margin += 0.0
        if len(obs["alive"]) <= 4 and len(opp_seats) == 1:
            me = obs["seat"]
            stacks = obs["stacks"]
            bets = obs["bets"]
            o = opp_seats[0]
            S0 = stacks[me]
            c = min(obs["to_call"], S0)
            myc = bets[me] + c
            exc = max(0, bets[o] - myc)
            W = obs["pot"] + c - exc
            win = {me: S0 - c + W, o: stacks[o] + exc}
            lose = {me: S0 - c, o: stacks[o] + exc + W}
            pot_to = o
            fold = {me: S0, o: stacks[o] + obs["pot"]}
            vf = self.vstate(obs, fold)
            return eq * self.vstate(obs, win) + (1 - eq) * self.vstate(obs, lose) > vf + margin

        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        S0 = stacks[me]
        c = min(obs["to_call"], S0)
        n, T = self.icm_ctx(obs)
        myc = bets[me] + c
        excess = 0
        busts = 0
        for s in opp_seats:
            if bets[s] > myc:
                excess += bets[s] - myc
            if stacks[s] == 0 and bets[s] <= myc and s in obs["in_hand"]:
                busts += 1
        W = obs["pot"] + c - excess
        vf = self.V(n, T, S0)
        vw = self.V(n, T, S0 - c + W, busts)
        vl = self.V(n, T, S0 - c)
        return eq * vw + (1 - eq) * vl > vf + margin

    def shove_icm(self, obs, ci, callers, mytot, pot, mybet):
        bets = obs["bets"]
        stacks = obs["stacks"]
        bb = max(obs["bb"], 1)
        n, T = self.icm_ctx(obs)
        S0 = mytot - mybet
        pfold = 1.0
        ev = 0.0
        seen = set()
        if n <= 4:
            me = obs["seat"]
            for s in callers:
                if s in seen:
                    continue
                seen.add(s)
                tot = stacks[s] + bets[s]
                E = min(mytot, tot)
                c = self.call_range(obs, s, E / bb, s == obs["bb_seat"])
                eq = eqr(ci, c)
                potf = pot + (E - mybet) + (E - bets[s])
                lose = S0 - (E - mybet)
                so = stacks[s] - (E - bets[s])
                v = eq * self.vstate(obs, {me: lose + potf, s: so}) + (1 - eq) * self.vstate(obs, {me: lose, s: so + potf})
                ev += pfold * c * v
                pfold *= (1 - c)
            ev += pfold * self.vstate(obs, {me: S0 + pot})
            bbs = obs["bb_seat"]
            fold = {me: S0}
            if bbs != me and bbs in obs["in_hand"]:
                fold[bbs] = stacks[bbs] + pot
            return ev - self.vstate(obs, fold)
        for s in callers:
            if s in seen:
                continue
            seen.add(s)
            tot = stacks[s] + bets[s]
            E = min(mytot, tot)
            c = self.call_range(obs, s, E / bb, s == obs["bb_seat"])
            eq = eqr(ci, c)
            potf = pot + (E - mybet) + (E - bets[s])
            lose = S0 - (E - mybet)
            win = lose + potf
            bust = 1 if tot <= mytot else 0
            v = eq * self.V(n, T, win, bust) + (1 - eq) * self.V(n, T, lose)
            ev += pfold * c * v
            pfold *= (1 - c)
        ev += pfold * self.V(n, T, S0 + pot)
        return ev - self.V(n, T, S0)

    def call_range(self, obs, s, shove_bb, is_bb):
        o = self.O(s)
        base = 0.06 + 2.0 / max(shove_bb, 1.0)
        if not is_bb:
            base *= 0.65
        if len(obs["alive"]) == 2:
            base = max(base, min(0.8, 0.06 + 3.0 / max(shove_bb, 1.0)))
        loose = o.vpip_est() / 0.28
        base *= max(0.6, min(1.8, loose ** 0.5))
        base = o.vcall_est(base)
        return max(0.03, min(0.85, base))

    def shove_ev(self, obs, ci, callers, mytot, pot, mybet):
        bets = obs["bets"]
        stacks = obs["stacks"]
        bb = max(obs["bb"], 1)
        pfold = 1.0
        ev = 0.0
        seen = set()
        for s in callers:
            if s in seen:
                continue
            seen.add(s)
            tot = stacks[s] + bets[s]
            E = min(mytot, tot)
            sbb = E / bb
            c = self.call_range(obs, s, sbb, s == obs["bb_seat"])
            eq = eqr(ci, c)
            final = pot + (E - mybet) + (E - bets[s])
            gain = eq * final - (E - mybet)
            ev += pfold * c * gain
            pfold *= (1 - c)
        ev += pfold * pot
        return ev

    # ------------------------------------------------------------ postflop
    def opp_range(self, obs, s):
        """preflop range fraction for opponent s this hand."""
        hist = obs["history"]
        raised = False
        called = False
        for h in hist:
            if h[0] == 0 and h[1] == s:
                if h[2] == "raise":
                    raised = True
                elif h[2] == "call":
                    called = True
        o = self.O(s)
        if raised:
            return max(0.08, min(0.6, o.pfr_est() * 1.1))
        if called:
            return max(0.15, min(0.9, o.vpip_est() * 1.1))
        return 1.0

    def equity(self, hole, board, ranges, t0, budget=0.00035):
        rng = self.rng.random
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        nd = len(deck)
        need = 5 - len(board)
        lists = []
        for r in ranges[:3]:
            g = min(19, max(0, int(r * 20 + 0.999) - 1))
            lists.append(RANGE_COMBOS[g])
        nsim = len(lists)
        nopp = len(ranges)
        wins = 0.0
        n = 0
        clock = time.perf_counter
        bkey = 0x3333
        for c in board:
            bkey += KEY[c]
        hk = KEY[hole[0]] + KEY[hole[1]]
        while True:
            used = set()
            hands = []
            for lst in lists:
                L = len(lst)
                h = None
                for _ in range(6):
                    cand = lst[int(rng() * L)]
                    a, b = cand
                    if a in known or b in known or a in used or b in used:
                        continue
                    h = cand
                    break
                if h is None:
                    while True:
                        a = deck[int(rng() * nd)]
                        b = deck[int(rng() * nd)]
                        if a != b and a not in used and b not in used:
                            break
                    h = (a, b)
                used.add(h[0])
                used.add(h[1])
                hands.append(h)
            run = []
            while len(run) < need:
                c = deck[int(rng() * nd)]
                if c in used:
                    continue
                used.add(c)
                run.append(c)
            full = board + run
            sk = bkey
            for c in run:
                sk += KEY[c]
            # my value
            s = sk + hk
            if s & 0x8888:
                my = ev7(hole + full)
            else:
                my = RANKT[s >> 16]
            best = -1
            ties = 0
            for h in hands:
                s2 = sk + KEY[h[0]] + KEY[h[1]]
                if s2 & 0x8888:
                    v = ev7([h[0], h[1]] + full)
                else:
                    v = RANKT[s2 >> 16]
                if v > best:
                    best = v
                    ties = 1 if v == my else 0
                elif v == best and v == my:
                    ties += 1
            if my > best:
                wins += 1.0
            elif my == best:
                wins += 1.0 / (1 + ties)
            n += 1
            if n >= 400:
                break
            if n >= 12 and clock() - t0 > budget:
                break
        e = wins / max(n, 1)
        if nopp > nsim and nsim > 0:
            e = e ** (nopp / nsim)
        return e

    def postflop(self, obs, hole, board, t0):
        me = obs["seat"]
        st = obs["street_index"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        mystack = stacks[me]
        pot = obs["pot"]
        to_call = obs["to_call"]
        others = [s for s in obs["in_hand"] if s != me]
        if not others:
            return self.fold_or_check(obs)
        ranges = sorted([self.opp_range(obs, s) for s in others])
        eq = self.equity(hole, board, ranges, t0)
        nopp = len(others)
        hist = obs["history"]
        street_raises = [h for h in hist if h[0] == st and h[2] == "raise"]
        rnd = self.rng.random()
        if to_call == 0:
            if eq >= 0.72:
                size = 0.75 if st < 3 else 0.8
                return self.raise_to(obs, max(obs["min_raise_to"], int(pot * size)))
            if eq >= 0.55 and (nopp <= 2 or eq >= 0.62):
                return self.raise_to(obs, max(obs["min_raise_to"], int(pot * 0.55)))
            # bluff / semi-bluff when fold equity makes betting beat checking
            fold_p = 1.0
            for so in others:
                fold_p *= self.O(so).ftb_est()
            if self.pf_aggr and st == 1:
                fold_p = min(0.95, fold_p * 1.15)
            frac_b = 0.5 if st == 1 else 0.6
            b = frac_b * pot
            if b < mystack * 0.5:
                eq_c = eq * (0.8 if st < 3 else 0.6)
                ev_bet = fold_p * pot + (1 - fold_p) * (eq_c * (pot + 2 * b) - b)
                ev_chk = eq * pot * 0.85
                if ev_bet > ev_chk + 0.04 * pot and rnd < 0.85:
                    return self.raise_to(obs, max(obs["min_raise_to"], int(b)))
            return {"action": "check"}
        # facing a bet
        aggr = street_raises[-1][1] if street_raises else None
        ag = self.O(aggr).agg_est() if aggr is not None else 0.5
        pot_before = pot - to_call if pot > to_call else pot
        frac = to_call / max(pot - to_call, 1)
        # betting narrows the range: discount scaled by size and street, less vs aggressive players
        disc = (0.04 + 0.03 * st + 0.08 * min(frac, 1.5)) * (1.3 - 0.6 * min(ag, 1.0)) * DISC_MULT
        if len(street_raises) >= 2:
            disc += 0.07
        eqe = eq - disc
        po = to_call / (pot + to_call)
        allin_spot = to_call >= mystack or (aggr is not None and stacks[aggr] == 0)
        if allin_spot:
            if self.call_ok(obs, max(0.0, eqe), others):
                return self.call(obs)
            return self.fold_or_check(obs)
        if eqe >= 0.68 and len(street_raises) <= 2:
            return self.raise_to(obs, 2.8 * street_raises[-1][3] if street_raises else 3 * to_call)
        if to_call >= 0.35 * mystack:
            # big call: demand an ICM-sound all-in equity
            if self.call_ok(obs, max(0.0, eqe), others):
                return self.call(obs)
            return self.fold_or_check(obs)
        if eqe >= po:
            return self.call(obs)
        # cheap calls with draws
        if st < 3 and frac <= 0.35 and eqe + 0.04 >= po and nopp == 1:
            return self.call(obs)
        return self.fold_or_check(obs)
