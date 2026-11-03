"""b08 crazy-pineapple bot: precomputed 3-card preflop equities, push/fold when short,
heuristic postflop equity with multiway/variant discounts, simple per-seat aggression reads."""

import os
import json
import random
from itertools import combinations
from time import perf_counter

from .common import (Variant, Spot, CARD, features, act_fold, act_call, act_raise, act_allin,
                     HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, safe_default)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _c(n, k):
    if n < k:
        return 0
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


C1 = [_c(n, 1) for n in range(53)]
C2 = [_c(n, 2) for n in range(53)]
C3 = [_c(n, 3) for n in range(53)]


def tri_index(cards):
    a, b, c = sorted(cards)
    return C3[c] + C2[b] + C1[a]


def _load():
    p = os.path.join(_HERE, "pre3.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        d = json.load(f)
    return d


PRE = _load()  # dict: eq -> [22100][7], pct -> [22100], rng -> optional [22100][nr]
if PRE is not None:
    EQ = PRE["eq"]
    PCT = PRE["pct"]
    RW = PRE.get("rw")  # range widths
    ER = PRE.get("er")  # equity vs top-r ranges
else:
    EQ = PCT = RW = ER = None

AGGR_STEP = 0.09
RERAISE_PEN = 0.16
PAIR_PEN = 0.10
PUSH_BASE = {1: 0.58, 2: 0.40, 3: 0.30, 4: 0.24, 5: 0.20, 6: 0.17, 7: 0.15}
OPEN_BASE = {1: 0.42, 2: 0.32, 3: 0.24, 4: 0.19, 5: 0.16, 6: 0.14, 7: 0.12}


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def icm_me(stacks, mi, pts):
    """Approximate expected points of player mi: Harville exact for places 1-4,
    uniform over the remaining places for the leftover probability."""
    n = len(stacks)
    s = stacks[mi]
    if s <= 0:
        return pts[n - 1] if n - 1 < len(pts) else 0.0
    S = float(sum(stacks))
    others = [x for i, x in enumerate(stacks) if i != mi and x > 0]
    n = len(others) + 1
    ev = pts[0] * s / S
    used = s / S
    if n >= 2:
        p2 = 0.0
        p3 = 0.0
        p4 = 0.0
        for j, a in enumerate(others):
            pa = a / S
            Sa = S - a
            p2 += pa * s / Sa
            if n >= 3:
                for k, b in enumerate(others):
                    if k == j:
                        continue
                    pb = pa * b / Sa
                    Sb = Sa - b
                    p3 += pb * s / Sb
                    if n >= 4:
                        for l, c in enumerate(others):
                            if l == j or l == k:
                                continue
                            p4 += pb * c / Sb * s / (Sb - c)
        ev += pts[1] * p2 + (pts[2] * p3 if n >= 3 else 0.0) + (pts[3] * p4 if n >= 4 else 0.0)
        used += p2 + p3 + p4
    if n > 4:
        rest = max(0.0, 1.0 - used)
        ev += rest * sum(pts[4:n]) / (n - 4)
    return ev


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        # per-seat reads: preflop opportunities, voluntary raises, all-ins
        self.n_seen = {}
        self.n_raise = {}
        self.n_vpip = {}
        self.pf_aggr_post = {}
        self.post_bets = {}
        self.post_acts = {}

    # ---------------------------------------------------------------- preflop strength
    def pct_of(self, hole):
        if PCT is not None and len(hole) == 3:
            return PCT[tri_index(hole)]
        pre = self.var.pre
        if pre is None:
            return 0.5
        best = min(pre.pct[pre.cls(a, b)] for a, b in combinations(hole, 2))
        return best * 0.75

    def eq_k(self, hole, k):
        k = clamp(k, 1, 7)
        if EQ is not None and len(hole) == 3:
            return EQ[tri_index(hole)][k - 1]
        pre = self.var.pre
        cls = min((pre.cls(a, b) for a, b in combinations(hole, 2)), key=pre.pct.__getitem__)
        return pre.multi(cls, k)

    def eq_vs_range(self, hole, pct, r):
        """Heads-up equity vs a top-r range."""
        r = clamp(r, 0.02, 1.0)
        if ER is not None and len(hole) == 3:
            row = ER[tri_index(hole)]
            rw = RW
            if r <= rw[0]:
                return row[0]
            for i in range(1, len(rw)):
                if r <= rw[i]:
                    t = (r - rw[i - 1]) / (rw[i] - rw[i - 1])
                    return row[i - 1] * (1 - t) + row[i] * t
            return row[-1]
        # crude fallback
        e1 = self.eq_k(hole, 1)
        return clamp(e1 - 0.30 * (1.0 - r) ** 1.5 + 0.0, 0.05, 0.95) if pct > r * 0.5 else clamp(e1 - 0.12 * (1 - r), 0.3, 0.95)

    # ---------------------------------------------------------------- reads
    def seat_aggr(self, s):
        n = self.n_seen.get(s, 0)
        r = self.n_raise.get(s, 0)
        return (r + 0.6) / (n + 3.0)  # prior ~0.2

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            raised = set()
            vpip = set()
            for st, seat, act, amt in hist:
                if st == 0 and act in ("fold", "call", "raise", "check"):
                    seen.add(seat)
                    if act == "raise":
                        raised.add(seat)
                    if act in ("call", "raise"):
                        vpip.add(seat)
                if st > 0 and act in ("raise", "call", "check", "fold"):
                    self.post_acts[seat] = self.post_acts.get(seat, 0) + 1
                    if act == "raise":
                        self.post_bets[seat] = self.post_bets.get(seat, 0) + 1
            for s in seen:
                self.n_seen[s] = self.n_seen.get(s, 0) + 1
            for s in raised:
                self.n_raise[s] = self.n_raise.get(s, 0) + 1
            for s in vpip:
                self.n_vpip[s] = self.n_vpip.get(s, 0) + 1
        except Exception:
            pass

    # ---------------------------------------------------------------- main
    def act(self, obs):
        try:
            if obs["phase"] == "discard":
                return self.discard(obs)
            sp = Spot(obs, self.var)
            if sp.street == 0:
                return self.preflop(sp, obs)
            return self.postflop(sp, obs)
        except Exception:
            return safe_default(obs)

    # ---------------------------------------------------------------- discard
    def keep_score(self, keep, board):
        s, outs, wet, cat = features(self.var, keep, board)
        left = 5 - len(board)
        return s + (1 - s) * min(0.6, outs * (0.04 if left == 2 else 0.021 if left == 1 else 0.0))

    def discard(self, obs):
        hole = obs["hole"]
        k = obs.get("n_discard") or 1
        cs = [CARD[c] for c in hole]
        board = [CARD[c] for c in obs.get("board") or []]
        keep_n = len(cs) - k
        best = None
        bs = -1e9
        for ix in combinations(range(len(cs)), keep_n):
            sc = self.keep_score([cs[i] for i in ix], board)
            if sc > bs:
                bs, best = sc, ix
        return {"action": "discard", "cards": [hole[i] for i in range(len(hole)) if i not in best]}

    # ---------------------------------------------------------------- preflop
    def preflop(self, sp, obs):
        bb = sp.bb
        hole = sp.hole
        pct = self.pct_of(hole)
        stack_total = sp.stack + sp.bet
        my_bb = stack_total / bb
        opps = sp.opps
        # effective stack vs others still in
        others = [sp.stacks[s] + sp.bets[s] for s in opps]
        eff = min(stack_total, max(others) if others else stack_total)
        eff_bb = eff / bb
        nb = len(sp.behind)
        n_alive = sp.n_alive
        max_bet = max(sp.bets)
        raises = sp.raises

        if raises == 0:
            # unopened (maybe limpers)
            limpers = sp.callers
            if eff_bb <= 13 or my_bb <= 13:
                if nb == 0:
                    # BB with only limpers / SB completes: check or shove strong
                    if pct <= 0.20 + 0.02 * (13 - eff_bb):
                        return act_allin(sp)
                    return act_call(sp) if sp.to_call == 0 else act_fold(sp)
                th = PUSH_BASE.get(nb, 0.14) * (10.0 / max(eff_bb, 1.5)) ** 0.75
                if limpers:
                    th *= 0.7
                th *= self.steal_mult(sp)
                if pct <= th:
                    return act_allin(sp)
                if sp.to_call == 0:
                    return act_call(sp)
                return act_fold(sp)
            # deeper: open-raise or fold
            th = OPEN_BASE.get(nb, 0.12) if nb > 0 else 0.30
            if limpers:
                th *= 0.75
            th *= self.steal_mult(sp)
            if pct <= th:
                size = (2.3 if eff_bb > 25 else 2.1) * bb + limpers * bb
                if nb == 1:  # SB vs BB
                    size = 3.0 * bb
                if nb == 0:
                    size = (3.5 + limpers) * bb
                if pct <= 0.03 and eff_bb <= 22:
                    return act_allin(sp)
                return act_raise(sp, size)
            if sp.to_call == 0:
                return act_call(sp)
            # SB complete with decent hands vs BB cheap
            if nb == 1 and pct <= 0.55 and sp.to_call <= 0.5 * bb and eff_bb > 13:
                return act_call(sp)
            return act_fold(sp)

        # facing a raise
        raiser = sp.raiser
        to_call = sp.to_call
        pot = sp.pot
        need = to_call / (pot + to_call)
        r_stack = sp.stacks[raiser] if raiser >= 0 else 0
        r_allin = raiser >= 0 and r_stack == 0
        r_total = sp.bets[raiser] if raiser >= 0 else max_bet
        r_bb = r_total / bb
        # estimate raiser range width
        aggr = self.seat_aggr(raiser) if raiser >= 0 else 0.2
        nbv = sp.position_of(raiser) if raiser >= 0 else 3
        nbv = clamp(nbv, 1, 7)
        if raises >= 2:
            base_r = 0.07
        elif r_allin or r_bb >= 8:
            # shove: a push range for their position and depth
            base_r = clamp(PUSH_BASE.get(nbv, 0.15) * (10.0 / max(r_bb, 1.5)) ** 0.75, 0.08, 0.9)
        else:
            base_r = clamp(OPEN_BASE.get(nbv, 0.15) * 1.1, 0.10, 0.5)
        r_w = clamp(base_r * (0.6 + 2.0 * aggr), 0.04, 0.9)
        # multiway: each additional caller tightens
        eq = self.eq_vs_range(hole, pct, r_w)
        callers = sp.callers
        if callers:
            eq *= 0.80 ** callers
        # all-in pressure / commitment
        commit = to_call >= 0.4 * stack_total
        risk = self.risk_premium(sp, to_call, commit)
        if (r_allin or commit) and raiser >= 0 and sp.n_alive > 2:
            ineed = self.icm_need(sp, obs, raiser)
            if ineed is not None:
                need = ineed
                risk = 0.01
        # premium: re-raise
        if pct <= 0.025 or (eq >= 0.62 and pct <= 0.06):
            if eff_bb <= 30 or raises >= 2 or commit:
                return act_allin(sp)
            return act_raise(sp, 3.0 * r_total + (callers * r_total))
        if not r_allin and not commit:
            eq *= 0.93 if sp.ip else 0.84  # equity realization when play continues postflop
        if eq >= need + risk:
            # short-stacked: shove instead of call when we would be committed anyway
            if my_bb <= 15 and not r_allin and eq >= 0.5:
                return act_allin(sp)
            return act_call(sp)
        # cheap calls in BB / limp-raise situations: implied odds with strong-ish hands
        if to_call <= 0.06 * stack_total and pct <= 0.30 and not commit and eff_bb >= 25:
            return act_call(sp)
        return act_fold(sp)

    def icm_need(self, sp, obs, v):
        """Equity needed (by points, ICM) to call the current bet from villain v."""
        me = sp.me
        stacks = sp.stacks
        bets = sp.bets
        pot = sp.pot
        call_amt = min(sp.to_call, stacks[me])
        excess = max(0, bets[v] - (bets[me] + stacks[me])) if v >= 0 else 0
        seats = [s for s in obs["alive"] if stacks[s] > 0 or s in (me, v) or s in sp.opps]
        n = len(seats)
        if n <= 1 or v < 0:
            return None
        pts = self.points

        def ev(my_st, v_st):
            st = []
            mi = 0
            for s in seats:
                if s == me:
                    mi = len(st)
                    st.append(my_st)
                elif s == v:
                    st.append(v_st)
                else:
                    st.append(stacks[s])
            if my_st <= 0:
                return pts[n - 1] if n - 1 < len(pts) else 0.0
            return icm_me(st, mi, pts)

        e_fold = ev(stacks[me], stacks[v] + pot)
        e_lose = ev(stacks[me] - call_amt, stacks[v] + pot + call_amt)
        e_win = ev(stacks[me] - call_amt + pot + call_amt - excess, stacks[v] + excess)
        if e_win <= e_lose + 1e-9:
            return 1.0
        return clamp((e_fold - e_lose) / (e_win - e_lose), 0.0, 1.0)

    def steal_mult(self, sp):
        """Widen steals when the players behind fold a lot (low aggression), tighten vs aggressive."""
        if not sp.behind:
            return 1.0
        a = sum(self.seat_aggr(s) for s in sp.behind) / len(sp.behind)
        return clamp(1.25 - 1.2 * (a - 0.2), 0.75, 1.35)

    def risk_premium(self, sp, to_call, commit):
        if not commit:
            return 0.0
        n = sp.n_alive
        if n <= 2:
            return 0.0
        # risking elimination: losers of chips lose more ICM than winners gain
        stacks = [s for s in sp.stacks]
        my = sp.stack + sp.bet
        avg = sum(sp.stacks[s] + sp.bets[s] for s in range(len(stacks))) / max(n, 1)
        prem = 0.03 if n >= 5 else 0.05
        if my < avg * 0.6:
            prem *= 0.5  # short: need to gamble anyway
        elif my > avg * 1.5:
            prem *= 0.7
        return prem

    # ---------------------------------------------------------------- postflop
    def hand_eq(self, sp):
        hole, board = sp.hole, sp.board
        left = 5 - len(board)
        best = None
        if len(hole) > 2:
            for keep in combinations(hole, 2):
                r = self._feat(list(keep), board, left)
                if best is None or r[0] > best[0]:
                    best = r
        else:
            best = self._feat(hole, board, left)
        return best

    def _feat(self, keep, board, left):
        s, outs, wet, cat = features(self.var, keep, board)
        de = min(0.6, outs * (0.04 if left == 2 else 0.021 if left == 1 else 0.0))
        e = s + (1 - s) * de
        return e, s, outs, wet, cat

    def mc_hs(self, hole2, board, budget=0.00022, max_n=180):
        """Hand strength vs one random 2-card hand (Monte Carlo, time-boxed); board has 4 or 5 cards."""
        t0 = perf_counter()
        dead = set(hole2) | set(board)
        deck = [c for c in range(52) if c not in dead]
        nd = len(deck)
        val = self.var.ranker.value
        rnd = self.rng.random
        wins = 0.0
        n = 0
        if len(board) >= 5:
            hv = val(hole2 + board)
            while n < max_n:
                i = int(rnd() * nd)
                j = int(rnd() * (nd - 1))
                if j >= i:
                    j += 1
                ov = val([deck[i], deck[j]] + board)
                if hv > ov:
                    wins += 1.0
                elif hv == ov:
                    wins += 0.5
                n += 1
                if (n & 15) == 0 and perf_counter() - t0 > budget:
                    break
        else:
            hvs = {}
            while n < max_n:
                k = int(rnd() * nd)
                i = int(rnd() * nd)
                j = int(rnd() * nd)
                if i == j or i == k or j == k:
                    continue
                rc = deck[k]
                b = board + [rc]
                hv = hvs.get(rc)
                if hv is None:
                    hv = hvs[rc] = val(hole2 + b)
                ov = val([deck[i], deck[j]] + b)
                if hv > ov:
                    wins += 1.0
                elif hv == ov:
                    wins += 0.5
                n += 1
                if (n & 15) == 0 and perf_counter() - t0 > budget:
                    break
        return wins / n if n else 0.5

    def postflop(self, sp, obs):
        e, s, outs, wet, cat = self.hand_eq(sp)
        n_opp = max(1, sp.n_opp)
        expo = (n_opp ** 0.8) * 1.12
        ee = e ** expo
        if len(sp.hole) == 2 and len(sp.board) >= 4:
            hs = self.mc_hs(sp.hole, sp.board)
            em = hs ** (3.4 * n_opp ** 0.8)
            w = 0.65 if len(sp.board) >= 5 else 0.5
            ee = w * em + (1 - w) * ee
        pot = sp.pot
        to_call = sp.to_call
        stack = sp.stack
        street = sp.street
        last = street == 3
        rng = self.rng.random()
        i_aggr = sp.last_aggr == sp.me
        spr = stack / max(pot, 1)

        if to_call == 0:
            if ee >= 0.80:
                frac = 0.75 if spr > 1.5 else 1.0
                return self.bet(sp, frac)
            if ee >= 0.62:
                return self.bet(sp, 0.55)
            if not last and outs >= 8 and n_opp <= 2 and rng < 0.45:
                return self.bet(sp, 0.5)
            if i_aggr and street == 1 and n_opp <= 2 and rng < (0.55 if n_opp == 1 else 0.3):
                return self.bet(sp, 0.4)
            if n_opp == 1 and last and rng < 0.12 and ee < 0.25:
                return self.bet(sp, 0.6)
            return act_call(sp)

        need = to_call / (pot + to_call)
        bet_frac = to_call / max(pot - to_call, 1)
        v_aggr = 0
        for h_st, h_seat, h_act, _ in sp.hist:
            if h_st >= 1 and h_act == "raise" and h_seat != sp.me:
                v_aggr += 1
        aggr_pen = 0.07 + 0.08 * min(bet_frac, 1.5) + AGGR_STEP * max(0, v_aggr - 1)
        if last:
            aggr_pen += 0.04
        if sp.raises >= 2:
            aggr_pen += RERAISE_PEN
        if n_opp >= 2:
            aggr_pen += 0.03 * (n_opp - 1)
        if cat <= PAIR and street >= 2 and bet_frac >= 0.4:
            aggr_pen += PAIR_PEN
        # opponent who bets a lot -> less penalty
        if sp.raiser >= 0:
            pa = self.post_acts.get(sp.raiser, 0)
            pb = self.post_bets.get(sp.raiser, 0)
            freq = (pb + 1.0) / (pa + 4.0)
            aggr_pen *= clamp(1.4 - 1.3 * freq, 0.6, 1.3)
        ea = ee - aggr_pen
        commit = to_call >= 0.5 * stack or spr < 0.6
        if commit and sp.raiser >= 0 and sp.n_alive > 2:
            ineed = self.icm_need(sp, obs, sp.raiser)
            if ineed is not None and ineed > need:
                need = ineed
        if ee >= 0.86 and sp.raises < 3:
            if spr < 2.5 or sp.raises >= 2:
                return act_allin(sp)
            return act_raise(sp, sp.bet + to_call + 1.0 * (pot + to_call))
        if ea >= need:
            if commit and ee >= 0.55:
                return act_allin(sp)
            return act_call(sp)
        return act_fold(sp)

    def bet(self, sp, frac):
        target = sp.bet + frac * sp.pot
        stack_total = sp.stack + sp.bet
        if stack_total - target < 0.3 * sp.pot:
            return act_allin(sp)
        return act_raise(sp, max(target, sp.min_to))
