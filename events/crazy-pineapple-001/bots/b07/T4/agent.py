import random
from itertools import combinations

RANKS = '23456789TJQKA'


def _parse(c):
    return (RANKS.index(c[0]), c[1])


def _chen2(a, b):
    ra, sa = a
    rb, sb = b
    hi, lo = max(ra, rb), min(ra, rb)
    pts = {12: 10, 11: 8, 10: 7, 9: 6}.get(hi, (hi + 2) / 2.0)
    if ra == rb:
        return max(5, pts * 2)
    s = pts
    if sa == sb:
        s += 2
    gap = hi - lo - 1
    s -= (0, 1, 2, 4)[gap] if gap < 4 else 5
    if gap <= 1 and hi < 10:
        s += 1
    return s


def _score3(cards):
    sc = sorted((_chen2(a, b) for a, b in combinations(cards, 2)), reverse=True)
    return sc[0] + 0.2 * sc[1] + 0.1 * sc[2]


# percentile table for 3-card preflop hands
_PCT = {}


def _build():
    deck = [(r, s) for r in range(13) for s in 'cdhs']
    vals = []
    for combo in combinations(deck, 3):
        vals.append((_score3(combo), combo))
    vals.sort(key=lambda x: x[0])
    n = len(vals)
    for i, (v, combo) in enumerate(vals):
        _PCT[frozenset(combo)] = i / float(n)


_build()


def _straight_high(rset):
    bits = 0
    for r in rset:
        bits |= 1 << (r + 1)
    if bits & (1 << 13):
        bits |= 1
    for top in range(13, 3, -1):
        m = 0b11111 << (top - 4)
        if bits & m == m:
            return top - 1
    return -1


def evaluate(cards):
    rc = [0] * 13
    suits = {}
    for r, s in cards:
        rc[r] += 1
        suits.setdefault(s, []).append(r)
    for s, rs in suits.items():
        if len(rs) >= 5:
            sh = _straight_high(rs)
            if sh >= 0:
                return (8, sh)
            fl = sorted(rs, reverse=True)[:5]
            flush = (5,) + tuple(fl)
            break
    else:
        flush = None
    quads = [r for r in range(12, -1, -1) if rc[r] == 4]
    trips = [r for r in range(12, -1, -1) if rc[r] == 3]
    pairs = [r for r in range(12, -1, -1) if rc[r] == 2]
    singles = [r for r in range(12, -1, -1) if rc[r] == 1]
    if quads:
        q = quads[0]
        k = max([r for r in range(13) if rc[r] and r != q] or [0])
        return (7, q, k)
    if trips and (len(trips) > 1 or pairs):
        t = trips[0]
        p = max(([trips[1]] if len(trips) > 1 else []) + pairs[:1])
        return (6, t, p)
    if flush:
        return flush
    sh = _straight_high([r for r in range(13) if rc[r]])
    if sh >= 0:
        return (4, sh)
    if trips:
        t = trips[0]
        ks = [r for r in range(12, -1, -1) if rc[r] and r != t][:2]
        return (3, t) + tuple(ks)
    if len(pairs) >= 2:
        a, b = pairs[0], pairs[1]
        k = max([r for r in range(13) if rc[r] and r != a and r != b] or [0])
        return (2, a, b, k)
    if pairs:
        p = pairs[0]
        return (1, p) + tuple(singles[:3])
    return (0,) + tuple(singles[:5])


def _draws(hole, board):
    """Return (flush_draw, straight_outs) using at least one hole card."""
    cards = hole + board
    fd = False
    sc = {}
    for r, s in cards:
        sc[s] = sc.get(s, 0) + 1
    for s, n in sc.items():
        if n == 4 and any(h[1] == s for h in hole):
            fd = True
    ranks = set(r for r, s in cards)
    branks = set(r for r, s in board)
    outs = 0
    if _straight_high(ranks) < 0:
        for add in range(13):
            if add in ranks:
                continue
            nr = ranks | {add}
            sh = _straight_high(nr)
            if sh >= 0 and _straight_high(branks | {add}) < 0:
                outs += 1
    return fd, outs


