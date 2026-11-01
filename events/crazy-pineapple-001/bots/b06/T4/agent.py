import random
from bisect import bisect_left, bisect_right
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = tuple(r + s for r in RANKS for s in SUITS)


def _top_ranks(k):
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


def _straight_tops():
    tops = {}
    for i in range(9):
        tops[sum(1 << r for r in range(i, i + 5))] = i + 4
    tops[(1 << 12) | 0b1111] = 3
    ordered = sorted(tops.items(), key=lambda t: -t[1])
    out = [-1] * 8192
    for m in range(8192):
        for sm, t in ordered:
            if m & sm == sm:
                out[m] = t
                break
    return tuple(out)


STOP = _straight_tops()


def value(cards):
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
    best = TOP5[m1]
    if m2:
        if m4:
            q = m4.bit_length() - 1
            v = 7 << 20 | q << 16 | TOP1[m1 & ~(1 << q)] << 12
            if v > best:
                best = v
        if m3:
            t = m3.bit_length() - 1
            rest = m2 & ~(1 << t)
            if rest:
                v = 6 << 20 | t << 16 | (rest.bit_length() - 1) << 12
                if v > best:
                    best = v
            v = 3 << 20 | t << 16 | TOP2[m1 & ~(1 << t)] << 8
            if v > best:
                best = v
        p = m2.bit_length() - 1
        rest = m2 & ~(1 << p)
        if rest:
            p2 = rest.bit_length() - 1
            v = 2 << 20 | p << 16 | p2 << 12 | TOP1[m1 & ~(1 << p | 1 << p2)] << 8
            if v > best:
                best = v
        v = 1 << 20 | p << 16 | TOP3[m1 & ~(1 << p)] << 4
        if v > best:
            best = v
    t = STOP[m1]
    if t >= 0:
        v = 4 << 20 | t << 16
        if v > best:
            best = v
    for f in sm:
        if f.bit_count() >= 5:
            t = STOP[f]
            v = 8 << 20 | t << 16 if t >= 0 else 5 << 20 | TOP5[f]
            if v > best:
                best = v
    return best


def chen(c1, c2):
    hi, lo = max(c1 >> 2, c2 >> 2), min(c1 >> 2, c2 >> 2)
    top = {12: 10.0, 11: 8.0, 10: 7.0, 9: 6.0}.get(hi, (hi + 2) / 2)
    if hi == lo:
        return max(5.0, top * 2)
    score = top + (2.0 if (c1 & 3) == (c2 & 3) else 0.0)
    gap = hi - lo - 1
    score -= (0, 1, 2, 4)[gap] if gap < 4 else 5
    if gap <= 1 and hi < 10:
        score += 1
    return score


def score3(hole):
    s = sorted((chen(a, b) for a, b in combinations(hole, 2)), reverse=True)
    return s[0] + 0.3 * s[1] + 0.1 * s[2]


def _build_pct():
    sc = []
    for h in combinations(range(52), 3):
        sc.append(score3(h))
    sc.sort()
    return sc


_SCORES = _build_pct()
_NS = len(_SCORES)


