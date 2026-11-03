"""b06 crazy pineapple bot: precomputed preflop equities, push/fold with ICM margin,
time-budgeted Monte Carlo postflop, per-seat opponent stats."""

import json
import os
import random
import time
from itertools import permutations

from .ev import Ranker

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)
_R = Ranker()
VAL = _R.value

_here = os.path.dirname(os.path.abspath(__file__))
XS = [0.03, 0.06, 0.1, 0.15, 0.22, 0.3, 0.4, 0.55, 0.75, 1.0]
H = {}
try:
    with open(os.path.join(_here, "pre2.json")) as f:
        _d = json.load(f)
    XS = _d["xs"]
    H = _d["h"]
except Exception:
    H = {}

MC_BUDGET = 0.00042


def canon_key(cards):
    best = None
    for p in permutations(cards):
        rs = [c >> 2 for c in p]
        if rs[0] < rs[1] or rs[1] < rs[2]:
            continue
        m = {}
        pat = []
        for c in p:
            s = c & 3
            if s not in m:
                m[s] = len(m)
            pat.append(m[s])
        k = (tuple(rs), tuple(pat))
        if best is None or k < best:
            best = k
    rs, pat = best
    return "".join(RANKS[r] for r in rs) + "".join("abcd"[x] for x in pat)


def best_val(hole, board):
    if len(hole) == 2:
        return VAL(hole + board)
    a, b, c = hole[0], hole[1], hole[2]
    v1 = VAL([a, b] + board)
    v2 = VAL([a, c] + board)
    v3 = VAL([b, c] + board)
    return v1 if v1 >= v2 and v1 >= v3 else (v2 if v2 >= v3 else v3)


def interp_vr(row, x):
    if x <= XS[0]:
        return row[0]
    for i in range(1, len(XS)):
        if x <= XS[i]:
            t = (x - XS[i - 1]) / (XS[i] - XS[i - 1])
            return row[i - 1] + t * (row[i] - row[i - 1])
    return row[-1]


OPEN = {1: 0.40, 2: 0.28, 3: 0.21, 4: 0.16, 5: 0.13, 6: 0.11, 7: 0.10}
PUSH = {1: 0.58, 2: 0.40, 3: 0.31, 4: 0.25, 5: 0.21, 6: 0.18, 7: 0.16}


