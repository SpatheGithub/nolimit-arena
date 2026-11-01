import os
import json
import random
import time

from .hs import CARD, KEY, START, evaluate_s, hand_class, class_combos

_DIR = os.path.dirname(os.path.abspath(__file__))
_D = json.load(open(os.path.join(_DIR, "pre.json")))
_I = json.load(open(os.path.join(_DIR, "icm.json")))
ICMG = _I["G"]
ICMT = {int(_k): _v for _k, _v in _I["tab"].items()}
PTS = [100, 45, 20, 8, 0, 0, 0, 0]


def icm_v(n, f):
    """ICM points of a player holding fraction f of the chips, n players, others equal."""
    if n < 2:
        return 100.0
    if n > 8:
        n = 8
    row = ICMT[n]
    if f <= 0:
        return row[0]
    if f >= 1:
        return row[-1]
    x = f * ICMG
    i = int(x)
    if i >= ICMG:
        return row[-1]
    t = x - i
    return row[i] * (1 - t) + row[i + 1] * t
M = _D["M"]
MW = _D["MW"]
NCOMB = _D["ncomb"]
TOTC = float(sum(NCOMB))

# strength score: blend of HU and 3-way equity
SCORE = [0.6 * MW[k][1] + 0.4 * MW[k][3] * 2.0 for k in range(81)]
ORDER = sorted(range(81), key=lambda k: -SCORE[k])
PCT = [0.0] * 81  # percentile (0 = best) at the middle of the class
_acc = 0.0
for _k in ORDER:
    PCT[_k] = (_acc + NCOMB[_k] * 0.5) / TOTC
    _acc += NCOMB[_k]

# equity of class k vs top-p range, p grid in 1%..100%
EQTOP = [[0.5] * 101 for _ in range(81)]
for _k in range(81):
    row = M[_k]
    s = 0.0
    w = 0.0
    acc = 0.0
    pi = 1
    for _j in ORDER:
        s += row[_j] * NCOMB[_j]
        w += NCOMB[_j]
        acc += NCOMB[_j]
        while pi <= 100 and acc / TOTC >= pi / 100.0 - 1e-9:
            EQTOP[_k][pi] = s / w
            pi += 1
    while pi <= 100:
        EQTOP[_k][pi] = s / w
        pi += 1
    EQTOP[_k][0] = EQTOP[_k][1]

# all 630 combos sorted strongest first (for range sampling)
ALLC = []
for _k in ORDER:
    ALLC.extend(class_combos(_k))
CUMC = []
_a = 0
for _k in ORDER:
    _a += NCOMB[_k]
    CUMC.append(_a)


def eq_vs_top(k, p):
    i = int(round(p * 100))
    if i < 1:
        i = 1
    if i > 100:
        i = 100
    return EQTOP[k][i]


