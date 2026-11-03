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
- chipsteal: price resteal the way event 2's winner (b06) did, in chips. The
  opener calls with probability 0.45 x its opening width, with the top of its
  range, and players behind call with 0.7x their calling chart. Shove when the
  EV beats folding and either the hand is top 10% or the EV is over 0.1 pot.
  Profiling showed resteal as first built almost never fired: 4.4% 3-bets
  against b06's 18.1%. Full ICM and a 25% call chance priced it out.
- calib: calibrate postflop hand strength to the variant. The house strength
  scale was tuned on a 52-card deck. In royal (T to A only) every 6-card hand
  holds at least a pair, so a pair is the weakest hand, yet the bot called
  like it was decent: it folded 28% to c-bets against the royal field's
  47-84%. At startup the bot measures the mean strength of random hands for
  each board size in this variant and in standard hold'em, and subtracts the
  difference. On 52-card decks the offset is zero.
- plo: an Omaha game with thresholds set to what the PLO builders do. The house
  omaha() opened the top 8-20% and won 0.2% of PLO tables, at 11% VPIP against
  the field's 23%. The thresholds are percentiles of plo_strength over random
  4-card hands. Open the top 40% late, 22% middle and 15% early. Facing an open,
  call with the top 15% (the big blind defends a late steal with the top 25%)
  and pot-raise with the top 5%. Heads-up flop c-bets go to 85%, and value bets
  are a little thinner.

The lab's verdicts so far (ourbot/NOTES.md) set the shipped switches.json:
- shove20 is off: it cost about 1.2 points per table in hold'em.
- chipsteal is on: with resteal and noflat it scored +7.5 +/- 1.5 points per
  table in hold'em, level with event 2's winner over the same tables.
- chipev is off: it was -0.6 on top of chipsteal.

