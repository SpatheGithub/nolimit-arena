"""b06: tight-aggressive baseline driven by in-table opponent modeling.

Per anonymous seat (this table only) we count VPIP, PFR, folds to preflop
raises, postflop aggression and folds to postflop bets. Those estimates
(shrunk to priors) set the range we assume behind a raise, the equity we
need to call, how wide we steal / shove and how often we c-bet or bluff.
"""

import json
import os
import random

from .common import (CARD, FLUSH, HIGH, PAIR, PREFLOP, STRAIGHT, TRIPS, TWO_PAIR, Spot, Variant,
                     features, safe_default)

_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_HERE, "eqrange.json")) as _f:
        _D = json.load(_f)
    BUCKETS = tuple(_D["buckets"])
    EQR = tuple(tuple(r) for r in _D["eq"])
except Exception:  # pragma: no cover
    BUCKETS = None
    EQR = None

PRE = PREFLOP["std"]

# stat slots
HANDS, VPIP, PFR, FR_OPP, FR_FOLD, P_AGG, P_CALL, P_CHECK, FB_OPP, FB_FOLD, SD_AGG, SD_WEAK = range(12)

OPEN_TH = {1: 0.55, 2: 0.40, 3: 0.30, 4: 0.24, 5: 0.19, 6: 0.16, 7: 0.14}
PUSH_TH = {1: 0.62, 2: 0.42, 3: 0.33, 4: 0.27, 5: 0.22, 6: 0.18, 7: 0.15}
OPEN_SCALE = 0.75
ICM_K = 0.012
DEF_PCT = 0.5
PUSH_SCALE = 1.0
PUSH_BB = 13
RERAISE_EQ = 0.60
TIGHT_K = 0.4
BARREL_K = 0.03
DECAY = 1.0
PUSH_EV = 1
PUSH_EV_MARGIN = 0.05
STEAL_PF = 0.72
RESTEAL = 1
RESTEAL_BB = 30
RESTEAL_MARGIN = 0.05
SQUEEZE_MAX = 0
CALL_BASE = 0.22
VTH_BASE = 0.62
ADJ_CAP = 0.2
ADJ_MULT = 1.0
FLOOR_HU = 0.0
FLOOR_3 = 0.0
LIMP_EV = 0
SHOVE3_K = 0.4
CBET_FRAC = 0.5
STACKOFF = 0.66
STACKOFF_FRAC = 0.35
STACKOFF_N = 5


def eq_vs_range(cls, p):
    """All-in equity of hand class vs a random hand from the top-p range."""
    if EQR is None:
        return PRE.multi(cls, 1) * (0.75 + 0.25 * min(1.0, p))
    row = EQR[cls]
    b = BUCKETS
    if p <= b[0]:
        return row[0]
    for i in range(1, len(b)):
        if p <= b[i]:
            t = (p - b[i - 1]) / (b[i] - b[i - 1])
            return row[i - 1] + t * (row[i] - row[i - 1])
    return row[-1]


