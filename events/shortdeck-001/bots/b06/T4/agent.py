import json
import os
import random
from time import perf_counter

from .ev import CID, KEY, T, FS, START, FL, RBIT, SUIT_OF_FLAG

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pf.json")))
PCT = [p / 10000.0 for p in _D["pct"]]
EQM = [[e / 10000.0 for e in row] for row in _D["eqm"]]
VS = [[e / 10000.0 for e in row] for row in _D["vs"]]
WCLS = [6 if c // 9 == c % 9 else (4 if c // 9 > c % 9 else 12) for c in range(81)]
ORDER = sorted(range(81), key=lambda c: PCT[c])
_TOT = float(sum(WCLS))
# cumulative top-fraction of each class (fraction of combos at least as good, midpoint)
CUM = [0.0] * 81
_acc = 0.0
for _c in ORDER:
    CUM[_c] = (_acc + WCLS[_c] / 2.0) / _TOT
    _acc += WCLS[_c]
FGRID = [0.03, 0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def _eq_vs_top(c, f):
    num = den = 0.0
    acc = 0.0
    for c2 in ORDER:
        w = WCLS[c2]
        lo = acc / _TOT
        acc += w
        if lo >= f:
            break
        part = min(1.0, (f - lo) / (w / _TOT))
        num += w * part * VS[c][c2]
        den += w * part
    return num / den if den else 0.5


EQR = [[_eq_vs_top(c, f) for f in FGRID] for c in range(81)]


def eq_vs_range(c, f):
    if f <= FGRID[0]:
        return EQR[c][0]
    for i in range(1, len(FGRID)):
        if f <= FGRID[i]:
            a, b = FGRID[i - 1], FGRID[i]
            t = (f - a) / (b - a)
            return EQR[c][i - 1] * (1 - t) + EQR[c][i] * t
    return EQR[c][-1]


def cls_of(a, b):
    ra, rb = a >> 2, b >> 2
    hi, lo = (ra, rb) if ra >= rb else (rb, ra)
    if ra == rb:
        return hi * 9 + hi
    if (a & 3) == (b & 3):
        return hi * 9 + lo
    return lo * 9 + hi


# combo -> top fraction of its class (for range sampling)
CPCT = [[CUM[cls_of(a, b)] if a != b else 2.0 for b in range(36)] for a in range(36)]


def _val(s, cards):
    v = T[s >> 16]
    if s & FL:
        su = SUIT_OF_FLAG[s & FL]
        m = 0
        for c in cards:
            if c & 3 == su:
                m |= RBIT[c]
        f = FS[m]
        if f > v:
            v = f
    return v


def icm(stacks, pay):
    n = len(stacks)
    pay = list(pay[:n]) + [0.0] * max(0, n - len(pay))
    paid = max((k + 1 for k, p in enumerate(pay) if p), default=0)
    memo = {}

    def rest(mask):
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < paid:
            total = sum(stacks[i] for i in members)
            for i in members:
                p = stacks[i] / total if total > 0 else 1.0 / len(members)
                if p <= 0:
                    continue
                res[i] += p * pay[place]
                sub = rest(mask & ~(1 << i))
                for j in members:
                    if j != i:
                        res[j] += p * sub[j]
        memo[mask] = res
        return res

    return rest((1 << n) - 1)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = list(config.get("points") or [100, 45, 20, 8, 0, 0, 0, 0])
        self.nseats = config.get("seats", 8)
        # opponent stats
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.shoves = [0] * 16
        self.pagg = [0] * 16
        self.pcall = [0] * 16
        self.ftb_f = [0] * 16
        self.ftb_n = [0] * 16
        self.start_tot = {}
        self.s0 = config.get("starting_stack", 2000)
        self.cur_hand = -1
        self.my_pf_aggr = False
        self.bet_streets = set()

    # ---------------- helpers -----------------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur_st = -1
            bettor = None
            for st, seat, a, amt in hist:
                seen.add(seat)
                if st != cur_st:
                    cur_st = st
                    bettor = None
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(seat)
                    if a == "raise":
                        pr.add(seat)
                        if amt >= 0.95 * self.start_tot.get(seat, self.s0):
                            self.shoves[seat] += 1
                else:
                    if bettor is not None and seat != bettor and a in ("fold", "call", "raise"):
                        self.ftb_n[seat] += 1
                        if a == "fold":
                            self.ftb_f[seat] += 1
                    if a == "raise":
                        self.pagg[seat] += 1
                        bettor = seat
                    elif a == "call":
                        self.pcall[seat] += 1
            for s in seen:
                self.hands[s] += 1
            stk = event.get("stacks")
            if stk:
                self.start_tot = {i: v for i, v in enumerate(stk)} if isinstance(stk, list) else {int(k): v for k, v in stk.items()}
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass

    def vp_rate(self, s):
        return (self.vpip[s] + 2.0) / (self.hands[s] + 6.0)

    def pfr_rate(self, s):
        return (self.pfr[s] + 1.2) / (self.hands[s] + 6.0)

    def agg(self, s):
        return (self.pagg[s] + 1.0) / (self.pagg[s] + self.pcall[s] + 2.0)

    def ftb(self, s):
        return (self.ftb_f[s] + 2.0) / (self.ftb_n[s] + 5.0)

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    @staticmethod
    def _fold(obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    @staticmethod
    def _call(obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _raise(self, obs, to):
        lg = obs["legal"]
        if ("raise" in lg or "bet" in lg) and obs["max_raise_to"] > 0:
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            to = int(to)
            if to >= hi * 0.75:
                to = hi
            to = max(lo, min(hi, to))
            return {"action": "raise", "amount": to}
        return self._call(obs)

    def _allin(self, obs):
        lg = obs["legal"]
        if ("raise" in lg or "bet" in lg) and obs["max_raise_to"] > 0:
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self._call(obs)

    # ---------------- main -----------------
    def _act(self, obs):
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["hand_id"] != self.cur_hand:
            self.cur_hand = obs["hand_id"]
            self.my_pf_aggr = False
            self.bet_streets = set()
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        if obs["street_index"] == 0 or not board:
            return self._preflop(obs, hole)
        return self._postflop(obs, hole, board)

    def _icm_ok(self, obs, eq, call_amt, win_gain, opp):
        """Return ICM-based decision value: (ev_call - ev_fold) in points, or None."""
        alive = [s for s in obs["alive"] if obs["stacks"][s] + obs["bets"][s] > 0]
        if len(alive) > 4 or len(alive) < 2:
            return None
        me = obs["seat"]
        st = obs["stacks"]
        base = {s: float(st[s]) for s in alive}
        pot = obs["pot"]
        # fold: opp collects the pot
        f = dict(base)
        f[opp] = f.get(opp, 0) + pot
        w = dict(base)
        w[me] = base[me] + win_gain
        l = dict(base)
        l[me] = base[me] - call_amt
        l[opp] = l.get(opp, 0) + pot + call_amt
        order = alive
        n = len(order)
        pay = self.points[: len(obs["alive"])][: n] if len(self.points) >= n else self.points
        pay = self.points[:n]
        idx = order.index(me)

        def ev(d):
            sts = [max(0.0, d[s]) for s in order]
            return icm(sts, pay)[idx]

        return eq * ev(w) + (1 - eq) * ev(l) - ev(f)

    def _preflop(self, obs, hole):
        me = obs["seat"]
        st, bets = obs["stacks"], obs["bets"]
        bb = max(1, obs["bb"])
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_total = st[me] + bets[me]
        others = [p for p in obs["in_hand"] if p != me]
        if not others:
            return self._call(obs)
        opp_max = max(st[p] + bets[p] for p in others)
        eff = min(my_total, opp_max)
        eff_bb = eff / bb
        c = cls_of(hole[0], hole[1])
        top = CUM[c]  # 0 best .. 1 worst
        hist = [h for h in obs["history"] if h[0] == 0]
        raises = [(h[1], h[3]) for h in hist if h[2] == "raise"]
        alive = obs["alive"]
        bbs = obs["bb_seat"]
        srt = sorted(alive)
        start = 0
        for i, s in enumerate(srt):
            if s > bbs:
                start = i
                break
        else:
            start = 0
        order = srt[start:] + srt[:start]
        n_behind = len(order) - 1 - order.index(me) if me in order else 0
        limpers = 0
        for h in hist:
            if h[2] == "raise":
                break
            if h[2] == "call":
                limpers += 1
        n_alive = len(alive)

        if not raises:
            # unopened (maybe limpers)
            if me == bbs and to_call == 0:
                if top <= 0.10 and n_behind == 0:
                    if eff_bb <= 12:
                        return self._allin(obs)
                    return self._raise(obs, bb * (3 + limpers))
                return {"action": "check"}
            nb = n_behind + limpers
            ih = set(obs["in_hand"])
            bh = [s for s in order[order.index(me) + 1:] if s in ih] if me in order else []
            if bh:
                vpb = sum(self.vp_rate(s) for s in bh) / len(bh)
                steal = max(0.8, min(1.3, 1.0 + 1.5 * (0.3 - vpb)))
            else:
                steal = 1.0
            if eff_bb <= 13:
                pf = min(1.0, 0.62 * (10.0 / max(eff_bb, 1.0)) ** 0.85 / max(nb, 1) ** 0.7)
                if n_alive <= 3:
                    pf = min(1.0, pf * 1.15)
                pf = min(1.0, pf * steal)
                if top <= pf:
                    return self._allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                return {"action": "fold"}
            of = {0: 0.0, 1: 0.5, 2: 0.42, 3: 0.32, 4: 0.25, 5: 0.2, 6: 0.17}.get(n_behind, 0.14)
            if limpers:
                of *= 0.7
            if n_alive == 2:
                of = 0.85
            elif n_alive <= 4:
                of = min(0.65, of * 1.3)
            of = min(0.9, of * steal)
            if top <= of:
                size = (2.5 if n_behind > 1 else 3.0) * bb + limpers * bb
                if size >= 0.33 * my_total:
                    return self._allin(obs)
                self.my_pf_aggr = True
                return self._raise(obs, size)
            if me == obs["sb_seat"] and to_call <= bb * 0.5 + 1 and top <= 0.6 and not limpers:
                return self._call(obs)
            if limpers and top <= 0.3 and to_call <= bb:
                return self._call(obs)
            return self._fold(obs)

        # facing raise(s)
        nr = len(raises)
        vill = raises[-1][0]
        v_total = st[vill] + bets[vill]
        v_allin = st[vill] == 0
        pfr = self.pfr_rate(vill)
        jr = (self.shoves[vill] + 0.3) / (self.hands[vill] + 3.0)
        if nr == 1:
            f = min(0.6, max(0.1, pfr * 1.1))
            if v_allin:
                vbb = v_total / bb
                nb_v = len(order) - 1 - order.index(vill) if vill in order else 2
                f_pos = min(1.0, 0.62 * (10.0 / max(vbb, 1.0)) ** 0.85 / max(nb_v, 1) ** 0.7)
                f = min(1.0, max(0.08, f_pos * 1.15, jr * 1.3))
        elif nr == 2:
            f = min(0.3, max(0.06, pfr * 0.45))
            if v_allin:
                f = min(0.45, max(f, 0.7 / max(v_total / bb, 1.0) ** 0.5))
        else:
            f = 0.05
        if nr == 1:
            if n_alive == 2:
                f = max(f, 0.6)
            elif n_alive == 3:
                f = max(f, 0.4)
            elif n_alive == 4:
                f = max(f, 0.3)
        elif nr == 2 and n_alive <= 3:
            f = max(f, 0.25)
        eq = eq_vs_range(c, f)
        # other players already in (callers) besides villain
        in_set = set(obs["in_hand"])
        callers = set(h[1] for h in hist if h[2] in ("call", "raise") and h[1] != vill and h[1] != me and h[1] in in_set)
        n_in = 1 + len(callers)
        if n_in > 1:
            eq = eq ** (1.0 + 0.6 * (n_in - 1))
        call_amt = min(to_call, st[me])
        need = call_amt / (pot + call_amt)
        commit = call_amt >= 0.4 * my_total or v_allin or eff_bb <= 15
        # players still to act behind us who could wake up
        behind_pen = 0.02 * n_behind
        # re-shove over a single open, counting fold equity
        if nr == 1 and not v_allin and not callers and eff_bb <= 25 and obs["max_raise_to"] > 0:
            X = min(my_total, v_total)
            dead = max(0, pot - bets[me] - bets[vill])
            f_call = max(0.04, f * 0.5)
            eqc = eq_vs_range(c, f_call) - behind_pen
            fe = 0.45
            ev_shove = fe * pot + (1 - fe) * (bets[me] - X + eqc * (2 * X + dead))
            ev_call = eq * (0.85 if n_behind else 0.92) * (pot + call_amt) - call_amt
            if ev_shove > 0 and ev_shove >= ev_call:
                return self._allin(obs)
        if commit:
            margin = 0.02 + behind_pen
            dv = None
            if v_allin or call_amt >= 0.9 * st[me]:
                excess = max(0, bets[vill] - (bets[me] + call_amt))
                win_gain = max(0, pot - excess)
                dv = self._icm_ok(obs, eq, call_amt, win_gain, vill)
            if dv is not None:
                if dv > 0:
                    return self._allin(obs) if eq > 0.55 else self._call(obs)
                return self._fold(obs)
            if eq >= need + margin:
                if eq > 0.5 and obs["max_raise_to"] > 0:
                    return self._allin(obs)
                return self._call(obs)
            return self._fold(obs)
        # deep-ish: 3bet / call / fold
        if eq >= 0.6 and obs["max_raise_to"] > 0:
            to = raises[-1][1] * 3 + (pot - sum(bets)) * 0
            if to >= 0.35 * my_total:
                return self._allin(obs)
            self.my_pf_aggr = True
            return self._raise(obs, to)
        ip = n_behind == 0 and me != obs["bb_seat"] and me != obs["sb_seat"]
        real = 0.95 if ip else 0.85
        if eq * real >= need + 0.03 and to_call <= 0.25 * my_total:
            return self._call(obs)
        return self._fold(obs)

    # ---------------- postflop -----------------
    def _ranges(self, obs, others):
        hist = obs["history"]
        last_r = None
        nr = 0
        callers = set()
        for st_i, seat, a, amt in hist:
            if st_i != 0:
                continue
            if a == "raise":
                last_r = seat
                nr += 1
            elif a == "call":
                callers.add(seat)
        rng = []
        for p in others:
            if p == last_r:
                f = min(0.5, max(0.1, self.pfr_rate(p) * (1.1 if nr == 1 else 0.5)))
            elif nr >= 1 and p in callers:
                f = min(0.7, max(0.2, self.vp_rate(p) * 1.2))
            else:
                f = 1.0
            rng.append(f)
        return rng, last_r

    def _mc(self, hole, board, ranges, budget):
        used0 = 0
        for c in hole:
            used0 |= 1 << c
        for c in board:
            used0 |= 1 << c
        deck = [c for c in range(36) if not used0 >> c & 1]
        D = len(deck)
        need = 5 - len(board)
        bkey = START
        for c in board:
            bkey += KEY[c]
        hkey = KEY[hole[0]] + KEY[hole[1]]
        rnd = self.rng.random
        t_end = perf_counter() + budget
        wins = 0.0
        n = 0
        cp = CPCT
        while True:
            for _ in range(8):
                used = used0
                opps = []
                ok = True
                for f in ranges:
                    for tries in range(10):
                        a = deck[int(rnd() * D)]
                        b = deck[int(rnd() * D)]
                        if a == b or (used >> a & 1) or (used >> b & 1):
                            continue
                        if cp[a][b] > f and tries < 9:
                            continue
                        break
                    else:
                        ok = False
                        break
                    if a == b or (used >> a & 1) or (used >> b & 1):
                        ok = False
                        break
                    used |= (1 << a) | (1 << b)
                    opps.append((a, b))
                if not ok:
                    continue
                run = []
                rk = bkey
                while len(run) < need:
                    x = deck[int(rnd() * D)]
                    if used >> x & 1:
                        continue
                    used |= 1 << x
                    run.append(x)
                    rk += KEY[x]
                full = board + run
                mine = _val(rk + hkey, full + hole)
                best = -1
                ties = 0
                for a, b in opps:
                    v = _val(rk + KEY[a] + KEY[b], full + [a, b])
                    if v > best:
                        best = v
                        ties = 1 if v == mine else 0
                    elif v == best and v == mine:
                        ties += 1
                if mine > best:
                    wins += 1.0
                elif mine == best:
                    wins += 1.0 / (1 + ties)
                n += 1
            if perf_counter() > t_end or n >= 600:
                break
        return wins / n if n else 0.5

    def _river(self, hole, board, f, top_q):
        used0 = 0
        for c in hole + board:
            used0 |= 1 << c
        deck = [c for c in range(36) if not used0 >> c & 1]
        bkey = START
        for c in board:
            bkey += KEY[c]
        mine = _val(bkey + KEY[hole[0]] + KEY[hole[1]], board + hole)
        cp = CPCT
        items = []
        D = len(deck)
        bm = [0, 0, 0, 0]
        for c in board:
            bm[c & 3] |= RBIT[c]
        for i in range(D):
            a = deck[i]
            ka = bkey + KEY[a]
            cpa = cp[a]
            for j in range(i + 1, D):
                b = deck[j]
                w = 1.0 if cpa[b] <= f else 0.15
                s = ka + KEY[b]
                if s & FL:
                    su = SUIT_OF_FLAG[s & FL]
                    m = bm[su]
                    if a & 3 == su:
                        m |= RBIT[a]
                    if b & 3 == su:
                        m |= RBIT[b]
                    v = T[s >> 16]
                    fv = FS[m]
                    if fv > v:
                        v = fv
                else:
                    v = T[s >> 16]
                items.append((v, w))
        W = 0.0
        E = 0.0
        for v, w in items:
            W += w
            if mine > v:
                E += w
            elif mine == v:
                E += 0.5 * w
        eq_all = E / W if W else 0.5
        if top_q >= 1.0:
            return eq_all, eq_all
        items.sort(key=lambda x: -x[0])
        lim = W * top_q
        acc = 0.0
        e2 = 0.0
        for v, w in items:
            if acc >= lim:
                break
            take = min(w, lim - acc)
            acc += take
            if mine > v:
                e2 += take
            elif mine == v:
                e2 += 0.5 * take
        return eq_all, (e2 / acc if acc else eq_all)

    def _postflop(self, obs, hole, board):
        me = obs["seat"]
        st, bets = obs["stacks"], obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        street = obs["street_index"]
        others = [p for p in obs["in_hand"] if p != me]
        if not others:
            return self._call(obs)
        n_opp = len(others)
        ranges, pf_r = self._ranges(obs, others)
        my_stack = st[me]
        hist_s = [h for h in obs["history"] if h[0] == street]
        bettor = None
        for h in hist_s:
            if h[2] == "raise":
                bettor = h[1]
        bet_frac = to_call / max(1.0, pot - to_call)
        if street >= 3 or len(board) >= 5:
            if to_call > 0:
                a = self.agg(bettor) if bettor is not None else 0.4
                fr = min(bet_frac, 2.0)
                if fr <= 0.4:
                    qb = 0.55
                elif fr <= 0.8:
                    qb = 0.55 - (fr - 0.4) * 0.25
                elif fr <= 1.3:
                    qb = 0.45 - (fr - 0.8) * 0.46
                else:
                    qb = max(0.12, 0.22 - (fr - 1.3) * 0.15)
                q = qb * (1.0 + 2.0 * max(0.0, a - 0.6))
                q = max(0.1, min(0.8, q))
            else:
                q = 1.0
                fr = 0.0
            fmin = min(ranges) if ranges else 1.0
            eq1, eqt = self._river(hole, board, fmin, q)
            if n_opp > 1:
                eq1 = eq1 ** n_opp
                eqt = eqt ** n_opp
            eq = eq1
            wt = 0.8 if fr < 0.8 else 0.9
            eq_adj = wt * eqt + (1 - wt) * eq1 if to_call > 0 else eq1
        else:
            eq = self._mc(hole, board, ranges[:3], 0.00028)
            if n_opp > 3:
                eq = eq ** (n_opp / 3.0)
            if to_call > 0:
                a = self.agg(bettor) if bettor is not None else 0.4
                pen = (0.04 + 0.09 * min(bet_frac, 1.5)) * (1.25 - 0.6 * (a - 0.4))
                if street == 2:
                    pen *= 1.15
                eq_adj = eq - pen
            else:
                eq_adj = eq
        call_amt = min(to_call, my_stack)
        need = call_amt / (pot + call_amt) if call_amt > 0 else 0.0
        spr = my_stack / max(1.0, pot)
        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        max_bet = max(bets) if bets else 0
        thr = min(0.66, 1.3 / (n_opp + 1))
        if to_call > 0:
            # facing a bet
            if can_raise and eq_adj >= max(0.72, thr + 0.12):
                to = max_bet + 0.85 * (pot + to_call)
                if spr < 2.0 or to >= 0.5 * (my_stack + bets[me]):
                    return self._allin(obs)
                return self._raise(obs, to)
            if eq_adj >= need + 0.01:
                return self._call(obs)
            return self._fold(obs)
        # checked to us / first to act
        if not can_raise:
            return self._call(obs)
        ft = sum(self.ftb(p) for p in others) / n_opp
        bm = max(0.3, min(1.8, ft / 0.4))
        if ft < 0.3:
            thr -= 0.04
        elif ft > 0.55:
            thr += 0.03
        if street >= 3:
            thr += 0.05
        if eq >= thr:
            frac = 0.7 if eq < 0.85 else 0.85
            if street >= 3:
                frac = 0.65 if eq < 0.85 else 0.9
            if ft < 0.3:
                frac *= 1.2
            if spr <= 1.3:
                return self._allin(obs)
            self.bet_streets.add(street)
            return self._raise(obs, max(obs["min_raise_to"], frac * pot))
        r = self.rng.random()
        if street == 1 and self.my_pf_aggr and n_opp <= 2:
            p = 0.55 if n_opp == 1 else 0.3
            if eq >= 0.3:
                p += 0.15
            if r < p * bm:
                self.bet_streets.add(street)
                return self._raise(obs, max(obs["min_raise_to"], 0.5 * pot))
        if street == 2 and n_opp == 1 and 1 in self.bet_streets and eq >= 0.38 and r < 0.5 * bm:
            self.bet_streets.add(street)
            return self._raise(obs, max(obs["min_raise_to"], 0.55 * pot))
        if street >= 3 and n_opp == 1 and 2 in self.bet_streets and eq < 0.2 and r < 0.3 * bm:
            return self._raise(obs, max(obs["min_raise_to"], 0.6 * pot))
        return {"action": "check"}
