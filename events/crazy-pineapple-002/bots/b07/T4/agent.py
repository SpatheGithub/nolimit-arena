"""b07 crazy pineapple bot: preflop equity table for 3-card hands, short
Monte Carlo postflop (time-boxed), push/fold when short, range-aware calling,
simple per-seat opponent stats."""
import json
import os
import random
import time

from .ev import CARD, KEY, RBIT, RT, ST, START, FLUSHBIT_SUIT, ev

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "pre3.json")) as _f:
    _PRE = json.load(_f)
PRE = {}
for _k, _v in _PRE.items():
    a, b, c = (int(x) for x in _k.split(","))
    PRE[(a, b, c)] = (_v[0], _v[1])
del _PRE
# percentiles (fraction of hands strictly better), 0 = best
_e1 = sorted((v[0] for v in PRE.values()), reverse=True)
_e3 = sorted((v[1] for v in PRE.values()), reverse=True)


def _pct_table(sorted_desc):
    n = len(sorted_desc)
    out = {}
    for i, v in enumerate(sorted_desc):
        if v not in out:
            out[v] = i / n
    return out


_P1 = _pct_table(_e1)
_P3 = _pct_table(_e3)
PCT = {k: (0.5 * (_P1[v[0]] + _P3[v[1]])) for k, v in PRE.items()}
# average HU equity of the top-x fraction of hands (for range estimates)
_cum = []
_s = 0.0
for _i, _v in enumerate(_e1):
    _s += _v
    _cum.append(_s / (_i + 1))


def range_eq(x):
    """Average HU equity vs random of the top fraction x of hands."""
    i = int(max(0.005, min(1.0, x)) * len(_cum)) - 1
    return _cum[max(0, i)]


