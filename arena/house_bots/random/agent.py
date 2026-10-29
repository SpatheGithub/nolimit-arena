"""random: picks a uniformly random legal action; a bet or raise goes to a
uniformly random amount between the minimum and the maximum. In a discard
phase it keeps its best hole cards.

Leak modelled: no strategy at all, the floor any real bot must clear; its
random shoves also test opponents' calling ranges.
"""

from ._common import SafeAgent, act_discard

CHOICES = ("fold", "check", "call", "raise", "bet")


class Agent(SafeAgent):
    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        name = self.rng.choice([a for a in obs["legal"] if a in CHOICES] or ["check"])
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if name in ("raise", "bet"):
            if 0 < lo <= hi:
                return {"action": "raise", "amount": self.rng.randint(lo, hi)}
            name = "call" if obs["to_call"] else "check"
        return {"action": name}
