import json
import os
import random

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "pre.json")) as _f:
    _PRE = json.load(_f)
PCT = _PRE["pct"]
EQR = _PRE["eqr"]
MW = _PRE["mw"]
ICM = {int(k): v for k, v in _PRE["icm"].items()}
ICM_W = 0.5


def icm_eq(n, x, w=ICM_W):
    if n < 2:
        return 100.0
    if n > 8:
        n = 8
    row = ICM[n]
    if x <= 0:
        return row[0]
    if x >= 1:
        return row[200]
    f = x * 200
    i = int(f)
    t = f - i
    v = row[i] * (1 - t) + row[i + 1] * t
    if w < 1.0:
        lin = row[0] + x * (sum(row_pts(n)) - n * row[0])
        v = w * v + (1 - w) * lin
    return v


def row_pts(n):
    return [100, 60, 40, 25, 15, 10, 5, 0][:n]

RANKS = "23456789TJQKA"
RIDX = {r: i for i, r in enumerate(RANKS)}
SIDX = {"c": 0, "d": 1, "h": 2, "s": 3}

# tunables
OPEN_PCT = {1: 0.48, 2: 0.33, 3: 0.23, 4: 0.18, 5: 0.14, 6: 0.12, 7: 0.11}
BLIND_COST = 0.3
PUSH_DEPTH = 14.0      # eff stack in bb at/below which we play push/fold first-in
CALL_MARGIN = 0.0


def cls_index(hole):
    r1, s1 = RIDX[hole[0][0]], hole[0][1]
    r2, s2 = RIDX[hole[1][0]], hole[1][1]
    hi, lo = (r1, r2) if r1 >= r2 else (r2, r1)
    if hi == lo:
        return hi * 13 + hi
    if s1 == s2:
        return hi * 13 + lo
    return lo * 13 + hi


def eq_vs(ci, pct):
    p = int(round(pct * 100))
    if p < 0:
        p = 0
    elif p > 100:
        p = 100
    return EQR[ci][p]


def shove_range(depth_bb):
    if depth_bb <= 4:
        return 0.55
    if depth_bb <= 7:
        return 0.40
    if depth_bb <= 10:
        return 0.30
    if depth_bb <= 15:
        return 0.22
    if depth_bb <= 25:
        return 0.15
    if depth_bb <= 40:
        return 0.10
    return 0.07


def call_range(shove_bb, is_bb):
    if shove_bb <= 3:
        c = 0.55
    elif shove_bb <= 5:
        c = 0.40
    elif shove_bb <= 8:
        c = 0.27
    elif shove_bb <= 12:
        c = 0.19
    elif shove_bb <= 18:
        c = 0.14
    elif shove_bb <= 25:
        c = 0.10
    else:
        c = 0.07
    if is_bb:
        c *= 1.35
    return min(c, 1.0)


# ---------- postflop hand features ----------
STRAIGHTS = []
for _top in range(12, 3, -1):
    STRAIGHTS.append((_top, sum(1 << (_top - k) for k in range(5))))
STRAIGHTS.append((3, (1 << 12) | 0b1111))


def straight_top(mask):
    for top, m in STRAIGHTS:
        if mask & m == m:
            return top
    return -1


def category(cards):
    """cards: list of (rank, suit). returns category 0..8"""
    rc = [0] * 13
    sc = [0, 0, 0, 0]
    mask = 0
    for r, s in cards:
        rc[r] += 1
        sc[s] += 1
        mask |= 1 << r
    fl = -1
    for s in range(4):
        if sc[s] >= 5:
            fl = s
    if fl >= 0:
        fm = 0
        for r, s in cards:
            if s == fl:
                fm |= 1 << r
        if straight_top(fm) >= 0:
            return 8
    cnts = sorted(rc, reverse=True)
    if cnts[0] >= 4:
        return 7
    if cnts[0] == 3 and cnts[1] >= 2:
        return 6
    if fl >= 0:
        return 5
    if straight_top(mask) >= 0:
        return 4
    if cnts[0] == 3:
        return 3
    if cnts[0] == 2 and cnts[1] == 2:
        return 2
    if cnts[0] == 2:
        return 1
    return 0


