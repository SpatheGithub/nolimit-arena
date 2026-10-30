"""Shared helpers for the house bots: cards, hand values, variant rules,
preflop tables and push/fold charts, ICM, the parsed decision ("Spot"), safe
actions, postflop features, in-table reads and the tight-aggressive core.

The source is arena/house_bots/_common.py plus its data file _common.json.
Every bot package that uses them carries identical copies, refreshed with
``python -m arena.house_bots.sync``. Standard library and numpy only; nothing
at module level is written after import.
"""

from __future__ import annotations

import json
import os
import random
from bisect import bisect_right
from itertools import combinations

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)
CATEGORIES = ("high_card", "pair", "two_pair", "trips", "straight",
              "flush", "full_house", "quads", "straight_flush")
HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)
ROLES = ("other", "SB", "BB")


def _top_ranks(k: int) -> tuple[int, ...]:
    """Rank mask -> its k highest ranks packed 4 bits each, highest first."""
    out = [0] * 8192
    for m in range(8192):
        v = n = 0
        x = m
        while x and n < k:
            r = x.bit_length() - 1
            v = v << 4 | r
            x ^= 1 << r
            n += 1
        out[m] = v << 4 * (k - n)
    return tuple(out)


TOP1, TOP2, TOP3, TOP5 = _top_ranks(1), _top_ranks(2), _top_ranks(3), _top_ranks(5)


def _straight_tops(ranks: str, ace_low: bool) -> tuple[int, ...]:
    """Rank mask -> top rank of the best straight it contains, or -1."""
    dr = sorted(RANKS.index(r) for r in ranks)
    tops: dict[int, int] = {}
    for i in range(len(dr) - 4):
        tops[sum(1 << r for r in dr[i:i + 5])] = dr[i + 4]
    if ace_low and 12 in dr and len(dr) >= 5 and 12 not in dr[:4]:
        tops.setdefault((1 << 12) | sum(1 << r for r in dr[:4]), dr[3])
    ordered = sorted(tops.items(), key=lambda t: -t[1])
    out = [-1] * 8192
    for m in range(8192):
        for sm, t in ordered:
            if m & sm == sm:
                out[m] = t
                break
    return tuple(out)


_STRAIGHTS = {(r, True): _straight_tops(r, True) for r in (RANKS, "6789TJQKA", "TJQKA")}


class Ranker:
    """Best-hand values for one deck and ranking, equal to the engine's:
    ``strength << 20 | tiebreak ranks``, higher wins. Fewer than five cards
    give the best partial hand (pairs, trips, high cards)."""

    def __init__(self, ranks: str = RANKS, ranking: dict | None = None):
        ranking = ranking or {}
        order = list(ranking.get("order") or CATEGORIES)
        ace_low = bool(ranking.get("ace_low", True))
        self.shift = [order.index(c) << 20 for c in CATEGORIES]
        self.cat_of = [CATEGORIES.index(c) for c in order]
        self.stop = _STRAIGHTS.get((ranks, ace_low)) or _straight_tops(ranks, ace_low)

    def value(self, cards) -> int:
        m1 = m2 = m3 = m4 = 0
        sm = [0, 0, 0, 0]
        for c in cards:
            b = 1 << (c >> 2)
            sm[c & 3] |= b
            if m1 & b:
                if m2 & b:
                    if m3 & b:
                        m4 |= b
                    else:
                        m3 |= b
                else:
                    m2 |= b
            else:
                m1 |= b
        s = self.shift
        stop = self.stop
        best = s[0] | TOP5[m1]
        if m2:
            if m4:
                q = m4.bit_length() - 1
                v = s[7] | q << 16 | TOP1[m1 & ~(1 << q)] << 12
                if v > best:
                    best = v
            if m3:
                t = m3.bit_length() - 1
                rest = m2 & ~(1 << t)
                if rest:
                    v = s[6] | t << 16 | (rest.bit_length() - 1) << 12
                    if v > best:
                        best = v
                v = s[3] | t << 16 | TOP2[m1 & ~(1 << t)] << 8
                if v > best:
                    best = v
            p = m2.bit_length() - 1
            rest = m2 & ~(1 << p)
            if rest:
                p2 = rest.bit_length() - 1
                v = s[2] | p << 16 | p2 << 12 | TOP1[m1 & ~(1 << p | 1 << p2)] << 8
                if v > best:
                    best = v
            v = s[1] | p << 16 | TOP3[m1 & ~(1 << p)] << 4
            if v > best:
                best = v
        t = stop[m1]
        if t >= 0:
            v = s[4] | t << 16
            if v > best:
                best = v
        for f in sm:
            if f.bit_count() >= 5:
                t = stop[f]
                v = s[8] | t << 16 if t >= 0 else s[5] | TOP5[f]
                if v > best:
                    best = v
        return best

    def category(self, value: int) -> int:
        return self.cat_of[value >> 20]