def strength(hole, board):
    """Approximate showdown win probability vs one random hand."""
    full = evaluate(hole + board)
    cat = full[0]
    brc = [0] * 13
    for r, s in board:
        brc[r] += 1
    bmax = max(r for r, s in board)
    h = sorted([r for r, s in hole], reverse=True)
    hset = set(h)
    bsuit = {}
    for r, s in board:
        bsuit[s] = bsuit.get(s, 0) + 1
    flushy = max(bsuit.values())
    paired_board = max(brc) >= 2
    if len(board) == 5:
        if evaluate(board) >= full:
            return 0.15
    if cat >= 7:
        s = 0.99
    elif cat == 6:
        s = 0.95 if max(brc) < 3 else 0.85
    elif cat == 5:
        top = max([r for r, su in hole if bsuit.get(su, 0) >= 3] or [0])
        s = 0.84 + 0.012 * (top - 6)
        if paired_board:
            s -= 0.08
    elif cat == 4:
        s = 0.82
        if flushy >= 3:
            s -= 0.1
        if paired_board:
            s -= 0.06
    elif cat == 3:
        t = full[1]
        if brc[t] == 1:
            s = 0.88  # set
        elif brc[t] == 2:
            s = 0.74 + 0.01 * (h[0] if h[0] != t else h[1]) / 1.0
        else:
            s = 0.2 + 0.02 * h[0]
        if flushy >= 3:
            s -= 0.06
    elif cat == 2:
        a, b = full[1], full[2]
        ina, inb = brc[a] < 2, brc[b] < 2
        if ina and inb:
            if h[0] == h[1]:
                s = 0.6
            else:
                s = 0.74 if a == bmax else 0.68
        elif ina or inb:
            p = a if ina else b
            if h[0] == h[1] and p == h[0]:
                s = 0.62 if p > bmax else 0.45
            else:
                s = 0.58 if p == bmax else 0.48
                kick = h[0] if h[0] != p else h[1]
                s += 0.005 * kick
        else:
            s = 0.18 + 0.02 * h[0]
        if flushy >= 3:
            s -= 0.05
    elif cat == 1:
        p = full[1]
        if brc[p] == 0:  # pocket pair
            s = 0.62 + 0.01 * p if p > bmax else 0.38 + 0.01 * p
        elif brc[p] == 1:
            kick = h[0] if h[0] != p else h[1]
            if p == bmax:
                s = 0.52 + 0.008 * kick
            else:
                s = 0.38 + 0.01 * p
        else:
            s = 0.1 + 0.015 * h[0]
        if flushy >= 3:
            s -= 0.05
    else:
        s = 0.04 + 0.012 * h[0]
    if len(board) < 5:
        fd, outs = _draws(hole, board)
        left = 5 - len(board)
        d = 0.0
        if fd:
            d += 0.35 if left == 2 else 0.19
        if outs >= 2:
            d += 0.3 if left == 2 else 0.16
        elif outs == 1:
            d += 0.16 if left == 2 else 0.09
        d = min(d, 0.55)
        if cat < 4:
            s = s + d * (1 - s) * 0.85
    return max(0.0, min(1.0, s))


