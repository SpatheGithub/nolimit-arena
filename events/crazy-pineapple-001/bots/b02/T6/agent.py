import json
import os
import random
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}

_D = json.load(open(os.path.join(os.path.dirname(__file__), "pre2.json")))
EQ = [[x / 1e4 for x in row] for row in _D["eq"]]


def _top(k):
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
    return out


TOP1, TOP2, TOP3, TOP5 = _top(1), _top(2), _top(3), _top(5)


def _stops():
    tops = {}
    for i in range(9):
        tops[sum(1 << r for r in range(i, i + 5))] = i + 4
    tops[(1 << 12) | 15] = 3
    ordered = sorted(tops.items(), key=lambda t: -t[1])
    out = [-1] * 8192
    for m in range(8192):
        for sm, t in ordered:
            if m & sm == sm:
                out[m] = t
                break
    return out


STOP = _stops()


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


def cls2(a, b):
    ra, rb = a >> 2, b >> 2
    hi, lo = max(ra, rb), min(ra, rb)
    if ra == rb:
        return hi * 13 + hi
    if (a & 3) == (b & 3):
        return hi * 13 + lo
    return lo * 13 + hi


def pre_strength(cards, k):
    """Equity proxy for a 3-card hand vs k random hands."""
    k = max(1, min(7, k))
    es = sorted((EQ[cls2(a, b)][k - 1] for a, b in combinations(cards, 2)), reverse=True)
    base = EQ[cls2(*cards[:2])][k - 1] if len(cards) == 2 else es[0]
    if len(cards) < 3:
        return base
    return es[0] + 0.25 * max(0.0, es[1] - es[0] * 0.8) + 0.1 * max(0.0, es[2] - es[0] * 0.8)


def draw_info(hole, board):
    """Return (flush_draw, straight_outs) using hole cards."""
    allc = hole + board
    fd = 0
    for s in range(4):
        n = sum(1 for c in allc if c & 3 == s)
        nh = sum(1 for c in hole if c & 3 == s)
        if n == 4 and nh >= 1:
            fd = 2 if nh == 2 else 1
    m = 0
    for c in allc:
        m |= 1 << (c >> 2)
    hm = 0
    for c in hole:
        hm |= 1 << (c >> 2)
    outs = 0
    if STOP[m] < 0:
        for r in range(13):
            if not (m >> r) & 1:
                mm = m | 1 << r
                if STOP[mm] >= 0:
                    outs += 1
    return fd, outs


