import random

from . import ev
from .ev import CARD, PCT, cls_of

# open-raise ranges (pct of hands, by percentile vs random) by number of players behind
OPEN = {1: 0.42, 2: 0.40, 3: 0.28, 4: 0.21, 5: 0.17, 6: 0.14, 7: 0.12}
# push ranges at 10bb by players behind (Nash-like)
PUSH10 = {1: 0.62, 2: 0.38, 3: 0.28, 4: 0.22, 5: 0.18, 6: 0.155, 7: 0.135}
PUSH_BB = 13.0
GAM0 = 0.5
GAM1 = 0.7
EQDISC = 0.02
RAISE_X = 1.0
RIVER_X = 0.3
ICM_FRAC = 0.15


def _fold(obs):
    return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        # per-seat stats: [hands, vpip, pfr, preflop allins]
        self.st = {}
        try:
            h = [CARD["As"], CARD["Kd"]]
            b = [CARD["7h"], CARD["8h"], CARD["9c"]]
            for k in (1, 2, 3):
                ev.equity(h, b, k, [(0.2, 0.15)] * k)
            ev.equity(h, b + [CARD["2c"]], 1, [(0.2, 0.15)])
            ev.equity(h, b + [CARD["2c"], CARD["3d"]], 1, [(0.2, 0.15)])
            ev.range_equity(cls_of(h[0], h[1]), 0.2)
        except Exception:
            pass

    # ------------------------------------------------------------------ utils
    def _raise(self, obs, amt):
        if obs["max_raise_to"] <= 0 or not ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return {"action": "call"} if "call" in obs["legal"] else _fold(obs)
        a = int(amt)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        # if raise leaves little behind, shove
        me = obs["seat"]
        tot = obs["stacks"][me] + obs["bets"][me]
        if a > 0.6 * tot:
            a = hi
        return {"action": "raise", "amount": a}

    def _call(self, obs):
        if obs["to_call"] == 0:
            return {"action": "check"}
        return {"action": "call"}

    def _allin(self, obs):
        return {"action": "allin"}

    def act(self, obs):
        try:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
            if obs["street_index"] == 0:
                return self.preflop(obs)
            return self.postflop(obs)
        except Exception:
            return _fold(obs)

    # --------------------------------------------------------------- modeling
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            ai = set()
            for h in hist:
                st, seat, act, amt = h[0], h[1], h[2], h[3]
                if st != 0:
                    continue
                seen.add(seat)
                if act == "call":
                    vp.add(seat)
                elif act == "raise":
                    vp.add(seat)
                    pr.add(seat)
            for s in seen:
                r = self.st.get(s)
                if r is None:
                    r = self.st[s] = [0, 0, 0, 0]
                r[0] += 1
                if s in vp:
                    r[1] += 1
                if s in pr:
                    r[2] += 1
        except Exception:
            pass

    def pfr_of(self, seat, prior=0.15, w=8.0):
        r = self.st.get(seat)
        if not r:
            return prior
        return (r[2] + prior * w) / (r[0] + w)

    def vpip_of(self, seat, prior=0.3, w=8.0):
        r = self.st.get(seat)
        if not r:
            return prior
        return (r[1] + prior * w) / (r[0] + w)

    def icm_push(self, obs, c, behind, mytot):
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        bb = obs["bb"] or 1
        me = obs["seat"]
        T = sum(stacks) + pot
        n = len(obs["alive"])
        v_fold = ev.icmv(n, stacks[me], T)
        pf = 1.0
        tot_called = 0.0
        sw = 0.0
        for s in behind:
            tot = stacks[s] + bets[s]
            matched = min(mytot, tot)
            rbb = matched / bb
            ci = 0.10 + 0.9 / max(rbb, 1.0)
            if s == obs["bb_seat"]:
                ci += 0.08
            elif s == obs["sb_seat"]:
                ci += 0.03
            ci *= (0.7 + self.vpip_of(s))
            ci = min(0.7, max(0.05, ci))
            pf *= (1 - ci)
            eq = ev.range_equity(c, ci)
            if eq is None:
                eq = 0.5
            dead = pot - bets[me] - bets[s]
            win_st = mytot + matched + dead
            lose_st = mytot - matched
            n_win = n - 1 if tot <= mytot else n
            v = eq * ev.icmv(n_win, win_st, T) + (1 - eq) * ev.icmv(n, lose_st, T)
            tot_called += ci * v
            sw += ci
        v_steal = ev.icmv(n, stacks[me] + pot, T)
        if sw <= 0:
            return True
        v_shove = pf * v_steal + (1 - pf) * tot_called / sw
        return v_shove > v_fold

    # ---------------------------------------------------------------- preflop
    def preflop(self, obs):
        me = obs["seat"]
        h = [CARD[c] for c in obs["hole"]]
        c = cls_of(h[0], h[1])
        pct = PCT[c]
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        mytot = stacks[me] + bets[me]
        others = [s for s in in_hand if s != me]
        opp_max = max([stacks[s] + bets[s] for s in others], default=0)
        eff = min(mytot, opp_max)
        eff_bb = eff / bb
        to_call = obs["to_call"]
        pot = obs["pot"]

        # order and players behind
        n = len(alive)
        btn = obs["button"]
        if n == 2:
            bi = alive.index(btn) if btn in alive else 0
            order = [alive[bi], alive[1 - bi]]
        else:
            bbs = obs["bb_seat"]
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        nb = len(behind)

        raises = 0
        limpers = 0
        raiser = -1
        allin_raisers = 0
        for hs, seat, act, amt in obs["history"]:
            if hs != 0:
                continue
            if act == "raise":
                raises += 1
                raiser = seat
                limpers = 0
                if stacks[seat] == 0:
                    allin_raisers += 1
            elif act == "call":
                if raises == 0:
                    limpers += 1
        callers = 0
        if raises:
            seen_r = False
            for hs, seat, act, amt in obs["history"]:
                if hs != 0:
                    continue
                if act == "raise":
                    seen_r = True
                    callers = 0
                elif act == "call" and seen_r:
                    callers += 1

        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])

        # ---------- unopened
        if raises == 0:
            if to_call == 0:
                # BB option
                if pct <= 0.10 and can_raise:
                    if eff_bb <= PUSH_BB:
                        return self._allin(obs)
                    return self._raise(obs, bb * (3.5 + limpers))
                return {"action": "check"}
            nbx = max(1, min(7, nb + limpers))
            if eff_bb <= PUSH_BB:
                p = PUSH10.get(nbx, 0.13) * (10.0 / max(eff_bb, 1.0)) ** 0.8
                if limpers:
                    p *= 0.7
                if pct <= p * 1.6 and self.icm_push(obs, c, [s for s in others if stacks[s] > 0], mytot):
                    return self._allin(obs)
                return _fold(obs)
            p = OPEN.get(max(1, min(7, nb)), 0.12) * (1.25 if nb <= 3 else 1.0)
            if behind:
                av = sum(self.vpip_of(s) for s in behind) / len(behind)
                p *= min(1.4, max(0.8, 0.3 / max(av, 0.05)))
            if limpers:
                p = min(p, 0.12)
            if eff_bb < 25:
                p *= 0.9
            if pct <= p:
                size = (2.5 if eff_bb >= 30 else 2.2) + limpers
                return self._raise(obs, bb * size)
            return _fold(obs)

        # ---------- facing raise(s)
        cur = max(bets)
        if (raiser >= 0 and stacks[raiser] == 0 and raises == allin_raisers
                and to_call <= 0.25 * mytot and stacks[me] > to_call):
            # small all-in(s): call by pot odds / ICM
            fr = -1
            for hs, seat, act, amt in obs["history"]:
                if hs == 0 and act == "raise":
                    fr = seat
                    break
            rnb = len(order) - 1 - order.index(fr) if fr in order else 3
            rnb = max(1, min(7, rnb))
            rbb = (stacks[raiser] + bets[raiser]) / bb
            est = max(0.08, min(0.8, PUSH10.get(rnb, 0.13) * (10.0 / max(rbb, 1.0)) ** 0.8))
            est = 0.65 * est + 0.35 * max(self.pfr_of(raiser), 0.03)
            eq = ev.range_equity(c, est)
            if eq is None:
                eq = 1.0 - pct
            ncall = sum(1 for hs, seat, act, amt in obs["history"]
                        if hs == 0 and act == "call" and seat != me and seat in in_hand)
            if ncall:
                eq = eq ** (1 + 0.7 * ncall)
            eq -= 0.03 * nb
            T = sum(stacks) + pot
            n = len(alive)
            v_call = eq * ev.icmv(n, stacks[me] + pot, T) + (1 - eq) * ev.icmv(n, stacks[me] - to_call, T)
            if v_call > ev.icmv(n, stacks[me], T) + 0.02:
                return self._call(obs)
            return _fold(obs)
        committed = to_call >= 0.33 * mytot or eff_bb <= 16 or cur >= 0.33 * eff
        if committed:
            # estimate opponent range
            rs = stacks[raiser] + bets[raiser] if raiser >= 0 else eff
            rbb = min(rs, mytot) / bb
            # first raiser's position: players behind them when they acted
            fr = -1
            for hs, seat, act, amt in obs["history"]:
                if hs == 0 and act == "raise":
                    fr = seat
                    break
            if fr in order:
                rnb = len(order) - 1 - order.index(fr)
            else:
                rnb = 3
            rnb = max(1, min(7, rnb))
            if allin_raisers or cur >= 0.5 * (stacks[raiser] + bets[raiser]):
                chart = PUSH10.get(rnb, 0.13) * (10.0 / max(rbb, 1.0)) ** 0.8
                est = max(0.06, min(0.75, chart))
            else:
                est = max(0.04, min(0.5, OPEN.get(rnb, 0.12) * 0.8))
            obsd = self.pfr_of(raiser)
            est = 0.65 * est + 0.35 * max(obsd, 0.03)
            if raises >= 2:
                est *= 0.5
            eq = ev.range_equity(c, est)
            if eq is None:
                eq = 1.0 - pct
            act_opps = set()
            for hs, seat, act, amt in obs["history"]:
                if hs == 0 and seat != me and (act == "raise" or act == "call") and seat in in_hand:
                    act_opps.add(seat)
            k = max(1, len(act_opps))
            if k > 1:
                eq = eq ** (1 + 0.7 * (k - 1))
            if nb:
                eq -= 0.02 * nb
            T = sum(stacks) + pot
            n = len(alive)
            opp_tot = max(stacks[s] + bets[s] for s in others) if others else mytot
            my_in = min(mytot, opp_tot)
            r_tot = stacks[raiser] + bets[raiser] if raiser >= 0 else opp_tot
            r_add = max(0, min(r_tot, my_in) - (bets[raiser] if raiser >= 0 else 0))
            excess = sum(max(0, bets[s] - my_in) for s in others)
            win_st = mytot + (pot - bets[me]) + r_add - excess
            lose_st = mytot - my_in
            n_win = n - 1 if r_tot <= my_in else n
            v_call = eq * ev.icmv(n_win, win_st, T) + (1 - eq) * ev.icmv(n, lose_st, T)
            v_fold = ev.icmv(n, stacks[me], T)
            pf = 0.0
            if can_raise and raiser >= 0 and stacks[raiser] > 0 and bets[raiser] < 0.4 * r_tot and nb == 0:
                pf = 0.25
            v_shove = pf * ev.icmv(n, stacks[me] + pot, T) + (1 - pf) * v_call
            if v_shove > v_fold + 0.05:
                return self._allin(obs)
            return _fold(obs)

        if raises == 1:
            if (pct <= 0.012 or c == 155 or c == 167) and can_raise:
                return self._raise(obs, cur * 3.2 + callers * cur)
            pos_ok = nb == 0 or me == obs["bb_seat"] or len(behind) <= 1
            callp = 0.09
            if me == obs["bb_seat"] and to_call <= 2.5 * bb:
                callp = 0.22
            elif pos_ok:
                callp = 0.12
            if pct <= callp and to_call <= 0.12 * mytot:
                return self._call(obs)
            # set mining
            if (c // 13) == (c % 13) and to_call <= 0.07 * eff:
                return self._call(obs)
            return _fold(obs)

        # facing 3-bet or more
        if pct <= 0.007 and can_raise:
            return self._allin(obs)
        if (pct <= 0.016 or c == 155 or c == 167) and to_call <= 0.2 * mytot:
            return self._call(obs)
        return _fold(obs)

    # --------------------------------------------------------------- postflop
    def postflop(self, obs):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        in_hand = obs["in_hand"]
        others = [s for s in in_hand if s != me]
        n_opp = len(others)
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        st = obs["street_index"]
        mystack = stacks[me]

        # preflop roles
        pf_raiser = -1
        role = {}
        raised_seen = False
        for hs, seat, act, amt in obs["history"]:
            if hs == 0:
                if act == "raise":
                    pf_raiser = seat
                    role[seat] = "r"
                    raised_seen = True
                elif act == "call":
                    if seat not in role:
                        role[seat] = "c" if raised_seen else "l"
        ranges = []
        for s in others:
            r = role.get(s)
            if r == "r":
                ranges.append((min(0.5, max(0.08, self.pfr_of(s) * 1.3)), 0.15))
            elif r == "c":
                ranges.append((min(0.7, max(0.2, self.vpip_of(s) * 1.2)), 0.25))
            elif r == "l":
                ranges.append((0.7, 0.4))
            else:
                ranges.append((1.0, 1.0))
        # aggression on this street
        st_raises = 0
        aggr = {}
        me_bet = False
        for hs, seat, act, amt in obs["history"]:
            if hs == st and act == "raise" and seat == me:
                me_bet = True
            if hs >= 1 and act == "raise" and seat != me:
                if hs == st:
                    st_raises += 1
                    aggr[seat] = aggr.get(seat, 0.0) + 1.0
                    if me_bet:
                        aggr[seat] += RAISE_X
                    elif st == 3:
                        aggr[seat] += RIVER_X
                else:
                    aggr[seat] = aggr.get(seat, 0.0) + 0.3
        gam = None
        if aggr:
            ratio0 = to_call / max(1, pot - to_call)
            gam = []
            for s in others:
                a = aggr.get(s, 0.0)
                if a <= 0:
                    gam.append(0.0)
                elif a >= 1.0:
                    gam.append(GAM0 + GAM1 * min(ratio0, 1.5) + 0.6 * (a - 1.0) if a < 1.5
                               else GAM0 + GAM1 * min(ratio0, 1.5) + (a - 1.0))
                else:
                    gam.append(a)
            if len(gam) > 3:
                gi = sorted(range(len(gam)), key=lambda k: -gam[k])[:3]
                ranges = [ranges[k] for k in gi]
                gam = [gam[k] for k in gi]
        eq = ev.equity(hole, board, n_opp, ranges, gam)

        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        if to_call == 0:
            thr = 0.60 if n_opp == 1 else 0.68 + 0.04 * (n_opp - 2)
            if eq >= thr and can_raise:
                frac = 0.75 if st == 3 else 0.6
                return self._raise(obs, frac * pot)
            # c-bet as preflop raiser heads-up on flop
            bf = 1.0
            if n_opp == 1:
                bf = min(1.2, max(0.3, (1.0 - self.vpip_of(others[0])) / 0.7))
            if (pf_raiser == me and n_opp == 1 and st == 1 and can_raise
                    and self.rng.random() < 0.55 * bf):
                return self._raise(obs, 0.5 * pot)
            # semi-bluff / steal when checked to on turn heads-up with decent equity
            if n_opp == 1 and can_raise and eq >= 0.45 and self.rng.random() < 0.3 * bf:
                return self._raise(obs, 0.5 * pot)
            return {"action": "check"}

        prev_pot = max(1, pot - to_call)
        ratio = to_call / prev_pot
        eq_adj = eq - EQDISC
        need = to_call / (pot + to_call)
        if to_call >= ICM_FRAC * mystack:
            T = sum(stacks) + pot
            n = len(obs["alive"])
            add = min(to_call, mystack)
            excess = to_call - add
            v_call = eq_adj * ev.icmv(n, mystack + pot - excess, T) + (1 - eq_adj) * ev.icmv(n, mystack - add, T)
            if v_call > ev.icmv(n, mystack, T) + 0.05:
                if eq_adj >= 0.78 and can_raise:
                    return self._allin(obs)
                return self._call(obs)
            return _fold(obs)
        if eq_adj >= 0.78 and can_raise:
            return self._raise(obs, obs["bets"][me] + to_call + 0.9 * (pot + to_call))
        if eq_adj >= need + 0.04:
            return self._call(obs)
        return _fold(obs)
