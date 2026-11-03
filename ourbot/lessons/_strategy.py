"""Strategy helpers for the house bots that stay out of builders' kits (tag,
icm_pushfold and chip_pushfold): push/fold charts and equity against ranges,
ICM, in-table reads and the tight-aggressive core.

The source is arena/house_bots/_strategy.py plus its data file
_strategy.json; it builds on _common. Every bot package that uses it carries
identical copies, refreshed with ``python -m arena.house_bots.sync``.
Standard library and numpy only; nothing at module level is written after
import. Builders' kits carry _common with the quick-build bots, so anything
the strong bots' play depends on belongs here, not in _common.
"""

from __future__ import annotations

import json
import os
from bisect import bisect_right

import numpy as np

from ._common import (ROLES, PreflopTable, SafeAgent, Spot, Variant, act_allin, act_call, act_discard,
                      act_fold, act_pot, act_raise, cat_strength, features, plo_strength, preflop_pct)


class Charts(PreflopTable):
    """A deck's PreflopTable plus equity vs a top-x% range and the chip-EV
    push/fold charts (see _strategy.json)."""

    def __init__(self, d: dict, grid: list[float]):
        super().__init__(d)
        n = self.n
        self.grid = tuple(grid)
        self.eq_top = tuple(tuple(x / 1e4 for x in row) for row in d["eq_top"])
        self.kmax = d["kmax"]
        self.push = tuple(tuple(row) for row in d["push"])
        self.call = tuple(tuple(tuple(row) for row in rows) for rows in d["call"])
        combos = [12] * (n * n)
        for hi in range(n):
            combos[hi * n + hi] = 6
            for lo in range(hi):
                combos[hi * n + lo] = 4
        total = sum(combos)
        self.push_frac = tuple(self._fracs(row, combos, total) for row in self.push)
        self.call_frac = tuple(tuple(self._fracs(row, combos, total) for row in rows) for rows in self.call)

    @staticmethod
    def _fracs(codes, combos: list[int], total: int) -> tuple[float, ...]:
        """Share of combos whose code reaches each half-big-blind step 0..41."""
        hist = [0] * 42
        for c, w in zip(codes, combos):
            hist[min(c, 41)] += w
        out = [0.0] * 42
        acc = 0
        for step in range(41, -1, -1):
            acc += hist[step]
            out[step] = acc / total
        return tuple(out)

    def top(self, c: int, x: float) -> float:
        """Equity of class c vs a random hand from the top x of combos."""
        g = self.grid
        row = self.eq_top[c]
        if x <= g[0]:
            return row[0]
        if x >= 1.0:
            return row[-1]
        i = bisect_right(g, x)
        t = (x - g[i - 1]) / (g[i] - g[i - 1])
        return row[i - 1] + t * (row[i] - row[i - 1])

    def push_ok(self, c: int, k: int, s: float) -> bool:
        code = self.push[min(max(k, 1), self.kmax) - 1][c]
        return code == 255 or 2 * s <= code

    def call_ok(self, c: int, k: int, role: str, s: float) -> bool:
        code = self.call[min(max(k, 1), self.kmax) - 1][ROLES.index(role)][c]
        return code == 255 or 2 * s <= code

    def push_range(self, k: int, s: float) -> float:
        return self.push_frac[min(max(k, 1), self.kmax) - 1][min(41, max(0, int(2 * s + 0.999)))]

    def call_range(self, k: int, role: str, s: float) -> float:
        rows = self.call_frac[min(max(k, 1), self.kmax) - 1]
        return rows[ROLES.index(role)][min(41, max(0, int(2 * s + 0.999)))]


def _load_charts() -> dict[str, Charts]:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "_common.json")) as f:
        base = json.load(f)["decks"]
    with open(os.path.join(here, "_strategy.json")) as f:
        data = json.load(f)
    return {k: Charts({**base[k], **d}, data["grid"]) for k, d in data["decks"].items()}


CHARTS = _load_charts()


class ChartVariant(Variant):
    """A Variant whose preflop table also has the charts."""

    def __init__(self, vd: dict | None):
        super().__init__(vd)
        if self.pre is not None:
            self.pre = CHARTS[self.deck_key or "std"]


# ICM (Malmuth-Harville)