All other play is icm_pushfold's: shoves and all-in calls compare
Malmuth-Harville equity under the points table, and deeper play is the shared
tight-aggressive core. _common and _strategy are copies of
arena/house_bots/_common.py and _strategy.py with their data files.
"""

import json
import os
import random

import numpy as np

from ._common import (PAIR, Spot, Variant, act_allin, act_call, act_discard, act_fold, act_pot, act_raise,
                      cat_strength, features, plo_strength, preflop_pct)
from ._strategy import Reads, TagCore, icm_hero

FUTURE_HANDS = 3
ICM_FROM = 4  # with chipev on, ICM applies only once this many players or fewer are left
VOLUNTARY = ("check", "call", "raise", "fold")  # history also holds the "sb", "bb" and ante posts
SWITCHES = ("resteal", "shove20", "noflat", "respect", "chipev", "chipsteal", "calib", "plo")
DEFAULTS = {"resteal": True, "shove20": False, "noflat": True, "respect": True, "chipev": False, "chipsteal": True,
            "calib": False, "plo": False}
# plo_strength at these shares of random 4-card hands, from 20,000 samples
PLO_TOP = {0.05: 0.682, 0.15: 0.500, 0.22: 0.427, 0.25: 0.405, 0.40: 0.295}
CALIB_SAMPLES = 400
_OFFSETS: dict[tuple, dict[int, float]] = {}


def strength_offsets(var) -> dict[int, float]:
    """{board size: this variant's mean postflop strength of random hands minus standard hold'em's},
    computed once per variant and process from fixed seeds. Empty for 52-card decks."""
    key = (var.ranks, var.board_count, len(var.deck), var.hole_count)
    if key not in _OFFSETS:
        if len(var.deck) == 52 or var.family != "holdem":
            _OFFSETS[key] = {}
        else:
            def means(v) -> dict[int, float]:
                rng = random.Random(20261103)
                out = {}
                for nb in range(3, max(5, var.board_count) + 1):
                    if nb > v.board_count:
                        break
                    tot = 0.0
                    for _ in range(CALIB_SAMPLES):
                        cards = rng.sample(v.deck, 2 + nb)
                        tot += features(v, cards[:2], cards[2:])[0]
                    out[nb] = tot / CALIB_SAMPLES
                return out
            mine, std = means(var), means(Variant(None))
            _OFFSETS[key] = {nb: m - std[nb] for nb, m in mine.items() if nb in std}
    return _OFFSETS[key]


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
        self.offsets = strength_offsets(self.var) if self.on["calib"] else {}

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
        # The preflop lessons price hands with two-card equity tables, so they apply only when two hole
        # cards are dealt: with crazy pineapple's three they cost 4.0 +/- 1.4 points per table.
        two = len(sp.hole) == 2
        if self.on["resteal"] and two and self.single_open(sp) and 8 <= sp.eff_bb <= 30 and \
                (self.chip_resteal_gains(sp) if self.on["chipsteal"] else self.resteal_gains(sp)):
            return act_allin(sp)
        if sp.eff_bb <= self.short_bb:
            return self.short_preflop(sp)
        if self.on["shove20"] and two and sp.raises == 0 and sp.to_call > 0 and sp.eff_bb <= 20 and len(sp.behind) <= 3:
            return act_allin(sp) if self.push_gains(sp) else act_fold(sp)
        a = self.preflop(sp)
        if self.on["noflat"] and two and a.get("action") == "call" and sp.role != "other" and self.single_open(sp) \
                and sp.eff_bb <= 30 and not (sp.role == "BB" and self.var.pre.pct[self.var.pre.best_cls(sp.hole)] <= 0.40):
            return act_fold(sp)
        return a

    def single_open(self, sp: Spot) -> bool:
        """One raise, nobody called it, hero hasn't acted voluntarily (posting a blind or
        ante isn't acting), and the opener has chips behind."""
        v = sp.raiser
        return (sp.raises == 1 and sp.callers == 0 and v >= 0 and v != sp.me and sp.stacks[v] > 0
                and not any(h[0] == 0 and h[1] == sp.me and h[2] in VOLUNTARY for h in sp.hist))

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

    def omaha(self, sp: Spot) -> dict:
        if not self.on["plo"]:
            return super().omaha(sp)
        if sp.street == 0:
            q = plo_strength(sp.hole) if len(sp.hole) >= 4 else 1.0 - preflop_pct(self.var, sp.hole)
            k = len(sp.behind)
            if sp.eff_bb <= 12:
                if sp.raises == 0 and q >= (0.33 if k <= 2 else 0.43):
                    return act_allin(sp)
                if sp.raises and q >= 0.55:
                    return act_allin(sp)
                return act_fold(sp)
            if sp.raises == 0:
                if sp.to_call == 0:
                    return act_pot(sp, 1.0) if q >= PLO_TOP[0.15] else act_fold(sp)
                if q >= (PLO_TOP[0.40] if k <= 2 else PLO_TOP[0.22] if k <= 4 else PLO_TOP[0.15]):
                    return act_raise(sp, (3 + sp.callers) * sp.bb)
                if sp.role == "SB" and q >= PLO_TOP[0.40]:
                    return act_call(sp)
                return act_fold(sp)
            if sp.raises == 1:
                if q >= PLO_TOP[0.05]:
                    return act_pot(sp, 1.0)
                late_steal = sp.role == "BB" and sp.position_of(sp.raiser) <= 2
                if q >= (PLO_TOP[0.25] if late_steal else PLO_TOP[0.15]) and sp.to_call <= 0.15 * sp.stack:
                    return act_call(sp)
                return act_fold(sp)
            if q >= 0.8:
                return act_pot(sp, 1.0)
            if q >= PLO_TOP[0.05] and sp.to_call <= 0.25 * sp.stack:
                return act_call(sp)
            return act_fold(sp)
        s, outs, wet, _ = cat_strength(self.var, sp.hole, sp.board)
        need = sp.to_call / max(1, sp.pot + sp.to_call)
        if sp.to_call == 0:
            if s >= 0.66:
                return act_pot(sp, 0.7)
            if sp.last_aggr == sp.me and sp.n_opp == 1 and len(sp.board) == 3 and self.rng.random() < 0.85:
                return act_pot(sp, 0.5)
            return act_fold(sp)
        if s >= 0.88:
            return act_pot(sp, 1.0)
        if s >= 0.70 or (s >= 0.40 and need <= 0.25) or self.draw_ok(sp, outs, need):
            return act_call(sp)
        return act_fold(sp)

    def chip_resteal_gains(self, sp: Spot) -> bool:
        """resteal priced in chips the way event 2's winner did it: callers in turn (players
        behind, then the opener), each calling with probability p and the top p of hands."""
        r = self.reads
        v = sp.raiser
        behind = [s for s in sp.behind if s != v]
        if r.loose(v) > 0.30 or any(r.loose(s) > 0.30 for s in behind):
            return False
        pre = self.var.pre
        c = pre.best_cls(sp.hole)
        hero_total = sp.stack + sp.bet
        callers = [(j, 0.7 * self.call_width(sp, j, 1, min(hero_total, sp.stacks[j] + sp.bets[j]) / sp.bb))
                   for j in behind]
        callers.append((v, max(0.04, min(0.5, 0.45 * self.villain_range(sp, v)))))
        ev, reach = 0.0, 1.0
        for j, p in callers:
            eff = min(hero_total, sp.stacks[j] + sp.bets[j])
            risk, win = eff - sp.bet, sp.pot + eff - sp.bets[j]
            eq = pre.top(c, p)
            ev += reach * p * (eq * win - (1 - eq) * risk)
            reach *= 1 - p
        ev += reach * sp.pot
        return ev > 0 and (pre.pct[c] <= 0.10 or ev > 0.1 * sp.pot)

    def postflop(self, sp: Spot) -> dict:
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        s -= self.offsets.get(len(sp.board), 0.0)
        if self.on["respect"] and sp.to_call > 0 and cat <= PAIR and s < 0.9 and outs < 8:
            big = len(sp.board) >= 4 and sp.to_call >= 0.7 * max(1.0, sp.pot - sp.to_call)
            if sp.raises >= 2 or big:
                return act_fold(sp)
        return self.tag_postflop(sp, s, outs, wet)

    def tag_postflop(self, sp: Spot, s: float, outs: int, wet: bool) -> dict:
        """TagCore.postflop with the strength passed in (so calib can shift it)."""
        if sp.n_opp > 1 and s < 0.85:
            s -= 0.05 * (sp.n_opp - 1)
        rng = self.rng
        flop = len(sp.board) == 3
        stations = any(self.reads.vpip_rate(o) > 0.45 for o in sp.opps)
        if sp.to_call == 0:
            if s >= (0.62 if sp.last_street else 0.58) - (0.05 if stations else 0.0):
                return act_pot(sp, 0.8 if stations else 0.75 if wet else 0.6)
            if sp.last_aggr == sp.me and not sp.last_street:
                if flop and sp.n_opp <= 2 and (s >= 0.3 or outs >= 4 or not stations) \
                        and rng.random() < (0.45 if wet else 0.65) / sp.n_opp:
                    return act_pot(sp, 0.5 if wet else 0.4)
                if not flop and sp.n_opp == 1 and (s >= 0.5 or outs >= 8) and rng.random() < 0.5:
                    return act_pot(sp, 0.6)
            if outs >= 8 and not sp.last_street and rng.random() < 0.35:
                return act_pot(sp, 0.55)
            return act_fold(sp)
        need = sp.to_call / (sp.pot + sp.to_call)
        if self.aggressive(sp.raiser):
            s += 0.08
        raised = sp.raises >= 2 or any(h[0] == sp.street and h[1] == sp.me and h[2] == "raise" for h in sp.hist)
        if s >= 0.9 or (s >= 0.8 and not raised):
            return act_pot(sp, 0.9)
        required = 0.12 + 1.35 * need + (0.12 if raised else 0.0)
        if sp.to_call >= 0.5 * sp.stack:
            required += 0.05 * max(0, sp.n_alive - 2) / 6
        if s >= required or self.draw_ok(sp, outs, need):
            return act_call(sp)
        return act_fold(sp)
