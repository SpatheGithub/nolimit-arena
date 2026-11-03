import json
import os
import random
import time
from bisect import bisect_right

from .ev import CID, FLV, FS, K5, KM, KS, NF

_DBG = False
PRE_V0 = False
OPEN_V0 = False
FACE_V0 = False
PUSH_V0 = True
PUSH_DEPTH = True
FACE2 = False
FACE3 = True
OPEN_MULT = 1.25
ADJ_PLUS = 0.08
RTHR = 0.78
RESHOVE = False
FACE_MULT = 1.0
PUSH_MULT = 1.15
PUSH_MAX = 12
HU_FIX = True
TH_FIX = False
HU_POST = True
PREM_FIX = True
POST_V0 = False
CBET = True
CBET_F = 0.65
VTHR = 0.63
VFRAC = 0.65
NARROW = True
BLUFF = False
_D = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_D, "_common.json")) as _f:
    _SH = json.load(_f)["decks"]["short"]
with open(os.path.join(_D, "pre.json")) as _f:
    _M = json.load(_f)["M"]

PCT = [x / 1e4 for x in _SH["pct"]]
EQM = [[x / 1e4 for x in row] for row in _SH["eq_multi"]]
M = [[x / 1e4 for x in row] for row in _M]


def _ncombo(c):
    hi, lo = c // 9, c % 9
    return 6 if hi == lo else (4 if hi > lo else 12)


NC = [_ncombo(c) for c in range(81)]
ORDER = sorted(range(81), key=lambda c: PCT[c])
# cumulative top-fraction boundaries
_CUM = []
_acc = 0
for _c in ORDER:
    _acc += NC[_c]
    _CUM.append(_acc / 630.0)
QGRID = [0.02 * (i + 1) for i in range(50)]
# EQR[c][i]: equity of class c vs top QGRID[i] of hands
EQR = []
for _c in range(81):
    row = []
    for q in QGRID:
        w = 0.0
        s = 0.0
        prev = 0.0
        for k, j in enumerate(ORDER):
            end = _CUM[k]
            if prev >= q:
                break
            frac = (min(end, q) - prev) / (end - prev)
            ww = NC[j] * frac
            w += ww
            s += ww * M[_c][j]
            prev = end
        row.append(s / w)
    EQR.append(row)
# top-fraction position (midpoint) of each class, used for range sampling
TOPQ = [0.0] * 81
_prev = 0.0
for _k, _c in enumerate(ORDER):
    TOPQ[_c] = (_prev + _CUM[_k]) / 2
    _prev = _CUM[_k]


def cls_of(c1, c2):
    r1, r2 = c1 >> 2, c2 >> 2
    if r1 == r2:
        return r1 * 9 + r1
    hi, lo = (r1, r2) if r1 > r2 else (r2, r1)
    return hi * 9 + lo if (c1 & 3) == (c2 & 3) else lo * 9 + hi


# class lookup for card pairs
PCLS = [[cls_of(a, b) if a != b else 0 for b in range(36)] for a in range(36)]
# all 630 hole combos, strongest class first
ALLC = sorted([(a, b) for a in range(36) for b in range(a + 1, 36)], key=lambda xy: TOPQ[PCLS[xy[0]][xy[1]]])
ALLQ = [TOPQ[PCLS[x][y]] for x, y in ALLC]


def eq_range(c, q):
    if q >= 1.0:
        return EQM[c][0]
    i = int(q / 0.02 + 0.5) - 1
    if i < 0:
        i = 0
    if i > 49:
        i = 49
    return EQR[c][i]