def icm(stacks, payouts) -> list[float]:
    """Each player's expected payout; ``payouts`` are by place, 1st first."""
    n = len(stacks)
    st = [max(float(x), 1e-9) for x in stacks]
    full = 1 << n
    used = [0.0] * full
    for m in range(1, full):
        low = m & -m
        used[m] = used[m ^ low] + st[low.bit_length() - 1]
    total = used[full - 1]
    dp = [0.0] * full
    dp[0] = 1.0
    eq = [0.0] * n
    pay = list(payouts) + [0.0] * n
    for m in range(full - 1):
        d = dp[m]
        if not d:
            continue
        f = d / (total - used[m])
        k = m.bit_count()
        pk = pay[k]
        for j in range(n):
            b = 1 << j
            if not m & b:
                p = f * st[j]
                dp[m | b] += p
                eq[j] += p * pk
    return eq


def _icm_plan(k: int):
    masks = sorted(range(1 << k), key=lambda m: (m.bit_count(), m))
    bounds = [0]
    for L in range(k + 1):
        bounds.append(bounds[-1] + sum(1 for m in masks if m.bit_count() == L))
    pos = {m: i for i, m in enumerate(masks)}
    steps = []
    for L in range(k):
        pairs = []
        for m in masks[bounds[L]:bounds[L + 1]]:
            for j in range(k):
                if not m >> j & 1:
                    pairs.append((pos[m | 1 << j] - bounds[L + 1], pos[m] - bounds[L], j))
        pairs.sort()
        steps.append((np.array([p[1] for p in pairs]), np.array([p[2] for p in pairs]), L + 1))
    memb = np.array([[m >> j & 1 for m in masks] for j in range(k)], dtype=float)
    return memb, bounds, steps


_ICM_PLANS = {k: _icm_plan(k) for k in range(1, 8)}


def icm_hero(others, hero, payouts) -> np.ndarray:
    """Hero's ICM equity in each scenario. ``others``: (scenarios, k) stacks
    of the other players, ``hero``: (scenarios,) hero stacks; a zero stack
    finishes below every positive one."""
    X = np.maximum(np.asarray(others, dtype=float), 1e-9)
    h = np.maximum(np.asarray(hero, dtype=float), 1e-9)
    m, k = X.shape
    pay = list(payouts) + [0.0] * (k + 1)
    if k == 0:
        return np.full(m, float(pay[0]))
    if k not in _ICM_PLANS:
        return np.array([icm([hv, *row], pay)[0] for hv, row in zip(h, X)])
    memb, bounds, steps = _ICM_PLANS[k]
    rem = (X.sum(1) + h)[:, None] - X @ memb
    dp = np.ones((m, 1))
    eq = np.zeros(m)
    for L in range(k + 1):
        w = dp / rem[:, bounds[L]:bounds[L + 1]]
        if pay[L]:
            eq += pay[L] * w.sum(1)
        if L == k:
            break
        parent, player, fan = steps[L]
        dp = (w[:, parent] * X[:, player]).reshape(m, -1, fan).sum(2)
    return eq * h


# In-table reads

class Reads:
    """Per-seat preflop counts from hand_end events: hands, VPIP, PFR, folds to a raise."""

    def __init__(self, seats: int):
        self.hands = [0] * seats
        self.vpip = [0] * seats
        self.pfr = [0] * seats
        self.faced = [0] * seats
        self.folded = [0] * seats

    def update(self, event: dict) -> None:
        n = len(self.hands)
        dealt = [s for s in map(int, event.get("payoffs") or {}) if 0 <= s < n]
        v_seen: set[int] = set()
        r_seen: set[int] = set()
        responded: set[int] = set()
        raised = False
        for st, s, act, _ in event.get("history") or []:
            if st != 0 or s not in dealt:
                continue
            if raised and act in ("fold", "call", "raise") and s not in responded:
                responded.add(s)
                self.faced[s] += 1
                if act == "fold":
                    self.folded[s] += 1
            if act in ("call", "raise"):
                v_seen.add(s)
            if act == "raise":
                r_seen.add(s)
                raised = True
        for s in dealt:
            self.hands[s] += 1
        for s in v_seen:
            self.vpip[s] += 1
        for s in r_seen:
            self.pfr[s] += 1

    def raise_rate(self, seat: int, prior: float = 0.15, weight: float = 10.0) -> float:
        return (self.pfr[seat] + prior * weight) / (self.hands[seat] + weight)

    def vpip_rate(self, seat: int) -> float:
        return (self.vpip[seat] + 0.3 * 10) / (self.hands[seat] + 10)

    def fold_rate(self, seat: int) -> float:
        return (self.folded[seat] + 0.6 * 6) / (self.faced[seat] + 6)


