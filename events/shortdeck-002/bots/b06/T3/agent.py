import json
import os
import random
import time

import numpy as np

from .common import CARD, Spot, Variant, act_call, act_fold, act_raise, safe_default
from . import fasteq as fe
from .icmfast import icm_me

_D = os.path.dirname(os.path.abspath(__file__))
_M = json.load(open(os.path.join(_D, "pf_matrix.json")))
EQ = np.array(_M["eq"], dtype=float)  # EQ[a][b]: class a vs class b
NC = np.array(_M["ncombo"], dtype=float)
EQ_RAND = EQ @ NC / NC.sum()
ORDER = np.argsort(-EQ_RAND)
_cum = np.cumsum(NC[ORDER]) / NC.sum()
PCT = np.zeros(81)  # top-fraction position of each class (midpoint)
_lo = np.zeros(81)
_hi = np.zeros(81)
for _i, _c in enumerate(ORDER):
    _hi[_c] = _cum[_i]
    _lo[_c] = _cum[_i] - NC[_c] / NC.sum()
    PCT[_c] = 0.5 * (_lo[_c] + _hi[_c])
QG = [0.02, 0.04, 0.06, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.85, 1.0]


def _frac_in(q):
    """fraction of each class inside the top-q range."""
    return np.clip((q - _lo) / np.maximum(_hi - _lo, 1e-9), 0.0, 1.0)


FRAC = np.array([_frac_in(q) for q in QG])  # (nq, 81)
EQR = np.array([EQ @ (NC * FRAC[i]) / (NC * FRAC[i]).sum() for i in range(len(QG))]).T  # (81, nq)
CLS_FRAC = FRAC[:, fe.CLS]  # (nq, NP) combo weights for each top-q range
CLS_PCT = PCT[fe.CLS]  # (NP,)


def qidx(q):
    best = 0
    for i, g in enumerate(QG):
        if abs(g - q) < abs(QG[best] - q):
            best = i
    return best


def eq_vs(c, q):
    """equity of class c vs top-q range, interpolated."""
    if q <= QG[0]:
        return EQR[c, 0]
    for i in range(1, len(QG)):
        if q <= QG[i]:
            t = (q - QG[i - 1]) / (QG[i] - QG[i - 1])
            return EQR[c, i - 1] * (1 - t) + EQR[c, i] * t
    return EQR[c, -1]


