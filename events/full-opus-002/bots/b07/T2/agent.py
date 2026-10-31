"""b07 bot: precomputed preflop equities, EV-based push/fold with ICM risk
premium, position-aware opening, heuristic postflop strength, and per-seat
opponent reads (VPIP/PFR/aggression/fold-to-raise) that pick steal and call spots."""

import json
import os
import random

from ._common import (CARD, HIGH, PAIR, PREFLOP, SafeAgent, Spot, Variant, act_allin, act_call, act_fold,
                      act_raise, features, safe_default)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_eq():
    try:
        with open(os.path.join(_HERE, "pfeq.json")) as f:
            m = json.load(f)
        if len(m) == 169:
            return m
    except Exception:
        pass
    return None


_PRE = PREFLOP["std"]
_PCT = _PRE.pct
_M = _load_eq()


def _ncombos(c):
    a, b = divmod(c, 13)
    return 6 if a == b else 4 if a > b else 12


# Classes ordered best first (by equity vs a random hand).
_ORDER = sorted(range(169), key=lambda c: _PCT[c])
_NC = [_ncombos(c) for c in range(169)]


def _build_range_eq():
    """RE[c][k]: equity of class c vs the top k% of hands (k = 1..100), all-in preflop."""
    cum = []
    tot = 0
    for c in _ORDER:
        tot += _NC[c]
        cum.append(tot)
    # index in _ORDER at which the top k% ends
    cut = []
    j = 0
    for k in range(101):
        target = max(1, k) / 100.0 * tot
        while j < 168 and cum[j] < target:
            j += 1
        cut.append(j)
    re = []
    for c in range(169):
        row_m = _M[c] if _M is not None else None
        acc = 0.0
        w = 0
        run = []
        for idx, o in enumerate(_ORDER):
            n = _NC[o]
            if row_m is not None:
                acc += row_m[o] * n
            else:
                acc += (1.0 - _PCT[c] * 0.5 + _PCT[o] * 0.5 - 0.5) * n
            w += n
            run.append(acc / w)
        re.append([run[cut[k]] for k in range(101)])
    return re


_RE = _build_range_eq()


P = {"deep": 1.0, "steal": 1.0, "icm": 0.5, "lam": 0.025, "pf_bb": 14, "open": 1.0, "call_m": 0.08, "pen": 1.0, "cbet": 0.75, "callq": 1.0, "resteal_bb": 22, "rs_margin": 0.3}
RESTEAL_BB = P["resteal_bb"]
CALL_SHARE = 0.4
RESTEAL_MARGIN = P["rs_margin"]
LAM_PER = P["lam"]
_LAM_FULL = (0.0, 0.0, 0.0, 0.33, 0.53, 0.6, 0.6, 0.6, 0.62)


def icm_small(stacks, pays):
    """Malmuth-Harville ICM for a few players (dict seat -> chips). Zero stacks share the last places."""
    live = [k for k, v in stacks.items() if v > 0]
    zero = [k for k, v in stacks.items() if v <= 0]
    res = dict.fromkeys(stacks, 0.0)
    nl = len(live)
    if zero:
        share = sum(pays[nl:nl + len(zero)]) / len(zero)
        for k in zero:
            res[k] = share

    def rec(players, place, prob, tot):
        pay = pays[place]
        last = len(players) == 1
        for i in players:
            si = stacks[i]
            pr = prob * si / tot
            res[i] += pr * pay
            if not last:
                rec([j for j in players if j != i], place + 1, pr, tot - si)

    if live:
        rec(live, 0, 1.0, float(sum(stacks[k] for k in live)))
    return res


def extra_callers(sp):
    return sp.callers > 0


def range_eq(c, frac):
    k = int(frac * 100 + 0.5)
    if k < 1:
        k = 1
    elif k > 100:
        k = 100
    return _RE[c][k]


