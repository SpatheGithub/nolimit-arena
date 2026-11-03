import json
import os
import random
import time

import numpy as np

from . import ev

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre.json")))
EQ = np.array(_D["eq"], dtype=float)
NCOMB = np.array(_D["ncomb"], dtype=float)
ORDER = _D["order"]
PCT = np.zeros(81)
_cum = 0.0
_tot = NCOMB.sum()
for _c in ORDER:
    PCT[_c] = (_cum + NCOMB[_c] / 2) / _tot
    _cum += NCOMB[_c]
PCTL = PCT.tolist()
FRACS = np.linspace(0.02, 1.0, 50)
_W = (PCT[None, :] <= FRACS[:, None]).astype(float) * NCOMB[None, :]
_W[_W.sum(axis=1) == 0, ORDER[0]] = NCOMB[ORDER[0]]
EQR = (EQ @ _W.T) / _W.sum(axis=1)[None, :]  # (81, 50): eq of class vs top-frac range
EQRL = EQR.tolist()


def icm_equity(stacks, payouts):
    n = len(stacks)
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


ALPHA = {5: 0.78, 6: 0.82, 7: 0.85, 8: 0.87}
PREM = {2: 0.0, 3: 0.12, 4: 0.10, 5: 0.08, 6: 0.06, 7: 0.05, 8: 0.05}
BANK_N = 3000
_brng = np.random.default_rng(12345)
BANK = {R: _brng.random((BANK_N, R)).argsort(axis=1)[:, :12].astype(np.int64) for R in (29, 30, 31)}


def eq_vs_frac(c, f):
    i = int(round((f - 0.02) / 0.02))
    i = 0 if i < 0 else 49 if i > 49 else i
    return EQRL[c][i]


def range_weights(f, floor=0.05):
    return np.where(PCT <= f, 1.0, floor)