def icm_me(stacks, me, pay):
    """Malmuth-Harville equity of player index ``me`` (top 4 places)."""
    T = float(sum(stacks))
    if stacks[me] <= 0 or T <= 0:
        return 0.0
    n = len(stacks)
    sm = stacks[me]
    p1 = pay[0] if len(pay) > 0 else 0
    res = p1 * sm / T
    p2 = pay[1] if len(pay) > 1 and n > 1 else 0
    p3 = pay[2] if len(pay) > 2 and n > 2 else 0
    p4 = pay[3] if len(pay) > 3 and n > 3 else 0
    if not (p2 or p3 or p4):
        return res
    others = [i for i in range(n) if i != me and stacks[i] > 0]
    for a in others:
        sa = stacks[a]
        Ta = T - sa
        pa = sa / T
        res += pa * p2 * sm / Ta
        if p3:
            for b in others:
                if b == a:
                    continue
                sb = stacks[b]
                Tb = Ta - sb
                pb = pa * sb / Ta
                res += pb * p3 * sm / Tb
                if p4:
                    for c in others:
                        if c == a or c == b:
                            continue
                        sc = stacks[c]
                        Tc = Tb - sc
                        if Tc <= 0:
                            continue
                        res += pb * sc / Tb * p4 * sm / Tc
    return res


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.pay = list(config.get("points") or [100, 45, 20, 8])
        n = config.get("seats", 8)
        self.n_seats = n
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.agg = [0] * 16
        self.pas = [0] * 16
        self.last_hand = -1
        self.pf_raiser = -1

    # ------------------------------------------------------------------ stats
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
                        self.agg[seat] += 1
                    elif act in ("call", "check"):
                        self.pas[seat] += 1
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass

    def vpip_est(self, s):
        return (self.vpip[s] + 3.5) / (self.hands[s] + 10.0)

    def pfr_est(self, s):
        return (self.pfr[s] + 2.0) / (self.hands[s] + 10.0)

    def agg_est(self, s):
        return (self.agg[s] + 2.0) / (self.agg[s] + self.pas[s] + 6.0)

    # ------------------------------------------------------------------ act
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            if _DBG:
                import traceback
                print(traceback.format_exc().replace("\n", " | ")[-600:])
            if "check" in obs.get("legal", ()):
                return {"action": "check"}
            return {"action": "fold"}

    def decide(self, obs):
        t0 = time.perf_counter()
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        legal = obs["legal"]
        self.can_check = "check" in legal
        self.can_raise = ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0
        if obs["street_index"] == 0:
            if PRE_V0:
                return self.pre_v0(obs)
            return self.preflop(obs)
        if POST_V0:
            return self.post_v0(obs)
        return self.postflop(obs, t0)

    def pre_v0(self, obs):
        from ._common import Spot, Variant, act_allin, act_call, act_fold, act_raise, preflop_pct
        if not hasattr(self, "var"):
            self.var = Variant(None if False else {"ranks": "6789TJQKA", "ranking": {"order": ["high_card", "pair", "two_pair", "trips", "straight", "full_house", "flush", "quads", "straight_flush"], "ace_low": True}})
        sp = Spot(obs, self.var)
        pct = preflop_pct(self.var, sp.hole)
        eff = sp.eff_bb
        if sp.raises == 0:
            nb = len(sp.behind)
            thr = 0.12 + 0.05 * max(0, 6 - nb)
            if eff <= 12:
                thr += 0.1
                if pct <= thr:
                    return act_allin(sp)
                return act_fold(sp)
            if pct <= thr:
                return act_raise(sp, sp.bb * 2.5 + sp.callers * sp.bb)
            return act_fold(sp)
        if pct <= 0.06:
            return act_allin(sp)
        if pct <= 0.16 and sp.to_call <= 0.2 * (sp.stack + sp.bet):
            return act_call(sp)
        return act_fold(sp)

    def post_v0(self, obs):
        from ._common import PAIR, TWO_PAIR, Spot, Variant, act_call, act_fold, act_raise
        if not hasattr(self, "var"):
            self.var = Variant({"ranks": "6789TJQKA", "ranking": {"order": ["high_card", "pair", "two_pair", "trips", "straight", "full_house", "flush", "quads", "straight_flush"], "ace_low": True}})
        sp = Spot(obs, self.var)
        v = self.var.best(sp.hole, sp.board)
        cat = self.var.ranker.category(v)
        bv = self.var.ranker.value(sp.board)
        if cat >= TWO_PAIR + 1 and v > bv:
            if sp.can_raise:
                return act_raise(sp, sp.bet + sp.to_call + 0.75 * (sp.pot + sp.to_call))
            return act_call(sp)
        if cat >= TWO_PAIR and v > bv:
            if sp.to_call == 0:
                return act_raise(sp, 0.6 * sp.pot)
            if sp.to_call <= 0.6 * sp.pot:
                return act_call(sp)
            return act_fold(sp)
        if cat >= PAIR and v > bv and sp.to_call <= 0.3 * sp.pot:
            return act_call(sp)
        return act_fold(sp)

    # helpers
    def fold(self):
        return {"action": "check"} if self.can_check else {"action": "fold"}

    def call(self, obs):
        return {"action": "check"} if obs["to_call"] == 0 else {"action": "call"}

    def raise_to(self, obs, amt):
        if not self.can_raise:
            return self.call(obs)
        a = int(amt)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        # if remaining stack after raise is tiny, just shove
        me = obs["seat"]
        tot = obs["stacks"][me] + obs["bets"][me]
        if tot - a < 0.2 * a:
            a = hi
        return {"action": "raise", "amount": a}

    def allin(self, obs):
        if self.can_raise:
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self.call(obs)

    def icm_ok(self, obs, eq, win_gain, lose_loss, extra=0.0, villain=-1, v_extra=0):
        """True if eq meets the (ICM-adjusted) requirement for an all-in-ish call.
        win_gain: chips added to my stack on a win vs folding (pot + villain's extra);
        lose_loss: chips I put in (lost on a loss)."""
        alive = obs["alive"]
        stacks = obs["stacks"]
        me = obs["seat"]
        if lose_loss <= 0:
            return True
        need_chip = lose_loss / float(win_gain + lose_loss)
        if len(alive) > 6:
            return eq >= need_chip + extra
        idx = alive.index(me)
        pot = obs["pot"]
        base = [stacks[s] for s in alive]
        vi = alive.index(villain) if villain in alive else -1
        f = list(base)
        win = list(base)
        lose = list(base)
        win[idx] = stacks[me] + win_gain
        lose[idx] = max(0, stacks[me] - lose_loss)
        if vi >= 0:
            f[vi] += pot
            win[vi] = max(0, stacks[villain] - v_extra)
            lose[vi] = stacks[villain] + pot + lose_loss
        pay = self.pay
        F = icm_me(f, idx, pay)
        W = icm_me(win, idx, pay)
        L = icm_me(lose, idx, pay)
        if W - L <= 1e-9:
            return eq >= need_chip + extra
        need = (F - L) / (W - L)
        return eq >= need + extra

    # ------------------------------------------------------------------ preflop
    def preflop(self, obs):
        me = obs["seat"]
        hole = [CID[c] for c in obs["hole"]]
        c = PCLS[hole[0]][hole[1]]
        pct = PCT[c]
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_tot = stacks[me] + bets[me]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        opps = [s for s in in_hand if s != me]
        hist = obs["history"]
        raises = 0
        raiser = -1
        callers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises += 1
                raiser = seat
                callers = 0
            elif act == "call":
                callers += 1
        # players yet to act behind me
        n = len(alive)
        btn = obs["button"]
        if n == 2:
            bi = alive.index(btn) if btn in alive else 0
            order = [alive[bi], alive[1 - bi]]
        else:
            bbs = obs["bb_seat"]
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me)
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        nb = len(behind)
        to_call = obs["to_call"]
        pot = obs["pot"]
        maxopp = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_tot, maxopp)
        eff_bb = eff / bb

        if HU_FIX and raises == 0 and n == 2 and to_call > 0 and eff_bb > PUSH_MAX:
            if eff_bb <= 16:
                if pct <= 0.65:
                    return self.allin(obs)
                return self.fold()
            if pct <= 0.85:
                return self.raise_to(obs, 2.2 * bb)
            return self.fold()
        if raises == 0 and PUSH_V0 and eff_bb <= PUSH_MAX:
            thr = 0.12 + 0.05 * max(0, 6 - nb) + 0.1
            if eff_bb > 12:
                thr *= 0.85
            if PUSH_DEPTH:
                if eff_bb <= 4:
                    thr *= 1.6
                elif eff_bb <= 6:
                    thr *= 1.35
                elif eff_bb <= 9:
                    thr *= 1.15
                if n == 2:
                    thr = max(thr, 0.62 if eff_bb > 8 else 0.75)
                thr = min(thr * PUSH_MULT, 0.92)
            if pct <= thr:
                return self.allin(obs)
            return self.fold()
        if raises == 0 and OPEN_V0 and eff_bb > 12:
            thr = 0.12 + 0.05 * max(0, 6 - nb)
            if pct <= thr:
                return self.raise_to(obs, bb * 2.5 + callers * bb)
            return self.fold()
        if raises > 0 and FACE_V0:
            if pct <= 0.06:
                return self.allin(obs)
            if pct <= 0.16 and to_call <= 0.2 * my_tot:
                return self.call(obs)
            return self.fold()
        if raises == 0:
            # unopened (maybe limpers / BB option)
            if eff_bb <= 14:
                if self.shove_ev(obs, c, behind, eff, pot, bets[me]):
                    return self.allin(obs)
                return self.fold()
            if to_call == 0:
                # BB option facing limpers
                if pct <= 0.12:
                    return self.raise_to(obs, bets[me] + 3 * bb + callers * bb)
                return self.fold()
            thr = {0: 0.6, 1: 0.5, 2: 0.42, 3: 0.32, 4: 0.26, 5: 0.22, 6: 0.19}.get(nb, 0.17) * OPEN_MULT
            if callers:
                thr = min(thr, 0.2)
            # loosen if players behind are tight
            if behind:
                tight = sum(1 for s in behind if self.vpip_est(s) < 0.25)
                thr *= 1.0 + 0.1 * tight / len(behind)
            if pct <= thr:
                size = (2.5 if eff_bb > 30 else 2.2) * bb + callers * bb
                if eff_bb <= 22 and pct <= 0.08:
                    size = 2.2 * bb
                return self.raise_to(obs, size)
            return self.fold()

        # facing a raise
        rbet = bets[raiser] if raiser >= 0 else max(bets)
        r_tot = stacks[raiser] + bets[raiser] if raiser >= 0 else maxopp
        r_allin = raiser >= 0 and stacks[raiser] == 0
        # raiser range estimate
        q = min(0.6, max(0.06, self.pfr_est(raiser) * 1.1)) if raiser >= 0 else 0.15
        rb = rbet / bb
        if FACE2 and (r_allin or rb >= 8):
            rbb = r_tot / bb
            if rbb <= 12:
                q = max(q, min(0.6, 0.18 + 0.025 * (12 - rbb)))
                if n == 2:
                    q = max(q, 0.45 if rbb > 8 else 0.6)
                elif n == 3:
                    q = max(q, 0.3)
            else:
                q = max(0.08, q * 0.8)
        elif rb >= 8:
            # big raises / shoves: when short, ranges are wide
            rbb = r_tot / bb
            if rbb <= 12:
                q = max(q, min(0.5, 0.18 + 0.02 * (12 - rbb)))
            else:
                q = max(0.08, q * 0.8)
        if FACE3 and raises == 1 and raiser >= 0 and raiser in order and (r_allin or rbet >= 0.6 * r_tot):
            rbb = r_tot / bb
            if rbb <= 16:
                nbr = len(order) - 1 - order.index(raiser)
                qm = 0.22 + 0.05 * max(0, 6 - nbr)
                if rbb <= 4:
                    qm *= 1.6
                elif rbb <= 6:
                    qm *= 1.35
                elif rbb <= 9:
                    qm *= 1.15
                elif rbb > 12:
                    qm *= 0.85
                if n == 2:
                    qm = max(qm, 0.62 if rbb > 8 else 0.75)
                qm = min(qm, 0.92) * FACE_MULT
                q = max(q, qm)
        if raises >= 2:
            q *= 0.45
        if HU_FIX and n == 2:
            q = max(q, 0.3 if raises >= 2 else 0.6)
        if TH_FIX and n == 3:
            q = max(q, 0.22 if raises >= 2 else 0.42)
        q = max(0.03, q)
        eq = eq_range(c, q)
        if callers:
            eq -= 0.06 * callers
        if HU_FIX and n == 2 and raises == 1 and not r_allin and rb <= 3.5:
            if eff_bb <= 25:
                if pct <= 0.28:
                    return self.allin(obs)
            elif pct <= 0.06:
                return self.raise_to(obs, 3 * rbet)
            if pct <= 0.8 and to_call <= 0.15 * my_tot:
                return self.call(obs)
            return self.fold()
        if TH_FIX and n == 3 and raises == 1 and callers == 0 and not r_allin and rb <= 3.5:
            if eff_bb <= 25:
                if pct <= 0.15:
                    return self.allin(obs)
            elif pct <= 0.05:
                return self.raise_to(obs, 3 * rbet)
            if pct <= 0.55 and to_call <= 0.15 * my_tot:
                return self.call(obs)
            return self.fold()
        if PREM_FIX and pct <= 0.03:
            if raises == 2 and eff_bb > 40:
                return self.raise_to(obs, 2.5 * rbet)
            if raises >= 2 or eff_bb <= 30:
                return self.allin(obs)
            return self.raise_to(obs, 3 * rbet + callers * rbet)
        # cost if we commit fully
        commit_amt = min(my_tot, r_tot) - bets[me]
        if r_allin or to_call >= 0.33 * stacks[me] or eff_bb <= 18:
            # all-in decision: shove or fold
            call_amt = min(commit_amt, my_tot - bets[me])
            v_extra = max(0, min(r_tot, my_tot) - rbet)
            win_gain = pot + v_extra
            if self.icm_ok(obs, eq, win_gain, call_amt, 0.01, raiser, v_extra):
                return self.allin(obs)
            return self.fold()
        price = to_call / float(pot + to_call)
        if RESHOVE and raises == 1 and callers == 0 and eff_bb <= 30 and q >= 0.24 and pct <= 0.16:
            return self.allin(obs)
        # value 3-bet
        if eq >= 0.6 and pct <= 0.1:
            tgt = 3 * rbet + callers * rbet
            if tgt >= 0.4 * my_tot:
                return self.allin(obs)
            return self.raise_to(obs, tgt)
        if raises >= 2:
            if PREM_FIX and pct <= 0.07 and eq >= price + 0.02:
                return self.call(obs)
            if eq >= price + 0.08 and to_call <= 0.25 * my_tot:
                return self.call(obs)
            return self.fold()
        if to_call <= 0.12 * my_tot and eq >= price + 0.1 and pct <= 0.35:
            return self.call(obs)
        return self.fold()

    def shove_ev(self, obs, c, behind, eff, pot, mybet):
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        pfold = 1.0
        qsum = 0.0
        wsum = 0.0
        for s in behind:
            st = stacks[s] + bets[s]
            e = min(st, eff)
            ebb = e / bb
            # caller range: wider when the shove is small vs the pot/blinds
            base = 0.12 + 0.08 * max(0.0, (self.vpip_est(s) - 0.3))
            if s == obs["bb_seat"]:
                base += 0.1
            q = base * (10.0 / max(ebb, 3.0)) ** 0.5
            q = min(0.7, max(0.05, q))
            p = q
            pfold *= (1 - p)
            qsum += q * p
            wsum += p
        if not behind:
            return True
        qavg = qsum / wsum if wsum > 0 else 0.15
        eq = eq_range(c, qavg)
        risk = eff - mybet
        # when called: win pot + caller's contribution, lose risk
        win_called = pot + (eff - mybet)  # approx (caller matches)
        ev = pfold * pot + (1 - pfold) * (eq * (pot + risk + risk) - risk)
        if len(obs["alive"]) <= 6:
            # ICM tax: require a margin proportional to risk
            alive = obs["alive"]
            me = obs["seat"]
            idx = alive.index(me)
            st = [stacks[s] for s in alive]
            f = icm_me(st, idx, self.pay)
            w = list(st)
            w[idx] = stacks[me] + pot
            l = list(st)
            l[idx] = max(0, stacks[me] - risk)
            wc = list(st)
            wc[idx] = stacks[me] + pot + risk
            evi = pfold * icm_me(w, idx, self.pay) + (1 - pfold) * (
                eq * icm_me(wc, idx, self.pay) + (1 - eq) * icm_me(l, idx, self.pay))
            return evi > f
        return ev > 0.0

    # ------------------------------------------------------------------ postflop
    def opp_range(self, obs, s):
        hist = obs["history"]
        raised = 0
        called = False
        for st, seat, act, amt in hist:
            if st == 0 and seat == s:
                if act == "raise":
                    raised += 1
                elif act == "call":
                    called = True
        if raised:
            q = min(0.6, max(0.08, self.pfr_est(s) * 1.1))
            if raised >= 2:
                q *= 0.5
            return q
        if called:
            # did anyone raise preflop?
            anyr = any(a == "raise" for st, _, a, _ in hist if st == 0)
            if anyr:
                return min(0.7, max(0.15, self.vpip_est(s)))
            return min(0.9, max(0.3, self.vpip_est(s) * 1.4))
        return 1.0

    def mc_equity(self, hole, board, qs, budget, t0, lvls=None):
        if lvls is None:
            lvls = [0] * len(qs)
        cnt = {}
        for c in board:
            cnt[c >> 2] = cnt.get(c >> 2, 0) + 1
        mx = max(cnt.values()) if cnt else 1
        npairs = sum(1 for v in cnt.values() if v >= 2)
        bcat = 0 if mx == 1 else (1 if (npairs == 1 and mx == 2) else (2 if mx == 2 else 3))
        known = set(hole) | set(board)
        deck = [c for c in range(36) if c not in known]
        nd = len(deck)
        need = 5 - len(board)
        a0 = b0 = m0 = 0
        for c in hole + board:
            a0 += K5[c]
            b0 += KS[c]
            m0 += KM[c]
        ba = bb_ = bm = 0
        for c in board:
            ba += K5[c]
            bb_ += KS[c]
            bm += KM[c]
        rnd = self.rng.random
        clock = time.perf_counter
        wins = 0.0
        n = 0
        live = []
        tq = []
        for i, xy in enumerate(ALLC):
            if xy[0] not in known and xy[1] not in known:
                live.append(xy)
                tq.append(ALLQ[i])
        lens = [max(bisect_right(tq, q), min(len(live), 8)) for q in qs]
        deadline = t0 + budget
        while True:
            used = set()
            # opponents first (sampled from their range)
            opp_hands = []
            for oi, L in enumerate(lens):
                lv = lvls[oi]
                ok = False
                for _ in range(24):
                    x, y = live[int(rnd() * L)]
                    if x in used or y in used:
                        continue
                    if lv:
                        s = FS[bb_ + KS[x] + KS[y]]
                        if s >= 0:
                            cv = FLV[((bm + KM[x] + KM[y]) >> (9 * s)) & 511]
                        else:
                            cv = NF[ba + K5[x] + K5[y]]
                        if (cv >> 20) < bcat + lv and rnd() > 0.3:
                            continue
                    ok = True
                    break
                if not ok:
                    for x, y in live:
                        if x not in used and y not in used:
                            break
                used.add(x)
                used.add(y)
                opp_hands.append((x, y))
            ra = ba
            rs = bb_
            rm = bm
            k = 0
            while k < need:
                x = deck[int(rnd() * nd)]
                if x in used:
                    continue
                used.add(x)
                ra += K5[x]
                rs += KS[x]
                rm += KM[x]
                k += 1
            # hero
            ha = ra - ba + a0
            hs = rs - bb_ + b0
            hm = rm - bm + m0
            s = FS[hs]
            hv = FLV[(hm >> (9 * s)) & 511] if s >= 0 else NF[ha]
            top = -1
            ties = 0
            for x, y in opp_hands:
                oa = ra + K5[x] + K5[y]
                os_ = rs + KS[x] + KS[y]
                s = FS[os_]
                if s >= 0:
                    v = FLV[((rm + KM[x] + KM[y]) >> (9 * s)) & 511]
                else:
                    v = NF[oa]
                if v > top:
                    top = v
                    ties = 1 if v == hv else 0
                elif v == top and v == hv:
                    ties += 1
            if hv > top:
                wins += 1.0
            elif hv == top:
                wins += 1.0 / (1 + ties)
            n += 1
            if (n & 3) == 0 and clock() > deadline:
                break
            if n >= 600:
                break
        return wins / n, n

    def postflop(self, obs, t0):
        me = obs["seat"]
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        st = obs["street_index"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        nopp = len(opps)
        hist = obs["history"]
        qs = []
        lvls = []
        for s in opps:
            qs.append(self.opp_range(obs, s))
            lv = 0
            for h_st, seat, act, amt in hist:
                if h_st >= 1 and seat == s and act == "raise":
                    lv += 1
            lvls.append(min(2, lv))
        if HU_FIX and len(obs["alive"]) == 2:
            qs = [max(q, 0.6) for q in qs]
        if nopp > 3:
            idx = sorted(range(nopp), key=lambda i: qs[i])[:3]
            qs = [qs[i] for i in idx]
            lvls = [lvls[i] for i in idx]
        eq, ns = self.mc_equity(hole, board, qs, 0.0003, t0, lvls if NARROW else None)
        if nopp > 3:
            eq = eq ** (nopp / 3.0)
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_tot = stacks[me] + bets[me]
        stack = stacks[me]
        hist = obs["history"]
        pf_raiser = -1
        street_raises = 0
        for h_st, seat, act, amt in hist:
            if h_st == 0 and act == "raise":
                pf_raiser = seat
            if h_st == st and act == "raise":
                street_raises += 1
        rel = eq * (nopp + 1)
        river = st == 3
        rng = self.rng.random
        if to_call == 0:
            # value bet
            vthr = VTHR if nopp == 1 else VTHR / (0.5 + 0.5 * nopp) + 0.08
            if HU_POST and len(obs["alive"]) == 2:
                vthr -= 0.05
            if eq >= vthr:
                frac = VFRAC if not river else (0.85 if eq > 0.85 else VFRAC)
                return self.raise_to(obs, bets[me] + frac * pot)
            # c-bet / bluff
            if CBET and nopp == 1 and pf_raiser == me and st == 1 and rng() < CBET_F:
                return self.raise_to(obs, bets[me] + 0.45 * pot)
            if nopp == 1 and st == 2 and eq >= 0.4 and pf_raiser == me and rng() < 0.4:
                return self.raise_to(obs, bets[me] + 0.5 * pot)
            if BLUFF and nopp == 1 and river and eq < 0.12 and rng() < 0.2:
                return self.raise_to(obs, bets[me] + 0.6 * pot)
            return self.fold()
        # facing a bet
        prev_pot = pot - to_call  # approx: pot before the bet portion we face
        bet_frac = to_call / float(max(1, pot - to_call))
        price = to_call / float(pot + to_call)
        if NARROW:
            adj = 0.02 + 0.03 * min(1.5, bet_frac) + 0.04 * max(0, street_raises - 1)
        else:
            adj = 0.03 + 0.06 * min(1.5, bet_frac) + 0.06 * max(0, street_raises - 1)
        # aggressive opponents bluff more
        bettor = -1
        for h_st, seat, act, amt in hist:
            if h_st == st and act == "raise":
                bettor = seat
        if bettor >= 0:
            a = self.agg_est(bettor)
            adj -= 0.1 * (a - 0.33)
        eqa = eq - adj - ADJ_PLUS
        if HU_POST and len(obs["alive"]) == 2:
            eqa += 0.05
        # raise for value
        rthr = RTHR if nopp == 1 else RTHR - 0.18
        if eq >= rthr and self.can_raise and street_raises < 3:
            if stack <= 1.2 * (pot + to_call):
                return self.allin(obs)
            return self.raise_to(obs, bets[me] + to_call + 0.8 * (pot + to_call))
        if eqa >= price:
            if to_call >= 0.5 * stack and len(obs["alive"]) <= 6:
                if not self.icm_ok(obs, eqa, pot, min(to_call, stack), 0.0, bettor, 0):
                    return self.fold()
            return self.call(obs)
        return self.fold()