def post_strength(hole, board):
    """returns (made strength 0..1, draw equity bonus, flags)"""
    h = [(RIDX[c[0]], SIDX[c[1]]) for c in hole]
    b = [(RIDX[c[0]], SIDX[c[1]]) for c in board]
    cat = category(h + b)
    bcat = category(b) if len(b) >= 5 else _board_cat(b)
    h1, h2 = max(h[0][0], h[1][0]), min(h[0][0], h[1][0])
    brs = sorted({r for r, _ in b}, reverse=True)
    bcount = [0] * 13
    for r, _ in b:
        bcount[r] += 1
    top = brs[0]
    pocket = h1 == h2
    s = 0.1
    if cat >= 4 and cat > bcat:
        if cat == 4:
            s = 0.9
        elif cat == 5:
            # flush: check strength of our flush card
            sc = [0, 0, 0, 0]
            for _, su in b:
                sc[su] += 1
            fs = max(range(4), key=lambda x: sc[x] + (h[0][1] == x) + (h[1][1] == x))
            myhi = max([r for r, su in h if su == fs] or [0])
            s = 0.93 if (sc[fs] <= 3 or myhi >= 11) else 0.8
        elif cat == 6:
            s = _boat_strength(h1, h2, pocket, bcount)
        else:
            s = 0.97
        if max(bcount) >= 2 and cat in (4, 5):
            s -= 0.08
    elif cat == 3:
        if pocket and bcount[h1] == 1:
            s = 0.93
        elif bcat >= 3:
            s = 0.25 + 0.1 * (h1 >= 11)
        else:
            tr = h1 if bcount[h1] >= 2 else h2
            kick = h2 if tr == h1 else h1
            s = 0.78 + 0.07 * (kick >= 10)
    elif cat == 2:
        if (not pocket) and bcount[h1] >= 1 and bcount[h2] >= 1:
            s = 0.84 if h1 == top else 0.78
        elif bcat >= 2:
            s = 0.22 + 0.1 * (h1 >= 12)
        elif pocket:
            s = 0.72 if h1 > top else 0.42
        else:
            # one hole card pairs with board, board has its own pair
            pr = h1 if bcount[h1] >= 1 else h2
            s = 0.62 if pr == top else 0.45
    elif cat == 1:
        if bcat >= 1:
            s = 0.15 + 0.12 * (h1 == 12) + 0.06 * (h1 == 11)
        elif pocket:
            if h1 > top:
                s = 0.68 + 0.02 * (h1 - 8)
            elif h1 > (brs[1] if len(brs) > 1 else -1):
                s = 0.45
            else:
                s = 0.32
        else:
            pr = h1 if bcount[h1] >= 1 else h2
            kick = h2 if pr == h1 else h1
            if pr == top:
                s = 0.6 + 0.04 * max(0, kick - 7) / 1.0 * 0.25 + (0.06 if kick >= 12 else 0)
                s = min(s, 0.74)
            elif len(brs) > 1 and pr == brs[1]:
                s = 0.46
            else:
                s = 0.36
    else:
        s = 0.08 + 0.1 * (h1 == 12) + 0.05 * (h1 == 11) + 0.03 * (h2 >= 9)
    if cat <= 3 and len(b) >= 3:
        bsc0 = [0, 0, 0, 0]
        for _, su in b:
            bsc0[su] += 1
        mx = max(bsc0)
        if mx >= 4:
            s *= 0.75
        elif mx == 3 and len(b) >= 4:
            s *= 0.9
    # draws
    draw = 0.0
    nut_fd = False
    if len(b) < 5:
        sc = [0, 0, 0, 0]
        for _, su in h + b:
            sc[su] += 1
        bsc = [0, 0, 0, 0]
        for _, su in b:
            bsc[su] += 1
        for su in range(4):
            if sc[su] == 4 and bsc[su] <= 3 and cat < 5:
                draw = max(draw, 0.35 if len(b) == 3 else 0.19)
                myhi = max([r for r, x in h if x == su] or [0])
                nut_fd = myhi == 12
        if cat < 4:
            mask = 0
            for r, _ in h + b:
                mask |= 1 << r
            bmask = 0
            for r, _ in b:
                bmask |= 1 << r
            outs = 0
            for r in range(13):
                if not mask >> r & 1:
                    if straight_top(mask | 1 << r) >= 0 and straight_top(bmask | 1 << r) < 0:
                        outs += 1
            if outs >= 2:
                draw = max(draw, 0.31 if len(b) == 3 else 0.17) + (0.1 if draw > 0.2 else 0)
            elif outs == 1:
                draw = max(draw, 0.16 if len(b) == 3 else 0.09) + (0.05 if draw > 0.15 else 0)
    return s, draw, nut_fd


