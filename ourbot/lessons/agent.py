"""lessons: the house icm_pushfold game plus what the debriefs say wins against
AI-built fields (LESSONS.md, and section 7 of each event's DEBRIEF.md). Each
lesson sits behind a switch in switches.json, so the lab (ourbot/lab.py) can
measure what it adds or costs:

- resteal: re-shove over a single open, with no callers, at 8-30 big blinds
  when the shove beats folding. Fold equity is priced from the opener's in-table
  folds to 3-bets (prior 0.75, weight 4). The opener continues with the top of
  its opening range, and players behind call with a tightened calling chart. It
  only fires on a tight table: the opener and everyone behind show VPIP <= 0.30
  (prior 0.25, weight 8). This was the biggest single lever in both hold'em
  events.
- shove20: first in from the cutoff or later (three or fewer players behind) at
  15-20 big blinds, shove or fold by push/fold EV, as at 15 bb or less.
- noflat: in the blinds, facing a single open with no callers at 30 bb or less,
  don't flat-call. Re-shove (resteal) or fold, except a big-blind call with a
  top-40% hand. Flat-calling steals lost 0.3-0.6 bb per steal faced.
- respect: postflop, fold one pair or worse to a raise, and to a turn or river
  bet of at least 0.7 pot, unless the hand has a strong draw.
- chipev: value shoves and all-in calls in chips until 4 or fewer players are
  left, then by ICM. Optimise P(1st), not survival. The lab found ICM-throughout
  wins too few tables.

The lab's verdicts so far (ourbot/NOTES.md) set the shipped switches.json:
shove20 is off, because it cost about 1.2 points per table in hold'em.

All other play is icm_pushfold's: shoves and all-in calls compare
Malmuth-Harville equity under the points table, and deeper play is the shared
tight-aggressive core. _common and _strategy are copies of
arena/house_bots/_common.py and _strategy.py with their data files.
"""

import json
import os

import numpy as np

from ._common import PAIR, Spot, act_allin, act_discard, act_fold, features
from ._strategy import Reads, TagCore, icm_hero

FUTURE_HANDS = 3
ICM_FROM = 4  # with chipev on, ICM applies only once this many players or fewer are left
SWITCHES = ("resteal", "shove20", "noflat", "respect", "chipev")
DEFAULTS = {"resteal": True, "shove20": False, "noflat": True, "respect": True, "chipev": False}


def load_switches() -> dict[str, bool]:
    on = dict(DEFAULTS)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "switches.json")) as f:
            on.update({k: bool(v) for k, v in json.load(f).items() if k in on})
    except (OSError, ValueError):
        pass
    return on


class LessonReads(Reads):
    """Reads plus each seat's folds when its open meets a re-raise, and VPIP with a tighter prior."""

    def __init__(self, seats: int):
        super().__init__(seats)
        self.faced3 = [0] * seats
        self.folded3 = [0] * seats

    def update(self, event: dict) -> None:
        super().update(event)
        n = len(self.hands)
        opener, reraised = None, False
        for st, s, act, _ in event.get("history") or []:
            if st != 0:
                break
            if opener is None:
                if act == "raise":
                    opener = s
            elif not reraised:
                reraised = act == "raise" and s != opener
            elif s == opener:
                if 0 <= s < n:
                    self.faced3[s] += 1
                    self.folded3[s] += act == "fold"
                break

    def fold3_rate(self, seat: int) -> float:
        return (self.folded3[seat] + 0.75 * 4) / (self.faced3[seat] + 4)

    def loose(self, seat: int) -> float:
        return (self.vpip[seat] + 0.25 * 8) / (self.hands[seat] + 8)


