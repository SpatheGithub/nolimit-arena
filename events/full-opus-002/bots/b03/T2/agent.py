import os
import pickle
import random

_D = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_D, 'ev.pkl'), 'rb') as _f:
    _ev = pickle.load(_f)
RANKT = _ev['rank']
SUITED = _ev['suited']
with open(os.path.join(_D, 'pre.pkl'), 'rb') as _f:
    _pre = pickle.load(_f)
PCT = _pre['pct']
EQR = _pre['eqr']
ERAND = _pre['erand']
CF = _pre['cf']
OPEN_BY_BEHIND = {0: 0.5, 1: 0.45, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14, 7: 0.12}
with open(os.path.join(_D, 'icm.pkl'), 'rb') as _f:
    ICMT = pickle.load(_f)
PTS = [100, 60, 40, 25, 15, 10, 5, 0]


ICM_LAMBDA = 1.0
XSCALE = 0.9
CBET_HU = 0.65
OPEN_MULT = 1.0
PF_BB = 15
VALUE_HU = 0.62
PSUM = [sum(PTS[:n]) for n in range(9)]


def icm_val(s, T, n):
    if n > 8:
        n = 8
    if s <= 0:
        return PTS[n - 1] if n >= 1 else 0
    if n <= 1:
        return PTS[0]
    x = s / T * 400
    i = int(x)
    row = ICMT[n]
    if i >= 400:
        v = row[400]
    else:
        f = x - i
        v = row[i] * (1 - f) + row[i + 1] * f
    if ICM_LAMBDA < 1.0:
        lin = PTS[n - 1] + (s / T) * (PSUM[n] - n * PTS[n - 1])
        v = ICM_LAMBDA * v + (1 - ICM_LAMBDA) * lin
    return v

RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
KEY = tuple(((RANK_KEYS[c >> 2] + COUNT) << 16) | (1 << 4 * (c & 3)) for c in range(52))
RBIT = tuple(1 << (c >> 2) for c in range(52))
SBITS = {8 << 4 * s: tuple(RBIT[c] if c & 3 == s else 0 for c in range(52)) for s in range(4)}
RSTR = '23456789TJQKA'
SSTR = 'cdhs'
CARD = {r + s: RSTR.index(r) * 4 + SSTR.index(s) for r in RSTR for s in SSTR}


def ev(cards):
    s = 0x3333
    for c in cards:
        s += KEY[c]
    fl = s & 0x8888
    if fl:
        b = SBITS[fl]
        f = SUITED[sum([b[c] for c in cards])]
        r = RANKT[s >> 16]
        return f if f > r else r
    return RANKT[s >> 16]


def hcls(a, b):
    ra, rb = a >> 2, b >> 2
    hi, lo = (ra, rb) if ra >= rb else (rb, ra)
    if hi == lo or (a & 3) == (b & 3):
        return hi * 13 + lo
    return lo * 13 + hi


_rng0 = random.Random(12345)
COMBOS = [(a, b, hcls(a, b)) for a in range(52) for b in range(a + 1, 52)]
_rng0.shuffle(COMBOS)


def range_w(p, floor=0.06):
    """class weights for 'top p' range (p in 0..1)"""
    return [1.0 if PCT[c] <= p + 0.004 else floor for c in range(169)]