# The tight-aggressive core (tag, and icm_pushfold's deep game)

OPEN = (0.0, 0.42, 0.32, 0.25, 0.20, 0.16, 0.14, 0.12)


class TagCore(SafeAgent):
    """Tight-aggressive play. Deep: position-aware opens, 3-bets with
    premiums, continuation bets, postflop by made hand and draws. At or below
    ``short_bb`` effective big blinds: push/fold, comparing final chip counts
    through values() with a survival premium(); icm_pushfold swaps both for
    ICM. Fixed-limit and Omaha-style variants use simpler versions."""

    short_bb = 15.0
    variant_cls = ChartVariant

    def __init__(self, config: dict):
        super().__init__(config)
        self.points = [float(p) for p in config.get("points") or []]
        self.reads = Reads(int(config.get("seats", 8)))

    def observe(self, event: dict) -> None:
        try:
            self.reads.update(event)
        except Exception:
            self.failures += 1

    def decide(self, obs: dict) -> dict:
        var = self.var
        if obs.get("phase") == "discard":
            return act_discard(obs, var)
        sp = Spot(obs, var)
        if var.family != "holdem":
            return self.omaha(sp)
        if var.limit:
            return self.limit_game(sp)
        if sp.street == 0:
            if sp.eff_bb <= self.short_bb:
                return self.short_preflop(sp)
            return self.preflop(sp)
        return self.postflop(sp)

    # ranges and estimates

    def villain_range(self, sp: Spot, seat: int) -> float:
        """Estimated width of ``seat``'s range for its last preflop raise."""
        if seat < 0:
            return 0.3
        r = self.reads
        k = sp.position_of(seat)
        prior = OPEN[min(max(k, 1), 7)] if sp.raises <= 1 else 0.06
        total = sp.stacks[seat] + sp.bets[seat]
        if sp.stacks[seat] == 0 or sp.bets[seat] >= 0.85 * total:
            s = min(total, sp.stack + sp.bet) / sp.bb
            prior = sp.var.pre.push_range(k, s) if s <= 20 else 0.08
        width = (r.pfr[seat] + prior * 10) / (r.hands[seat] + 10)
        if sp.raises >= 2:
            width *= 0.5
        return min(0.95, max(0.02, width))

    def aggressive(self, seat: int) -> bool:
        return seat >= 0 and self.reads.raise_rate(seat) > 0.35

    # all-in decisions: final chip counts per scenario, valued by values()

    def values(self, sp: Spot, rows: list[dict]) -> list[float]:
        """Hero's value of each final chip count {seat: chips}; chips here."""
        return [r[sp.me] for r in rows]

    def premium(self, sp: Spot) -> float:
        """Equity demanded beyond the chip price when hero can bust: a
        survival premium that shrinks as players bust."""
        return 0.10 * max(0, sp.n_alive - 2) / 6

    def fold_cost(self, sp: Spot) -> float:
        """Chips charged to folding for the blinds paid before the next spot."""
        return 0.0

    def showdown_rows(self, sp: Spot, base: dict, villain: int) -> tuple[dict, dict]:
        """Final chips when hero and ``villain`` get it all in: hero wins, hero loses."""
        me = sp.me
        hero_total = sp.stack + sp.bet
        vill_total = sp.stacks[villain] + sp.bets[villain]
        matched = min(hero_total, vill_total)
        pot = 2 * matched + sp.pot - sp.bet - sp.bets[villain]
        win, lose = dict(base), dict(base)
        win[me], win[villain] = hero_total - matched + pot, vill_total - matched
        lose[me], lose[villain] = hero_total - matched, vill_total - matched + pot
        return win, lose

    def call_width(self, sp: Spot, seat: int, k: int, s: float) -> float:
        """Share of hands ``seat`` calls a shove with: its calling chart, blended
        with its VPIP as the table goes on."""
        obs = sp.obs
        role = "BB" if seat == obs["bb_seat"] else "SB" if seat == obs["sb_seat"] else "other"
        r = self.reads
        w = (self.var.pre.call_range(k, role, s) * 10 + r.vpip[seat]) / (10 + r.hands[seat])
        return min(0.9, max(0.01, w))

    def push_gains(self, sp: Spot) -> bool:
        """Does shoving first in beat folding? Any player behind, or a limper,
        may call; at most one does."""
        pre = self.var.pre
        obs = sp.obs
        me = sp.me
        c = pre.best_cls(sp.hole)
        limpers = [s for st, s, a, _ in sp.hist if st == 0 and a == "call" and s != me and sp.stacks[s] > 0]
        callers = [s for s in sp.behind if s not in limpers] + limpers
        base = {s: sp.stacks[s] for s in obs["alive"]}
        fold, steal = dict(base), dict(base)
        fold[me] = max(0.0, base[me] - self.fold_cost(sp))
        taker = obs["bb_seat"] if obs["bb_seat"] != me else (callers[-1] if callers else me)
        if taker != me and taker in fold:
            fold[taker] += sp.pot
        steal[me] += sp.pot
        rows = [fold, steal]
        k = max(1, len(callers))
        blinds = (obs["sb"] + obs["bb"] + obs["ante"] * sp.n_alive) / sp.bb
        hero_total = sp.stack + sp.bet
        prem = self.premium(sp)
        odds = []
        for j in callers:
            s = min(hero_total, sp.stacks[j] + sp.bets[j]) / sp.bb * 1.5 / max(1.5, blinds)
            width = self.call_width(sp, j, k, s)
            odds.append((width, max(0.0, pre.top(c, width) - prem)))
            rows.extend(self.showdown_rows(sp, base, j))
        v = self.values(sp, rows)
        ev = 0.0
        nocall = 1.0
        for i, (width, eq) in enumerate(odds):
            ev += nocall * width * (eq * v[2 + 2 * i] + (1 - eq) * v[3 + 2 * i])
            nocall *= 1 - width
        return ev + nocall * v[1] > v[0]

    def call_allin(self, sp: Spot, eq: float, villain: int) -> bool:
        """Call, or shove over, a bet that commits the stack, when that beats folding."""
        me = sp.me
        base = {s: sp.stacks[s] for s in sp.obs["alive"]}
        if villain not in base:
            villain = max(sp.opps, key=sp.bets.__getitem__, default=-1)
            if villain not in base:
                return False
        fold = dict(base)
        fold[me] = max(0.0, base[me] - self.fold_cost(sp))
        fold[villain] += sp.pot
        win, lose = self.showdown_rows(sp, base, villain)
        extra = sum(1 for s in sp.opps if s != villain and sp.bets[s] > 0)
        eq = eq * 0.8 ** extra - self.premium(sp)
        v = self.values(sp, [fold, win, lose])
        return eq * v[1] + (1 - eq) * v[2] > v[0]

    # no-limit hold'em

    def short_preflop(self, sp: Spot) -> dict:
        pre = self.var.pre
        c = pre.best_cls(sp.hole)
        if sp.raises == 0:
            if sp.to_call == 0:
                return act_allin(sp) if pre.pct[c] <= 0.15 else act_fold(sp)
            return act_allin(sp) if self.push_gains(sp) else act_fold(sp)
        v = sp.raiser
        eq = pre.top(c, self.villain_range(sp, v))
        return act_allin(sp) if self.call_allin(sp, eq, v) else act_fold(sp)

    def preflop(self, sp: Spot) -> dict:
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
            width = 0.70 if sp.n_alive == 2 else OPEN[min(k, 7)]
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
                mult = 3.0 if sp.ip else 3.7
                return self.raise_or_shove(sp, cur * (mult + sp.callers))
            need = sp.to_call / (sp.pot + sp.to_call)
            realize = 0.92 if sp.ip else 0.80
            pocket = (sp.hole[0] >> 2) == (sp.hole[1] >> 2) if len(sp.hole) == 2 else False
            if p <= 0.30 and eq * realize >= need:
                return act_call(sp)
            if pocket and sp.eff >= 15 * sp.to_call:
                return act_call(sp)
            return act_fold(sp)
        if p <= 0.012 or (p <= 0.03 and self.aggressive(v)):
            return self.raise_or_shove(sp, 2.3 * cur)
        if p <= 0.04 and sp.to_call <= 0.25 * sp.stack:
            return act_call(sp)
        return act_fold(sp)

    def raise_or_shove(self, sp: Spot, target: float) -> dict:
        if target >= 0.4 * (sp.stack + sp.bet):
            return act_allin(sp)
        return act_raise(sp, target)

    def postflop(self, sp: Spot) -> dict:
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
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

    def draw_ok(self, sp: Spot, outs: int, need: float) -> bool:
        if not outs or sp.last_street:
            return False
        left = max(1, len(sp.var.deck) - len(sp.hole) - len(sp.board))
        eq = outs / left
        implied = 1.4 if sp.eff >= 5 * max(sp.to_call, 1) else 1.0
        return eq * implied >= need

    # fixed-limit hold'em

    def limit_game(self, sp: Spot) -> dict:
        if sp.street == 0:
            p = preflop_pct(self.var, sp.hole)
            k = len(sp.behind)
            if sp.raises == 0:
                if sp.to_call == 0:
                    return act_raise(sp, sp.max_to) if p <= 0.14 else act_fold(sp)
                if p <= (0.70 if sp.n_alive == 2 else OPEN[min(k, 7)] + 0.04):
                    return act_raise(sp, sp.max_to)
                if sp.role == "SB" and p <= 0.5:
                    return act_call(sp)
                return act_fold(sp)
            if sp.raises == 1:
                if p <= 0.05:
                    return act_raise(sp, sp.max_to)
                if p <= 0.18 or (sp.role == "BB" and p <= 0.40):
                    return act_call(sp)
                return act_fold(sp)
            if p <= 0.02:
                return act_raise(sp, sp.max_to)
            return act_call(sp) if p <= 0.07 else act_fold(sp)
        s, outs, _, _ = features(self.var, sp.hole, sp.board)
        need = sp.to_call / max(1, sp.pot + sp.to_call)
        if sp.to_call == 0:
            if s >= 0.55 or outs >= 8 or (sp.last_aggr == sp.me and sp.n_opp <= 2 and self.rng.random() < 0.7):
                return act_raise(sp, sp.max_to)
            return act_fold(sp)
        if s >= 0.75:
            return act_raise(sp, sp.max_to)
        if s >= 0.40 or outs >= 8 or (outs >= 4 and need <= 0.2):
            return act_call(sp)
        if sp.last_street and s >= 0.3 and need <= 0.2:
            return act_call(sp)
        return act_fold(sp)

    # Omaha-style and other variants

    def omaha(self, sp: Spot) -> dict:
        if sp.street == 0:
            q = plo_strength(sp.hole) if len(sp.hole) >= 4 else 1.0 - preflop_pct(self.var, sp.hole)
            k = len(sp.behind)
            if sp.eff_bb <= 12:
                if sp.raises == 0 and q >= (0.40 if k <= 2 else 0.5):
                    return act_allin(sp)
                if sp.raises and q >= 0.6:
                    return act_allin(sp)
                return act_fold(sp)
            if sp.raises == 0:
                if sp.to_call == 0:
                    return act_pot(sp, 1.0) if q >= 0.75 else act_fold(sp)
                if q >= (0.45 if k <= 2 else 0.55 if k <= 4 else 0.62):
                    return act_raise(sp, (3 + sp.callers) * sp.bb)
                if sp.role == "SB" and q >= 0.4:
                    return act_call(sp)
                return act_fold(sp)
            if sp.raises == 1:
                if q >= 0.8:
                    return act_pot(sp, 1.0)
                if q >= 0.55 and sp.to_call <= 0.15 * sp.stack:
                    return act_call(sp)
                return act_fold(sp)
            if q >= 0.88:
                return act_pot(sp, 1.0)
            if q >= 0.75 and sp.to_call <= 0.25 * sp.stack:
                return act_call(sp)
            return act_fold(sp)
        s, outs, wet, _ = cat_strength(self.var, sp.hole, sp.board)
        need = sp.to_call / max(1, sp.pot + sp.to_call)
        if sp.to_call == 0:
            if s >= 0.72:
                return act_pot(sp, 0.7)
            if sp.last_aggr == sp.me and sp.n_opp == 1 and len(sp.board) == 3 and self.rng.random() < 0.5:
                return act_pot(sp, 0.5)
            return act_fold(sp)
        if s >= 0.88:
            return act_pot(sp, 1.0)
        if s >= 0.70 or (s >= 0.40 and need <= 0.25) or self.draw_ok(sp, outs, need):
            return act_call(sp)
        return act_fold(sp)
