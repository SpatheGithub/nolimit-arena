"""b03 bot: tight-aggressive preflop with push/fold when short, simple
made-hand postflop play. Helpers (evaluator, preflop tables) in _common."""

import json
import os
import random

from ._common import (Spot, Variant, act_allin, act_call, act_fold, act_raise, features,
                      safe_default)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eqr.json")) as _f:
    EQR = tuple(tuple(r) for r in json.load(_f)["eqr"])


def eq_vs(c, width):
    """Equity of class c vs the top `width` fraction of hands."""
    k = int(width * 100 + 0.5) - 1
    return EQR[c][0 if k < 0 else 99 if k > 99 else k]


def call_width(e_bb, heads_up):
    """Assumed fraction of hands an opponent calls a shove with, by effective depth."""
    w = P["cw"] / max(e_bb, 1.0)
    if heads_up:
        w *= P["hu_cw"]
    return 0.05 if w < 0.05 else 0.6 if w > 0.6 else w


def shove_width(s_bb, late):
    w = 2.8 / max(s_bb, 1.0)
    if late:
        w *= 1.3
    return 0.06 if w < 0.06 else 0.7 if w > 0.7 else w

P = dict(icmd=15, icmpost=0, icmx=1.0, hu_cw=1.6, blend_bb=30, m3=1, deep=0.05, stackoff=0.10, sdef=0, ftoshove=0, steal=2, cw=1.6, posw=0.0, ftb=1, evpush=1, hu_def=0.45, icm=1, big_frac=0.85, aggmod=0.4, shove3=1, model=1, open_mult=1.3, cbet=0.5, vbet=0.60, raise_pen=0.0, call_tight=0.0, bet_frac=0.65)

# open-raise percentile thresholds by number of players still to act behind
OPEN = {0: 0.45, 1: 0.42, 2: 0.30, 3: 0.24, 4: 0.19, 5: 0.16, 6: 0.14, 7: 0.12}
# open-shove thresholds at ~10bb by players behind
PUSH = {0: 0.60, 1: 0.58, 2: 0.42, 3: 0.33, 4: 0.27, 5: 0.22, 6: 0.19, 7: 0.17}


def icm_me(stacks, me, pay):
    """Malmuth-Harville expected payout of index `me` (stacks > 0 only)."""
    n = len(stacks)
    memo = {}

    def rec(mask, place):
        got = memo.get(mask)
        if got is not None:
            return got
        total = 0.0
        for i in range(n):
            if mask >> i & 1:
                total += stacks[i]
        res = 0.0
        for i in range(n):
            if mask >> i & 1:
                p = stacks[i] / total
                if i == me:
                    res += p * pay[place]
                else:
                    res += p * rec(mask & ~(1 << i), place + 1)
        memo[mask] = res
        return res

    return rec((1 << n) - 1, 0)


BF_A = {8: 0.65, 7: 0.55, 6: 0.45, 5: 0.33, 4: 0.2, 3: 0.06}