class Variant:
    """What the bots need from config["variant"]: deck, card counts, card-use
    rule, betting structure, ranking, and the family that picks a strategy
    ("holdem": two hole cards at showdown, best five of any; "omaha": the rest)."""

    def __init__(self, vd: dict | None):
        vd = vd or {}
        streets = vd.get("streets") or [{"hole": 2}, {"board": 3}, {"board": 1}, {"board": 1}]
        self.ranks = str(vd.get("ranks", RANKS))
        suits = str(vd.get("suits", SUITS))
        self.deck = [c for c in range(52) if NAME[c][0] in self.ranks and NAME[c][1] in suits]
        self.rank_ids = sorted({c >> 2 for c in self.deck})
        held = sum(s.get("hole", 0) - s.get("discard", 0) for s in streets)
        self.hole_count = held
        self.board_count = sum(s.get("board", 0) for s in streets)
        cu = vd.get("card_use") or {}
        self.use_lo = int(cu.get("hole_min", 0))
        self.use_hi = int(cu.get("hole_max", 5))
        self.limit = (vd.get("betting") or {}).get("structure") == "fixed_limit"
        self.ranker = Ranker(self.ranks, vd.get("ranking"))
        self.family = "holdem" if held == 2 and self.use_lo == 0 and self.use_hi >= 2 else "omaha"
        key = {RANKS: "std", "6789TJQKA": "short", "TJQKA": "royal"}.get(self.ranks)
        self.deck_key = key
        self.pre = PREFLOP.get(key or "std") if self.family == "holdem" else None

    def best(self, hole, board) -> int:
        """Best value under the card-use rule (a partial hand before five cards are possible)."""
        nh, nb = len(hole), len(board)
        need_lo, need_hi = max(0, 5 - nb), min(5, nh)
        lo, hi = max(self.use_lo, need_lo), min(self.use_hi, need_hi)
        value = self.ranker.value
        if lo > hi:
            return value(list(hole)[:max(0, min(self.use_hi, nh))] + list(board))
        if lo == need_lo and hi == need_hi:
            return value(list(hole) + list(board))
        best = -1
        for k in range(lo, hi + 1):
            boards = list(combinations(board, 5 - k))
            for hs in combinations(hole, k):
                for bs in boards:
                    v = value(hs + bs)
                    if v > best:
                        best = v
        return best


class PreflopTable:
    """Preflop data for one deck (see _common.json): class index, percentile,
    equity vs a top-x% range and vs k random hands, push/fold charts."""

    def __init__(self, d: dict, grid: list[float]):
        self.ranks = d["ranks"]
        n = self.n = len(self.ranks)
        self.pos = [-1] * 13
        for i, r in enumerate(self.ranks):
            self.pos[RANKS.index(r)] = i
        self.grid = tuple(grid)
        self.pct = tuple(x / 1e4 for x in d["pct"])
        self.eq_top = tuple(tuple(x / 1e4 for x in row) for row in d["eq_top"])
        self.eq_multi = tuple(tuple(x / 1e4 for x in row) for row in d["eq_multi"])
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

    def cls(self, c1: int, c2: int) -> int:
        a, b = self.pos[c1 >> 2], self.pos[c2 >> 2]
        n = self.n
        if a == b:
            return a * n + a
        hi, lo = (a, b) if a > b else (b, a)
        return hi * n + lo if (c1 & 3) == (c2 & 3) else lo * n + hi

    def best_cls(self, hole) -> int:
        if len(hole) == 2:
            return self.cls(hole[0], hole[1])
        pct = self.pct
        return min((self.cls(a, b) for a, b in combinations(hole, 2)), key=pct.__getitem__)

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

    def multi(self, c: int, k: int) -> float:
        row = self.eq_multi[c]
        return row[min(max(k, 1), len(row)) - 1]

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