class SeatStats:
    __slots__ = ("hands", "vpip", "pfr", "allin", "faced_raise", "fold_to_raise", "post_bets",
                 "post_calls", "post_checks", "post_folds", "faced_allin", "called_allin")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.allin = 0
        self.faced_raise = 0
        self.fold_to_raise = 0
        self.post_bets = 0
        self.post_calls = 0
        self.post_checks = 0
        self.post_folds = 0
        self.faced_allin = 0
        self.called_allin = 0

    def vpip_rate(self):
        return (self.vpip + 0.25 * 4) / (self.hands + 4)

    def pfr_rate(self):
        return (self.pfr + 0.15 * 5) / (self.hands + 5)

    def fold_raise_rate(self):
        return (self.fold_to_raise + 0.6 * 4) / (self.faced_raise + 4)

    def aggr(self):
        # share of postflop actions that are bets/raises
        return (self.post_bets + 1.0) / (self.post_bets + self.post_calls + self.post_checks + 3.0)

    def ftb(self):
        # fold-to-bet postflop: folds vs calls/raises when facing action
        return (self.post_folds + 0.45 * 4) / (self.post_folds + self.post_calls + 4)

    def call_allin_rate(self):
        return (self.called_allin + 0.25 * 3) / (self.faced_allin + 3)


