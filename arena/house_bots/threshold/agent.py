"""threshold: a static preflop strength threshold (Chen score of the best two
hole cards) and postflop thresholds on the made-hand category. Min-raises
strong hands, calls medium ones, check-folds the rest.

Leaks modelled: ignores position, stack depth, bet size, the points table and
the opponents; counts hands made by the board as its own; the same
thresholds in every variant.
"""

from ._common import PAIR, TWO_PAIR, SafeAgent, Spot, act_call, act_discard, act_fold, act_raise, best_chen

RAISE_CHEN = 9.0
CALL_CHEN = 6.0


class Agent(SafeAgent):
    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            score = best_chen(sp.hole)
            strong, medium = score >= RAISE_CHEN, score >= CALL_CHEN
        else:
            cat = self.var.ranker.category(self.var.best(sp.hole, sp.board))
            strong, medium = cat >= TWO_PAIR, cat == PAIR
        if strong:
            return act_raise(sp, sp.min_to)
        if medium:
            return act_call(sp)
        return act_fold(sp)