def made_strength(hole, board):
    """Heuristic equity vs one random-ish opponent hand on this board."""
    v = value(hole + board)
    cat = v >> 20
    bv = value(board) if len(board) >= 1 else 0
    bcat = bv >> 20
    brs = sorted({c >> 2 for c in board}, reverse=True)
    top = brs[0] if brs else 0
    hr = [c >> 2 for c in hole]
    # does our hand improve on the board alone?
    if cat >= 8:
        s = 0.99
    elif cat == 7:
        s = 0.98 if bcat < 7 else 0.6
    elif cat == 6:
        s = 0.95 if bcat < 6 else 0.55
        if bcat == 3:
            s = 0.85
    elif cat == 5:
        fs = [c for c in board if True]
        # flush: rank of our highest flush card
        suitc = [0, 0, 0, 0]
        for c in board:
            suitc[c & 3] += 1
        fsuit = max(range(4), key=lambda x: suitc[x])
        mine = [c >> 2 for c in hole if c & 3 == fsuit]
        hi = max(mine) if mine else -1
        if not mine:
            s = 0.5
        else:
            s = 0.82 + 0.015 * hi
        if bcat >= 1 and len(board) >= 4:
            s -= 0.08
    elif cat == 4:
        s = 0.86
        suitc = [0, 0, 0, 0]
        for c in board:
            suitc[c & 3] += 1
        mx = max(suitc)
        if mx >= 3:
            s -= 0.12 if mx == 3 else 0.3
        if bcat == 4:
            s = 0.5
        if bcat >= 1:
            s -= 0.06
    elif cat == 3:
        t = (v >> 16) & 15
        if bcat == 3:
            s = 0.35 + 0.02 * max(hr)
        elif hr.count(t) == 2:
            s = 0.9
        else:
            s = 0.78 + 0.008 * t
    elif cat == 2:
        p1 = (v >> 16) & 15
        p2 = (v >> 12) & 15
        uses = sum(1 for r in (p1, p2) if r in hr)
        if bcat == 2:
            s = 0.25 + 0.02 * max(hr)
        elif uses == 2 and hr[0] != hr[1]:
            s = 0.78 + 0.005 * p1
        elif hr[0] == hr[1] and hr[0] > top:
            s = 0.68
        elif uses >= 1:
            s = 0.55 + 0.012 * max(p1 if p1 in hr else p2, 0)
        else:
            s = 0.4
    elif cat == 1:
        p = (v >> 16) & 15
        if bcat >= 1:
            s = 0.15 + 0.025 * max(hr)
        elif hr[0] == hr[1] and p > top:
            s = 0.58 + 0.015 * p
        elif p == top:
            kick = max(r for r in hr if r != p) if any(r != p for r in hr) else 0
            s = 0.5 + 0.012 * kick
        elif len(brs) > 1 and p >= brs[1]:
            s = 0.38
        else:
            s = 0.28
    else:
        s = 0.06 + 0.012 * max(hr)
    n_to_come = 5 - len(board)
    if n_to_come > 0 and cat < 5:
        fd, outs = draw_info(hole, board)
        o = 0
        if fd:
            o += 9 if fd == 2 else 7
        o += min(outs, 2) * 4
        if o:
            de = min(0.65, o * (0.04 if n_to_come == 2 else 0.021))
            s = s + (1 - s) * de * 0.8
    return s


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        self.stats = {}
        self.keep = None

    def st(self, s):
        d = self.stats.get(s)
        if d is None:
            d = self.stats[s] = [0, 0, 0, 0, 0]  # hands, vpip, pfr, aggr postflop, calls postflop
        return d

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history", [])
            seen = set()
            vp = set()
            pr = set()
            for h in hist:
                st_i, s, a = h[0], h[1], h[2]
                if a in ("sb", "bb", "ante"):
                    seen.add(s)
                    continue
                seen.add(s)
                if st_i == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    d = self.st(s)
                    if a == "raise":
                        d[3] += 1
                    elif a == "call":
                        d[4] += 1
            for s in seen:
                d = self.st(s)
                d[0] += 1
                if s in vp:
                    d[1] += 1
                if s in pr:
                    d[2] += 1
        except Exception:
            pass

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    # ------------------------------------------------------------------
    def _discard(self, obs):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        best = None
        bs = -1
        for keep in combinations(range(len(hole)), len(hole) - obs["n_discard"]):
            kc = [hole[i] for i in keep]
            s = made_strength(kc, board)
            if s > bs:
                bs, best = s, keep
        disc = [obs["hole"][i] for i in range(len(hole)) if i not in best]
        return {"action": "discard", "cards": disc}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return self._discard(obs)
        legal = obs["legal"]
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        bb = max(1, obs["bb"])
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_stack = stacks[me]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        eff = min(my_stack + bets[me], max([stacks[s] + bets[s] for s in opps] or [0]))
        eff_bb = eff / bb
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        street = obs["street_index"]
        can_raise = "raise" in legal or "bet" in legal
        minr, maxr = obs["min_raise_to"], obs["max_raise_to"]

        def do_fold():
            return {"action": "check"} if "check" in legal else {"action": "fold"}

        def do_call():
            if to_call == 0:
                return {"action": "check"}
            return {"action": "call"}

        def do_raise(to):
            if not can_raise or maxr <= 0:
                return do_call()
            to = int(max(minr, min(maxr, to)))
            if to >= maxr * 0.85:
                to = maxr
            return {"action": "raise", "amount": to}

        def do_allin():
            if can_raise and maxr > 0:
                return {"action": "raise", "amount": maxr}
            return do_call()

        n_alive = len(alive)
        # ICM pressure: fewer players near the money -> tighter calling
        if street == 0:
            return self._preflop(obs, hole, n_opp, eff_bb, to_call, pot, bb, my_stack, bets, me,
                                 do_fold, do_call, do_raise, do_allin, n_alive)
        # postflop
        if len(hole) == 3:
            s = max(made_strength([hole[i], hole[j]], board) for i, j in ((0, 1), (0, 2), (1, 2)))
        else:
            s = made_strength(hole, board)
        eq = s ** (0.75 + 0.6 * max(0, n_opp - 1) / 1.0) if n_opp > 1 else s
        hist = obs["history"]
        # aggression from opponents this street
        raises_this = sum(1 for h in hist if h[0] == street and h[2] == "raise" and h[1] != me)
        pre_raiser = None
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                pre_raiser = h[1]
        spr = my_stack / max(1, pot)
        if to_call == 0:
            r = self.rng.random()
            if eq >= 0.72:
                frac = 0.75 if eq < 0.9 else 0.85
                return do_raise(bets[me] + max(bb, int(pot * frac)))
            if eq >= 0.55 and n_opp <= 2 and r < 0.7:
                return do_raise(bets[me] + max(bb, int(pot * 0.55)))
            if pre_raiser == me and n_opp <= 2 and street == 1 and r < 0.55:
                return do_raise(bets[me] + max(bb, int(pot * 0.45)))
            if n_opp == 1 and street == 3 and eq < 0.2 and r < 0.15:
                return do_raise(bets[me] + max(bb, int(pot * 0.6)))
            return do_fold()
        # facing a bet
        price = to_call / (pot + to_call)
        bet_frac = to_call / max(1, pot - to_call)
        adj = eq - 0.08 * min(2.0, bet_frac) - 0.05 * max(0, raises_this - 1)
        # opponent tendencies: loose aggressive bettor -> less discount
        agg = 0
        for h in reversed(hist):
            if h[0] == street and h[2] == "raise" and h[1] != me:
                d = self.stats.get(h[1])
                if d and d[0] >= 10:
                    agg = (d[3] + 1) / (d[3] + d[4] + 3)
                break
        if agg > 0.6:
            adj += 0.05
        commit = to_call >= my_stack * 0.6 or spr < 1.2
        if adj >= 0.85 and can_raise:
            return do_raise(bets[me] + to_call + int((pot + to_call) * 0.9))
        if commit:
            return do_call() if adj >= price + 0.02 else do_fold()
        if adj >= price + 0.07:
            if adj >= 0.75 and can_raise and self.rng.random() < 0.5:
                return do_raise(bets[me] + to_call + int((pot + to_call) * 0.75))
            return do_call()
        return do_fold()

    def _preflop(self, obs, hole, n_opp, eff_bb, to_call, pot, bb, my_stack, bets, me,
                 do_fold, do_call, do_raise, do_allin, n_alive):
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        n_raises = len(raises)
        cur_bet = max(bets)
        # players still to act after me (approx)
        n_players = len(obs["in_hand"])
        k = max(1, n_players - 1)
        s1 = pre_strength(hole, 1)
        sk = pre_strength(hole, min(7, k))
        # position: number of players yet to act behind me
        order = obs["alive"]
        btn = obs["button"]
        # stealing position: seats after me before the button
        n = len(order)
        idx = order.index(me) if me in order else 0
        bidx = order.index(btn) if btn in order else 0
        behind = (bidx - idx) % n  # players acting after me until button (0 = button)
        if me == obs["sb_seat"]:
            behind = 1
        if me == obs["bb_seat"]:
            behind = 0
        late = behind <= 1
        stack_bb = my_stack / bb
        # ---- short stack: push/fold ----
        if eff_bb <= 13 or (my_stack + bets[me]) / bb <= 13:
            if n_raises == 0:
                need = (0.67 if behind >= 5 else 0.645 if behind >= 3 else 0.625 if behind >= 2 else 0.60) - 0.006 * (13 - min(13, eff_bb))
                if n_alive <= 3:
                    need -= 0.02
                if s1 >= need:
                    return do_allin()
                if to_call == 0:
                    return do_call()
                return do_fold()
            # facing a raise/all-in
            price = to_call / (pot + to_call)
            raiser = raises[-1][1]
            d = self.stats.get(raiser)
            loose = 0.0
            if d and d[0] >= 8:
                loose = (d[2] / d[0])
            # equity vs a raising range ~ discount
            eqv = s1 - 0.17 + 0.3 * min(0.4, loose)
            if n_raises >= 2:
                eqv -= 0.05
            if eqv >= price + 0.03 or (s1 >= 0.75):
                return do_allin()
            return do_fold()
        # ---- deeper play ----
        if n_raises == 0:
            limpers = sum(1 for h in hist if h[0] == 0 and h[2] == "call")
            need = 0.68 if behind >= 4 else 0.657 if behind >= 2 else 0.633
            if me == obs["sb_seat"] and limpers == 0:
                need = 0.63
            if me == obs["bb_seat"] and to_call == 0:
                if s1 >= 0.70:
                    return do_raise(bb * (3 + limpers))
                return do_call()
            if s1 >= need:
                size = bb * (2.5 + limpers) if eff_bb > 25 else bb * 2.2
                return do_raise(size)
            if limpers >= 1 and s1 >= need - 0.02 and to_call <= bb:
                return do_call()
            return do_fold()
        # facing raise
        raiser = raises[-1][1]
        d = self.stats.get(raiser)
        pfr = (d[2] + 1) / (d[0] + 6) if d else 0.17
        price = to_call / (pot + to_call)
        rsize = to_call / bb
        three_bet = 0.775 - (0.025 if pfr > 0.3 else 0)
        if n_raises >= 2:
            three_bet = 0.80
        if s1 >= three_bet:
            if to_call >= my_stack * 0.35 or n_raises >= 2 and s1 >= 0.80:
                return do_allin()
            return do_raise(cur_bet * 3 + 0)
        call_need = 0.69 + 0.004 * min(10, rsize) - (0.02 if pfr > 0.3 else 0)
        if to_call >= my_stack * 0.35:
            call_need = 0.75 - (0.03 if pfr > 0.35 else 0)
        if s1 >= call_need and to_call <= my_stack:
            return do_call()
        if me == obs["bb_seat"] and price < 0.25 and s1 >= 0.65:
            return do_call()
        return do_fold()
