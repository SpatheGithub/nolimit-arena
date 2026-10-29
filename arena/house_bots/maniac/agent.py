"""maniac: shoves or makes big raises very often. Preflop it plays any pair,
any ace and any two broadway cards (ten or better), shoving about half of
them and raising big with the rest; postflop it bets the pot or shoves any
pair or draw, and bluffs often when checked to.

Leaks modelled: overshoves and overbets with weak ranges; can be called down
lighter and trapped.
"""

from ._common import (PAIR, SafeAgent, Spot, act_allin, act_call, act_discard, act_fold, act_pot,
                      act_raise, cat_strength)


class Agent(SafeAgent):
    def in_range(self, hole: list[int]) -> bool:
        ranks = [c >> 2 for c in hole]
        return len(set(ranks)) < len(ranks) or 12 in ranks or sum(1 for r in ranks if r >= 8) >= 2

    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        r = self.rng.random()
        if sp.street == 0:
            if self.in_range(sp.hole):
                if r < 0.5:
                    return act_allin(sp)
                return act_raise(sp, max(4 * (sp.bet + sp.to_call), 5 * sp.bb))
            if sp.to_call == 0:
                return act_raise(sp, 4 * sp.bb) if r < 0.25 else act_fold(sp)
            return act_call(sp) if sp.to_call <= 2 * sp.bb and r < 0.3 else act_fold(sp)
        s, outs, _, cat = cat_strength(self.var, sp.hole, sp.board)
        if cat >= PAIR or outs >= 8:
            return act_allin(sp) if r < 0.4 else act_pot(sp, 1.0)
        if sp.to_call == 0:
            return act_pot(sp, 0.75) if r < 0.4 else act_fold(sp)
        return act_call(sp) if r < 0.15 else act_fold(sp)
