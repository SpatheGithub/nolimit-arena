"""b08 shortdeck bot: precomputed class-vs-class equity, push/fold EV model,
range-based preflop, heuristic postflop, per-seat reads."""

import json
import os
import random

from ._common import (CARD, FLUSH, HIGH, PAIR, STRAIGHT, TRIPS, TWO_PAIR, Spot, Variant, act_allin,
                      act_call, act_fold, act_pot, act_raise, features, safe_default)

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "eqmat.json")) as _f:
    _D = json.load(_f)
EQ = _D["eq"]
NCOMBO = _D["ncombo"]

_V0 = Variant({"ranks": "6789TJQKA"})
PRE = _V0.pre
PCT = PRE.pct
ORDER = sorted(range(81), key=lambda c: PCT[c])
TOTAL = float(sum(NCOMBO))

# tunables
P_PUSH_BB = 15
P_OPEN = 1.0
P_DEEPCALL = 0.08
P_AI_MARGIN = 0.09
P_POSTCALL = 0.28
P_BLUFF = 2.2
P_BBDEF = 0.05
P_SBLIMP = 0.5
P_THIN = 0.38
P_READ = 1.0
P_STEAL = 0.6
P_HUM = 0.5
P_HUOPEN = 0.6
P_BETPEN = 0.15
P_RIVPEN = 0.0
P_BARREL = 0.04
P_FTB = 1.0
P_LIGHT3 = 0.0
P_RESTEAL = 0.5
P_VSIZE = 1.0
P_3BCOMMIT = 0
P_CALLQ = 1.0
P_WIDEN = 1
P_M5 = 0.0
P_POSW = 1

# EQR[c][i]: equity of class c vs the top (i+1)*2% of hands
GRID = 50


def _build_eqr():
    out = []
    cum = []
    acc = 0.0
    for c in ORDER:
        acc += NCOMBO[c]
        cum.append(acc / TOTAL)
    for me in range(81):
        row_eq = EQ[me]
        row = []
        for i in range(GRID):
            p = (i + 1) / GRID
            w_sum = 0.0
            e_sum = 0.0
            prev = 0.0
            for k, c in enumerate(ORDER):
                hi = cum[k]
                if prev >= p:
                    break
                frac = 1.0 if hi <= p else (p - prev) / (hi - prev)
                w = NCOMBO[c] * frac
                if c == me:
                    w *= 0.4  # crude card removal
                w_sum += w
                e_sum += w * row_eq[c]
                prev = hi
            row.append(e_sum / w_sum if w_sum > 0 else 0.5)
        out.append(row)
    return out


EQR = _build_eqr()


def eq_vs(cls, p):
    i = int(p * GRID + 0.5) - 1
    if i < 0:
        i = 0
    elif i >= GRID:
        i = GRID - 1
    return EQR[cls][i]


def _interp(x, pts):
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


# opponents' calling range (fraction of hands) vs a shove of X big blinds
CALL_PTS = [(2, 0.65), (4, 0.45), (6, 0.34), (8, 0.28), (10, 0.24), (15, 0.18), (20, 0.14), (30, 0.11),
            (50, 0.08), (100, 0.06)]
# opponents' shoving range by their stack in BB
SHOVE_PTS = [(2, 0.7), (5, 0.5), (8, 0.38), (10, 0.32), (15, 0.24), (20, 0.18), (30, 0.12), (50, 0.08),
             (100, 0.06)]
