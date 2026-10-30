"""b08 bot: table-driven preflop (equity vs estimated ranges, push/fold when
short) and heuristic postflop (made-hand strength + draws vs pot odds)."""

import json
import os
import random

from ._common import (CARD, HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, PREFLOP, Spot, Variant,
                      act_allin, act_call, act_fold, act_raise, features, safe_default)

_HERE = os.path.dirname(os.path.abspath(__file__))
PUSH_ICM = 0.95
HU_OPEN = 0.80
RAISED_ADJ = 0.10
WEAK_TURN = 0.08
WEAK_RIVER = 0.10
BARREL = 0.35
TB_PCT = 0.05
OPEN_LATE = 1.15
F_CAP = 8.0
CBET = 1.0
STAB = 0.8
LINE_ADJ = 0.05
DANGER = 0.08
FOLD_MIN = 0.35
STREET_ADJ = (0.0, 0.03, 0.10, 0.15)
ICM3 = 0.07
ICM4 = 0.10
_PRE = PREFLOP["std"]
_PCT = _PRE.pct


def _load_eqtop():
    """eqtop[c][k]: equity of class c vs the top (k+1)% of hands (by combos)."""
    try:
        with open(os.path.join(_HERE, "eqtop.json")) as f:
            return json.load(f)
    except Exception:
        return None


_EQTOP = _load_eqtop()