def _load_tables() -> dict[str, PreflopTable]:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_common.json")) as f:
        data = json.load(f)
    return {k: PreflopTable(d, data["grid"]) for k, d in data["decks"].items()}


PREFLOP = _load_tables()


def chen(c1: int, c2: int) -> float:
    """Bill Chen's preflop score for two cards."""
    hi, lo = max(c1 >> 2, c2 >> 2), min(c1 >> 2, c2 >> 2)
    top = {12: 10.0, 11: 8.0, 10: 7.0, 9: 6.0}.get(hi, (hi + 2) / 2)
    if hi == lo:
        return max(5.0, top * 2)
    score = top + (2.0 if (c1 & 3) == (c2 & 3) else 0.0)
    gap = hi - lo - 1
    score -= (0, 1, 2, 4)[gap] if gap < 4 else 5
    if gap <= 1 and hi < 10:
        score += 1
    return float(int(score + 0.5 + 1e-9)) if score > 0 else score


def best_chen(hole) -> float:
    return max((chen(a, b) for a, b in combinations(hole, 2)), default=0.0)


def plo_strength(hole) -> float:
    """Rough 0..1 preflop strength for Omaha-style hands (higher is better)."""
    counts: dict[int, int] = {}
    suits = [0, 0, 0, 0]
    high = [-1, -1, -1, -1]
    for c in hole:
        r, s = c >> 2, c & 3
        counts[r] = counts.get(r, 0) + 1
        suits[s] += 1
        high[s] = max(high[s], r)
    score = 0.0
    for r, n in counts.items():
        score += (4 + r * 0.5) if n == 2 else (1 + r * 0.15) if n > 2 else 0.0
    for s in range(4):
        if suits[s] == 2:
            score += 2.0 + (1.5 if high[s] == 12 else 0.5 if high[s] >= 10 else 0.0)
        elif suits[s] == 3:
            score += 1.0
    distinct = sorted(counts, reverse=True)
    if len(distinct) >= 3:
        span = distinct[0] - distinct[-1]
        if len(distinct) >= 4:
            score += 7 if span <= 3 else 5 if span <= 4 else 3 if span <= 5 else 0
        else:
            score += 2 if span <= 3 else 0
    score += 0.35 * sum(max(0, (c >> 2) - 7) for c in hole)
    return min(1.0, score / 22.0)


def preflop_pct(var: Variant, hole) -> float:
    """Approximate percentile of the hand among starting hands (0 = best)."""
    if var.pre is not None:
        return var.pre.pct[var.pre.best_cls(hole)]
    if len(hole) >= 4:
        return 1.0 - plo_strength(hole)
    score = best_chen(hole)
    return max(0.01, min(0.95, 0.85 - 0.075 * score))


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


# The decision