# open-raise range by players left to act behind
OPEN_W = {0: 0.0, 1: 0.45, 2: 0.36, 3: 0.28, 4: 0.22, 5: 0.18, 6: 0.15, 7: 0.13}


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.n = config.get("seats", 8)
        self.hands = {}
        self.vpip = {}
        self.pfr = {}
        self.faced = {}
        self.called = {}
        self.shoves = {}
        self.pf_aggr = {}  # postflop bets/raises
        self.pf_pass = {}  # postflop calls/checks
        self.start_hid = -1
        self.ftb_f = {}
        self.ftb_c = {}
        self.start_tot = []

    # ---------- reads ----------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            allin_raise = False
            cur_st = 0
            bet_on = False
            for st, seat, act, amt in hist:
                if seat is None or seat < 0:
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
                    if allin_raise and seat != self.seat:
                        self.faced[seat] = self.faced.get(seat, 0) + 1
                        if act in ("call", "raise"):
                            self.called[seat] = self.called.get(seat, 0) + 1
                else:
                    if st != cur_st:
                        cur_st = st
                        bet_on = False
                    if bet_on and seat != self.seat:
                        if act == "fold":
                            self.ftb_f[seat] = self.ftb_f.get(seat, 0) + 1
                        elif act in ("call", "raise"):
                            self.ftb_c[seat] = self.ftb_c.get(seat, 0) + 1
                    if act == "raise":
                        bet_on = True
                    if act in ("raise",):
                        self.pf_aggr[seat] = self.pf_aggr.get(seat, 0) + 1
                    elif act in ("call", "check"):
                        self.pf_pass[seat] = self.pf_pass.get(seat, 0) + 1
                if st == 0 and act == "raise" and amt is not None and self.start_hid == event.get("hand_id"):
                    tot = self.start_tot
                    if seat < len(tot) and amt >= tot[seat] > 0:
                        allin_raise = True
            for s in seen:
                self.hands[s] = self.hands.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
            for s in pr:
                self.pfr[s] = self.pfr.get(s, 0) + 1
        except Exception:
            pass

    def rate(self, d, seat, prior, k=6.0):
        h = self.hands.get(seat, 0)
        return (d.get(seat, 0) + prior * k) / (h + k)

    def call_rate(self, seat, base):
        f = self.faced.get(seat, 0)
        c = self.called.get(seat, 0)
        k = 3.0
        return (c + base * k) / (f + k)

    # ---------- main ----------
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            return safe_default(obs)

    def decide(self, obs):
        if obs["phase"] == "discard":
            return safe_default(obs)
        sp = Spot(obs, self.var)
        if sp.street == 0:
            if self.start_hid != obs["hand_id"]:
                self.start_hid = obs["hand_id"]
                self.start_tot = [a + b for a, b in zip(obs["stacks"], obs["bets"])]
            return self.preflop(sp, obs)
        return self.postflop(sp, obs)

    # ---------- preflop ----------
    def margin(self, sp, obs):
        """Extra equity demanded for risking our stack (points-table caution)."""
        n = sp.n_alive
        stack_bb = (sp.stack + sp.bet) / sp.bb
        m = P_AI_MARGIN * (P_HUM if n == 2 else 0.6 if n == 3 else 1.0)
        if n >= 5:
            m += P_M5
        if n == 5:
            m += 0.02  # bubble: 4 paid
        if stack_bb < 8:
            m -= 0.02
        return m

    def opp_total(self, sp, s):
        return sp.stacks[s] + sp.bets[s]

    def shove_ev(self, sp, cls, obs):
        me_total = sp.stack + sp.bet
        pot = sp.pot
        bb = sp.bb
        ev = 0.0
        p_none = 1.0
        for s in sp.opps:
            ot = self.opp_total(sp, s)
            if sp.stacks[s] <= 0:
                continue
            risk = min(me_total, ot)
            final = pot + (risk - sp.bet) + (risk - sp.bets[s])
            x = risk / bb
            q = _interp(x, CALL_PTS)
            if s == obs["bb_seat"] and sp.raises == 0:
                q = min(1.0, q * 1.25)
            q = self.call_rate(s, q)
            vr = self.rate(self.vpip, s, 0.25)
            q = min(1.0, max(0.02, q * (0.6 + 0.4 * vr / 0.25) * P_CALLQ))
            e = eq_vs(cls, q)
            gain = e * final - (risk - sp.bet)
            ev += p_none * q * gain
            p_none *= (1.0 - q)
        ev += p_none * pot
        return ev

    def preflop(self, sp, obs):
        cls = PRE.cls(sp.hole[0], sp.hole[1])
        pct = PCT[cls]
        bb = sp.bb
        me_total = sp.stack + sp.bet
        eff_bb = sp.eff_bb
        to_call = sp.to_call
        raises = sp.raises
        n_beh = len(sp.behind)
        rng = self.rng

        # facing an all-in or a raise that commits us
        if raises > 0:
            raiser = sp.raiser
            r_total = self.opp_total(sp, raiser) if raiser >= 0 else 0
            raiser_allin = raiser >= 0 and sp.stacks[raiser] == 0
            commit = to_call >= 0.4 * sp.stack or raiser_allin or (raises >= 2 and eff_bb <= P_3BCOMMIT)
            # estimated raiser range
            r_bb = r_total / bb
            pfr_rate = self.rate(self.pfr, raiser, 0.15)
            if raiser_allin or (sp.bets[raiser] >= 0.5 * r_total):
                base = _interp(r_bb, SHOVE_PTS)
                w = 0.5 * base + 0.5 * min(1.0, pfr_rate * 1.1) if self.hands.get(raiser, 0) >= 8 else base
                if P_POSW and raises == 1:
                    pb = sp.position_of(raiser)
                    base = min(1.0, base * (1.8 if pb <= 1 else 1.4 if pb == 2 else 1.15 if pb == 3 else 1.0))
                if P_WIDEN:
                    w = max(w, base)
            else:
                w = min(0.6, max(0.05, pfr_rate))
            if raises >= 2:
                w *= 0.45
            w = max(0.02, min(1.0, w))
            e = eq_vs(cls, w)
            n_in = sum(1 for s in sp.opps if s != raiser and sp.bets[s] > 0 and s != obs["bb_seat"] and s != obs["sb_seat"])
            callers_in = sp.callers
            if callers_in:
                e = e ** (1.0 + 0.7 * callers_in)
            if commit or eff_bb <= 15:
                # all-in decision: call/shove vs fold
                final = sp.pot + to_call
                if not raiser_allin:
                    # we shove; raiser may fold some -- treat as call with fold equity small
                    risk = min(me_total, r_total) - sp.bet
                    final = sp.pot + risk + (min(me_total, r_total) - sp.bets[raiser])
                    need = risk / final
                else:
                    need = min(to_call, sp.stack) / final
                need += self.margin(sp, obs)
                if n_beh:
                    need += 0.02 * n_beh
                if P_RESTEAL and not raiser_allin and sp.bets[raiser] < 0.4 * r_total and raises == 1:
                    wc = max(0.02, w * P_RESTEAL)
                    pf = max(0.0, 1.0 - wc / w)
                    e_c = eq_vs(cls, wc)
                    if callers_in:
                        e_c = e_c ** (1.0 + 0.7 * callers_in)
                        pf *= 0.6 ** callers_in
                    ev = pf * sp.pot + (1.0 - pf) * (e_c * final - risk)
                    if ev > (need - risk / final) * final * (1.0 - pf):
                        return act_allin(sp)
                if e >= need:
                    if raiser_allin and to_call < 0.5 * sp.stack and not (n_beh and e >= need + 0.12):
                        return act_call(sp)
                    return act_allin(sp)
                return act_fold(sp)
            # deep: 3-bet / call / fold
            final = sp.pot + to_call
            need = to_call / final
            if e >= 0.62 and pct <= 0.05:
                target = 3 * (sp.bets[raiser]) + sp.pot - sp.bets[raiser]
                if target >= 0.4 * me_total:
                    return act_allin(sp)
                return act_raise(sp, target)
            if raises >= 2 and pct > 0.03:
                return act_fold(sp)
            if P_LIGHT3 and raises == 1 and not sp.callers and 0.05 < pct <= 0.35 and eff_bb >= 25 \
                    and rng.random() < P_LIGHT3 * min(1.5, pfr_rate / 0.15):
                return act_raise(sp, 3 * (sp.bets[raiser]) + sp.pot - sp.bets[raiser])
            implied = 0.06 if to_call <= 0.08 * me_total else 0.0
            if e + implied >= need + P_DEEPCALL and (pct <= 0.25 or sp.role == "BB"):
                return act_call(sp)
            if sp.role == "BB" and e >= need + P_BBDEF:
                return act_call(sp)
            return act_fold(sp)

        # no raise yet (blinds and maybe limps)
        if eff_bb <= P_PUSH_BB:
            ev = self.shove_ev(sp, cls, obs)
            thr = self.margin(sp, obs) * sp.pot
            if ev > thr:
                return act_allin(sp)
            if sp.can_check:
                return act_call(sp)
            return act_fold(sp)
        w = OPEN_W.get(n_beh, 0.13) * P_OPEN
        if sp.n_alive == 2:
            w = P_HUOPEN
        elif sp.n_alive == 3:
            w *= 1.4
        limpers = sp.callers
        if limpers:
            w *= 0.7
        if sp.can_check:
            # BB option
            if pct <= 0.12:
                return act_raise(sp, sp.pot + (3 + limpers) * bb)
            return act_call(sp)
        size = (2.5 if eff_bb >= 30 else 2.2) * bb + limpers * bb
        if sp.role == "SB":
            size = 3 * bb
        if pct <= w:
            return act_raise(sp, size)
        # steal vs tight players behind (reads)
        if P_STEAL and not limpers and 0 < n_beh <= 3 and pct <= 0.75:
            pf = 1.0
            for s in sp.behind:
                d = min(0.95, 1.2 * self.rate(self.vpip, s, 0.3))
                pf *= (1.0 - d)
            risk = size - sp.bet
            if pf * sp.pot > (1.0 - pf) * risk * (0.25 + pct) * P_STEAL:
                return act_raise(sp, size)
        if sp.role == "SB" and pct <= P_SBLIMP and to_call <= bb:
            return act_call(sp)
        return act_fold(sp)

    # ---------- postflop ----------
    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        n_opp = max(1, sp.n_opp)
        s_eff = s - 0.07 * (n_opp - 1)
        cards_left = 5 - len(sp.board)
        unseen = 36 - 2 - len(sp.board)
        if cards_left == 2:
            deq = 1.0 - (1.0 - outs / unseen) * (1.0 - outs / (unseen - 1))
        elif cards_left == 1:
            deq = outs / unseen
        else:
            deq = 0.0
        deq *= 0.85
        pot = sp.pot
        to_call = sp.to_call
        me_total = sp.stack + sp.bet
        rng = self.rng
        was_aggr = sp.last_aggr == sp.me
        bf = P_BLUFF
        if P_FTB and n_opp == 1:
            o = sp.opps[0]
            ff = self.ftb_f.get(o, 0)
            fc = self.ftb_c.get(o, 0)
            r = (ff + 0.4 * 4) / (ff + fc + 4)
            bf *= max(0.4, min(2.0, r / 0.4))
        if to_call == 0:
            if s_eff >= 0.85:
                return act_pot(sp, 0.75 * P_VSIZE)
            if s_eff >= 0.68:
                return act_pot(sp, 0.6 * P_VSIZE)
            if s_eff >= P_THIN and n_opp == 1:
                return act_pot(sp, 0.45 * P_VSIZE) if rng.random() < 0.7 else act_call(sp)
            if outs >= 8 and cards_left >= 1 and n_opp <= 2 and rng.random() < 0.55 * bf:
                return act_pot(sp, 0.55)
            if was_aggr and n_opp == 1 and cards_left == 2 and rng.random() < 0.6 * bf:
                return act_pot(sp, 0.4)
            if n_opp == 1 and sp.ip and cards_left >= 1 and rng.random() < 0.25 * bf:
                return act_pot(sp, 0.45)
            return act_call(sp)
        # facing a bet
        final = pot + to_call
        need = to_call / final
        bettor = -1
        for h_st, seat, a, _ in reversed(sp.hist):
            if h_st == sp.street and a == "raise":
                bettor = seat
                break
        e = s_eff
        bet_frac = to_call / max(1.0, pot - to_call)
        if P_BARREL and bettor >= 0:
            e -= P_BARREL * sum(1 for h_st, seat, a, _ in sp.hist if 0 < h_st < sp.street and seat == bettor and a == "raise")
        e = e - P_BETPEN * max(0.0, bet_frac - 0.5) - 0.04 * sp.raises - (P_RIVPEN if cards_left == 0 else 0.0)
        e = max(e, 0.0) + deq * (1.0 - max(e, 0.0))
        big = to_call >= 0.5 * sp.stack
        if s_eff >= 0.9 or (s_eff >= 0.8 and sp.raises <= 1 and not big):
            if sp.raises >= 2 and s_eff < 0.93:
                return act_call(sp)
            return act_pot(sp, 0.9)
        if big:
            need += 0.06
        if bettor >= 0 and P_READ:
            ag = self.pf_aggr.get(bettor, 0)
            ps = self.pf_pass.get(bettor, 0)
            af = (ag + 1.0) / (ag + ps + 3.0)
            vr = self.rate(self.vpip, bettor, 0.3)
            adj = 0.12 * (af - 0.33) + 0.3 * (vr - 0.3)
            e += P_READ * max(-0.08, min(0.08, adj))
        if e >= need + P_POSTCALL:
            # commit when little behind
            if sp.stack - to_call < 0.3 * (final + to_call) and e >= 0.5:
                return act_allin(sp)
            return act_call(sp)
        return act_fold(sp)
