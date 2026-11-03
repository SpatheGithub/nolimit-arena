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
  are a little thinner. The lab measured -1.6 points per table: looser early
  play only added busts.
- plohu: heads-up Omaha. The house omaha() has no heads-up mode. Our bot reached
  heads-up on 13% of PLO tables but won 1.5% of those, because it folded the
  small blind about 75% of the time and called shoves with the top 9%. Heads-up:
  - Small blind: raise the top 70%, limp the next 20%; at 12 bb or less, shove
    the top 70%.
  - Big blind facing a raise: re-raise the top 15%, call the top 70%; call an
    all-in with the top 55%.
  - Postflop: bet more and call wider.

  The lab measured +0.41 +/- 0.15 points per table, with heads-up wins going
  from 2% to 10% of those reached. It's on.
- resteal3: let resteal (only) fire with three hole cards (crazy pineapple). It
  splits the -4.0 that resteal, shove20 and noflat cost together there
  before the two-card gate.
- eqpost: postflop by Monte Carlo equity (equity.py) against each opponent's
  range instead of the house strength scale, which was tuned on 52 cards and
  misjudged royal (every hand holds a pair) and crazy pineapple. A range is
  the top share of combos by preflop percentile (the raiser's PFR, a caller's
  VPIP, a checked big blind's everything), narrowed on each postflop bet,
  raise or call to the combos with the best made hands on the board. Bet for
  value at 60%+ equity heads-up, c-bet heads-up flops 65% of the time, call
  when equity covers the price, raise at 72%+ (80% on the last street), and
  price all-in calls through values() as before.
- eqdisc: discard (crazy pineapple) to keep the pair with the most equity
  against a 60% range, instead of the best made hand.
- eqplo: Omaha postflop by Monte Carlo equity (equity.OmahaEquity), with the
  same ranges and thresholds as eqpost. Opponents' hands come from a bank of
  random hands sorted by plo_strength. Preflop stays as before (plohu
  heads-up).
- eqbluff: with eqpost or eqplo, bluff the river heads-up with under 25%
  equity when checked to (35% of the time after betting the turn, else 15%),
  and bet flops and turns 1.5x as often once three or fewer players are left.
  The fields fold a lot: 57-83% to river bets in royal.
- hu: heads-up, read a single raise as the top 50% or wider. The house range
  for a raiser blends its full-table PFR, so heads-up opens looked tight and
  the bot folded too much. Royal-001's winner fixed the same leak (heads-up
  conversion from 48% to 57%).
- wide: open and call wider before the flop in small decks, where equities
  run close. Royal-001's winner opened 26% early to 62% from the small blind
  and saw 35% of flops to our 21%. Opening widths go x1.5 in royal and x1.2
  in short deck; calls of a single raise go up to the top 45% and 36% (from
  30%).

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
import time

import numpy as np

from . import equity
from ._common import (CARD, PAIR, Spot, Variant, act_allin, act_call, act_discard, act_fold, act_pot, act_raise,
                      cat_strength, features, plo_strength, preflop_pct)
from ._strategy import OPEN, Reads, TagCore, icm_hero

FUTURE_HANDS = 3
ICM_FROM = 4  # with chipev on, ICM applies only once this many players or fewer are left
VOLUNTARY = ("check", "call", "raise", "fold")  # history also holds the "sb", "bb" and ante posts
SWITCHES = ("resteal", "shove20", "noflat", "respect", "chipev", "chipsteal", "calib", "plo", "plohu", "resteal3",
            "eqpost", "eqdisc", "wide", "eqplo", "eqbluff", "hu")
DEFAULTS = {"resteal": True, "shove20": False, "noflat": True, "respect": True, "chipev": False, "chipsteal": True,
            "calib": False, "plo": False, "plohu": True, "resteal3": False, "eqpost": False, "eqdisc": False,
            "wide": False, "eqplo": False, "eqbluff": False, "hu": False}
