"""b03 PLO bot: vectorised Monte-Carlo equity + range-narrowing, preflop
equity table, stack-aware sizing, opponent stats."""
import json
import os
import random
import time

import numpy as np

from . import ev
from .ranker import CARD
from .icm import icm_equity

_HERE = os.path.dirname(os.path.abspath(__file__))
_PF = {}
_PCT_E1 = None
_PCT_E12 = None
try:
    with open(os.path.join(_HERE, "pf.json")) as _f:
        _d = json.load(_f)
    _PF = {k: tuple(v) for k, v in _d["t"].items()}
    _PCT_E1 = np.array(_d["q"], dtype=np.float64)   # e1 value at percentile grid 0..100 (descending)
    _PCT_E12 = np.array(_d["q2"], dtype=np.float64)  # e1+e2 grid
except Exception:
    _PF = {}


def _key(h):
    g = [[], [], [], []]
    for c in h:
        g[c & 3].append(c >> 2)
    return str(tuple(sorted(tuple(sorted(x)) for x in g if x)))


SAMPLES = {1: 130, 2: 90, 3: 66}
OPEN_MULT = 1.0
CALL_MULT = 1.0
BLUFF = 1.0
VALUE_THR = 0.60
X_SMALL, X_MID, X_BIG = 0.45, 0.36, 0.28
DEF_BONUS = 1.0
LOW_SPR_JAM = True
STEAL = False
RESAMPLE = False
HU_FIX = True
HU_DEF = True
HU_CBET = False
BLEND = True