class Spot:
    """One decision, parsed from obs."""

    __slots__ = ("obs", "var", "me", "hole", "board", "street", "can_check", "can_raise", "to_call",
                 "min_to", "max_to", "pot", "bb", "stack", "bet", "stacks", "bets", "opps", "n_opp",
                 "n_alive", "eff", "eff_bb", "raises", "raiser", "callers", "last_aggr", "order",
                 "behind", "ip", "role", "last_street", "hist")

    def __init__(self, obs: dict, var: Variant):
        self.obs = obs
        self.var = var
        me = self.me = obs["seat"]
        self.hole = [CARD[c] for c in obs["hole"]]
        self.board = [CARD[c] for c in obs["board"]]
        st = self.street = obs["street_index"]
        legal = obs["legal"]
        self.can_check = "check" in legal
        self.can_raise = ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0
        self.to_call = obs["to_call"]
        self.min_to = obs["min_raise_to"]
        self.max_to = obs["max_raise_to"]
        self.pot = obs["pot"]
        self.bb = obs["bb"] or 1
        stacks = self.stacks = obs["stacks"]
        bets = self.bets = obs["bets"]
        self.stack = stacks[me]
        self.bet = bets[me]
        in_hand = obs["in_hand"]
        opps = self.opps = [s for s in in_hand if s != me]
        self.n_opp = len(opps)
        alive = obs["alive"]
        n = self.n_alive = len(alive)
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        self.eff = min(self.stack + self.bet, other)
        self.eff_bb = self.eff / self.bb
        hist = self.hist = obs["history"]
        raises = callers = 0
        raiser = last_aggr = -1
        for h_st, seat, act, _ in hist:
            if act == "raise":
                if h_st == st:
                    raises += 1
                    raiser = seat
                    callers = 0
                elif h_st < st:
                    last_aggr = seat
            elif act == "call" and h_st == st:
                callers += 1
        self.raises, self.raiser, self.callers, self.last_aggr = raises, raiser, callers, last_aggr
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        if st == 0:
            if n == 2:
                order = [alive[bi], alive[1 - bi]]
            else:
                bbs = obs["bb_seat"]
                j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
                order = alive[j:] + alive[:j]
        else:
            order = alive[bi + 1:] + alive[:bi + 1]
        self.order = order
        i = order.index(me) if me in order else 0
        self.behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in in_hand and (stacks[s] > 0 or s == me)]
        self.ip = bool(live) and live[-1] == me
        self.role = "BB" if me == obs["bb_seat"] else "SB" if me == obs["sb_seat"] else "other"
        self.last_street = len(self.board) >= var.board_count

    def position_of(self, seat: int) -> int:
        """Players behind ``seat`` in this street's order (all alive seats)."""
        order = self.order
        return len(order) - 1 - order.index(seat) if seat in order else 3


# Safe actions: every return value is legal for the decision it was built from.

def act_fold(sp: Spot) -> dict:
    return {"action": "check"} if sp.can_check else {"action": "fold"}


def act_call(sp: Spot) -> dict:
    return {"action": "check"} if sp.to_call == 0 else {"action": "call"}


def act_raise(sp: Spot, amount: float) -> dict:
    if not sp.can_raise:
        return act_call(sp)
    a = int(amount)
    return {"action": "raise", "amount": sp.min_to if a < sp.min_to else sp.max_to if a > sp.max_to else a}


def act_allin(sp: Spot) -> dict:
    return act_raise(sp, sp.max_to) if sp.can_raise else act_call(sp)


def act_pot(sp: Spot, frac: float) -> dict:
    """Bet or raise by ``frac`` of the pot after calling; shove when little would be left."""
    target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
    if sp.stack + sp.bet - target < 0.25 * (sp.pot + 2 * (target - sp.bet)):
        target = sp.max_to
    return act_raise(sp, target)


def safe_default(obs: dict) -> dict:
    """What the dealer would substitute; used when a bot's own logic fails."""
    if obs.get("phase") == "discard":
        return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
    return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}


class SafeAgent:
    """Base for the house bots: act() never raises. A failure in decide()
    returns the dealer's default and is counted in ``failures``."""

    def __init__(self, config: dict):
        self.failures = 0
        self.var = Variant(config.get("variant"))
        self.rng = random.Random(config.get("seed", 0))

    def act(self, obs: dict) -> dict:
        try:
            return self.decide(obs)
        except Exception:
            self.failures += 1
            return safe_default(obs)

    def decide(self, obs: dict) -> dict:
        return safe_default(obs)


