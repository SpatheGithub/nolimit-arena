import os
import json
import random
import time
from itertools import combinations

from .ev import value, CARD

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, 'pre.json')) as _f:
    _D = json.load(_f)
_CLSL = _D['cls']
_CLS = {}
for _i, _c in enumerate(combinations(range(52), 3)):
    _CLS[_c] = _CLSL[_i]
_PCT = _D['pct']
_EQ1 = _D['eq1']
_EQ3 = _D['eq3']
with open(os.path.join(_DIR, 'pre2.json')) as _f:
    _D2 = json.load(_f)
_RANGES = _D2['ranges']
_NB = _D2['nb']
_M0 = _D2['M']
# light smoothing of the equity-vs-range matrix along the bucket axis
_M = []
for _b in range(_NB):
    _row = []
    for _j in range(len(_RANGES)):
        _vals = [_M0[_b][_j]]
        _w = [2.0]
        if _b > 0:
            _vals.append(_M0[_b - 1][_j])
            _w.append(1.0)
        if _b < _NB - 1:
            _vals.append(_M0[_b + 1][_j])
            _w.append(1.0)
        _row.append(sum(v * w for v, w in zip(_vals, _w)) / sum(_w))
    _M.append(_row)
_ICM = {int(k): v for k, v in _D2['icm'].items()}
_PAIRS3 = ((0, 1), (0, 2), (1, 2))
_P = {'push_bb': 12, 'open_mult': 1.15, 'bluff_mult': 1.5, 'vb': 0.5, 'call_margin': 0.0, 'rr': 0.5, 'wf': 1.45, 'wt': 1.2, 'hu_open': 2.2}


def eq_vs_range(p, x):
    b = int(p * _NB)
    if b >= _NB:
        b = _NB - 1
    row = _M[b]
    R = _RANGES
    if x <= R[0]:
        return row[0]
    if x >= R[-1]:
        return row[-1]
    for j in range(len(R) - 1):
        if x <= R[j + 1]:
            t = (x - R[j]) / (R[j + 1] - R[j])
            return row[j] * (1 - t) + row[j + 1] * t
    return row[-1]


def icm_val(n, share, points):
    if n <= 1:
        return points[0]
    if n > 8:
        n = 8
    if share <= 0:
        return points[n - 1] if n - 1 < len(points) else 0.0
    if share >= 1:
        return points[0]
    row = _ICM[n]
    x = share * 100.0
    i = int(x)
    if i >= 100:
        return row[100]
    t = x - i
    return row[i] * (1 - t) + row[i + 1] * t


def icm_exact(vals, me, pts):
    """Malmuth-Harville equity of player index me; vals: stacks (0 = busted now)."""
    if vals[me] <= 0:
        n = len([v for v in vals if v > 0]) + 1
        return pts[n - 1] if n - 1 < len(pts) else 0.0
    live = [v for i, v in enumerate(vals) if v > 0 or i == me]
    mi = 0
    k = 0
    for i, v in enumerate(vals):
        if v > 0 or i == me:
            if i == me:
                mi = k
            k += 1
    n = len(live)
    if n == 1:
        return pts[0]
    if n > 5:
        tot = float(sum(live))
        return icm_val(n, live[mi] / tot, pts)
    memo = {}

    def V(mask, place):
        r = memo.get(mask)
        if r is not None:
            return r
        tot = 0.0
        for i in range(n):
            if mask >> i & 1:
                tot += live[i]
        res = 0.0
        for i in range(n):
            if mask >> i & 1:
                p = live[i] / tot
                if i == mi:
                    res += p * pts[place]
                else:
                    res += p * V(mask & ~(1 << i), place + 1)
        memo[mask] = res
        return res

    return V((1 << n) - 1, 0)