def _boat_strength(h1, h2, pocket, bcount):
    """full house: how much do our hole cards matter vs the board?"""
    allc = list(bcount)
    allc[h1] += 1
    allc[h2] += 1
    trips_b = [r for r in range(13) if bcount[r] >= 3]
    if trips_b:
        t = max(trips_b)
        if h1 == t or h2 == t:
            return 0.99
        if pocket:
            mypair = h1
        else:
            cand = [x for x in (h1, h2) if bcount[x] >= 1]
            mypair = max(cand) if cand else -1
        if mypair < 0:
            return 0.3
        higher = [r for r in range(13) if bcount[r] >= 1 and r != t and r > mypair]
        if higher:
            return 0.5
        return 0.84
    T = max(r for r in range(13) if allc[r] >= 3)
    higher_pair = [r for r in range(13) if bcount[r] >= 2 and r > T]
    if higher_pair:
        return 0.7
    if pocket and bcount[h1] == 1:
        return 0.96
    return 0.92


def _board_cat(b):
    rc = [0] * 13
    for r, _ in b:
        rc[r] += 1
    c = sorted(rc, reverse=True)
    if c[0] >= 4:
        return 7
    if c[0] == 3:
        return 3
    if c[0] == 2 and c[1] == 2:
        return 2
    if c[0] == 2:
        return 1
    return 0


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.n_seats = config.get("seats", 8)
        self.stats = {}
        self.ftb = {}
        self.pf_aggr = False
        self.pending_shove = None
        self.icm_w = ICM_W
        self.hl_fac = 1.0
        self.exp_calls = 0.0
        self.obs_calls = 0.0

    # ------------------------------------------------------------------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            if self.pending_shove is not None:
                me = self.seat
                after = False
                called = 0.0
                for st, seat, act, amt in hist:
                    if st != 0:
                        continue
                    if seat == me and act == "raise":
                        after = True
                    elif after and seat != me and act in ("call", "raise"):
                        called = 1.0
                if after:
                    self.exp_calls += self.pending_shove
                    self.obs_calls += called
                self.pending_shove = None
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in hist:
                if seat is None:
                    continue
                seen.add(seat)
                if st == 0 and act in ("call", "raise"):
                    vp.add(seat)
                if st == 0 and act == "raise":
                    pr.add(seat)
            me = self.seat
            for i, (st, seat, act, amt) in enumerate(hist):
                if st >= 1 and seat == me and act in ("raise", "bet"):
                    for st2, seat2, act2, amt2 in hist[i + 1:]:
                        if st2 != st:
                            break
                        if seat2 == me:
                            break
                        if act2 in ("fold", "call", "raise"):
                            f = self.ftb.get(seat2)
                            if f is None:
                                f = self.ftb[seat2] = [0, 0]
                            f[0] += 1
                            if act2 == "fold":
                                f[1] += 1
            for s in seen:
                d = self.stats.get(s)
                if d is None:
                    d = self.stats[s] = [0, 0, 0]
                d[0] += 1
                if s in vp:
                    d[1] += 1
                if s in pr:
                    d[2] += 1
        except Exception:
            pass

    def _icm(self, n, x):
        return icm_eq(n, x, self.icm_w)

    def fold_rate(self, seats):
        n = 0.0
        f = 0.0
        for x in seats:
            d = self.ftb.get(x)
            if d:
                n += d[0]
                f += d[1]
        return (f + 2.0) / (n + 4.0), n

    def call_mult(self):
        k = (self.obs_calls + 1.5) / (self.exp_calls + 1.5)
        return max(0.5, min(2.0, k))

    def looseness(self, seat):
        d = self.stats.get(seat)
        if not d or d[0] < 10:
            return 1.0
        pfr = (d[2] + 1.5) / (d[0] + 10)
        f = (pfr / 0.15) ** 0.7
        if pfr > 0.45:
            f *= 1.0 + 2.0 * (pfr - 0.45)
        return max(0.6, min(6.0, f))

    # ------------------------------------------------------------------
    def act(self, obs):
        try:
            a = self._act(obs)
            if a is None:
                raise ValueError
            return a
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def _raise_to(self, obs, amt):
        legal = obs["legal"]
        if "raise" not in legal and "bet" not in legal:
            if "call" in legal:
                return {"action": "call"}
            return {"action": "check"}
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        amt = int(amt)
        if amt >= hi * 0.8:
            amt = hi
        if amt < lo:
            amt = lo
        if amt > hi:
            amt = hi
        return {"action": "raise", "amount": amt}

    def _allin(self, obs):
        legal = obs["legal"]
        if "raise" in legal or "bet" in legal:
            return {"action": "raise", "amount": obs["max_raise_to"]}
        if "call" in legal:
            return {"action": "call"}
        return {"action": "check"}

    def _passive(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def _act(self, obs):
        hl = obs.get("hands_left", 200) or 200
        self.icm_w = ICM_W if hl > 20 else ICM_W + (1.0 - ICM_W) * (20 - hl) / 20.0
        self.hl_fac = min(1.0, hl / 8.0)
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["street_index"] == 0:
            return self._preflop(obs)
        return self._postflop(obs)

    # ------------------------------------------------------------------
    def _preflop(self, obs):
        me = obs["seat"]
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        hist = obs["history"]
        ci = cls_index(obs["hole"])
        pct = PCT[ci]
        R = stacks[me]
        b = bets[me]
        T = R + b

        # action order preflop: after bb clockwise
        n = self.n_seats
        order = []
        bbs = obs["bb_seat"]
        for k in range(1, n + 1):
            s = (bbs + k) % n
            if s in alive:
                order.append(s)
        acted = set()
        raises = []
        limpers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act in ("call", "raise", "fold", "check"):
                acted.add(seat)
            if act == "raise":
                raises.append((seat, amt))
            elif act == "call" and not raises:
                limpers += 1
        pos = order.index(me) if me in order else 0
        behind = [s for s in order[pos + 1:] if s in in_hand and stacks[s] > 0]
        others = [s for s in in_hand if s != me]
        max_other_T = max([stacks[s] + bets[s] for s in others] or [0])
        eff = min(T, max_other_T)
        eff_bb = eff / bb
        self.pf_aggr = False

        if not raises:
            # unopened (maybe limpers)
            if to_call == 0:
                # big blind option with limpers
                if pct <= 0.10:
                    self.pf_aggr = True
                    return self._raise_to(obs, bets[me] + (3 + limpers) * bb if eff_bb > PUSH_DEPTH else obs["max_raise_to"])
                return {"action": "check"}
            if eff_bb <= PUSH_DEPTH or (limpers > 0 and eff_bb <= PUSH_DEPTH + 6):
                ev = self._shove_ev(obs, ci, behind, R, b, pot, bb)
                if ev > 0.0:
                    self.pf_aggr = True
                    self.pending_shove = self._last_pcall
                    return self._allin(obs)
                if limpers and to_call <= 0.5 * bb and pct <= 0.45 and "call" in obs["legal"]:
                    return self._call(obs)
                return self._passive(obs)
            nb = len(behind)
            op = OPEN_PCT.get(nb, 0.10 if nb > 7 else 0.42)
            if limpers:
                op = min(op, 0.12)
            if pct <= op:
                self.pf_aggr = True
                size = (2.5 if nb > 1 else 3.0) * bb + limpers * bb
                if eff_bb <= 25:
                    size = 2.2 * bb + limpers * bb
                return self._raise_to(obs, size)
            # small blind completing vs limpers / cheap
            if limpers and to_call <= 0.5 * bb and pct <= 0.45:
                return self._call(obs)
            return self._passive(obs)

        # facing raise(s)
        nraise = len(raises)
        rseat, ramt = raises[-1]
        r_T = stacks[rseat] + bets[rseat]
        r_allin = stacks[rseat] == 0 or ramt >= 0.9 * r_T
        loose = self.looseness(rseat)
        if r_allin or ramt >= 0.45 * r_T:
            vr = shove_range(r_T / bb) * loose
            if nraise >= 2:
                vr *= 0.6
        else:
            if nraise == 1:
                vr = 0.20 * loose
            elif nraise == 2:
                vr = 0.07 * loose
            else:
                vr = 0.035 * loose
        if nraise == 1 and rseat in order:
            nbr = len(order) - 1 - order.index(rseat)
            vr *= {1: 2.2, 2: 1.45, 3: 1.15}.get(nbr, 1.0)
        vr = max(0.02, min(1.0, vr))
        e = eq_vs(ci, vr)
        # multiway adjustment: other players already in / behind
        n_in = len([s for s in others if bets[s] > 0 or s in behind])
        call_amt = min(to_call, R)
        excess = max(0, bets[rseat] - (b + R))
        pot_after = pot + call_amt - excess
        need = call_amt / max(1, pot_after)
        extra_players = max(0, len(behind)) + max(0, len([s for s in others if s != rseat and bets[s] >= bets[rseat]]))
        e_adj = e * (0.92 ** extra_players)
        is_pair = ci // 13 == ci % 13
        if r_allin or "raise" not in obs["legal"] or call_amt >= 0.45 * T:
            # pure call / fold by pot odds (or shove if we'd be all-in anyway)
            n = len(obs["alive"])
            tot = float(sum(stacks) + pot)
            effc = min(T, r_T)
            pot_sd = (pot - b - bets[rseat]) + 2 * effc
            n_win = n - 1 if r_T <= T else n
            ev_call = e_adj * self._icm(n_win, (T - effc + pot_sd) / tot) + (1 - e_adj) * self._icm(n, (T - effc) / tot)
            if ev_call > self._icm(n, R / tot) + 0.2:
                if r_allin or "raise" not in obs["legal"]:
                    return self._call(obs)
                return self._allin(obs)
            return self._passive(obs)
        if eff_bb <= 25:
            # re-shove EV vs the raiser (calls with the top part of its range) and players behind
            cf = max(0.03, min(vr, vr * 0.45, 0.25))
            pc = cf / vr
            effc = min(T, r_T)
            ec = eq_vs(ci, cf)
            pot_sd = (pot - b - bets[rseat]) + 2 * effc
            p_fold_behind = 1.0
            for s in behind:
                if s == rseat:
                    continue
                p_fold_behind *= 1 - min(0.5, call_range(min(T, stacks[s] + bets[s]) / bb, s == obs["bb_seat"]) * 0.6)
            pc_tot = 1 - (1 - pc) * p_fold_behind
            n = len(obs["alive"])
            tot = float(sum(stacks) + pot)
            n_win = n - 1 if r_T <= T else n
            ev_sh = (1 - pc_tot) * self._icm(n, (R + pot) / tot) + pc_tot * (
                ec * 0.97 * self._icm(n_win, (T - effc + pot_sd) / tot) + (1 - ec * 0.97) * self._icm(n, (T - effc) / tot))
            if ev_sh > self._icm(n, R / tot) + 0.2:
                self.pf_aggr = True
                return self._allin(obs)
            if call_amt <= 0.12 * T and (e_adj >= 0.5 or (is_pair and call_amt <= 0.07 * T)) \
                    and e_adj >= need:
                return self._call(obs)
            if me == obs["bb_seat"] and nraise == 1 and call_amt <= 1.5 * bb and e_adj >= need + 0.15:
                return self._call(obs)
            return self._passive(obs)
        # deep: 3bet / call / fold
        if e_adj >= 0.62 or (nraise == 1 and pct <= 0.025):
            self.pf_aggr = True
            if eff_bb <= 30:
                return self._allin(obs)
            mult = 3.0 if len(behind) == 0 else 3.5
            return self._raise_to(obs, ramt * mult)
        if me == obs["bb_seat"] and nraise == 1 and call_amt <= 2.0 * bb and e_adj >= need + 0.14 \
                and call_amt <= 0.08 * T:
            return self._call(obs)
        if call_amt <= 0.08 * T and (e_adj >= 0.45 or (ci // 13 == ci % 13 and call_amt <= 0.06 * T)):
            if e_adj * pot_after >= call_amt * 0.8 or ci // 13 == ci % 13:
                return self._call(obs)
        if to_call <= 0:
            return {"action": "check"}
        return self._passive(obs)

    def _shove_ev(self, obs, ci, behind, R, b, pot, bb):
        stacks = obs["stacks"]
        bets = obs["bets"]
        n = len(obs["alive"])
        tot = float(sum(stacks) + pot)
        T = R + b
        p_reach = 1.0
        ev = 0.0
        for s in behind:
            V = stacks[s] + bets[s]
            effc = min(T, V)
            c = call_range(effc / bb, s == obs["bb_seat"]) * self.looseness(s) ** 0.5 * self.call_mult()
            if len(behind) == 1:
                c *= 1.45
            c = max(0.02, min(0.9, c))
            e = eq_vs(ci, c)
            pot_sd = (pot - b - bets[s]) + 2 * effc
            win = T - effc + pot_sd
            lose = T - effc
            n_win = n - 1 if V <= T else n
            ev += p_reach * c * (e * self._icm(n_win, win / tot) + (1 - e) * self._icm(n, lose / tot))
            p_reach *= (1 - c)
        ev += p_reach * self._icm(n, (R + pot) / tot)
        self._last_pcall = 1.0 - p_reach
        # folding is not free when short: blinds keep coming
        r_fold = max(0.0, R - BLIND_COST * self.hl_fac * (obs["sb"] + bb) * min(1.0, 3.0 / max(2, n)))
        return ev - self._icm(n, r_fold / tot)

    # ------------------------------------------------------------------
    def _postflop(self, obs):
        me = obs["seat"]
        stacks = obs["stacks"]
        R = stacks[me]
        pot = obs["pot"]
        to_call = obs["to_call"]
        street = obs["street_index"]
        in_hand = obs["in_hand"]
        n_opp = max(1, len(in_hand) - 1)
        s, draw, nut_fd = post_strength(obs["hole"], obs["board"])
        eq = s + draw * (1 - s)
        eq_m = eq ** (1 + 0.6 * (n_opp - 1))
        rnd = self.rng.random()
        river = street >= 3
        spr = R / max(1, pot)
        opps = [x for x in in_hand if x != me]
        fr, fn = self.fold_rate(opps)
        station = fn >= 4 and fr < 0.3
        folder = fn >= 4 and fr > 0.6
        if to_call == 0:
            if eq_m >= 0.78:
                if spr < 1.2:
                    return self._allin(obs)
                if station:
                    return self._raise_to(obs, pot * 0.9)
                return self._raise_to(obs, pot * (0.75 if rnd < 0.7 else 0.55))
            if eq_m >= 0.6 and not (river and eq_m < 0.66):
                if spr < 0.8:
                    return self._allin(obs)
                return self._raise_to(obs, pot * 0.5)
            if not river and draw >= 0.25 and n_opp <= 2 and rnd < 0.55:
                if spr < 1.0:
                    return self._allin(obs)
                return self._raise_to(obs, pot * 0.6)
            cb = 0.25 if station else (0.85 if folder else 0.6)
            if self.pf_aggr and street == 1 and n_opp == 1 and rnd < cb:
                return self._raise_to(obs, pot * 0.5)
            if folder and n_opp == 1 and not river and rnd < 0.35:
                return self._raise_to(obs, pot * 0.5)
            if river and n_opp == 1 and s < 0.2 and rnd < (0.3 if folder else (0.0 if station else 0.1)):
                return self._raise_to(obs, pot * 0.6)
            return {"action": "check"}
        call_amt = min(to_call, R)
        pot_after = pot + call_amt
        need = call_amt / max(1, pot_after)
        bet_frac = to_call / max(1, pot - to_call)
        strength_pen = 0.08 * max(0.0, bet_frac - 0.4) + 0.04 * (street - 1) + 0.03 * river
        raised_me = any(h[0] == street and h[1] == me and h[2] in ("raise", "bet") for h in obs["history"])
        if raised_me:
            strength_pen += 0.12
        eq_c = eq_m - strength_pen
        if s >= (0.96 if raised_me else 0.88) and eq_m >= 0.75:
            if spr < 2 or call_amt >= 0.4 * R:
                return self._allin(obs)
            return self._raise_to(obs, obs["min_raise_to"] + pot * 0.6)
        if call_amt >= 0.5 * R:
            # committed decision (ICM)
            n = len(obs["alive"])
            tot = float(sum(stacks) + pot)
            villain_allin = any(stacks[x] == 0 for x in in_hand if x != me)
            n_win = n - 1 if villain_allin and n_opp == 1 else n
            ev_call = eq_c * self._icm(n_win, (R + pot) / tot) + (1 - eq_c) * self._icm(n, (R - call_amt) / tot)
            if ev_call > self._icm(n, R / tot) + 0.2:
                return self._allin(obs) if eq_c >= 0.7 else self._call(obs)
            return self._passive(obs)
        if eq_c >= 0.72 and rnd < 0.3 and not river:
            return self._raise_to(obs, obs["min_raise_to"] + pot * 0.5)
        if eq_c >= need + 0.12 or (eq_c >= 0.55 and bet_frac <= 0.75):
            return self._call(obs)
        if not river and draw >= 0.15:
            implied = draw + 0.05
            if implied >= need:
                return self._call(obs)
        return self._passive(obs)