def val(s, cards):
    fl = s & 0x8888
    if fl:
        su = FLUSHBIT_SUIT[fl]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= RBIT[c]
        f = ST[m]
        r = RT[s >> 16]
        return f if f > r else r
    return RT[s >> 16]


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        n = config.get("seats", 8)
        # per-seat stats: hands seen, vpip, pfr, postflop aggressive, postflop passive
        self.st = {}
        self.pf_aggr = False  # we raised preflop this hand
        self.last_hand = -1
        self.budget = 0.0003
        self.hs_id = -1
        self.hs = None

    # ------------------------------------------------------------ helpers
    def stat(self, s):
        d = self.st.get(s)
        if d is None:
            d = self.st[s] = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        return d

    def shove_freq(self, s):
        d = self.stat(s)
        return (d[7] + 0.05 * 3) / (d[8] + 3.0)

    def ftb(self, s):
        d = self.stat(s)
        return (d[6] + 1.2) / (d[5] + 3.0)

    def vpip(self, s):
        d = self.stat(s)
        return (d[1] + 0.25 * 4) / (d[0] + 4)

    def pfr(self, s):
        d = self.stat(s)
        return (d[2] + 0.15 * 4) / (d[0] + 4)

    def aggr(self, s):
        d = self.stat(s)
        return (d[3] + 1.0) / (d[3] + d[4] + 3.0)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            bet_st = -1
            for h in hist:
                st, seat, act = h[0], h[1], h[2]
                seen.add(seat)
                if st > 0 and act in ("fold", "call", "raise") and bet_st == st:
                    d = self.stat(seat)
                    d[5] += 1
                    if act == "fold":
                        d[6] += 1
                if st > 0 and act == "raise":
                    bet_st = st
                if st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        self.stat(seat)[3] += 1
                    elif act in ("call", "check"):
                        self.stat(seat)[4] += 1
            if self.hs is not None and event.get("hand_id") == self.hs_id:
                hs = self.hs
                shv = set()
                for h in hist:
                    if h[0] == 0 and h[2] == "raise" and h[1] < len(hs) and h[3] >= hs[h[1]] - 1:
                        shv.add(h[1])
                for s in seen:
                    d = self.stat(s)
                    d[8] += 1
                    if s in shv:
                        d[7] += 1
            for s in seen:
                d = self.stat(s)
                d[0] += 1
                if s in vp:
                    d[1] += 1
                if s in pr:
                    d[2] += 1
        except Exception:
            pass

    # ------------------------------------------------------------ actions
    def a_fold(self, o):
        return {"action": "check"} if "check" in o["legal"] else {"action": "fold"}

    def a_call(self, o):
        if o["to_call"] == 0:
            return {"action": "check"}
        if "call" in o["legal"]:
            return {"action": "call"}
        return self.a_fold(o)

    def a_raise(self, o, amt):
        if not (("raise" in o["legal"] or "bet" in o["legal"]) and o["max_raise_to"] > 0):
            return self.a_call(o)
        a = int(amt)
        lo, hi = o["min_raise_to"], o["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        # if the raise leaves us with little behind, just shove
        me = o["seat"]
        stack_tot = o["stacks"][me] + o["bets"][me]
        if a > 0.7 * stack_tot:
            a = hi
        return {"action": "raise", "amount": a}

    def a_allin(self, o):
        if ("raise" in o["legal"] or "bet" in o["legal"]) and o["max_raise_to"] > 0:
            return {"action": "raise", "amount": o["max_raise_to"]}
        return self.a_call(o)

    # ------------------------------------------------------------ main
    def act(self, obs):
        t0 = time.perf_counter()
        try:
            if obs["phase"] == "discard":
                return self.discard(obs, t0)
            if obs["street_index"] == 0:
                if obs["hand_id"] != self.hs_id:
                    self.hs_id = obs["hand_id"]
                    self.hs = [a + b for a, b in zip(obs["stacks"], obs["bets"])]
                return self.preflop(obs)
            return self.postflop(obs, t0)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    # ------------------------------------------------------------ discard
    def discard(self, o, t0):
        hole = [CARD[c] for c in o["hole"]]
        board = [CARD[c] for c in o["board"]]
        k = o.get("n_discard") or 1
        if len(hole) != 3 or k != 1:
            return {"action": "discard", "cards": list(o["hole"][:k])}
        opts = ((0, 1, 2), (0, 2, 1), (1, 2, 0))
        eqs = self.mc3(hole, board, t0, 0.0004)
        best = max(range(3), key=lambda i: eqs[i])
        return {"action": "discard", "cards": [o["hole"][opts[best][2]]]}

    # Monte Carlo: hero 3 cards on a 3-card board; equity of each keep option
    # vs one random opponent (3 cards, keeps his best two on the final board).
    def mc3(self, hole, board, t0, budget):
        dead = set(hole) | set(board)
        deck = [c for c in range(52) if c not in dead]
        pairs = ((hole[0], hole[1]), (hole[0], hole[2]), (hole[1], hole[2]))
        hk = [KEY[a] + KEY[b] for a, b in pairs]
        bsum = START
        for c in board:
            bsum += KEY[c]
        w = [0.0, 0.0, 0.0]
        n = 0
        sample = self.rng.sample
        clock = time.perf_counter
        t_end = t0 + budget
        while True:
            for _ in range(10):
                t, r, o1, o2, o3 = sample(deck, 5)
                sb = bsum + KEY[t] + KEY[r]
                bc = board + [t, r]
                k1, k2, k3 = KEY[o1], KEY[o2], KEY[o3]
                a = val(bsum + k1 + k2, board + [o1, o2])
                b = val(bsum + k1 + k3, board + [o1, o3])
                c = val(bsum + k2 + k3, board + [o2, o3])
                if a >= b and a >= c:
                    ov = val(sb + k1 + k2, bc + [o1, o2])
                elif b >= c:
                    ov = val(sb + k1 + k3, bc + [o1, o3])
                else:
                    ov = val(sb + k2 + k3, bc + [o2, o3])
                for i in range(3):
                    hv = val(sb + hk[i], bc + list(pairs[i]))
                    if hv > ov:
                        w[i] += 1.0
                    elif hv == ov:
                        w[i] += 0.5
                n += 1
            if clock() > t_end or n >= 600:
                break
        return [x / n for x in w]

    # hero 2 cards, board 4 or 5 cards; opponent dealt 3 cards and kept
    # the 2 making his best hand on the flop.
    def mc2(self, hole, board, t0, budget):
        dead = set(hole) | set(board)
        deck = [c for c in range(52) if c not in dead]
        need = 5 - len(board)
        bsum = START
        for c in board:
            bsum += KEY[c]
        flop = board[:3]
        fsum = START
        for c in flop:
            fsum += KEY[c]
        hsum = bsum + KEY[hole[0]] + KEY[hole[1]]
        w = 0.0
        n = 0
        sample = self.rng.sample
        clock = time.perf_counter
        t_end = t0 + budget
        hv0 = val(hsum, board + hole) if need == 0 else 0
        while True:
            for _ in range(10):
                d = sample(deck, 3 + need)
                o1, o2, o3 = d[0], d[1], d[2]
                k1, k2, k3 = KEY[o1], KEY[o2], KEY[o3]
                a = val(fsum + k1 + k2, flop + [o1, o2])
                b = val(fsum + k1 + k3, flop + [o1, o3])
                c = val(fsum + k2 + k3, flop + [o2, o3])
                if a >= b and a >= c:
                    ok, oc = k1 + k2, [o1, o2]
                elif b >= c:
                    ok, oc = k1 + k3, [o1, o3]
                else:
                    ok, oc = k2 + k3, [o2, o3]
                if need:
                    r = d[3]
                    kr = KEY[r]
                    bc = board + [r]
                    hv = val(hsum + kr, bc + hole)
                    ov = val(bsum + kr + ok, bc + oc)
                else:
                    hv = hv0
                    ov = val(bsum + ok, board + oc)
                if hv > ov:
                    w += 1.0
                elif hv == ov:
                    w += 0.5
                n += 1
            if clock() > t_end or n >= 800:
                break
        return w / n

    # ------------------------------------------------------------ context
    def ctx(self, o):
        me = o["seat"]
        st = o["street_index"]
        hist = o["history"]
        raises = 0
        callers = 0
        raiser = -1
        for h in hist:
            if h[0] == st:
                if h[2] == "raise":
                    raises += 1
                    raiser = h[1]
                    callers = 0
                elif h[2] == "call":
                    callers += 1
        alive = o["alive"]
        in_hand = o["in_hand"]
        stacks = o["stacks"]
        bets = o["bets"]
        n = len(alive)
        btn = o["button"]
        bi = alive.index(btn) if btn in alive else 0
        if st == 0:
            if n == 2:
                order = [alive[bi], alive[1 - bi]]
            else:
                bbs = o["bb_seat"]
                j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
                order = alive[j:] + alive[:j]
        else:
            order = alive[bi + 1:] + alive[:bi + 1]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        opps = [s for s in in_hand if s != me]
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(stacks[me] + bets[me], other)
        return raises, callers, raiser, behind, opps, eff

    # ------------------------------------------------------------ preflop
    def preflop(self, o):
        me = o["seat"]
        bb = o["bb"] or 1
        hole = sorted(CARD[c] for c in o["hole"])
        if len(hole) == 3:
            e1, e3 = PRE[tuple(hole)]
            p = PCT[tuple(hole)]
        else:
            e1, e3, p = 0.5, 0.25, 0.5
        raises, callers, raiser, behind, opps, eff = self.ctx(o)
        eff_bb = eff / bb
        stack = o["stacks"][me] + o["bets"][me]
        to_call = o["to_call"]
        pot = o["pot"]
        nb = len(behind)
        n_alive = len(o["alive"])
        if raises == 0:
            # unopened or limped
            if eff_bb <= 13:
                # push/fold by EV
                if self.shove_ev(o, e1, opps) > (0.15 * pot if to_call == 0 else 0.0):
                    return self.a_allin(o)
                if to_call == 0:
                    return {"action": "check"}
                return self.a_fold(o)
            open_thr = {0: 0.6, 1: 0.5, 2: 0.38, 3: 0.27, 4: 0.2, 5: 0.16, 6: 0.13}.get(nb, 0.12)
            if n_alive == 2:
                open_thr = 0.72
            # steal more against tight blinds
            if nb <= 2 and behind:
                fold_more = sum(1 for s in behind if self.vpip(s) < 0.2)
                open_thr += 0.05 * fold_more
            if callers:
                open_thr = 0.10 + 0.02 * (nb <= 2)
                if n_alive == 2:
                    open_thr = 0.35
            if p <= open_thr:
                size = (2.2 + callers) * bb if eff_bb > 25 else 2.1 * bb + callers * bb
                if o["sb_seat"] == me and nb == 1:
                    size = 3 * bb
                self.pf_aggr = True
                return self.a_raise(o, size)
            if to_call == 0:
                return {"action": "check"}
            # limp/complete cheaply with decent hands in late spots
            if callers and p <= 0.25 and to_call <= bb and eff_bb > 20:
                return self.a_call(o)
            if o["sb_seat"] == me and p <= 0.3 and to_call <= bb / 2 + 1 and eff_bb > 20:
                return self.a_call(o)
            return self.a_fold(o)

        # facing a raise
        rbet = max(o["bets"])
        cost_frac = to_call / max(stack, 1)
        pot_odds = to_call / (pot + to_call)
        # raiser range estimate
        rs = raiser if raiser >= 0 else (opps[0] if opps else me)
        r_stack_bb = (o["stacks"][rs] + o["bets"][rs]) / bb if rs != me else 50
        width = self.pfr(rs) * (1.0 if raises == 1 else 0.45)
        allin_r = o["stacks"][rs] == 0 if rs != me else False
        if allin_r and r_stack_bb < 15:
            width = max(width, 0.25 + 0.02 * (15 - r_stack_bb))
        if allin_r and raises == 1:
            width = max(width, 1.8 * self.shove_freq(rs))
        width = max(0.03, min(0.8, width))
        eq_vs = 0.5 + (e1 - range_eq(width))
        n_in = len(opps)
        if n_in > 1:
            eq_vs = eq_vs ** (1 + 0.6 * (n_in - 1))
        # ICM-ish margin when risking much of the stack
        margin = 0.0
        if cost_frac > 0.3 and n_alive > 2:
            margin = 0.03 + 0.01 * min(n_alive - 2, 4)
        # re-steal shove with fold equity
        if raises == 1 and rs != me and not allin_r and o["max_raise_to"] > 0 and stack <= 25 * bb:
            if self.resteal_ev(o, e1, rs, width, opps) > 0.05 * pot:
                return self.a_allin(o)
        commit = cost_frac > 0.4 or eff_bb <= 15
        if commit:
            if eq_vs >= pot_odds + margin + 0.02:
                if eq_vs > 0.55 and o["max_raise_to"] > 0:
                    return self.a_allin(o)
                return self.a_call(o)
            return self.a_fold(o)
        # deep: 3-bet value, call with good hands
        three_thr = 0.035 if raises == 1 else 0.015
        three_thr += 0.5 * max(0.0, width - 0.15) * (1 if raises == 1 else 0.5)
        if p <= three_thr:
            self.pf_aggr = True
            return self.a_raise(o, 3 * rbet + 1 * bb * callers)
        # call by pot odds with equity realization
        R = 0.72 if me in (o["bb_seat"], o["sb_seat"]) else 0.85
        if n_alive == 2:
            R = 0.85 if me == o["bb_seat"] else 0.95
        if to_call > 0.2 * stack:
            R *= 0.85
        if n_alive >= 4:
            call_thr = 0.10 if raises == 1 else 0.03
            if me == o["bb_seat"]:
                call_thr += 0.06
            call_thr += 0.3 * max(0.0, width - 0.15)
            if to_call > 0.12 * stack:
                call_thr *= 0.6
            if p > call_thr:
                return self.a_fold(o)
        if eq_vs * R >= pot_odds and to_call <= 0.35 * stack:
            return self.a_call(o)
        return self.a_fold(o)

    # ------------------------------------------------------------ postflop
    def postflop(self, o, t0):
        me = o["seat"]
        bb = o["bb"] or 1
        hole = [CARD[c] for c in o["hole"]]
        board = [CARD[c] for c in o["board"]]
        raises, callers, raiser, behind, opps, eff = self.ctx(o)
        if len(hole) == 3:
            eqs = self.mc3(hole, board, t0, self.budget)
            eq1 = max(eqs)
        else:
            eq1 = self.mc2(hole, board, t0, self.budget)
        n_opp = max(1, len(opps))
        eq = eq1 ** n_opp if n_opp > 1 else eq1
        pot = o["pot"]
        to_call = o["to_call"]
        stack = o["stacks"][me]
        st = o["street_index"]
        if to_call == 0:
            ftb = min(self.ftb(s) for s in opps) if opps else 0.4
            sticky = ftb < 0.33
            # value bet
            vthr = 0.62 if sticky else 0.68
            if eq >= vthr or (eq1 >= 0.8 and n_opp <= 2):
                frac = 0.75 if eq < 0.85 else 0.9
                if sticky:
                    frac += 0.15
                return self.a_raise(o, frac * pot)
            # c-bet / bluff
            if n_opp == 1 and st == 1 and raiser < 0 and self.was_pf_aggr(o):
                if eq1 >= 0.45 or self.rng.random() < max(0.12, min(0.7, 1.1 * ftb)):
                    return self.a_raise(o, 0.5 * pot)
            if n_opp == 1 and not behind and eq1 < 0.35 and st >= 2 and self.rng.random() < 0.35 * ftb:
                return self.a_raise(o, 0.6 * pot)
            return {"action": "check"}
        # facing a bet
        pot_before = pot - sum(o["bets"])  # chips before this street
        bet_frac = to_call / max(1, pot - to_call) if pot > to_call else 1.0
        f = 0.28 + 0.22 * min(bet_frac, 1.5) + 0.15 * max(0, raises - 1)
        if raiser >= 0:
            ag = self.aggr(raiser)
            f -= 0.3 * max(0.0, ag - 0.4)
            f += 0.15 * max(0.0, 0.25 - ag)
        if st == 3:
            f += 0.05
        if to_call > 0.3 * stack and eff > 25 * bb:
            f += 0.15
        f = max(0.1, min(0.85, f))
        eq_adj = max(0.0, (eq - f) / (1 - f))
        pot_odds = to_call / (pot + to_call)
        n_alive = len(o["alive"])
        margin = 0.0
        if to_call > 0.4 * stack and n_alive > 2:
            margin = 0.04
        if eq_adj >= 0.72 and eq1 >= 0.85:
            return self.a_raise(o, o["bets"][raiser] * 2.5 + pot * 0.3 if raiser >= 0 else pot)
        if eq_adj >= pot_odds + margin:
            return self.a_call(o)
        return self.a_fold(o)

    def shove_ev(self, o, e1, opps):
        """Chip EV of shoving now vs folding, with ICM-ish loss penalty."""
        me = o["seat"]
        bb = o["bb"] or 1
        stacks, bets = o["stacks"], o["bets"]
        S = stacks[me] + bets[me]
        b0 = bets[me]
        pot = o["pot"]
        p_nc = 1.0
        best = None
        for s in opps:
            tot = stacks[s] + bets[s]
            if stacks[s] <= 0:
                continue
            E = min(S, tot)
            risk_bb = max(1.0, (E - bets[s]) / bb)
            c = 1.6 / risk_bb
            v = self.vpip(s)
            c *= (v / 0.25) ** 0.5
            c = max(0.03, min(0.75, c))
            p_nc *= (1 - c)
            if best is None or c > best[0]:
                best = (c, E, bets[s])
        if best is None:
            return pot
        c, E, bj = best
        eq = 0.5 + (e1 - range_eq(c))
        eq = max(0.05, min(0.95, eq))
        final_pot = pot - b0 - bj + 2 * E
        risk = E - b0
        n_alive = len(o["alive"])
        icm_k = 0.0 if n_alive <= 2 else 0.08 + 0.02 * min(n_alive - 3, 4)
        called = eq * final_pot - risk - icm_k * (1 - eq) * risk
        return p_nc * pot + (1 - p_nc) * called

    def resteal_ev(self, o, e1, rs, width, opps):
        me = o["seat"]
        bb = o["bb"] or 1
        stacks, bets = o["stacks"], o["bets"]
        S = stacks[me] + bets[me]
        b0 = bets[me]
        pot = o["pot"]
        Er = min(S, stacks[rs] + bets[rs])
        add_r = max(1.0, (Er - bets[rs]) / bb)
        c_call = 1.8 / add_r * (self.vpip(rs) / 0.25) ** 0.5
        c_call = max(0.02, min(width, c_call))
        p_nc = 1.0 - c_call / width
        for s in opps:
            if s == rs or stacks[s] <= 0:
                continue
            E = min(S, stacks[s] + bets[s])
            risk_bb = max(1.0, (E - bets[s]) / bb)
            c = max(0.02, min(0.6, 1.6 / risk_bb * (self.vpip(s) / 0.25) ** 0.5))
            p_nc *= (1 - c)
        eq = 0.5 + (e1 - range_eq(c_call))
        eq = max(0.05, min(0.95, eq))
        final_pot = pot - b0 - bets[rs] + 2 * Er
        risk = Er - b0
        n_alive = len(o["alive"])
        icm_k = 0.0 if n_alive <= 2 else 0.08 + 0.02 * min(n_alive - 3, 4)
        called = eq * final_pot - risk - icm_k * (1 - eq) * risk
        return p_nc * pot + (1 - p_nc) * called

    def was_pf_aggr(self, o):
        me = o["seat"]
        last = -1
        for h in o["history"]:
            if h[0] == 0 and h[2] == "raise":
                last = h[1]
        return last == me
