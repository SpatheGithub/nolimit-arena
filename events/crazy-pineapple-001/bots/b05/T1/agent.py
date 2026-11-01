import random
from itertools import combinations

from ._common import (CARD, HIGH, PAIR, TWO_PAIR, Spot, Variant, act_allin, act_call, act_discard,
                      act_fold, act_pot, act_raise, features, keep_score, preflop_pct, safe_default)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.stats = {}  # seat -> [hands, vpip, pfr]

    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            return safe_default(obs)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            seen = set()
            vp = set()
            pr = set()
            for st, seat, a, _ in event.get("history", []):
                if st == 0:
                    seen.add(seat)
                    if a in ("call", "raise"):
                        vp.add(seat)
                    if a == "raise":
                        pr.add(seat)
            for s in seen:
                r = self.stats.setdefault(s, [0, 0, 0])
                r[0] += 1
                r[1] += s in vp
                r[2] += s in pr
        except Exception:
            pass

    def pfr(self, seat, default=0.15):
        r = self.stats.get(seat)
        if not r or r[0] < 12:
            return default
        return (r[2] + default * 4) / (r[0] + 4)

    def vpip(self, seat, default=0.3):
        r = self.stats.get(seat)
        if not r or r[0] < 12:
            return default
        return (r[1] + default * 4) / (r[0] + 4)

    def decide(self, obs):
        var = self.var
        if obs["phase"] == "discard":
            return act_discard(obs, var)
        sp = Spot(obs, var)
        if sp.street == 0:
            return self.preflop(sp, obs)
        return self.postflop(sp, obs)

    # ---------------- preflop ----------------
    def preflop(self, sp, obs):
        pct = preflop_pct(self.var, sp.hole)
        eff = 1.0 - (1.0 - pct) ** 2.6  # percentile among 3-card hands
        bb = sp.bb
        m = sp.eff_bb
        behind = len(sp.behind)
        n_opp = sp.n_opp
        if sp.raises == 0:
            # unopened (maybe limpers)
            if m <= 13:
                base = {0: 0.55, 1: 0.50, 2: 0.38, 3: 0.30, 4: 0.24}.get(behind, 0.19)
                if m <= 6:
                    base += 0.15
                elif m <= 9:
                    base += 0.07
                if sp.callers:
                    base *= 0.7
                tight = sum(1 for s in sp.behind if self.vpip(s) < 0.22)
                base += 0.03 * tight
                if eff < base:
                    return act_allin(sp)
                return act_fold(sp)
            thr = {0: 0.45, 1: 0.42, 2: 0.33, 3: 0.24, 4: 0.19}.get(behind, 0.15)
            if sp.callers:
                thr *= 0.6
            tight = sum(1 for s in sp.behind if self.vpip(s) < 0.22)
            thr += 0.02 * tight
            if eff < thr:
                size = bb * (2.5 + sp.callers) + sp.bet * 0
                if m <= 20:
                    size = bb * (2.2 + sp.callers)
                return act_raise(sp, size)
            if sp.can_check:
                return act_fold(sp)
            # SB complete cheap
            if sp.role == "SB" and sp.to_call <= bb * 0.5 and eff < 0.5 and sp.callers == 0:
                return act_call(sp)
            return act_fold(sp)
        # facing raise
        raiser = sp.raiser
        R = max(0.08, min(0.6, self.pfr(raiser) * 1.1))
        if sp.raises >= 2:
            R *= 0.45
        stack_total = sp.stack + sp.bet
        commit = sp.to_call >= 0.35 * sp.stack or sp.stacks[raiser] == 0
        price = sp.to_call / (sp.pot + sp.to_call)
        x = (R - eff) / max(R, eff, 1e-6)
        eq = 0.5 + 0.33 * x
        eq = max(0.28, min(0.85, eq))
        if n_opp >= 2:
            eq *= 0.85 ** (n_opp - 1)
        # reraise
        if eff < min(0.035, R * 0.4) or (eff < R * 0.25 and sp.raises == 1):
            if m <= 30 or sp.raises >= 2:
                return act_allin(sp)
            return act_raise(sp, sp.bet + sp.to_call + 2.2 * (sp.pot + sp.to_call) * 0.75)
        if commit:
            if eq > price + 0.02:
                return act_call(sp)
            return act_fold(sp)
        # cheap call with good hand / implied odds
        if sp.to_call <= 0.08 * stack_total and eq > price + 0.05 and eff < 0.22:
            return act_call(sp)
        if eq > price + 0.12 and sp.to_call <= 0.2 * stack_total:
            return act_call(sp)
        return act_fold(sp)

    # ---------------- postflop ----------------
    def postflop(self, sp, obs):
        var = self.var
        hole, board = sp.hole, sp.board
        if len(hole) > 2:
            keep = list(max(combinations(hole, 2), key=lambda h: keep_score(var, list(h), board)))
        else:
            keep = hole
        s, outs, wet, cat = features(var, keep, board)
        # crazy pineapple: everyone picks best 2 of 3, hands run stronger
        if cat == PAIR:
            s *= 0.88
        elif cat == TWO_PAIR:
            s *= 0.94
        elif cat == HIGH:
            s *= 0.9
        if len(hole) > 2:
            outs += 2
        n_opp = max(1, sp.n_opp)
        eq = s ** (1.0 + 0.45 * (n_opp - 1))
        cards_left = var.board_count - len(board)
        if cards_left > 0:
            de = min(0.45, outs * (0.04 if cards_left >= 2 else 0.022))
            eq = eq + (1 - eq) * de * 0.85
        pot = sp.pot
        stack = sp.stack
        rng = self.rng
        if sp.to_call == 0:
            if eq >= 0.72:
                return act_pot(sp, 0.7)
            if eq >= 0.55 and n_opp <= 2:
                return act_pot(sp, 0.5)
            if outs >= 8 and cards_left > 0 and rng.random() < 0.45:
                return act_pot(sp, 0.55)
            if sp.last_aggr == sp.me and n_opp == 1 and len(board) == 3 and rng.random() < 0.6:
                return act_pot(sp, 0.4)
            if n_opp == 1 and sp.ip and rng.random() < 0.25 and not wet:
                return act_pot(sp, 0.45)
            return act_fold(sp)
        price = sp.to_call / (pot + sp.to_call)
        need = price + 0.06 + 0.10 * min(1.0, sp.to_call / max(1, pot - sp.to_call))
        if eq >= 0.86 or (eq >= 0.75 and sp.to_call >= 0.4 * stack):
            if eq >= 0.86:
                return act_pot(sp, 0.9)
            return act_call(sp)
        if eq >= need:
            return act_call(sp)
        return act_fold(sp)