W_RAND = [1.0] * 169


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        self.nseats = config.get("seats", 8)
        self.cache = {}
        # opponent stats
        self.st = {}
        self.wcache = {}

    # ---------------- opponent model ----------------
    def stat(self, s):
        d = self.st.get(s)
        if d is None:
            d = self.st[s] = {'h': 0, 'vpip': 0, 'pfr': 0, 'agg': 0, 'pas': 0, 'shove': 0, 'shn': 0,
                              'fb': 0, 'ff': 0, 'aif': 0, 'aic': 0, 'sh': 0}
        return d

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            bet_on = -1
            for h in hist:
                st, s, a = h[0], h[1], h[2]
                if a in ('sb', 'bb', 'ante', 'return'):
                    seen.add(s)
                    continue
                seen.add(s)
                if st > 0:
                    if bet_on == st and a in ('fold', 'call', 'raise') and s != self.seat:
                        d = self.stat(s)
                        d['fb'] += 1
                        if a == 'fold':
                            d['ff'] += 1
                    if a == 'raise':
                        bet_on = st
                if st == 0:
                    if a in ('call', 'raise'):
                        vp.add(s)
                    if a == 'raise':
                        pr.add(s)
                else:
                    d = self.stat(s)
                    if a == 'raise':
                        d['agg'] += 1
                    elif a in ('call', 'check'):
                        d['pas'] += 1
            try:
                self.track_allin(event, hist)
            except Exception:
                pass
            for s in seen:
                if s == self.seat:
                    continue
                d = self.stat(s)
                d['h'] += 1
                if s in vp:
                    d['vpip'] += 1
                if s in pr:
                    d['pfr'] += 1
        except Exception:
            pass

    def track_allin(self, event, hist):
        stacks = event["stacks"]
        pay = event["payoffs"]
        start = {}
        for k, v in pay.items():
            k = int(k)
            start[k] = stacks[k] - v
        prev = {k: 0 for k in start}
        sb = {k: 0 for k in start}
        pending = False
        for h in hist:
            st, sv, a, amt = h[0], h[1], h[2], h[3]
            if st != 0:
                break
            if sv not in start:
                continue
            if a == 'ante':
                prev[sv] += amt
                continue
            if a in ('sb', 'bb'):
                sb[sv] = amt
                continue
            if a == 'raise':
                if pending and sv != self.seat:
                    d = self.stat(sv)
                    d['aif'] += 1
                    d['aic'] += 1
                sb[sv] = amt
                if prev[sv] + amt >= start[sv] and start[sv] > 0:
                    pending = True
                    if sv != self.seat:
                        self.stat(sv)['sh'] += 1
            elif a == 'call':
                sb[sv] += amt
                if pending and sv != self.seat:
                    d = self.stat(sv)
                    d['aif'] += 1
                    d['aic'] += 1
            elif a == 'fold':
                if pending and sv != self.seat:
                    self.stat(sv)['aif'] += 1

    def fold_rate(self, s):
        d = self.st.get(s)
        if not d:
            return 0.45
        return (d['ff'] + 0.45 * 4) / (d['fb'] + 4)

    def agg_factor(self, s):
        d = self.st.get(s)
        if not d:
            return 1.0
        af = (d['agg'] + 1.0) / (d['agg'] + d['pas'] + 3.0)
        return max(0.75, min(1.6, 0.6 + 1.2 * af))

    def looseness(self, s):
        """estimated fraction of hands opponent raises preflop (pfr)"""
        d = self.st.get(s)
        if not d or d['h'] < 6:
            return None
        return (d['pfr'] + 0.15 * 4) / (d['h'] + 4)

    # ---------------- helpers ----------------
    def act(self, obs):
        try:
            a = self.decide(obs)
        except Exception:
            a = None
        if a is None:
            a = {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return self.legalize(a, obs)

    def legalize(self, a, obs):
        legal = obs["legal"]
        act = a["action"]
        if act in ("raise", "bet"):
            if "raise" not in legal and "bet" not in legal:
                return {"action": "call"} if "call" in legal else {"action": "check"}
            amt = int(a["amount"])
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if amt >= hi * 0.9 or amt >= hi:
                amt = hi
            amt = max(lo, min(hi, amt))
            name = "raise" if "raise" in legal else "bet"
            return {"action": name, "amount": amt}
        if act == "allin":
            return {"action": "allin"}
        if act == "call":
            if "call" in legal:
                return a
            return {"action": "check"}
        if act == "check":
            if "check" in legal:
                return a
            return {"action": "fold"}
        if act == "fold":
            if "check" in legal:
                return {"action": "check"}
            return a
        return {"action": "check"} if "check" in legal else {"action": "fold"}

    def raise_to(self, obs, amt):
        return {"action": "raise", "amount": int(amt)}

    # ---------------- main ----------------
    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if obs["street_index"] == 0:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    def ctx(self, obs):
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        bb = max(obs["bb"], 1)
        mystack = stacks[me]
        mybet = bets[me]
        opps = [s for s in in_hand if s != me]
        # effective stack: max of opponents' total (stack+bet) capped by mine
        my_total = mystack + mybet
        opp_tot = [stacks[s] + bets[s] for s in opps]
        eff = min(my_total, max(opp_tot) if opp_tot else 0)
        return me, stacks, bets, bb, mystack, mybet, opps, eff

    def risk_premium(self, obs):
        alive = len(obs["alive"])
        # tournament risk: losing a stack costs more than winning one gains
        return 0.025 + 0.01 * max(0, 6 - alive) if alive > 2 else 0.0

    # ---------------- preflop ----------------
    def preflop(self, obs, hole):
        me, stacks, bets, bb, mystack, mybet, opps, eff = self.ctx(obs)
        c = hcls(hole[0], hole[1])
        p = PCT[c]
        hist = obs["history"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        alive = obs["alive"]
        n_alive = len(alive)
        raises = [h for h in hist if h[0] == 0 and h[2] == 'raise']
        limpers = 0
        for h in hist:
            if h[0] == 0 and h[2] == 'raise':
                break
            if h[0] == 0 and h[2] == 'call':
                limpers += 1
        # players yet to act after me (preflop order)
        order = self.preflop_order(obs)
        idx = order.index(me) if me in order else 0
        behind = [s for s in order[idx + 1:] if s in obs["in_hand"] and stacks[s] > 0]
        n_behind = len(behind)
        eff_bb = eff / bb
        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        allin_amt = obs["max_raise_to"]
        rp = self.risk_premium(obs)

        if not raises:
            # unopened (maybe limpers)
            if eff_bb <= PF_BB or (eff_bb <= PF_BB + 5 and limpers > 0):
                # push/fold
                if not can_raise:
                    return {"action": "call"} if to_call == 0 else self.call_or_fold_allin(obs, c, opps, rp)
                ev_push = self.push_ev(obs, c, behind, eff, pot, to_call)
                if ev_push > 0.0:
                    return {"action": "allin"}
                if to_call == 0:
                    return {"action": "check"}
                return {"action": "fold"}
            # open range by position
            base = {0: 0.5, 1: 0.42, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14, 7: 0.12}.get(n_behind, 0.12)
            if n_alive <= 4:
                base += 0.05
            base *= OPEN_MULT
            if limpers:
                base = base * 0.6
            if to_call == 0:
                # BB option with limpers
                if p <= 0.10 and can_raise:
                    return self.raise_to(obs, bets[me] + (3 + limpers) * bb + pot * 0.3)
                return {"action": "check"}
            if p <= base and can_raise:
                size = (2.3 if n_behind > 2 else 2.5) * bb + limpers * bb
                if eff_bb < 25 and p <= base * 0.5:
                    size = 2.2 * bb
                return self.raise_to(obs, size)
            # SB complete / limp behind with speculative hands when cheap
            if to_call <= bb * 0.5 + 1 and p <= 0.5 and eff_bb > 20:
                return {"action": "call"}
            if limpers and to_call <= bb and eff_bb > 40 and self.speculative(hole) and n_behind <= 3:
                return {"action": "call"}
            return {"action": "fold"}

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        nr = len(raises)
        raise_to_amt = last[3]
        raiser_total = stacks[raiser] + bets[raiser]
        raiser_allin = stacks[raiser] == 0
        # estimate raiser's range
        r_bb = raiser_total / bb
        order_r = self.preflop_order(obs)
        n_behind_r = len(order_r) - 1 - order_r.index(raiser) if raiser in order_r else 3
        if raiser_allin or bets[raiser] >= 0.85 * raiser_total:
            rng_p = 0.12 if r_bb > 30 else (0.2 if r_bb > 15 else (0.32 if r_bb > 8 else 0.5))
            if nr == 1 and n_behind_r <= 2:
                rng_p *= 1.5
            elif nr >= 2:
                rng_p *= 0.6
            shove_branch = True
        elif nr == 1:
            shove_branch = False
            rng_p = OPEN_BY_BEHIND.get(n_behind_r, 0.12)
            if limpers:
                rng_p *= 0.7
        else:
            shove_branch = False
            rng_p = {2: 0.06, 3: 0.03}.get(nr, 0.025)
        loose = self.looseness(raiser)
        f_l = max(0.5, min(3.0, loose / 0.15)) if loose is not None else 1.0
        dr = self.st.get(raiser)
        if shove_branch and dr and dr['h'] >= 8:
            shr = (dr['sh'] + 0.05 * 6) / (dr['h'] + 6)
            f_s = max(0.7, min(2.5, shr / 0.05))
            f_l = (f_l * f_s) ** 0.5
        rng_p = min(0.9, rng_p * f_l)
        rng_p = max(0.02, min(0.9, rng_p))
        eq = self.eqr(c, rng_p)
        # multiway adjust: other callers in
        callers_after = sum(1 for h in hist if h[0] == 0 and h[2] == 'call' and h[1] != me
                            and hist.index(h) > hist.index(last))
        n_others = callers_after + n_behind * 0.15
        eq_m = eq * (0.82 ** n_others) if n_others else eq
        pot_after = pot + to_call
        need = to_call / pot_after if pot_after > 0 else 0
        need = max(need, self.call_req(obs))
        my_total = mystack + mybet

        # if calling commits most of my stack or opponent all-in: all-in math
        if to_call >= 0.5 * mystack or raiser_allin:
            if not can_raise or raiser_allin or to_call >= mystack:
                return self.call_or_fold_allin(obs, c, opps, rp, eq_override=eq_m)
            if eq_m > self.call_req(obs, mystack):
                return {"action": "allin"}
            return {"action": "fold"}

        # 3-bet / 4-bet decision
        value_cut = rng_p * 0.33
        if can_raise and (p <= max(0.025, value_cut) or (p <= 0.012)):
            # value re-raise
            jam = eff_bb <= 35 or nr >= 2
            size = raise_to_amt * (3.0 if n_behind or callers_after else 2.7) + callers_after * raise_to_amt
            if size >= 0.4 * my_total:
                jam = True
            if not jam:
                return self.raise_to(obs, size)
            if p <= 0.01:
                return {"action": "allin"}
            if nr == 1:
                if self.resteal_ev(obs, c, raiser, rng_p, eff, pot, to_call, behind) > 0:
                    return {"action": "allin"}
            else:
                eq_c = self.eqr(c, max(0.015, rng_p * 0.6))
                if eq_c >= self.call_req(obs, mystack):
                    return {"action": "allin"}
            # otherwise fall through to call/fold logic
        # shove over open with decent hand when short-ish
        if can_raise and eff_bb <= 25 and nr == 1:
            ev_j = self.resteal_ev(obs, c, raiser, rng_p, eff, pot, to_call, behind)
            if ev_j > 0 and p <= 0.25:
                return {"action": "allin"}
        # light 3-bet bluff vs late position opener
        if can_raise and nr == 1 and eff_bb > 35 and callers_after == 0 and rng_p >= 0.2 \
                and 0.06 < p <= 0.3 and self.rng.random() < 0.12:
            return self.raise_to(obs, raise_to_amt * 3.0)
        # call
        implied = 1.0 if eff_bb > 30 else 0.9
        real = 0.9 if n_behind == 0 else 0.8
        if nr >= 2:
            real -= 0.1
        spec_bonus = 0.0
        if self.speculative(hole) and to_call <= eff * 0.06:
            spec_bonus = 0.05 * implied
        if eq_m * real + spec_bonus > need and p <= 0.5:
            return {"action": "call"}
        return {"action": "fold"}

    def speculative(self, hole):
        ra, rb = hole[0] >> 2, hole[1] >> 2
        if ra == rb:
            return True
        if (hole[0] & 3) == (hole[1] & 3) and abs(ra - rb) <= 2 and min(ra, rb) >= 3:
            return True
        return False

    def eqr(self, c, p):
        x = p * 100.0
        i = int(x)
        if i >= 100:
            return EQR[c][100]
        f = x - i
        row = EQR[c]
        return row[i] * (1 - f) + row[i + 1] * f

    def preflop_order(self, obs):
        n = len(obs["stacks"])
        alive = set(obs["alive"])
        bb = obs["bb_seat"]
        if len(alive) == 2:
            btn = obs["button"]
            other = [s for s in alive if s != btn]
            return [btn] + other
        out = []
        k = (bb + 1) % n
        for _ in range(n):
            if k in alive:
                out.append(k)
            k = (k + 1) % n
        # move so that bb is last
        return out

    def call_range(self, s, bb, shove_size, obs=None, rt=None):
        """estimated fraction of hands opponent s calls an all-in with"""
        st_bb = shove_size / max(bb, 1)
        if obs is not None:
            me = obs["seat"]
            bets = obs["bets"]
            call_amt = rt - bets[s]
            final = obs["pot"] + (rt - bets[me]) + call_amt
            n_al = len(obs["alive"])
            t = call_amt / max(1, final) + (0.06 if n_al > 3 else (0.03 if n_al == 3 else 0.0))
            if n_al > 2 and obs["stacks"][me] + bets[me] >= obs["stacks"][s] + bets[s]:
                t += 0.03
            x = 50 if st_bb < 8 else (30 if st_bb < 20 else 20)
            if s == obs["bb_seat"] and len(obs["in_hand"]) == 2:
                x = min(100, x + 20)
            ti = (t - 0.30) * 100
            if ti <= 0:
                base = CF[x][0]
            elif ti >= 40:
                base = CF[x][40]
            else:
                i = int(ti)
                f = ti - i
                base = CF[x][i] * (1 - f) + CF[x][i + 1] * f
        else:
            base = 0.22 if st_bb < 8 else (0.16 if st_bb < 15 else (0.11 if st_bb < 30 else 0.07))
        d = self.st.get(s)
        if d and d['aif'] >= 2:
            acr = (d['aic'] + 0.25 * 3) / (d['aif'] + 3)
            base *= max(0.4, min(2.5, acr / 0.25))
        elif d and d['h'] >= 8:
            vp = (d['vpip'] + 0.25 * 5) / (d['h'] + 5)
            base *= max(0.6, min(2.0, vp / 0.25))
        return max(0.03, min(0.8, base))

    def icm_req(self, obs, risk, win_amt, n_bust):
        """required equity to call/commit `risk` chips to win `win_amt` (net to stack)"""
        stacks = obs["stacks"]
        me = obs["seat"]
        T = sum(stacks) + obs["pot"]
        n = len(obs["alive"])
        S = stacks[me]
        ef = icm_val(S, T, n)
        ew = icm_val(S + win_amt, T, max(1, n - n_bust))
        sl = S - risk
        el = icm_val(sl, T, n) if sl > 0 else PTS[n - 1]
        if ew - el <= 1e-9:
            return 1.0
        return (ef - el) / (ew - el)

    def call_req(self, obs, call_amt=None):
        """ICM required equity for calling to_call (or call_amt) now"""
        stacks, bets = obs["stacks"], obs["bets"]
        me = obs["seat"]
        S = stacks[me]
        risk = min(obs["to_call"] if call_amt is None else call_amt, S)
        level = bets[me] + risk
        excess = 0
        n_bust = 0
        for j in obs["in_hand"]:
            if j == me:
                continue
            if bets[j] > level:
                excess += bets[j] - level
            elif stacks[j] == 0 and bets[j] > 0:
                n_bust += 1
        win_amt = obs["pot"] - excess
        return self.icm_req(obs, risk, win_amt, n_bust)

    def push_ev(self, obs, c, behind, eff, pot, to_call):
        """ICM gain of shoving vs folding (in points)"""
        stacks, bets = obs["stacks"], obs["bets"]
        me = obs["seat"]
        bb = obs["bb"]
        S = stacks[me]
        my_total = S + bets[me]
        T = sum(stacks) + pot
        n = len(obs["alive"])
        e_fold = icm_val(S, T, n)
        ev = 0.0
        pacc = 1.0
        for s in behind:
            opp_total = stacks[s] + bets[s]
            rt = min(my_total, opp_total)
            cr = self.call_range(s, bb, rt, obs, rt)
            eq = self.eqr(c, cr)
            sw = S + pot + rt - bets[s]
            sl = my_total - rt
            nb = 1 if opp_total <= my_total else 0
            ew = icm_val(sw, T, max(1, n - nb))
            el = icm_val(sl, T, n) if sl > 0 else PTS[n - 1]
            ev += pacc * cr * (eq * ew + (1 - eq) * el)
            pacc *= (1 - cr)
        ev += pacc * icm_val(S + pot, T, n)
        return ev - e_fold

    def resteal_ev(self, obs, c, raiser, rng_p, eff, pot, to_call, behind):
        stacks, bets = obs["stacks"], obs["bets"]
        me = obs["seat"]
        S = stacks[me]
        my_total = S + bets[me]
        T = sum(stacks) + pot
        n = len(obs["alive"])
        callp = min(1.0, max(0.25, 0.4 * 0.17 / max(rng_p, 0.05) + 0.1))
        eq = self.eqr(c, rng_p * callp)
        opp_total = stacks[raiser] + bets[raiser]
        rt = min(my_total, opp_total)
        sw = S + pot + rt - bets[raiser]
        sl = my_total - rt
        nb = 1 if opp_total <= my_total else 0
        ew = icm_val(sw, T, max(1, n - nb))
        el = icm_val(sl, T, n) if sl > 0 else PTS[n - 1]
        ev = (1 - callp) * icm_val(S + pot, T, n) + callp * (eq * ew + (1 - eq) * el)
        return ev - icm_val(S, T, n)

    def call_or_fold_allin(self, obs, c, opps, rp, eq_override=None):
        if eq_override is None:
            eq = self.eqr(c, 0.3)
        else:
            eq = eq_override
        need = self.call_req(obs)
        if eq >= need:
            return {"action": "call"}
        return {"action": "fold"}

    # ---------------- postflop ----------------
    def opp_weights(self, obs, opps):
        """range weights for the most aggressive preflop opponent"""
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == 'raise']
        p = 0.6
        if raises:
            last = raises[-1][1]
            nr = len(raises)
            if last in opps:
                p = {1: 0.2, 2: 0.07}.get(nr, 0.04)
                loose = self.looseness(last)
                if loose is not None:
                    p = min(0.9, p * max(0.5, min(3.0, loose / 0.15)))
            else:
                p = 0.35  # callers of my raise
        else:
            p = 0.7
        p = round(p, 2)
        w = self.wcache.get(p)
        if w is None:
            w = self.wcache[p] = range_w(p, 0.08)
        return w

    def hand_strength(self, hole, board, w, k=220):
        dead = set(hole)
        dead.update(board)
        hv = ev(hole + board)
        bs = 0x3333
        for c_ in board:
            bs += KEY[c_]
        bsb = {}
        win = tie = tot = 0.0
        n = 0
        vals = []
        for a, b, ci in COMBOS:
            if a in dead or b in dead:
                continue
            s = bs + KEY[a] + KEY[b]
            fl = s & 0x8888
            if fl:
                bt = SBITS[fl]
                m = bsb.get(fl)
                if m is None:
                    m = bsb[fl] = sum([bt[x] for x in board])
                f = SUITED[m + bt[a] + bt[b]]
                r = RANKT[s >> 16]
                v = f if f > r else r
            else:
                v = RANKT[s >> 16]
            wt = w[ci]
            if v < hv:
                win += wt
            elif v == hv:
                tie += wt
            tot += wt
            vals.append((v, wt))
            n += 1
            if n >= k:
                break
        vals.sort(reverse=True)
        return (win + 0.5 * tie) / tot if tot > 0 else 0.5, hv, vals, tot

    @staticmethod
    def hs_top(vals, tot, hv, X):
        """HS vs the strongest X fraction (by weight) of the sampled range"""
        limit = X * tot
        acc = win = tie = 0.0
        for v, wt in vals:
            if acc >= limit:
                break
            take = wt if wt < limit - acc else limit - acc
            if v < hv:
                win += take
            elif v == hv:
                tie += take
            acc += take
        return (win + 0.5 * tie) / acc if acc > 0 else 0.5

    def draw_outs(self, hole, board, hv):
        if len(board) >= 5:
            return 0.0
        cat = hv >> 20
        outs = 0.0
        allc = hole + board
        # flush draw
        if cat < 5:
            for s in range(4):
                n_all = sum(1 for x in allc if x & 3 == s)
                n_h = sum(1 for x in hole if x & 3 == s)
                if n_all == 4 and n_h >= 1:
                    outs += 9 if n_h == 2 or max(x >> 2 for x in hole if x & 3 == s) >= 10 else 7
                    break
        # straight draw
        if cat < 4:
            ranks = set(x >> 2 for x in allc)
            branks = set(x >> 2 for x in board)
            hit = 0
            for r in range(13):
                if r in ranks:
                    continue
                rs = ranks | {r}
                if self.has_straight(rs) and not self.has_straight(branks | {r}):
                    hit += 1
            outs += 4 * min(hit, 2)
        # overcards
        if cat == 0:
            top = max(x >> 2 for x in board)
            ov = sum(1 for x in hole if (x >> 2) > top)
            outs += 1.5 * ov
        return outs

    @staticmethod
    def has_straight(rs):
        if 12 in rs:
            rs = rs | {-1}
        run = 0
        for r in range(-1, 13):
            if r in rs:
                run += 1
                if run >= 5:
                    return True
            else:
                run = 0
        return False

    def postflop(self, obs, hole, board):
        me, stacks, bets, bb, mystack, mybet, opps, eff = self.ctx(obs)
        key = (obs["hand_id"], obs["street_index"])
        cached = self.cache.get(key)
        if cached is None:
            w = self.opp_weights(obs, opps)
            hs, hv, vals, tot = self.hand_strength(hole, board, w)
            outs = self.draw_outs(hole, board, hv)
            if len(board) == 3:
                ph = 1 - (47 - outs) / 47 * (46 - outs) / 46
            elif len(board) == 4:
                ph = outs / 46
            else:
                ph = 0.0
            cached = (hs, ph, hv, outs, vals, tot)
            self.cache = {key: cached}
        hs, ph, hv, outs, vals, tot = cached
        n_opp = len(opps)
        pot = obs["pot"]
        to_call = obs["to_call"]
        hist = obs["history"]
        street = obs["street_index"]
        if to_call > 0:
            # narrow bettor's range to its strongest X
            st_r = [h for h in hist if h[0] == street and h[2] == 'raise']
            bettor = st_r[-1][1] if st_r else None
            X = {1: 0.6, 2: 0.48, 3: 0.4}.get(street, 0.4)
            bet_frac = to_call / max(1, pot - to_call)
            X *= max(0.45, 1.15 - 0.25 * min(bet_frac, 2.8))
            if len(st_r) >= 2:
                X *= 0.55 ** (len(st_r) - 1)
            if bettor is not None:
                prior = sum(1 for h in hist if 0 < h[0] < street and h[1] == bettor and h[2] == 'raise')
                X *= 0.85 ** prior
                X *= self.agg_factor(bettor)
            X = max(0.08, min(1.0, X * XSCALE))
            hs_n = self.hs_top(vals, tot, hv, X)
        else:
            # narrow by opponents' earlier postflop aggression this hand
            X = 1.0
            for h in hist:
                if 0 < h[0] < street and h[2] == 'raise' and h[1] != me:
                    X *= 0.7
            if X < 1.0:
                hs_n = self.hs_top(vals, tot, hv, max(0.25, X * XSCALE))
            else:
                hs_n = hs
        ehs = hs_n + (1 - hs_n) * ph * 0.8
        eq = ehs ** (1 + 0.75 * (n_opp - 1))
        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        my_total_left = mystack
        # was I the preflop aggressor?
        pre_raises = [h for h in hist if h[0] == 0 and h[2] == 'raise']
        aggressor = bool(pre_raises) and pre_raises[-1][1] == me
        street_raises = [h for h in hist if h[0] == street and h[2] == 'raise']
        spr = min(mystack, eff) / max(pot, 1)
        r = self.rng.random()

        if to_call == 0:
            # betting decision
            if not can_raise:
                return {"action": "check"}
            pf = 1.0
            for o in opps:
                pf *= self.fold_rate(o)
            vthr = VALUE_HU - (0.04 if pf < 0.2 else 0.0)
            if eq >= vthr + 0.1 or (eq >= vthr and n_opp == 1):
                frac = 0.7 if eq >= 0.8 else 0.55
                if pf < 0.25 and eq >= 0.75:
                    frac = 0.85
                if spr < 1.2:
                    return {"action": "allin"}
                return self.bet(obs, pot * frac)
            if outs >= 8 and street < 3 and r < 0.55 + 0.4 * pf:
                return self.bet(obs, pot * 0.6)
            if aggressor and n_opp <= 2 and street == 1:
                cb = CBET_HU * min(1.4, max(0.4, pf / 0.42)) if n_opp == 1 else CBET_HU * 0.55 * min(1.4, max(0.3, pf / 0.18))
                if r < cb:
                    return self.bet(obs, pot * 0.4)
            if n_opp == 1 and street >= 2 and eq < 0.3 and pf >= 0.5 and r < 0.35 * pf:
                return self.bet(obs, pot * 0.6)
            return {"action": "check"}

        # facing bet
        need = to_call / (pot + to_call)
        bet_frac = to_call / max(1, pot - to_call)
        # opponent bets narrow range: discount equity by bet size
        eq_b = eq
        allin_call = to_call >= mystack
        if eq_b >= 0.78 and can_raise and len(street_raises) < 3:
            if spr < 2.5 or len(street_raises) >= 2:
                return {"action": "allin"}
            return self.raise_to(obs, obs["bets"][self.seat] + to_call + (pot + to_call) * 0.8)
        need = max(need, self.call_req(obs))
        prem = 0.0
        # draws: implied odds
        if street < 3 and outs >= 8 and not allin_call:
            if to_call <= 0.6 * pot and eq_b + 0.08 >= need:
                return {"action": "call"}
        if eq_b >= need + prem:
            return {"action": "call"}
        return {"action": "fold"}

    def bet(self, obs, amt):
        me = obs["seat"]
        target = obs["bets"][me] + max(amt, obs["bb"])
        if target >= 0.7 * (obs["stacks"][me] + obs["bets"][me]):
            return {"action": "allin"}
        return self.raise_to(obs, target)
