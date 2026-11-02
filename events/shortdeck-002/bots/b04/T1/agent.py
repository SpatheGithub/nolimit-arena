"""b04 shortdeck bot: preflop class tables + push/fold EV, range-aware Monte
Carlo postflop, per-seat opponent stats."""

import gc
import json
import os
import random
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
CATS = ("high_card", "pair", "two_pair", "trips", "straight",
        "flush", "full_house", "quads", "straight_flush")


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
    return out


TOP1, TOP2, TOP3, TOP5 = _top_ranks(1), _top_ranks(2), _top_ranks(3), _top_ranks(5)


def _straight_tops(ranks, ace_low):
    dr = sorted(RANKS.index(r) for r in ranks)
    tops = {}
    for i in range(len(dr) - 4):
        tops[sum(1 << r for r in dr[i:i + 5])] = dr[i + 4]
    if ace_low and 12 in dr and len(dr) >= 5 and 12 not in dr[:4]:
        tops.setdefault((1 << 12) | sum(1 << r for r in dr[:4]), dr[3])
    ordered = sorted(tops.items(), key=lambda t: -t[1])
    out = [-1] * 8192
    for m in range(8192):
        for sm, t in ordered:
            if m & sm == sm:
                out[m] = t
                break
    return out


class Ranker:
    def __init__(self, ranks, ranking=None):
        ranking = ranking or {}
        order = list(ranking.get("order") or ["high_card", "pair", "two_pair", "trips", "straight",
                                              "full_house", "flush", "quads", "straight_flush"])
        ace_low = bool(ranking.get("ace_low", True))
        self.shift = [order.index(c) << 20 for c in CATS]
        self.stop = _straight_tops(ranks, ace_low)

    def value(self, cards):
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
        s = self.shift
        stop = self.stop
        best = s[0] | TOP5[m1]
        if m2:
            if m4:
                q = m4.bit_length() - 1
                v = s[7] | q << 16 | TOP1[m1 & ~(1 << q)] << 12
                if v > best:
                    best = v
            if m3:
                t = m3.bit_length() - 1
                rest = m2 & ~(1 << t)
                if rest:
                    v = s[6] | t << 16 | (rest.bit_length() - 1) << 12
                    if v > best:
                        best = v
                v = s[3] | t << 16 | TOP2[m1 & ~(1 << t)] << 8
                if v > best:
                    best = v
            p = m2.bit_length() - 1
            rest = m2 & ~(1 << p)
            if rest:
                p2 = rest.bit_length() - 1
                v = s[2] | p << 16 | p2 << 12 | TOP1[m1 & ~(1 << p | 1 << p2)] << 8
                if v > best:
                    best = v
            v = s[1] | p << 16 | TOP3[m1 & ~(1 << p)] << 4
            if v > best:
                best = v
        t = stop[m1]
        if t >= 0:
            v = s[4] | t << 16
            if v > best:
                best = v
        for f in sm:
            if f.bit_count() >= 5:
                t = stop[f]
                v = s[8] | t << 16 if t >= 0 else s[5] | TOP5[f]
                if v > best:
                    best = v
        return best


# ---------------------------------------------------------------- preflop data
SRANKS = "6789TJQKA"
NR = 9
DECK = [CARD[r + s] for r in SRANKS for s in SUITS]
with open(os.path.join(_DIR, "pre.json")) as _f:
    _PRE = json.load(_f)
EQM = _PRE["E"]
CNT = _PRE["cnt"]
EQMULTI = [[x / 1e4 for x in row] for row in _PRE["eq_multi"]]
_TOT = float(sum(CNT))
EQR = [sum(CNT[j] * EQM[i][j] for j in range(81)) / _TOT for i in range(81)]
ORDER = sorted(range(81), key=lambda k: -EQR[k])
PCT = [0.0] * 81
_cum = 0
for _k in ORDER:
    PCT[_k] = (_cum + CNT[_k] / 2.0) / _TOT
    _cum += CNT[_k]

# CLS[c1][c2] -> class index for cards in DECK
CLS = [[-1] * 52 for _ in range(52)]
for _a in DECK:
    for _b in DECK:
        if _a == _b:
            continue
        pa, pb = (_a >> 2) - 4, (_b >> 2) - 4
        if pa == pb:
            CLS[_a][_b] = pa * NR + pa
        else:
            hi, lo = (pa, pb) if pa > pb else (pb, pa)
            CLS[_a][_b] = hi * NR + lo if (_a & 3) == (_b & 3) else lo * NR + hi