def range_weights(q):
    """combo weights (NP,) for a top-q range, smooth edge."""
    return np.clip((q + 0.06 - CLS_PCT) / 0.12, 0.03, 1.0)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        self.hands = {}  # seat -> hands seen
        self.vpip = {}
        self.pfr = {}
        self.aggr = {}  # postflop bets/raises
        self.passive = {}  # postflop calls/checks
        self.faced = {}  # postflop bets faced
        self.folded = {}  # postflop folds to a bet
        self.pre_aggr = -1

    # ---------------- opponent stats
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in hist:
                if act in ("sb", "bb", "ante", "return"):
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
                        self.aggr[seat] = self.aggr.get(seat, 0) + 1
                    elif act in ("call", "check"):
                        self.passive[seat] = self.passive.get(seat, 0) + 1
            cur = -1
            bet_on = False
            for st, seat, act, amt in hist:
                if st == 0 or act in ("return", "ante", "sb", "bb"):
                    continue
                if st != cur:
                    cur = st
                    bet_on = False
                if bet_on and act in ("fold", "call", "raise"):
                    self.faced[seat] = self.faced.get(seat, 0) + 1
                    if act == "fold":
                        self.folded[seat] = self.folded.get(seat, 0) + 1
                if act == "raise":
                    bet_on = True
            for s in seen:
                self.hands[s] = self.hands.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
            for s in pr:
                self.pfr[s] = self.pfr.get(s, 0) + 1
        except Exception:
            pass

    def stat(self, seat, d, prior, w=6.0):
        n = self.hands.get(seat, 0)
        return (d.get(seat, 0) + prior * w) / (n + w)

    # ---------------- main
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            return safe_default(obs)

    def decide(self, obs):
        self.t0 = time.perf_counter()
        if obs["phase"] == "discard":
            return safe_default(obs)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            return self.preflop(sp, obs)
        return self.postflop(sp, obs)

    # ---------------- preflop
    def raiser_range(self, seat, nraises, size_bb, allin, stack_bb, behind=7):
        pfr = self.stat(seat, self.pfr, 0.18)
        if nraises <= 1:
            q = pfr * 1.1
            if allin and stack_bb > 15:
                q *= 0.6
            if size_bb > 6 and not allin:
                q *= 0.8
        elif nraises == 2:
            q = pfr * 0.45
        else:
            q = pfr * 0.25
        if allin and stack_bb <= 15:
            if nraises <= 1:
                qpos = {0: 0.6, 1: 0.6, 2: 0.45, 3: 0.35, 4: 0.28, 5: 0.22, 6: 0.18}.get(behind, 0.15)
                q = max(q, qpos * min(1.4, max(0.75, (10.0 / max(stack_bb, 1.0)) ** 0.5)))
            else:
                q = max(q, 0.12)
        return min(max(q, 0.03), 0.8)

    def preflop(self, sp, obs):
        hole = sp.hole
        c = self.var.pre.cls(hole[0], hole[1])
        pct = PCT[c]
        bb = sp.bb
        T = sp.stack + sp.bet
        eff_bb = sp.eff / bb
        n_behind = len(sp.behind)
        maxbet = max(sp.bets)
        n_alive = sp.n_alive
        if sp.raises == 0:
            # unopened or limped
            limpers = sum(1 for h in sp.hist if h[0] == 0 and h[2] == "call")
            if eff_bb <= 14:
                if self.shove_ev(sp, c) > 0:
                    return act_raise(sp, sp.max_to)
                return act_call(sp) if sp.to_call == 0 else act_fold(sp)
            oq = {0: 0.5, 1: 0.45, 2: 0.33, 3: 0.26, 4: 0.21, 5: 0.17, 6: 0.14}.get(n_behind, 0.12)
            if n_alive <= 4:
                oq *= 1.25
            if sp.behind:
                avg_vp = sum(self.stat(x, self.vpip, 0.3) for x in sp.behind) / len(sp.behind)
                oq *= min(1.3, max(0.85, 1.0 + (0.28 - avg_vp) * 1.5))

            if limpers:
                oq *= 0.7
            if pct <= oq:
                size = bb * (2.5 if eff_bb > 30 else 2.2) + limpers * bb
                if size >= 0.4 * T:
                    return act_raise(sp, sp.max_to)
                return act_raise(sp, size)
            if sp.to_call == 0:
                return act_call(sp)
            if sp.role == "SB" and limpers == 0 and pct <= 0.55 and n_behind == 1 and False:
                return act_call(sp)
            return act_fold(sp)
        # facing raise(s)
        raiser = sp.raiser
        rstack = sp.stacks[raiser] + sp.bets[raiser] if raiser >= 0 else T
        allin = raiser >= 0 and sp.stacks[raiser] == 0
        q = self.raiser_range(raiser, sp.raises, maxbet / bb, allin, rstack / bb, sp.position_of(raiser))
        e = eq_vs(c, q)
        # extra players in the pot (callers) reduce equity
        others_in = sp.callers
        if others_in > 0:
            e = e * (0.82 ** others_in) if e > 0.3 else e * 0.8
        e *= 0.985 ** len(sp.behind)
        to_call = sp.to_call
        pot = sp.pot
        need = to_call / (pot + to_call)
        if sp.raises == 1 and not allin and sp.eff / bb <= 22 and sp.can_raise and self.shove_ev(sp, c, raiser, q) > 0:
            return act_raise(sp, sp.max_to)
        commit = to_call >= 0.35 * T or sp.eff <= maxbet * 2.2
        if commit:
            # all-in or near: ICM-priced call/shove
            need_i = self.icm_need(sp, raiser)
            if e > need_i + 0.005:
                return act_raise(sp, sp.max_to) if sp.can_raise and not allin else act_call(sp)
            return act_fold(sp)
        # deep: 3bet / call / fold
        if e > 0.6 or pct <= 0.025:
            target = maxbet * 3 + sum(sp.bets) - maxbet
            if target >= 0.35 * T:
                return act_raise(sp, sp.max_to)
            return act_raise(sp, target)
        if e > need + (0.035 if sp.role == "BB" and not sp.behind else 0.06) and to_call <= 0.12 * T:
            return act_call(sp)
        return act_fold(sp)

    def risk_premium(self, sp):
        # crude ICM: survival matters more near the money places and with big stacks covered
        n = sp.n_alive
        if n <= 2:
            return 0.0
        if n <= 4:
            return 0.03
        return 0.015

    def icm_need(self, sp, o):
        """equity needed to call an all-in-ish bet from seat o, priced in points."""
        alive = sp.obs["alive"]
        base = [sp.stacks[s] for s in alive]
        mi = alive.index(sp.me)
        oi = alive.index(o) if o in alive else -1
        T = sp.stack + sp.bet
        if oi < 0:
            return sp.to_call / (sp.pot + sp.to_call)
        To = sp.stacks[o] + sp.bets[o]
        S = min(T, To)
        dead = sp.pot - sp.bet - sp.bets[o]
        final = dead + 2 * S
        P = self.points
        b = list(base)
        b[oi] = sp.stacks[o] + sp.pot
        F = icm_me(b, mi, P)
        b = list(base)
        b[mi] = T - S + final
        b[oi] = To - S
        W = icm_me(b, mi, P)
        b = list(base)
        b[mi] = T - S
        b[oi] = To - S + final
        L = icm_me(b, mi, P)
        if W - L <= 1e-9:
            return 1.0
        return (F - L) / (W - L)

    def shove_ev(self, sp, c, raiser=-1, rq=0.0):
        """points EV of shoving minus folding (ICM), one-caller model."""
        bb = sp.bb
        T = sp.stack + sp.bet
        pot = sp.pot
        alive = sp.obs["alive"]
        base = [sp.stacks[s] for s in alive]
        mi = alive.index(sp.me)
        P = self.points
        cands = []
        pnf = 1.0
        for s in sp.opps:
            if sp.stacks[s] <= 0 or s not in alive:
                continue
            ot = sp.stacks[s] + sp.bets[s]
            S = min(T, ot)
            shove_bb = S / bb
            qc = min(0.5, max(0.07, 1.4 / max(shove_bb, 1.0)))
            vp = self.stat(s, self.vpip, 0.3)
            qc *= min(1.6, max(0.6, vp / 0.3))
            if sp.bets[s] > 0:  # blinds call wider
                qc *= 1.25
            qc *= {2: 1.6, 3: 1.3, 4: 1.15}.get(sp.n_alive, 1.0)
            qc = min(qc, 0.8)
            if s == raiser:
                qc = rq * min(1.0, max(0.4, 0.3 + 2.0 * sp.bets[s] / max(ot, 1)))
            cands.append((pnf * qc, s, qc, S, ot))
            pnf *= (1 - qc)
        b = list(base)
        for s in alive:
            if s != sp.me:
                b[alive.index(s)] += sp.bets[s]
        F = icm_me(b, mi, P)
        b = list(base)
        b[mi] = sp.stack + pot
        ev = pnf * icm_me(b, mi, P)
        cands.sort(reverse=True)
        WL = None
        for k, (pc, s, qc, S, ot) in enumerate(cands):
            e = eq_vs(c, qc)
            if k < 2 or WL is None:
                si = alive.index(s)
                final = pot - sp.bet - sp.bets[s] + 2 * S
                b = list(base)
                b[mi] = T - S + final
                b[si] = ot - S
                W = icm_me(b, mi, P)
                b = list(base)
                b[mi] = T - S
                b[si] = ot - S + final
                L = icm_me(b, mi, P)
                WL = (W, L)
            else:
                W, L = WL
            ev += pc * (e * W + (1 - e) * L)
        return ev - F

    # ---------------- postflop
    def opp_weights(self, sp, seat):
        """preflop-action range for an opponent as combo weights."""
        raised = called = False
        for st, s, act, amt in sp.hist:
            if st == 0 and s == seat:
                if act == "raise":
                    raised = True
                elif act == "call":
                    called = True
        if raised:
            q = self.stat(seat, self.pfr, 0.18) * 1.1
        elif called:
            q = self.stat(seat, self.vpip, 0.35) * 1.0
        else:
            q = 1.0
        q = min(max(q, 0.06), 1.0)
        return q

    def postflop(self, sp, obs):
        hero = [fe.conv(x) for x in sp.hole]
        board = [fe.conv(x) for x in sp.board]
        st = sp.street
        opps = sp.opps
        # main opponent: last aggressor on this street, else preflop/previous aggressor, else tightest
        main = sp.raiser if sp.raiser >= 0 else (sp.last_aggr if sp.last_aggr in opps else opps[0])
        q = self.opp_weights(sp, main)
        w = range_weights(q)
        # narrow by postflop aggression of the main opponent: weight by current made-hand strength
        bets_now = 0
        bets_prev = 0
        me_bet = False
        for h_st, s, act, amt in sp.hist:
            if h_st == st and s == sp.me and act == "raise":
                me_bet = True
            if s == main and act == "raise" and h_st >= 1:
                if h_st == st:
                    bets_now += (2.4 if st >= 2 else 1.6) if me_bet else 1
                else:
                    bets_prev += 1
        if bets_now or bets_prev:
            dead = hero + board
            alive = ~fe.INC[dead].any(axis=0)
            idx = np.nonzero(alive)[0]
            cv = fe.cur_values(board, idx).astype(float)
            ww = w[idx]
            order = np.argsort(cv)
            cw = np.cumsum(ww[order])
            pr = np.empty(len(idx))
            pr[order] = cw / cw[-1]
            k = 0.8 * bets_now + 0.4 * bets_prev
            ag = self.stat(main, self.aggr, 0.5, 8.0) / max(0.05, self.stat(main, self.passive, 0.5, 8.0))
            if ag > 1.5:
                k *= 0.6
            w = w.copy()
            w[idx] = ww * (0.15 + pr) ** (1.0 + 1.5 * k)
        el = time.perf_counter() - self.t0
        fast = el < 0.00012
        e1 = fe.equity(hero, board, w, self.rng, 12 if fast else 6, 16 if fast else 8)
        n_opp = sp.n_opp
        e = e1 ** (1 + 0.75 * (n_opp - 1)) if n_opp > 1 else e1
        pot = sp.pot
        to_call = sp.to_call
        T = sp.stack + sp.bet
        spr = sp.stack / max(pot, 1)
        last = st == 3
        if to_call == 0:
            # bet or check
            if e > 0.72 or (e > 0.6 and n_opp == 1):
                frac = 0.75 if e > 0.8 else 0.6
                return self.bet(sp, frac)
            was_aggr = sp.last_aggr == sp.me or self.pre_aggr_is_me(sp)
            fr = 1.0
            for o in opps:
                f_o = (self.folded.get(o, 0) + 0.45 * 6) / (self.faced.get(o, 0) + 6)
                fr *= f_o
            fr = fr ** (1.0 / max(1, n_opp))
            bl = min(1.6, max(0.3, 1.0 + (fr - 0.45) * 3.0))
            if not last and was_aggr and n_opp <= 2 and st == 1 and self.rng.random() < min(0.95, 0.6 * bl) and e > 0.3 - 0.15 * (bl - 1):
                return self.bet(sp, 0.5)
            if not last and n_opp == 1 and e > 0.45 - 0.1 * (bl - 1) and self.rng.random() < 0.3 * bl:
                return self.bet(sp, 0.5)
            if last and n_opp == 1 and e < 0.15 and self.rng.random() < 0.12 * bl * bl:
                return self.bet(sp, 0.6)
            return act_call(sp)
        need = to_call / (pot + to_call)
        if e > 0.85 or (e > 0.75 and spr < 1.5):
            if sp.can_raise:
                target = sp.bet + to_call + 1.0 * (pot + to_call) + to_call
                if target >= 0.5 * T:
                    return act_raise(sp, sp.max_to)
                return act_raise(sp, target)
            return act_call(sp)
        margin = 0.02 if last else 0.0
        if (to_call >= 0.4 * sp.stack or sp.stacks[main] == 0) and main >= 0:
            need = max(need, self.icm_need(sp, main))
        if e > need + margin:
            return act_call(sp)
        return act_fold(sp)

    def pre_aggr_is_me(self, sp):
        last = -1
        for h_st, s, act, amt in sp.hist:
            if h_st == 0 and act == "raise":
                last = s
        return last == sp.me

    def turn_eq(self, hero, board, w):
        return fe.equity(hero, board, w, self.rng, 0)

    def bet(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        T = sp.stack + sp.bet
        if target >= 0.6 * T:
            target = sp.max_to
        return act_raise(sp, target)
