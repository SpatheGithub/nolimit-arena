"""Shared helpers for the house bots: cards, hand values, variant rules,
preflop tables, the parsed decision ("Spot"), safe actions and postflop
features.

The source is arena/house_bots/_common.py plus its data file _common.json.
Every bot package that uses them carries identical copies, refreshed with
``python -m arena.house_bots.sync``. Standard library only; nothing at module
level is written after import.
"""

from __future__ import annotations

import json
import os
import random
from itertools import combinations

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
    """Preflop data for one deck (see _common.json): class index, percentile
    and equity vs k random hands."""

    def __init__(self, d: dict):
        self.ranks = d["ranks"]
        self.n = len(self.ranks)
        self.pos = [-1] * 13
        for i, r in enumerate(self.ranks):
            self.pos[RANKS.index(r)] = i
        self.pct = tuple(x / 1e4 for x in d["pct"])
        self.eq_multi = tuple(tuple(x / 1e4 for x in row) for row in d["eq_multi"])

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

    def multi(self, c: int, k: int) -> float:
        row = self.eq_multi[c]
        return row[min(max(k, 1), len(row)) - 1]


def _load_tables() -> dict[str, PreflopTable]:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_common.json")) as f:
        data = json.load(f)
    return {k: PreflopTable(d) for k, d in data["decks"].items()}


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

    variant_cls = Variant

    def __init__(self, config: dict):
        self.failures = 0
        self.var = self.variant_cls(config.get("variant"))
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
