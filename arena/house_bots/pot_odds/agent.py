"""pot_odds: calls whenever a crude equity estimate beats the pot odds.
Preflop equity comes from a table of equity against k random hands; postflop
from the made-hand category, plus draw outs by the rule of 4 and 2, raised to
the number of opponents. Bets or raises only near-certain winners and never
bluffs.

Leaks modelled: a calling station; random-hand equity overrates its holdings
against real betting ranges, and it pays off value bets.
"""

from ._common import SafeAgent, Spot, act_call, act_discard, act_fold, act_pot, draw_outs, preflop_pct

CRUDE = (0.15, 0.50, 0.72, 0.82, 0.88, 0.90, 0.95, 0.98, 0.99)


class Agent(SafeAgent):
    def equity(self, sp: Spot) -> float:
        var = self.var
        k = max(1, sp.n_opp)
        if sp.street == 0:
            if var.pre is not None:
                return var.pre.multi(var.pre.best_cls(sp.hole), k)
            return (1.0 - preflop_pct(var, sp.hole) / 2) ** k
        cat = var.ranker.category(var.best(sp.hole, sp.board))
        eq = CRUDE[cat]
        if not sp.last_street:
            eq += draw_outs(var, sp.hole, sp.board, cat) * (0.04 if len(sp.board) == 3 else 0.02)
        return min(eq, 0.99) ** k

    def decide(self, obs: dict) -> dict:
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        eq = self.equity(sp)
        if sp.to_call == 0:
            return act_pot(sp, 0.5) if eq >= 0.85 else act_fold(sp)
        if eq >= 0.92:
            return act_pot(sp, 0.5)
        if eq >= sp.to_call / (sp.pot + sp.to_call):
            return act_call(sp)
        return act_fold(sp)
