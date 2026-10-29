"""montecarlo: estimates equity at decision time by Monte Carlo against a
random hand for every opponent still in, dealing out the board, for a
wall-clock budget of about 0.7 ms (in Omaha-style variants, where one
showdown is slow, it simulates at most two opponents and extrapolates).
Raises when equity is well above its fair share, calls when it beats the pot
odds, folds otherwise.

Leaks modelled: random-hand equity ignores what opponents' bets say; the
sample size, and so the noise, depends on machine load, and under load a
decision can run past the 1 ms limit.
"""

import time
from itertools import combinations

from ._common import SafeAgent, Spot, act_allin, act_call, act_discard, act_fold, act_pot, keep_score

BUDGET_S = 0.0007


class Agent(SafeAgent):
    def equity(self, sp: Spot, t0: float) -> float:
        var = self.var
        hero = sp.hole
        per = var.hole_count
        if len(hero) > per:
            hero = list(max(combinations(hero, per), key=lambda h: keep_score(var, list(h), sp.board)))
        known = set(sp.hole) | set(sp.board)
        deck = [c for c in var.deck if c not in known]
        need = max(0, var.board_count - len(sp.board))
        n_opp = max(1, min(sp.n_opp, (len(deck) - need) // max(per, 1)))
        sim = n_opp if var.family == "holdem" else min(n_opp, 2)
        draw = need + per * sim
        best, sample, clock = var.best, self.rng.sample, time.perf_counter
        board0 = sp.board
        wins = 0.0
        n = 0
        start = clock()
        while True:
            cards = sample(deck, draw)
            board = board0 + cards[:need]
            hv = best(hero, board)
            top = -1
            ties = 0
            for i in range(need, draw, per):
                v = best(cards[i:i + per], board)
                if v > top:
                    top = v
                if v == hv:
                    ties += 1
            wins += 1.0 if hv > top else 1.0 / (1 + ties) if hv == top else 0.0
            n += 1
            now = clock()
            if now - t0 + (now - start) / n > BUDGET_S:
                return (wins / n) ** (n_opp / sim)

    def decide(self, obs: dict) -> dict:
        t0 = time.perf_counter()
        if obs["phase"] == "discard":
            return act_discard(obs, self.var)
        sp = Spot(obs, self.var)
        eq = self.equity(sp, t0)
        share = eq * (max(1, sp.n_opp) + 1)
        if sp.to_call == 0:
            return act_pot(sp, 0.75) if share >= 1.3 else act_fold(sp)
        if share >= 1.85:
            return act_allin(sp)
        if share >= 1.6:
            return act_pot(sp, 1.0)
        if eq >= sp.to_call / (sp.pot + sp.to_call):
            return act_call(sp)
        return act_fold(sp)
