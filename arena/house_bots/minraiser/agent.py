"""minraiser: min-raises any decent hand on every street (a top-30% starting
hand; later, a made hand that improves on the board or a strong draw) and
otherwise calls small bets; its raise size never depends on strength.

Leaks modelled: fixed min-raise sizing that offers cheap prices and earns no
fold equity; strong and marginal hands are played the same way.
"""

from ._common import SafeAgent, Spot, act_call, act_discard, act_fold, act_raise, cat_strength, preflop_pct

MAX_RAISES = 4


class Agent(SafeAgent):
    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            decent = preflop_pct(self.var, sp.hole) <= 0.30
        else:
            s, outs, _, _ = cat_strength(self.var, sp.hole, sp.board)
            decent = s >= 0.32 or outs >= 8
        if decent:
            return act_raise(sp, sp.min_to) if sp.raises < MAX_RAISES else act_call(sp)
        if sp.to_call <= max(sp.bb, 0.25 * sp.pot):
            return act_call(sp)
        return act_fold(sp)
