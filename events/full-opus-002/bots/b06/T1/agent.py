"""b06 bot: preflop EV push/fold + range equities, ICM bubble factors computed
in observe(), opponent stats, heuristic postflop."""

import json
import os
import random

from ._common import (CARD, PREFLOP, Spot, Variant, act_allin, act_call, act_fold, act_raise,
                      features, safe_default, HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH)

_DIR = os.path.dirname(os.path.abspath(__file__))
_PRE = PREFLOP["std"]
_PCT = _PRE.pct
with open(os.path.join(_DIR, "eqmat.json")) as _f:
    _EQ = json.load(_f)


def _ncombo(c):
    a, b = c // 13, c % 13
    return 6 if a == b else 4 if a > b else 12


_ORDER = sorted(range(169), key=lambda c: _PCT[c])
_W = [_ncombo(c) for c in _ORDER]
_GRID = 50  # range widths 2%, 4%, ..., 100%
# _ER[c][k]: equity of class c vs the top (k+1)*2% of hands
_ER = []
for _c in range(169):
    row = _EQ[_c]
    cum = 0.0
    wsum = 0.0
    out = []
    k = 0
    for idx, oc in enumerate(_ORDER):
        w = _W[idx]
        if oc == _c:
            w = w * (0.5 if _c // 13 == _c % 13 else 0.75)  # card removal, rough
        cum += w * row[oc]
        wsum += w
        while k < _GRID and wsum >= (k + 1) / _GRID * 1326 * 0.999:
            out.append(cum / wsum)
            k += 1
    while len(out) < _GRID:
        out.append(cum / wsum)
    _ER.append(out)


def eq_range(c, width):
    if width >= 1.0:
        return _ER[c][_GRID - 1]
    x = width * _GRID - 1
    if x <= 0:
        return _ER[c][0]
    i = int(x)
    f = x - i
    r = _ER[c]
    return r[i] * (1 - f) + r[i + 1] * f


def icm(stacks, pay):
    n = len(stacks)
    E = [0.0] * n
    T = float(sum(stacks))
    if T <= 0 or n == 0:
        return E
    pay = list(pay[:n]) + [0.0] * max(0, n - len(pay))
    zero = [i for i in range(n) if stacks[i] <= 0]
    if zero:
        # busted players share the bottom places
        m = n - len(zero)
        share = sum(pay[m:n]) / len(zero)
        for i in zero:
            E[i] = share
        pay = pay[:m] + [0.0] * len(zero)
    paid = 0
    for k, p in enumerate(pay):
        if p:
            paid = k + 1
    cur = {0: (1.0, T)}
    for place in range(min(paid, n)):
        pp = pay[place]
        nxt = {}
        for mask, (p, R) in cur.items():
            if R <= 0:
                continue
            for i in range(n):
                if mask >> i & 1:
                    continue
                s = stacks[i]
                if s <= 0:
                    continue
                q = p * s / R
                E[i] += q * pp
                m2 = mask | (1 << i)
                o = nxt.get(m2)
                if o is None:
                    nxt[m2] = (q, R - s)
                else:
                    nxt[m2] = (o[0] + q, o[1])
        cur = nxt
    return E


# Nash-ish call widths vs a shove, by caller's effective stack in bb
_CALLW = [(1, 0.80), (2, 0.65), (3, 0.52), (4, 0.43), (5, 0.37), (6, 0.32), (7, 0.28), (8, 0.25),
          (10, 0.20), (12, 0.17), (15, 0.14), (20, 0.105), (25, 0.085), (35, 0.065), (60, 0.05)]
# typical open-shove widths by shover's stack in bb
_SHOVEW = [(2, 0.70), (4, 0.55), (6, 0.45), (8, 0.38), (10, 0.32), (13, 0.25), (16, 0.20),
           (20, 0.15), (30, 0.10), (50, 0.07), (100, 0.05)]


def _interp(tab, x):
    if x <= tab[0][0]:
        return tab[0][1]
    for i in range(1, len(tab)):
        if x <= tab[i][0]:
            x0, y0 = tab[i - 1]
            x1, y1 = tab[i]
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tab[-1][1]


# open-raise widths by players left to act behind
_OPENW = {0: 0.0, 1: 0.42, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14, 7: 0.12}


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        self.nseats = config.get("seats", 8)
        st = config.get("starting_stack", 2000)
        # opponent stats per seat
        self.hands = {}
        self.vpip = {}
        self.pfr = {}
        self.shoves = {}
        self.pf_aggr = {}
        self.pf_pass = {}
        self.bf = {}
        self._last_hand = -1
        self._seen_hands = set()
        self.failures = 0
        self.bf_scale = 0.75
        self.prev_stacks = [st] * self.nseats
        self.sc_calls = {}
        self.sc_exp = {}
        self.post_aggr = {}
        self.post_pass = {}
        stacks = [st] * self.nseats
        self._compute_bf(stacks)

    # ---------- ICM bubble factors for the next hand ----------
    def _compute_bf(self, stacks):
        me = self.seat
        alive = [s for s in range(len(stacks)) if stacks[s] > 0]
        self.bf = {}
        if me not in alive or len(alive) < 2:
            return
        pay = self.points[:len(alive)]
        st = [float(stacks[s]) for s in alive]
        mi = alive.index(me)
        e0 = icm(st, pay)[mi]
        for j, sj in enumerate(alive):
            if sj == me:
                continue
            d = min(st[mi], st[j])
            w = list(st)
            w[mi] += d
            w[j] -= d
            ew = icm(w, pay)[mi]
            l = list(st)
            l[mi] -= d
            l[j] += d
            el = icm(l, pay)[mi]
            gain = ew - e0
            loss = e0 - el
            if gain > 1e-9:
                self.bf[sj] = max(1.0, min(4.0, loss / gain))
            else:
                self.bf[sj] = 1.0

    def _bf(self, seats, risk, mystack, bb=0):
        b = 1.0
        for s in seats:
            v = self.bf.get(s, 1.2)
            if v > b:
                b = v
        if mystack > 0:
            frac = min(1.0, risk / mystack)
            b = 1.0 + (b - 1.0) * (0.35 + 0.65 * frac)
            if bb > 0:
                # short stacks bleed blinds when folding: damp ICM pressure
                mbb = mystack / bb
                if mbb < 15:
                    b = 1.0 + (b - 1.0) * max(0.25, mbb / 15.0)
        return 1.0 + (b - 1.0) * self.bf_scale

    # ---------- opponent stats ----------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            raised = set()
            vp = set()
            shoved = set()
            for h in hist:
                st, seat, act, amt = h[0], h[1], h[2], h[3]
                if seat == self.seat:
                    continue
                if st == 0:
                    if act in ("sb", "bb", "ante"):
                        seen.add(seat)
                        continue
                    seen.add(seat)
                    if act == "raise":
                        raised.add(seat)
                        vp.add(seat)
                        self.pf_aggr[seat] = self.pf_aggr.get(seat, 0) + 1
                    elif act == "call":
                        vp.add(seat)
                        self.pf_pass[seat] = self.pf_pass.get(seat, 0) + 1
            for h in hist:
                if h[0] >= 1 and h[1] != self.seat:
                    if h[2] == "raise":
                        self.post_aggr[h[1]] = self.post_aggr.get(h[1], 0) + 1
                    elif h[2] in ("call", "check"):
                        self.post_pass[h[1]] = self.post_pass.get(h[1], 0) + 1
            for s in seen:
                self.hands[s] = self.hands.get(s, 0) + 1
            for s in raised:
                self.pfr[s] = self.pfr.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
            # calls vs shoves, relative to model width
            start = self.prev_stacks
            bbamt = 0
            for h in hist:
                if h[0] == 0 and h[2] == "bb":
                    bbamt = max(bbamt, h[3])
            if bbamt > 0:
                shove_amt = 0
                bbseat = -1
                for h in hist:
                    if h[0] == 0 and h[2] == "bb":
                        bbseat = h[1]
                for h in hist:
                    if h[0] != 0:
                        continue
                    seat, act, amt = h[1], h[2], h[3]
                    if seat >= len(start):
                        continue
                    if act == "raise" and shove_amt == 0 and amt >= start[seat] and amt >= 4 * bbamt:
                        shove_amt = amt
                        continue
                    if shove_amt and seat != self.seat and act in ("call", "fold", "raise"):
                        eff = min(shove_amt, start[seat]) / bbamt
                        e = _interp(_CALLW, eff) * (1.25 if seat == bbseat else 1.0)
                        self.sc_exp[seat] = self.sc_exp.get(seat, 0.0) + e
                        if act != "fold":
                            self.sc_calls[seat] = self.sc_calls.get(seat, 0) + 1
            stacks = event.get("stacks")
            if stacks:
                self.prev_stacks = list(stacks)
                self._compute_bf(list(stacks))
        except Exception:
            self.failures += 1

    def pfr_est(self, seat, prior=0.16, k=8.0):
        n = self.hands.get(seat, 0)
        return (self.pfr.get(seat, 0) + prior * k) / (n + k)

    def aggr_est(self, seat, prior=0.35, k=6.0):
        a = self.post_aggr.get(seat, 0)
        n = a + self.post_pass.get(seat, 0)
        return (a + prior * k) / (n + k)

    def vpip_est(self, seat, prior=0.25, k=8.0):
        n = self.hands.get(seat, 0)
        return (self.vpip.get(seat, 0) + prior * k) / (n + k)

    # ---------- acting ----------
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            self.failures += 1
            return safe_default(obs)

    def decide(self, obs):
        if obs.get("phase") == "discard":
            return safe_default(obs)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            return self.preflop(sp, obs)
        return self.postflop(sp, obs)

    # shove EV (in chips, losses scaled by ICM bubble factor) vs folding now
    def shove_ev(self, sp, obs, c, callers_info):
        me = sp.me
        my_total = sp.stack + sp.bet
        pot = sp.pot
        pf = 1.0
        ev_called = 0.0
        p_reach = 1.0
        for seat, width in callers_info:
            if width <= 0:
                continue
            tot = obs["stacks"][seat] + obs["bets"][seat]
            eff = min(my_total, tot)
            risk = eff - sp.bet
            win = pot + (eff - obs["bets"][seat])
            eq = eq_range(c, width)
            bf = self._bf([seat], risk, sp.stack, sp.bb)
            ev_c = eq * win - (1 - eq) * risk * bf
            ev_called += p_reach * width * ev_c
            p_reach *= (1 - width)
        pf = p_reach
        return pf * pot + ev_called

    def call_width(self, seat, obs, my_total, bb, is_bb):
        tot = obs["stacks"][seat] + obs["bets"][seat]
        eff = min(my_total, tot) / bb
        w = _interp(_CALLW, eff)
        if is_bb:
            w *= 1.25
        # looser players call wider
        v = self.vpip_est(seat)
        w *= max(0.7, min(1.8, v / 0.25))
        ex = self.sc_exp.get(seat, 0.0)
        if ex > 0:
            k = 1.5
            ratio = (self.sc_calls.get(seat, 0) + k) / (ex + k)
            w *= max(0.4, min(2.5, ratio))
        return min(0.9, w)

    def preflop(self, sp, obs):
        c = _PRE.cls(sp.hole[0], sp.hole[1])
        pct = _PCT[c]
        bb = sp.bb
        me = sp.me
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_total = sp.stack + sp.bet
        my_bb = my_total / bb
        eff_bb = sp.eff_bb
        behind = sp.behind
        nb = len(behind)
        bbseat = obs["bb_seat"]
        hist = sp.hist
        # count raises / limpers
        limpers = 0
        for h in hist:
            if h[0] == 0 and h[2] == "call":
                limpers += 1
        if sp.raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= 14 or (my_bb <= 16 and limpers > 0):
                callers = [(s, self.call_width(s, obs, my_total, bb, s == bbseat)) for s in behind]
                # limpers may call too
                for h in hist:
                    if h[0] == 0 and h[2] == "call" and h[1] != me and h[1] in sp.opps:
                        callers.append((h[1], min(0.9, 1.4 * self.call_width(h[1], obs, my_total, bb, False))))
                ev = self.shove_ev(sp, obs, c, callers)
                cap = 1.0 if nb <= 1 else 0.6 if eff_bb <= 7 else 0.42 if eff_bb <= 10 else 0.30
                if ev > 0.0 and sp.can_raise and pct <= cap:
                    return act_allin(sp)
                return act_fold(sp)
            # deeper: open raise / iso / check
            if sp.can_check:
                # BB with option
                if pct <= 0.10 and sp.can_raise:
                    return act_raise(sp, sp.bet + (3 + limpers) * bb)
                return act_fold(sp)
            w = _OPENW.get(nb, 0.12)
            if behind:
                av = sum(self.vpip_est(x) for x in behind) / len(behind)
                w *= max(0.75, min(1.5, (0.25 / max(0.05, av)) ** 0.5))
            if limpers:
                w *= 0.6
            # short-ish: smaller opens
            size = (2.2 if eff_bb < 25 else 2.5) * bb + limpers * bb
            if sp.role == "SB" and nb == 1:
                size = 3.0 * bb if eff_bb >= 25 else 2.5 * bb
            if pct <= w and sp.can_raise:
                return act_raise(sp, size)
            # SB complete with decent hands vs BB
            if sp.role == "SB" and nb == 1 and limpers == 0 and pct <= 0.6 and sp.to_call <= bb * 0.5 + 1:
                return act_call(sp)
            return act_fold(sp)
        # facing a raise
        raiser = sp.raiser
        to_call = sp.to_call
        rz_total = bets[raiser] if raiser >= 0 else max(bets)
        raiser_allin = raiser >= 0 and stacks[raiser] == 0
        raiser_bb = (stacks[raiser] + bets[raiser]) / bb if raiser >= 0 else 20
        # estimate the raiser's range width
        pfr = self.pfr_est(raiser) if raiser >= 0 else 0.16
        if sp.raises == 1:
            if raiser_allin:
                w = max(_interp(_SHOVEW, raiser_bb), 0.8 * pfr)
            else:
                w = max(0.06, min(0.6, pfr))
        elif sp.raises == 2:
            w = max(0.03, min(0.25, pfr * 0.35)) if not raiser_allin else max(0.05, min(0.3, 0.5 * pfr))
        else:
            w = 0.03
        commit = to_call >= 0.4 * sp.stack or raiser_allin
        # count other callers already in
        n_callers = sp.callers
        eq = eq_range(c, w)
        if n_callers:
            eq = eq * (0.82 ** n_callers)
        involved = [s for s in sp.opps if bets[s] > 0 or stacks[s] == 0] or ([raiser] if raiser >= 0 else [])
        # chips we can actually win: cap others' contributions at our total
        if commit:
            call_amt = min(to_call, sp.stack)
            my_final = sp.bet + call_amt
            pot_eff = 0
            for s in range(len(bets)):
                pot_eff += min(bets[s], my_final) if s != me else 0
            pot_eff += sp.pot - sum(bets)  # dead money from earlier (antes)
            bf = self._bf(involved, call_amt, sp.stack, bb)
            margin = 0.015 * nb
            need = bf * call_amt / (bf * call_amt + pot_eff + 1e-9)
            # option to shove over a non-allin raise
            if not raiser_allin and sp.can_raise and eq > need + margin - 0.02:
                return act_allin(sp)
            if eq >= need + margin:
                return act_call(sp)
            return act_fold(sp)
        # not committing: 3-bet / call / fold
        if sp.raises == 1:
            if eff_bb <= 25 and sp.can_raise:
                # resteal shove
                rw = max(0.08, min(0.6, w * 0.65))
                callers = [(raiser, rw)]
                for s in behind:
                    callers.append((s, self.call_width(s, obs, my_total, bb, s == bbseat)))
                for h in hist:
                    if h[0] == 0 and h[2] == "call" and h[1] != me and h[1] in sp.opps:
                        callers.append((h[1], max(0.1, 0.5 * self.vpip_est(h[1]))))
                ev = self.shove_ev(sp, obs, c, callers)
                cap = 0.30 if eff_bb <= 12 else 0.20 if eff_bb <= 18 else 0.12
                if ev > 0.0 and pct <= cap:
                    return act_allin(sp)
            if pct <= 0.035 and sp.can_raise:
                return act_raise(sp, rz_total * 3 + bets[me] * 0 + limpers * bb)
            # call
            po = to_call / (sp.pot + to_call)
            ip = sp.role not in ("SB", "BB")
            req = po + (0.06 if ip else 0.10)
            if sp.role == "BB":
                req = po + 0.07
            if to_call > 0.2 * sp.stack:
                req += 0.05
            if eq >= req and pct <= 0.45:
                return act_call(sp)
            return act_fold(sp)
        # facing 3-bet or more
        if pct <= 0.02 and sp.can_raise:
            return act_allin(sp)
        po = to_call / (sp.pot + to_call)
        if eq >= po + 0.08 and pct <= 0.06:
            return act_call(sp)
        return act_fold(sp)

    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        n_opp = sp.n_opp
        pot = sp.pot
        to_call = sp.to_call
        street = sp.street
        cards_left = 5 - len(sp.board)
        draw_eq = 0.0
        if cards_left == 2:
            draw_eq = min(0.45, outs * 0.038)
        elif cards_left == 1:
            draw_eq = min(0.25, outs * 0.021)
        # scary boards: four to a flush / straight
        if len(sp.board) >= 4 and cat < FLUSH:
            bs = [0, 0, 0, 0]
            bm = 0
            for x in sp.board:
                bs[x & 3] += 1
                bm |= 1 << (x >> 2)
            mx = max(bs)
            if mx >= 4:
                fs = bs.index(mx)
                if not any((x & 3) == fs for x in sp.hole):
                    s -= 0.18 if mx == 4 else 0.35
            if cat < STRAIGHT:
                bm2 = bm | ((bm >> 12) & 1)  # ace low
                bmx = (bm << 1) | ((bm >> 12) & 1)
                for lo in range(10):
                    if ((bmx >> lo) & 0x1F).bit_count() >= 4:
                        s -= 0.10
                        break
        strength = s - 0.06 * (n_opp - 1)
        eq = max(strength, draw_eq + (0.1 if cat >= PAIR else 0.0) * 0.5)
        stack = sp.stack
        spr = stack / max(1, pot)
        was_aggr = sp.last_aggr == sp.me
        rng = self.rng
        if to_call == 0:
            if not sp.can_raise:
                return act_call(sp)
            if strength >= 0.80:
                return self.bet(sp, 0.7)
            if strength >= 0.62 and n_opp <= 2:
                return self.bet(sp, 0.55)
            loose = max(self.vpip_est(o) for o in sp.opps) if sp.opps else 0.25
            bluff_ok = loose < 0.38
            if was_aggr and n_opp == 1 and street == 1:
                if strength >= 0.3 or outs >= 4 or (bluff_ok and rng.random() < 0.55):
                    return self.bet(sp, 0.4)
            if outs >= 8 and n_opp <= 2 and rng.random() < 0.5:
                return self.bet(sp, 0.55)
            if bluff_ok and n_opp == 1 and sp.ip and strength < 0.3 and rng.random() < 0.25:
                return self.bet(sp, 0.5)
            return act_call(sp)
        # facing a bet: chips above our stack are not winnable
        my_cap = sp.bet + stack
        bets_ = obs["bets"]
        over = 0
        for o in sp.opps:
            if bets_[o] > my_cap:
                over += bets_[o] - my_cap
        pot = pot - over
        to_call = min(to_call, stack)
        po = to_call / (pot + to_call)
        bet_frac = to_call / max(1, pot - to_call)
        # bets signal strength: discount made-hand strength
        adj = strength - 0.05 - 0.08 * min(2.0, bet_frac) - 0.04 - 0.08 * max(0, sp.raises - 1)
        bettor = sp.raiser
        if bettor >= 0:
            adj += max(-0.08, min(0.10, (self.aggr_est(bettor) - 0.35) * 0.4))
            # multi-street aggression from the same bettor
            barrels = set()
            for h in sp.hist:
                if h[1] == bettor and h[2] == "raise" and 1 <= h[0] < street:
                    barrels.add(h[0])
            adj -= 0.04 * len(barrels)
        adj -= 0.03 if street == 2 else 0.06 if street == 3 else 0.0
        e = max(adj, draw_eq)
        commit = to_call >= 0.5 * stack
        if commit:
            bf = self._bf(sp.opps, min(to_call, stack), stack, sp.bb)
            need = bf * to_call / (bf * to_call + pot)
        else:
            need = po
        if strength >= 0.88 and sp.can_raise:
            return self.raise_(sp, 2.8)
        if strength >= 0.78 and sp.raises <= 1 and sp.can_raise and n_opp <= 2:
            return self.raise_(sp, 2.6)
        if e >= need + 0.03:
            return act_call(sp)
        # cheap draws
        if outs >= 8 and cards_left >= 1 and po <= 0.3 and not commit:
            return act_call(sp)
        return act_fold(sp)

    def bet(self, sp, frac):
        target = sp.bet + frac * sp.pot
        if sp.stack - (target - sp.bet) < 0.4 * sp.pot:
            return act_allin(sp)
        return act_raise(sp, target)

    def raise_(self, sp, mult):
        cur = sp.bet + sp.to_call
        target = cur * mult + (sp.pot - cur - sp.bet) * 0.3
        if sp.stack + sp.bet - target < 0.5 * (sp.pot + target):
            return act_allin(sp)
        return act_raise(sp, target)