class Stat:
    __slots__ = ('hands', 'vpip', 'pfr', 'f2r_o', 'f2r', 'fb_o', 'fb', 'pa', 'pagg')

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.f2r_o = 0
        self.f2r = 0
        self.fb_o = 0
        self.fb = 0
        self.pa = 0
        self.pagg = 0

    def vpip_r(self):
        return (self.vpip + 0.32 * 5) / (self.hands + 5)

    def pfr_r(self):
        return (self.pfr + 0.16 * 5) / (self.hands + 5)

    def f2r_r(self):
        return (self.f2r + 0.6 * 4) / (self.f2r_o + 4)

    def fb_r(self):
        return (self.fb + 0.45 * 4) / (self.fb_o + 4)

    def agg_r(self):
        return (self.pagg + 0.3 * 5) / (self.pa + 5)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        n = config.get("seats", 8)
        self.st = {}
        self.nseats = n
        self.sample = self.rng.sample

    def U(self, obs, mine, ch):
        stacks = obs["stacks"]
        bets = obs["bets"]
        vals = []
        mi = 0
        for x in obs["alive"]:
            if x == self.seat:
                mi = len(vals)
                vals.append(mine)
            else:
                v = ch.get(x)
                vals.append(stacks[x] + bets[x] if v is None else v)
        return icm_exact(vals, mi, self.points)

    def S(self, s):
        x = self.st.get(s)
        if x is None:
            x = self.st[s] = Stat()
        return x

    # ------------------------------------------------------------------
    def act(self, obs):
        t0 = time.perf_counter()
        try:
            if obs["phase"] == "discard":
                return self.discard(obs, t0)
            if obs["street_index"] == 0:
                return self.preflop(obs)
            return self.postflop(obs, t0)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    # ------------------------------------------------------------------
    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _call(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "call"}

    def _raise(self, obs, amt):
        legal = obs["legal"]
        if ("raise" not in legal and "bet" not in legal) or obs["max_raise_to"] <= 0:
            return self._call(obs)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        a = int(amt)
        if a >= 0.85 * hi:
            a = hi
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        return {"action": "raise", "amount": a}

    def _allin(self, obs):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self._call(obs)

    def _order(self, obs):
        alive = obs["alive"]
        n = len(alive)
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        if obs["street_index"] == 0:
            if n == 2:
                return [alive[bi], alive[1 - bi]]
            bbs = obs["bb_seat"]
            j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
            return alive[j:] + alive[:j]
        return alive[bi + 1:] + alive[:bi + 1]

    # ------------------------------------------------------------------
    def preflop(self, obs):
        me = self.seat
        ids = [CARD[c] for c in obs["hole"]]
        if len(ids) == 3:
            ci = _CLS[tuple(sorted(ids))]
            p = _PCT[ci]
        else:
            p = 0.5
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        hist = obs["history"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_total = stacks[me] + bets[me]
        total_chips = sum(stacks) + pot
        alive = obs["alive"]
        n_alive = len([s for s in alive if stacks[s] + bets[s] > 0]) if alive else 2
        n_alive = max(2, len(alive))
        order = self._order(obs)
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        n_raises = len(raises)
        limpers = len([h for h in hist if h[0] == 0 and h[2] == "call"]) if n_raises == 0 else 0
        opps = [s for s in in_hand if s != me]
        max_other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_total, max_other)
        eff_bb = eff / bb
        pts = self.points
        is_bb = me == obs["bb_seat"]

        if n_raises == 0:
            # unopened (possibly limped)
            if eff_bb <= _P['push_bb'] or (limpers == 0 and eff_bb <= _P['push_bb'] + 4 and len(behind) <= 2):
                ev_shove, ev_fold = self.shove_ev(obs, p, behind, my_total, total_chips, n_alive)
                if ev_shove > ev_fold:
                    return self._allin(obs)
                if eff_bb <= _P['push_bb']:
                    if to_call == 0:
                        return {"action": "check"}
                    return self._fold(obs)
            nb = len(behind)
            thr = {0: 0.6, 1: 0.48, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14}.get(nb, 0.12)
            if behind:
                avg_f = sum(self.S(s).f2r_r() for s in behind) / len(behind)
                thr *= min(1.45, max(0.8, 0.5 + avg_f * 0.9))
            if limpers:
                thr *= 0.75
            thr *= _P['open_mult']
            if n_alive == 2:
                thr = max(thr, 0.8)
            elif n_alive == 3:
                thr = max(thr, {1: 0.62, 2: 0.48}.get(nb, thr))
            elif n_alive <= 4:
                thr *= 1.15
            if p <= thr:
                size = 2.5 * bb if nb >= 3 else 2.8 * bb
                size += limpers * bb
                if is_bb or me == obs["sb_seat"]:
                    size += 0.5 * bb
                if n_alive == 2:
                    size = _P['hu_open'] * bb
                return self._raise(obs, size)
            if to_call == 0:
                return {"action": "check"}
            # SB complete in limped pots with decent hand
            if to_call <= 0.5 * bb and p <= 0.55:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        raiser = raises[-1][1]
        rs = self.S(raiser)
        x = min(0.6, max(0.06, rs.pfr_r() * 1.1))
        if n_raises == 1 and raiser in order:
            ri = order.index(raiser)
            nb_r = len([s_ for s_ in order[ri + 1:] if s_ in alive])
            fpos = {1: 2.0, 2: 1.7, 3: 1.35, 4: 1.12}.get(nb_r, 1.0)
            x = min(0.7, x * fpos)
        raiser_total = stacks[raiser] + bets[raiser]
        if raiser_total <= 15 * bb or stacks[raiser] == 0:
            # likely a push: push ranges are wider for short stacks
            x = max(x, min(0.5, 0.12 + 1.6 / max(raiser_total / bb, 1.0) * 0.5))
        if n_alive == 2:
            x = max(x, 0.55)
        elif n_alive == 3:
            x = max(x, 0.35)
        if n_raises >= 2:
            x = max(0.025, x * 0.4)
        e = eq_vs_range(p, x)
        n_callers_after = len([h for h in hist if h[0] == 0 and h[2] == "call" and h[1] != me and
                               hist.index(h) > hist.index(raises[-1])])
        e_m = e * (0.8 ** n_callers_after) * (0.95 ** len(behind))
        cur_bet = max(bets)
        call_cost = to_call
        # all-in-ish decision?
        commit = call_cost >= 0.4 * stacks[me] or stacks[raiser] == 0 or eff_bb <= 22
        if commit:
            # options: call (or shove) all-in vs fold, judged by ICM
            opp_total = raiser_total
            dead = pot - bets[me] - bets[raiser]
            u_fold = self.U(obs, stacks[me], {raiser: opp_total + pot - bets[raiser]})
            risk = min(my_total, opp_total)
            u_win = self.U(obs, my_total + risk + dead, {raiser: opp_total - risk})
            u_lose = self.U(obs, my_total - risk, {raiser: opp_total + risk + dead})
            ev_call = e_m * u_win + (1 - e_m) * u_lose
            # shove with fold equity if raiser not all-in
            ev_shove = -1
            if stacks[raiser] > 0 and obs["max_raise_to"] > 0:
                pf = 0.45 if n_raises == 1 else 0.25
                if raiser_total > 2.5 * my_total:
                    pf *= 0.8
                pf *= max(0.0, 1.0 - 2.0 * bets[raiser] / max(1, raiser_total))
                pf *= (0.88 ** n_callers_after)
                u_steal = self.U(obs, stacks[me] + pot, {raiser: stacks[raiser]})
                ev_shove = pf * u_steal + (1 - pf) * ev_call
            if ev_shove > max(ev_call, u_fold):
                return self._allin(obs)
            if ev_call > u_fold:
                if stacks[me] <= call_cost or call_cost >= 0.6 * stacks[me]:
                    return self._allin(obs)
                return self._call(obs)
            return self._fold(obs)
        # deep: 3bet / call / fold
        if e_m >= 0.60 or p <= 0.012:
            tgt = cur_bet * (3.0 if len(behind) == 0 else 3.5) + 0 * bb
            if tgt >= 0.4 * my_total:
                return self._allin(obs)
            return self._raise(obs, tgt)
        odds = call_cost / (pot + call_cost)
        need = odds + 0.06 + (0.04 if not is_bb else 0.0)
        if e_m >= need and call_cost <= 0.25 * stacks[me]:
            return self._call(obs)
        # light 3bet vs habitual stealers in late position
        if (n_raises == 1 and n_callers_after == 0 and rs.f2r_r() > 0.6 and rs.pfr_r() > 0.3
                and p <= 0.3 and self.rng.random() < 0.3 and len(behind) <= 2):
            tgt = cur_bet * 3.2
            if tgt < 0.35 * my_total:
                return self._raise(obs, tgt)
        return self._fold(obs)

    def shove_ev(self, obs, p, behind, my_total, total_chips, n_alive):
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        bb = obs["bb"] or 1
        bbs = obs["bb_seat"]
        u_fold = self.U(obs, stacks[me], {bbs: stacks[bbs] + pot - bets[me]} if bbs != me else {})
        if not behind:
            return u_fold + 1, u_fold
        pnc = 1.0
        ev_called = 0.0
        for s in behind:
            st = self.S(s)
            c = 0.5 * (1.0 - st.f2r_r()) + 0.05
            ot = stacks[s] + bets[s]
            if s == bbs:
                c += 0.06
            if ot < 10 * bb:
                c += 0.08
            if ot < my_total * 0.3:
                c += 0.1
            c = min(0.65, max(0.06, c * 0.8))
            pc = pnc * c
            pnc *= (1 - c)
            e = eq_vs_range(p, c)
            risk = min(my_total, ot)
            dead = pot - bets[me] - bets[s]
            u_win = self.U(obs, my_total + risk + dead, {s: ot - risk})
            u_lose = self.U(obs, my_total - risk, {s: ot + risk + dead})
            ev_called += pc * (e * u_win + (1 - e) * u_lose)
        ch = {}
        for s in obs["alive"]:
            if s != me and bets[s] > 0:
                ch[s] = stacks[s]
        u_steal = self.U(obs, stacks[me] + pot, ch)
        ev = pnc * u_steal + ev_called
        return ev, u_fold

    # ------------------------------------------------------------------
    def best_keep(self, hole, board):
        best = -1
        bk = hole[:2]
        for a, b in _PAIRS3:
            v = value([hole[a], hole[b]] + board)
            if v > best:
                best = v
                bk = [hole[a], hole[b]]
        return bk

    def discard(self, obs, t0):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        k = obs.get("n_discard") or 1
        if len(hole) != 3 or k != 1:
            return {"action": "discard", "cards": list(obs["hole"][:k])}
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        opts = [[hole[a], hole[b]] for a, b in _PAIRS3]
        score = [0.0, 0.0, 0.0]
        sample = self.sample
        clock = time.perf_counter
        n = 0
        while n < 300:
            cards = sample(deck, need + 2)
            bd = board + cards[:need]
            ov = value(cards[need:] + bd)
            for j in range(3):
                hv = value(opts[j] + bd)
                if hv > ov:
                    score[j] += 1.0
                elif hv == ov:
                    score[j] += 0.5
            n += 1
            if n >= 24 and clock() - t0 > 0.00038:
                break
        # tie-break by current made value
        j = max(range(3), key=lambda j: (score[j], value(opts[j] + board)))
        keep = opts[j]
        out = [c for c in obs["hole"] if CARD[c] not in keep]
        return {"action": "discard", "cards": out[:1]}

    # ------------------------------------------------------------------
    def mc(self, hole, board, n_opp, opp_hole, t0, budget):
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        nsim = min(n_opp, 3)
        if len(hole) == 3:
            hero = self.best_keep(hole, board)
        else:
            hero = hole
        draw = need + opp_hole * nsim
        sample = self.sample
        clock = time.perf_counter
        res = []
        n = 0
        while n < 400:
            cards = sample(deck, draw)
            bd = board + cards[:need]
            hv = value(hero + bd)
            top = -1
            for j in range(need, draw, opp_hole):
                v = value(cards[j:j + opp_hole] + bd)
                if v > top:
                    top = v
            res.append((top, 1.0 if hv > top else (0.5 if hv == top else 0.0)))
            n += 1
            if n >= 20 and clock() - t0 > budget:
                break
        return res, nsim

    def range_x(self, obs, opps, street, frac):
        hist = obs["history"]
        best = 1.0
        for s in opps:
            st = self.S(s)
            ag = min(2.0, max(0.5, st.agg_r() / 0.3))
            x = 1.0
            raised0 = False
            called0 = False
            for h in hist:
                if h[1] != s:
                    continue
                if h[0] == 0:
                    if h[2] == "raise":
                        raised0 = True
                    elif h[2] == "call":
                        called0 = True
            if raised0:
                x *= min(1.0, max(0.3, st.pfr_r() * 1.6)) ** 0.5
            elif called0:
                x *= min(1.0, max(0.4, st.vpip_r() * 1.3)) ** 0.5
            for stt in range(1, street + 1):
                r = c = rr = False
                prior = False
                for h in hist:
                    if h[0] == stt:
                        if h[1] == s:
                            if h[2] == "raise":
                                r = True
                                if prior:
                                    rr = True
                            elif h[2] == "call":
                                c = True
                        if h[2] == "raise":
                            prior = True
                if r:
                    if stt == street:
                        f = (0.62 - 0.2 * min(frac, 1.5)) * ag ** 0.7
                    else:
                        f = 0.55 * ag ** 0.7
                    if rr:
                        f *= min(0.85, _P['rr'] * ag ** 0.6)
                    x *= min(0.9, f)
                elif c:
                    x *= 0.72
            if x < best:
                best = x
        return max(0.06, best)

    def postflop(self, obs, t0):
        me = self.seat
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        street = obs["street_index"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        in_hand = obs["in_hand"]
        hist = obs["history"]
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        pts = self.points
        opp_hole = 3 if len(hole) == 3 else 2
        res, nsim = self.mc(hole, board, max(1, n_opp), opp_hole, t0, 0.0004)
        N = len(res)
        ext = max(1, n_opp) / nsim
        res.sort(key=lambda r: -r[0])
        pre = [0.0]
        acc = 0.0
        for r in res:
            acc += r[1]
            pre.append(acc)

        def eq_top(X):
            k = int(N * X + 0.5)
            if k < 5:
                k = min(N, 5)
            if k > N:
                k = N
            return (pre[k] / k) ** ext

        st_raises = [h for h in hist if h[0] == street and h[2] == "raise"]
        last_aggr = None
        for h in hist:
            if h[2] == "raise" and h[0] < street:
                last_aggr = h[1]
        i_was_aggr = last_aggr == me
        my_stack = stacks[me]
        alive = obs["alive"]
        n_alive = max(2, len(alive))
        total_chips = sum(stacks) + pot
        last_street = street == 3
        widen = _P['wf'] if street == 1 else (_P['wt'] if street == 2 else 1.0)
        frac = to_call / max(1.0, pot - to_call) if to_call > 0 else 0.0
        X = self.range_x(obs, opps, street, frac)

        if to_call == 0:
            e_cur = eq_top(min(1.0, X * widen))
            e_call = eq_top(min(1.0, X * 0.6 * widen))
            if e_call >= _P['vb'] or e_cur >= 0.72:
                fr = 0.6 if not last_street else 0.7
                if e_call >= 0.7:
                    fr = 0.8
                amt = bets[me] + fr * pot
                if my_stack <= 1.3 * pot or amt >= 0.7 * (my_stack + bets[me]):
                    if e_call >= 0.6:
                        return self._allin(obs)
                    amt = bets[me] + 0.5 * pot
                return self._raise(obs, amt)
            if n_opp <= 2 and e_cur < 0.6:
                pf = 1.0
                for s in opps:
                    pf *= self.S(s).fb_r()
                freq = 0.0
                if i_was_aggr and street == 1:
                    freq = 0.3 + 0.6 * pf
                elif i_was_aggr and street == 2:
                    freq = 0.1 + 0.5 * pf
                elif n_opp == 1 and street >= 2 and hist and hist[-1][2] == "check":
                    freq = 0.05 + 0.45 * pf
                if e_cur > 0.3 and not last_street:
                    freq += 0.1
                if self.rng.random() < freq * _P['bluff_mult'] * (1.0 if n_opp == 1 else 0.5):
                    amt = bets[me] + 0.5 * pot
                    if amt >= 0.5 * (my_stack + bets[me]):
                        return {"action": "check"}
                    return self._raise(obs, amt)
            return {"action": "check"}

        bettor = st_raises[-1][1] if st_raises else (opps[0] if opps else me)
        e = eq_top(min(1.0, X * widen))
        odds = to_call / (pot + to_call)
        if to_call >= 0.45 * my_stack:
            my_total = my_stack + bets[me]
            ot = stacks[bettor] + bets[bettor]
            risk = min(my_total, ot)
            dead = pot - bets[me] - bets[bettor]
            u_fold = self.U(obs, my_stack, {bettor: stacks[bettor] + pot})
            u_win = self.U(obs, my_total + risk + dead, {bettor: ot - risk})
            u_lose = self.U(obs, my_total - risk, {bettor: ot + risk + dead})
            if e * u_win + (1 - e) * u_lose > u_fold:
                return self._allin(obs)
            return self._fold(obs)
        if obs["max_raise_to"] > 0 and e >= 0.62:
            e_r = eq_top(min(1.0, X * 0.5 * widen))
            if e_r >= 0.55:
                tgt = max(bets) + 2.2 * to_call + pot * 0.3
                if tgt >= 0.5 * (my_stack + bets[me]):
                    return self._allin(obs)
                return self._raise(obs, tgt)
        margin = (0.03 if last_street else 0.0) + _P['call_margin']
        if e >= odds + margin:
            return self._call(obs)
        return self._fold(obs)

    # ------------------------------------------------------------------
    def observe(self, ev):
        try:
            if ev.get("type") != "hand_end":
                return
            hist = ev.get("history") or []
            me = self.seat
            seen = set()
            vp = set()
            pr = set()
            raised = False
            faced = set()
            cur_st = -1
            st_bet = False
            for h in hist:
                st, seat, a = h[0], h[1], h[2]
                if a not in ("fold", "check", "call", "raise"):
                    continue
                if st != cur_st:
                    cur_st = st
                    st_bet = False
                if st == 0:
                    if seat != me:
                        seen.add(seat)
                        if a in ("call", "raise"):
                            vp.add(seat)
                        if a == "raise":
                            pr.add(seat)
                        if raised and seat not in faced:
                            faced.add(seat)
                            S = self.S(seat)
                            S.f2r_o += 1
                            if a == "fold":
                                S.f2r += 1
                    if a == "raise":
                        raised = True
                else:
                    if seat != me:
                        S = self.S(seat)
                        if st_bet:
                            S.fb_o += 1
                            if a == "fold":
                                S.fb += 1
                        if a != "fold":
                            S.pa += 1
                            if a == "raise":
                                S.pagg += 1
                    if a == "raise":
                        st_bet = True
            for s in seen:
                S = self.S(s)
                S.hands += 1
                if s in vp:
                    S.vpip += 1
                if s in pr:
                    S.pfr += 1
        except Exception:
            pass
