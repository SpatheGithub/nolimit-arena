"""nit: plays only about the top 8% of starting hands, raising them first in,
and folds to any raise without a premium (QQ+ or AK). Postflop it bets strong
made hands, calls with good ones and folds to a raise without a monster.
Never bluffs.

Leaks modelled: folds too often to aggression, so steals and 3-bets print
money against it; the same ranges at every stack depth, so it blinds away
when short.
"""

from ._common import (SafeAgent, Spot, act_allin, act_call, act_discard, act_fold, act_pot, act_raise,
                      cat_strength, plo_strength, preflop_pct)

PLAY = 0.08


class Agent(SafeAgent):
    def premium(self, hole: list[int]) -> bool:
        if len(hole) >= 4:
            return plo_strength(hole) >= 0.85
        ranks = sorted((c >> 2 for c in hole), reverse=True)
        return any(ranks[i] == ranks[j] >= 10 for i in range(len(ranks)) for j in range(i + 1, len(ranks))) \
            or (12 in ranks and 11 in ranks)

    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            if sp.raises == 0:
                if preflop_pct(self.var, sp.hole) <= PLAY:
                    return act_raise(sp, (3 + sp.callers) * sp.bb)
                return act_fold(sp)
            if not self.premium(sp.hole):
                return act_fold(sp)
            if sp.raises == 1:
                return act_raise(sp, 3 * (sp.bet + sp.to_call))
            ranks = sorted(c >> 2 for c in sp.hole)
            return act_allin(sp) if ranks[-1] == ranks[-2] >= 11 else act_call(sp)
        s, _, _, _ = cat_strength(self.var, sp.hole, sp.board)
        if sp.to_call == 0:
            return act_pot(sp, 0.5) if s >= 0.6 else act_fold(sp)
        raised = sp.raises >= 2 or any(h[0] == sp.street and h[1] == sp.me and h[2] == "raise" for h in sp.hist)
        if raised:
            return act_call(sp) if s >= 0.85 else act_fold(sp)
        if s >= 0.85:
            return act_pot(sp, 0.75)
        if s >= 0.6 and sp.to_call <= sp.pot:
            return act_call(sp)
        return act_fold(sp)