# RQ[i][b]: equity of class i vs top range width (b+1)/20
NB = 20
RQ = [[0.5] * NB for _ in range(81)]
for _b in range(NB):
    width = (_b + 1) / NB * _TOT
    wts = [0.0] * 81
    cum = 0.0
    for _k in ORDER:
        take = min(CNT[_k], max(0.0, width - cum))
        wts[_k] = take
        cum += CNT[_k]
    sw = sum(wts)
    for _i in range(81):
        RQ[_i][_b] = sum(wts[j] * EQM[_i][j] for j in range(81)) / sw


# CALLW[b][k]: fraction of combos whose equity vs top (b+1)/20 range is >= need 0.20+0.01k
NK = 50
CALLW = [[0.0] * NK for _ in range(NB)]
for _b in range(NB):
    for _k in range(NK):
        need = 0.20 + 0.01 * _k
        CALLW[_b][_k] = sum(CNT[j] for j in range(81) if RQ[j][_b] >= need) / _TOT


def call_width(w, need):
    b = min(NB - 1, max(0, int(round(w * NB - 1))))
    k = int((need - 0.20) * 100)
    if k < 0:
        return CALLW[b][0]
    if k >= NK:
        return CALLW[b][NK - 1] * 0.5
    return CALLW[b][k]


def eq_vs_range(cls, r):
    """Equity of class vs top-r fraction of hands (heads-up)."""
    x = r * NB - 1.0
    if x <= 0:
        return RQ[cls][0]
    if x >= NB - 1:
        return RQ[cls][NB - 1]
    i = int(x)
    f = x - i
    row = RQ[cls]
    return row[i] * (1 - f) + row[i + 1] * f


