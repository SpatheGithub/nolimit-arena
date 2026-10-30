"""b04: aggressive-pressure NLHE sit-and-go bot.

Preflop: position-aware steal/open ranges, push/fold when short, calls of
raises/all-ins by equity vs an estimated range (precomputed table eqr.json).
Postflop: heuristic hand strength (features()) with c-bets, barrels,
value bets, semi-bluffs and pot-odds calls.
"""

import json
import os
import random

from ._common import (CARD, FLUSH, HIGH, PAIR, PREFLOP, STRAIGHT, TRIPS, TWO_PAIR, Spot, Variant,
                      features)

_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_DIR, "eqr.json")) as _f:
        _EQR = json.load(_f)
    _R = _EQR["R"]
    _EQ = _EQR["eq"]
except Exception:  # pragma: no cover
    _R = None
    _EQ = None

try:
    with open(os.path.join(_DIR, "icm.json")) as _f:
        _ICMD = json.load(_f)
    _ICMK = _ICMD["K"]
    _ICM = {int(k): v for k, v in _ICMD["tab"].items()}
except Exception:  # pragma: no cover
    _ICM = None
    _ICMK = 200

_PRE = PREFLOP["std"]


def icm_me(st, pay):
    """Exact Malmuth-Harville ICM points of player st[0] (all stacks > 0)."""
    n = len(st)
    memo = {}

    def rec(mask, k):
        e = memo.get(mask)
        if e is not None:
            return e
        tot = 0.0
        for i in range(n):
            if mask >> i & 1:
                tot += st[i]
        e = st[0] / tot * (pay[k] if k < len(pay) else 0.0)
        for j in range(1, n):
            if mask >> j & 1:
                e += st[j] / tot * rec(mask & ~(1 << j), k + 1)
        memo[mask] = e
        return e

    return rec((1 << n) - 1, 0)


_PTS = [100, 60, 40, 25, 15, 10, 5, 0]


def lin_e(n, f):
    n = max(1, min(8, n))
    last = _PTS[n - 1]
    return last + f * (sum(_PTS[:n]) - n * last)


def icm_e(n, f):
    """Blend of ICM points (others equal) and chip-linear points."""
    if ICM_W >= 1.0:
        return icm_e0(n, f)
    return ICM_W * icm_e0(n, f) + (1 - ICM_W) * lin_e(n, f)


def icm_e0(n, f):
    """ICM points of a stack holding fraction f of all chips with n players left (others equal)."""
    if n <= 1:
        return 100.0
    if _ICM is None:
        return f * 100.0
    row = _ICM[min(n, 8)]
    x = max(0.0, min(1.0, f)) * _ICMK
    i = int(x)
    if i >= _ICMK:
        return row[_ICMK]
    t = x - i
    return row[i] * (1 - t) + row[i + 1] * t
_DEBUG = os.path.exists(os.path.join(_DIR, "DEBUG"))

RESTEAL = 0.0  # min ICM-point EV to re-shove over an open
STAB = 0.25
PUSH_CAP = 1.6
DEEP_OPEN = 0.7   # open-range multiplier when deep (eff > 40bb) from early/mid position
RIVER_BLUFF = 0.2
ICM_W = 0.8       # weight of ICM vs chip-linear points in all-in decisions
# open (raise-first-in) fraction by number of players still to act behind
OPEN = {0: 1.0, 1: 0.62, 2: 0.48, 3: 0.34, 4: 0.26, 5: 0.21, 6: 0.17, 7: 0.15}
# push fraction at 10bb by players behind
PUSH = {0: 1.0, 1: 0.62, 2: 0.42, 3: 0.32, 4: 0.26, 5: 0.22, 6: 0.19, 7: 0.17}


def eq_vs_range(c, r):
    """Heads-up all-in equity of class c vs top-r fraction of hands."""
    if _EQ is None:
        p = _PRE.pct[c]
        return max(0.2, min(0.85, 0.5 + (r - p) * 0.4))
    R = _R
    row = _EQ[c]
    if r <= R[0]:
        return row[0]
    for i in range(1, len(R)):
        if r <= R[i]:
            t = (r - R[i - 1]) / (R[i] - R[i - 1])
            return row[i - 1] * (1 - t) + row[i] * t
    return row[-1]


