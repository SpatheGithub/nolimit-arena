"""checkfold: the template's behaviour. Checks when checking is free and
folds otherwise; in a discard phase it keeps its best hole cards.

Leak modelled: never puts a chip in voluntarily, so it blinds away and
gives up every pot to any bet.
"""

from ._common import SafeAgent, act_discard


class Agent(SafeAgent):
    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