WIDE = {"royal": (1.5, 0.45), "short": (1.2, 0.36)}  # (opening width multiplier, cap on calling a raise)
POSTS = ("fold", "check", "call", "raise", "discard", "return")  # any other history label is a blind or ante post
EQ_ROWS = 360  # hands evaluated per equity call (samples x (opponents + hero's pairs)); about 0.15 ms
# plo_strength at these shares of random 4-card hands (the top x), from 20,000 samples
PLO_TOP = {0.05: 0.682, 0.08: 0.618, 0.15: 0.500, 0.22: 0.427, 0.25: 0.405, 0.30: 0.361, 0.40: 0.295,
           0.55: 0.225, 0.70: 0.161, 0.90: 0.093}
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
        self.eq = equity.for_variant(self.var) if any(self.on[k] for k in ("eqpost", "eqdisc", "eqplo")) else None
        self.nrng = np.random.default_rng([int(config.get("seed", 0)) & 0xFFFFFFFF, 7])
        streets = (config.get("variant") or {}).get("streets") or [{"hole": 2}]
        self.dealt = sum(int(st.get("hole", 0)) for st in streets)

    # icm_pushfold's ICM game (arena/house_bots/icm_pushfold/agent.py)

    def villain_range(self, sp: Spot, seat: int) -> float:
        w = super().villain_range(sp, seat)
        return max(w, 0.5) if self.on["hu"] and sp.n_alive == 2 and sp.raises <= 1 else w

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
        self.t0 = time.thread_time_ns()
        var = self.var
        if obs.get("phase") == "discard":
            if self.on["eqdisc"] and isinstance(self.eq, equity.Equity):
                return self.eq_discard(obs)
            return act_discard(obs, var)
        sp = Spot(obs, var)
        if var.family != "holdem" or var.limit or sp.street > 0:
            return super().decide(obs)
        # The preflop lessons price hands with two-card equity tables, so they apply only when two hole
        # cards are dealt: with crazy pineapple's three they cost 4.0 +/- 1.4 points per table.
        two = len(sp.hole) == 2
        steal_ok = two or (self.on["resteal3"] and len(sp.hole) == 3)  # resteal3: test the re-steal alone with 3 cards
        if self.on["resteal"] and steal_ok and self.single_open(sp) and 8 <= sp.eff_bb <= 30 and \
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

    def preflop(self, sp: Spot) -> dict:
        w = WIDE.get(self.var.deck_key) if self.on["wide"] else None
        return super().preflop(sp) if w is None else self.wide_preflop(sp, *w)

    def wide_preflop(self, sp: Spot, mult: float, call_cap: float) -> dict:
        """TagCore.preflop with opening widths times ``mult`` and calls up to the top ``call_cap``."""
        pre = self.var.pre
        c = pre.best_cls(sp.hole)
        p = pre.pct[c]
        bb = sp.bb
        if sp.raises == 0:
            limpers = sp.callers
            if sp.to_call == 0:
                if p <= 0.10 + (0.04 if limpers <= 1 else 0.0):
                    return act_raise(sp, (3 + limpers) * bb)
                return act_fold(sp)
            k = len(sp.behind)
            width = 0.70 if sp.n_alive == 2 else min(0.85, OPEN[min(k, 7)] * mult)
            if sp.behind and k <= 3:
                folds = min(self.reads.fold_rate(s) for s in sp.behind)
                width += max(0.0, folds - 0.6) * 0.3
            if p <= width - 0.03 * limpers:
                size = (2.5 if k > 1 or sp.n_alive == 2 else 3.0) + limpers
                return self.raise_or_shove(sp, size * bb)
            return act_fold(sp)
        v = sp.raiser
        r = self.villain_range(sp, v)
        cur = sp.bet + sp.to_call
        total = sp.stack + sp.bet
        eq = pre.top(c, r)
        if sp.to_call >= 0.35 * sp.stack or cur >= 0.4 * total:
            return act_allin(sp) if self.call_allin(sp, eq, v) else act_fold(sp)
        if sp.raises == 1:
            if p <= max(0.03, min(0.07, 0.25 * r)):
                mult3 = 3.0 if sp.ip else 3.7
                return self.raise_or_shove(sp, cur * (mult3 + sp.callers))
            need = sp.to_call / (sp.pot + sp.to_call)
            realize = 0.92 if sp.ip else 0.80
            pocket = (sp.hole[0] >> 2) == (sp.hole[1] >> 2) if len(sp.hole) == 2 else False
            if p <= call_cap and eq * realize >= need:
                return act_call(sp)
            if pocket and sp.eff >= 15 * sp.to_call:
                return act_call(sp)
            return act_fold(sp)
        if p <= 0.012 or (p <= 0.03 and self.aggressive(v)):
            return self.raise_or_shove(sp, 2.3 * cur)
        if p <= 0.04 and sp.to_call <= 0.25 * sp.stack:
            return act_call(sp)
        return act_fold(sp)

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

    def omaha_hu(self, sp: Spot) -> dict:
        """Heads-up Omaha (plohu): equities run close heads-up, so play most hands."""
        if sp.street == 0:
            q = plo_strength(sp.hole) if len(sp.hole) >= 4 else 1.0 - preflop_pct(self.var, sp.hole)
            commit = sp.to_call >= 0.35 * sp.stack or (sp.raiser >= 0 and sp.stacks[sp.raiser] == 0)
            if sp.raises == 0:
                if sp.to_call == 0:
                    return act_pot(sp, 1.0) if q >= PLO_TOP[0.22] else act_fold(sp)
                if sp.eff_bb <= 12:
                    return act_allin(sp) if q >= PLO_TOP[0.70] else act_fold(sp)
                if q >= PLO_TOP[0.70]:
                    return act_raise(sp, 3 * sp.bb)
                return act_call(sp) if q >= PLO_TOP[0.90] else act_fold(sp)
            if commit:
                return act_call(sp) if q >= (PLO_TOP[0.55] if sp.raises == 1 else PLO_TOP[0.40]) else act_fold(sp)
            if sp.raises == 1:
                if q >= PLO_TOP[0.15]:
                    return act_pot(sp, 1.0)
                return act_call(sp) if q >= PLO_TOP[0.70] else act_fold(sp)
            if q >= PLO_TOP[0.08]:
                return act_pot(sp, 1.0)
            return act_call(sp) if q >= PLO_TOP[0.30] else act_fold(sp)
        s, outs, wet, _ = cat_strength(self.var, sp.hole, sp.board)
        need = sp.to_call / max(1, sp.pot + sp.to_call)
        if sp.to_call == 0:
            if s >= 0.55:
                return act_pot(sp, 0.7)
            if sp.last_aggr == sp.me and len(sp.board) == 3 and self.rng.random() < 0.8:
                return act_pot(sp, 0.5)
            return act_fold(sp)
        if s >= 0.85:
            return act_pot(sp, 1.0)
        if s >= 0.45 or (s >= 0.30 and need <= 0.30) or self.draw_ok(sp, outs, need):
            return act_call(sp)
        return act_fold(sp)

    def omaha(self, sp: Spot) -> dict:
        if self.on["eqplo"] and sp.street > 0 and isinstance(self.eq, equity.OmahaEquity):
            return self.eq_postflop(sp)
        if self.on["plohu"] and sp.n_alive == 2:
            return self.omaha_hu(sp)
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
        if self.on["eqpost"] and self.eq is not None:
            return self.eq_postflop(sp)
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

    # equity play (eqpost, eqplo, eqbluff, eqdisc)

    @staticmethod
    def actions(sp: Spot) -> dict[int, list[tuple[int, str, float, int]]]:
        """Each seat's voluntary actions this hand: (street, action, size, raises before it on the
        street). A bet or raise's size is its share of the pot it faced; 0 for calls and checks."""
        out: dict[int, list] = {}
        pot = cur = 0.0
        street, raises, put = 0, 0, {}
        for st, s, act, amt in sp.hist:
            if st != street:
                street, cur, raises, put = st, 0.0, 0, {}
            if act == "raise":
                mine = put.get(s, 0.0)
                size = (amt - cur) / max(1.0, pot + cur - mine)
                out.setdefault(s, []).append((st, act, size, raises))
                pot += amt - mine
                put[s] = cur = float(amt)
                raises += 1
            elif act == "call":
                pot += amt
                put[s] = put.get(s, 0.0) + amt
                out.setdefault(s, []).append((st, act, 0.0, raises))
            elif act == "check":
                out.setdefault(s, []).append((st, act, 0.0, raises))
            elif act == "return":
                pot -= amt
            elif act not in POSTS:
                pot += amt
                if act != "ante":
                    put[s] = put.get(s, 0.0) + amt
                    cur = max(cur, put[s])
        return out

    def opp_range(self, sp: Spot, j: int, acts: dict, dead: np.ndarray) -> np.ndarray:
        """Seat j's range: the top share of combos its preflop play implies, narrowed by its
        postflop bets, raises and calls to the best made hands on this board."""
        r = self.reads
        mine = acts.get(j, [])
        pre = [(a, n) for st, a, _, n in mine if st == 0]
        if any(a == "raise" for a, _ in pre):
            q = r.raise_rate(j, prior=0.18)
            if any(a == "raise" and n >= 1 for a, n in pre):
                q *= 0.4
        elif any(a == "call" and n >= 1 for a, n in pre):
            q = min(0.6, max(0.15, r.vpip_rate(j)))
        elif any(a == "call" for a, _ in pre):
            q = max(0.35, r.vpip_rate(j))
        else:
            q = 1.0
        if self.var.family == "holdem" and self.dealt > 2:
            q *= 0.6  # best two of three dealt cards
        keep = 1.0
        for st, a, size, n in mine:
            if st == 0:
                continue
            if a == "raise":
                keep *= 0.35 if n >= 1 else 0.6 if size <= 0.4 else 0.5 if size <= 0.8 else 0.4 if size <= 1.2 else 0.3
            elif a == "call":
                keep *= 0.8
        if self.aggressive(j):
            keep **= 0.6
        return self.eq.range_idx(max(0.03, q), dead, sp.board, keep=max(0.08, keep), rng=self.nrng,
                                 budget=2000 // max(1, sp.n_opp))  # (Omaha's narrowing work is per opponent)

    def eq_postflop(self, sp: Spot) -> dict:
        """Bet, call, raise or fold by equity against every opponent's range (eqpost, eqplo)."""
        acts = self.actions(sp)
        dead = self.eq.dead_mask(sp.hole + sp.board)
        ranges = [self.opp_range(sp, j, acts, dead) for j in sp.opps]
        e = self.eq.equity(sp.hole, sp.board, ranges, self.nrng, self.samples(len(ranges), len(sp.hole)))
        rng = self.rng
        first, last = sp.street == 1, sp.last_street
        # eqbluff: bluff more when few players are left, as royal-001's winner did (x1.5, capped)
        more = 1.5 if self.on["eqbluff"] and sp.n_alive <= 3 else 1.0
        if sp.to_call == 0:
            if e >= (0.60 if last else 0.62) + 0.07 * (sp.n_opp - 1):
                return act_pot(sp, 0.75 if e >= 0.8 else 0.6)
            if sp.last_aggr == sp.me and not last:
                if first and sp.n_opp == 1 and rng.random() < min(0.9, 0.65 * more):
                    return act_pot(sp, 0.5)
                if first and sp.n_opp == 2 and e >= 0.40 and rng.random() < 0.5:
                    return act_pot(sp, 0.5)
                if not first and sp.n_opp == 1 and e >= 0.45 and rng.random() < min(0.9, 0.5 * more):
                    return act_pot(sp, 0.6)
            if not last and sp.n_opp == 1 and e >= 0.40 and rng.random() < 0.25:
                return act_pot(sp, 0.55)
            if self.on["eqbluff"] and last and sp.n_opp == 1 and e < 0.25 and \
                    rng.random() < min(0.7, (0.35 if sp.last_aggr == sp.me else 0.15) * more):
                return act_pot(sp, 0.6)
            return act_fold(sp)
        if e >= (0.80 if last else 0.72) and sp.can_raise:
            return act_pot(sp, 0.9)
        v = sp.raiser
        if sp.to_call >= 0.4 * sp.stack or (v >= 0 and sp.stacks[v] == 0):
            base = sp.obs["alive"]
            if v not in base:
                v = max(sp.opps, key=sp.bets.__getitem__, default=-1)
            extra = sum(1 for s in sp.opps if s != v and sp.bets[s] > 0)
            return act_allin(sp) if v in base and self.call_allin(sp, min(1.0, e / 0.8 ** extra), v) else act_fold(sp)
        need = sp.to_call / (sp.pot + sp.to_call)
        realize = 1.0 if last else 0.95 if sp.ip else 0.88
        return act_call(sp) if e * realize >= need + 0.02 else act_fold(sp)

    def samples(self, opps: int, hole: int) -> int:
        """Monte Carlo samples for this equity call: fewer with more hands to evaluate per sample,
        and half as many when the decision has already used 0.25 ms."""
        if isinstance(self.eq, equity.OmahaEquity):
            n = max(30, min(70, 180 // (opps + 1)))
        else:
            n = max(40, min(150, EQ_ROWS // (opps + hole * (hole - 1) // 2)))
        return n // 2 if time.thread_time_ns() - self.t0 > 250_000 else n

    def eq_discard(self, obs: dict) -> dict:
        """Keep the two hole cards with the most equity against a 60% range."""
        hole = obs["hole"]
        k = obs.get("n_discard") or 1
        board = [CARD[c] for c in obs.get("board") or []]
        if len(hole) - k != 2 or not board:
            return act_discard(obs, self.var)
        cs = [CARD[c] for c in hole]
        opps = max(1, min(2, len(obs.get("in_hand") or ()) - 1))
        rg = self.eq.range_idx(0.6, self.eq.dead_mask(cs + board))
        (a, b), _ = max(self.eq.shares(cs, board, [rg] * opps, self.nrng, self.samples(opps, len(cs))),
                        key=lambda t: t[1])
        return {"action": "discard", "cards": [h for h, c in zip(hole, cs) if c not in (a, b)]}
