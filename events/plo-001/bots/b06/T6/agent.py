import os
import random
from bisect import bisect_left
from itertools import combinations

import numpy as np

from .evaluator import CARD, SUIT, omaha_value, opp_pair_values, next_card_values, STRAIGHT, FLUSH, FULL_HOUSE, TRIPS, TWO_PAIR

_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- preflop table
_BINOM = [[0] * 5 for _ in range(53)]
for _n in range(53):
    for _k in range(5):
        if _k == 0:
            _BINOM[_n][_k] = 1
        elif _n == 0:
            _BINOM[_n][_k] = 0
        else:
            _BINOM[_n][_k] = _BINOM[_n - 1][_k - 1] + _BINOM[_n - 1][_k]

PF = None       # shape (K, 270725) float32 equities vs k random hands (colex index)
PF_KS = None
PF_PCT = None   # percentile (0 best) by strength key
try:
    _d = np.load(os.path.join(_DIR, "pf_eq.npz"))
    PF = _d["eq"].astype(np.float32) / 65535.0
    PF_KS = [int(k) for k in _d["ks"]]
    PF_PCT = _d["pct"].astype(np.float32) / 65535.0
except Exception:
    PF = None


def hand_index(cards):
    a, b, c, d = sorted(cards)
    return a + _BINOM[b][2] + _BINOM[c][3] + _BINOM[d][4]


def heur_score(cards):
    ranks = [x >> 2 for x in cards]
    suits = [x & 3 for x in cards]
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    s = 0.0
    for r, n in cnt.items():
        if n == 2:
            s += 6 + r * 0.9
        elif n == 3:
            s += 1 + r * 0.2
        elif n == 4:
            s -= 2
    for su in range(4):
        n = suits.count(su)
        if n >= 2:
            hi = max(r for r, ss in zip(ranks, suits) if ss == su)
            bonus = 2 + (4 if hi == 12 else 2 if hi == 11 else 1 if hi >= 9 else 0)
            s += bonus if n == 2 else bonus * 0.5
    d = sorted(cnt)
    for i in range(len(d)):
        for j in range(i + 1, len(d)):
            g = d[j] - d[i]
            s += (0, 3, 2, 1.2, 0.5)[g] if g <= 4 else 0
    if len(d) == 4 and d[-1] - d[0] <= 4:
        s += 3
    s += 0.6 * sum(max(0, r - 7) for r in ranks)
    return s


_HEUR_SORTED = None


def _heur_pct(cards):
    global _HEUR_SORTED
    if _HEUR_SORTED is None:
        rr = random.Random(12345)
        deck = list(range(52))
        _HEUR_SORTED = sorted(heur_score(rr.sample(deck, 4)) for _ in range(6000))
    s = heur_score(cards)
    return 1.0 - bisect_left(_HEUR_SORTED, s) / len(_HEUR_SORTED)


def pf_info(cards):
    """(percentile 0=best, eq vs 1, eq vs 3) for a 4-card hand."""
    if PF is not None:
        i = hand_index(cards)
        return float(PF_PCT[i]), float(PF[0, i]), float(PF[2, i])
    p = _heur_pct(cards)
    return p, 0.62 - 0.24 * p, 0.38 - 0.25 * p


def pf_eq_k(cards, k):
    if PF is None:
        p = _heur_pct(cards)
        return max(0.02, (0.62 - 0.24 * p) ** (k ** 0.8))
    i = hand_index(cards)
    ks = PF_KS
    if k <= ks[0]:
        return float(PF[0, i])
    for j in range(1, len(ks)):
        if k <= ks[j]:
            lo, hi = ks[j - 1], ks[j]
            t = (k - lo) / (hi - lo)
            return float(PF[j - 1, i]) * (1 - t) + float(PF[j, i]) * t
    return float(PF[-1, i])


# ---------------------------------------------------------------- straights helper
STRAIGHTS = []
for _top in range(4, 13):
    STRAIGHTS.append(0x1F << (_top - 4))
