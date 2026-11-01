"""b04 crazy pineapple bot: preflop percentile ranges + push/fold, postflop
Monte Carlo equity with a time budget, simple opponent stats."""

import time
from itertools import combinations

from ._common import (CARD, SafeAgent, Spot, act_allin, act_call, act_discard, act_fold,
                      act_pot, act_raise)

BUDGET_S = 0.00028


class Agent(SafeAgent):
    def __init__(self, config):
        super().__init__(config)
        self.seat = config["seat"]
        self.vpip = {}
        self.pfr = {}
        self.seen = {}
        self.aggr = {}

    # ---------- opponent stats ----------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seats = set()
            vp = set()
            pr = set()
            for st, seat, act, _ in hist:
                if st == 0:
                    seats.add(seat)
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                elif act == "raise":
                    self.aggr[seat] = self.aggr.get(seat, 0) + 1
            for s in seats:
                self.seen[s] = self.seen.get(s, 0) + 1
                if s in vp:
                    self.vpip[s] = self.vpip.get(s, 0) + 1
                if s in pr:
                    self.pfr[s] = self.pfr.get(s, 0) + 1
        except Exception:
            pass

    def pfr_rate(self, seat):
        n = self.seen.get(seat, 0)
        return (self.pfr.get(seat, 0) + 2.0) / (n + 10.0)

    def vpip_rate(self, seat):
        n = self.seen.get(seat, 0)
        return (self.vpip.get(seat, 0) + 3.0) / (n + 10.0)

    # ---------- preflop strength ----------
    def q3(self, hole):
        """Approximate fraction of 3-card hands that are better (0 = best)."""
        pre = self.var.pre
        ps = sorted(pre.pct[pre.cls(a, b)] for a, b in combinations(hole, 2))
        s = ps[0] - 0.08 * max(0.0, 0.5 - ps[1]) - 0.04 * max(0.0, 0.5 - ps[2])
        s = max(0.0, s)
        return 1.0 - (1.0 - s) ** 3

    # ---------- equity ----------
    def equity(self, sp, t0):
        hero = sp.hole
        board0 = sp.board
        best = self.var.best
        if len(hero) > 2:
            pre = self.var.pre
            hero = list(max(combinations(hero, 2), key=lambda h: (best(list(h), board0), -pre.pct[pre.cls(h[0], h[1])])))
        known = set(sp.hole) | set(board0)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board0)
        per = 3 if len(board0) == 3 else 2
        n_opp = max(1, min(sp.n_opp, 4))
        draw = need + per * n_opp
        value = self.var.ranker.value
        sample = self.rng.sample
        clock = time.perf_counter
        wins = 0.0
        n = 0
        while True:
            cards = sample(deck, draw)
            board = board0 + cards[:need]
            hv = value(hero + board)
            top = -1
            ties = 0
            for i in range(need, draw, per):
                v = value(cards[i:i + per] + board)
                if v > top:
                    top = v
                    ties = 0
                if v == hv:
                    ties += 1
            wins += 1.0 if hv > top else (1.0 / (1 + ties) if hv == top else 0.0)
            n += 1
            if n >= 200 or clock() - t0 > BUDGET_S:
                break
        eq = wins / n
        if sp.n_opp > n_opp:
            eq = eq ** (sp.n_opp / n_opp)
        return eq

    # ---------- decisions ----------
    def decide(self, obs):
        t0 = time.perf_counter()
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            return self.preflop(sp, obs)
        return self.postflop(sp, obs, t0)

    def preflop(self, sp, obs):
        q = self.q3(sp.hole)
        bb = sp.bb
        my_total = sp.stack + sp.bet
        eff_bb = sp.eff_bb
        nbehind = len(sp.behind)
        n_alive = sp.n_alive
        # open thresholds by players behind (incl. blinds)
        open_thr = {0: 0.5, 1: 0.45, 2: 0.32, 3: 0.24, 4: 0.19, 5: 0.15, 6: 0.13, 7: 0.11}.get(nbehind, 0.11)
        if n_alive <= 4:
            open_thr *= 1.25
        cur = max(sp.bets) if sp.bets else 0
        raises = sp.raises
        if raises == 0:
            # unopened or limped pot
            limpers = sum(1 for s in sp.opps if sp.bets[s] >= bb and s != obs["bb_seat"])
            if eff_bb <= 13:
                thr = min(0.75, open_thr * (13.0 / max(eff_bb, 1.0)) ** 0.8)
                if limpers:
                    thr *= 0.7
                if q <= thr:
                    return act_allin(sp)
                return act_fold(sp)
            if sp.can_check:
                # BB option after limps
                if q <= 0.08:
                    return act_raise(sp, cur + (3 + limpers) * bb)
                return act_fold(sp)
            thr = open_thr * (0.75 if limpers else 1.0)
            if q <= thr:
                return act_raise(sp, (2.5 + limpers) * bb)
            # complete SB cheaply with decent hands
            if sp.role == "SB" and limpers == 0 and q <= 0.5 and sp.to_call <= bb / 2:
                return act_call(sp)
            return act_fold(sp)
        # facing raise(s)
        raiser = sp.raiser
        to_call = sp.to_call
        pot = sp.pot
        po = to_call / float(pot + to_call)
        r_total = sp.stacks[raiser] + sp.bets[raiser] if raiser >= 0 else my_total
        allin_raise = raiser >= 0 and sp.stacks[raiser] == 0
        x = self.pfr_rate(raiser) if raiser >= 0 else 0.2
        r_bb = r_total / bb
        # range width estimate of the raiser (in 3-card percentile units)
        if allin_raise:
            width = min(0.7, max(0.06, x * 1.2 + (0.25 if r_bb < 8 else 0.1 if r_bb < 15 else 0.0)))
        else:
            width = min(0.6, max(0.05, x))
        if raises >= 2:
            width *= 0.5
        g = min(1.6, max(0.35, 0.7 + 2.5 * (0.45 - po)))
        call_thr = min(0.65, max(0.015, width * g))
        # commitment: call would put most of stack in
        committed = to_call >= 0.4 * my_total or eff_bb <= 15
        if committed:
            if q <= call_thr:
                return act_allin(sp)
            return act_fold(sp)
        # deep: 3-bet / call / fold
        if q <= min(0.03, width * 0.3) or q <= 0.012:
            target = cur * 3 + sum(sp.bets[s] for s in sp.opps if s != raiser) * 0
            if target > 0.35 * my_total:
                return act_allin(sp)
            return act_raise(sp, target)
        flat_thr = min(call_thr, 0.2 if (sp.role == "BB" and po <= 0.3) else 0.12) * (1.0 if sp.ip or sp.role == "BB" else 0.75)
        if to_call <= 0.12 * my_total and q <= flat_thr:
            return act_call(sp)
        return act_fold(sp)

    def postflop(self, sp, obs, t0):
        eq = self.equity(sp, t0)
        n_opp = max(1, sp.n_opp)
        pot = sp.pot
        to_call = sp.to_call
        share = eq * (n_opp + 1)
        my_total = sp.stack + sp.bet
        # was I the preflop aggressor?
        pre_aggr = -1
        for st, seat, act, _ in sp.hist:
            if st == 0 and act == "raise":
                pre_aggr = seat
        rnd = self.rng.random()
        if to_call == 0:
            if share >= 1.45 or eq >= 0.72:
                return act_pot(sp, 0.7)
            if share >= 1.15 and n_opp <= 2 and rnd < 0.5:
                return act_pot(sp, 0.5)
            if pre_aggr == sp.me and sp.street == 1 and (n_opp == 1 and rnd < 0.55 or n_opp == 2 and rnd < 0.2):
                return act_pot(sp, 0.45)
            if n_opp == 1 and sp.ip and rnd < 0.25 and sp.street >= 2 and eq >= 0.4:
                return act_pot(sp, 0.55)
            return act_fold(sp)
        po = to_call / float(pot + to_call)
        # bettors have stronger ranges than random: discount equity by bet size
        frac = to_call / float(max(1, pot - to_call))
        adj = eq - (0.08 + 0.14 * min(1.5, frac)) * (1.0 if sp.raises <= 1 else 1.5)
        if sp.street == 3:
            adj -= 0.04
        if (eq >= 0.85 or share >= 2.4) and sp.can_raise:
            return act_pot(sp, 0.9)
        if adj >= po:
            if to_call >= 0.5 * my_total and adj < po + 0.05 and eq < 0.6:
                return act_fold(sp)
            return act_call(sp)
        return act_fold(sp)