class Agent(TagCore):
    def __init__(self, config: dict):
        super().__init__(config)
        self.reads = LessonReads(int(config.get("seats", 8)))
        self.on = load_switches()

    # icm_pushfold's ICM game (arena/house_bots/icm_pushfold/agent.py)

    def payouts(self, n: int) -> list[float]:
        pts = self.points[:n]
        return pts + [0.0] * (n - len(pts))

    def icm_matters(self, sp: Spot) -> bool:
        pay = self.payouts(sp.n_alive)
        if self.on["chipev"] and sp.n_alive > ICM_FROM:
            return False
        return sp.n_alive >= 3 and max(pay) > min(pay)

    def values(self, sp: Spot, rows: list[dict]) -> list[float]:
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

    # the lessons

    def decide(self, obs: dict) -> dict:
        var = self.var
        if obs.get("phase") == "discard":
            return act_discard(obs, var)
        sp = Spot(obs, var)
        if var.family != "holdem" or var.limit or sp.street > 0:
            return super().decide(obs)
        if self.on["resteal"] and self.single_open(sp) and 8 <= sp.eff_bb <= 30 and self.resteal_gains(sp):
            return act_allin(sp)
        if sp.eff_bb <= self.short_bb:
            return self.short_preflop(sp)
        if self.on["shove20"] and sp.raises == 0 and sp.to_call > 0 and sp.eff_bb <= 20 and len(sp.behind) <= 3:
            return act_allin(sp) if self.push_gains(sp) else act_fold(sp)
        a = self.preflop(sp)
        if self.on["noflat"] and a.get("action") == "call" and sp.role != "other" and self.single_open(sp) \
                and sp.eff_bb <= 30 and not (sp.role == "BB" and self.var.pre.pct[self.var.pre.best_cls(sp.hole)] <= 0.40):
            return act_fold(sp)
        return a

    def single_open(self, sp: Spot) -> bool:
        """One raise, nobody called it, hero hasn't acted voluntarily, and the opener has chips behind."""
        v = sp.raiser
        return (sp.raises == 1 and sp.callers == 0 and v >= 0 and v != sp.me and sp.stacks[v] > 0
                and not any(h[0] == 0 and h[1] == sp.me for h in sp.hist))

    def resteal_gains(self, sp: Spot) -> bool:
        """Does an all-in re-raise over the open beat folding? Players behind may call first, then the opener."""
        r = self.reads
        v = sp.raiser
        behind = [s for s in sp.behind if s != v]
        if r.loose(v) > 0.30 or any(r.loose(s) > 0.30 for s in behind):
            return False
        pre = self.var.pre
        c = pre.best_cls(sp.hole)
        me = sp.me
        base = {s: sp.stacks[s] for s in sp.obs["alive"]}
        fold, steal = dict(base), dict(base)
        fold[me] = max(0.0, base[me] - self.fold_cost(sp))
        fold[v] += sp.pot
        steal[me] += sp.pot
        rows = [fold, steal]
        hero_total = sp.stack + sp.bet
        odds = []
        for j in behind:
            s = min(hero_total, sp.stacks[j] + sp.bets[j]) / sp.bb
            width = 0.6 * self.call_width(sp, j, 1, s)
            odds.append((width, pre.top(c, width)))
            rows.extend(self.showdown_rows(sp, base, j))
        keep = 1.0 - r.fold3_rate(v)
        odds.append((keep, pre.top(c, max(0.02, self.villain_range(sp, v) * keep))))
        rows.extend(self.showdown_rows(sp, base, v))
        val = self.values(sp, rows)
        ev, nocall = 0.0, 1.0
        for i, (p, eq) in enumerate(odds):
            ev += nocall * p * (eq * val[2 + 2 * i] + (1 - eq) * val[3 + 2 * i])
            nocall *= 1 - p
        return ev + nocall * val[1] > val[0]

    def postflop(self, sp: Spot) -> dict:
        if self.on["respect"] and sp.to_call > 0:
            s, outs, _, cat = features(self.var, sp.hole, sp.board)
            if cat <= PAIR and s < 0.9 and outs < 8:
                big = len(sp.board) >= 4 and sp.to_call >= 0.7 * max(1.0, sp.pot - sp.to_call)
                if sp.raises >= 2 or big:
                    return act_fold(sp)
        return super().postflop(sp)