def best_keep(hole, board):
    best = None
    for keep in combinations(hole, 2):
        st = strength(list(keep), board)
        if best is None or st > best[0]:
            best = (st, keep)
    return best


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.n_seats = config.get("seats", 8)
        self.hands = {}
        self.pfr = {}
        self.vpip = {}
        self.preflop_aggr = False

    # ------------------------------------------------------------ helpers
    def _act(self, obs, kind, amount=None):
        legal = obs["legal"]
        if kind == "raise":
            if "raise" not in legal and "bet" not in legal:
                kind = "call" if "call" in legal else "check"
            else:
                lo, hi = obs["min_raise_to"], obs["max_raise_to"]
                amt = int(max(lo, min(hi, amount)))
                if amt >= hi:
                    return {"action": "allin"}
                return {"action": "raise" if "raise" in legal else "bet", "amount": amt}
        if kind == "allin":
            if "raise" in legal or "bet" in legal:
                return {"action": "allin"}
            kind = "call" if "call" in legal else "check"
        if kind == "call":
            if "call" in legal:
                return {"action": "call"}
            kind = "check"
        if kind == "check" and "check" in legal:
            return {"action": "check"}
        if "check" in legal:
            return {"action": "check"}
        return {"action": "fold"}

    def _loose(self, seat):
        n = self.hands.get(seat, 0)
        if n < 8:
            return 0.0
        return self.pfr.get(seat, 0) / float(n)

    # ------------------------------------------------------------ main
    def act(self, obs):
        try:
            return self._decide(obs)
        except Exception:
            if obs["phase"] == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    def _decide(self, obs):
        hole = [_parse(c) for c in obs["hole"]]
        board = [_parse(c) for c in obs["board"]]
        if obs["phase"] == "discard":
            st, keep = best_keep(hole, board)
            disc = [obs["hole"][i] for i, c in enumerate(hole) if c not in keep][:obs["n_discard"]]
            return {"action": "discard", "cards": disc}
        if obs["street_index"] == 0:
            return self._preflop(obs, hole)
        return self._postflop(obs, hole, board)

    def _preflop(self, obs, hole):
        me = self.seat
        bb = max(1, obs["bb"])
        stacks, bets = obs["stacks"], obs["bets"]
        p = _PCT.get(frozenset(hole), 0.5)
        to_call = obs["to_call"]
        pot = obs["pot"]
        mystack = stacks[me] + bets[me]
        others = [stacks[s] + bets[s] for s in obs["in_hand"] if s != me]
        eff = min(mystack, max(others) if others else mystack)
        eff_bb = eff / float(bb)
        hist = [h for h in obs["history"] if h[0] == 0]
        raises = [h for h in hist if h[2] == "raise"]
        nraise = len(raises)
        # order
        alive = sorted(obs["alive"])
        bbs = obs["bb_seat"]
        idx = 0
        for i, s in enumerate(alive):
            if s > bbs:
                idx = i
                break
        else:
            idx = 0
        order = alive[idx:] + alive[:idx]
        behind = len(order) - 1 - order.index(me) if me in order else 0
        nplayers = len(alive)
        # ICM-ish tightening when many players and moderate stack
        tight = 0.0
        if nplayers <= 4:
            tight -= 0.05
        self.preflop_aggr = False
        if eff_bb <= 13:
            # push / fold
            if nraise == 0:
                thr = 0.36 + 0.065 * behind - 0.012 * (13 - eff_bb)
                thr = max(0.25, min(0.9, thr + tight))
                if p >= thr:
                    self.preflop_aggr = True
                    return self._act(obs, "allin")
                if to_call == 0:
                    return self._act(obs, "check")
                return self._act(obs, "fold")
            odds = to_call / float(pot + to_call)
            thr = 0.72 + max(0.0, odds - 0.3) * 0.7
            raiser = raises[-1][1]
            if self._loose(raiser) > 0.35:
                thr -= 0.08
            if to_call <= bb * 0.5 + 1 and nraise == 0:
                thr = 0.3
            if p >= min(0.95, thr):
                if p > 0.9:
                    return self._act(obs, "allin")
                return self._act(obs, "call")
            return self._act(obs, "fold")
        if nraise == 0:
            limpers = len([h for h in hist if h[2] == "call"])
            thr = {0: 0.6, 1: 0.6, 2: 0.66, 3: 0.72, 4: 0.78}.get(behind, 0.82)
            thr += tight
            if p >= thr:
                self.preflop_aggr = True
                amt = bb * (2.5 + limpers) + bets[me] * 0
                if obs["sb_seat"] == me:
                    amt = bb * 3
                return self._act(obs, "raise", amt)
            if to_call == 0:
                return self._act(obs, "check")
            if obs["sb_seat"] == me and p >= 0.5 and to_call <= bb / 2:
                return self._act(obs, "call")
            return self._act(obs, "fold")
        raiser = raises[-1][1]
        loose = self._loose(raiser) > 0.3
        adj = -0.05 if loose else 0.0
        odds = to_call / float(pot + to_call)
        cost_frac = to_call / float(max(1, mystack))
        if nraise == 1:
            if p >= 0.95 + adj:
                self.preflop_aggr = True
                tgt = raises[-1][3] * 3 + bets[me] * 0
                if tgt > mystack * 0.4:
                    return self._act(obs, "allin")
                return self._act(obs, "raise", tgt)
            callthr = 0.84 + adj
            if obs["bb_seat"] == me:
                callthr -= 0.07
            if cost_frac > 0.25:
                callthr += 0.06
            if p >= callthr:
                return self._act(obs, "call")
            return self._act(obs, "fold")
        # facing 3bet+
        if p >= 0.975 + adj:
            return self._act(obs, "allin")
        if p >= 0.93 + adj and cost_frac < 0.3:
            return self._act(obs, "call")
        if p >= 0.95 + adj:
            return self._act(obs, "call")
        return self._act(obs, "fold")

    def _postflop(self, obs, hole, board):
        me = self.seat
        if len(hole) > 2:
            s, keep = best_keep(hole, board)
        else:
            s = strength(hole, board)
        n_opp = max(1, len(obs["in_hand"]) - 1)
        s_eff = s ** (1 + 0.55 * (n_opp - 1))
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks, bets = obs["stacks"], obs["bets"]
        mystack = stacks[me]
        cur = bets[me] + to_call
        street = obs["street_index"]
        if to_call == 0:
            if s_eff > 0.7:
                return self._act(obs, "raise", bets[me] + pot * 0.7)
            if s_eff > 0.58 and n_opp <= 2:
                return self._act(obs, "raise", bets[me] + pot * 0.55)
            fd, outs = _draws(hole[:2], board) if len(hole) == 2 else (False, 0)
            if street < 3 and (fd or outs >= 2) and self.rng.random() < 0.5:
                return self._act(obs, "raise", bets[me] + pot * 0.55)
            if self.preflop_aggr and n_opp == 1 and street == 1 and self.rng.random() < 0.55:
                return self._act(obs, "raise", bets[me] + pot * 0.5)
            return self._act(obs, "check")
        odds = to_call / float(pot + to_call)
        bet_frac = to_call / float(max(1, pot - to_call))
        need = odds + 0.06 + 0.12 * min(1.5, bet_frac)
        # opponent read: aggressive bettors bluff more
        last_aggr = None
        for h in obs["history"]:
            if h[0] == street and h[2] in ("raise", "bet"):
                last_aggr = h[1]
        if last_aggr is not None and self._loose(last_aggr) > 0.35:
            need -= 0.06
        if s_eff > 0.85 or (s_eff > 0.78 and to_call < pot * 0.4):
            tgt = cur + (pot + to_call) * 0.8
            if tgt > mystack * 0.45 + bets[me]:
                return self._act(obs, "allin")
            return self._act(obs, "raise", tgt)
        if s_eff >= need:
            return self._act(obs, "call")
        return self._act(obs, "fold")

    def observe(self, event):
        try:
            hist = event.get("history", [])
            seen = set()
            pf = set()
            vp = set()
            for h in hist:
                st, seat, a = h[0], h[1], h[2]
                seen.add(seat)
                if st == 0 and a == "raise":
                    pf.add(seat)
                if st == 0 and a in ("raise", "call"):
                    vp.add(seat)
            for s in seen:
                self.hands[s] = self.hands.get(s, 0) + 1
            for s in pf:
                self.pfr[s] = self.pfr.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
        except Exception:
            pass