ICM_SCALE = 1.3


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        var = config.get("variant") or {}
        ranks = var.get("ranks", SRANKS)
        self.ranker = Ranker(ranks, var.get("ranking"))
        self.points = list(config.get("points") or [100, 45, 20, 8, 0, 0, 0, 0])
        self.nseats = config.get("seats", 8)
        # per-seat stats: [pf_opps, vpip, pfr, allin_pf, post_aggr, post_passive]
        self.st = {}
        self.cache_key = None
        self.cache_eq = 0.5
        self.cache_n = 0
        self.hand_id = -1
        self.was_pfr = False

    # ------------------------------------------------------------ stats
    def stat(self, s):
        x = self.st.get(s)
        if x is None:
            x = self.st[s] = [0, 0, 0, 0, 0, 0, 0, 0]
        return x

    def ftb_of(self, s):
        x = self.stat(s)
        return (x[6] + 0.4 * 5) / (x[6] + x[7] + 5)

    def pfr_of(self, s):
        x = self.stat(s)
        return (x[2] + 0.22 * 6) / (x[0] + 6)

    def vpip_of(self, s):
        x = self.stat(s)
        return (x[1] + 0.35 * 6) / (x[0] + 6)

    def shove_rate(self, s):
        x = self.stat(s)
        return (x[3] + 0.05 * 6) / (x[0] + 6)

    def aggr_of(self, s):
        x = self.stat(s)
        return (x[4] + 1.0 * 3) / (x[4] + x[5] + 3 * 2)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            for x in self.st.values():
                for k in range(len(x)):
                    x[k] *= 0.985
            seen = set()
            vp = set()
            pr = set()
            ai = set()
            # track stack for allin detection: amounts relative to stacks unknown; use raise amount vs start stacks
            cur_st = -1
            bet_open = False
            for h in hist:
                st, seat, act, amt = h[0], h[1], h[2], h[3]
                if st != cur_st:
                    cur_st = st
                    bet_open = False
                if st > 0 and seat != self.seat:
                    if bet_open and act == "fold":
                        self.stat(seat)[6] += 1
                    elif bet_open and act in ("call", "raise"):
                        self.stat(seat)[7] += 1
                if st > 0 and act == "raise":
                    bet_open = True
                if st == 0:
                    if act in ("fold", "check", "call", "raise"):
                        seen.add(seat)
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        self.stat(seat)[4] += 1
                    elif act in ("call", "check"):
                        self.stat(seat)[5] += 1
            stacks = event.get("stacks") or []
            payoffs = event.get("payoffs") or {}
            for s in seen:
                x = self.stat(s)
                x[0] += 1
                if s in vp:
                    x[1] += 1
                if s in pr:
                    x[2] += 1
            # preflop all-in raises: raise amount equal to the seat's whole stack at start
            for h in hist:
                if h[0] == 0 and h[2] == "raise":
                    s = h[1]
                    try:
                        start = stacks[s] - payoffs.get(s, payoffs.get(str(s), 0))
                    except Exception:
                        start = None
                    if start is not None and h[3] >= start * 0.95 and h[3] > 0:
                        self.stat(s)[3] += 1
        except Exception:
            pass

    # ------------------------------------------------------------ helpers
    def act(self, obs):
        t0 = time.perf_counter()
        was = gc.isenabled()
        if was:
            gc.disable()
        try:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 0])}
            a = self.decide(obs, t0)
            return self.legalize(obs, a)
        except Exception:
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}
        finally:
            if was:
                gc.enable()

    def legalize(self, obs, a):
        legal = obs["legal"]
        act = a.get("action")
        if act == "fold":
            return {"action": "check"} if "check" in legal else {"action": "fold"}
        if act in ("check", "call"):
            if obs["to_call"] == 0:
                return {"action": "check"} if "check" in legal else {"action": "call"}
            return {"action": "call"} if "call" in legal else {"action": "fold"}
        if act == "allin":
            if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
                return {"action": "raise", "amount": obs["max_raise_to"]}
            if obs["to_call"] > 0:
                return {"action": "call"} if "call" in legal else {"action": "fold"}
            return {"action": "check"}
        if act in ("raise", "bet"):
            if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
                amt = int(a.get("amount", 0))
                lo, hi = obs["min_raise_to"], obs["max_raise_to"]
                amt = lo if amt < lo else hi if amt > hi else amt
                # avoid leaving a tiny stub behind
                me = obs["seat"]
                total = obs["stacks"][me] + obs["bets"][me]
                if total - amt < 0.2 * (obs["pot"] + amt):
                    amt = hi
                return {"action": "raise", "amount": amt}
            if obs["to_call"] > 0:
                return {"action": "call"} if "call" in legal else {"action": "fold"}
            return {"action": "check"}
        return {"action": "check"} if "check" in legal else {"action": "fold"}

    def decide(self, obs, t0):
        if obs["hand_id"] != self.hand_id:
            self.hand_id = obs["hand_id"]
            self.was_pfr = False
            self.cache_key = None
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs, t0)

    # ------------------------------------------------------------ preflop
    def preflop(self, obs):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        cls = CLS[hole[0]][hole[1]]
        pct = PCT[cls]
        bb = obs["bb"] or 1
        stacks, bets = obs["stacks"], obs["bets"]
        my_total = stacks[me] + bets[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        hist = obs["history"]
        opps = [s for s in in_hand if s != me]
        n_alive = len(alive)

        raisers = []
        limpers = 0
        for h in hist:
            if h[0] != 0:
                continue
            if h[2] == "raise":
                raisers.append(h[1])
            elif h[2] == "call" and not raisers:
                limpers += 1
        nr = len(raisers)

        # order and players behind
        btn = obs["button"]
        if n_alive == 2:
            bi = alive.index(btn) if btn in alive else 0
            order = [alive[bi], alive[1 - bi]]
        else:
            bbs = obs["bb_seat"]
            j = (alive.index(bbs) + 1) % n_alive if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        # BB acts last preflop; if I'm not BB, include blinds after me
        opp_max = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_total, opp_max)
        eff_bb = eff / bb

        if self.rng.random() < 0.0:
            pass

        if nr == 0:
            # unopened (maybe limpers)
            if to_call == 0 and not behind:
                # BB option vs limpers
                if eff_bb <= 12:
                    if self.shove_ev(cls, pot, eff, opps, bb, obs) > 0.5 * bb and pct < 0.35:
                        return {"action": "allin"}
                    return {"action": "check"}
                if pct <= 0.12:
                    amt = bets[me] + int((3 + limpers) * bb)
                    self.was_pfr = True
                    return {"action": "raise", "amount": amt}
                return {"action": "check"}
            if eff_bb <= 15:
                limp_seats = [s for s in opps if bets[s] > 0 and s not in behind and stacks[s] > 0]
                ev = self.shove_ev(cls, pot, eff, behind + limp_seats, bb, obs)
                if ev > 0.15 * bb + self.icm_margin(obs, eff / max(1, my_total)) * eff:
                    self.was_pfr = True
                    return {"action": "allin"}
                if to_call == 0:
                    return {"action": "check"}
                return {"action": "fold"}
            nb = len(behind)
            th = {0: 0.15, 1: 0.45, 2: 0.33, 3: 0.24, 4: 0.19, 5: 0.16, 6: 0.14}.get(nb, 0.12)
            if limpers:
                th *= 0.8
            if eff_bb <= 25:
                th *= 0.9
            if behind and not limpers:
                # steal wider when the players left to act are tight, tighter when loose
                avp = sum(self.vpip_of(s) for s in behind) / len(behind)
                th *= min(1.7, max(0.8, 1.0 + (0.35 - avp) * 3.0))
            if pct <= th:
                amt = int((2.5 + limpers) * bb)
                if n_alive <= 3:
                    amt = int((2.2 + limpers) * bb)
                if amt >= 0.33 * my_total:
                    return {"action": "allin"}
                self.was_pfr = True
                return {"action": "raise", "amount": amt}
            if to_call == 0:
                return {"action": "check"}
            # SB completing cheaply vs BB
            if len(behind) == 1 and to_call <= 0.5 * bb and pct <= 0.6 and eff_bb > 15:
                return {"action": "call"}
            return {"action": "fold"}

        # facing raise(s)
        last = raisers[-1]
        last_amt = 0
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                last_amt = h[3]
        r = self.pfr_of(last)
        # position of the first raiser: fewer players behind -> wider range
        first = raisers[0]
        if first in order:
            nbr = len(order) - 1 - order.index(first)
            r *= {0: 1.6, 1: 1.7, 2: 1.45, 3: 1.2, 4: 1.0}.get(nbr, 0.85)
        if n_alive <= 3:
            r *= 1.2
        sr = self.shove_rate(last)
        raiser_total = stacks[last] + bets[last]
        raiser_allin = stacks[last] == 0
        if raiser_allin or last_amt >= 0.6 * (raiser_total):
            if nr == 1 and first in order:
                # push/fold prior by position and depth, scaled by the seat's looseness
                sbb = max(1.0, raiser_total / bb)
                base = {0: 0.6, 1: 0.6, 2: 0.42, 3: 0.32, 4: 0.26}.get(nbr, 0.18)
                base *= min(1.5, max(0.6, (10.0 / sbb) ** 0.4))
                loose = min(2.0, max(0.5, self.pfr_of(last) / 0.22))
                r = max(base * loose, sr, 0.06)
            else:
                r = max(r * 0.8, sr, 0.06)
        if nr >= 2:
            r = r * 0.45
        # big raise sizes are tighter
        if last_amt > 4 * bb and not raiser_allin:
            r *= 0.85
        r = min(max(r, 0.03), 1.0)
        eq = eq_vs_range(cls, r)
        # extra opponents already in (callers / other raisers)
        others = [s for s in opps if s != last and bets[s] > 0 and s not in behind]
        if others:
            eq = eq ** (1.0 + 0.8 * len(others))
        eq -= 0.025 * len(behind) * (1 if nr == 1 else 0.5)
        risk_total = min(my_total, raiser_total)
        call_amt = min(to_call, stacks[me])
        commit = (call_amt >= 0.35 * my_total) or eff_bb <= 18 or raiser_allin
        icm = self.icm_margin(obs, risk_total / max(1, my_total))
        if commit:
            # all-in or fold
            need = (min(risk_total, my_total) - bets[me]) / (pot + (min(risk_total, my_total) - bets[me]) + max(0, min(risk_total, my_total) - bets[last]) + 1e-9)
            need = max(0.0, need)
            if eq >= need + icm:
                return {"action": "allin"}
            if nr == 1 and not raiser_allin and stacks[me] > to_call and not others:
                # resteal shove with fold equity
                committed = last_amt >= 0.4 * raiser_total
                fc = 1.0 if committed else 0.45
                rc = max(0.03, r * fc)
                eqc = eq_vs_range(cls, rc) - 0.02 * len(behind)
                R = min(my_total, raiser_total)
                invest = R - bets[me]
                final = pot + invest + max(0, R - bets[last])
                pf = 1.0 - fc
                for s in behind:
                    pf *= 0.9
                ev = pf * pot + (1 - pf) * (eqc * final - invest)
                if ev > 0.3 * bb + icm * final:
                    self.was_pfr = True
                    return {"action": "allin"}
            return {"action": "fold"}
        # deep: 3bet / call / fold
        po = to_call / (pot + to_call)
        if eq >= 0.60 or (nr == 1 and pct <= 0.04):
            amt = int(last_amt * 3 + (pot - last_amt - bets[me]) )
            if amt >= 0.4 * my_total:
                return {"action": "allin"}
            self.was_pfr = True
            return {"action": "raise", "amount": amt}
        if nr == 1 and not raiser_allin and eff_bb <= 28 and not others and stacks[me] > to_call:
            # resteal shove over a single open at medium depth
            fc = 0.5
            rc = max(0.03, r * fc)
            eqc = eq_vs_range(cls, rc) - 0.02 * len(behind)
            R = min(my_total, raiser_total)
            invest = R - bets[me]
            final = pot + invest + max(0, R - bets[last])
            pf = (1.0 - fc) * (0.9 ** len(behind))
            ev = pf * pot + (1 - pf) * (eqc * final - invest)
            if ev > 0.5 * bb + icm * final:
                self.was_pfr = True
                return {"action": "allin"}
        if eq >= po + 0.06 and pct <= 0.55:
            return {"action": "call"}
        return {"action": "fold"}

    def icm_margin(self, obs, frac=1.0):
        # break-even equity above 0.5 for an even stack-for-stack all-in under the
        # 100/45/20/8 ICM (kit/icm.py), scaled by the share of my stack at risk
        n = len(obs["alive"])
        base = {2: 0.0, 3: 0.065, 4: 0.08, 5: 0.085, 6: 0.07, 7: 0.06}.get(n, 0.05)
        return base * min(1.0, max(0.25, frac)) * ICM_SCALE

    def shove_ev(self, cls, pot, eff, callers, bb, obs):
        """chip EV of shoving relative to folding."""
        stacks, bets = obs["stacks"], obs["bets"]
        me = obs["seat"]
        my_total = stacks[me] + bets[me]
        pfold = 1.0
        ev_call = 0.0
        for s in callers:
            their = stacks[s] + bets[s]
            risk = min(my_total, their)
            # their calling range: wider when cheap relative to pot
            # rational caller: calls when equity vs perceived shove range beats pot odds
            nal = len(obs["alive"])
            w = 0.5 if nal == 2 else 0.35 if nal <= 4 else 0.25
            inv_c = max(0, risk - bets[s])
            need = inv_c / (pot + (risk - bets[me]) + inv_c + 1e-9)
            c = call_width(w, need + 0.02)
            vp = self.vpip_of(s)
            c = c * (0.75 + 0.7 * vp)
            c = min(max(c, 0.04), 0.95)
            eq = eq_vs_range(cls, c)
            win_pot = pot + 2 * risk - bets[me] - bets[s]
            invest = risk - bets[me]
            ev_c = eq * (pot + invest + (risk - bets[s])) - invest
            ev_call += pfold * c * ev_c
            pfold *= (1 - c)
        return pfold * pot + ev_call

    # ------------------------------------------------------------ postflop
    def opp_range(self, s, hist):
        raised = False
        called = False
        for h in hist:
            if h[0] == 0 and h[1] == s:
                if h[2] == "raise":
                    raised = True
                elif h[2] == "call":
                    called = True
        if raised:
            return min(1.0, max(0.08, self.pfr_of(s)))
        if called:
            return min(1.0, max(0.2, self.vpip_of(s)))
        return 1.0

    def equity(self, hole, board, ranges, t0, budget):
        known = set(hole) | set(board)
        deck = [c for c in DECK if c not in known]
        L = len(deck)
        need = 5 - len(board)
        val = self.ranker.value
        rnd = self.rng.random
        clsm = CLS
        pctv = PCT
        wins = 0.0
        n = 0
        clock = time.perf_counter
        base = hole + board
        while True:
            used = set()
            opp_hands = []
            for r in ranges:
                for t in range(8):
                    a = deck[int(rnd() * L)]
                    b = deck[int(rnd() * L)]
                    if a == b or a in used or b in used:
                        continue
                    if r >= 1.0 or pctv[clsm[a][b]] <= r or t >= 6:
                        break
                else:
                    # fallback
                    while True:
                        a = deck[int(rnd() * L)]
                        b = deck[int(rnd() * L)]
                        if a != b and a not in used and b not in used:
                            break
                used.add(a)
                used.add(b)
                opp_hands.append((a, b))
            bd = list(board)
            while len(bd) < 5:
                c = deck[int(rnd() * L)]
                if c in used:
                    continue
                used.add(c)
                bd.append(c)
            hv = val(hole + bd)
            res = 1.0
            ties = 0
            for a, b in opp_hands:
                v = val([a, b] + bd)
                if v > hv:
                    res = 0.0
                    break
                if v == hv:
                    ties += 1
            if res > 0 and ties:
                res = 1.0 / (1 + ties)
            wins += res
            n += 1
            if n >= 400 or (n >= 12 and clock() - t0 > budget):
                break
        return wins / n, n

    def postflop(self, obs, t0):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        st = obs["street_index"]
        stacks, bets = obs["stacks"], obs["bets"]
        my_total = stacks[me] + bets[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        bb = obs["bb"] or 1
        hist = obs["history"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        nopp = len(opps)
        key = (obs["hand_id"], st)
        if self.cache_key == key and self.cache_n >= 30:
            eq = self.cache_eq
        else:
            ranges = [self.opp_range(s, hist) for s in opps]
            eq, n = self.equity(hole, board, ranges, t0, 0.00045)
            if self.cache_key == key:
                eq = (eq * n + self.cache_eq * self.cache_n) / (n + self.cache_n)
                n += self.cache_n
            self.cache_key, self.cache_eq, self.cache_n = key, eq, n

        # actions on this street
        street_raises = [h for h in hist if h[0] == st and h[2] == "raise"]
        nr = len(street_raises)
        last_aggr_prev = None
        for h in hist:
            if h[0] == st - 1 and h[2] == "raise":
                last_aggr_prev = h[1]
        i_was_aggr = last_aggr_prev == me
        eff = min(my_total, max([stacks[s] + bets[s] for s in opps], default=0))
        spr = (eff - bets[me]) / max(pot, 1)
        # position: am I last to act?
        alive = obs["alive"]
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in in_hand and (stacks[s] > 0 or s == me)]
        ip = bool(live) and live[-1] == me
        rnd = self.rng.random()

        if to_call == 0:
            # betting decision
            vt = 0.5 + 0.08 * (nopp - 1)
            f = 1.0
            for s in opps:
                f *= self.ftb_of(s)
            if f < 0.3:
                vt -= 0.04
            if eq >= vt + 0.25:
                frac = 0.8
                if spr < 1.5:
                    return {"action": "allin"}
                return {"action": "raise", "amount": int(frac * pot)}
            if eq >= vt + 0.08:
                return {"action": "raise", "amount": int(0.6 * pot)}
            # c-bet / bluff, scaled by how often these opponents fold to bets
            fs = min(2.0, max(0.25, f / 0.4))
            if nopp == 1 and st < 3 and (i_was_aggr or (ip and st >= 1)) and rnd < min(0.9, (0.55 if i_was_aggr else 0.3) * fs) and eq >= 0.2:
                return {"action": "raise", "amount": int(0.5 * pot)}
            if nopp == 2 and st == 1 and i_was_aggr and f > 0.3 and rnd < 0.5 and eq >= 0.25:
                return {"action": "raise", "amount": int(0.5 * pot)}
            if nopp == 1 and st == 3 and eq < 0.2 and rnd < (0.25 if f >= 0.5 else 0.12 if f >= 0.33 else 0.0) * (1.0 if ip else 0.6):
                return {"action": "raise", "amount": int(0.65 * pot)}
            return {"action": "check"}

        # facing a bet
        bettor = street_raises[-1][1] if street_raises else None
        ag = self.aggr_of(bettor) if bettor is not None else 0.5
        call_amt = min(to_call, stacks[me])
        po = call_amt / (pot + call_amt)
        bet_frac = to_call / max(1, pot - to_call)
        # bettor's range is stronger than preflop range; penalty shrinks for aggressive seats
        pen = (0.04 + 0.10 * min(bet_frac, 1.5)) * (1.3 - 0.8 * ag)
        if nr >= 2:
            pen += 0.08
        if st == 3:
            pen += 0.03
        adj = eq - pen
        allin_call = call_amt >= stacks[me] * 0.95
        icm = self.icm_margin(obs, call_amt / max(1, my_total)) if (allin_call or call_amt > 0.4 * my_total) else 0.0
        if adj >= 0.72 and nr < 3:
            if spr < 2 or adj >= 0.85:
                return {"action": "allin"}
            amt = int(bets[street_raises[-1][1]] * 2.8 + (pot - to_call - bets[me]) * 0.5) if street_raises else int(pot)
            return {"action": "raise", "amount": amt}
        if adj >= po + icm:
            # if calling leaves little behind, just go in
            if stacks[me] - call_amt < 0.25 * pot and adj >= 0.5:
                return {"action": "allin"}
            return {"action": "call"}
        return {"action": "fold"}
