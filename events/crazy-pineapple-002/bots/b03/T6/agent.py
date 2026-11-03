"""b03 crazy pineapple bot: precomputed 3-card preflop equities, push/fold,
range-weighted Monte Carlo postflop, simple opponent stats."""

import json
import os
import random
import time

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
_HERE = os.path.dirname(os.path.abspath(__file__))


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
    for lo in range(9):
        tops[sum(1 << r for r in range(lo, lo + 5))] = lo + 4
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
# category shifts: high 0, pair 1, two pair 2, trips 3, straight 4, flush 5, full house 6, quads 7, sf 8
S = [c << 20 for c in range(9)]


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
            v = S[7] | q << 16 | TOP1[m1 & ~(1 << q)] << 12
            if v > best:
                best = v
        if m3:
            t = m3.bit_length() - 1
            rest = m2 & ~(1 << t)
            if rest:
                v = S[6] | t << 16 | (rest.bit_length() - 1) << 12
                if v > best:
                    best = v
            v = S[3] | t << 16 | TOP2[m1 & ~(1 << t)] << 8
            if v > best:
                best = v
        p = m2.bit_length() - 1
        rest = m2 & ~(1 << p)
        if rest:
            p2 = rest.bit_length() - 1
            v = S[2] | p << 16 | p2 << 12 | TOP1[m1 & ~(1 << p | 1 << p2)] << 8
            if v > best:
                best = v
        v = S[1] | p << 16 | TOP3[m1 & ~(1 << p)] << 4
        if v > best:
            best = v
    t = STOP[m1]
    if t >= 0:
        v = S[4] | t << 16
        if v > best:
            best = v
    for f in sm:
        if f.bit_count() >= 5:
            t = STOP[f]
            v = S[8] | t << 16 if t >= 0 else S[5] | TOP5[f]
            if v > best:
                best = v
    return best


def _load(name):
    try:
        with open(os.path.join(_HERE, name)) as f:
            return {int(k): tuple(x / 1000.0 for x in v) for k, v in json.load(f).items()}
    except Exception:
        return {}


PRE = _load("pre3.json")   # key -> (eq vs1, vs2, vs4 random)
RNG = _load("rng3.json")   # key -> (eq vs top10, top25, top50, pct)


P = dict(w2a=0.05, w2p=0.25, w1a=0.2, w1p=0.6, wpa=0.5, wpp=0.85, vth1=0.66, vthm=0.74,
         bf1=0.6, bf2=0.85, semi=0.3, bluff=0.2, thin=0.56, rth=0.82, rmarg=0.03, marg=0.0,
         open=1.0, push=1.0, pfbb=13, callm=0.08, callpct=0.18, aim=0.03, sbc=0.4, bbd=0.45, adapt=1, icm=1, icmpush=1, qcm=0.6, shadapt=1,
         rmodel=1, xr=0.09, xb=0.58, bw=0.05, mw=0.8, myr=1, keep3=1, keep3b=0, shade=0.04, soft=0, enum=1, anal=1, barrel=0.8, qsh=0.75, posnb=1)


PAIRS = {L: tuple((i, j) for i in range(L) for j in range(i + 1, L)) for L in range(36, 50)}
STRIDES = (101, 103, 107, 109, 113, 127, 131, 137)


def hkey(cs):
    a, b, c = sorted(cs)
    return a * 2704 + b * 52 + c