def keep_score(var: Variant, kept: list[int], board: list[int]) -> tuple:
    if board:
        return (var.best(kept, board), -preflop_pct(var, kept) if len(kept) >= 2 else 0.0)
    if len(kept) == 2 and var.pre is not None:
        return (-var.pre.pct[var.pre.cls(kept[0], kept[1])],)
    ranks = [c >> 2 for c in kept]
    pairs = len(ranks) - len(set(ranks))
    suited = len(kept) - len({c & 3 for c in kept})
    return (pairs * 20 + suited * 3 + sum(ranks),)


def act_discard(obs: dict, var: Variant) -> dict:
    """Discard so that the best remaining hole cards are kept."""
    hole = obs["hole"]
    k = obs.get("n_discard") or 1
    keep = len(hole) - k
    if keep <= 0:
        return {"action": "discard", "cards": list(hole[:k])}
    cs = [CARD[c] for c in hole]
    board = [CARD[c] for c in obs.get("board") or []]
    best = max(combinations(range(len(cs)), keep), key=lambda ix: keep_score(var, [cs[i] for i in ix], board))
    return {"action": "discard", "cards": [hole[i] for i in range(len(hole)) if i not in best]}


# Postflop hand features

_DECK_SCALE = {"short": (1.0, 0.88, 0.93, 0.97, 1.0), "royal": (1.0, 0.6, 0.75, 0.85, 0.9)}


def draw_outs(var: Variant, hole: list[int], board: list[int], cat: int) -> int:
    if len(board) >= var.board_count or cat >= STRAIGHT:
        return 0
    hs = [0, 0, 0, 0]
    bs = [0, 0, 0, 0]
    for c in hole:
        hs[c & 3] += 1
    for c in board:
        bs[c & 3] += 1
    outs = 0
    for s in range(4):
        if hs[s] and hs[s] + bs[s] == 4:
            outs = 9 if hs[s] >= 2 else 7
    bm = 0
    for c in board:
        bm |= 1 << (c >> 2)
    hm = 0
    for c in hole:
        hm |= 1 << (c >> 2)
    stop = var.ranker.stop
    allm = bm | hm
    cur = stop[allm]
    ranks_out = 0
    for r in var.rank_ids:
        if allm >> r & 1:
            continue
        t = stop[allm | 1 << r]
        if t > cur and t > stop[bm | 1 << r]:
            ranks_out += 1
    outs += 4 * min(ranks_out, 2) - (1 if outs and ranks_out else 0)
    if cat == HIGH:
        top = max(c >> 2 for c in board)
        outs += 3 * sum(1 for c in hole if c >> 2 > top)
    return min(outs, 15)