STRAIGHTS.append((1 << 12) | 0xF)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        self.n_seats = config.get("seats", 8)
        # opponent stats
        self.st = {}

    # ------------------------------------------------------------ stats
    def _s(self, seat):
        d = self.st.get(seat)
        if d is None:
            d = self.st[seat] = {"h": 0, "vpip": 0, "pfr": 0, "agg": 0, "pas": 0, "fold": 0, "fb": 0, "ff": 0}
        return d

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur = -1
            bet_on = False
            for st, seat, act, amt in hist:
                if st != cur:
                    cur = st
                    bet_on = False
                if st > 0 and act in ("fold", "call", "raise") and bet_on and seat != self.seat:
                    d = self._s(seat)
                    d["fb"] += 1
                    if act == "fold":
                        d["ff"] += 1
                if st > 0 and act == "raise":
                    bet_on = True
                if act in ("ante", "sb", "bb", "return"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    d = self._s(seat)
                    if act == "raise":
                        d["agg"] += 1
                    elif act == "call":
                        d["pas"] += 1
                    elif act == "fold":
                        d["fold"] += 1
            for seat in seen:
                d = self._s(seat)
                d["h"] += 1
                if seat in vp:
                    d["vpip"] += 1
                if seat in pr:
                    d["pfr"] += 1
        except Exception:
            pass

    def _foldrate(self, seat):
        d = self.st.get(seat)
        if d is None:
            return 0.45
        return (d["ff"] + 2.0) / (d["fb"] + 4.0)

    def _loose(self, seat):
        """(vpip, pfr, aggression) with priors."""
        d = self.st.get(seat)
        if d is None:
            return 0.35, 0.15, 1.0
        h = d["h"]
        vpip = (d["vpip"] + 3.5) / (h + 10)
        pfr = (d["pfr"] + 1.5) / (h + 10)
        af = (d["agg"] + 2) / (d["pas"] + 2)
        return vpip, pfr, af

    # ------------------------------------------------------------ actions
    def act(self, obs):
        try:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs.get("n_discard", 1)]}
            return self._act(obs)
        except Exception:
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def _icm_premium(self, to_call):
        """Extra equity needed for calls that risk much of our stack (flat payout ladder)."""
        f = min(1.0, to_call / max(1, self.my_stack))
        if f < 0.15:
            return 0.0
        n = self.n_alive
        base = 0.0 if n <= 2 else 0.05 if n == 3 else 0.07 if n == 4 else 0.08 if n <= 6 else 0.16
        # a big stack loses less when it loses; scale by how much of our stack is at risk
        return base * f

    def _fold(self):
        return {"action": "check"} if self.can_check else {"action": "fold"}

    def _call(self):
        return {"action": "check"} if self.to_call == 0 else {"action": "call"}

    def _raise_to(self, amt):
        if not self.can_raise:
            return self._call()
        a = int(amt)
        if a < self.min_to:
            a = self.min_to
        if a > self.max_to:
            a = self.max_to
        # if remaining stack after this would be tiny, shove
        if self.my_stack + self.my_bet - a < 0.3 * (self.pot + 2 * (a - self.my_bet)):
            a = self.max_to
        return {"action": "raise", "amount": a}

    def _pot_frac(self, f):
        target = self.my_bet + self.to_call + f * (self.pot + self.to_call)
        return self._raise_to(target)

    def _act(self, obs):
        me = self.seat = obs["seat"]
        legal = obs["legal"]
        self.can_check = "check" in legal
        self.can_raise = ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0
        self.to_call = obs["to_call"]
        self.min_to = obs["min_raise_to"]
        self.max_to = obs["max_raise_to"]
        self.pot = obs["pot"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        self.my_stack = stacks[me]
        self.my_bet = bets[me]
        self.bb = obs["bb"] or 1
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        opps = [s for s in in_hand if s != me]
        self.opps = opps
        self.n_opp = len(opps)
        self.n_alive = len(alive)
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        self.eff = min(self.my_stack + self.my_bet, other)
        hist = obs["history"]
        st = obs["street_index"]
        raises = 0
        raiser = -1
        last_aggr = -1
        callers = 0
        for h_st, seat, a, _ in hist:
            if a == "raise":
                if h_st == st:
                    raises += 1
                    raiser = seat
                    callers = 0
                else:
                    last_aggr = seat
            elif a == "call" and h_st == st:
                callers += 1
        self.raises, self.raiser, self.callers, self.last_aggr = raises, raiser, callers, last_aggr
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        n = len(alive)
        if st == 0:
            if n == 2:
                order = [alive[bi], alive[1 - bi]]
            else:
                bbs = obs["bb_seat"]
                j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
                order = alive[j:] + alive[:j]
        else:
            order = alive[bi + 1:] + alive[:bi + 1]
        i = order.index(me) if me in order else 0
        self.behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in in_hand and (stacks[s] > 0 or s == me)]
        self.ip = bool(live) and live[-1] == me
        self.is_bb = me == obs["bb_seat"]
        self.is_sb = me == obs["sb_seat"]
        self.stacks = stacks
        self.obs = obs
        if st == 0:
            return self._preflop(hole, obs)
        return self._postflop(hole, board, obs)

    # ------------------------------------------------------------ preflop
    def _preflop(self, hole, obs):
        pct, e1, e3 = pf_info(hole)
        bb = self.bb
        eff_bb = self.eff / bb
        stack_bb = (self.my_stack + self.my_bet) / bb
        to_call = self.to_call
        n_behind = len(self.behind)
        raises = self.raises
        # short-stack mode: get it in with decent hands
        if eff_bb <= 12 or stack_bb <= 12 or (self.n_alive == 2 and eff_bb <= 30):
            # equity vs likely callers
            k = 1 + (1 if self.n_opp >= 3 and raises == 0 else 0)
            eq = pf_eq_k(hole, k)
            if raises == 0:
                th = 0.35 + 0.05 * (12 - min(12, stack_bb)) / 12.0 - 0.03 * n_behind
                th = max(0.12, min(0.6, th))
                if 0 < n_behind <= 3:
                    th += 0.05 * sum(1 for b in self.behind if self._loose(b)[0] < 0.25)
                if self.n_alive == 2:
                    th = 0.85
                elif self.n_alive == 3:
                    th += 0.15
                if pct < th:
                    return self._raise_to(self.max_to)
                if self.can_check:
                    return self._fold()
                return self._fold()
            # facing a raise: pot odds
            need = to_call / (self.pot + to_call)
            rv, rp, raf = self._loose(self.raiser) if self.raiser >= 0 else (0.35, 0.15, 1.0)
            # vs a raiser's range: discount equity
            adj = 0.06 + (0.06 if raises >= 2 else 0) - (0.05 if rp > 0.3 else 0)
            if self.n_alive == 2 and raises == 1:
                adj = min(adj, 0.02)
            if e1 - adj > need + 0.02 + self._icm_premium(to_call):
                if pct < 0.08:
                    return self._raise_to(self.max_to)
                return self._call()
            return self._fold()

        rv, rp, raf = self._loose(self.raiser) if self.raiser >= 0 else (0.35, 0.15, 1.0)
        loose_raiser = rp > 0.3
        if raises == 0:
            limpers = self.callers
            if self.can_check:  # BB option
                if pct < 0.07 and self.can_raise:
                    return self._pot_frac(1.0)
                return {"action": "check"}
            # open thresholds by players left to act
            open_th = 1.25 * {0: 0.4, 1: 0.36, 2: 0.28, 3: 0.22, 4: 0.17, 5: 0.14}.get(n_behind, 0.12)
            if self.n_alive <= 4:
                open_th += 0.08
            if limpers:
                open_th *= 0.8
            elif 0 < n_behind <= 3:
                tight = sum(1 for b in self.behind if self._loose(b)[0] < 0.25)
                open_th += 0.05 * tight
            if pct < open_th:
                return self._pot_frac(1.0)
            # limp / complete with playable hands cheaply
            if to_call <= bb and pct < open_th + 0.15 and (limpers or self.is_sb):
                return self._call()
            return self._fold()
        # facing raise(s)
        frac = to_call / max(1, self.my_stack)
        if raises == 1:
            three = 0.06 + (0.03 if loose_raiser else 0) + (0.01 if self.ip else 0)
            call_th = 0.09 + (0.06 if loose_raiser else 0) + (0.04 if self.is_bb else 0) + (0.03 if self.ip else 0)
            if frac > 0.25:
                call_th *= 0.5
            elif frac > 0.12:
                call_th *= 0.75
            if self.callers:
                call_th += 0.02
            if rp < 0.09:
                call_th *= 0.7
            if pct < three:
                return self._pot_frac(1.0)
            if pct < call_th:
                return self._call()
            return self._fold()
        # 3-bet or more
        four = 0.012 + (0.02 if loose_raiser else 0)
        call_th = 0.04 + (0.04 if loose_raiser else 0)
        if frac > 0.4:
            call_th *= 0.6
        if pct < four:
            return self._raise_to(self.max_to)
        if pct < call_th:
            return self._call()
        return self._fold()

    # ------------------------------------------------------------ postflop
    def _postflop(self, hole, board, obs):
        dead = hole + board
        myv = omaha_value(hole, board)
        cat = myv >> 20
        best, valid = opp_pair_values(board, dead)
        bv = best[valid]
        nv = bv.size
        better = int(np.count_nonzero(bv > myv))
        tie = int(np.count_nonzero(bv == myv))
        p_pair = (better + 0.5 * tie) / max(1, nv)
        b1 = 1.0 - (1.0 - p_pair) ** 6  # chance a random 4-card hand beats us now
        n_opp = max(1, self.n_opp)
        st = len(board)
        # draws: count cards that make a strong hand
        p_hit = 0.0
        if st < 5:
            used = set(dead)
            bsuit = [0, 0, 0, 0]
            for c in board:
                bsuit[c & 3] += 1
            brank = [c >> 2 for c in board]
            board_paired = len(set(brank)) < len(brank)
            maxbs = max(bsuit)
            cands = np.array([c for c in range(52) if c not in used], dtype=np.int64)
            nvals = next_card_values(hole, board, cands, myv)
            outs = 0.0
            cnt = len(cands)
            for j in range(cnt):
                v2 = int(nvals[j])
                c2 = v2 >> 20
                if c2 <= cat or c2 < STRAIGHT:
                    continue
                c = int(cands[j])
                paired = board_paired or (c >> 2) in brank
                if c2 == STRAIGHT and (paired or maxbs >= 3 or bsuit[c & 3] >= 2):
                    continue
                if c2 == FLUSH:
                    if paired:
                        continue
                    fs = c & 3
                    mine = [h >> 2 for h in hole if h & 3 == fs]
                    if not mine or max(mine) < 10:
                        outs += 0.5
                        continue
                outs += 1
            if cnt:
                q = outs / cnt
                p_hit = q if st == 4 else 1 - (1 - q) * (1 - outs / max(1, cnt - 1))
        # value now vs random hands
        w_now = (1 - b1) ** n_opp
        vul = 0.0 if st == 5 else (0.22 if st == 3 else 0.12)
        if p_pair < 0.003:
            vul *= 0.3
        eq_rand = w_now * (1 - vul) + (1 - w_now) * p_hit * 0.8

        pot = self.pot
        to_call = self.to_call
        spr = self.eff / max(1, pot)
        # facing a bet
        if to_call > 0:
            # estimate bettor range width
            aggr = self.raiser if self.raiser >= 0 else (self.opps[0] if self.opps else -1)
            vp, pr, af = self._loose(aggr) if aggr >= 0 else (0.35, 0.15, 1.0)
            bet_frac = to_call / max(1, pot - to_call)
            X = 0.42 - 0.12 * min(1.0, bet_frac) - 0.08 * (self.raises - 1)
            X *= min(1.8, max(0.6, (af / 1.0) ** 0.5))
            X = max(0.08, min(0.85, X))
            w_vs = max(0.0, (X - b1) / X) ** max(1, n_opp - 1 if self.raises else n_opp)
            # extra opponents still to act / called
            eq = w_vs * (1 - vul) + (1 - w_vs) * p_hit * 0.85
            need = to_call / (pot + to_call)
            need += self._icm_premium(to_call)
            if eq > 0.72 and self.can_raise and w_vs > 0.6:
                return self._pot_frac(1.0)
            if (st < 5 and n_opp == 1 and self.can_raise and p_hit >= 0.4 and self.raises == 1
                    and self._foldrate(aggr) > 0.4 and self.rng.random() < 0.5):
                return self._pot_frac(1.0)
            if eq > need:
                return self._call()
            return self._fold()
        # no bet to us: bet for value / bluff
        if not self.can_raise:
            return {"action": "check"}
        fr0 = 1.0
        for o in self.opps:
            fr0 = min(fr0, self._foldrate(o))
        vth = 0.46 if fr0 > 0.4 else 0.40
        if w_now >= vth or (p_pair < 0.01 and w_now > 0.3):
            big = w_now > 0.7 and fr0 < 0.4
            return self._pot_frac(1.0 if big else 0.75 if n_opp == 1 else 0.9)
        # semi-bluff with strong draws
        if p_hit >= 0.3 and n_opp <= 2 and self.rng.random() < 0.6:
            return self._pot_frac(0.7)
        # bluffs, scaled by how often the opponents fold to bets
        fr = 1.0
        for o in self.opps:
            fr *= self._foldrate(o)
        if n_opp == 1 and self.last_aggr == self.seat and st == 3 and self.rng.random() < 0.35 + 0.5 * fr:
            return self._pot_frac(0.55)
        if n_opp <= 2 and fr > 0.42 and self.rng.random() < fr - 0.2:
            return self._pot_frac(0.6)
        if n_opp == 1 and self.ip and self.rng.random() < 0.15 and w_now > 0.25:
            return self._pot_frac(0.6)
        return {"action": "check"}