class Agent:
    def __init__(self, config):
        self.seat = config.get("seat", 0)
        self.rng = random.Random(config.get("seed", 0))
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        self.st = {}
        self.pf_cache = {}

    # ---------------- stats -----------------
    def stat(self, s):
        d = self.st.get(s)
        if d is None:
            # hands, vpip, pfr, post_aggr, post_call, post_fold, post_check
            d = self.st[s] = [0, 0, 0, 0, 0, 0, 0]
        return d

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in event.get("history", ()):
                if act in ("ante", "sb", "bb", "return"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                d = self.stat(seat)
                if st == 0:
                    if act == "raise":
                        pr.add(seat)
                        vp.add(seat)
                    elif act == "call":
                        vp.add(seat)
                else:
                    if act == "raise":
                        d[3] += 1
                    elif act == "call":
                        d[4] += 1
                    elif act == "fold":
                        d[5] += 1
                    elif act == "check":
                        d[6] += 1
            for s in seen:
                d = self.stat(s)
                d[0] += 1
                if s in vp:
                    d[1] += 1
                if s in pr:
                    d[2] += 1
        except Exception:
            pass

    def looseness(self, s):
        """(vpip, pfr, aggression, fold-rate) with priors."""
        d = self.stat(s)
        h = d[0]
        vpip = (d[1] + 0.3 * 8) / (h + 8)
        pfr = (d[2] + 0.12 * 8) / (h + 8)
        ag = (d[3] + 1.5) / (d[3] + d[4] + d[6] + 4)
        fr = (d[5] + 1.0) / (d[5] + d[4] + d[3] + 3)
        return vpip, pfr, ag, fr

    # ---------------- helpers -----------------
    def pf_eq(self, hole):
        k = _key(hole)
        v = _PF.get(k)
        if v is not None:
            return v
        v = self.pf_cache.get(k)
        if v is None:
            e1 = ev.equity(hole, [], 1, 300, self.rng.randrange(ev.NBANK - 300))[0]
            v = (e1, e1 * e1 * 1.05)
            self.pf_cache[k] = v
        return v

    def pct(self, e1):
        """fraction of hands better than this one (0 = best)."""
        q = _PCT_E1
        if q is None:
            return max(0.0, min(1.0, (0.72 - e1) / 0.34))
        # q descending: q[i] = e1 at top i%
        i = int(np.searchsorted(-q, -e1))
        return min(1.0, i / 100.0)

    def _act(self, obs):
        legal = obs["legal"]
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        street = obs["street_index"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        stack = stacks[me]
        mybet = bets[me]
        bb = obs["bb"] or 1
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        opps = [s for s in in_hand if s != me]
        can_check = "check" in legal
        can_raise = ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0
        min_to = obs["min_raise_to"]
        max_to = obs["max_raise_to"]
        hist = obs["history"]
        opp_tot = max([stacks[s] + bets[s] for s in opps] or [0])
        eff = min(stack + mybet, opp_tot)
        self.ctx = (legal, can_check, can_raise, min_to, max_to, to_call, pot, mybet, stack)

        # order / position
        n = len(alive)
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        if street == 0:
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
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in in_hand and (stacks[s] > 0 or s == me)]
        ip = bool(live) and live[-1] == me

        raises = 0
        last_raiser = -1
        callers = 0
        for h_st, seat, act, _ in hist:
            if h_st == street:
                if act == "raise":
                    raises += 1
                    last_raiser = seat
                    callers = 0
                elif act == "call":
                    callers += 1

        if street == 0:
            return self.preflop(obs, hole, pot, to_call, stack, mybet, bb, opps, behind, raises,
                                last_raiser, callers, eff, n)
        return self.postflop(obs, hole, board, street, pot, to_call, stack, mybet, bb, opps, behind,
                             raises, last_raiser, eff, ip, n)

    def act(self, obs):
        self.t0 = time.thread_time()
        try:
            return self._act(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    # ---------------- actions -----------------
    def a_fold(self):
        return {"action": "check"} if self.ctx[1] else {"action": "fold"}

    def a_call(self):
        legal = self.ctx[0]
        if self.ctx[5] == 0:
            return {"action": "check"}
        return {"action": "call"} if "call" in legal else self.a_fold()

    def a_raise(self, amount):
        legal, can_check, can_raise, min_to, max_to = self.ctx[:5]
        if not can_raise:
            return self.a_call()
        a = int(amount)
        a = min_to if a < min_to else max_to if a > max_to else a
        return {"action": "raise", "amount": a}

    def a_pot(self, frac):
        legal, can_check, can_raise, min_to, max_to, to_call, pot, mybet, stack = self.ctx
        target = mybet + to_call + frac * (pot + to_call)
        left = stack + mybet - target
        if left < 0.35 * (pot + 2 * (target - mybet)):
            target = max_to
        return self.a_raise(target)

    # ---------------- preflop -----------------
    def preflop(self, obs, hole, pot, to_call, stack, mybet, bb, opps, behind, raises, last_raiser,
                callers, eff, n):
        e1, e2 = self.pf_eq(hole)
        if BLEND and _PCT_E12 is not None:
            pc = min(1.0, int(np.searchsorted(-_PCT_E12, -(e1 + e2))) / 100.0)
        else:
            pc = self.pct(e1)
        eff_bb = eff / bb
        nb = len(behind)
        can_check = self.ctx[1]
        commit = (to_call >= 0.3 * stack) or (stack + mybet - to_call) < 3 * bb

        if raises == 0:
            # unopened / limped
            if eff_bb <= 12:
                thr = 0.45 if nb <= 2 else 0.35 if nb <= 4 else 0.28
                if HU_FIX:
                    if n == 2:
                        thr = 0.85 if nb >= 1 else 0.35
                    elif n == 3:
                        thr += 0.10
            else:
                thr = {0: 0.12, 1: 0.30, 2: 0.30, 3: 0.22, 4: 0.17, 5: 0.14}.get(nb, 0.12)
                thr -= 0.02 * callers
                if n == 2:
                    thr = (0.70 if HU_FIX else 0.60) if nb >= 1 else 0.25
                elif n == 3:
                    thr += 0.12
                elif n <= 5:
                    thr += 0.06
                if STEAL and behind and nb <= 3:
                    vps = [self.looseness(o)[0] for o in behind]
                    if max(vps) < 0.22:
                        thr += 0.12
                    elif sum(vps) / len(vps) < 0.25:
                        thr += 0.05
            if pc <= thr * OPEN_MULT:
                return self.a_raise(self.ctx[4])  # pot
            if can_check:
                return {"action": "check"}
            # SB completion
            if to_call <= 0.5 * bb + 1 and pc <= 0.5:
                return self.a_call()
            return self.a_fold()

        # facing a raise
        rv, rp, rag, rfr = self.looseness(last_raiser) if last_raiser >= 0 else (0.3, 0.12, 0.4, 0.4)
        k = len(opps)
        loose = rp > 0.25
        pot_odds = to_call / (pot + to_call)
        if commit or eff_bb <= 15:
            eq = e1 if k <= 1 else e2 if k == 2 else e2 * 0.8
            pen = 0.03 if loose else 0.07 if rp > 0.12 else 0.10
            if raises >= 2:
                pen += 0.03
            eq -= pen
            if eq >= self.req_eq(obs, to_call, pot):
                if eq >= 0.5 and self.ctx[2]:
                    return self.a_raise(self.ctx[4])
                return self.a_call()
            return self.a_fold()

        three = 0.035 if not loose else 0.07
        call = 0.12 if not loose else 0.20
        if obs["bb_seat"] == obs["seat"]:
            call += 0.05
        if raises >= 2:
            three = 0.012
            call = 0.04 if not loose else 0.07
        if to_call > 0.15 * stack:
            call *= 0.6
        call = call * CALL_MULT + DEF_BONUS * max(0.0, 0.33 - pot_odds)
        if HU_DEF:
            if n == 2:
                if raises >= 2:
                    three, call = max(three, 0.04), max(call, 0.25)
                else:
                    three, call = max(three, 0.08), max(call, 0.55)
            elif n == 3 and raises == 1:
                call += 0.08
        if pc <= three:
            return self.a_raise(self.ctx[4])
        if pc <= call:
            return self.a_call()
        return self.a_fold()

    def icm_prem(self, obs, risk):
        stack = self.ctx[8] + self.ctx[7]
        if stack <= 0:
            return 0.0
        frac = min(1.0, risk / stack)
        n = len(obs["alive"])
        base = 0.02 if n >= 6 else 0.035 if n >= 4 else 0.02
        return base * frac

    def req_eq(self, obs, to_call, pot):
        """Equity needed to call (ICM-adjusted when few players are left)."""
        stack = self.ctx[8]
        po = to_call / (pot + to_call)
        if stack <= 0:
            return po
        c = min(to_call, stack)
        alive = obs["alive"]
        n = len(alive)
        if n <= 4 and c >= 0.2 * stack:
            try:
                me = obs["seat"]
                stacks = obs["stacks"]
                bets = obs["bets"]
                opps = [s for s in obs["in_hand"] if s != me]
                vil = max(opps, key=lambda s: bets[s])
                pts = self.points[:n]
                mi = alive.index(me)
                vi = alive.index(vil)
                base = [stacks[s] for s in alive]
                f = list(base)
                f[vi] += pot
                w = list(base)
                w[mi] += pot
                w[vi] += max(0, to_call - c)
                l = list(base)
                l[mi] -= c
                l[vi] += pot + c
                uf = icm_equity(f, pts)[mi]
                uw = icm_equity(w, pts)[mi]
                ul = icm_equity(l, pts)[mi]
                if uw - ul > 1e-9:
                    return max(po, (uf - ul) / (uw - ul))
            except Exception:
                pass
            return po + 0.03
        return po + self.icm_prem(obs, to_call)

    # ---------------- postflop -----------------
    def postflop(self, obs, hole, board, street, pot, to_call, stack, mybet, bb, opps, behind, raises,
                 last_raiser, eff, ip, n):
        k = len(opps)
        kk = min(k, 3)
        S = SAMPLES[kk]
        eq, mine, opp, cur = ev.equity(hole, board, kk, S, self.rng.randrange(ev.NBANK - S))
        if k > 3:
            eq = eq ** (k / 3.0)
        arr = [mine, opp, cur]

        def eq_top(x):
            mine, opp, cur = arr
            n_s = len(mine)
            m = max(10, int(x * n_s))
            if m >= n_s:
                e = float(((mine > opp) + 0.5 * (mine == opp)).mean())
                return e ** (k / 3.0) if k > 3 else e
            if cur is not None:
                score = 0.6 * np.argsort(np.argsort(cur, kind="stable")) + 0.4 * np.argsort(np.argsort(opp))
            else:
                score = opp
            idx = np.argpartition(score, n_s - m)[n_s - m:]
            mm = mine[idx]
            oo = opp[idx]
            e = float(((mm > oo) + 0.5 * (mm == oo)).mean())
            if k > 3:
                e = e ** (k / 3.0)
            return e

        def resample():
            if not RESAMPLE or time.thread_time() - self.t0 > 0.00035:
                return False
            _, m2, o2, c2 = ev.equity(hole, board, kk, S, self.rng.randrange(ev.NBANK - S))
            arr[0] = np.concatenate((arr[0], m2))
            arr[1] = np.concatenate((arr[1], o2))
            if arr[2] is not None:
                arr[2] = np.concatenate((arr[2], c2))
            return True

        spr = eff / max(1, pot)
        if to_call == 0:
            if LOW_SPR_JAM and spr <= 1.0 and eq >= 0.45 and self.ctx[2]:
                return self.a_raise(self.ctx[4])
            ev_v = eq_top(0.55)
            thr = VALUE_THR if street < 3 else VALUE_THR + 0.02
            if ev_v >= thr:
                frac = 1.0 if ev_v >= 0.75 else 0.75
                return self.a_pot(frac)
            # semi-bluff / stab
            if HU_CBET and n == 2 and k == 1 and street == 1 and eq >= 0.35:
                pfr = -1
                for h_st, seat, act, _ in obs["history"]:
                    if h_st == 0 and act == "raise":
                        pfr = seat
                if pfr == obs["seat"] and self.rng.random() < 0.6:
                    return self.a_pot(0.6)
            if k == 1:
                o = opps[0]
                _, _, _, fr = self.looseness(o)
                if street < 3 and eq >= 0.45 and self.rng.random() < 0.45 * BLUFF:
                    return self.a_pot(0.66)
                if fr > 0.5 and self.rng.random() < 0.35 * BLUFF and (ip or street < 3):
                    return self.a_pot(0.6)
            return {"action": "check"}

        # facing a bet
        pot_before = max(1, pot - to_call)
        f = to_call / pot_before
        x = X_SMALL if f <= 0.4 else X_MID if f <= 0.75 else X_BIG
        if raises >= 2:
            x *= 0.6
        if last_raiser >= 0:
            _, _, ag, _ = self.looseness(last_raiser)
            if ag > 0.55:
                x = min(1.0, x * 1.5)
            elif ag < 0.3:
                x *= 0.8
            if STEAL and self.looseness(last_raiser)[0] < 0.2:
                x *= 0.75
        er = eq_top(x)
        need = self.req_eq(obs, to_call, pot)
        if to_call >= 0.2 * stack and (abs(er - need - 0.02) < 0.05 or abs(er - 0.68) < 0.04):
            if resample():
                er = eq_top(x)
        if er >= 0.68 and self.ctx[2]:
            return self.a_pot(1.0)
        if er >= need + 0.02:
            # if calling commits us anyway and we're strong, shove
            if er >= 0.55 and to_call >= 0.4 * stack and self.ctx[2]:
                return self.a_raise(self.ctx[4])
            return self.a_call()
        return self.a_fold()