class Agent:
    def __init__(self, config):
        self.var = Variant(config.get("variant"))
        self.rng = random.Random(config.get("seed", 0))
        self.seat = config.get("seat")
        self.pf_aggr = False
        self.hand = -1
        self.failed = False
        self.stats = {}
        self.post = {}
        self.ftb = {}
        self.fto = {}
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])

    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception as e:
            if not self.failed:
                self.failed = True
                print("b03 error:", repr(e))
            return safe_default(obs)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            seen, vp, pr = set(), set(), set()
            cur_st, bet_open = -1, False
            for h in event.get("history") or ():
                if h[0] != cur_st:
                    cur_st, bet_open = h[0], False
                if h[0] != 0:
                    if bet_open and h[1] != self.seat and (h[2] == "fold" or h[2] == "call" or h[2] == "raise"):
                        ft = self.ftb.get(h[1])
                        if ft is None:
                            ft = self.ftb[h[1]] = [0, 0]
                        ft[1] += 1
                        if h[2] == "fold":
                            ft[0] += 1
                    if h[2] == "raise":
                        bet_open = True
                    if h[2] == "raise" or h[2] == "call" or h[2] == "check":
                        st = self.post.get(h[1])
                        if st is None:
                            st = self.post[h[1]] = [0, 0]
                        st[0 if h[2] == "raise" else 1] += 1
                    continue
                seen.add(h[1])
                if h[2] == "call" or h[2] == "raise":
                    vp.add(h[1])
                    if h[2] == "raise":
                        pr.add(h[1])
            nr = 0
            acted = set()
            for h in event.get("history") or ():
                if h[0] != 0:
                    break
                a = h[2]
                if a == "fold" or a == "call" or a == "raise":
                    x = h[1]
                    if nr == 1 and x not in acted and x != self.seat:
                        fo = self.fto.get(x)
                        if fo is None:
                            fo = self.fto[x] = [0, 0]
                        fo[1] += 1
                        if a == "fold":
                            fo[0] += 1
                    acted.add(x)
                    if a == "raise":
                        nr += 1
            for x in seen:
                st = self.stats.get(x)
                if st is None:
                    st = self.stats[x] = [0, 0, 0]
                st[0] += 1
                if x in vp:
                    st[1] += 1
                if x in pr:
                    st[2] += 1
        except Exception:
            pass

    def bfac(self, sp, e):
        """Approximate ICM bubble factor for risking e chips (1 = chip EV)."""
        if not P["icmx"]:
            return 1.0
        k = sum(1 for x in sp.obs["alive"] if sp.stacks[x] + sp.bets[x] > 0)
        my_tot = sp.stack + sp.bet
        f = e / my_tot if my_tot > 0 else 1.0
        a = BF_A.get(k, 0.0) * P["icmx"] * (1.0 if f > 1.0 else f)
        if P["icmd"]:
            d = my_tot / (sp.bb * P["icmd"])
            if d < 1.0:
                a *= 0.3 if d < 0.3 else d
        return 1.0 + a

    def need_icm(self, sp, v, chip_need):
        """Equity needed to call villain v's all-in, by ICM when few players remain."""
        if not P["icm"]:
            return chip_need
        alive = [x for x in sp.obs["alive"] if sp.stacks[x] + sp.bets[x] > 0]
        k = len(alive)
        if k > 5 or k < 3 or sp.callers:
            if P["icmx"] and k >= 3:
                e = min(sp.stack + sp.bet, sp.stacks[v] + sp.bets[v])
                b = self.bfac(sp, e)
                return b * chip_need / (b * chip_need + 1.0 - chip_need)
            return chip_need
        me = sp.me
        my_tot = sp.stack + sp.bet
        v_tot = sp.stacks[v] + sp.bets[v]
        e = min(my_tot, v_tot)
        dead = sp.pot - sp.bet - sp.bets[v]
        base = [sp.stacks[x] + sp.bets[x] for x in alive]
        im, iv = alive.index(me), alive.index(v)
        pay = self.points[:k] + [0] * 8
        fold = list(base)
        fold[im] = sp.stack
        fold[iv] = v_tot + sp.bet + dead
        win = list(base)
        win[im] = my_tot + e + dead
        win[iv] = v_tot - e
        lose = list(base)
        lose[im] = my_tot - e
        lose[iv] = v_tot + e + dead
        u_fold = icm_me([x for x in fold], im, pay)
        u_win = icm_me([x for x in win if x > 0] if win[iv] > 0 else [x for x in win if x > 0], 
                       sum(1 for j in range(im) if win[j] > 0), pay)
        if lose[im] <= 0:
            u_lose = pay[k - 1]
        else:
            u_lose = icm_me(lose, im, pay)
        if win[iv] <= 0:
            # villain busts: I hold places among k-1 players; payouts shift up a place
            u_win = icm_me([x for x in win if x > 0], sum(1 for j in range(im) if win[j] > 0), self.points[:k - 1] + [0] * 8)
        d = u_win - u_lose
        if d <= 0:
            return chip_need
        return (u_fold - u_lose) / d

    def raise_w(self, seat, w):
        """Blend a prior raising/shoving width with the seat's observed preflop raise rate."""
        st = self.stats.get(seat)
        if not st or not P["model"]:
            return w
        n = st[0]
        obs = st[2] / n if n else 0.0
        obs = 0.03 if obs < 0.03 else 0.9 if obs > 0.9 else obs * 1.1
        return (w * 15 + obs * n) / (15 + n)

    def call_w(self, seat, w):
        st = self.stats.get(seat)
        if not st or not P["model"]:
            return w
        n = st[0]
        f = (st[1] / n) / 0.25 if n else 1.0
        f = 0.6 if f < 0.6 else 2.0 if f > 2.0 else f
        w2 = w * (15 + f * n) / (15 + n)
        return 0.9 if w2 > 0.9 else w2

    def decide(self, obs):
        if obs["phase"] == "discard":
            return safe_default(obs)
        if obs["hand_id"] != self.hand:
            self.hand = obs["hand_id"]
            self.pf_aggr = False
        sp = Spot(obs, self.var)
        if sp.street == 0:
            a = self.preflop(sp)
            if a.get("action") == "raise":
                self.pf_aggr = True
            return a
        return self.postflop(sp)

    # ---------------- preflop ----------------
    def shove_ev(self, sp, c, raiser_w=0.0):
        """Chip EV (vs folding now) of going all-in, assuming at most one caller."""
        bb = sp.bb
        me_tot = sp.stack + sp.bet
        dead = sp.pot
        ev = 0.0
        p_none = 1.0
        n_live = len(sp.opps)
        pm = 1.0 + P["posw"] * max(0, 4 - len(sp.behind))
        for s in sp.opps:
            o_tot = sp.stacks[s] + sp.bets[s]
            e = min(me_tot, o_tot)
            if sp.stacks[s] == 0:
                cw = 1.0
                pc = 1.0
            elif s == sp.raiser and raiser_w > 0:
                # raiser continues with the top part of its opening range
                cw = min(raiser_w, max(0.04, call_width(e / bb, n_live == 1) * (1.0 + sp.bets[s] / max(1, o_tot) * 3)))
                pc = cw / raiser_w
            else:
                cw = self.call_w(s, call_width(e / bb, n_live == 1) * pm)
                if P["ftoshove"]:
                    fo = self.fto.get(s)
                    if fo and fo[1] >= 5:
                        k = (1.0 - (fo[0] + 2.1) / (fo[1] + 3.0)) / 0.3
                        cw *= 0.6 if k < 0.6 else 1.5 if k > 1.5 else k
                if cw > 0.9:
                    cw = 0.9
                pc = cw
            if pc > 1.0:
                pc = 1.0
            my_add = e - sp.bet if e > sp.bet else 0
            final = dead + my_add + (e - sp.bets[s] if e > sp.bets[s] else 0)
            q = eq_vs(c, cw)
            ev += p_none * pc * (q * (final - my_add) - (1.0 - q) * my_add * self.bfac(sp, e))
            p_none *= 1.0 - pc
        ev += p_none * dead
        return ev

    def preflop(self, sp):
        pre = self.var.pre
        c = pre.best_cls(sp.hole)
        pct = pre.pct[c]
        bb = sp.bb
        stack_tot = sp.stack + sp.bet
        eff = sp.eff_bb
        to_call = sp.to_call
        if sp.raises == 0:
            if eff <= 14 and P["evpush"]:
                if self.shove_ev(sp, c) > 0.15 * bb:
                    return act_allin(sp)
                return act_fold(sp)
        elif sp.raiser >= 0:
            r = sp.raiser
            r_tot = sp.stacks[r] + sp.bets[r]
            if sp.raises == 1 and (sp.stacks[r] == 0 or to_call >= 0.3 * stack_tot or sp.bets[r] >= 0.4 * r_tot):
                # facing a shove (or a commit-size raise): call by equity vs shoving range
                e_bb = min(r_tot, stack_tot) / bb
                late = sp.position_of(r) <= 2
                w = shove_width(e_bb, late)
                if not (P["deep"] and e_bb > P["blend_bb"]):
                    w = self.raise_w(r, w)
                need = self.need_icm(sp, r, to_call / (sp.pot + to_call))
                margin = 0.02 + 0.03 * len(sp.behind)
                if P["deep"] and e_bb > 30:
                    margin += P["deep"]
                eq = eq_vs(c, w * (0.7 if sp.callers else 1.0))
                if sp.callers:
                    eq = eq ** (1 + 0.8 * sp.callers)
                if eq >= need + margin:
                    return act_allin(sp)
                return act_fold(sp)
            if sp.raises >= 2 and (sp.stacks[r] == 0 or to_call >= 0.3 * stack_tot) and P["shove3"]:
                # facing a re-shove / big 3-bet: call by equity vs a tighter shoving range
                e_bb = min(r_tot, stack_tot) / bb
                late = sp.position_of(r) <= 2
                w = shove_width(e_bb, late) * 0.6
                if P["m3"]:
                    if sp.raises >= 3:
                        w *= 0.7
                elif not (P["deep"] and e_bb > 30):
                    w = self.raise_w(r, w)
                need = self.need_icm(sp, r, to_call / (sp.pot + to_call))
                margin = 0.03 + 0.03 * len(sp.behind)
                if P["deep"] and e_bb > 30:
                    margin += P["deep"]
                eq = eq_vs(c, w)
                if P["m3"]:
                    multi = sum(1 for x in sp.opps if x != r and sp.bets[x] > bb)
                    if multi:
                        eq = eq ** (1 + 0.8 * multi)
                elif sp.callers:
                    eq = eq ** (1 + 0.8 * sp.callers)
                if eq >= need + margin:
                    return act_allin(sp)
                return act_fold(sp)
            if sp.raises == 1 and eff <= 28:
                # re-shove over a normal open
                late = sp.position_of(r) <= 2
                open_w = self.raise_w(r, 0.30 if late else 0.18)
                if self.shove_ev(sp, c, open_w) > 0.5 * bb and pct <= 0.30:
                    return act_allin(sp)
        return self.preflop_v1(sp, pct)

    def preflop_v1(self, sp, pct):
        pre = self.var.pre
        bb = sp.bb
        stack_tot = sp.stack + sp.bet
        eff = sp.eff_bb
        behind = len(sp.behind)
        to_call = sp.to_call
        if sp.raises == 0:
            if eff <= 13:
                thr = PUSH.get(behind, 0.17) * min(2.0, max(0.7, 10.0 / max(eff, 1.0)))
                if pct <= thr:
                    return act_allin(sp)
                return act_fold(sp)
            thr = OPEN.get(behind, 0.12) * P["open_mult"]
            if sp.callers:
                thr = min(thr * 0.6, 0.15)
            elif P["steal"] and behind <= (5 if P["steal"] == 3 else 4 if P["steal"] == 2 else 3):
                pf = 1.0
                for x in sp.behind:
                    fo = self.fto.get(x)
                    pf *= (fo[0] + 2.1) / (fo[1] + 3.0) if fo else 0.7
                if P["steal"] == 3:
                    if pf > 0.65:
                        thr = max(thr, 1.0)
                    elif pf > 0.55:
                        thr = max(thr, 0.7)
                    elif pf > 0.45:
                        thr = max(thr, 0.5)
                elif P["steal"] == 2:
                    if pf > 0.72:
                        thr = max(thr, 1.0)
                    elif pf > 0.6:
                        thr = max(thr, 0.7)
                    elif pf > 0.5:
                        thr = max(thr, 0.5)
                elif pf > 0.75:
                    thr = max(thr, 0.85)
                elif pf > 0.6:
                    thr = max(thr, 0.6)
            if pct <= thr:
                target = (2.5 + sp.callers) * bb
                if target >= 0.4 * stack_tot:
                    return act_allin(sp)
                return act_raise(sp, target)
            if sp.can_check:
                return act_fold(sp)
            # SB completing vs BB alone, cheap: fold (keep it tight)
            return act_fold(sp)
        # facing a raise
        raiser = sp.raiser
        r_total = sp.stacks[raiser] + sp.bets[raiser] if raiser >= 0 else stack_tot
        r_bb = r_total / bb
        need = to_call / (sp.pot + to_call)
        committed = to_call >= 0.35 * stack_tot or sp.stacks[raiser] == 0 if raiser >= 0 else False
        if sp.raises >= 2:
            # facing a 3-bet or more
            if pct <= 0.012:
                return act_allin(sp)
            if pct <= 0.035 and (committed or r_bb <= 40):
                return act_allin(sp)
            if pct <= 0.02:
                return act_call(sp)
            return act_fold(sp)
        if committed or (to_call >= 0.2 * stack_tot):
            # treat as a shove: call with a range depending on raiser depth
            eff_r = min(r_bb, stack_tot / bb)
            if eff_r > 25:
                thr = 0.05
            elif eff_r > 15:
                thr = 0.09
            elif eff_r > 9:
                thr = 0.15
            elif eff_r > 5:
                thr = 0.25
            else:
                thr = 0.40
            if need < 0.35:
                thr *= 1.4
            if pct <= thr:
                return act_allin(sp)
            return act_fold(sp)
        # single normal raise
        if pct <= 0.035:
            target = 3 * (sp.bet + to_call) + sp.callers * (sp.bet + to_call)
            if target >= 0.35 * stack_tot:
                return act_allin(sp)
            return act_raise(sp, target)
        if eff <= 15:
            # short: reshove good hands
            if pct <= 0.10:
                return act_allin(sp)
            return act_fold(sp)
        bbdef = P["hu_def"] if sp.n_alive == 2 else 0.30
        cheap = 0.16
        if P["sdef"] and sp.raiser >= 0 and sp.callers == 0:
            st = self.stats.get(sp.raiser)
            if st and st[0] >= 15 and st[2] > 0.3 * st[0]:
                bbdef = max(bbdef, 0.5)
                cheap = 0.28
        if pct <= 0.09 or (pct <= cheap and to_call <= 2.5 * bb) or (sp.role == "BB" and pct <= bbdef and to_call <= 1.5 * bb):
            return act_call(sp)
        return act_fold(sp)

    # ---------------- postflop ----------------
    def postflop(self, sp):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        pot = sp.pot
        to_call = sp.to_call
        stack = sp.stack
        last = sp.last_street
        n_opp = sp.n_opp
        # multiway: demand more
        adj = 0.04 * max(0, n_opp - 1)
        if to_call == 0:
            if s >= 0.85:
                return self.bet(sp, P["big_frac"])
            if s >= P["vbet"] + adj:
                return self.bet(sp, P["bet_frac"])
            if not last and outs >= 8 and self.rng.random() < 0.5:
                return self.bet(sp, 0.55)
            if P["ftb"] and n_opp == 1 and (self.pf_aggr or sp.street >= 2):
                ft = self.ftb.get(sp.opps[0])
                if ft and ft[1] >= 4:
                    ff = (ft[0] + 1.0) / (ft[1] + 2.5)
                    if (sp.street == 1 and ff >= 0.42) or (not last and ff >= 0.6 and s >= 0.2):
                        return self.bet(sp, 0.5)
                    if sp.street == 1 and ff < 0.3:
                        return act_fold(sp)
            if self.pf_aggr and sp.street == 1 and n_opp == 1 and self.rng.random() < P["cbet"]:
                return self.bet(sp, 0.5)
            return act_fold(sp)
        need = to_call / (pot + to_call)
        if P["icmpost"] and to_call >= 0.35 * (stack + sp.bet):
            b = self.bfac(sp, min(stack + sp.bet, to_call + sp.bet))
            need = b * need / (b * need + 1.0 - need)
        spr_after = (stack - to_call) / max(1, pot + to_call)
        if P["stackoff"] and s < 0.85 and to_call >= 0.35 * (stack + sp.bet) and sp.eff_bb > 25:
            s -= P["stackoff"]
        if s >= 0.85:
            return self.bet(sp, 0.9) if sp.can_raise else act_call(sp)
        me = sp.me
        st = sp.street
        if any(h[0] == st and h[1] == me and h[2] == "raise" for h in sp.hist):
            s -= P["raise_pen"]
        if P["aggmod"] and sp.raiser >= 0:
            ps = self.post.get(sp.raiser)
            if ps:
                f = (ps[0] + 0.9) / (ps[0] + ps[1] + 3.0)
                d = P["aggmod"] * (f - 0.33)
                s += -0.12 if d < -0.12 else 0.12 if d > 0.12 else d
        s -= P["call_tight"]
        if s >= 0.70 + adj:
            if need <= 0.45 or spr_after < 0.5:
                return act_call(sp)
            return act_fold(sp)
        if s >= 0.58 + adj:
            if need <= 0.36 or spr_after < 0.3:
                return act_call(sp)
            return act_fold(sp)
        if s >= 0.44 + adj:
            if need <= 0.25:
                return act_call(sp)
            return act_fold(sp)
        if not last and outs >= 8:
            eq = outs * (0.035 if sp.street == 1 else 0.02)
            if need <= eq:
                return act_call(sp)
        return act_fold(sp)

    def bet(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            target = sp.max_to
        return act_raise(sp, target)
