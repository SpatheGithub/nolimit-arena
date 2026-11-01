"""b05 royal hold'em bot: precomputed rank-only equities, range-aware pot odds,
push/fold when short, 3-place ICM for big all-in decisions, opponent stats."""
import json
import os
import random

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.json")))
TURN = _D["turn"]
TURNQ = _D["turnq"]
FLOP = _D["flop"]
FLOPQ = _D["flopq"]
PRE = _D["pre"]
MAT = _D["mat"]
RIDX = {"T": 0, "J": 1, "Q": 2, "K": 3, "A": 4}
SIDX = {"c": 0, "d": 1, "h": 2, "s": 3}

HKEYS = sorted(PRE.keys(), key=lambda k: -PRE[k][0])  # strongest first (HU)
HW = {k: (6 if k[0] == k[1] else 16) for k in HKEYS}
QGRID = [0.03, 0.06, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def _range(q):
    """top-q fraction of hands -> {key: weight fraction (0..1)}"""
    tot = 190.0
    lim = q * tot
    acc = 0.0
    out = {}
    for k in HKEYS:
        w = HW[k]
        take = min(w, lim - acc)
        if take <= 0:
            break
        out[k] = take / w
        acc += take
    return out


RANGES = [_range(q) for q in QGRID]
# EQR[h][i] = equity of h vs top-QGRID[i] range (heads-up, card removal)
EQR = {}
for h in HKEYS:
    row = []
    for rg in RANGES:
        s = ws = 0.0
        for o, frac in rg.items():
            e, w = MAT[h + o]
            w = w * frac
            s += e * w
            ws += w
        row.append(s / ws if ws else 0.5)
    EQR[h] = row
# rank of each hand class (fraction of hands stronger or equal, midpoint)
HPCT = {}
_acc = 0.0
for k in HKEYS:
    HPCT[k] = (_acc + HW[k] / 2.0) / 190.0
    _acc += HW[k]


def eq_vs_q(h, q):
    if q <= QGRID[0]:
        return EQR[h][0]
    for i in range(1, len(QGRID)):
        if q <= QGRID[i]:
            a, b = QGRID[i - 1], QGRID[i]
            t = (q - a) / (b - a)
            return EQR[h][i - 1] * (1 - t) + EQR[h][i] * t
    return EQR[h][-1]


def icm3(stacks, i, pts):
    """Expected points of player i (Malmuth-Harville, first 3 places)."""
    T = float(sum(stacks))
    si = stacks[i]
    if si <= 0:
        return None
    n = len(stacks)
    p1 = si / T
    ev = p1 * pts[0]
    if n >= 2 and pts[1]:
        p2 = 0.0
        p3 = 0.0
        for j in range(n):
            if j == i or stacks[j] <= 0:
                continue
            sj = stacks[j]
            pj = sj / T
            T1 = T - sj
            p2 += pj * si / T1
            if n >= 3 and pts[2]:
                for k in range(n):
                    if k == i or k == j or stacks[k] <= 0:
                        continue
                    sk = stacks[k]
                    T2 = T1 - sk
                    if T2 > 0:
                        p3 += pj * sk / T1 * si / T2
        ev += p2 * pts[1] + p3 * pts[2]
    return ev


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = list(config.get("points") or [100, 25, 5, 0, 0, 0, 0, 0]) + [0] * 8
        self.n_seats = config.get("seats", 8)
        # opponent stats per seat
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.aggr = [0] * 16   # postflop bets/raises
        self.passv = [0] * 16  # postflop calls/checks
        self.foldf = [0] * 16  # folds to a bet postflop
        self.facedbet = [0] * 16
        self.shows = [0] * 16

    # ------------------------------------------------------------ helpers
    def observe(self, ev):
        try:
            if ev.get("type") != "hand_end":
                return
            hist = ev.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in hist:
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        self.aggr[seat] += 1
                    elif act in ("call", "check"):
                        self.passv[seat] += 1
            bet_on = {}
            for st, seat, act, amt in hist:
                if st == 0 or act in ("sb", "bb", "ante", "return"):
                    continue
                if act == "raise":
                    bet_on[st] = seat
                elif st in bet_on and bet_on[st] != seat and act in ("fold", "call"):
                    self.facedbet[seat] += 1
                    if act == "fold":
                        self.foldf[seat] += 1
            for s in seen:
                if 0 <= s < 16:
                    self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass

    def opp_vpip(self, s):
        n = self.hands[s]
        return (self.vpip[s] + 0.35 * 6) / (n + 6)

    def opp_pfr(self, s):
        n = self.hands[s]
        return (self.pfr[s] + 0.2 * 6) / (n + 6)

    def opp_ftb(self, s):
        return (self.foldf[s] + 0.4 * 5) / (self.facedbet[s] + 5.0)

    def opp_af(self, s):
        a = self.aggr[s]
        p = self.passv[s]
        return (a + 2.0) / (a + p + 5.0)

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def _raise(self, obs, amt):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            amt = int(max(obs["min_raise_to"], min(obs["max_raise_to"], amt)))
            return {"action": "raise", "amount": amt}
        return self._call(obs)

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def _fold(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _allin(self, obs):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            return {"action": "raise", "amount": int(obs["max_raise_to"])}
        return self._call(obs)

    # ------------------------------------------------------------ main
    def _act(self, obs):
        if obs["phase"] != "bet":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        me = obs["seat"]
        hole = obs["hole"]
        hr = sorted(RIDX[c[0]] for c in hole)
        hkey = "%d%d" % (hr[0], hr[1])
        if obs["street_index"] == 0:
            return self._preflop(obs, me, hkey)
        return self._postflop(obs, me, hr)

    def _icm_ok(self, obs, me, risk, win_gain, eq, opp=None):
        """Compare ICM EV of calling an all-in-ish spot vs folding.
        risk: chips we put in from now; win_gain: chips we win in addition (pot + opp contribution).
        Returns (ev_call - ev_fold) in points."""
        stacks = list(obs["stacks"])
        alive = [s for s in obs["alive"] if stacks[s] > 0 or s in obs["in_hand"]]
        # total chips per seat including this hand's bets: approximate with stacks + bets
        tot = [0] * len(stacks)
        bets = obs["bets"]
        for s in range(len(stacks)):
            tot[s] = stacks[s]
        live = [s for s in range(len(stacks)) if s in obs["alive"]]
        pot = obs["pot"]
        # fold state: we keep stacks[me]; pot goes to opponent (approx: opp)
        base = [stacks[s] for s in live]
        im = live.index(me)
        io = live.index(opp) if (opp is not None and opp in live) else None
        f = list(base)
        if io is not None:
            f[io] += pot
        w = list(base)
        w[im] += pot + win_gain
        if io is not None:
            w[io] -= max(0, win_gain - 0)  # opp pays what they add
            w[io] = max(0, w[io])
        l = list(base)
        l[im] -= risk
        if io is not None:
            l[io] += pot + risk
        pts = self.points
        n_left = len([x for x in base if x > 0 or True])
        ev_f = icm3(f, im, pts)
        ev_w = icm3(w, im, pts)
        if l[im] <= 0:
            # busted: finish at place = number of players with chips after
            place = len([x for x in l if x > 0]) + 1
            ev_l = pts[place - 1] if place - 1 < len(pts) else 0.0
            l2 = None
        else:
            ev_l = icm3(l, im, pts)
        if ev_f is None:
            ev_f = 0.0
        return eq * ev_w + (1 - eq) * ev_l - ev_f

    # ------------------------------------------------------------ preflop
    def _preflop(self, obs, me, hkey):
        stacks = obs["stacks"]
        bets = obs["bets"]
        bb = obs["bb"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        my_total = my_stack + bets[me]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        n = len(alive)
        others = [s for s in in_hand if s != me]
        eff = min(my_total, max([stacks[s] + bets[s] for s in others] or [0]))
        eff_bb = eff / float(bb)
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        callers = [h for h in hist if h[0] == 0 and h[2] == "call"]
        # players left to act after me (who haven't acted yet this round)
        acted = set(h[1] for h in hist if h[0] == 0 and h[2] not in ("sb", "bb", "ante"))
        # order: seats after bb
        order = self._preflop_order(obs)
        pos = order.index(me) if me in order else 0
        behind = [s for s in order[pos + 1:] if s in in_hand]
        if obs["bb_seat"] in behind or obs["bb_seat"] == me:
            pass
        k_behind = len([s for s in behind if s not in acted])
        pct = HPCT[hkey]
        e1 = PRE[hkey][0]
        nraise = len(raises)

        if nraise == 0:
            # unopened (maybe limpers)
            nl = len(callers)
            if eff_bb <= 13:
                return self._pushfold(obs, me, hkey, eff, k_behind)
            # open-raise ranges by players behind
            if k_behind <= 1:
                q = 0.62
            elif k_behind == 2:
                q = 0.48
            elif k_behind == 3:
                q = 0.38
            elif k_behind == 4:
                q = 0.32
            else:
                q = 0.26
            q -= 0.05 * nl
            if me == obs["bb_seat"] and to_call == 0:
                # option: raise strong, else check
                if pct <= 0.15 + 0.05 * (nl == 0):
                    return self._raise(obs, bb * (3 + nl) + pot * 0)
                return self._call(obs)
            if pct <= q:
                size = bb * (2.5 + nl) if eff_bb > 25 else bb * 2.2
                if eff_bb <= 20 and pct <= 0.15:
                    size = bb * 2.2
                return self._raise(obs, size)
            # complete SB cheaply with decent hands
            if me == obs["sb_seat"] and to_call <= bb / 2 and pct <= 0.75:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        raise_to = last[3]
        raiser_total = stacks[raiser] + bets[raiser]
        allin_faced = stacks[raiser] == 0
        # estimate raiser's range
        pfr = self.opp_pfr(raiser)
        if nraise == 1:
            q = min(1.0, max(0.08, pfr * 1.1))
        elif nraise == 2:
            q = min(0.3, max(0.05, pfr * 0.5))
        else:
            q = 0.05
        # bigger raises -> tighter (unless short stack shoves)
        rsz = raise_to / float(bb)
        if rsz > 6 and not (allin_faced and raiser_total / float(bb) < 15):
            q *= 0.75
        if allin_faced and raiser_total / float(bb) < 12:
            q = max(q, 0.35)
        eq = eq_vs_q(hkey, q)
        # multiway penalty: only players who put chips in voluntarily
        vol = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise") and h[1] != me)
        n_others_in = len([s for s in others if s in vol])
        n_yet = len([s for s in others if s not in vol and s not in acted])
        if n_others_in > 1:
            eq = eq * (0.88 ** (n_others_in - 1))
        if n_yet > 0:
            eq = eq * (0.985 ** n_yet)
        n_others_in = max(1, n_others_in)
        my_after = my_stack - to_call
        call_cost = to_call
        pot_odds = call_cost / float(pot + call_cost)
        commit = to_call >= 0.4 * my_stack or my_after <= 3 * bb
        # strong: 3bet / jam
        if eq >= 0.60 and pct <= 0.12:
            if eff_bb <= 30 or nraise >= 2:
                return self._allin(obs)
            return self._raise(obs, raise_to * 3 + 0)
        # re-steal jam vs loose openers when not too deep
        if nraise == 1 and not allin_faced and eff_bb <= 25 and q >= 0.3 and eq >= 0.5 \
                and n_others_in <= 1:
            return self._allin(obs)
        if commit or allin_faced:
            # all-in decision with ICM
            risk = min(to_call, my_stack)
            gain = min(raiser_total - bets[me] - 0, my_total) - 0
            d = self._icm_ok(obs, me, risk, 0, eq, raiser)
            if d > 0:
                return self._allin(obs) if not allin_faced and eq > 0.55 else self._call(obs)
            return self._fold(obs)
        # normal call: need equity edge with implied/position
        margin = 0.06 if n_others_in == 1 else 0.03
        if eq >= pot_odds + margin and to_call <= 0.25 * my_stack:
            return self._call(obs)
        return self._fold(obs)

    def _preflop_order(self, obs):
        alive = sorted(obs["alive"])
        bbs = obs["bb_seat"]
        # order starting after bb
        if bbs in alive:
            i = alive.index(bbs)
        else:
            i = 0
        return alive[i + 1:] + alive[:i + 1]

    def _pushfold(self, obs, me, hkey, eff, k_behind):
        stacks = obs["stacks"]
        bets = obs["bets"]
        bb = obs["bb"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        eff_bb = eff / float(bb)
        if k_behind <= 0:
            # bb with no raise: check option / raise strong
            if HPCT[hkey] <= 0.35:
                return self._allin(obs)
            return self._call(obs)
        # assumed calling range for each player behind: depends on our shove size
        c = 0.15 + 0.2 * max(0.0, (13 - eff_bb)) / 13.0  # 15% at 13bb, 35% at ~0bb
        if k_behind <= 2:
            c += 0.05
        pf = (1 - c) ** k_behind
        eqc = eq_vs_q(hkey, c)
        # chips: gain pot if all fold; if called (approx 1 caller), win pot + eff
        risk = eff - bets[me]
        ev_call = eqc * (pot + eff - bets[me]) - (1 - eqc) * risk  # rough
        ev = pf * pot + (1 - pf) * ev_call
        # limp-fold alternative EV = 0
        if ev > 0.0:
            return self._allin(obs)
        if me == obs["sb_seat"] and to_call <= bb / 2 and HPCT[hkey] <= 0.6 and k_behind == 1:
            return self._call(obs)
        return self._fold(obs)

    # ------------------------------------------------------------ postflop
    def _postflop(self, obs, me, hr):
        board = obs["board"]
        hole = obs["hole"]
        st = obs["street_index"]
        br = sorted(RIDX[c[0]] for c in board)
        key = "%d%d" % (hr[0], hr[1]) + "".join(str(x) for x in br)
        # straight flush check
        suits = [0, 0, 0, 0]
        for c in hole + board:
            suits[SIDX[c[1]]] += 1
        sf = max(suits) >= 5
        if st == 1:
            e_r = FLOP.get(key, 0.5)
            eq50, eq25, eq10 = FLOPQ.get(key, [0.45, 0.4, 0.35])
        else:
            e_r = TURN.get(key, 0.5)
            eq50, eq25, eq10 = TURNQ.get(key, [0.45, 0.4, 0.35])
        if sf:
            e_r = eq50 = eq25 = eq10 = 1.0
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        in_hand = obs["in_hand"]
        others = [s for s in in_hand if s != me]
        active_others = [s for s in others if stacks[s] > 0]
        n_opp = len(others)
        bb = obs["bb"]
        hist = obs["history"]
        # was I the preflop aggressor?
        pre_raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        i_aggr = bool(pre_raises) and pre_raises[-1][1] == me
        street_raises = [h for h in hist if h[0] == st and h[2] == "raise"]
        last_street = st == 2
        eff = min(my_stack, max([stacks[s] for s in others] or [0]))
        rng = self.rng

        if to_call == 0:
            # we may bet
            if n_opp == 1:
                eq_v = eq50
                ftb = self.opp_ftb(others[0])
            else:
                eq_v = eq50 ** (0.8 * n_opp)
                ftb = 1.0
                for s in others:
                    ftb *= self.opp_ftb(s)
            vthr = 0.58
            if n_opp == 1 and ftb < 0.3:
                vthr = 0.54  # station: thinner value
            # value bet threshold
            if eq_v >= vthr or (eq25 >= 0.55):
                frac = 0.7 if eq_v < 0.75 else 0.85
                if n_opp == 1 and ftb < 0.3 and eq_v >= 0.7:
                    frac = 1.0
                size = pot * frac
                if size >= 0.6 * my_stack:
                    return self._allin(obs)
                return self._raise(obs, size)
            # bluff / semi-bluff, heads-up mostly
            if n_opp <= 2:
                bl = 0.0
                if st == 1 and e_r >= 0.4:
                    bl = 0.35 if i_aggr else 0.2
                elif e_r < 0.3:
                    bl = 0.25 if i_aggr else 0.12
                if ftb > 0.5:
                    bl += 0.25
                elif ftb < 0.3:
                    bl *= 0.2
                if n_opp == 2:
                    bl *= 0.5
                if rng.random() < bl:
                    size = pot * 0.6
                    if size >= 0.6 * my_stack:
                        return self._call(obs)
                    return self._raise(obs, size)
            return self._call(obs)

        # facing a bet
        bettor = street_raises[-1][1] if street_raises else (others[0] if others else me)
        bet_frac = to_call / float(max(1, pot - to_call))
        af = self.opp_af(bettor) if bettor != me else 0.4
        # range tightness from bet size and aggression
        if bet_frac <= 0.35:
            e = 0.6 * eq50 + 0.4 * e_r
        elif bet_frac <= 0.75:
            e = eq50
        elif bet_frac <= 1.3:
            e = 0.5 * eq50 + 0.5 * eq25
        else:
            e = 0.5 * eq25 + 0.5 * eq10
        # aggressive opponents bluff more -> widen; passive tighten
        if af > 0.55:
            e = 0.6 * e + 0.4 * e_r
        elif af < 0.3:
            e = 0.7 * e + 0.3 * eq25
        if len(street_raises) >= 2:
            e = 0.5 * e + 0.5 * eq10
        if n_opp > 1:
            e = e * (0.9 ** (n_opp - 1))
        if sf:
            e = 1.0
        pot_odds = to_call / float(pot + to_call)
        call_amt = min(to_call, my_stack)
        # raise for value
        if e >= 0.72 and obs["max_raise_to"] > 0:
            if len(street_raises) >= 2 or to_call >= 0.35 * my_stack:
                return self._allin(obs)
            size = bets[bettor] * 2.5 + (pot - to_call) * 0.5
            if size >= 0.55 * (my_stack + bets[me]):
                return self._allin(obs)
            return self._raise(obs, size)
        big = call_amt >= 0.5 * my_stack
        if big:
            d = self._icm_ok(obs, me, call_amt, 0, e, bettor)
            if d > 0:
                return self._call(obs)
            return self._fold(obs)
        margin = 0.0 if last_street else 0.03
        if e >= pot_odds + margin:
            return self._call(obs)
        return self._fold(obs)
