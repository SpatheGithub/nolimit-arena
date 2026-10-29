"""chip_pushfold: under 15 big blinds, Nash-like chip-EV push/fold charts.
First in, it shoves when the pushing chart allows the hand at its effective
stack (scaled down for antes and limps); facing a raise, it shoves or calls
only when the calling chart for the raiser's position allows the hand.
Deeper it limps or folds, calls raises only with premiums, and plays made
hands straightforwardly after the flop.

Leaks modelled: chip EV that ignores ICM, the points table and the hand cap;
passive limping when deep.
"""

from ._common import (SafeAgent, Spot, act_allin, act_call, act_discard, act_fold, act_pot, cat_strength,
                      plo_strength, preflop_pct)
from ._strategy import ChartVariant

SHORT_BB = 15.0


class Agent(SafeAgent):
    variant_cls = ChartVariant

    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            if sp.eff_bb < SHORT_BB and not self.var.limit:
                return self.push_fold(sp)
            return self.limp_fold(sp)
        return self.postflop(sp)

    def push_fold(self, sp: Spot) -> dict:
        pre = self.var.pre
        if pre is None:
            q = plo_strength(sp.hole) if len(sp.hole) >= 4 else 1.0 - preflop_pct(self.var, sp.hole)
            return act_allin(sp) if q >= (0.5 if sp.raises == 0 else 0.62) else act_fold(sp)
        c = pre.best_cls(sp.hole)
        obs = sp.obs
        blinds = (obs["sb"] + obs["bb"] + obs["ante"] * sp.n_alive) / sp.bb
        if sp.raises == 0:
            s = sp.eff_bb * 1.5 / max(1.5, sp.pot / sp.bb)
            if pre.push_ok(c, max(1, len(sp.behind) + sp.callers), s):
                return act_allin(sp)
            return act_fold(sp)
        v = sp.raiser
        s = min(sp.stacks[v] + sp.bets[v], sp.stack + sp.bet) / sp.bb * 1.5 / max(1.5, blinds)
        if pre.call_ok(c, sp.position_of(v), sp.role, s):
            return act_allin(sp)
        return act_fold(sp)

    def limp_fold(self, sp: Spot) -> dict:
        p = preflop_pct(self.var, sp.hole)
        if sp.raises == 0:
            return act_call(sp) if sp.to_call and p <= 0.35 else act_fold(sp)
        if p <= 0.04 and sp.to_call <= 0.2 * sp.stack:
            return act_call(sp)
        return act_fold(sp)

    def postflop(self, sp: Spot) -> dict:
        s, _, _, _ = cat_strength(self.var, sp.hole, sp.board)
        if sp.to_call == 0:
            return act_pot(sp, 0.5) if s >= 0.6 else act_fold(sp)
        if s >= 0.85:
            return act_pot(sp, 1.0)
        if s >= 0.55 and sp.to_call <= sp.pot:
            return act_call(sp)
        return act_fold(sp)
