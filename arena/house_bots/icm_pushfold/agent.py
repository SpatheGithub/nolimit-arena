"""icm_pushfold: ICM-aware push/fold at or below 15 big blinds; deeper, the
shared tight-aggressive game.

Shoves and all-in calls compare Malmuth-Harville equity under
config["points"] (the open places are 1..players left) between folding and
shoving or calling. Opponents call with the chip-EV calling chart for their
seat, blended with their in-table VPIP; a shover's range comes from the
pushing chart and its in-table raise frequency. Folding is charged the
blinds the stack pays before its next good spot, a cost that falls to zero
as the 200-hand cap nears, when ICM on the current stacks is the exact
settlement. Heads-up, ICM is linear in chips, so chips are compared.

Strength: survives pay jumps and the hand-cap settlement that chip-EV bots
ignore, while still stealing from players who fold too much.
"""

import numpy as np

from ._common import Spot
from ._strategy import TagCore, icm_hero

FUTURE_HANDS = 3


class Agent(TagCore):
    def payouts(self, n: int) -> list[float]:
        pts = self.points[:n]
        return pts + [0.0] * (n - len(pts))

    def icm_matters(self, sp: Spot) -> bool:
        pay = self.payouts(sp.n_alive)
        return sp.n_alive >= 3 and max(pay) > min(pay)

    def values(self, sp: Spot, rows: list[dict]) -> list[float]:
        """Hero's Malmuth-Harville equity for each final chip count."""
        if not self.icm_matters(sp):
            return super().values(sp, rows)
        alive = sp.obs["alive"]
        others = [s for s in alive if s != sp.me]
        X = np.array([[r[s] for s in others] for r in rows], dtype=float)
        h = np.array([r[sp.me] for r in rows], dtype=float)
        return icm_hero(X, h, self.payouts(len(alive))).tolist()

    def premium(self, sp: Spot) -> float:
        return 0.0

    def fold_cost(self, sp: Spot) -> float:
        if not self.icm_matters(sp):
            return 0.0
        obs = sp.obs
        per_hand = (obs["sb"] + obs["bb"]) / max(2, sp.n_alive) + obs["ante"]
        return per_hand * min(FUTURE_HANDS, max(0, obs["hands_left"] - 1))