class Stat:
    __slots__ = ("hands", "vpip", "pfr", "f2r_opp", "f2r", "pa", "pagg", "fb_opp", "fb", "jc_opp", "jc")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.f2r_opp = 0
        self.f2r = 0
        self.pa = 0
        self.pagg = 0
        self.fb_opp = 0
        self.fb = 0
        self.jc_opp = 0
        self.jc = 0

    def vp(self):
        return (self.vpip + 3 * 0.30) / (self.hands + 3)

    def pr(self):
        return (self.pfr + 3 * 0.16) / (self.hands + 3)

    def fold_to_raise(self):
        return (self.f2r + 4 * 0.70) / (self.f2r_opp + 4)

    def aggr(self):
        return (self.pagg + 4 * 0.35) / (self.pa + 4)

    def fold_to_bet(self):
        return (self.fb + 4 * 0.45) / (self.fb_opp + 4)

    def jam_call(self):
        return (self.jc + 3 * 0.25) / (self.jc_opp + 3)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nrng = np.random.default_rng(config["seed"])
        self.stats = {}
        self.cache = {}
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        self.alpha = 1.0
        self.t0 = 0.0
        n = config.get("seats", 8)
        self.prev_stacks = [config.get("starting_stack", 2000)] * n

    def st(self, s):
        x = self.stats.get(s)
        if x is None:
            x = self.stats[s] = Stat()
        return x

    # ------------------------------------------------------------------ act
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", ()):
                return {"action": "check"}
            return {"action": "fold"}

    def _ret_raise(self, obs, amt):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            a = int(amt)
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if a < lo:
                a = lo
            if a > hi or a > 0.85 * hi:
                a = hi
            return {"action": "raise", "amount": a}
        return self._ret_call(obs)

    def _ret_call(self, obs):
        if obs["to_call"] == 0 or "call" not in obs["legal"]:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return {"action": "call"}

    def _ret_fold(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _act(self, obs):
        self.t0 = time.perf_counter()
        self.alpha = ALPHA.get(len(obs["alive"]), 1.0)
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs)

    # ------------------------------------------------------------ helpers
    def ctx(self, obs):
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        mytot = stacks[me] + bets[me]
        live_opps = [s for s in opps if stacks[s] > 0]
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(mytot, other)
        return me, opps, live_opps, eff

    def order_after(self, obs):
        """Seats yet to act after me this street (preflop order), still with chips."""
        alive = obs["alive"]
        me = obs["seat"]
        n = len(alive)
        if obs["street_index"] == 0:
            if n == 2:
                bi = alive.index(obs["button"]) if obs["button"] in alive else 0
                order = [alive[bi], alive[1 - bi]]
            else:
                bbs = obs["bb_seat"]
                j = (alive.index(bbs) + 1) % n if bbs in alive else 0
                order = alive[j:] + alive[:j]
        else:
            bi = alive.index(obs["button"]) if obs["button"] in alive else 0
            order = alive[bi + 1:] + alive[:bi + 1]
        i = order.index(me) if me in order else 0
        return order, order[i + 1:]

    def jam_ev(self, obs, c_eq_fn, callers):
        """Chip EV of shoving relative to folding (0). callers: list of
        (seat, call_frac). c_eq_fn(frac) -> our equity vs that range."""
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        mytot = stacks[me] + bets[me]
        P = obs["pot"]
        mybet = bets[me]
        a = self.alpha
        s0 = max(1.0, float(stacks[me]))
        u0 = s0 ** a
        du = a * s0 ** (a - 1)
        ev_called = 0.0
        p_left = 1.0
        for s, q in callers:
            q = min(max(q, 0.02), 1.0)
            # probability this seat is the (first) caller
            pc = p_left * q
            opp_tot = stacks[s] + bets[s]
            matched = min(mytot, opp_tot)
            pot_sd = P - mybet - bets[s] + 2 * matched
            e = c_eq_fn(q)
            wf = pot_sd + (mytot - matched)
            lf = mytot - matched
            ev_called += pc * (e * wf ** a + (1 - e) * lf ** a - u0)
            p_left *= (1 - q)
        return (p_left * ((s0 + P) ** a - u0) + ev_called) / du

    def icm_me(self, fin, alive, me):
        st = [max(0.0, float(fin[x])) for x in alive]
        pay = self.points[:len(alive)]
        return icm_equity(st, pay)[alive.index(me)]

    def jam_ev_icm(self, obs, c_eq_fn, callers, fold_to):
        """ICM points EV of shoving minus folding."""
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        alive = obs["alive"]
        mytot = stacks[me] + bets[me]
        P = obs["pot"]
        base = {x: stacks[x] for x in alive}
        fb = dict(base)
        fb[fold_to] = fb.get(fold_to, 0) + P
        v_fold = self.icm_me(fb, alive, me)
        fa = dict(base)
        fa[me] = stacks[me] + P
        p_left = 1.0
        evv = 0.0
        callers = sorted(callers, key=lambda t: -t[1])[:2]
        for s, q in callers:
            if time.perf_counter() - self.t0 > 0.0004:
                break
            q = min(max(q, 0.02), 1.0)
            pc = p_left * q
            opp_tot = stacks[s] + bets[s]
            matched = min(mytot, opp_tot)
            pot_sd = P - bets[me] - bets[s] + 2 * matched
            e = c_eq_fn(q)
            w = dict(base)
            w[me] = mytot - matched + pot_sd
            w[s] = opp_tot - matched
            lo = dict(base)
            lo[me] = mytot - matched
            lo[s] = opp_tot - matched + pot_sd
            evv += pc * (e * self.icm_me(w, alive, me) + (1 - e) * self.icm_me(lo, alive, me))
            p_left *= (1 - q)
        evv += p_left * self.icm_me(fa, alive, me)
        return evv - v_fold

    def call_ev_icm(self, obs, e, raiser):
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        alive = obs["alive"]
        mytot = stacks[me] + bets[me]
        rtot = stacks[raiser] + bets[raiser]
        P = obs["pot"]
        matched = min(mytot, rtot)
        pot_sd = P - bets[me] - bets[raiser] + 2 * matched
        base = {x: stacks[x] for x in alive}
        fb = dict(base)
        fb[raiser] = fb.get(raiser, 0) + P
        w = dict(base)
        w[me] = mytot - matched + pot_sd
        w[raiser] = rtot - matched
        lo = dict(base)
        lo[me] = mytot - matched
        lo[raiser] = rtot - matched + pot_sd
        return e * self.icm_me(w, alive, me) + (1 - e) * self.icm_me(lo, alive, me) - self.icm_me(fb, alive, me)

    # ------------------------------------------------------------ preflop
    def preflop(self, obs):
        me, opps, live_opps, eff = self.ctx(obs)
        hole = [ev.CARD[c] for c in obs["hole"]]
        c = ev.cls_of(hole[0], hole[1])
        pct = PCTL[c]
        bb = obs["bb"] or 1
        stacks, bets = obs["stacks"], obs["bets"]
        stack = stacks[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        eff_bb = eff / bb
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        limpers = [h for h in hist if h[0] == 0 and h[2] == "call"]
        order, behind = self.order_after(obs)
        behind = [s for s in behind if s in obs["in_hand"] and stacks[s] > 0]
        nb = len(behind)
        can_raise = ("raise" in obs["legal"] or "bet" in obs["legal"]) and obs["max_raise_to"] > 0
        n_alive = len(obs["alive"])

        def callers_list(seats, base_q):
            out = []
            for s in seats:
                x = self.st(s)
                q = base_q * (0.6 + 0.8 * x.jam_call() / 0.25 * 0.5)
                out.append((s, min(0.9, max(0.04, q))))
            return out

        if not raises:
            # unopened (maybe limpers)
            if eff_bb <= 13 and can_raise:
                base_q = 0.16 if eff_bb > 8 else 0.24 if eff_bb > 4 else 0.4
                if n_alive <= 3:
                    base_q *= 1.4
                lseats = [h[1] for h in limpers if h[1] != me and stacks[h[1]] > 0 and h[1] not in behind]
                cl = callers_list(behind, base_q) + callers_list(lseats, base_q * 0.8)
                if n_alive in (3, 4):
                    e = self.jam_ev_icm(obs, lambda q: eq_vs_frac(c, q), cl, obs["bb_seat"])
                    e = 1.0 if e > 0 else -1.0
                else:
                    e = self.jam_ev(obs, lambda q: eq_vs_frac(c, q), cl)
                if e > 0.05 * bb:
                    return self._ret_raise(obs, obs["max_raise_to"])
                if to_call == 0:
                    return {"action": "check"}
                return self._ret_fold(obs)
            # open raise
            open_tab = {0: 1.0, 1: 0.55, 2: 0.40, 3: 0.30, 4: 0.24, 5: 0.19, 6: 0.16, 7: 0.13}
            f = open_tab.get(nb, 0.12)
            if n_alive == 2:
                f = 0.85
            fr = [self.st(s).fold_to_raise() for s in behind]
            avg_f = sum(fr) / len(fr) if fr else 0.7
            f *= 0.75 + 0.6 * (avg_f - 0.5)
            if limpers:
                f = min(f * 0.6, 0.2 if to_call == 0 else 0.15)
            if pct <= f and can_raise:
                size = (2.3 + len(limpers)) * bb if eff_bb > 20 else (2.0 + len(limpers)) * bb
                if me == obs["sb_seat"]:
                    size = 3 * bb
                return self._ret_raise(obs, size)
            if to_call == 0:
                return {"action": "check"}
            # SB complete / limp-call cheap
            if to_call <= 0.5 * bb and pct <= 0.55:
                return {"action": "call"}
            if limpers and to_call <= bb and pct <= 0.3 and eff_bb > 15:
                return {"action": "call"}
            return self._ret_fold(obs)

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        nraises = len(raises)
        rs = self.st(raiser)
        rtot = stacks[raiser] + bets[raiser]
        allin_r = stacks[raiser] == 0
        f_r = rs.pr()
        if nraises >= 2:
            f_r *= 0.45
        # raiser who jams / big raise: range a bit wider than pfr for short stacks
        if bets[raiser] >= 0.5 * rtot or allin_r:
            rbb = rtot / bb
            if rbb > 30:
                f_r = min(max(f_r * 0.6, 0.03), 0.10)
            else:
                f_r = max(f_r, 0.12 if rbb > 15 else 0.2 if rbb > 8 else 0.3)
        if n_alive == 2 and nraises == 1:
            f_r = max(f_r, 0.45 if (bets[raiser] >= 0.5 * rtot or allin_r) else 0.6)
        elif n_alive == 3 and nraises == 1:
            f_r = max(f_r, 0.28)
        f_r = min(max(f_r, 0.04), 0.7)
        e_r = eq_vs_frac(c, f_r)
        n_in = len([s for s in obs["in_hand"] if s != me])
        if n_in >= 2:
            e_r = e_r ** (1 + 0.45 * (n_in - 1))
        call_cost = to_call
        potodds = call_cost / (pot + call_cost)
        commit = (to_call >= 0.4 * stack) or eff_bb <= 15
        # re-jam option
        if can_raise and (commit or eff_bb <= 30):
            # opponents remaining: raiser + behind
            cold = [s for s in obs["in_hand"] if s not in (me, raiser) and s not in behind and stacks[s] > 0]
            seats = [raiser] + [s for s in behind if s != raiser] + cold
            cl = []
            for s in seats:
                x = self.st(s)
                if s == raiser:
                    # raiser calls a shove with top fraction of his range
                    q = min(0.95, 0.45 + 0.4 * (bets[s] / max(1, stacks[s] + bets[s])))
                    cl.append((s, q))
                else:
                    cl.append((s, 0.08))
            fr_ = f_r

            def eqf(q, fr_=fr_):
                return eq_vs_frac(c, max(0.03, fr_ * q))
            e_jam = self.jam_ev(obs, eqf, cl)
        else:
            e_jam = -1e9
            eqf = cl = None
        if commit and n_alive in (3, 4) and time.perf_counter() - self.t0 < 0.0003:
            e_call_i = self.call_ev_icm(obs, e_r, raiser)
            e_jam_i = self.jam_ev_icm(obs, eqf, cl, raiser) if cl else -1e9
            if e_jam_i > max(e_call_i, 0) and e_jam_i > 0:
                return self._ret_raise(obs, obs["max_raise_to"])
            if e_call_i > 0:
                return {"action": "call"}
            return self._ret_fold(obs)
        # call EV (approx, treat as showdown when committed)
        if commit:
            matched = min(stack + bets[me], rtot)
            pot_sd = pot - bets[me] - bets[raiser] + 2 * matched
            a = self.alpha
            s0 = max(1.0, float(stack))
            wf = pot_sd + (stack + bets[me] - matched)
            lf = stack + bets[me] - matched
            e_call = (e_r * wf ** a + (1 - e_r) * lf ** a - s0 ** a) / (a * s0 ** (a - 1))
            if e_jam > max(e_call, 0) and e_jam > 0.1 * bb:
                return self._ret_raise(obs, obs["max_raise_to"])
            if e_call > 0:
                return {"action": "call"}
            return self._ret_fold(obs)
        # deep: value 3-bet, call with decent equity (implied odds)
        if e_r > 0.58 and can_raise and nraises <= 2:
            size = bets[raiser] * (3.0 if nraises == 1 else 2.3) + 0.5 * (pot - sum(bets))
            return self._ret_raise(obs, size)
        if e_jam > 0.3 * bb and e_r > 0.45:
            return self._ret_raise(obs, obs["max_raise_to"])
        need = potodds + (0.04 if to_call > 3 * bb else 0.0) - (0.05 if eff_bb > 40 else 0.02)
        if me != obs["bb_seat"]:
            need += 0.05
        if e_r > need and to_call <= 0.25 * stack:
            return {"action": "call"}
        return self._ret_fold(obs)

    # ------------------------------------------------------------ postflop
    def opp_weights(self, obs, s, board):
        """Class weight array for seat s from its preflop action."""
        hist = obs["history"]
        x = self.st(s)
        raised = any(h[0] == 0 and h[1] == s and h[2] == "raise" for h in hist)
        if raised:
            return range_weights(min(0.6, max(0.08, x.pr())), 0.04)
        called = any(h[0] == 0 and h[1] == s and h[2] == "call" for h in hist)
        if called:
            return range_weights(min(0.8, max(0.15, x.vp())), 0.08)
        return None

    def equity(self, obs):
        me = obs["seat"]
        hole = [ev.CARD[c] for c in obs["hole"]]
        board = [ev.CARD[c] for c in obs["board"]]
        opps = [s for s in obs["in_hand"] if s != me]
        st = obs["street_index"]
        hist = obs["history"]
        aggr_now = set(h[1] for h in hist if h[0] == st and h[2] == "raise")
        key = (obs["hand_id"], st, tuple(opps), tuple(sorted(aggr_now)))
        if key in self.cache:
            return self.cache[key]
        opps_sim = opps[:4]
        ws = [self.opp_weights(obs, s, board) for s in opps_sim]
        M = 150 if len(opps_sim) == 1 else 105 if len(opps_sim) == 2 else 70
        if time.perf_counter() - self.t0 > 0.00015:
            M = M // 2
        e = self.mc(hole, board, opps_sim, ws, aggr_now, hist, st, M)
        if len(opps) > 4:
            e = e ** (len(opps) / 4.0)
        self.cache[key] = e
        return e

    def mc(self, hole, board, opps, ws, aggr_now, hist, st, M):
        rng = self.nrng
        known = set(hole) | set(board)
        rem = np.array([c for c in ev.DECK if c not in known], dtype=np.int64)
        n_opp = len(opps)
        need = 5 - len(board)
        k = 2 * n_opp + need
        R = len(rem)
        bank = BANK.get(R)
        if bank is None:
            drawn = rem[rng.random((M, R)).argsort(axis=1)[:, :k]]
        else:
            o0 = int(rng.integers(0, BANK_N - M))
            drawn = rem[bank[o0:o0 + M, :k]]
        bk = ev.START + sum(ev.KEY[c] for c in board)
        board_arr = np.array(board, dtype=np.int64)
        if need:
            bcards = drawn[:, 2 * n_opp:]
            bsum = bk + ev.KEY_NP[bcards].sum(axis=1)
            ball = np.concatenate([np.broadcast_to(board_arr, (M, len(board))), bcards], axis=1)
        else:
            bsum = np.full(M, bk, dtype=np.int64)
            ball = np.broadcast_to(board_arr, (M, 5))
        hk = ev.KEY[hole[0]] + ev.KEY[hole[1]]
        hcards = np.concatenate([np.broadcast_to(np.array(hole, dtype=np.int64), (M, 2)), ball], axis=1)
        hv = ev.ev_np(bsum + hk, hcards)
        w = np.ones(M)
        best = np.full(M, -2, dtype=np.int64)
        nbest = np.zeros(M)
        brm = 0
        bsuits = [0, 0, 0, 0]
        for b in board:
            brm |= 1 << (b >> 2)
            bsuits[b & 3] += 1
        top_board = max(b >> 2 for b in board)
        fsuit = max(range(4), key=lambda i: bsuits[i])
        fcount = bsuits[fsuit]
        for i in range(n_opp):
            o = drawn[:, 2 * i:2 * i + 2]
            ow = ws[i]
            if ow is not None:
                w = w * ow[ev.CLS[o[:, 0], o[:, 1]]]
            s = opps[i]
            # postflop action weighting: bettors/raisers usually connect
            r1 = o[:, 0] >> 2
            r2 = o[:, 1] >> 2
            hit = (((brm >> r1) & 1) | ((brm >> r2) & 1) | (r1 == r2)).astype(bool)
            fd = np.zeros(M, dtype=bool)
            if fcount >= 2 and st < 3:
                fd = ((o[:, 0] & 3) == fsuit) & ((o[:, 1] & 3) == fsuit) if fcount == 2 else (((o[:, 0] & 3) == fsuit) | ((o[:, 1] & 3) == fsuit))
            strong = hit | fd
            nagg = sum(1 for h in hist if h[0] >= 1 and h[1] == s and h[2] == "raise")
            ncall = sum(1 for h in hist if h[0] >= 1 and h[1] == s and h[2] == "call")
            if nagg or ncall:
                ag = self.st(s).aggr()
                # raised over someone's bet this street?
                ra = 0
                seen_bet = False
                for h in hist:
                    if h[0] == st and h[2] == "raise":
                        if h[1] == s and seen_bet:
                            ra += 1
                        seen_bet = True
                keep = (0.6 ** (nagg + ra)) * (0.8 ** ncall)
                keep = 0.12 if keep < 0.12 else keep
                # opponent's current made-hand strength on this board, as a percentile among samples
                cv = ev.ev_np(bk + ev.KEY_NP[o].sum(axis=1), np.concatenate([o, np.broadcast_to(board_arr, (M, len(board)))], axis=1))
                rk = np.empty(M)
                rk[cv.argsort(kind="stable")] = np.arange(M) / M
                bw = (0.1 + 0.4 * ag) if nagg else 0.3
                wv = np.where(rk >= 1.0 - keep, 1.0, bw)
                if st < 3:
                    wv = np.where(fd, np.maximum(wv, 0.7), wv)
                w = w * wv
            ov = ev.ev_np(bsum + ev.KEY_NP[o].sum(axis=1), np.concatenate([o, ball], axis=1))
            gt = ov > best
            eqm = ov == best
            nbest = np.where(gt, 1, np.where(eqm, nbest + 1, nbest))
            best = np.maximum(best, ov)
        win = np.where(hv > best, 1.0, np.where(hv == best, 1.0 / (nbest + 1), 0.0))
        sw = w.sum()
        if sw <= 1e-9:
            return float(win.mean())
        return float((win * w).sum() / sw)

    def postflop(self, obs):
        me, opps, live_opps, eff = self.ctx(obs)
        stacks, bets = obs["stacks"], obs["bets"]
        stack = stacks[me]
        bb = obs["bb"] or 1
        pot = obs["pot"]
        to_call = obs["to_call"]
        st = obs["street_index"]
        hist = obs["history"]
        can_raise = ("raise" in obs["legal"] or "bet" in obs["legal"]) and obs["max_raise_to"] > 0
        n_opp = len(opps)
        e = self.equity(obs)
        r = self.rng.random()
        # was I the last aggressor on the previous street(s)?
        prev_aggr = [h[1] for h in hist if h[0] < st and h[2] == "raise"]
        i_was_aggr = bool(prev_aggr) and prev_aggr[-1] == me
        eff_rem = min(stack, max([stacks[s] for s in opps], default=0) + max(0, max([bets[s] for s in opps], default=0) - bets[me]))
        spr = eff_rem / max(1, pot)
        fold_rate = sum(self.st(s).fold_to_bet() for s in opps) / max(1, n_opp)

        if to_call == 0:
            vthr = 0.64 if n_opp == 1 else 0.56 if n_opp == 2 else 0.5
            if e >= vthr and can_raise:
                frac = 0.75 if e > 0.8 else 0.6
                if fold_rate < 0.35:
                    frac += 0.2
                if spr < 1.3:
                    return self._ret_raise(obs, obs["max_raise_to"])
                return self._ret_raise(obs, frac * pot)
            # bluffs / semi-bluffs
            if can_raise and n_opp <= 2:
                bf = 0.0
                if st == 1 and i_was_aggr:
                    bf = (0.55 if n_opp == 1 else 0.25) * (0.6 + fold_rate)
                elif st == 2 and e >= 0.35:
                    bf = 0.35 * (0.6 + fold_rate)
                elif st == 3 and e < 0.25 and n_opp == 1:
                    bf = 0.25 * (0.4 + fold_rate)
                elif st == 2 and n_opp == 1 and i_was_aggr:
                    bf = 0.3 * (0.6 + fold_rate)
                if r < bf:
                    return self._ret_raise(obs, 0.55 * pot)
            return {"action": "check"}

        # facing a bet
        potodds = to_call / (pot + to_call)
        rthr = (0.78 if n_opp == 1 else 0.7) + 0.5 * PREM.get(len(obs["alive"]), 0.05)
        if e >= rthr and can_raise:
            if spr < 2.5 or to_call >= 0.35 * stack:
                return self._ret_raise(obs, obs["max_raise_to"])
            return self._ret_raise(obs, 2.6 * (bets[me] + to_call) + 0.3 * pot)
        need = potodds + 0.02
        if st < 3:
            need -= 0.03  # some realization/implied odds
        need += PREM.get(len(obs["alive"]), 0.05) * min(1.0, to_call / max(1.0, stack))
        if e >= need:
            if to_call >= stack * 0.9 and e < potodds + 0.05 and e < 0.5:
                return self._ret_fold(obs)
            return {"action": "call"}
        return self._ret_fold(obs)

    # ------------------------------------------------------------ observe
    def observe(self, event):
        try:
            self._observe(event)
        except Exception:
            pass

    def _observe(self, event):
        if event.get("type") != "hand_end":
            return
        self.cache = {}
        hist = event.get("history") or []
        seen = set()
        raised_pre = False
        faced = {}
        cur_street = -1
        street_bet = False
        for h in hist:
            stn, s, a, amt = h[0], h[1], h[2], h[3]
            if s == self.seat and a not in ("ante", "sb", "bb", "return"):
                # still track facing for others, but skip own stats
                pass
            if stn != cur_street:
                cur_street = stn
                street_bet = False
            if a in ("ante", "sb", "bb"):
                seen.add(s)
                continue
            if a == "return":
                continue
            seen.add(s)
            x = self.st(s)
            if stn == 0:
                if raised_pre:
                    x.f2r_opp += 1
                    if a == "fold":
                        x.f2r += 1
                if a in ("call", "raise"):
                    x.vpip += 1 if s not in faced else 0
                    faced[s] = 1
                if a == "raise":
                    x.pfr += 1 if faced.get(s) != 2 else 0
                    faced[s] = 2
                    raised_pre = True
            else:
                if a in ("raise", "call", "check"):
                    x.pa += 1
                    if a == "raise":
                        x.pagg += 1
                if street_bet:
                    x.fb_opp += 1
                    if a == "fold":
                        x.fb += 1
                if a == "raise":
                    street_bet = True
        for s in seen:
            self.st(s).hands += 1
        # all-in call tracking
        start = self.prev_stacks
        self.prev_stacks = list(event.get("stacks") or [])
        if start and len(start) >= 8:
            committed = {}
            street_bet = {}
            cur = -1
            facing_allin = False
            for h in hist:
                stn, s, a, amt = h[0], h[1], h[2], h[3]
                if stn != cur:
                    cur = stn
                    for k in street_bet:
                        committed[k] = committed.get(k, 0) + street_bet[k]
                    street_bet = {}
                    facing_allin = False
                if a in ("sb", "bb", "raise"):
                    street_bet[s] = amt
                    if a == "raise" and committed.get(s, 0) + amt >= start[s] > 0:
                        facing_allin = True
                        continue
                elif a == "call":
                    street_bet[s] = max(street_bet.values()) if street_bet else amt
                if facing_allin and s != self.seat and a in ("call", "fold", "raise"):
                    x = self.st(s)
                    x.jc_opp += 1
                    if a != "fold":
                        x.jc += 1