class Agent:
    def __init__(self, config):
        self.seat = config.get("seat")
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        self.hand_id = None
        self.pf_aggr = False      # I made the last preflop raise
        self.bet_streets = set()  # streets on which I bet/raised this hand
        # opponent model (this table only)
        self.open_opp = {}
        self.opens = {}
        self.face_opp = {}
        self.face_fold = {}
        self.face_raise = {}
        self.post_aggr = {}
        self.post_pass = {}
        self.pfold = {}
        self.pcont = {}
        self.sh_open = {}   # weakest shown hand percentile per action type
        self.sh_3b = {}
        self.sh_call = {}

    # ------------------------------------------------------------------
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if _DEBUG:
                import traceback
                print("ERR", traceback.format_exc().replace("\n", " | ")[-600:])
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            self._learn(event.get("history") or [])
            self._learn_shown(event.get("history") or [], event.get("shown") or {})
        except Exception:
            pass

    def _learn_shown(self, hist, shown):
        if not shown:
            return
        kinds = {}
        raised = 0
        for st, seat, act, amt in hist:
            if st != 0 or act in ("ante", "sb", "bb", "return"):
                continue
            if act == "raise":
                k = "open" if raised == 0 else "3b"
                raised += 1
            elif act == "call" and raised >= 1:
                k = "call"
            else:
                continue
            kinds.setdefault(seat, set()).add(k)
        for seat, cards in shown.items():
            try:
                seat_i = int(seat)
            except Exception:
                continue
            ks = kinds.get(seat_i) or kinds.get(seat)
            if not ks or not cards or len(cards) != 2:
                continue
            c1, c2 = CARD[cards[0]], CARD[cards[1]]
            pct = _PRE.pct[_PRE.cls(c1, c2)]
            for k, d in (("open", self.sh_open), ("3b", self.sh_3b), ("call", self.sh_call)):
                if k in ks:
                    t = d.get(seat_i)
                    d[seat_i] = (t[0] + pct, t[1] + 1) if t else (pct, 1)

    @staticmethod
    def _shown_width(d, seat):
        t = d.get(seat)
        if not t:
            return 0.0
        tot, n = t
        if n == 1:
            return 0.6 * tot
        return min(1.0, 1.7 * tot / n)

    def _learn(self, hist):
        raised = 0
        oo, op, fo, ff, fr = self.open_opp, self.opens, self.face_opp, self.face_fold, self.face_raise
        pa, pp = self.post_aggr, self.post_pass
        pfo, pco = self.pfold, self.pcont
        cur_st = -1
        bet_on = False
        for st, seat, act, amt in hist:
            if act in ("ante", "sb", "bb", "return"):
                continue
            if st != 0:
                if st != cur_st:
                    cur_st = st
                    bet_on = False
                if bet_on:
                    if act == "fold":
                        pfo[seat] = pfo.get(seat, 0) + 1
                    elif act in ("call", "raise"):
                        pco[seat] = pco.get(seat, 0) + 1
                if act in ("bet", "raise"):
                    pa[seat] = pa.get(seat, 0) + 1
                    bet_on = True
                elif act in ("call", "check"):
                    pp[seat] = pp.get(seat, 0) + 1
                continue
            if raised == 0:
                oo[seat] = oo.get(seat, 0) + 1
                if act == "raise":
                    op[seat] = op.get(seat, 0) + 1
            else:
                fo[seat] = fo.get(seat, 0) + 1
                if act == "fold":
                    ff[seat] = ff.get(seat, 0) + 1
                elif act == "raise":
                    fr[seat] = fr.get(seat, 0) + 1
            if act == "raise":
                raised += 1

    def open_rate(self, seat):
        return (self.opens.get(seat, 0) + 0.2 * 8) / (self.open_opp.get(seat, 0) + 8)

    def fold_rate(self, seat):
        return (self.face_fold.get(seat, 0) + 0.6 * 6) / (self.face_opp.get(seat, 0) + 6)

    def reraise_rate(self, seat):
        return (self.face_raise.get(seat, 0) + 0.08 * 8) / (self.face_opp.get(seat, 0) + 8)

    def post_fold(self, seat):
        f = self.pfold.get(seat, 0)
        return (f + 0.45 * 8) / (f + self.pcont.get(seat, 0) + 8)

    def aggr_rate(self, seat):
        a = self.post_aggr.get(seat, 0)
        return (a + 0.3 * 10) / (a + self.post_pass.get(seat, 0) + 10)

    # ------------------------------------------------------------------
    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs["n_discard"]])}
        if obs["hand_id"] != self.hand_id:
            self.hand_id = obs["hand_id"]
            self.pf_aggr = False
            self.bet_streets = set()
        sp = Spot(obs, self.var)
        self.T = max(1, sum(obs["stacks"]) + obs["pot"])
        self.n = len(obs["alive"])
        if sp.street == 0:
            a = self.preflop(sp, obs)
        else:
            a = self.postflop(sp, obs)
        if a["action"] == "raise":
            self.bet_streets.add(sp.street)
            if sp.street == 0:
                self.pf_aggr = True
        return a

    # ---------------- action helpers (always legal) -------------------
    def fold(self, sp):
        return {"action": "check"} if sp.can_check else {"action": "fold"}

    def call(self, sp):
        return {"action": "check"} if sp.to_call == 0 else {"action": "call"}

    def raise_to(self, sp, amount):
        if not sp.can_raise:
            return self.call(sp)
        a = int(amount)
        if a < sp.min_to:
            a = sp.min_to
        if a > sp.max_to:
            a = sp.max_to
        # if the raise leaves us with little behind, just shove
        left = sp.stack + sp.bet - a
        if left < 0.3 * (sp.pot + 2 * (a - sp.bet)) or left < 2 * sp.bb:
            a = sp.max_to
        return {"action": "raise", "amount": a}

    def allin(self, sp):
        if sp.can_raise:
            return {"action": "raise", "amount": sp.max_to}
        return self.call(sp)

    def bet_pot(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        return self.raise_to(sp, target)

    def _icm_of(self, sp, my_s, villain, v_s):
        if my_s <= 0:
            return float(self.points[self.n - 1]) if self.n - 1 < len(self.points) else 0.0
        lst = [my_s]
        stacks = sp.stacks
        me = sp.me
        for x in sp.obs["alive"]:
            if x == me:
                continue
            st = v_s if x == villain else stacks[x]
            if st > 0:
                lst.append(st)
        if len(lst) <= 4:
            v = icm_me(lst, self.points)
            if ICM_W >= 1.0:
                return v
            return ICM_W * v + (1 - ICM_W) * lin_e(len(lst), my_s / self.T)
        return icm_e(len(lst), my_s / self.T)

    def ev_allin(self, sp, eq, my_add, final_pot, villain_busts, pf=0.0, villain=None):
        """ICM points gained by going/calling all-in vs folding now."""
        T, n = self.T, self.n
        s0 = sp.stack
        if villain is not None and villain >= 0 and n <= 5:
            vs = sp.stacks[villain]
            their_add = max(0, final_pot - sp.pot - my_add)
            ev_fold = self._icm_of(sp, s0, villain, vs + sp.pot)
            ev_win = self._icm_of(sp, s0 - my_add + final_pot, villain, max(0, vs - their_add))
            ev_lose = self._icm_of(sp, max(0, s0 - my_add), villain, vs - their_add + final_pot)
            ev = (1 - pf) * (eq * ev_win + (1 - eq) * ev_lose)
            if pf > 0:
                ev += pf * self._icm_of(sp, s0 + sp.pot, villain, vs)
            return ev - ev_fold
        ev_fold = icm_e(n, s0 / T)
        ev_win = icm_e(n - 1 if villain_busts else n, (s0 - my_add + final_pot) / T)
        ev_lose = icm_e(n, max(0, s0 - my_add) / T)
        ev = (1 - pf) * (eq * ev_win + (1 - eq) * ev_lose)
        if pf > 0:
            ev += pf * icm_e(n, (s0 + sp.pot) / T)
        return ev - ev_fold

    # ---------------- preflop -----------------------------------------
    def preflop(self, sp, obs):
        c = _PRE.cls(sp.hole[0], sp.hole[1])
        pct = _PRE.pct[c]
        bb = sp.bb
        mystack = sp.stack + sp.bet  # chips I have this hand (street 0 includes blind)
        eff_bb = sp.eff / bb
        nb = len(sp.behind)
        rng = self.rng
        stacks = sp.stacks

        if sp.raises == 0:
            limpers = sp.callers
            if sp.can_check:
                # BB option after limps / SB complete
                if limpers <= 1 and sp.n_opp == 1:
                    # SB completed: pressure
                    if pct <= 0.35 or (pct <= 0.55 and rng.random() < 0.5):
                        if eff_bb <= 10:
                            return self.allin(sp)
                        return self.raise_to(sp, 3.5 * bb)
                    return self.fold(sp)
                if pct <= 0.10:
                    if eff_bb <= 12:
                        return self.allin(sp)
                    return self.raise_to(sp, (4 + limpers) * bb)
                return self.fold(sp)
            # unopened / limped, facing only the blind
            if eff_bb <= 20:
                f = PUSH.get(nb, 0.15) * (10.0 / max(eff_bb, 1.5)) ** 0.6
                if limpers:
                    f *= 0.6
                elif sp.behind:
                    fr = sum(self.fold_rate(x) for x in sp.behind) / len(sp.behind)
                    f *= 0.7 + 0.5 * fr
                if pct <= f * PUSH_CAP and sp.behind:
                    # ICM check with fold equity
                    my_total = sp.stack + sp.bet
                    pf = 1.0
                    big = None
                    crs = []
                    for x in sp.behind:
                        cr = max(0.05, min(0.5, 0.12 + 0.3 * (0.6 - self.fold_rate(x))))
                        x_tot = stacks[x] + sp.bets[x]
                        risk = min(my_total, x_tot) - sp.bets[x]
                        if risk < 0.3 * x_tot:
                            cr *= 1.6
                        if x == obs["bb_seat"]:
                            cr *= 1.8
                        elif x == obs["sb_seat"]:
                            cr *= 1.2
                        if x_tot < 4 * bb:
                            cr *= 2.5
                        cr = min(0.6, max(cr, self._shown_width(self.sh_call, x)))
                        crs.append(cr)
                        pf *= 1 - cr
                        tot = stacks[x] + sp.bets[x]
                        if big is None or tot > big[1]:
                            big = (x, tot)
                    cr = sum(crs) / len(crs)
                    eq = eq_vs_range(c, cr) - 0.03 * limpers
                    eff_total = min(my_total, big[1])
                    my_add = eff_total - sp.bet
                    their_add = eff_total - sp.bets[big[0]]
                    final = sp.pot + my_add + their_add
                    ev = self.ev_allin(sp, eq, my_add, final, big[1] <= my_total, pf, big[0])
                    if ev > 0 or pct <= 0.03:
                        return self.allin(sp)
                    return self.fold(sp)
                if pct <= f:
                    return self.allin(sp)
                return self.fold(sp)
            f = OPEN.get(nb, 0.15)
            if eff_bb > 40 and nb >= 3:
                f *= DEEP_OPEN
            if limpers:
                f *= 0.55
            elif sp.behind:
                fr = sum(self.fold_rate(x) for x in sp.behind) / len(sp.behind)
                f *= 0.6 + 0.8 * fr  # 1.08 at the prior 0.6
            if pct <= f:
                size = 2.3 if nb >= 2 else 3.0
                if limpers:
                    size = 3.5 + limpers
                return self.raise_to(sp, size * bb)
            return self.fold(sp)

        # ---- facing a raise ----
        raiser = sp.raiser
        r_stack_bb = (stacks[raiser] + sp.bets[raiser]) / bb if raiser >= 0 else 20
        r_allin = raiser >= 0 and stacks[raiser] == 0
        cur = max(sp.bets) if sp.bets else 0  # current bet to match
        if sp.raises == 1:
            orate = self.open_rate(raiser)
            behind_r = sp.position_of(raiser)
            posf = {0: 1.6, 1: 1.6, 2: 1.35, 3: 1.15}.get(behind_r, 0.85)
            rng_est = orate * posf
            if r_allin:
                rng_est *= 1.4 if r_stack_bb <= 10 else 1.15 if r_stack_bb <= 20 else 0.9
            elif cur > 4 * bb:
                rng_est *= 0.8
        elif sp.raises == 2:
            rng_est = self.reraise_rate(raiser) * (1.3 if r_allin and r_stack_bb <= 15 else 1.0)
        else:
            rng_est = self.reraise_rate(raiser) * 0.6
        if sp.raises == 1:
            rng_est = max(rng_est, self._shown_width(self.sh_open, raiser))
        elif sp.raises == 2:
            rng_est = max(rng_est, self._shown_width(self.sh_3b, raiser))
        rng_est = max(0.025, min(1.0, rng_est))

        eq = eq_vs_range(c, rng_est)
        # multiway penalty: others still in or to act
        others = sp.n_opp - 1
        to_call = sp.to_call
        pot_after = sp.pot + to_call
        call_commits = to_call >= 0.45 * sp.stack or sp.stack - to_call < 3 * bb
        if sp.raises == 1 and not r_allin and eff_bb <= 32 and sp.can_raise:
            # re-steal shove with fold equity
            my_total = sp.stack + sp.bet
            r_total = stacks[raiser] + sp.bets[raiser]
            eff_total = min(my_total, r_total)
            my_add = eff_total - sp.bet
            their_add = eff_total - sp.bets[raiser]
            call_r = min(rng_est, max(0.07, (1 - self.fold_rate(raiser)) * 0.3) + 0.05 * min(1.0, 15.0 / max(eff_bb, 1)))
            pc = call_r / rng_est
            n_beh = len(sp.behind)
            pf = (1 - pc) * (0.94 ** n_beh) * (0.85 ** sp.callers)
            eq_c = eq_vs_range(c, call_r) - 0.03 * sp.callers
            final = sp.pot + my_add + their_add
            ev_shove = self.ev_allin(sp, eq_c, my_add, final, r_total <= my_total, pf, raiser)
            if ev_shove > RESTEAL:
                return self.allin(sp)
        if r_allin or call_commits or eff_bb <= 15:
            # all-in decision: go all-in with enough equity
            my_total = sp.stack + sp.bet
            r_total = stacks[raiser] + sp.bets[raiser] if raiser >= 0 else my_total
            eff_total = min(my_total, max(r_total, cur))
            my_add = max(0, eff_total - sp.bet)
            their_add = max(0, eff_total - (sp.bets[raiser] if raiser >= 0 else cur))
            final = sp.pot + my_add + their_add - sum(max(0, b - eff_total) for b in sp.bets)
            eq_m = eq ** (1 + 0.4 * sp.callers) - 0.012 * max(0, others - sp.callers)
            ev = self.ev_allin(sp, eq_m, my_add, final, r_total <= my_total, 0.0, raiser)
            if ev > 0:
                return self.allin(sp)
            # cheap flat in the BB / with good odds when not facing an all-in
            if (not r_allin and not call_commits and sp.raises == 1 and to_call <= 0.15 * sp.stack
                    and sp.callers == 0 and pct <= (0.35 if sp.role == "BB" else 0.12)
                    and eq > to_call / pot_after + 0.08):
                return self.call(sp)
            if not r_allin and not call_commits and pct <= 0.03:
                return self.allin(sp)
            return self.fold(sp)

        # deeper stacks, facing a normal raise
        if sp.raises == 1:
            if pct <= 0.035 or (pct <= 0.06 and eq > 0.6):
                if eff_bb <= 30:
                    return self.allin(sp)
                return self.raise_to(sp, (3.2 if sp.ip else 3.8) * cur)
            # light 3-bet vs late opens (pressure)
            if rng_est >= 0.3 and pct <= 0.16 and others == 0 and rng.random() < 0.35:
                if eff_bb <= 25:
                    return self.allin(sp)
                return self.raise_to(sp, (3.0 if sp.ip else 3.6) * cur)
            odds = to_call / pot_after
            if sp.role == "BB" and others <= 1 and to_call <= 3 * bb and pct <= 0.45:
                return self.call(sp)
            if pct <= 0.12 + (0.06 if sp.ip else 0) and to_call <= 0.12 * sp.stack and eq > odds + 0.05:
                return self.call(sp)
            return self.fold(sp)
        # facing 3-bet or more
        if pct <= 0.02:
            return self.allin(sp)
        if pct <= 0.05:
            if eff_bb <= 45:
                return self.allin(sp)
            if to_call <= 0.15 * sp.stack:
                return self.call(sp)
        return self.fold(sp)

    # ---------------- postflop ----------------------------------------
    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        rng = self.rng
        st = sp.street
        n_opp = sp.n_opp
        pot = sp.pot
        to_call = sp.to_call
        bb = sp.bb
        spr = sp.stack / max(pot, 1)
        draw1 = outs / 47.0
        draw2 = 1 - (1 - outs / 47.0) * (1 - outs / 46.0) if st == 1 else draw1
        aggr = sp.last_aggr == sp.me  # last aggressor on previous streets
        mult = 1.0 if n_opp == 1 else 0.8 if n_opp == 2 else 0.65

        if to_call == 0:
            # betting decision
            opps = sp.opps
            fr = sum(self.post_fold(x) for x in opps) / len(opps) if opps else 0.45
            vs = 1.2 if fr < 0.35 else 0.85 if fr > 0.55 else 1.0  # value size vs stations/folders
            if s >= 0.80:
                if spr < 1.2:
                    return self.allin(sp)
                return self.bet_pot(sp, 0.75 * vs)
            if s >= 0.60 * (1 if n_opp == 1 else 1.12):
                if spr < 0.8:
                    return self.allin(sp)
                return self.bet_pot(sp, 0.6 * vs)
            bm = max(0.15, min(1.7, (fr / 0.45) ** 1.5))
            if st < 3 and outs >= 8 and n_opp <= 2 and rng.random() < 0.65:
                return self.bet_pot(sp, 0.6)
            if aggr and n_opp <= 2:
                freq = (0.75 if st == 1 else 0.5 if st == 2 else RIVER_BLUFF) * (1 if n_opp == 1 else 0.5)
                if wet and s < 0.3 and outs < 4:
                    freq *= 0.6
                if s < 0.45:
                    freq = min(0.95, freq * bm)
                if rng.random() < freq:
                    return self.bet_pot(sp, 0.55 if st == 1 else 0.65)
            elif n_opp == 1 and sp.ip and rng.random() < STAB * bm:
                # stab when checked to in position
                return self.bet_pot(sp, 0.5)
            return self.fold(sp)  # check

        # facing a bet
        pot_before = pot - to_call if pot > to_call else pot
        bet_frac = to_call / max(pot - to_call, 1)
        odds = to_call / (pot + to_call)
        eq = s * mult - 0.08 * min(bet_frac, 1.5) - (0.04 if sp.raises >= 2 else 0)
        bettor = sp.raiser if sp.raiser >= 0 else -1
        if bettor < 0:
            for h in reversed(sp.hist):
                if h[0] == st and h[2] in ("bet", "raise"):
                    bettor = h[1]
                    break
        if bettor >= 0:
            eq += 0.35 * (self.aggr_rate(bettor) - 0.3)
        allin_call = to_call >= sp.stack * 0.9
        if allin_call:
            de = draw2
        elif st == 1:
            de = draw2 * 0.85 if to_call <= 0.15 * sp.stack else draw1 * 1.2
        else:
            de = draw1 * (1.25 if to_call <= 0.15 * sp.stack else 1.0)
        if cat <= PAIR or outs >= 8:
            eq = max(eq, de * 0.95 + (0.1 if cat == PAIR else 0))
        # strong: raise
        if s >= 0.85 or (s >= 0.76 and n_opp == 1 and st >= 2):
            if sp.can_raise:
                if spr < 2.5:
                    return self.allin(sp)
                return self.raise_to(sp, max(sp.bets) * 3)
            return self.call(sp)
        # semi-bluff raise with big draws on flop
        if st == 1 and outs >= 12 and n_opp == 1 and sp.can_raise and rng.random() < 0.5:
            return self.allin(sp) if spr < 3 else self.raise_to(sp, max(sp.bets) * 3)
        if eq >= odds:
            if to_call >= 0.5 * sp.stack and s < 0.85:
                # committing call: ICM check (treat as all-in)
                my_add = sp.stack
                final = pot + sp.stack + max(0, min(sp.stack - to_call, (sp.stacks[bettor] if bettor >= 0 else 0)))
                vb = bettor >= 0 and sp.stacks[bettor] + sp.bets[bettor] <= sp.stack + sp.bet
                if self.ev_allin(sp, min(0.95, eq), my_add, final, vb, 0.0, bettor) <= 0:
                    return self.fold(sp)
            return self.call(sp)
        return self.fold(sp)