class Agent(SafeAgent):
    def __init__(self, config):
        super().__init__(config)
        self.seat = config.get("seat", 0)
        self.rng = random.Random(config.get("seed", 0))
        self.stats = {}
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        self.start_stacks = None
        self.start_default = config.get("starting_stack", 2000)
        self.pf_aggr = False

    # ---------------------------------------------------------------- reads
    def st(self, seat):
        s = self.stats.get(seat)
        if s is None:
            s = self.stats[seat] = SeatStats()
        return s

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            self.pf_aggr = False
            hist = event.get("history") or []
            start = self.start_stacks
            try:
                fin = event.get("stacks")
                if isinstance(fin, dict):
                    self.start_stacks = {int(k): v for k, v in fin.items()}
                elif fin is not None:
                    self.start_stacks = {i: v for i, v in enumerate(fin)}
            except Exception:
                self.start_stacks = None
            if start is None and event.get("hand_id", 99) in (0, 1):
                start = {}
            if start is not None:
                # who called / folded facing a preflop all-in
                shover = -1
                responded = set()
                for h in hist:
                    if h[0] != 0:
                        break
                    seat, act, amt = h[1], h[2], h[3]
                    if act == "raise" and shover < 0:
                        st0 = start.get(seat, self.start_default)
                        if st0 and amt >= st0:
                            shover = seat
                            if seat != self.seat:
                                self.st(seat).allin += 1
                            continue
                    if shover >= 0 and seat != shover and seat != self.seat and seat not in responded:
                        if act in ("fold", "call", "raise"):
                            responded.add(seat)
                            so = self.st(seat)
                            so.faced_allin += 1
                            if act != "fold":
                                so.called_allin += 1
            seen = set()
            vp = set()
            pr = set()
            raised = False
            raise_seen_by = {}
            stacks_start = {}
            for h in hist:
                stn, seat, act, amt = h[0], h[1], h[2], h[3]
                if stn == 0:
                    if act in ("sb", "bb", "ante"):
                        continue
                    seen.add(seat)
                    if raised and seat not in raise_seen_by and seat != self.seat:
                        raise_seen_by[seat] = act
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                        raised = True
                else:
                    if seat == self.seat:
                        continue
                    s = self.st(seat)
                    if act == "raise":
                        s.post_bets += 1
                    elif act == "call":
                        s.post_calls += 1
                    elif act == "check":
                        s.post_checks += 1
                    elif act == "fold":
                        s.post_folds += 1
            for seat in seen:
                if seat == self.seat:
                    continue
                s = self.st(seat)
                s.hands += 1
                if seat in vp:
                    s.vpip += 1
                if seat in pr:
                    s.pfr += 1
            for seat, act in raise_seen_by.items():
                s = self.st(seat)
                s.faced_raise += 1
                if act == "fold":
                    s.fold_to_raise += 1
        except Exception:
            pass

    # ---------------------------------------------------------------- helpers
    def risk_lambda(self, sp):
        n = sp.n_alive
        if n <= 2:
            return 0.0
        lam = LAM_PER * (n - 2)
        # short stacks have less to protect
        if sp.stack + sp.bet < 6 * sp.bb:
            lam *= 0.5
        return lam

    def lam_risk(self, sp, risk):
        """ICM risk premium on chips lost: calibrated so an even-stack all-in for
        everything needs the exact-ICM break-even equity, scaled by the share of
        our stack at risk."""
        n = sp.n_alive
        if n <= 2 or P["icm"] <= 0:
            return 0.0
        full = _LAM_FULL[n] if n < len(_LAM_FULL) else 0.62
        my_total = sp.stack + sp.bet
        frac = risk / my_total if my_total > 0 else 1.0
        if frac > 1.0:
            frac = 1.0
        lam = full * frac * P["icm"]
        if my_total < 6 * sp.bb:
            lam *= 0.5
        return lam

    def opp_call_freq(self, seat, eff_bb):
        """Estimated chance a seat calls our all-in (fraction of hands)."""
        base = 0.10 + 0.9 / max(eff_bb, 1.5)
        if base > 0.45:
            base = 0.45
        s = self.stats.get(seat)
        if s is not None and s.hands >= 6:
            v = s.vpip_rate()
            # looser players call wider
            base *= 0.6 + 1.6 * v
        if s is not None and s.faced_raise >= 4 and P["steal"] > 0:
            # calling an all-in is at most as common as continuing vs a raise
            cap = (1.0 - s.fold_raise_rate()) * 1.1 + 0.02
            if base > cap:
                base = cap
        if s is not None and s.faced_allin >= 1:
            # direct read: how often this seat called preflop all-ins
            w = s.faced_allin / (s.faced_allin + 4.0)
            obs_rate = s.called_allin / s.faced_allin
            base = (1 - w) * base + w * obs_rate
        return min(0.7, max(0.04, base * P["callq"]))

    def opp_raise_range(self, seat, sp, allin, nraises):
        """Estimated range width (fraction of hands) of a raiser."""
        s = self.stats.get(seat)
        stack_bb = (sp.stacks[seat] + sp.bets[seat]) / sp.bb
        if allin and stack_bb > 25 and P["deep"] > 0:
            # deep shoves are premium-heavy unless this seat is seen shoving a lot
            base = 0.035 if stack_bb > 45 else 0.06
            if s is not None and s.hands >= 6:
                shove_rate = (s.allin + 0.2) / (s.hands + 6)
                base = max(base, min(0.6, shove_rate * 1.5))
            return base
        if allin:
            base = 0.12 if stack_bb > 25 else 0.18 if stack_bb > 15 else 0.28 if stack_bb > 8 else 0.40
        else:
            base = 0.16
        if nraises >= 2:
            base *= 0.4
        if s is not None and s.hands >= 5:
            r = s.pfr_rate()
            base = 0.5 * base + 0.5 * min(0.8, r * (1.3 if allin else 1.0))
            if nraises >= 2:
                base = min(base, 0.5 * r + 0.03)
        return max(0.025, min(0.85, base))

    # ---------------------------------------------------------------- decide
    def decide(self, obs):
        if obs["phase"] == "discard":
            return safe_default(obs)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            return self.preflop(sp, obs)
        return self.postflop(sp, obs)

    def preflop(self, sp, obs):
        h = sp.hole
        c = _PRE.cls(h[0], h[1])
        pct = _PCT[c]
        bb = sp.bb
        my_total = sp.stack + sp.bet
        lam = self.risk_lambda(sp)
        hist = sp.hist
        raises = sp.raises
        n_opp_in = sp.n_opp
        if raises == 0:
            self.pf_aggr = False
            behind = sp.behind
            limpers = sp.callers
            others = [sp.stacks[s] + sp.bets[s] for s in behind]
            eff = min(my_total, max(others)) if others else my_total
            eff_bb = eff / bb
            if not behind:
                # BB with limpers / everybody folded to us with no one behind
                if sp.can_check:
                    if pct < 0.10 and sp.can_raise:
                        return self.raise_to(sp, sp.to_call + sp.bet + (3 + limpers) * bb)
                    return {"action": "check"}
                return act_call(sp)
            if eff_bb <= P["pf_bb"] or my_total <= P["pf_bb"] * bb:
                callers = [o for o in sp.opps if sp.stacks[o] > 0]
                if 3 <= sp.n_alive <= 4 and P["icm"] > 0 and callers:
                    ev = self.shove_icm(sp, c, callers, obs)
                else:
                    ev = self.shove_ev(sp, c, callers, eff, lam)
                if ev > 0.0:
                    self.pf_aggr = True
                    return act_allin(sp)
                if sp.role == "SB" and limpers == 0 and len(behind) == 1 and pct < 0.55 and eff_bb > 8:
                    return act_call(sp)
                return act_fold(sp)
            # deeper: open raise
            nb = len(behind)
            thr = {1: 0.42, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14}.get(nb, 0.12)
            if sp.n_alive == 2:
                thr = 0.72
            elif sp.n_alive == 3:
                thr = 0.48 if nb == 2 else 0.52
            # adjust for how foldy the players behind are
            fr = 0.0
            for s in behind:
                st = self.stats.get(s)
                fr += st.fold_raise_rate() if st is not None and st.faced_raise >= 4 else 0.6
            fr /= nb
            thr *= (0.7 + 0.6 * fr) * P["open"]
            if limpers:
                thr *= 0.6
            steal = False
            if not limpers and pct > thr and P["steal"] > 0:
                # steal any two cards when the observed fold rates behind make it pay
                p_all = 1.0
                known = True
                for o in behind:
                    so = self.stats.get(o)
                    if so is None or so.faced_raise < 4:
                        known = False
                        break
                    p_all *= so.fold_raise_rate()
                if known:
                    add = (3.0 if sp.role == "SB" else 2.3) * bb - sp.bet
                    ev = p_all * sp.pot - (1 - p_all) * add * 0.55
                    steal = ev > 0.2 * bb and pct < 0.97
            if pct <= thr or steal:
                self.pf_aggr = True
                size = (2.3 if eff_bb < 25 else 2.6) * bb + limpers * bb
                if sp.role == "SB":
                    size = 3.0 * bb
                return self.raise_to(sp, size)
            if sp.role == "SB" and limpers >= 1 and pct < 0.45:
                return act_call(sp)
            if sp.can_check:
                return {"action": "check"}
            return act_fold(sp)

        # facing a raise
        raiser = sp.raiser
        if raiser < 0:
            raiser = sp.opps[0] if sp.opps else -1
        r_total = sp.stacks[raiser] + sp.bets[raiser] if raiser >= 0 else 0
        r_allin = raiser >= 0 and sp.stacks[raiser] == 0
        width = self.opp_raise_range(raiser, sp, r_allin, raises) if raiser >= 0 else 0.15
        eq = range_eq(c, width)
        # other players also in (callers, players behind who might wake up)
        extra = max(0, n_opp_in - 1)
        if extra:
            eq *= 0.80 ** extra
        to_call = sp.to_call
        pot = sp.pot
        commit = to_call >= 0.35 * (sp.stack) or r_allin or (sp.stack - to_call) < 6 * bb
        # how much can still go in from others behind
        behind_alive = [s for s in sp.behind if s != raiser]
        if commit:
            # all-in decision: call (or shove) vs fold
            risk = min(sp.stack, max(r_total - sp.bet, to_call))
            if not r_allin and sp.can_raise:
                # we'd shove; raiser may fold sometimes
                win_net = pot + risk - (to_call if risk > to_call else 0) * 0
                win_net = pot + (risk - to_call)
                p_fold = 0.0 if to_call >= 0.5 * risk else 0.25
                ev = p_fold * pot + (1 - p_fold) * (eq * (pot + risk - to_call) * 1.0 - (1 - eq) * risk * (1 + self.lam_risk(sp, risk)))
                if ev > 0:
                    self.pf_aggr = True
                    return act_allin(sp)
                return act_fold(sp)
            call_amt = min(to_call, sp.stack)
            win = pot
            if behind_alive:
                eq *= 0.93 ** len(behind_alive)
            if 3 <= sp.n_alive <= 4 and P["icm"] > 0 and raiser >= 0 and sp.n_opp == 1:
                me = sp.me
                base = {o: sp.stacks[o] for o in obs["alive"]}
                pays = self.points[:sp.n_alive] + [0] * 8
                excess = max(0, sp.bets[raiser] - (sp.bet + call_amt))
                f = dict(base)
                f[raiser] += pot
                w = dict(base)
                w[me] = sp.stack + pot - excess
                w[raiser] += excess
                l = dict(base)
                l[me] = sp.stack - call_amt
                l[raiser] += pot + call_amt
                ef = icm_small(f, pays)[me]
                ew = icm_small(w, pays)[me]
                el = icm_small(l, pays)[me]
                if eq * ew + (1 - eq) * el > ef:
                    return act_call(sp)
                return act_fold(sp)
            ev = eq * win - (1 - eq) * call_amt * (1 + self.lam_risk(sp, call_amt))
            if ev > 0:
                return act_call(sp)
            return act_fold(sp)
        # deep: 3-bet / call / fold
        my_eff_bb = min(my_total, r_total) / bb
        if raises == 1 and my_eff_bb <= RESTEAL_BB and sp.can_raise and not extra_callers(sp):
            # resteal shove: raiser folds unless in the top part of the range
            wc = max(0.025, width * CALL_SHARE)
            eqc = range_eq(c, wc)
            p_call = min(1.0, wc / width)
            risk = min(sp.stack, r_total - sp.bet)
            final = pot + risk + (min(r_total, my_total) - sp.bets[raiser])
            ev_c = eqc * (final - risk) - (1 - eqc) * risk * (1 + self.lam_risk(sp, risk))
            p_behind = 1.0
            for s in behind_alive:
                p_behind *= 1 - 0.5 * self.opp_call_freq(s, min(my_total, sp.stacks[s] + sp.bets[s]) / bb)
            ev = p_behind * ((1 - p_call) * pot + p_call * ev_c) - (1 - p_behind) * risk * 0.4
            if ev > RESTEAL_MARGIN * bb:
                self.pf_aggr = True
                return act_allin(sp)
        if (eq >= 0.60 or pct < 0.025) and sp.can_raise:
            self.pf_aggr = True
            if my_eff_bb <= 30:
                return act_allin(sp)
            cur = sp.bet + to_call
            return self.raise_to(sp, cur * 3 + (pot - cur - sp.bet))
        need = to_call / (pot + to_call)
        implied = 0.0
        a, b = divmod(c, 13)
        if a == b and my_eff_bb > 25 and to_call <= min(my_total, r_total) / 12:
            implied = 0.12
        elif a > b and my_eff_bb > 30 and to_call <= min(my_total, r_total) / 15:
            implied = 0.06
        if eq + implied >= need + P["call_m"] and to_call <= 0.25 * sp.stack:
            return act_call(sp)
        return act_fold(sp)

    def shove_ev(self, sp, c, behind, eff, lam):
        bb = sp.bb
        dead = sp.pot
        p_all_fold = 1.0
        ev_called = 0.0
        p_reach = 1.0
        my_total = sp.stack + sp.bet
        for s in behind:
            o_total = sp.stacks[s] + sp.bets[s]
            e = min(my_total, o_total)
            q = self.opp_call_freq(s, e / bb)
            eq = range_eq(c, q)
            risk = e - sp.bet
            final = dead - sp.bets[s] + 2 * e - sp.bet + sp.bet
            # final pot when called heads-up: dead money + both all-in amounts
            final = dead + (e - sp.bet) + (e - sp.bets[s])
            win_net = final - risk
            ev_c = eq * win_net - (1 - eq) * risk * (1 + self.lam_risk(sp, risk))
            ev_called += p_reach * q * ev_c
            p_reach *= (1 - q)
        p_all_fold = p_reach
        return p_all_fold * dead + ev_called

    def shove_icm(self, sp, c, callers, obs):
        """Points EV of shoving minus folding (exact ICM, 3-4 players)."""
        bb = sp.bb
        me = sp.me
        pot = sp.pot
        base = {o: sp.stacks[o] for o in obs["alive"]}
        pays = self.points[:sp.n_alive] + [0] * 8
        # folding: approximate the pot going to the big blind
        f = dict(base)
        tgt = obs["bb_seat"] if obs["bb_seat"] in f and obs["bb_seat"] != me else callers[-1]
        f[tgt] += pot
        ef = icm_small(f, pays)[me]
        a = dict(base)
        a[me] += pot
        total = 0.0
        p_reach = 1.0
        my_total = sp.stack + sp.bet
        for o in callers:
            o_total = sp.stacks[o] + sp.bets[o]
            e = min(my_total, o_total)
            q = self.opp_call_freq(o, e / bb)
            eq = range_eq(c, q)
            my_add = e - sp.bet
            o_add = e - sp.bets[o]
            final = pot + my_add + o_add
            w = dict(base)
            w[me] = sp.stack - my_add + final
            w[o] -= o_add
            l = dict(base)
            l[me] = sp.stack - my_add
            l[o] += final - o_add
            ev_c = eq * icm_small(w, pays)[me] + (1 - eq) * icm_small(l, pays)[me]
            total += p_reach * q * ev_c
            p_reach *= 1 - q
        total += p_reach * icm_small(a, pays)[me]
        return total - ef

    def raise_to(self, sp, amount):
        if not sp.can_raise:
            return act_call(sp)
        amount = int(amount)
        # if raise would leave little behind, shove instead
        if sp.stack + sp.bet - amount < 0.35 * (sp.stack + sp.bet):
            if amount > 0.6 * (sp.stack + sp.bet):
                return act_allin(sp)
        return act_raise(sp, amount)

    def bet_frac(self, sp, frac):
        """Bet/raise by frac of pot (after calling)."""
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            return act_allin(sp)
        return act_raise(sp, target)

    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        st = sp.street
        n_opp = max(1, sp.n_opp)
        draw = 0.0
        if st == 1:
            draw = min(0.45, outs * 0.04)
        elif st == 2:
            draw = min(0.30, outs * 0.022)
        eq = s + (1 - s) * draw if draw > 0 else s
        if n_opp > 1:
            eq = eq ** (1 + 0.65 * (n_opp - 1))
        pot = sp.pot
        to_call = sp.to_call
        spr = sp.stack / max(pot, 1)
        rng = self.rng
        if to_call == 0:
            if not sp.can_raise:
                return {"action": "check"}
            # how often the opponents fold to postflop bets (prior 0.45)
            ftb = 0.0
            for o in sp.opps:
                so = self.stats.get(o)
                ftb += so.ftb() if so is not None else 0.45
            ftb /= n_opp
            station = ftb < 0.3
            if eq >= 0.72:
                if spr < 1.2:
                    return act_allin(sp)
                return self.bet_frac(sp, (0.85 if station else 0.7) if wet else (0.75 if station else 0.6))
            bluff_scale = min(1.6, max(0.3, ftb / 0.45))
            if self.pf_aggr and st == 1 and n_opp <= 2:
                # continuation bet
                freq = (P["cbet"] if n_opp == 1 else 0.6 * P["cbet"]) * bluff_scale
                if eq >= 0.45 or rng.random() < freq:
                    return self.bet_frac(sp, 0.5)
            if n_opp == 1 and (eq >= 0.55 or (station and eq >= 0.5)):
                return self.bet_frac(sp, 0.6 if station else 0.5)
            if outs >= 8 and st < 3 and rng.random() < 0.45 * bluff_scale:
                return self.bet_frac(sp, 0.6)
            if sp.ip and n_opp == 1 and st >= 2 and rng.random() < 0.25 * bluff_scale and s >= 0.2:
                return self.bet_frac(sp, 0.5)
            return {"action": "check"}
        # facing a bet
        need = to_call / (pot + to_call)
        bet_ratio = to_call / max(pot - to_call, 1)
        # aggressors' perceived strength
        ag = 0.35
        if sp.raiser >= 0:
            so = self.stats.get(sp.raiser)
            if so is not None:
                ag = so.aggr()
        penalty = (0.10 + 0.08 * min(bet_ratio, 2.0)) * (1.3 - ag) * P["pen"]
        if sp.raises >= 2:
            penalty += 0.08
        # draws: only next card guaranteed
        all_in_call = to_call >= sp.stack
        bettor_allin = sp.raiser >= 0 and sp.stacks[sp.raiser] == 0
        if all_in_call or bettor_allin or st == 3:
            eqe = eq - penalty
        else:
            # draws: only the next card is guaranteed, plus some implied odds
            eq_c = s + (1 - s) * (min(0.24, outs * 0.023 + (0.02 if outs >= 8 and spr > 2 else 0.0)) if st < 3 else 0.0)
            if n_opp > 1:
                eq_c = eq_c ** (1 + 0.65 * (n_opp - 1))
            eqe = eq_c - penalty
        if (eqe >= 0.75 or s >= 0.86) and sp.can_raise and not all_in_call:
            if spr < 2.0:
                return act_allin(sp)
            return self.raise_to(sp, sp.bet + to_call + 0.9 * (pot + to_call) + to_call)
        if eqe >= need + 0.03:
            return act_call(sp)
        # pot committed
        if sp.stack < 0.25 * pot and eqe >= need - 0.05:
            return act_call(sp)
        return act_fold(sp)