def eq_vs_top(c, r):
    """Equity of class c against the top fraction r of starting hands."""
    if _EQTOP is None:
        # fallback: crude from percentile
        p = _PCT[c]
        return max(0.05, min(0.95, 0.5 + 0.4 * (r - p) / max(r, p, 0.05)))
    k = int(r * 100 + 0.5) - 1
    if k < 0:
        k = 0
    elif k > 99:
        k = 99
    return _EQTOP[c][k]


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.pf_aggr = False  # we were last preflop aggressor this hand
        self.hand_id = -1
        self.bb_now = 20
        # per-seat stats within this table
        self.dealt = {}
        self.pfr = {}
        self.vp = {}
        self.big = {}
        self.agg = {}
        self.ff = {}
        self.fc = {}
        self.pas = {}

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            seen = set()
            raised = set()
            bigr = set()
            vp = set()
            bb = self.bb_now
            cur_st = -1
            bet_open = False
            for st, seat, act, amt in event.get("history", ()):
                if st != cur_st:
                    cur_st = st
                    bet_open = False
                if st > 0:
                    if bet_open and act in ("fold", "call", "raise"):
                        if act == "fold":
                            self.ff[seat] = self.ff.get(seat, 0) + 1
                        else:
                            self.fc[seat] = self.fc.get(seat, 0) + 1
                    if act == "raise":
                        bet_open = True
                if st == 0:
                    seen.add(seat)
                    if act == "call":
                        vp.add(seat)
                    if act == "raise":
                        vp.add(seat)
                        raised.add(seat)
                        if amt >= 8 * bb:
                            bigr.add(seat)
                else:
                    if act == "raise" or act == "bet":
                        self.agg[seat] = self.agg.get(seat, 0) + 1
                    elif act == "call" or act == "check":
                        self.pas[seat] = self.pas.get(seat, 0) + 1
            for seat in seen:
                self.dealt[seat] = self.dealt.get(seat, 0) + 1
            for seat in raised:
                self.pfr[seat] = self.pfr.get(seat, 0) + 1
            for seat in vp:
                self.vp[seat] = self.vp.get(seat, 0) + 1
            for seat in bigr:
                self.big[seat] = self.big.get(seat, 0) + 1
        except Exception:
            pass

    def pfr_of(self, seat):
        d = self.dealt.get(seat, 0)
        return (self.pfr.get(seat, 0) + 0.15 * 10) / (d + 10)

    def vpip_of(self, seat):
        d = self.dealt.get(seat, 0)
        return (self.vp.get(seat, 0) + 0.25 * 8) / (d + 8)

    def big_of(self, seat):
        d = self.dealt.get(seat, 0)
        return (self.big.get(seat, 0) + 0.05 * 10) / (d + 10)

    def af_of(self, seats):
        a = sum(self.agg.get(x, 0) for x in seats)
        p = sum(self.pas.get(x, 0) for x in seats)
        return (a + 1.0) / (a + p + 3.0)

    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            return safe_default(obs)

    # ------------------------------------------------------------------
    def decide(self, obs):
        if obs["phase"] == "discard":
            return safe_default(obs)
        if obs["hand_id"] != self.hand_id:
            self.hand_id = obs["hand_id"]
            self.pf_aggr = False
        sp = Spot(obs, self.var)
        self.bb_now = sp.bb
        if sp.street == 0:
            a = self.preflop(sp, obs)
            if a.get("action") == "raise":
                self.pf_aggr = True
            return a
        return self.postflop(sp, obs)

    # ------------------------------------------------------------------
    def preflop(self, sp, obs):
        h = sp.hole
        c = _PRE.cls(h[0], h[1])
        pct = _PCT[c]
        bb = sp.bb
        stack_total = sp.stack + sp.bet  # chips I have in this street + behind
        eff_bb = sp.eff_bb
        n_behind = len(sp.behind)
        to_call = sp.to_call
        pot = sp.pot
        hist = sp.hist
        # count raises / limpers preflop
        raises = 0
        limpers = 0
        last_raiser = -1
        last_raise_to = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises += 1
                limpers = 0
                last_raiser = seat
                last_raise_to = amt
            elif act == "call" and raises == 0:
                limpers += 1
        n_alive = sp.n_alive

        if raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= 13:
                # push/fold
                thr = self.push_thr(n_behind, eff_bb, n_alive)
                if limpers:
                    thr *= 0.75
                if pct <= thr:
                    return act_allin(sp)
                if to_call == 0:
                    return {"action": "check"}
                return act_fold(sp)
            open_thr = {1: 0.42, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14}.get(n_behind, 0.12)
            if n_behind <= 4:
                open_thr *= OPEN_LATE
            if n_alive == 2:
                open_thr = HU_OPEN
            elif n_alive == 3:
                open_thr *= 1.4
            elif n_alive == 4:
                open_thr *= 1.25
            if limpers:
                open_thr *= 0.6
            elif sp.behind and n_alive >= 4 and n_behind <= 3:
                v = sum(self.vpip_of(x) for x in sp.behind) / len(sp.behind)
                open_thr *= min(1.35, max(0.85, (0.25 / max(v, 0.05)) ** 0.5))
            if pct <= open_thr:
                size = (2.5 if eff_bb > 25 else 2.2) * bb + limpers * bb
                if sp.role == "SB":
                    size = 3.0 * bb
                return self.raise_to(sp, size)
            if to_call == 0:
                return {"action": "check"}
            # cheap limp/complete with speculative hands when there are limpers
            if limpers and to_call <= bb and pct <= 0.40 and eff_bb > 25:
                return act_call(sp)
            if sp.role == "SB" and to_call <= bb / 2 and pct <= 0.30 and eff_bb > 20:
                return act_call(sp)
            return act_fold(sp)

        # facing a raise
        opp_total = last_raise_to  # raise-to on this street
        # raiser's total stack at start of street ~ stack + bet
        rs = sp.stacks[last_raiser] if last_raiser >= 0 else 0
        rb = sp.bets[last_raiser] if last_raiser >= 0 else 0
        raiser_allin = rs == 0
        raiser_total_bb = (rs + rb) / bb
        # estimate raiser's range
        if raises == 1:
            if raiser_allin or opp_total >= 0.5 * (rs + rb):
                # shove: range widens as stack shrinks
                x = raiser_total_bb
                r = 0.06 if x >= 40 else 0.09 if x >= 25 else 0.14 if x >= 15 else 0.22 if x >= 10 else 0.33 if x >= 6 else 0.5
                if n_alive == 2:
                    r = 0.20 if x >= 25 else 0.30 if x >= 15 else 0.40 if x >= 10 else 0.5 if x >= 6 else 0.7
                elif n_alive == 3:
                    r = min(1.0, r * 1.6)
            else:
                r = 0.18 if opp_total <= 3 * bb else 0.13
                pos = sp.position_of(last_raiser) if hasattr(sp, "position_of") else 3
                if pos <= 2:
                    r *= 1.5
                if n_alive == 2:
                    r = 0.45 if opp_total <= 3 * bb else 0.30
                elif n_alive == 3:
                    r = max(r, 0.35)
        elif raises == 2:
            r = 0.06
            if raiser_allin and raiser_total_bb < 20:
                r = 0.10
        else:
            r = 0.035
        if last_raiser >= 0:
            if raiser_allin or opp_total >= 8 * bb:
                f = self.big_of(last_raiser) / 0.05
            else:
                f = self.pfr_of(last_raiser) / 0.15
            if n_alive <= 3:
                f = min(4.0, max(1.0, f)) ** 0.5
            else:
                f = min(F_CAP, max(0.75, f))
                f = f if f < 1.0 else f ** 0.8
            r = min(1.0, r * f)
        eq = eq_vs_top(c, r)
        # multiway: others already called
        callers = sp.callers
        if callers:
            eq = eq ** (1.0 + 0.6 * callers)
        call_amt = min(to_call, sp.stack)
        need = call_amt / (pot + call_amt)
        commit = call_amt >= 0.45 * sp.stack or sp.stack - call_amt < 8 * bb

        # strong: re-raise
        if raises == 1 and pct <= TB_PCT or raises >= 2 and pct <= 0.02 or eq >= 0.64:
            if not sp.can_raise:
                return act_call(sp)
            if eff_bb <= 30 or commit or raises >= 2:
                return act_allin(sp)
            size = 3.0 * opp_total + callers * opp_total
            if size >= 0.4 * stack_total:
                return act_allin(sp)
            return self.raise_to(sp, size)
        if commit:
            # all-in decision (with ICM risk premium)
            if eq >= need + 0.01 + self.icm_prem(sp):
                return act_allin(sp) if sp.can_raise and eq > 0.55 else act_call(sp)
            return act_fold(sp)
        # non-committing call with implied odds
        implied = 0.0
        if c // 13 == c % 13 and call_amt * 12 <= min(sp.stack, sp.eff):
            implied = 0.10  # set mining
        if sp.role == "BB" and raises == 1:
            implied += 0.03
        cap = {2: 0.70, 3: 0.45, 4: 0.38}.get(n_alive, 0.30)
        margin = 0.05 if sp.role == "BB" and raises == 1 else 0.10
        if eq + implied >= need + margin and pct <= cap:
            return act_call(sp)
        return act_fold(sp)

    def push_thr(self, n_behind, eff_bb, n_alive):
        base = {1: 0.60, 2: 0.42, 3: 0.32, 4: 0.25, 5: 0.20, 6: 0.17}.get(n_behind, 0.14)
        f = (10.0 / max(eff_bb, 1.0)) ** 0.6
        if n_alive >= 4:
            f *= PUSH_ICM
        return min(0.95, base * f)

    def icm_prem(self, sp):
        n = sp.n_alive
        if n <= 2:
            return 0.0
        base = ICM3 if n == 3 else ICM4
        my = sp.stack + sp.bet
        frac = min(1.0, sp.eff / max(my, 1))
        return base * (0.2 + 0.8 * frac)

    def raise_to(self, sp, total):
        if not sp.can_raise:
            return act_call(sp)
        total = int(total)
        # if raise would commit most of stack, shove
        if total >= 0.55 * (sp.stack + sp.bet):
            return act_allin(sp)
        return act_raise(sp, total)

    # ------------------------------------------------------------------
    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        if cat <= TWO_PAIR and len(sp.board) >= 4:
            bm = 0
            bsu = [0, 0, 0, 0]
            for c in sp.board:
                bm |= 1 << (c >> 2)
                bsu[c & 3] += 1
            m = (bm << 1) | ((bm >> 12) & 1)  # bit 0 = ace low
            if max(bsu) >= 4 or any((m >> lo & 0x1F).bit_count() >= 4 for lo in range(10)):
                s -= DANGER
        n_opp = sp.n_opp
        pot = sp.pot
        to_call = sp.to_call
        stack = sp.stack
        street = sp.street
        cards_to_come = 3 - street  # flop:2, turn:1, river:0
        # multiway discount
        if n_opp > 1:
            s = s ** (1.0 + 0.45 * (n_opp - 1))
        draw_eq = 0.0
        if cards_to_come > 0 and outs:
            draw_eq = min(0.45, outs * (0.04 if cards_to_come == 2 else 0.021))
        eq = max(s, draw_eq) + 0.3 * min(s, draw_eq)
        rng = self.rng
        bb = sp.bb
        spr = stack / max(pot, 1)

        if to_call == 0:
            if not sp.can_raise:
                return {"action": "check"}
            if s >= 0.80:
                return self.bet_frac(sp, 0.75)
            if s >= 0.62 and n_opp <= 2:
                return self.bet_frac(sp, 0.6)
            if s >= 0.52 and n_opp == 1 and street < 3:
                return self.bet_frac(sp, 0.5)
            if draw_eq >= 0.25 and n_opp <= 2 and rng.random() < 0.6:
                return self.bet_frac(sp, 0.6)
            if n_opp == 1 and s < 0.45 and draw_eq < 0.15:
                o = sp.opps[0]
                f_, c_ = self.ff.get(o, 0), self.fc.get(o, 0)
                if (f_ + 3.0) / (f_ + c_ + 6.0) < FOLD_MIN:
                    return {"action": "check"}  # sticky opponent: no pure bluffs
            if street == 2 and n_opp == 1 and s < 0.5 and rng.random() < BARREL:
                me = sp.me
                if any(h[0] == 1 and h[1] == me and h[2] == "raise" for h in sp.hist):
                    return self.bet_frac(sp, 0.5)
            if self.pf_aggr and street == 1 and n_opp == 1 and rng.random() < CBET:
                return self.bet_frac(sp, 0.45)
            if not self.pf_aggr and street == 1 and n_opp == 1 and sp.ip and rng.random() < STAB:
                return self.bet_frac(sp, 0.5)
            if self.pf_aggr and street == 1 and n_opp == 2 and s >= 0.3 and rng.random() < 0.4:
                return self.bet_frac(sp, 0.5)
            return {"action": "check"}

        # facing a bet
        call_amt = min(to_call, stack)
        need = call_amt / (pot + call_amt)
        if call_amt >= 0.4 * stack or stack - call_amt < 0.3 * pot:
            need += self.icm_prem(sp)
        bet_ratio = to_call / max(pot - to_call, 1)
        # opponents' bets are stronger than random: discount by size
        adj = STREET_ADJ[street] + 0.06 * min(bet_ratio, 2.0)
        if sp.bet > 0:
            adj += RAISED_ADJ  # raised over our own bet
        # the bettor's line: bets on earlier postflop streets, preflop 3-bet
        bettor = -1
        pre_raises = 0
        pre_last = -1
        for h in sp.hist:
            if h[2] == "raise":
                if h[0] == street:
                    bettor = h[1]
                elif h[0] == 0:
                    pre_raises += 1
                    pre_last = h[1]
        if bettor >= 0:
            prior = 0
            seen_st = set()
            for h in sp.hist:
                if 0 < h[0] < street and h[1] == bettor and h[2] == "raise" and h[0] not in seen_st:
                    seen_st.add(h[0])
                    prior += 1
            adj += LINE_ADJ * prior
            if pre_raises >= 2 and pre_last == bettor:
                adj += LINE_ADJ
        af = self.af_of(sp.opps)
        adj *= min(1.3, max(0.2, (0.65 - af) / 0.32))
        eq_eff = eq - adj
        if street == 2 and s < 0.45 and draw_eq < 0.15:
            eq_eff -= WEAK_TURN
        elif street == 3 and s < 0.48:
            eq_eff -= WEAK_RIVER
        if s >= 0.88 or (s >= 0.80 and n_opp == 1):
            if sp.can_raise:
                if spr < 3 or s >= 0.93:
                    return act_allin(sp)
                total = sp.bet + to_call + 1.0 * (pot + to_call)
                return self.raise_to(sp, total)
            return act_call(sp)
        if eq_eff >= need:
            # semi-bluff raise occasionally with big draws
            if draw_eq >= 0.30 and sp.can_raise and n_opp == 1 and rng.random() < 0.25 and street == 1:
                return act_allin(sp) if spr < 2.5 else self.raise_to(sp, sp.bet + to_call + (pot + to_call))
            return act_call(sp)
        return act_fold(sp)

    def bet_frac(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * target):
            return act_allin(sp)
        target = max(target, sp.min_to)
        return act_raise(sp, target)