class Stat:
    __slots__ = ("hands", "vpip", "pfr", "pf_open_chances", "agg", "pas", "fold_resp", "resp", "shove", "callallin", "faceallin")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.pf_open_chances = 0
        self.agg = 0
        self.pas = 0
        self.fold_resp = 0
        self.resp = 0
        self.shove = 0
        self.callallin = 0
        self.faceallin = 0


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        self.st = {}
        self.pf_raiser_me = False

    # ---------------- stats ----------------
    def S(self, seat):
        s = self.st.get(seat)
        if s is None:
            s = self.st[seat] = Stat()
        return s

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur_street = -1
            facing = False
            for h in hist:
                st, seat, act, amt = h[0], h[1], h[2], h[3]
                if st != cur_street:
                    cur_street = st
                    facing = False
                if seat == self.seat:
                    if act == "raise":
                        facing = True
                    continue
                if act in ("sb", "bb", "ante", "return"):
                    continue
                seen.add(seat)
                s = self.S(seat)
                if st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        s.agg += 1
                    elif act in ("call", "check"):
                        s.pas += 1
                if st > 0:
                    if facing and act in ("fold", "call", "raise"):
                        s.resp += 1
                        if act == "fold":
                            s.fold_resp += 1
                if act == "raise":
                    facing = True
            for seat in seen:
                s = self.S(seat)
                s.hands += 1
                if seat in vp:
                    s.vpip += 1
                if seat in pr:
                    s.pfr += 1
        except Exception:
            pass

    def vpip(self, seat):
        s = self.st.get(seat)
        if s is None or s.hands < 4:
            return 0.30
        return (s.vpip + 0.3 * 4) / (s.hands + 4)

    def pfr(self, seat):
        s = self.st.get(seat)
        if s is None or s.hands < 4:
            return 0.15
        return (s.pfr + 0.15 * 4) / (s.hands + 4)

    def foldrate(self, seat):
        s = self.st.get(seat)
        if s is None:
            return 0.45
        return (s.fold_resp + 0.45 * 5) / (s.resp + 5)

    def aggr(self, seat):
        s = self.st.get(seat)
        if s is None:
            return 0.35
        return (s.agg + 0.35 * 5) / (s.agg + s.pas + 5)

    # ---------------- actions ----------------
    def _raise(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0 or ("raise" not in obs["legal"] and "bet" not in obs["legal"]):
            if "call" in obs["legal"]:
                return {"action": "call"}
            return {"action": "check"}
        amt = int(amt)
        if amt >= hi * 0.85:
            amt = hi
        if amt < lo:
            amt = lo
        if amt > hi:
            amt = hi
        return {"action": "raise", "amount": amt}

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def _fold(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def _act(self, obs):
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs)

    # ---------------- preflop ----------------
    def preflop(self, obs):
        me = self.seat
        hole = [CARD[c] for c in obs["hole"]]
        k = hand_class(hole[0], hole[1])
        pct = PCT[k]
        bb = obs["bb"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = sorted(obs["alive"])
        to_call = obs["to_call"]
        pot = obs["pot"]
        mystack = stacks[me]
        mytot = mystack + bets[me]
        hist = obs["history"]
        nalive = len(alive)

        # action order preflop: starts left of bb
        bbs = obs["bb_seat"]
        if bbs in alive:
            i0 = alive.index(bbs)
        else:
            i0 = 0
        order = alive[i0 + 1:] + alive[:i0 + 1]
        acted = set()
        raises = []
        callers = []
        for h in hist:
            if h[0] != 0:
                continue
            a = h[2]
            if a in ("fold", "check", "call", "raise"):
                acted.add(h[1])
            if a == "raise":
                raises.append((h[1], h[3]))
            elif a == "call":
                callers.append(h[1])
        myi = order.index(me) if me in order else 0
        behind = [s for s in order[myi + 1:] if s in in_hand and stacks[s] > 0]
        # if there was a raise, players before me who already acted may act again but ignore
        opps = [s for s in in_hand if s != me]
        # effective stack vs opponents that can still play
        maxopp = 0
        for s in opps:
            t = stacks[s] + bets[s]
            if t > maxopp:
                maxopp = t
        eff = min(mytot, maxopp)
        eff_bb = eff / float(bb)
        nr = len(raises)
        self.pf_raiser_me = False

        # ----- unopened pot (no raise) -----
        if nr == 0:
            limpers = [c for c in callers if c != me and c in in_hand]
            nlimp = len(limpers)
            if eff_bb <= 14:
                return self.pushfold(obs, k, behind, eff, pot, to_call, limpers)
            # open range by number of players behind
            nb = len(behind)
            base = {0: 0.45, 1: 0.48, 2: 0.36, 3: 0.28, 4: 0.22, 5: 0.18, 6: 0.15, 7: 0.13}.get(nb, 0.13)
            if me == obs["sb_seat"] and nb == 1:
                base = 0.45
            if nalive == 2:
                base = 0.75
            elif nalive == 3 and nb == 2:
                base = 0.5
            # steal more vs tight blinds
            if behind:
                fr = sum(1.0 - self.vpip(s) for s in behind) / len(behind)
                base *= 0.75 + 0.5 * fr
            if nlimp:
                base *= 0.7
            if eff_bb < 25:
                base *= 0.9
            if pct <= base:
                if eff_bb <= 18 and pct <= base * 0.6:
                    return self._raise(obs, obs["max_raise_to"])
                size = bb * (2.3 if eff_bb < 30 else 2.6) + nlimp * bb
                self.pf_raiser_me = True
                return self._raise(obs, size)
            if to_call == 0:
                return {"action": "check"}
            # completing from sb / limping behind limpers with decent hands
            if to_call <= bb * 0.5 + 1 and pct <= 0.45 and eff_bb > 15:
                return self._call(obs)
            if nlimp and to_call <= bb and pct <= 0.25 and eff_bb > 25:
                return self._call(obs)
            return self._fold(obs)

        # ----- facing a raise -----
        rseat, rto = raises[-1]
        rstack_after = stacks[rseat]
        rs = rseat
        # estimate raiser range
        pf = self.pfr(rs)
        nfold_before = 0
        for h in hist:
            if h[0] == 0:
                if h[2] == "raise":
                    break
                if h[2] == "fold":
                    nfold_before += 1
        if nr == 1:
            rng_frac = min(0.7, max(0.05, pf * 1.1 * (1 + 0.12 * nfold_before)))
        elif nr == 2:
            rng_frac = min(0.3, max(0.03, pf * 0.45))
        else:
            rng_frac = min(0.15, max(0.02, pf * 0.25))
        # all-in shoves are often wider by short stacks
        rtot = rstack_after + rto
        if rstack_after == 0:
            rbb = rtot / float(bb)
            if rbb < 15:
                base_sh = min(0.55, 0.12 + 2.5 / max(rbb, 1)) * (1 + 0.06 * nfold_before)
                if nalive == 2:
                    base_sh += 0.25
                elif nalive == 3:
                    base_sh += 0.1
                rng_frac = max(rng_frac, min(0.85, base_sh))
        eq = eq_vs_top(k, rng_frac)
        # multiway adjustment: callers in between
        ncall = len([c for c in callers if c != me])
        # cost to call and pot odds
        call_amt = min(to_call, mystack)
        potodds = call_amt / float(pot + call_amt)
        all_in_call = call_amt >= mystack * 0.9 or rstack_after == 0
        # how much of stack is committed
        if all_in_call or call_amt >= 0.4 * mystack:
            # pure equity decision (approx). others behind may wake up
            need = self.icm_need(obs, rseat, call_amt) + 0.02 + 0.01 * len(behind) + 0.03 * ncall
            if eq >= need:
                if rstack_after > 0 and eq >= need + 0.08 and obs["max_raise_to"] > 0:
                    return self._raise(obs, obs["max_raise_to"])
                return self._call(obs)
            return self._fold(obs)
        # short-stack resteal shove
        if nr == 1 and eff_bb <= 25 and obs["max_raise_to"] > 0:
            rcall = rng_frac * min(1.0, 0.6 + 1.2 * rto / float(max(1, rtot)))
            my_total = mystack + bets[me]
            cl = [(rseat, max(0.03, rcall))]
            for s in behind:
                risk = min(stacks[s] + bets[s], my_total) - bets[s]
                cl.append((s, 0.5 * self.call_frac(obs, s, risk)))
            for s in callers:
                if s != me and s in in_hand and s != rseat:
                    risk = min(stacks[s] + bets[s], my_total) - bets[s]
                    cl.append((s, 0.6 * self.call_frac(obs, s, risk)))
            gain, potv = self.shove_icm(obs, k, cl)
            if pct <= 0.24 and gain > 0.1 * potv:
                return self._raise(obs, obs["max_raise_to"])
        # not committed: 3-bet / call / fold
        if eq >= 0.58 or pct <= 0.03 or (nr == 1 and pct <= 0.06 and pf > 0.2):
            # 3bet / 4bet
            if eff_bb <= 30 or nr >= 2:
                return self._raise(obs, obs["max_raise_to"])
            size = rto * 3 + ncall * rto
            if size > 0.4 * eff:
                return self._raise(obs, obs["max_raise_to"])
            self.pf_raiser_me = True
            return self._raise(obs, size)
        # call with good equity, IP-ish adjustment
        real = 0.75 if behind or me in (obs["sb_seat"], obs["bb_seat"]) else 0.85
        if eq * real >= potodds + 0.03 and eq >= 0.36 and eff_bb > 12:
            return self._call(obs)
        # cheap set-mining-like calls with pairs / suited connectors deep
        if eff_bb > 40 and call_amt <= 0.06 * eff and pct <= 0.3:
            return self._call(obs)
        return self._fold(obs)

    def icm_margin(self, obs):
        # mild risk-aversion when calling for stack with many alive; none heads-up
        n = len(obs["alive"])
        if n <= 2:
            return 0.0
        stacks = obs["stacks"]
        me = self.seat
        mytot = stacks[me] + obs["bets"][me]
        tot = sum(stacks[s] + obs["bets"][s] for s in obs["alive"])
        share = mytot / float(max(1, tot))
        m = 0.0
        if n <= 4:
            m += 0.03
        if share > 1.5 / n:
            m += 0.01
        return m

    def icm_need(self, obs, opp, call_amt):
        """Min equity to call call_amt against seat opp (all-in confrontation), by ICM."""
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        n = len(obs["alive"])
        T = float(sum(stacks[s] for s in obs["alive"]) + pot)
        if T <= 0:
            return 0.5
        S = stacks[me]
        my_tot = bets[me] + call_amt
        opp_tot = stacks[opp] + bets[opp]
        matched = min(my_tot, opp_tot)
        excess = max(0, bets[opp] - matched)
        S_w = S + pot - excess
        S_l = S - call_amt
        n_w = n - 1 if opp_tot <= matched else n
        W = icm_v(n_w, S_w / T)
        L = icm_v(n, S_l / T) if S_l > 0 else float(PTS[n - 1])
        F = icm_v(n, S / T)
        if W <= L:
            return 1.0
        return (F - L) / (W - L)

    def shove_icm(self, obs, k, callers):
        """ICM value of shoving minus value of folding, and the value of the pot (for margins)."""
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        n = len(obs["alive"])
        T = float(sum(stacks[s] for s in obs["alive"]) + pot)
        S = stacks[me]
        my_total = S + bets[me]
        F = icm_v(n, S / T)
        P = icm_v(n, (S + pot) / T)
        pf = 1.0
        ev = 0.0
        for s, c in callers:
            st_tot = stacks[s] + bets[s]
            match = min(st_tot, my_total)
            their_add = max(0, match - bets[s])
            my_add = max(0, match - bets[me])
            e = eq_vs_top(k, c)
            S_w = S + pot + their_add
            S_l = S - my_add
            W = icm_v(n - 1 if st_tot <= my_total else n, S_w / T)
            L = icm_v(n, S_l / T) if S_l > 0 else float(PTS[n - 1])
            ev += pf * c * (e * W + (1 - e) * L)
            pf *= (1 - c)
        ev += pf * P
        return ev - F, P - F

    def call_frac(self, obs, s, risk):
        """Fraction of hands seat s calls an all-in with, risking `risk` more chips."""
        bb = obs["bb"]
        rbb = max(risk / float(bb), 1.0)
        if s == obs["bb_seat"]:
            c = 0.12 + 2.2 / rbb
        elif s == obs["sb_seat"]:
            c = 0.06 + 1.6 / rbb
        else:
            c = 0.04 + 1.2 / rbb
        if len(obs["alive"]) == 2:
            c += 0.08
        c *= 0.6 + 1.3 * self.vpip(s)
        sc = self.st.get(s)
        if sc is not None and sc.faceallin >= 3:
            obsr = (sc.callallin + 0.25 * 3) / (sc.faceallin + 3)
            c = 0.5 * c + 0.5 * obsr
        return max(0.04, min(0.8, c))

    def shove_ev(self, obs, k, callers):
        """callers: list of (seat, call_frac). EV in chips of shoving vs folding now."""
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        my_total = stacks[me] + bets[me]
        pf = 1.0
        ev = 0.0
        for s, c in callers:
            st_tot = stacks[s] + bets[s]
            match = min(st_tot, my_total)
            their_add = max(0, match - bets[s])
            my_add = max(0, match - bets[me])
            e = eq_vs_top(k, c)
            ev_c = e * (pot + their_add + my_add) - my_add
            ev += pf * c * ev_c
            pf *= (1 - c)
        ev += pf * pot
        return ev

    def pushfold(self, obs, k, behind, eff, pot, to_call, limpers=()):
        """Open shove or fold (or check in bb), EV in chips."""
        stacks = obs["stacks"]
        bets = obs["bets"]
        me = self.seat
        if not behind and not limpers:
            if to_call == 0:
                if PCT[k] <= 0.12:
                    return self._raise(obs, obs["max_raise_to"])
                return {"action": "check"}
        my_total = stacks[me] + bets[me]
        callers = []
        for s in behind:
            risk = min(stacks[s] + bets[s], my_total) - bets[s]
            callers.append((s, self.call_frac(obs, s, risk)))
        for s in limpers:
            risk = min(stacks[s] + bets[s], my_total) - bets[s]
            callers.append((s, 0.8 * self.call_frac(obs, s, risk)))
        gain, potv = self.shove_icm(obs, k, callers)
        if gain > 0.0:
            return self._raise(obs, obs["max_raise_to"])
        if to_call == 0:
            return {"action": "check"}
        return self._fold(obs)

    # ---------------- postflop ----------------
    def postflop(self, obs):
        t0 = time.perf_counter()
        me = self.seat
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        mystack = stacks[me]
        opps = [s for s in obs["in_hand"] if s != me]
        nopp = len(opps)
        street = obs["street_index"]
        hist = obs["history"]
        # who raised preflop (last raiser)
        pf_raiser = None
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                pf_raiser = h[1]
        # ranges for opponents
        ranges = []
        for s in opps:
            vp = self.vpip(s)
            if s == pf_raiser:
                r = min(0.6, max(0.12, self.pfr(s) * 1.4))
            else:
                r = min(0.85, max(0.2, vp * 1.1))
            ranges.append(r)
        # postflop action reads -> hand-category weights
        A = {}
        C = {}
        for h in hist:
            if h[0] >= 1 and h[1] != me:
                if h[2] == "raise":
                    A[h[1]] = A.get(h[1], 0) + 1
                elif h[2] == "call":
                    C[h[1]] = C.get(h[1], 0) + 1
        wts = []
        anyw = False
        for s in opps:
            a = A.get(s, 0)
            c = C.get(s, 0)
            ag = self.aggr(s)
            loose = min(1.0, max(0.0, (ag - 0.3) * 1.5))
            if a >= 2:
                wt = (0.05 + 0.2 * loose, 0.25 + 0.3 * loose, 0.7, 1.0)
            elif a == 1:
                wt = (0.15 + 0.3 * loose, 0.5 + 0.3 * loose, 1.0, 1.0)
            elif c >= 1:
                wt = (0.3, 0.8, 1.0, 1.0)
            else:
                wt = None
            if wt is not None:
                anyw = True
            wts.append(wt)
        eq = self.mc(hole, board, ranges, t0, wts if anyw else None)
        # street-aggression read: count raises this street by opponents
        n_str_raises = 0
        last_aggr = None
        for h in hist:
            if h[0] == street and h[2] == "raise":
                n_str_raises += 1
                last_aggr = h[1]
        bigbet = to_call / float(max(1, pot - to_call))
        if to_call == 0:
            share = eq * (nopp + 1)
            if share >= 1.3:
                frac = 0.66 if share < 1.6 else 0.8
                amt = int(pot * frac)
                if mystack <= pot * 1.2:
                    amt = obs["max_raise_to"]
                return self._raise(obs, max(amt, obs["bb"]))
            # c-bet / bluff
            if nopp == 1 and street == 1 and pf_raiser == me:
                fr = self.foldrate(opps[0])
                if self.rng.random() < 0.35 + 0.6 * fr - 0.2:
                    return self._raise(obs, max(int(pot * 0.5), obs["bb"]))
            if nopp == 1 and street >= 2 and eq < 0.35:
                fr = self.foldrate(opps[0])
                if fr > 0.55 and self.rng.random() < (fr - 0.45):
                    return self._raise(obs, max(int(pot * 0.6), obs["bb"]))
            return {"action": "check"}
        # facing a bet
        call_amt = min(to_call, mystack)
        potodds = call_amt / float(pot + call_amt)
        # opponent bet strength discount
        ag = self.aggr(last_aggr) if last_aggr is not None else 0.35
        pen = (0.02 + 0.05 * min(bigbet, 1.5)) * (1.3 - ag) + 0.03 * (n_str_raises - 1)
        if street == 3:
            pen += 0.03
        eqa = eq - pen
        share = eqa * (nopp + 1)
        if share >= 1.55 and eqa > 0.6 and (street < 3 or eqa >= 0.85):
            if mystack <= pot * 0.8:
                return self._raise(obs, obs["max_raise_to"])
            amt = to_call * 2.5 + pot
            if amt > 0.5 * mystack:
                amt = obs["max_raise_to"]
            return self._raise(obs, amt + bets[me])
        need = potodds
        if last_aggr is not None and call_amt >= 0.5 * mystack:
            need = max(potodds, self.icm_need(obs, last_aggr, call_amt))
        if eqa >= need:
            return self._call(obs)
        return self._fold(obs)

    def mc(self, hole, board, ranges, t0, wts=None):
        rnd = self.rng.random
        used0 = set(hole) | set(board)
        deck = [c for c in range(36) if c not in used0]
        nd = len(deck)
        need = 5 - len(board)
        bsum = START
        for c in board:
            bsum += KEY[c]
        hsum = KEY[hole[0]] + KEY[hole[1]]
        k = len(ranges)
        lims = []
        for r in ranges:
            lims.append(max(30, min(630, int(r * 630))))
        win = 0.0
        wsum = 0.0
        n = 0
        clock = time.perf_counter
        bnow = bsum
        brc = {}
        for c in board:
            brc[c >> 2] = brc.get(c >> 2, 0) + 1
        bbase = 0
        for v in brc.values():
            if v == 2:
                bbase += 1
            elif v >= 3:
                bbase += 2
        if bbase > 2:
            bbase = 2
        while n < 400:
            if (n & 3) == 0 and n > 0 and clock() - t0 > 0.00038:
                break
            used = set(used0)
            ocards = []
            for L in lims:
                for _ in range(20):
                    a, b = ALLC[int(rnd() * L)]
                    if a not in used and b not in used:
                        break
                else:
                    while True:
                        a = deck[int(rnd() * nd)]
                        b = deck[int(rnd() * nd)]
                        if a != b and a not in used and b not in used:
                            break
                used.add(a)
                used.add(b)
                ocards.append((a, b))
            bd = list(board)
            s = bsum
            for _ in range(need):
                while True:
                    c = deck[int(rnd() * nd)]
                    if c not in used:
                        break
                used.add(c)
                bd.append(c)
                s += KEY[c]
            w = 1.0
            if wts is not None:
                for i in range(k):
                    wt = wts[i]
                    if wt is not None:
                        a, b = ocards[i]
                        ct = (evaluate_s(bnow + KEY[a] + KEY[b], board + [a, b]) >> 20)
                        if ct < 4:
                            ct -= bbase
                            if ct < 0:
                                ct = 0
                        if ct > 3:
                            ct = 3
                        w *= wt[ct]
            mv = evaluate_s(s + hsum, bd + hole)
            best = -1
            ties = 0
            for a, b in ocards:
                v = evaluate_s(s + KEY[a] + KEY[b], bd + [a, b])
                if v > best:
                    best = v
                    ties = 1 if v == mv else 0
                elif v == mv and v == best:
                    ties += 1
            if mv > best:
                win += w
            elif mv == best:
                win += w / (1 + ties)
            wsum += w
            n += 1
        return win / wsum if wsum > 0 else 0.5