def features(var: Variant, hole: list[int], board: list[int]) -> tuple[float, int, bool, int]:
    """(strength 0..1, draw outs, wet board, category) for a two-card hold'em hand on a board."""
    if not board:
        return 0.6 * (1.0 - preflop_pct(var, hole)), 0, False, HIGH
    rk = var.ranker
    v = var.best(hole, board)
    cat = rk.cat_of[v >> 20]
    bv = rk.value(board)
    bcat = rk.cat_of[bv >> 20]
    plays_board = len(board) >= 5 and v == bv
    h1, h2 = sorted((c >> 2 for c in hole), reverse=True)[:2]
    bm = 0
    bsuits = [0, 0, 0, 0]
    for c in board:
        bm |= 1 << (c >> 2)
        bsuits[c & 3] += 1
    brs = [r for r in range(12, -1, -1) if bm >> r & 1]
    top = brs[0]
    second = brs[1] if len(brs) > 1 else -1
    flushy = max(bsuits) >= 3
    paired = len(brs) < len(board)
    connected = any(((bm >> lo) & 0x1F).bit_count() >= 3 for lo in range(9))
    wet = flushy or (max(bsuits) == 2 and len(board) == 3) or connected

    def pair_strength(r: int, pocket: bool, kicker: int) -> float:
        if pocket:
            if r > top:
                return min(0.80, 0.70 + 0.02 * (r - 8))
            return 0.46 if r > second else 0.32
        if r == top:
            s = 0.66 if kicker == 12 else 0.63 if kicker == 11 else 0.60 if kicker >= 9 else 0.55
            return s - (0.04 if top <= 7 else 0.0)
        return 0.45 if r == second else 0.33

    if plays_board:
        s = 0.12
    elif cat == HIGH:
        s = 0.08 + 0.04 * sum(1 for r in (h1, h2) if r > top)
    elif cat == PAIR:
        if h1 == h2:
            s = pair_strength(h1, True, 0)
        elif bm >> h1 & 1:
            s = pair_strength(h1, False, h2)
        elif bm >> h2 & 1:
            s = pair_strength(h2, False, h1)
        else:
            s = 0.10 + 0.03 * sum(1 for r in (h1, h2) if r > top)
    elif cat == TWO_PAIR:
        hits = [r for r in {h1, h2} if bm >> r & 1]
        if h1 != h2 and len(hits) == 2:
            s = 0.82 if top in hits else 0.76
        elif h1 == h2:
            s = pair_strength(h1, True, 0) + 0.02
        elif hits:
            s = pair_strength(hits[0], False, h1 if hits[0] == h2 else h2) + 0.05
        else:
            s = 0.12 + (0.10 if h1 >= 11 else 0.0)
    elif cat == TRIPS:
        if h1 == h2 and bm >> h1 & 1:
            s = 0.90
        elif bcat == TRIPS:
            s = 0.15 + (0.15 if h1 == 12 else 0.0)
        else:
            s = 0.76 + (0.04 if max(h1, h2) >= 10 else 0.0)
        if flushy:
            s -= 0.10
    elif cat == STRAIGHT:
        s = 0.86 - (0.15 if flushy else 0.0) - (0.08 if paired else 0.0)
    elif cat == FLUSH:
        fs = max(range(4), key=bsuits.__getitem__)
        mine = [c >> 2 for c in hole if c & 3 == fs]
        hi_card = max(mine) if mine else -1
        missing = [r for r in range(12, -1, -1) if not any(c >> 2 == r and c & 3 == fs for c in board)]
        s = 0.96 if missing and hi_card == missing[0] else 0.88 if hi_card >= 10 else 0.82
        if bsuits[fs] >= 4 and hi_card < 10:
            s = 0.68
        if paired:
            s -= 0.10
    elif cat == FULL_HOUSE:
        s = 0.95 if bcat < TRIPS else 0.85
    else:
        s = 0.99
    if var.deck_key in _DECK_SCALE and HIGH < cat <= STRAIGHT:
        s *= _DECK_SCALE[var.deck_key][cat]
    outs = 0 if plays_board else draw_outs(var, hole, board, cat)
    return s, outs, wet, cat


_CAT_BASE = (0.05, 0.22, 0.42, 0.60, 0.74, 0.84, 0.92, 0.97, 0.99)


def cat_strength(var: Variant, hole: list[int], board: list[int]) -> tuple[float, int, bool, int]:
    """Category-based (strength, outs, wet, category) for any family."""
    if var.family == "holdem" and len(hole) == 2 or not board:
        return features(var, hole, board)
    rk = var.ranker
    cat = rk.cat_of[var.best(hole, board) >> 20]
    bsuits = [0, 0, 0, 0]
    bm = 0
    for c in board:
        bsuits[c & 3] += 1
        bm |= 1 << (c >> 2)
    flushy = max(bsuits) >= 3
    paired = bm.bit_count() < len(board)
    s = _CAT_BASE[cat]
    if flushy and TRIPS <= cat < FLUSH:
        s -= 0.15
    if paired and STRAIGHT <= cat <= FLUSH:
        s -= 0.12
    outs = 0
    if len(board) < var.board_count and cat < STRAIGHT:
        for su in range(4):
            mine = sum(1 for c in hole if c & 3 == su)
            if mine >= 2 and bsuits[su] == 2:
                outs = 9
    return s, outs, flushy or max(bsuits) == 2, cat


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
            if sp.behind and k <= 5:
                folds = min(self.reads.fold_rate(s) for s in sp.behind)
                width += max(0.0, folds - 0.5) * 0.8
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