def icm_me(stk, i, pay):
    """Malmuth-Harville value for player i: places 1-4 exact, the rest averaged."""
    if stk[i] <= 0:
        m = sum(1 for x in stk if x > 0)
        return pay[m] if m < len(pay) else 0.0
    idx = [j for j in range(len(stk)) if stk[j] > 0 and j != i]
    si = stk[i]
    T = si + sum(stk[j] for j in idx)
    m = len(idx) + 1
    p0 = si / T
    p1 = p2 = p3 = 0.0
    for j in idx:
        sj = stk[j]
        pj = sj / T
        T1 = T - sj
        p1 += pj * si / T1
        if m >= 3:
            for k in idx:
                if k == j:
                    continue
                sk = stk[k]
                pjk = pj * sk / T1
                T2 = T1 - sk
                p2 += pjk * si / T2
                if 4 <= m <= 5:
                    for l in idx:
                        if l == j or l == k:
                            continue
                        sl = stk[l]
                        T3 = T2 - sl
                        p3 += pjk * sl / T2 * si / T3
    ps = (p0, p1, p2, p3)
    ev = 0.0
    tot = 0.0
    d = 4 if m <= 5 else 3
    for k in range(min(d, m)):
        ev += ps[k] * pay[k]
        tot += ps[k]
    if m > d:
        rest = 1.0 - tot
        tail = pay[d:m]
        if rest > 0 and tail:
            ev += rest * sum(tail) / len(tail)
    return ev