class Agent:
    def __init__(self, config):
        self.seat = config.get("seat", 0)
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.n = config.get("seats", 8)
        self.st = {}

    # ---------------------------------------------------------------- stats
    def s(self, seat):
        st = self.st.get(seat)
        if st is None:
            st = self.st[seat] = [0] * 12
        return st

    def vpip(self, seat):
        st = self.s(seat)
        return (st[VPIP] + 0.28 * 8) / (st[HANDS] + 8)

    def pfr(self, seat):
        st = self.s(seat)
        return (st[PFR] + 0.16 * 8) / (st[HANDS] + 8)

    def fold_to_raise(self, seat):
        st = self.s(seat)
        return (st[FR_FOLD] + 0.6 * 6) / (st[FR_OPP] + 6)

    def agg(self, seat):
        st = self.s(seat)
        n = st[P_AGG] + st[P_CALL] + st[P_CHECK]
        return (st[P_AGG] + 0.35 * 8) / (n + 8)

    def fold_to_bet(self, seat):
        st = self.s(seat)
        return (st[FB_FOLD] + 0.45 * 6) / (st[FB_OPP] + 6)

    def bluffiness(self, seat):
        st = self.s(seat)
        return (st[SD_WEAK] + 0.25 * 3) / (st[SD_AGG] + 3)

    def observe(self, ev):
        try:
            if ev.get("type") != "hand_end":
                return
            hist = ev.get("history") or []
            me = self.seat
            if DECAY < 1.0:
                for st in self.st.values():
                    for i in range(12):
                        st[i] *= DECAY
            seen = set()
            vp = set()
            pr = set()
            raised = False
            for h in hist:
                stt, seat, act = h[0], h[1], h[2]
                if stt != 0:
                    continue
                seen.add(seat)
                if seat == me or act in ("ante", "sb", "bb", "return"):
                    if act == "raise":
                        raised = True
                    continue
                st = self.s(seat)
                if act == "fold":
                    if raised:
                        st[FR_OPP] += 1
                        st[FR_FOLD] += 1
                elif act == "call":
                    vp.add(seat)
                    if raised:
                        st[FR_OPP] += 1
                elif act == "raise":
                    vp.add(seat)
                    pr.add(seat)
                    if raised:
                        st[FR_OPP] += 1
                    raised = True
            for seat in seen:
                if seat == me:
                    continue
                st = self.s(seat)
                st[HANDS] += 1
                if seat in vp:
                    st[VPIP] += 1
                if seat in pr:
                    st[PFR] += 1
            cur = -1
            bet_out = False
            aggr_seats = set()
            for h in hist:
                stt, seat, act = h[0], h[1], h[2]
                if stt == 0:
                    continue
                if stt != cur:
                    cur = stt
                    bet_out = False
                if act == "raise":
                    if seat != me:
                        st = self.s(seat)
                        st[P_AGG] += 1
                        if bet_out:
                            st[FB_OPP] += 1
                        if stt >= 2:
                            aggr_seats.add(seat)
                    bet_out = True
                elif seat == me:
                    continue
                elif act == "call":
                    st = self.s(seat)
                    st[P_CALL] += 1
                    st[FB_OPP] += 1
                elif act == "fold":
                    st = self.s(seat)
                    st[FB_OPP] += 1
                    st[FB_FOLD] += 1
                elif act == "check":
                    self.s(seat)[P_CHECK] += 1
            shown = ev.get("shown") or {}
            board = [CARD[c] for c in (ev.get("board") or [])]
            if len(board) == 5:
                for seat, cards in shown.items():
                    try:
                        seat = int(seat)
                    except Exception:
                        continue
                    if seat == me or seat not in aggr_seats:
                        continue
                    hole = [CARD[c] for c in cards]
                    sv, _, _, _ = features(self.var, hole, board)
                    st = self.s(seat)
                    st[SD_AGG] += 1
                    if sv < 0.45:
                        st[SD_WEAK] += 1
        except Exception:
            pass

    # ---------------------------------------------------------------- acting
    def act(self, obs):
        try:
            if obs.get("phase") == "discard":
                return safe_default(obs)
            sp = Spot(obs, self.var)
            if sp.street == 0:
                return self.preflop(sp, obs)
            return self.postflop(sp, obs)
        except Exception:
            return safe_default(obs)

    # helpers
    def fold(self, sp):
        return {"action": "check"} if sp.can_check else {"action": "fold"}

    def call(self, sp):
        return {"action": "check"} if sp.to_call == 0 else {"action": "call"}

    def raise_to(self, sp, amount):
        if not sp.can_raise:
            return self.call(sp)
        a = int(amount)
        # if the raise leaves little behind, just shove
        if a >= 0.7 * (sp.stack + sp.bet):
            a = sp.max_to
        if a < sp.min_to:
            a = sp.min_to
        if a > sp.max_to:
            a = sp.max_to
        return {"action": "raise", "amount": a}

    def allin(self, sp):
        if sp.can_raise:
            return {"action": "raise", "amount": sp.max_to}
        return self.call(sp)

    def bet_pot(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            target = sp.max_to
        return self.raise_to(sp, target)

    # ---------------------------------------------------------------- preflop
    def preflop(self, sp, obs):
        h = sp.hole
        cls = PRE.cls(h[0], h[1])
        pct = PRE.pct[cls]
        bb = sp.bb
        my_total = sp.stack + sp.bet
        eff = max(sp.eff, 1)
        eff_bb = eff / bb
        behind = sp.behind
        nb = max(1, min(7, len(behind)))
        rng = self.rng.random()

        if sp.raises == 0:
            limpers = sp.callers
            if sp.can_check:
                # big blind option vs limpers
                th = 0.10 if limpers <= 1 else 0.07
                if pct <= th:
                    if eff_bb <= 15:
                        return self.allin(sp)
                    return self.raise_to(sp, (3.5 + limpers) * bb)
                return self.call(sp)
            # fold tendency of players behind
            if behind:
                f = sum(self.fold_to_raise(s) for s in behind) / len(behind)
            else:
                f = 0.6
            fadj = 0.55 + 0.75 * f  # f=0.6 -> 1.0
            # probability everyone behind folds to a raise
            p_f = 1.0
            for s_ in behind:
                p_f *= self.fold_to_raise(s_)
            if eff_bb <= PUSH_BB:
                th = PUSH_TH[nb] * (10.0 / max(eff_bb, 3.0)) ** 0.5 * fadj * PUSH_SCALE
                if limpers:
                    th *= 0.6
                if pct <= min(th, 1.0):
                    return self.allin(sp)
                if PUSH_EV and behind and (not limpers or LIMP_EV):
                    # model-based shove EV from observed fold rates of players behind (and limpers)
                    pf = 1.0
                    fs = []
                    others = list(behind)
                    if limpers:
                        others += [s_ for s_ in sp.opps if s_ not in behind and sp.stacks[s_] > 0]
                    for s_ in others:
                        fsh = min(0.97, self.fold_to_raise(s_) + 0.05)
                        pf *= fsh
                        fs.append(fsh)
                    p_call = 1.0 - sum(fs) / len(fs)
                    eqc = eq_vs_range(cls, max(0.03, p_call))
                    risk = eff - sp.bet
                    ev = pf * sp.pot + (1.0 - pf) * (eqc * (sp.pot + 2 * risk) - risk)
                    if ev > PUSH_EV_MARGIN * risk:
                        return self.allin(sp)
                return self.fold(sp)
            th = OPEN_TH[nb] * fadj * OPEN_SCALE
            if STEAL_PF and p_f >= STEAL_PF and behind:
                th = max(th, 0.9)
            if limpers:
                th *= 0.6
            if pct <= th:
                size = (2.5 if eff_bb > 25 else 2.2) + limpers
                if sp.role == "SB":
                    size += 0.5
                return self.raise_to(sp, size * bb)
            # cheap completes / limps with speculative hands
            if sp.role == "SB" and sp.to_call <= bb / 2 and pct <= 0.55 and limpers == 0 and eff_bb > 20:
                return self.call(sp)
            if limpers and sp.to_call <= bb and pct <= 0.30 and eff_bb > 30:
                return self.call(sp)
            return self.fold(sp)

        # facing a raise
        raiser = sp.raiser
        p_r = self.pfr(raiser) if raiser >= 0 else 0.15
        r_stack = (sp.stacks[raiser] + sp.bets[raiser]) if raiser >= 0 else eff
        r_bb = r_stack / bb
        if r_bb <= 10:
            p_r *= 2.0
        elif r_bb <= 20:
            p_r *= 1.5
        if sp.raises == 1 and r_bb <= 20:
            if sp.n_alive == 2:
                p_r = max(p_r, FLOOR_HU)
            elif sp.n_alive == 3:
                p_r = max(p_r, FLOOR_3)
        if sp.raises >= 2:
            p_r *= SHOVE3_K if (r_bb <= 25 and raiser >= 0 and sp.stacks[raiser] == 0) else 0.4
        if sp.raises >= 3:
            p_r *= 0.6
        p_r = max(0.025, min(0.9, p_r))
        eq = eq_vs_range(cls, p_r)
        # other players involved (callers / extra raisers)
        extra = max(0, min(sp.callers, 3))
        eq_eff = eq * (0.82 ** extra) if extra else eq

        to_call = min(sp.to_call, sp.stack)
        pot = sp.pot
        cur_max = max(sp.bets)
        # how much the rest of the hand costs if it goes all-in
        risk = eff - sp.bet
        committed = cur_max >= 0.4 * eff or to_call >= 0.35 * my_total or eff_bb <= 15
        raiser_allin = raiser >= 0 and sp.stacks[raiser] == 0
        margin = 0.01
        if risk > 0.5 * my_total:
            # ICM-ish risk premium: losing busts/cripples us; worse with many players left
            covered = r_stack < my_total
            margin = 0.02 + ICM_K * (sp.n_alive - 2) * (0.4 if covered else 1.0)

        # value re-raise
        if eq_eff >= RERAISE_EQ and sp.can_raise and not raiser_allin:
            if eff_bb <= 35 or sp.raises >= 2 or cur_max >= 0.25 * eff:
                return self.allin(sp)
            mult = 3.0 if sp.ip else 3.6
            return self.raise_to(sp, mult * cur_max + sp.callers * cur_max)

        # re-steal shove over an open, priced from the opener's observed fold rate
        if (RESTEAL and sp.raises == 1 and sp.callers <= SQUEEZE_MAX and sp.can_raise and not raiser_allin
                and raiser >= 0 and 8 <= eff_bb <= RESTEAL_BB and cur_max <= 0.3 * eff):
            fr = max(0.05, min(0.9, self.fold_to_raise(raiser) - 0.1))
            pf = fr
            for s_ in behind:
                pf *= min(0.97, self.fold_to_raise(s_) + 0.05)
            if sp.callers:
                for s_ in sp.opps:
                    if s_ != raiser and s_ not in behind and sp.stacks[s_] > 0:
                        pf *= min(0.97, self.fold_to_raise(s_) + 0.1)
            p_call = max(0.02, p_r * (1.0 - fr))
            eqc = eq_vs_range(cls, p_call)
            call_amt = max(0, eff - sp.bets[raiser])
            ev = pf * pot + (1.0 - pf) * (eqc * (pot + risk + call_amt) - risk)
            if ev > RESTEAL_MARGIN * risk:
                return self.allin(sp)

        if committed:
            # treat as an all-in decision
            final_pot = pot + risk + max(0, eff - (sp.bets[raiser] if raiser >= 0 else cur_max))
            need = risk / max(final_pot, 1)
            if raiser_allin or to_call >= sp.stack:
                need = to_call / max(pot + to_call, 1)
            if eq_eff >= need + margin:
                if sp.can_raise and not raiser_allin and eq_eff >= 0.5:
                    return self.allin(sp)
                return self.call(sp)
            return self.fold(sp)

        # light 3-bet bluff vs frequent folders when deep
        if (sp.raises == 1 and sp.can_raise and eff_bb > 40 and sp.callers == 0
                and 0.08 < pct <= 0.25 and self.fold_to_raise(raiser) > 0.6 and rng < 0.25):
            return self.raise_to(sp, (3.0 if sp.ip else 3.6) * cur_max)

        need = to_call / max(pot + to_call, 1)
        realize = 0.92 if sp.ip else 0.80
        implied = 0.0
        r1, r2 = h[0] >> 2, h[1] >> 2
        suited = (h[0] & 3) == (h[1] & 3)
        if eff_bb > 40 and to_call <= eff / 15:
            if r1 == r2:
                implied = 0.07
            elif suited and abs(r1 - r2) <= 2:
                implied = 0.04
        if eq_eff * realize + implied >= need + 0.02 and pct <= DEF_PCT:
            return self.call(sp)
        return self.fold(sp)

    # ---------------------------------------------------------------- postflop
    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        me = sp.me
        st = sp.street
        river = sp.last_street
        n_opp = max(1, sp.n_opp)
        pot = sp.pot
        rng = self.rng.random()
        opps = sp.opps
        my_total = sp.stack + sp.bet
        spr = sp.stack / max(pot, 1)

        if sp.to_call == 0:
            # value
            stations = sum(1 for o in opps if self.fold_to_bet(o) < 0.35) if opps else 0
            vth = VTH_BASE if n_opp == 1 else VTH_BASE + 0.08
            if stations:
                vth -= 0.05
            if s >= vth:
                if s >= 0.9 and rng < 0.15 and not river and spr > 1.5:
                    return self.call(sp)  # occasional slowplay of monsters
                frac = 0.75 if (wet or stations) else 0.6
                return self.bet_pot(sp, frac)
            if s >= 0.55 and n_opp <= 2 and not river and rng < 0.5:
                return self.bet_pot(sp, 0.5)
            if not river and outs >= 8 and n_opp <= 2 and rng < 0.55:
                return self.bet_pot(sp, 0.6)
            fold_p = 1.0
            for o in opps:
                fold_p *= self.fold_to_bet(o)
            aggressor = sp.last_aggr == me
            if aggressor and st == 1 and n_opp <= 2:
                p = max(0.2, min(0.9, (fold_p - 0.15) * 2.0))
                if rng < p:
                    return self.bet_pot(sp, CBET_FRAC)
            elif n_opp == 1 and sp.ip and fold_p > 0.45 and rng < (fold_p - 0.3):
                return self.bet_pot(sp, 0.55)
            return self.call(sp)

        # facing a bet
        to_call = min(sp.to_call, sp.stack)
        bettor = sp.raiser if sp.raiser >= 0 else (opps[0] if opps else -1)
        a = self.agg(bettor) if bettor >= 0 else 0.35
        bl = self.bluffiness(bettor) if bettor >= 0 else 0.25
        vp = self.vpip(bettor) if bettor >= 0 else 0.28
        adj = (a - 0.35) * 0.45 + (bl - 0.25) * 0.4 + (vp - 0.28) * TIGHT_K
        # sustained aggression across streets means a stronger range
        barrels = len({h[0] for h in sp.hist if h[1] == bettor and h[2] == "raise" and 0 < h[0] < st})
        adj -= BARREL_K * barrels
        adj = max(-0.18, min(ADJ_CAP, adj * ADJ_MULT if adj > 0 else adj))
        pot_odds = to_call / max(pot + to_call, 1)
        hs = s + adj - 0.05 * (n_opp - 1)
        # facing a raise of our own bet: stronger range
        if sp.raises >= 2:
            hs -= 0.08
        draw = 0.0
        if not river and outs:
            draw = outs * (0.036 if st == 1 else 0.021)
            if to_call >= sp.stack:  # all-in: we see all remaining cards
                draw = outs * (0.04 if st == 1 else 0.022)
        # value raise
        rth = 0.86 if sp.raises <= 1 else 0.93
        if s >= rth and sp.can_raise:
            if spr < 3 or sp.raises >= 2:
                return self.allin(sp)
            return self.raise_to(sp, sp.to_call + sp.bet + 0.9 * (pot + sp.to_call) + sp.bet)
        threshold = CALL_BASE + 0.95 * pot_odds
        if to_call >= 0.5 * my_total:
            threshold += 0.03
        if STACKOFF and to_call >= STACKOFF_FRAC * my_total and sp.n_alive >= STACKOFF_N:
            # early/mid game: don't stack off light, busting early costs the most places
            threshold = max(threshold, STACKOFF)
        if hs + draw >= threshold:
            return self.call(sp)
        # semi-bluff raise with big draws vs folders
        if (not river and outs >= 12 and sp.can_raise and sp.raises == 1 and n_opp == 1
                and self.fold_to_bet(bettor) > 0.45 and rng < 0.4):
            return self.allin(sp) if spr < 3 else self.raise_to(sp, 3 * (sp.bet + sp.to_call))
        return self.fold(sp)