def pf_pct(hole):
    """Fraction of 3-card starting hands at least as good (0 = best)."""
    s = score3(hole)
    hi = bisect_right(_SCORES, s)
    lo = bisect_left(_SCORES, s)
    return 1.0 - (lo + hi) / 2.0 / _NS


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        self.hands = {}
        self.vpip = {}
        self.pfr = {}
        self.shoves = {}
        self.agg = {}
        self.pf_aggr = False

    # ---------- opponent stats ----------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in hist:
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0 and act in ("call", "raise"):
                    vp.add(seat)
                if st == 0 and act == "raise":
                    pr.add(seat)
                if act == "raise":
                    self.agg[seat] = self.agg.get(seat, 0) + 1
            for s in seen:
                self.hands[s] = self.hands.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
            for s in pr:
                self.pfr[s] = self.pfr.get(s, 0) + 1
        except Exception:
            pass

    def loose(self, seat):
        n = self.hands.get(seat, 0)
        if n < 6:
            return 0.25
        return (self.pfr.get(seat, 0) + 1) / (n + 4)

    # ---------- main ----------
    def act(self, obs):
        try:
            if obs["phase"] == "discard":
                return self.discard(obs)
            return self.decide(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def discard(self, obs):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        k = obs["n_discard"]
        keep_n = len(hole) - k
        best = None
        bestv = -1
        for keep in combinations(hole, keep_n):
            v = value(list(keep) + board) * 64 + self.draw_bonus(list(keep), board) * 4 + max(c >> 2 for c in keep)
            if v > bestv:
                bestv = v
                best = keep
        out = [NAME[c] for c in hole if c not in best]
        return {"action": "discard", "cards": out[:k]}

    def draw_bonus(self, hole, board):
        cards = hole + board
        b = 0
        sc = [0, 0, 0, 0]
        for c in cards:
            sc[c & 3] += 1
        for c in hole:
            if sc[c & 3] >= 4:
                b = max(b, 10)
        m = 0
        for c in cards:
            m |= 1 << (c >> 2)
        if STOP[m] < 0:
            outs = 0
            for r in range(13):
                if not (m >> r) & 1 and STOP[m | 1 << r] >= 0:
                    outs += 1
            b += 3 * outs
        return b

    def ctx(self, obs):
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        opps = [s for s in in_hand if s != me]
        st = obs["street_index"]
        btn = obs["button"]
        n = len(alive)
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
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        return me, stacks, bets, opps, behind

    def decide(self, obs):
        legal = obs["legal"]
        can_check = "check" in legal
        can_raise = ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0
        self.can_check = can_check
        self.can_raise = can_raise
        self.obs = obs
        me, stacks, bets, opps, behind = self.ctx(obs)
        bb = obs["bb"] or 1
        stack = stacks[me]
        mybet = bets[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(stack + mybet, other)
        eff_bb = eff / bb
        st = obs["street_index"]
        hist = obs["history"]
        raises = 0
        raiser = -1
        for h_st, seat, a, amt in hist:
            if a == "raise" and h_st == st:
                raises += 1
                raiser = seat
        if st == 0:
            return self.preflop(obs, stack, mybet, to_call, pot, eff_bb, bb, opps, behind, raises, raiser, stacks, bets)
        return self.postflop(obs, stack, mybet, to_call, pot, eff, bb, opps, behind, raises, raiser)

    # ---------- action helpers ----------
    def a_fold(self):
        return {"action": "check"} if self.can_check else {"action": "fold"}

    def a_call(self):
        return {"action": "check"} if self.obs["to_call"] == 0 else {"action": "call"}

    def a_raise(self, amount):
        if not self.can_raise:
            return self.a_call()
        o = self.obs
        a = int(amount)
        lo, hi = o["min_raise_to"], o["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        return {"action": "raise", "amount": a}

    def a_allin(self):
        if self.can_raise:
            return self.a_raise(self.obs["max_raise_to"])
        return self.a_call()

    # ---------- preflop ----------
    def preflop(self, obs, stack, mybet, to_call, pot, eff_bb, bb, opps, behind, raises, raiser, stacks, bets):
        hole = [CARD[c] for c in obs["hole"]]
        pct = pf_pct(hole)
        nb = len(behind)
        n_alive = len(obs["alive"])
        me = obs["seat"]
        my_bb = (stack + mybet) / bb
        self.pf_aggr = False
        if raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= 14 or my_bb <= 14:
                pos_w = {0: 0.9, 1: 0.55, 2: 0.42, 3: 0.32, 4: 0.26, 5: 0.21, 6: 0.18, 7: 0.16}.get(nb, 0.15)
                w = pos_w * (10.0 / max(eff_bb, 2.0)) ** 0.6
                if n_alive <= 3:
                    w *= 1.25
                w = min(0.95, w)
                if pct <= w:
                    self.pf_aggr = True
                    return self.a_allin()
                if can_check(obs):
                    return {"action": "check"}
                return self.a_fold()
            pos_w = {0: 0.5, 1: 0.45, 2: 0.36, 3: 0.28, 4: 0.23, 5: 0.19, 6: 0.16, 7: 0.14}.get(nb, 0.13)
            if n_alive <= 4:
                pos_w *= 1.2
            limpers = sum(1 for h in obs["history"] if h[0] == 0 and h[2] == "call")
            if pct <= pos_w * (1.0 if limpers == 0 else 0.7):
                self.pf_aggr = True
                size = (2.5 if eff_bb > 25 else 2.2) * bb + limpers * bb
                return self.a_raise(size)
            if to_call == 0:
                return {"action": "check"}
            # SB complete with decent hand cheaply
            if to_call <= bb * 0.5 + 1 and pct <= 0.45:
                return self.a_call()
            return self.a_fold()
        # facing a raise
        rbet = max(bets)
        rstack_total = stacks[raiser] + bets[raiser] if raiser >= 0 else rbet
        l = self.loose(raiser) if raiser >= 0 else 0.25
        need = to_call / float(pot + to_call)
        allin_faced = raiser >= 0 and stacks[raiser] == 0
        commit = to_call >= 0.4 * stack or allin_faced or rbet >= 0.4 * (stack + mybet)
        if commit:
            # calling an all-in / big bet: width from pot odds and opener looseness
            w = 0.05 + 0.5 * max(0.0, 0.5 - need) + 0.35 * max(0.0, l - 0.15)
            if raises >= 2:
                w *= 0.7
            if eff_bb <= 6:
                w *= 1.3
            w = min(w, 0.6)
            if pct <= w:
                if pct <= 0.04 and self.can_raise and not allin_faced:
                    return self.a_allin()
                return self.a_call()
            return self.a_fold()
        # non-committing raise
        if eff_bb <= 18:
            # reshove range
            w = 0.04 + 0.3 * max(0.0, l - 0.12)
            if nb == 0:
                w *= 1.3
            if pct <= w:
                self.pf_aggr = True
                return self.a_allin()
            if pct <= 0.12 and to_call <= 0.12 * stack:
                return self.a_call()
            return self.a_fold()
        if raises >= 2:
            if pct <= 0.02:
                return self.a_allin()
            if pct <= 0.05 and to_call <= 0.25 * stack:
                return self.a_call()
            return self.a_fold()
        tw = 0.035 + 0.15 * max(0.0, l - 0.15)
        if pct <= tw:
            self.pf_aggr = True
            target = rbet * 3 + (pot - sum(bets))  # rough
            if target > 0.4 * (stack + mybet):
                return self.a_allin()
            return self.a_raise(target)
        cw = 0.13 + 0.25 * max(0.0, l - 0.15)
        if to_call <= 2 * bb + 1:
            cw += 0.08
        if nb == 0:
            cw += 0.05
        if to_call > 0.15 * stack:
            cw *= 0.6
        if pct <= cw:
            return self.a_call()
        return self.a_fold()

    # ---------- postflop ----------
    def strength(self, hole, board):
        """Rough equity vs one unknown hand and outs info."""
        bv = value(board)
        bcat = bv >> 20
        best = -1
        bkeep = None
        for keep in combinations(hole, 2):
            v = value(list(keep) + board)
            if v > best:
                best = v
                bkeep = keep
        cat = best >> 20
        brs = sorted((c >> 2 for c in board), reverse=True)
        top = brs[0]
        e = 0.2
        if cat >= 4 and cat > bcat:
            e = 0.9
            if cat == 4:
                # straight: worse if flush possible on board
                sc = [0, 0, 0, 0]
                for c in board:
                    sc[c & 3] += 1
                if max(sc) >= 3:
                    e = 0.72
                # board-paired straights weaker
                if len(set(brs)) < len(brs):
                    e -= 0.08
            elif cat == 5:
                hi_flush = max((c >> 2) for c in bkeep)
                e = 0.82 + 0.012 * hi_flush
                if len(set(brs)) < len(brs):
                    e -= 0.08
        elif cat == 3 and bcat < 3:
            pr = (best >> 16) & 15
            # set (pocket pair) vs trips with board pair
            if bcat == 1:
                e = 0.8
            else:
                e = 0.9
        elif cat == 2 and bcat < 2:
            if bcat == 1:
                # board pair + our pair
                pr = (best >> 16) & 15
                pr2 = (best >> 12) & 15
                bp = (bv >> 16) & 15
                mine = pr if pr != bp else pr2
                e = 0.45 + 0.02 * mine
                if mine > top:
                    e = 0.7
            else:
                e = 0.78
        elif cat == 1 and bcat == 0:
            pr = (best >> 16) & 15
            hr = [c >> 2 for c in bkeep]
            kick = max([r for r in hr if r != pr] or [0])
            if hr[0] == hr[1] and pr > top:
                e = 0.68 + 0.015 * pr
            elif pr == top:
                e = 0.55 + 0.012 * kick
            elif pr >= brs[1]:
                e = 0.42 + 0.01 * pr
            else:
                e = 0.32 + 0.008 * pr
        elif cat == bcat:
            hr = max(c >> 2 for c in hole)
            e = 0.12 + 0.012 * hr
            if cat >= 1:
                e = 0.15 + 0.01 * hr
        else:
            e = 0.3
        # draws
        outs = 0
        if len(board) < 5:
            cards = list(bkeep) + board
            best_outs = 0
            for keep in combinations(hole, 2):
                cs = list(keep) + board
                o = 0
                sc = [0, 0, 0, 0]
                for c in cs:
                    sc[c & 3] += 1
                fd = False
                for c in keep:
                    if sc[c & 3] == 4:
                        fd = True
                if fd:
                    o += 9
                m = 0
                bm = 0
                for c in cs:
                    m |= 1 << (c >> 2)
                for c in board:
                    bm |= 1 << (c >> 2)
                if STOP[m] < 0:
                    so = 0
                    for r in range(13):
                        if not (m >> r) & 1 and STOP[m | 1 << r] >= 0 and STOP[bm | 1 << r] < 0:
                            so += 1
                    o += 4 * so if not fd else 3 * so
                if o > best_outs:
                    best_outs = o
            outs = best_outs
            if outs and e < 0.7:
                left = 2 if len(board) == 3 else 1
                de = min(0.55, outs * (0.04 if left == 2 else 0.021))
                e = e + de * (1 - e) * 0.9
        return e, outs

    def postflop(self, obs, stack, mybet, to_call, pot, eff, bb, opps, behind, raises, raiser):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        st = obs["street_index"]
        e, outs = self.strength(hole, board)
        n_opp = len(opps)
        # multiway discount
        em = e ** (1.0 + 0.6 * (n_opp - 1))
        rng = self.rng
        if to_call == 0:
            if em >= 0.62:
                frac = 0.66 if em < 0.85 else 0.75
                return self.bet_pot(frac, pot, stack, mybet)
            if outs >= 8 and n_opp <= 2 and st < 3 and rng.random() < 0.5:
                return self.bet_pot(0.55, pot, stack, mybet)
            if self.pf_aggr and n_opp == 1 and st == 1 and rng.random() < 0.55:
                return self.bet_pot(0.5, pot, stack, mybet)
            if n_opp == 1 and st == 3 and e < 0.3 and len(behind) == 0 and rng.random() < 0.25:
                return self.bet_pot(0.6, pot, stack, mybet)
            return {"action": "check"}
        need = to_call / float(pot + to_call)
        # opponent bet strengthens their range
        betfrac = to_call / float(max(1, pot - to_call))
        l = self.loose(raiser) if raiser >= 0 else 0.25
        adj = 0.06 + 0.06 * min(betfrac, 1.5) + 0.07 * (raises - 1) - 0.25 * max(0.0, l - 0.2)
        ea = em - adj
        if ea >= 0.75 and self.can_raise and raises <= 2:
            target = mybet + to_call + (pot + to_call) * 0.8
            if target > 0.45 * (stack + mybet):
                return self.a_allin()
            return self.a_raise(target)
        if ea >= need + 0.03:
            return self.a_call()
        return self.a_fold()

    def bet_pot(self, frac, pot, stack, mybet):
        target = mybet + frac * pot
        if stack + mybet - target < 0.35 * (pot + 2 * target):
            return self.a_allin()
        return self.a_raise(max(target, self.obs["bb"]))


def can_check(obs):
    return "check" in obs["legal"]
