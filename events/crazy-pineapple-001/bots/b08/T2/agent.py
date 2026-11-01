"""b08 crazy-pineapple bot: tight-aggressive, push/fold when short, opponent reads."""

import random
from itertools import combinations

from ._common import (Variant, Spot, CARD, act_fold, act_call, act_raise, act_allin,
                      features, safe_default, HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.pre = self.var.pre
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        n = max(8, config.get("seats", 8))
        self.seen = [0] * 16
        self.pfr = [0] * 16
        self.vpip = [0] * 16
        self.shoves = [0] * 16
        self.pf_aggr_hand = -1

    # ---------------- helpers
    def pct2(self, a, b):
        pre = self.pre
        return pre.pct[pre.cls(a, b)]

    def rank3(self, hole):
        """Percentile rank (0 best) of our hole among dealt hands of this size."""
        if self.pre is None:
            return 0.5
        if len(hole) == 2:
            return self.pct2(hole[0], hole[1])
        ps = sorted(self.pct2(a, b) for a, b in combinations(hole, 2))
        p = ps[0]
        r = 1.0 - (1.0 - p) ** len(hole)
        if len(ps) > 1 and ps[1] < 0.25:
            r -= 0.04 * (0.25 - ps[1]) / 0.25
        return clamp(r, 0.0, 1.0)

    def best_pair_eq(self, hole, k):
        pre = self.pre
        best = None
        for a, b in combinations(hole, 2):
            c = pre.cls(a, b)
            if best is None or pre.pct[c] < pre.pct[best]:
                best = c
        return pre.multi(best, k)

    def post_strength(self, hole, board):
        """(eq estimate vs one random-ish opponent, s, outs, wet, cat, kept)."""
        best = None
        for kept in combinations(hole, 2):
            s, outs, wet, cat = features(self.var, list(kept), board)
            nb = len(board)
            q = s + outs * (0.032 if nb == 3 else 0.018 if nb == 4 else 0.0)
            if best is None or q > best[0]:
                best = (q, s, outs, wet, cat, kept)
        if len(hole) == 3:
            # third card adds options on the flop
            best = (best[0] + 0.02,) + best[1:]
        return best

    def opp_aggr(self, seat):
        return (self.pfr[seat] + 1.0) / (self.seen[seat] + 6.0)

    # ---------------- main
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            return safe_default(obs)

    def decide(self, obs):
        if obs["phase"] == "discard":
            return self.discard(obs)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            return self.preflop(obs, sp)
        return self.postflop(obs, sp)

    def discard(self, obs):
        hole = obs["hole"]
        k = obs.get("n_discard") or 1
        cs = [CARD[c] for c in hole]
        board = [CARD[c] for c in obs.get("board") or []]
        keep = len(cs) - k
        bestq, bestix = None, None
        for ix in combinations(range(len(cs)), keep):
            kept = [cs[i] for i in ix]
            if board and keep == 2:
                s, outs, wet, cat = features(self.var, kept, board)
                q = s + outs * 0.03
            else:
                q = -self.pct2(kept[0], kept[1]) if keep == 2 else 0
            if bestq is None or q > bestq:
                bestq, bestix = q, ix
        return {"action": "discard", "cards": [hole[i] for i in range(len(hole)) if i not in bestix]}

    def icm_tight(self, obs, sp):
        """Extra equity required when risking our stack (ICM pressure)."""
        alive = obs["alive"]
        n = len(alive)
        stacks = obs["stacks"]
        my = stacks[self.seat] + obs["bets"][self.seat]
        tot = sum(stacks) + sum(obs["bets"])
        avg = tot / max(1, n)
        extra = 0.0
        if n <= 4:
            extra += 0.03
        if my > 1.5 * avg:
            extra += 0.03
        if obs.get("hands_left", 200) <= 25 and n >= 3:
            extra += 0.03
        return extra

    def preflop(self, obs, sp):
        hole = sp.hole
        r = self.rank3(hole)
        bb = sp.bb
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_total = stacks[me] + bets[me]
        eff_bb = sp.eff_bb
        nb = len(sp.behind)
        raises = sp.raises
        to_call = sp.to_call
        pot = sp.pot
        rng = self.rng

        # ---- unopened pot (only blinds / limpers)
        if raises == 0:
            limpers = sp.callers
            if eff_bb <= 13:
                # push/fold
                nbe = max(1, nb)
                thr = 0.55 * nbe ** -0.75 * (10.0 / max(eff_bb, 2.0)) ** 0.8
                thr *= 1.0 - 0.1 * limpers
                thr -= self.icm_tight(obs, sp)
                if r <= thr:
                    return act_allin(sp)
                if sp.can_check:
                    return {"action": "check"}
                return act_fold(sp)
            # open raise ranges by players behind
            thr = {0: 0.0, 1: 0.40, 2: 0.30, 3: 0.24, 4: 0.20, 5: 0.17, 6: 0.15}.get(nb, 0.14)
            thr -= 0.04 * limpers
            if eff_bb < 25:
                thr *= 0.9
            if r <= thr:
                size = (2.5 + limpers) * bb if nb > 1 else 3.0 * bb
                if eff_bb < 25 and r <= 0.05:
                    return act_allin(sp) if eff_bb < 18 else act_raise(sp, size)
                return act_raise(sp, size)
            if sp.can_check:
                # BB option: raise strong hands
                if r <= 0.10 and limpers > 0:
                    return act_raise(sp, (3 + limpers) * bb)
                return {"action": "check"}
            # SB completing / limping is a leak; fold
            if to_call <= 0.5 * bb and r <= 0.5 and nb == 1:
                return act_call(sp)
            return act_fold(sp)

        # ---- facing a raise
        raiser = sp.raiser
        need = to_call / float(pot + to_call)
        r_bet = max(bets) / bb
        allin_faced = any(stacks[s] == 0 and bets[s] > 0 for s in sp.opps)
        aggr = self.opp_aggr(raiser) if raiser >= 0 else 0.2
        # estimated raiser range width
        q = 0.12
        rstack = (stacks[raiser] + bets[raiser]) / bb if raiser >= 0 else 20
        if allin_faced or to_call >= 0.6 * my_total:
            q = 0.30 if rstack <= 8 else 0.22 if rstack <= 15 else 0.14 if rstack <= 30 else 0.08
        else:
            q = 0.14 if r_bet <= 3.5 else 0.10
        q = max(q, min(0.6, aggr * 1.2))
        if raises >= 2:
            q *= 0.5
        commit = to_call >= 0.4 * my_total or eff_bb <= 15
        if commit:
            f = clamp((0.62 - need) / 0.24, 0.25, 1.6)
            thr = q * f - self.icm_tight(obs, sp) * 0.5
            if r <= thr or r <= 0.015:
                return act_allin(sp)
            return act_fold(sp)
        # deep-ish: 3-bet / call / fold
        if r <= min(0.035, q * 0.35) or r <= 0.02:
            if eff_bb <= 30:
                return act_allin(sp)
            target = 3.0 * max(bets) + sum(1 for _ in sp.opps) * 0 + (pot - sum(bets))
            if raises >= 2:
                target = 2.4 * max(bets)
            return act_raise(sp, target)
        call_thr = q * 0.9 * clamp((0.45 - need) / 0.2, 0.3, 1.5)
        if raises >= 2:
            call_thr = min(call_thr, 0.03)
        if r <= call_thr and to_call <= 0.25 * my_total:
            return act_call(sp)
        return act_fold(sp)

    def postflop(self, obs, sp):
        hole = sp.hole
        board = sp.board
        eq, s, outs, wet, cat, kept = self.post_strength(hole, board)
        n_opp = max(1, sp.n_opp)
        eqm = eq - 0.08 * (n_opp - 1)
        pot = sp.pot
        to_call = sp.to_call
        me = self.seat
        my_total = sp.stack + sp.bet
        rng = self.rng
        last = sp.last_street
        # was I the preflop aggressor?
        pf_raiser = -1
        for h_st, seat, a, _ in sp.hist:
            if h_st == 0 and a == "raise":
                pf_raiser = seat
        aggressor = pf_raiser == me or sp.last_aggr == me
        spr = sp.stack / float(max(pot, 1))

        if to_call == 0:
            if eqm >= 0.70 or (eqm >= 0.60 and n_opp <= 2):
                frac = 0.75 if wet else 0.6
                if spr < 1.2:
                    return act_allin(sp)
                return self.bet_frac(sp, frac)
            if outs >= 8 and not last and n_opp <= 2 and rng.random() < 0.6:
                return self.bet_frac(sp, 0.6)
            if aggressor and n_opp <= 2 and sp.street == 1 and rng.random() < (0.55 if not wet else 0.4):
                return self.bet_frac(sp, 0.5)
            if sp.ip and n_opp == 1 and rng.random() < 0.25 and eqm < 0.35:
                return self.bet_frac(sp, 0.5)
            return {"action": "check"}

        # facing a bet
        need = to_call / float(pot + to_call)
        bet_ratio = to_call / float(max(1, pot - to_call))
        eqa = eqm - 0.06 * clamp(bet_ratio, 0, 2) - self.icm_tight(obs, sp) * (1 if to_call >= 0.4 * my_total else 0.3)
        # vs aggressive opponent loosen
        bettor = -1
        for h_st, seat, a, _ in sp.hist:
            if h_st == sp.street and a == "raise":
                bettor = seat
        if bettor >= 0 and self.opp_aggr(bettor) > 0.35:
            eqa += 0.06
        if eqa >= 0.80 and sp.can_raise:
            if spr < 2.0 or to_call >= 0.35 * my_total:
                return act_allin(sp)
            return act_raise(sp, sp.bet + to_call + 1.0 * (pot + to_call) + to_call)
        if eqa >= need + 0.04:
            if to_call >= 0.6 * my_total and eqa < 0.6:
                return act_fold(sp)
            return act_call(sp)
        return act_fold(sp)

    def bet_frac(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            target = sp.max_to
        return act_raise(sp, target)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            raised = set()
            vp = set()
            for h_st, seat, a, amt in hist:
                if seat is None or seat < 0 or seat >= 16:
                    continue
                if h_st == 0:
                    seen.add(seat)
                    if a == "raise":
                        raised.add(seat)
                        vp.add(seat)
                    elif a == "call":
                        vp.add(seat)
            for s in seen:
                self.seen[s] += 1
            for s in raised:
                self.pfr[s] += 1
            for s in vp:
                self.vpip[s] += 1
        except Exception:
            pass