class Agent:
    def __init__(self, config):
        self.seat = config.get("seat", 0)
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        self.stats = {}
        self._hk = None
        self._hinfo = None

    # ------------------------------------------------------------------ stats
    def _s(self, seat):
        s = self.stats.get(seat)
        if s is None:
            s = self.stats[seat] = {"n": 0, "vpip": 0, "pfr": 0, "shove": 0, "agg": 0, "pas": 0,
                                    "fold_post": 0}
        return s

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            sh = set()
            for st, seat, act, amt in hist:
                if seat == self.seat:
                    continue
                if act in ("ante", "return", "discard"):
                    continue
                seen.add(seat)
                s = self._s(seat)
                if st == 0:
                    if act == "call":
                        vp.add(seat)
                    elif act == "raise":
                        vp.add(seat)
                        pr.add(seat)
                        if amt >= 0.9 * self.start_stack_guess(event, seat, amt):
                            sh.add(seat)
                else:
                    if act == "raise":
                        s["agg"] += 1
                    elif act in ("call", "check"):
                        s["pas"] += 1
                    elif act == "fold":
                        s["fold_post"] += 1
            for seat in seen:
                s = self._s(seat)
                s["n"] += 1
                if seat in vp:
                    s["vpip"] += 1
                if seat in pr:
                    s["pfr"] += 1
                if seat in sh:
                    s["shove"] += 1
        except Exception:
            pass

    def start_stack_guess(self, event, seat, amt):
        # stack at end + what they put in is unknown cheaply; use end stack + amt as proxy
        try:
            return event["stacks"][seat] + amt if event["stacks"][seat] > 0 else amt
        except Exception:
            return 1e18

    def pfr_of(self, seat, prior, w=8.0):
        s = self.stats.get(seat)
        if not s:
            return prior
        return (s["pfr"] + prior * w) / (s["n"] + w)

    def vpip_of(self, seat, prior=0.3, w=8.0):
        s = self.stats.get(seat)
        if not s:
            return prior
        return (s["vpip"] + prior * w) / (s["n"] + w)

    def agg_of(self, seat):
        s = self.stats.get(seat)
        if not s:
            return 0.33
        return (s["agg"] + 1.0) / (s["agg"] + s["pas"] + 3.0)

    # ------------------------------------------------------------------ helpers
    def hinfo(self, hole):
        key = tuple(hole)
        if self._hk == key:
            return self._hinfo
        info = None
        if len(hole) == 3:
            info = H.get(canon_key(hole))
        if info is None:
            info = {"eq": [0.45, 0.3, 0.22, 0.18, 0.15, 0.13, 0.11], "pct": 0.5,
                    "vr": [0.4] * len(XS)}
        self._hk = key
        self._hinfo = info
        return info

    def act(self, obs):
        t0 = time.perf_counter()
        try:
            return self._act(obs, t0)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][: obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    # ------------------------------------------------------------------ main
    def _act(self, obs, t0):
        if obs["phase"] == "discard":
            return self.discard(obs, t0)
        self.obs = obs
        legal = obs["legal"]
        self.legal = legal
        self.can_check = "check" in legal
        self.to_call = obs["to_call"]
        self.min_to = obs["min_raise_to"]
        self.max_to = obs["max_raise_to"]
        self.can_raise = ("raise" in legal or "bet" in legal) and self.max_to > 0
        me = obs["seat"]
        self.me = me
        stacks = obs["stacks"]
        bets = obs["bets"]
        self.stack = stacks[me]
        self.mybet = bets[me]
        in_hand = obs["in_hand"]
        self.opps = [s for s in in_hand if s != me]
        bb = obs["bb"] or 1
        self.bb = bb
        other = max([stacks[s] + bets[s] for s in self.opps], default=0)
        self.eff = min(self.stack + self.mybet, other)
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if obs["street_index"] == 0:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board, t0)

    # actions
    def a_fold(self):
        return {"action": "check"} if self.can_check else {"action": "fold"}

    def a_call(self):
        if self.can_check:
            return {"action": "check"}
        return {"action": "call"}

    def a_raise(self, amt):
        if not self.can_raise:
            return self.a_call()
        a = int(amt)
        if a < self.min_to:
            a = self.min_to
        if a > self.max_to:
            a = self.max_to
        # if remaining stack after raise is tiny, just shove
        if self.max_to - a < 0.2 * a:
            a = self.max_to
        name = "raise" if "raise" in self.legal else "bet"
        return {"action": name, "amount": a}

    def a_allin(self):
        if self.can_raise:
            name = "raise" if "raise" in self.legal else "bet"
            return {"action": name, "amount": self.max_to}
        return self.a_call()

    def price(self, pot, bets):
        """Pot odds counting only chips we can actually win (uncalled excess returns)."""
        risk = min(self.to_call, self.stack)
        my_total = self.mybet + risk
        excess = 0
        for b in bets:
            if b > my_total:
                excess += b - my_total
        pot_eff = pot - excess + risk
        if pot_eff <= 0:
            return 0.5
        return risk / float(pot_eff)

    def icm_margin(self, risk_chips):
        """Extra equity demanded for risking chips, from the points table shape."""
        obs = self.obs
        n = len(obs["alive"])
        if n <= 2:
            return 0.0
        total = self.stack + self.mybet
        if total <= 0:
            return 0.0
        frac = min(1.0, risk_chips / float(total))
        mybb = total / self.bb
        if mybb <= 4:
            return 0.0
        # exact ICM (kit/icm.py) says ~0.10 even with 3-5 left, but tested tighter = worse
        # here (blinds rise fast, opponents shove wide), so keep the lighter margin
        base = 0.10 if n >= 4 else 0.07
        if mybb <= 8:
            base *= 0.5
        elif mybb >= 40:
            base += 0.03
        if risk_chips >= total:
            base *= 1.2
        return base * frac

    # ------------------------------------------------------------------ preflop
    def preflop(self, obs, hole):
        if getattr(self, "_hs_id", None) != obs["hand_id"]:
            self._hs_id = obs["hand_id"]
            self._hs = self.stack + self.mybet
        info = self.hinfo(hole)
        pct = info["pct"]
        me = self.me
        bb = self.bb
        alive = obs["alive"]
        n = len(alive)
        hist = obs["history"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        # preflop order
        bbs = obs["bb_seat"]
        if n == 2:
            btn = obs["button"]
            bi = alive.index(btn) if btn in alive else 0
            order = [alive[bi], alive[1 - bi]]
        else:
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        nb = max(1, len(behind))
        raises = []
        limpers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises.append((seat, amt))
            elif act == "call" and not raises:
                limpers += 1
        eff_bb = self.eff / bb
        to_call = self.to_call
        pot = obs["pot"]

        if not raises:
            # unopened (maybe limpers)
            if eff_bb <= 13:
                rng_ = (0.66 if n == 2 else PUSH.get(nb, 0.16)) * (10.0 / max(eff_bb, 1.0)) ** 0.7
                if limpers:
                    rng_ *= 0.75
                # loosen vs tight players behind
                if behind:
                    tight = sum(1 for s in behind if self.vpip_of(s) < 0.14)
                    rng_ *= 1.0 + 0.5 * tight / len(behind)
                if pct <= min(1.0, rng_):
                    return self.a_allin()
                if self.can_check:
                    return self.a_call()
                # SB completing for cheap with decent hands when deep-ish
                return self.a_fold()
            open_r = OPEN.get(nb, 0.10)
            if n == 2:
                open_r = 0.80
            elif n == 3:
                open_r = max(open_r, 0.5 if nb == 1 else 0.45)
            if limpers:
                open_r *= 0.7
            elif behind:
                # steal wider when the players behind rarely play
                tight = 0
                for s in behind:
                    sv = self.stats.get(s)
                    if sv and sv["n"] >= 12 and sv["vpip"] < 0.14 * sv["n"]:
                        tight += 1
                open_r = min(0.75, open_r * (1.0 + 1.2 * tight / len(behind)))
            if self.can_check:
                # BB option vs limpers
                if pct <= 0.12:
                    return self.a_raise((3.5 + limpers) * bb)
                return self.a_call()
            if pct <= open_r:
                size = (2.5 if eff_bb > 30 else 2.2) * bb + limpers * bb
                return self.a_raise(size)
            # SB limp with medium hands when only BB behind
            if nb == 1 and me == obs["sb_seat"] and pct <= 0.55 and to_call <= 0.5 * bb + 1:
                return self.a_call()
            # cheap limp behind limpers with speculative hands
            if limpers and to_call <= bb and pct <= open_r * 1.6 and eff_bb > 40:
                return self.a_call()
            return self.a_fold()

        # facing raise(s)
        raiser, raise_to = raises[-1]
        nr = len(raises)
        call_total = self.mybet + to_call  # my street total after call
        risk = min(self.stack, to_call)
        raiser_left = stacks[raiser]
        raiser_allin = raiser_left == 0
        commit = to_call >= 0.4 * (self.stack + self.mybet) or raiser_allin or self.stack - to_call < 4 * bb
        # estimate raiser range width
        r_eff_bb = min(stacks[raiser] + bets[raiser], self.stack + self.mybet) / bb
        shove = raiser_allin or raise_to >= 0.9 * (stacks[raiser] + bets[raiser])
        if shove:
            prior = 0.12 if r_eff_bb > 25 else 0.2 if r_eff_bb > 12 else 0.3 if r_eff_bb > 6 else 0.45
        else:
            prior = 0.14 if nr == 1 else 0.06 if nr == 2 else 0.03
        # late-position first raiser steals wider
        if nr == 1 and limpers == 0 and raiser in order:
            ri = order.index(raiser)
            r_behind = len(order) - 1 - ri
            if r_behind <= 2:
                prior *= 1.5 if r_behind == 1 else 1.25
        x = self.pfr_of(raiser, prior)
        if shove and nr == 1 and r_eff_bb <= 15:
            x = max(x, prior * 0.9)
        if nr >= 2:
            x = min(x, prior * 1.5)
        x = max(0.03, min(0.9, x * (0.75 if nr == 1 else 0.6)))
        # several players in: each other committed player multiplies our equity
        callers_after = 0
        others = 0
        for s in self.opps:
            if s == raiser:
                continue
            if bets[s] > bb or stacks[s] == 0:
                others += 1
        for st, seat, act, amt in hist:
            if st == 0 and act == "call" and seat != me:
                callers_after += 1
        eqv = interp_vr(info["vr"], x)
        if others:
            eqc = interp_vr(info["vr"], 0.1)
            eqv *= eqc ** others
        # players still to act behind may wake up
        eqv *= 0.98 ** len(behind)
        need = self.price(pot, bets)

        if commit:
            # all-in style decision: call/shove if equity beats price plus icm margin
            m = self.icm_margin(min(self.stack, max(raiser_left + bets[raiser] - self.mybet, to_call)))
            if eqv >= need + m:
                # shove if we can and it's not just a call
                if self.can_raise and not raiser_allin and eqv >= need + m + 0.05:
                    return self.a_allin()
                return self.a_call()
            return self.a_fold()

        # non-committing raise
        rb = raise_to / bb
        if nr == 1:
            three_r = 0.035 if x <= 0.15 else 0.06 if x <= 0.3 else 0.09
            if n == 2:
                three_r = max(three_r, 0.12)
            if pct <= three_r:
                if eff_bb <= 25:
                    return self.a_allin()
                ip = len(behind) == 0 or (me != obs["sb_seat"] and me != bbs)
                return self.a_raise(raise_to * (3.0 if ip else 3.6) + callers_after * raise_to)
            # resteal shove at medium stacks
            if eff_bb <= 20 and pct <= max(0.06, x * 0.45):
                return self.a_allin()
            call_r = 0.10 + (0.06 if rb <= 3 else 0.0) + (0.05 if x > 0.3 else 0.0)
            if me == bbs:
                call_r += 0.12 if rb <= 3 else 0.06
            if n == 2:
                call_r = max(call_r, 0.6 if rb <= 3 else 0.4)
            elif n == 3:
                call_r += 0.08
            if eff_bb < 30:
                call_r *= 0.8
            if pct <= call_r and need < 0.4:
                return self.a_call()
            return self.a_fold()
        # 3bet+ facing
        if pct <= 0.02 or (eqv >= 0.55 and pct <= 0.05):
            return self.a_allin()
        if eqv >= need + 0.1 and pct <= 0.06:
            return self.a_call()
        return self.a_fold()

    # ------------------------------------------------------------------ postflop
    def equity(self, hole, board, n_opp, t0, budget=MC_BUDGET):
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        per = len(hole)
        sim = max(1, min(n_opp, 2))
        draw = need + per * sim
        rng = self.rng
        sample = rng.sample
        ckey = (tuple(hole), tuple(board), sim)
        cache = self.__dict__.setdefault("_eqc", {})
        if len(cache) > 64:
            cache.clear()
        wins, cnt = cache.get(ckey, (0.0, 0))
        start_cnt = cnt
        clock = time.perf_counter
        fixed = None
        if need == 0:
            fixed = best_val(hole, board)
        while True:
            cards = sample(deck, draw)
            b = board + cards[:need] if need else board
            hv = fixed if fixed is not None else best_val(hole, b)
            res = 1.0
            for k in range(sim):
                o = cards[need + per * k: need + per * (k + 1)]
                ov = best_val(o, b)
                if ov > hv:
                    res = 0.0
                    break
                if ov == hv:
                    res *= 0.5
            wins += res
            cnt += 1
            if cnt >= 600:
                break
            if cnt - start_cnt >= 8 and clock() - t0 > budget:
                break
        cache[ckey] = (wins, cnt)
        eq = wins / cnt
        if n_opp > sim:
            eq = eq ** (n_opp / float(sim))
        return eq, cnt

    def postflop(self, obs, hole, board, t0):
        n_opp = len(self.opps)
        st = obs["street_index"]
        pot = obs["pot"]
        to_call = self.to_call
        eq, cnt = self.equity(hole, board, n_opp, t0)
        share = eq * (n_opp + 1)
        hist = obs["history"]
        me = self.me
        bb = self.bb
        # who was last aggressor preflop / previous street
        pf_aggr = None
        last_aggr_prev = None
        bettors = []
        for h_st, seat, act, amt in hist:
            if act == "raise":
                if h_st == 0:
                    pf_aggr = seat
                if h_st == st - 1:
                    last_aggr_prev = seat
                if h_st == st:
                    bettors.append(seat)
        stack = self.stack
        spr = stack / float(max(pot, 1))
        r = self.rng.random()

        if to_call == 0:
            # value bet
            if share >= 1.35 or (n_opp == 1 and eq >= 0.66):
                frac = 0.6 if share < 1.7 else 0.75
                if spr < 1.2:
                    return self.a_allin()
                return self.a_raise(self.mybet + frac * pot)
            # c-bet / semi-bluff when we were aggressor
            if pf_aggr == me and st == 1 and n_opp <= 2:
                p = 0.65 if n_opp == 1 else 0.35
                if eq >= 0.38 and r < p:
                    return self.a_raise(self.mybet + 0.5 * pot)
            if last_aggr_prev == me and n_opp == 1 and st == 2 and eq >= 0.5 and r < 0.5:
                return self.a_raise(self.mybet + 0.55 * pot)
            # occasional probe/bluff heads-up when checked to on river
            if n_opp == 1 and st == 3 and eq < 0.2 and r < 0.12:
                return self.a_raise(self.mybet + 0.6 * pot)
            return self.a_call()

        # facing a bet
        pot_after = pot + to_call
        po = self.price(pot, obs["bets"])
        pot_before = max(1, pot - to_call)
        bf = to_call / float(pot_before)
        aggr = self.agg_of(bettors[-1]) if bettors else 0.33
        adj = 0.06 + 0.10 * min(bf, 1.5)
        # bettor also bet earlier streets this hand: stronger range
        if bettors:
            bs = bettors[-1]
            prev = 0
            for h in hist:
                if 0 < h[0] < st and h[1] == bs and h[2] == "raise":
                    prev += 1
            adj += 0.06 * prev
        if aggr > 0.5:
            adj -= 0.07
        elif aggr < 0.2:
            adj += 0.05
        if len(bettors) >= 2:
            adj += 0.08
        # we are pot-committed: little left behind relative to pot
        left_after = stack - to_call
        if left_after < 0.25 * pot_after:
            adj -= 0.05
        need = po + adj
        # multiway: eq already reflects n_opp; compare in share terms
        if n_opp >= 2:
            need = need * 0.85
        # big commitments face stronger ranges
        need += 0.15 * min(1.0, to_call / float(max(1, stack + self.mybet)))
        i_raised = False
        for h in hist:
            if h[0] == st and h[1] == me and h[2] == "raise":
                i_raised = True
        if i_raised:
            need += 0.08
        raise_gate = 0.86 if n_opp == 1 else 0.66
        if i_raised:
            raise_gate = 0.95
        # deep-stack guard: don't stack off with weak made hands while many players remain
        hs = self._hs if getattr(self, "_hs_id", None) == obs["hand_id"] else stack + self.mybet + pot
        weak = False
        if hs > 25 * bb and len(obs["alive"]) >= 4 and (stack - to_call) < 0.5 * hs:
            cat = VAL(hole + board) >> 20 if len(hole) == 2 else best_val(hole, board) >> 20
            if eq < 0.9 and (cat < 2 or (st >= 2 and cat < 3)):
                weak = True
        if eq >= raise_gate and self.can_raise and len(bettors) <= 2 and not weak:
            if spr < 2.5 or (eq >= 0.93 and st == 3):
                return self.a_allin()
            return self.a_raise(self.mybet + to_call + (pot + to_call) * 0.8)
        if eq >= need and not weak:
            return self.a_call()
        return self.a_fold()

    # ------------------------------------------------------------------ discard
    def discard(self, obs, t0):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        k = obs.get("n_discard") or 1
        if len(hole) - k != 2 or len(hole) != 3:
            return {"action": "discard", "cards": list(obs["hole"][:k])}
        keeps = [(0, 1), (0, 2), (1, 2)]
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        score = [0.0, 0.0, 0.0]
        rng = self.rng
        cnt = 0
        clock = time.perf_counter
        n_opp = max(1, min(2, len(obs["in_hand"]) - 1))
        draw = need + 2 * n_opp
        while True:
            cards = rng.sample(deck, draw)
            b = board + cards[:need]
            ovs = [VAL(cards[need + 2 * j: need + 2 * j + 2] + b) for j in range(n_opp)]
            ov = max(ovs)
            for ki, (x, y) in enumerate(keeps):
                hv = VAL([hole[x], hole[y]] + b)
                if hv > ov:
                    score[ki] += 1.0
                elif hv == ov:
                    score[ki] += 0.5
            cnt += 1
            if cnt >= 300:
                break
            if cnt >= 10 and clock() - t0 > 0.0005:
                break
        # tie-break by current made hand
        cur = [VAL([hole[x], hole[y]] + board) for (x, y) in keeps]
        bi = max(range(3), key=lambda i: (score[i], cur[i]))
        x, y = keeps[bi]
        drop = [c for i, c in enumerate(obs["hole"]) if i not in (x, y)]
        return {"action": "discard", "cards": drop}