def push_pct(sbb, nb):
    """Approximate push range (fraction of hands) for stack sbb BB with nb players behind."""
    c = (2.3, 1.6, 1.2, 0.97, 0.82, 0.74, 0.70, 0.68)[max(0, min(nb - 1, 7))]
    return min(1.0, c / max(1.0, sbb) ** 0.6)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        n = config.get("seats", 8)
        # opponent stats per seat
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.shoves = [0] * 16
        self.aggr = [0] * 16
        self.passive = [0] * 16
        self.faced = [0] * 16
        self.fcall = [0] * 16

    # ------------------------------------------------------------------ utils
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in hist:
                if seat is None or seat < 0 or seat >= 16:
                    continue
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
                        self.passive[seat] += 1
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
            # preflop shoves and responses to shoves
            pay = event.get("payoffs") or {}
            est = event.get("stacks") or []
            start = {}
            for k, v in pay.items():
                k = int(k)
                if 0 <= k < len(est):
                    start[k] = est[k] - v
            shoved = False
            sb = {}
            for st, seat, act, amt in hist:
                if st != 0:
                    break
                if seat not in start:
                    continue
                if act in ("sb", "bb"):
                    sb[seat] = amt or 0
                elif act == "raise":
                    sb[seat] = amt or 0
                    if amt and amt >= start[seat]:
                        self.shoves[seat] += 1
                        if shoved:
                            self.fcall[seat] += 1
                            self.faced[seat] += 1
                        shoved = True
                    elif shoved:
                        self.fcall[seat] += 1
                        self.faced[seat] += 1
                elif shoved and act in ("call", "fold"):
                    self.faced[seat] += 1
                    if act == "call":
                        self.fcall[seat] += 1
        except Exception:
            pass

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

    # ------------------------------------------------------------- actions
    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _call(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "allin"}

    def _raise(self, obs, amount):
        legal = obs["legal"]
        if ("raise" not in legal and "bet" not in legal) or obs["max_raise_to"] <= 0:
            return self._call(obs)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        a = int(amount)
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        me = obs["seat"]
        # if raise leaves little behind, just shove
        left = obs["stacks"][me] + obs["bets"][me] - a
        if left < 0.3 * (obs["pot"] + a - obs["bets"][me]):
            a = hi
        return {"action": "raise", "amount": a}

    def _allin(self, obs):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self._call(obs)

    # ------------------------------------------------------------- helpers
    def opp_loose(self, s):
        h = self.hands[s]
        if h < 6:
            return 0.35, 0.15
        return (self.vpip[s] + 1.0) / (h + 3.0), (self.pfr[s] + 0.5) / (h + 3.0)

    def eq_vs_range(self, key, q):
        r = RNG.get(key)
        p = PRE.get(key)
        e1 = p[0] if p else 0.5
        if not r:
            return 0.5 + (e1 - 0.5) * (1.0 - 0.5 * (1 - q))  # crude
        pts = ((0.10, r[0]), (0.25, r[1]), (0.50, r[2]), (1.0, e1))
        if q <= 0.10:
            return r[0]
        for (q0, e0), (q1, e1_) in zip(pts, pts[1:]):
            if q <= q1:
                w = (q - q0) / (q1 - q0)
                return e0 + w * (e1_ - e0)
        return e1

    def icm_need(self, obs, v, call_amt):
        """Equity needed to call an all-in for call_amt vs seat v under ICM."""
        me = obs["seat"]
        alive = obs["alive"]
        stacks = obs["stacks"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        if me not in alive or v not in alive:
            return None
        n = len(alive)
        pay = list(self.points[:n]) + [0] * max(0, n - len(self.points))
        excess = max(0, to_call - call_amt)
        base = [stacks[s] for s in alive]
        im = alive.index(me)
        iv = alive.index(v)
        fold = list(base)
        fold[iv] += pot
        win = list(base)
        win[im] = stacks[me] + pot - excess
        win[iv] = stacks[v] + excess
        lose = list(base)
        lose[im] = stacks[me] - call_amt
        lose[iv] = stacks[v] + pot + call_amt
        ef = icm_me(fold, im, pay)
        ew = icm_me(win, im, pay)
        el = icm_me(lose, im, pay)
        if ew - el <= 1e-9:
            return None
        return (ef - el) / (ew - el)

    def push_ev(self, obs, key, behind):
        """ICM value of shoving vs folding, one caller at most, callers by observed looseness."""
        me = obs["seat"]
        alive = obs["alive"]
        stacks, bets = obs["stacks"], obs["bets"]
        pot = obs["pot"]
        bb = obs["bb"] or 1
        n = len(alive)
        pay = list(self.points[:n]) + [0] * max(0, n - len(self.points))
        im = alive.index(me)
        base = [stacks[s] for s in alive]
        mytot = stacks[me] + bets[me]
        # fold: pot goes to the big blind (or last player behind)
        fold = list(base)
        tgt = obs["bb_seat"] if obs["bb_seat"] in alive and obs["bb_seat"] != me else behind[-1]
        fold[alive.index(tgt)] += pot
        ev_fold = icm_me(fold, im, pay)
        steal = list(base)
        steal[im] = stacks[me] + pot
        p_none = 1.0
        ev = 0.0
        for j in behind:
            if j not in alive:
                continue
            vp, _ = self.opp_loose(j)
            jt = stacks[j] + bets[j]
            e = min(mytot, jt)
            qc = min(0.6, max(0.05, P["qcm"] * vp + 0.03 + (0.08 if e / bb < 6 else 0.0)))
            if P["shadapt"] and self.faced[j] >= 2:
                fr = (self.fcall[j] + 2.0 * qc) / (self.faced[j] + 2.0)
                qc = min(0.8, max(0.04, fr))
            pj = p_none * qc
            p_none *= 1.0 - qc
            if pj < 1e-4:
                continue
            eqj = self.eq_vs_range(key, qc)
            dead = pot - bets[me] - bets[j]
            ij = alive.index(j)
            w = list(base)
            w[im] = mytot + e + dead
            w[ij] = jt - e
            lo = list(base)
            lo[im] = mytot - e
            lo[ij] = jt + e + dead
            ev += pj * (eqj * icm_me(w, im, pay) + (1 - eqj) * icm_me(lo, im, pay))
        ev += p_none * icm_me(steal, im, pay)
        return ev, ev_fold

    # ------------------------------------------------------------- preflop
    def preflop(self, obs):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        key = hkey(hole)
        pre = PRE.get(key, (0.5, 0.35, 0.22))
        rr = RNG.get(key)
        pct = rr[3] if rr else max(0.0, min(1.0, (0.62 - pre[0]) / 0.3))
        bb = obs["bb"] or 1
        stacks, bets = obs["stacks"], obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        mystack = stacks[me] + bets[me]
        opps = [s for s in in_hand if s != me]
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(mystack, other)
        eff_bb = eff / bb
        to_call = obs["to_call"]
        pot = obs["pot"]
        hist = obs["history"]
        raises = 0
        raiser = -1
        limpers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises += 1
                raiser = seat
            elif act == "call" and raises == 0:
                limpers += 1
        # order / players behind
        n = len(alive)
        btn = obs["button"]
        if n == 2:
            order = [btn] + [s for s in alive if s != btn]
        else:
            bbs = obs["bb_seat"]
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        nb = len(behind)
        # behind includes blinds who posted; for opens they still act
        is_bb = me == obs["bb_seat"]

        if raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= P["pfbb"] or (eff_bb <= P["pfbb"] + 5 and limpers == 0 and nb <= 2):
                th = P["push"] * push_pct(eff_bb, max(1, nb))
                if limpers:
                    th *= 0.7
                if P["icmpush"] and limpers == 0 and nb >= 1 and to_call > 0 and th * 0.5 < pct <= th * 1.6:
                    evp, evf = self.push_ev(obs, key, behind)
                    if evp > evf:
                        return self._allin(obs)
                    if to_call == 0:
                        return {"action": "check"}
                    return self._fold(obs)
                if pct <= th:
                    return self._allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                # SB completing vs BB cheap: fold mostly
                return self._fold(obs)
            # deeper: open raise
            open_th = P["open"] * (0.55, 0.42, 0.32, 0.25, 0.20, 0.17, 0.15, 0.14)[max(0, min(nb - 1, 7))]
            if limpers:
                open_th *= 0.75
            if pct <= open_th:
                size = (2.5 + limpers) * bb if nb > 1 else 3.0 * bb
                return self._raise(obs, size)
            if to_call == 0:
                return {"action": "check"}
            # limp/complete with decent hands when cheap
            if to_call <= 0.5 * bb and pct <= P["sbc"]:
                return self._call(obs)
            if limpers and to_call <= bb and pct <= 0.30 and eff_bb > 30:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        rstack = stacks[raiser] + bets[raiser] if raiser >= 0 else other
        r_allin = raiser >= 0 and stacks[raiser] == 0
        vp, pf = self.opp_loose(raiser) if raiser >= 0 else (0.35, 0.15)
        # players who were still to act behind the raiser when they raised
        if P["posnb"] and raiser in order:
            nbr = max(1, min(3, len(order) - 1 - order.index(raiser)))
        else:
            nbr = 3
        if raises == 1:
            if rstack / bb <= 15 or r_allin:
                q = max(P["qsh"] * push_pct(rstack / bb, nbr), 0.10)
                if P["shadapt"] and self.hands[raiser] >= 8:
                    shr = (self.shoves[raiser] + 0.5) / (self.hands[raiser] + 4.0)
                    q = max(q, min(0.9, 1.2 * shr))
            else:
                q = max(0.08, min(0.5, pf * 1.3))
                if P["posnb"]:
                    q = max(q, (0.0, 0.5, 0.33, 0.22)[nbr])
        else:
            q = max(0.05, min(0.3, pf * 0.6))
        # more than one opponent in -> tighten
        eq = self.eq_vs_range(key, q)
        ncomp = len([s for s in opps if s != raiser and bets[s] > 0 and s not in behind])
        if ncomp >= 1:
            eq -= 0.07 * ncomp
        if nb >= 1:
            eq -= 0.02 * min(nb, 3)
        call_amt = min(to_call, stacks[me])
        need = call_amt / max(1, pot - (to_call - call_amt) + call_amt)
        commit = call_amt >= 0.35 * mystack or (stacks[me] - call_amt) < 4 * bb
        # ICM-ish premium when risking our stack
        risk = min(1.0, call_amt / max(1, mystack))
        prem = 0.0
        if len(alive) <= 6:
            prem = 0.02 * risk
        if commit and P["icm"] and raiser >= 0 and len(alive) > 2:
            ineed = self.icm_need(obs, raiser, call_amt)
            if ineed is not None:
                need = max(need, ineed)
                prem = 0.0
        if commit:
            if eq >= need + prem + P["aim"]:
                return self._allin(obs) if eq > need + 0.08 and not r_allin else self._call(obs)
            return self._fold(obs)
        # not committing: 3-bet strong, call good with odds, else fold
        if eq >= 0.60 or (pct <= 0.03 and raises == 1):
            if eff_bb <= 25:
                return self._allin(obs)
            cur = max(bets)
            return self._raise(obs, cur * 3 + 0.5 * pot)
        if eq >= need + P["callm"] and (pct <= P["callpct"] or call_amt <= 1.0 * bb):
            return self._call(obs)
        if is_bb and call_amt <= 1.5 * bb and pct <= P["bbd"]:
            return self._call(obs)
        return self._fold(obs)

    # ------------------------------------------------------------- postflop
    def equity(self, obs, hole, board, t0, budget, weighted=True):
        """MC equity vs opponents with range weighting by aggression."""
        me = obs["seat"]
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        opps = [s for s in obs["in_hand"] if s != me]
        nopp = max(1, len(opps))
        sim = min(nopp, 2)
        per = 3 if len(hole) == 3 else 2
        # aggression on this street
        st = obs["street_index"]
        a_now = 0
        a_prev = 0
        aggseat = -1
        aggset = set()
        my_r = 0
        for h_st, seat, act, amt in obs["history"]:
            if seat == me:
                if act == "raise" and h_st == st and P["myr"]:
                    my_r += 1
                continue
            if act == "raise":
                if h_st == st:
                    a_now += 1 + my_r
                    my_r = 0
                    aggseat = seat
                    aggset.add(seat)
                elif h_st >= 1:
                    a_prev += 1
            elif act == "call" and h_st >= 1 and h_st < st:
                a_prev += 1
        if not weighted:
            a_now = a_prev = 0
        if a_now >= 1 and aggseat >= 0 and P["rmodel"]:
            return self.equity_range(obs, hole, board, deck, need, per, a_now, aggseat, nopp, t0, budget, len(aggset))
        if a_now >= 2:
            w_air, w_pair = P["w2a"], P["w2p"]
        elif a_now == 1:
            w_air, w_pair = P["w1a"], P["w1p"]
        elif a_prev >= 1:
            w_air, w_pair = P["wpa"], P["wpp"]
        else:
            w_air, w_pair = 1.0, 1.0
        if aggseat >= 0 and P["adapt"]:
            ag, pa = self.aggr[aggseat], self.passive[aggseat]
            af = (ag + 1.0) / (ag + pa + 3.0)
            sc = min(2.0, max(0.4, af / 0.33))
            w_air = min(1.0, w_air * sc)
            w_pair = min(1.0, w_pair * sc ** 0.5)
        bval = value(board) if board else 0
        bcat = bval >> 20
        sample = self.rng.sample
        clock = time.perf_counter
        draw = need + per * sim
        win = 0.0
        tot = 0.0
        n = 0
        weighting = w_air < 1.0 or w_pair < 1.0
        h3 = len(hole) == 3 and P["keep3b"]
        if h3:
            p1, p2, p3 = [hole[0], hole[1]], [hole[0], hole[2]], [hole[1], hole[2]]
        while n < 400:
            cs = sample(deck, draw)
            b = board + cs[:need]
            if h3:
                hv = max(value(p1 + b), value(p2 + b), value(p3 + b))
            else:
                hv = value(hole + b)
            res = 1.0
            wt = 1.0
            for k in range(need, draw, per):
                oh = cs[k:k + per]
                ov = value(oh + b)
                if weighting:
                    if need == 0:
                        cv = ov
                    else:
                        cv = value(oh + board)
                    cc = cv >> 20
                    if cc <= bcat:
                        wt *= w_air
                    elif cc == bcat + 1 and cc <= 1:
                        wt *= w_pair
                if ov > hv:
                    res = 0.0
                elif ov == hv and res > 0:
                    res *= 0.5
            win += res * wt
            tot += wt
            n += 1
            if (n & 7) == 0 and clock() - t0 > budget:
                break
        eq = win / tot if tot > 0 else 0.5
        if nopp > sim:
            eq = eq ** (nopp / sim)
        return eq, n

    def equity_range(self, obs, hole, board, deck, need, per, a_now, aggseat, nopp, t0, budget, nagg=1):
        """Equity vs the bettor's range: top X% of hands by current strength plus some bluffs."""
        st = obs["street_index"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        frac = to_call / max(1.0, pot - to_call)
        if a_now >= 2:
            x = P["xr"]
        else:
            x = (0.5, 0.5, 0.4, 0.33)[min(st, 3)] * P["xb"]
        x *= 1.0 if frac <= 0.5 else 0.85 if frac <= 1.0 else 0.65 if frac <= 2.0 else 0.5
        if P["barrel"] < 1.0:
            prev = {h[0] for h in obs["history"] if h[1] == aggseat and h[2] == "raise" and 1 <= h[0] < st}
            x *= P["barrel"] ** len(prev)
        ag, pa = self.aggr[aggseat], self.passive[aggseat]
        af = (ag + 1.0) / (ag + pa + 3.0)
        sc = min(2.0, max(0.5, af / 0.33)) if P["adapt"] else 1.0
        x = min(0.9, max(0.06, x * sc ** 0.5))
        bw = min(0.4, P["bw"] * sc * (0.5 if a_now >= 2 else 1.0))
        sample = self.rng.sample
        clock = time.perf_counter
        draw = need + per
        cvs = []
        rs = []
        n = 0
        h3 = len(hole) == 3 and P["keep3"]
        if h3:
            p1, p2, p3 = [hole[0], hole[1]], [hole[0], hole[2]], [hole[1], hole[2]]
        hv0 = value(hole + board) if need == 0 else -1
        prs = PAIRS.get(len(deck)) if (need == 0 and per == 2 and P["enum"]) else None
        if prs is not None:
            M = len(prs)
            g = 1
            for g in STRIDES:
                if M % g:
                    break
            pos = self.rng.randrange(M)
            while n < M:
                i, j = prs[pos]
                pos = (pos + g) % M
                ov = value([deck[i], deck[j]] + board)
                cvs.append(ov)
                rs.append(1.0 if hv0 > ov else 0.5 if hv0 == ov else 0.0)
                n += 1
                if (n & 7) == 0 and clock() - t0 > budget:
                    break
        while prs is None and n < 600:
            cs = sample(deck, draw)
            b = board + cs[:need]
            if hv0 >= 0:
                hv = hv0
            elif h3:
                hv = max(value(p1 + b), value(p2 + b), value(p3 + b))
            else:
                hv = value(hole + b)
            oh = cs[need:draw]
            ov = value(oh + b)
            cvs.append(ov if need == 0 else value(oh + board))
            rs.append(1.0 if hv > ov else 0.5 if hv == ov else 0.0)
            n += 1
            if (n & 7) == 0 and clock() - t0 > budget:
                break
        if need == 0 and P["anal"] and n > 0:
            fb = 0.0
            for r in rs:
                if r < 1.0:
                    fb += 1.0 - r
            F = fb / n
            if F >= x:
                tw = 0.0
                rw = (1.0 - F) / (1.0 - x) if x < 1.0 else 0.0
            else:
                tw = (x - F) / x
                rw = 1.0
            eq = (tw * x + bw * rw * (1.0 - x)) / (x + bw * (1.0 - x))
            if nopp > 1:
                k = min(max(1, nagg), nopp)
                eq = eq ** k * P["mw"] ** (nopp - k)
            return eq, n
        order = sorted(range(n), key=cvs.__getitem__, reverse=True)
        if P["soft"]:
            lo, hi = 0.7 * x * n, 1.3 * x * n
            num = den = 0.0
            for r, i in enumerate(order):
                if r < lo:
                    w = 1.0
                elif r >= hi:
                    w = bw
                else:
                    w = 1.0 - (1.0 - bw) * (r - lo) / (hi - lo)
                num += w * rs[i]
                den += w
            eq = num / den if den > 0 else 0.5
        else:
            ntop = max(1, int(x * n))
            top = sum(rs[i] for i in order[:ntop])
            rest = sum(rs[i] for i in order[ntop:])
            eq = (top + bw * rest) / (ntop + bw * (n - ntop))
        if nopp > 1:
            k = min(max(1, nagg), nopp)
            eq = eq ** k * P["mw"] ** (nopp - k)
        return eq, n

    def discard(self, obs, t0):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        k = obs.get("n_discard") or 1
        if len(hole) - k != 2 or len(board) != 3:
            return {"action": "discard", "cards": list(obs["hole"][:k])}
        opts = [(0, 1), (0, 2), (1, 2)]
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        sc = [0.0, 0.0, 0.0]
        sample = self.rng.sample
        clock = time.perf_counter
        n = 0
        while n < 200:
            cs = sample(deck, 4)
            b = board + cs[:2]
            ov = value(cs[2:4] + b)
            for oi, (x, y) in enumerate(opts):
                hv = value([hole[x], hole[y]] + b)
                if hv > ov:
                    sc[oi] += 1.0
                elif hv == ov:
                    sc[oi] += 0.5
            n += 1
            if (n & 3) == 0 and clock() - t0 > 0.00045:
                break
        # tiebreak with current made value
        best = max(range(3), key=lambda oi: (sc[oi], value([hole[opts[oi][0]], hole[opts[oi][1]]] + board)))
        keep = opts[best]
        drop = [obs["hole"][i] for i in range(3) if i not in keep]
        return {"action": "discard", "cards": drop[:k]}

    def postflop(self, obs, t0):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        eq, n = self.equity(obs, hole, board, t0, 0.00055)
        stacks, bets = obs["stacks"], obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        mystack = stacks[me]
        opps = [s for s in obs["in_hand"] if s != me]
        nopp = len(opps)
        st = obs["street_index"]
        river = st >= 3
        bb = obs["bb"] or 1
        rng = self.rng.random()
        # position: last to act postflop?
        alive = obs["alive"]
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in obs["in_hand"] and (stacks[s] > 0 or s == me)]
        ip = bool(live) and live[-1] == me
        spr = mystack / max(1, pot)
        # flop equity with 3 hole cards uses hindsight best-of-3: shade it
        if len(hole) == 3:
            eq -= P["shade"]
        if to_call <= 0:
            # we can check or bet
            vth = P["vth1"] if nopp == 1 else P["vthm"]
            if eq >= vth:
                frac = P["bf1"] if eq < 0.82 else P["bf2"]
                if spr < 1.2:
                    return self._allin(obs)
                return self._raise(obs, frac * pot)
            if not river and eq >= 0.42 and nopp == 1 and rng < P["semi"]:
                return self._raise(obs, 0.55 * pot)
            if nopp == 1 and ip and rng < P["bluff"] and eq < 0.35:
                return self._raise(obs, 0.5 * pot)
            if nopp == 1 and eq >= P["thin"] and ip and rng < 0.5:
                return self._raise(obs, 0.45 * pot)
            return {"action": "check"}
        call_amt = min(to_call, mystack)
        need = call_amt / max(1, pot - (to_call - call_amt) + call_amt)
        # strong: raise
        if eq >= P["rth"] and nopp <= 2:
            if spr < 2.0 or call_amt >= 0.4 * mystack:
                return self._allin(obs)
            cur = max(bets)
            return self._raise(obs, cur * 2.5 + pot * 0.5)
        margin = P["rmarg"] if river else P["marg"]
        if call_amt >= 0.5 * mystack:
            margin += 0.03
        if eq >= need + margin:
            return self._call(obs)
        return self._fold(obs)
