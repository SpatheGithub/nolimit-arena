"""b01 bot: range-based preflop with push/fold EV model, heuristic postflop,
light per-table opponent modelling."""

import os
import random
import time

import numpy as np

from ._common import CARD, PREFLOP, Variant, Spot, features

HERE = os.path.dirname(os.path.abspath(__file__))

_PT = PREFLOP["std"]
PCT = _PT.pct  # 169 classes, 0 = best

EQ = np.load(os.path.join(HERE, "eq169.npy")).astype(np.float64)
_W = np.array([6.0 if i // 13 == i % 13 else (4.0 if i // 13 > i % 13 else 12.0) for i in range(169)])
_ORDER = sorted(range(169), key=lambda i: PCT[i])


def _range_weights():
    wt = np.zeros((101, 169))
    for k in range(1, 101):
        t = k / 100.0 * 1326.0
        acc = 0.0
        for c in _ORDER:
            if acc >= t:
                break
            w = min(_W[c], t - acc)
            wt[k, c] = w
            acc += w
    wt[0] = wt[1]
    return wt


_WT = _range_weights()
RQ = (EQ @ _WT.T) / _WT.sum(axis=1)  # RQ[h, k] = equity of class h vs top-k% range
RQ = [list(map(float, row)) for row in RQ]
# fraction rank of each class (0 best .. 1 worst) by combos
_RANKPOS = [0.0] * 169
_acc = 0.0
for _c in _ORDER:
    _RANKPOS[_c] = (_acc + _W[_c] / 2) / 1326.0
    _acc += _W[_c]


def _combo_lists():
    out = []
    allc = []
    for c1 in range(52):
        for c2 in range(c1 + 1, 52):
            allc.append((c1, c2))
    for k in range(11):
        x = max(0.1, k / 10.0)
        lst = [cc for cc in allc if _RANKPOS[hcls(cc[0], cc[1])] <= x]
        out.append(lst)
    return out


def hcls(c1, c2):
    a, b = c1 >> 2, c2 >> 2
    if a == b:
        return a * 13 + a
    hi, lo = (a, b) if a > b else (b, a)
    return hi * 13 + lo if (c1 & 3) == (c2 & 3) else lo * 13 + hi


def rq(h, frac):
    k = int(frac * 100 + 0.5)
    if k < 1:
        k = 1
    elif k > 100:
        k = 100
    return RQ[h][k]


COMBOS = _combo_lists()

SHOVE_K = 2.6  # prior shove range ~ SHOVE_K / stack_bb
HU_LIMP_PCT = 0.0   # HU SB completes (when not shoving) with top 80%
HU_SHOVE_K = 6.5    # HU opponent shove range prior ~ HU_SHOVE_K / stack_bb
HU_OPEN_PCT = 0.85  # HU SB open-raise range when deeper than push/fold zone
DEEP_STACKOFF_PCT = 0.012  # deep (>=30bb) vs 3bet/4bet: only AA/KK shove preflop
# opener range multiplier by players left behind the opener (SB=1, BTN=2, CO=3, ...)
OPEN_POS_F = {0: 2.0, 1: 2.0, 2: 1.6, 3: 1.25, 4: 0.95}
SHOVE_MARGIN = 0.02  # ICM points
ICM_ALPHA = 0.85  # blend of ICM vs chip-linear utility
CALL_PRIOR = 0.16
CALL_MARGIN = 0.02

# open-raise thresholds by players left to act behind
OPEN_PCT = {0: 0.5, 1: 0.48, 2: 0.40, 3: 0.30, 4: 0.24, 5: 0.19, 6: 0.16, 7: 0.14}


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        pts = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        self.points = pts + [0] * (16 - len(pts))
        self.psum = [sum(self.points[:k]) for k in range(17)]
        self.var = Variant(config.get("variant"))
        n = config.get("seats", 8)
        self.n = n
        # opponent stats per seat
        self.hands = [0] * 16
        self.pfr = [0] * 16       # preflop raises (any)
        self.shoves = [0] * 16    # preflop all-in raises
        self.faced = [0] * 16     # faced a big preflop bet (>= 30% stack)
        self.called_big = [0] * 16
        self.vpip = [0] * 16
        self.pf_faced = [0] * 16
        self.pf_folds = [0] * 16
        self.fo_faced = [0] * 16
        self.fo_folds = [0] * 16
        self.po_aggr = [0] * 16
        self.po_pass = [0] * 16
        self.pf_aggr_me = False
        self.cur_hand = -1

    def fold_freq(self, s):
        return (self.pf_folds[s] + 0.45 * 5) / (self.pf_faced[s] + 5)

    # ---------- opponent model ----------
    def raise_freq(self, s):
        return (self.pfr[s] + 0.18 * 8) / (self.hands[s] + 8)

    def shove_freq(self, s):
        return (self.shoves[s] + 0.08 * 6) / (self.hands[s] + 6)

    def call_freq(self, s):
        return (self.called_big[s] + CALL_PRIOR * 3) / (self.faced[s] + 3)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            stacks = event["stacks"]
            pay = event["payoffs"]
            start = {}
            for s in range(len(stacks)):
                p = pay.get(s, pay.get(str(s), 0)) if isinstance(pay, dict) else pay[s]
                start[s] = stacks[s] - p
            hist = event["history"]
            seen = set()
            bet = {}
            raised_big = None
            for st, seat, act, amt in hist:
                if st != 0:
                    continue
                if act in ("sb", "bb", "ante"):
                    bet[seat] = amt if act != "ante" else 0
                    continue
                seen.add(seat)
                if act == "raise":
                    self.pfr[seat] += 1
                    self.vpip[seat] += 1
                    if start.get(seat, 1e9) > 0 and amt >= start.get(seat, 1e9):
                        self.shoves[seat] += 1
                    if start.get(seat, 1e9) > 0 and amt >= 0.3 * start.get(seat, 1e9):
                        raised_big = (seat, amt)
                    bet[seat] = amt
                elif act == "call":
                    self.vpip[seat] += 1
                    if raised_big is not None and seat != raised_big[0]:
                        self.faced[seat] += 1
                        self.called_big[seat] += 1
                    bet[seat] = bet.get(seat, 0) + amt
                elif act == "fold":
                    if raised_big is not None and seat != raised_big[0]:
                        self.faced[seat] += 1
            for s in seen:
                self.hands[s] += 1
            # fold-to-open stats
            opener = None
            for st, seat, act, amt in hist:
                if st != 0 or act in ("sb", "bb", "ante"):
                    continue
                if act == "raise":
                    if opener is None:
                        opener = seat
                        continue
                    if seat != opener:
                        self.fo_faced[seat] += 1
                    break
                if opener is not None and seat != opener:
                    self.fo_faced[seat] += 1
                    if act == "fold":
                        self.fo_folds[seat] += 1
            # postflop fold-to-bet stats
            cur = -1
            bet_open = False
            for st, seat, act, amt in hist:
                if st == 0:
                    continue
                if st != cur:
                    cur = st
                    bet_open = False
                if act == "raise":
                    self.po_aggr[seat] += 1
                    if bet_open:
                        self.pf_faced[seat] += 1
                    bet_open = True
                elif act in ("check", "call"):
                    self.po_pass[seat] += 1
                elif bet_open and act in ("fold", "call"):
                    self.pf_faced[seat] += 1
                    if act == "fold":
                        self.pf_folds[seat] += 1
        except Exception:
            pass

    # ---------- helpers ----------
    @staticmethod
    def _raise(sp, amount):
        if not sp.can_raise:
            return {"action": "call"} if sp.to_call > 0 else {"action": "check"}
        a = int(amount)
        if a < sp.min_to:
            a = sp.min_to
        if a > sp.max_to:
            a = sp.max_to
        return {"action": "raise", "amount": a}

    @staticmethod
    def _call(sp):
        return {"action": "call"} if sp.to_call > 0 else {"action": "check"}

    @staticmethod
    def _fold(sp):
        return {"action": "check"} if sp.can_check else {"action": "fold"}

    def _allin(self, sp):
        if sp.can_raise:
            return {"action": "raise", "amount": sp.max_to}
        return self._call(sp)

    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs["n_discard"]])}
        sp = Spot(obs, self.var)
        if obs["hand_id"] != self.cur_hand:
            self.cur_hand = obs["hand_id"]
            self.pf_aggr_me = False
        if sp.street == 0:
            a = self.preflop(sp, obs)
            if a.get("action") == "raise":
                self.pf_aggr_me = True
            return a
        return self.postflop(sp, obs)

    # ---------- preflop ----------
    def U(self, x, n, T):
        """ICM points for stack x with n alive and T chips total (others symmetric)."""
        pts = self.points
        if n < 1:
            n = 1
        if x <= 0:
            return pts[n - 1]
        if x >= T or n == 1:
            return pts[0]
        lin = pts[n - 1] + (self.psum[n] - n * pts[n - 1]) * x / T
        return ICM_ALPHA * self._icm(x, n, T) + (1 - ICM_ALPHA) * lin

    def _icm(self, x, n, T):
        pts = self.points
        m = n - 1
        y = (T - x) / m
        pr = 1.0
        eq = 0.0
        for k in range(n):
            rem = m - k
            if rem <= 0:
                eq += pr * pts[k]
                break
            pk = x / (x + rem * y)
            eq += pr * pk * pts[k]
            pr *= (1 - pk)
        return eq

    def icm_call(self, sp, n, T, e, call_amt, excess, n_win):
        """Points gain of calling (all-in style) vs folding."""
        win_stack = sp.stack + sp.pot - excess
        lose_stack = sp.stack - call_amt
        U = self.U
        u_l = U(lose_stack, n, T) if lose_stack > 0 else self.points[n - 1]
        return e * U(win_stack, n_win, T) + (1 - e) * u_l - U(sp.stack, n, T)

    def icm_need(self, sp, n, T, call_amt, excess, n_win):
        U = self.U
        u_w = U(sp.stack + sp.pot - excess, n_win, T)
        lose_stack = sp.stack - call_amt
        u_l = U(lose_stack, n, T) if lose_stack > 0 else self.points[n - 1]
        u_f = U(sp.stack, n, T)
        if u_w - u_l <= 1e-9:
            return 1.0
        return (u_f - u_l) / (u_w - u_l)

    def shove_ev(self, sp, obs, h):
        """ICM points gain of shoving now vs folding, unopened-ish pot."""
        stacks, bets = sp.stacks, sp.bets
        pot = sp.pot
        my_total = sp.stack + sp.bet
        n = len(obs["alive"])
        T = sum(stacks) + pot
        U = self.U
        p_none = 1.0
        ev = 0.0
        for j in sp.behind:
            their_total = stacks[j] + bets[j]
            eff = min(my_total, their_total)
            call_amt = eff - bets[j]
            if call_amt <= 0:
                continue
            q = self.call_freq(j)
            if j == obs["bb_seat"]:
                q += 0.06
            if n == 2:
                q += 0.14
            elif n == 3:
                q += 0.05
            # cheap calls relative to pot get called wider
            odds = call_amt / (pot - sp.bet + bets[j] + 2 * eff - bets[j] + 1e-9)
            if odds < 0.35:
                q = q + (0.35 - odds) * 1.2
            # big stacks risking little call wider
            if their_total > 2.5 * my_total:
                q += 0.05
            q = min(0.9, max(0.04, q))
            e = rq(h, q)
            dead = pot - sp.bet - bets[j]
            win_stack = sp.stack - (eff - sp.bet) + dead + 2 * eff
            lose_stack = sp.stack - (eff - sp.bet)
            n_win = n - 1 if their_total <= my_total else n
            u_l = U(lose_stack, n, T) if lose_stack > 0 else self.points[n - 1]
            ev += p_none * q * (e * U(win_stack, n_win, T) + (1 - e) * u_l)
            p_none *= (1 - q)
        ev += p_none * U(sp.stack + pot, n, T)
        return ev - U(sp.stack, n, T)

    def preflop(self, sp, obs):
        hole = sp.hole
        h = hcls(hole[0], hole[1])
        pr = _RANKPOS[h]  # 0 best .. 1 worst
        bb = sp.bb
        stacks, bets = sp.stacks, sp.bets
        my_total = sp.stack + sp.bet
        hist = obs["history"]
        raises = []
        limpers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises.append((seat, amt))
            elif act == "call" and not raises:
                limpers += 1
        n_r = len(raises)
        others_max = max([stacks[s] + bets[s] for s in sp.opps], default=0)
        eff = min(my_total, others_max)
        eff_bb = eff / bb
        n_behind = len(sp.behind)
        n_left = len(obs["alive"])

        if n_r == 0:
            # unopened (maybe limpers)
            if eff_bb <= 14 or (eff_bb <= 18 and n_behind <= 2):
                ev = self.shove_ev(sp, obs, h)
                if ev > SHOVE_MARGIN:
                    return self._allin(sp)
                if sp.can_check:
                    return {"action": "check"}
                # heads-up SB (in position postflop): complete instead of folding
                if n_left == 2 and n_behind == 1 and sp.to_call <= 0.5 * bb + 1 and pr < HU_LIMP_PCT:
                    return self._call(sp)
                return self._fold(sp)
            op = OPEN_PCT.get(n_behind, 0.14)
            if n_left <= 4:
                op = min(0.6, op * 1.25)
            if n_left == 2:
                op = HU_OPEN_PCT
            if 0 < n_behind <= 3 and not limpers:
                fo = sum((self.fo_folds[j] + 0.7 * 4) / (self.fo_faced[j] + 4) for j in sp.behind) / n_behind
                op = min(0.75, op * min(1.6, max(0.75, 1 + (fo - 0.7) * 2.5)))
            if limpers:
                op *= 0.6
            if sp.can_check:  # BB option vs limpers
                if pr < 0.12:
                    return self._raise(sp, sp.bet + (3 + limpers) * bb)
                return {"action": "check"}
            if pr < op:
                size = (2.5 if n_behind > 1 else 3.0) * bb + limpers * bb
                if eff_bb < 22:
                    size = 2.2 * bb + limpers * bb
                return self._raise(sp, size)
            # SB limp when cheap and decent
            if n_behind == 1 and sp.to_call <= 0.5 * bb and pr < 0.65:
                return self._call(sp)
            return self._fold(sp)

        # facing raise(s)
        raiser, raise_to = raises[-1]
        r_stack_total = stacks[raiser] + bets[raiser]
        raiser_allin = stacks[raiser] == 0
        if n_r == 1:
            if raise_to >= 0.6 * r_stack_total or raiser_allin:
                rng_ = max(self.shove_freq(raiser), self.raise_freq(raiser) * 0.7)
                rbb = r_stack_total / bb
                order = sp.order
                nb_sh = len(order) - 1 - order.index(raiser) if raiser in order else 4
                pos_f = 1.0 + 0.3 * max(0, 4 - nb_sh)
                rng_ = max(rng_, min(0.7, SHOVE_K * pos_f / max(rbb, 1)))
                if n_left == 2:
                    # heads-up shoves are wide (equilibrium-ish ~6.5/stack_bb)
                    rng_ = max(rng_, min(0.9, HU_SHOVE_K / max(rbb, 1)))
            else:
                rng_ = self.raise_freq(raiser)
                # late-position opens are wider
                order = sp.order
                nb_r = len(order) - 1 - order.index(raiser) if raiser in order else 4
                rng_ *= OPEN_POS_F.get(nb_r, 0.8)
                if n_left == 2:
                    rng_ = max(rng_, 0.6)
                # bigger raises are stronger
                if raise_to > 5 * bb:
                    rng_ *= 0.75
        elif n_r == 2:
            rng_ = max(0.04, self.raise_freq(raiser) * 0.35)
        else:
            rng_ = max(0.025, self.raise_freq(raiser) * 0.2)
        rng_ = min(0.9, max(0.025, rng_))
        e = rq(h, rng_)
        # other players already in (callers) reduce equity
        n_in = len(sp.opps)
        if n_in > 1:
            e = e ** (1 + 0.55 * (n_in - 1))
        call_amt = min(sp.to_call, sp.stack)
        pot_after = sp.pot + call_amt
        need = call_amt / pot_after if pot_after > 0 else 1.0
        commit = call_amt >= 0.35 * my_total or (sp.stack - call_amt) < 3 * bb or raiser_allin

        # stack-off threshold: shove/call all-in decisions
        if commit:
            T = sum(stacks) + sp.pot
            excess = max(0, raise_to - my_total)
            n_win = n_left - 1 if (raiser_allin and r_stack_total <= my_total) else n_left
            gain = self.icm_call(sp, n_left, T, e, call_amt, excess, n_win)
            if gain > CALL_MARGIN:
                # re-shove if raiser not all-in and others can't cover? just shove for fold equity
                if sp.can_raise and not raiser_allin and e > 0.5:
                    return self._allin(sp)
                return self._call(sp)
            return self._fold(sp)

        # resteal shove vs a single open when stacks are shortish
        if n_r == 1 and not raiser_allin and eff_bb <= 24 and n_in == 1 and sp.can_raise:
            q_call = 0.4 if eff_bb > 14 else 0.55
            e_c = rq(h, rng_ * q_call)
            risk_eff = min(my_total, r_stack_total)
            dead = sp.pot - sp.bet - bets[raiser]
            T = sum(stacks) + sp.pot
            U = self.U
            u_f = U(sp.stack, n_left, T)
            lose_stack = sp.stack - (risk_eff - sp.bet)
            u_l = U(lose_stack, n_left, T) if lose_stack > 0 else self.points[n_left - 1]
            n_win = n_left - 1 if r_stack_total <= my_total else n_left
            u_w = U(sp.stack - (risk_eff - sp.bet) + dead + 2 * risk_eff, n_win, T)
            u_steal = U(sp.stack + sp.pot, n_left, T)
            p_bf = 0.95 ** len(sp.behind)
            eb = rq(h, 0.05)
            u_bad = eb * U(sp.stack + sp.pot + my_total, n_left, T) + (1 - eb) * self.points[n_left - 1]
            ev = p_bf * ((1 - q_call) * u_steal + q_call * (e_c * u_w + (1 - e_c) * u_l)) + (1 - p_bf) * u_bad
            if ev - u_f > SHOVE_MARGIN:
                return self._allin(sp)

        # deep: consider 3bet / 4bet
        value_thr = max(0.025, min(0.06, rng_ * 0.25))
        if pr < value_thr:
            if n_r >= 2 and eff_bb >= 30 and pr >= DEEP_STACKOFF_PCT:
                # deep 3bet/4bet pot: don't stack off preflop with QQ/AK, just call
                if call_amt <= 0.25 * my_total:
                    return self._call(sp)
                return self._fold(sp)
            if eff_bb < 30 or n_r >= 2:
                return self._allin(sp)
            size = raise_to * 3 + (n_in - 1) * raise_to
            if size > 0.4 * my_total:
                return self._allin(sp)
            return self._raise(sp, size)
        # light 3-bet steal occasionally vs wide raisers in late position
        if n_r == 1 and rng_ > 0.35 and pr < 0.2 and self.rng.random() < 0.5:
            size = raise_to * 3
            if size > 0.4 * my_total:
                if eff_bb <= 25 and e > 0.45:
                    return self._allin(sp)
            else:
                return self._raise(sp, size)
        # call: needs equity with postflop discount, cheap relative to stack
        is_pair = (h // 13) == (h % 13)
        implied_ok = is_pair and call_amt <= 0.08 * eff and n_r == 1
        if (e - 0.10 > need and call_amt <= 0.25 * my_total) or implied_ok:
            return self._call(sp)
        return self._fold(sp)

    # ---------- postflop ----------
    def mc(self, sp, opp_info, t0, budget=0.00025, max_trials=200):
        hero = sp.hole
        b0 = sp.board
        val = self.var.ranker.value
        used0 = set(hero)
        used0.update(b0)
        deck = [c for c in range(52) if c not in used0]
        need = 5 - len(b0)
        bv = val(b0)
        bc = bv >> 20
        btop = max(c >> 2 for c in b0)
        rand = self.rng.random
        sample = self.rng.sample
        clock = time.perf_counter
        tot_w = 0.0
        win_w = 0.0
        n = 0
        nop = len(opp_info)
        hb = list(hero) + list(b0)
        LD = len(deck)
        hv_river = val(hb) if need == 0 else 0
        while n < max_trials:
            n += 1
            if (n & 1) == 0 and clock() - t0 > budget:
                break
            used = set(used0)
            opps = []
            w = 1.0
            ok = True
            for lst, wtab in opp_info:
                L = len(lst)
                for _ in range(10):
                    cc = lst[int(rand() * L)]
                    if cc[0] not in used and cc[1] not in used:
                        break
                else:
                    ok = False
                    break
                used.add(cc[0])
                used.add(cc[1])
                if wtab is not None:
                    v = val([cc[0], cc[1]] + b0)
                    c = v >> 20
                    if c > bc:
                        lvl = 3 if c >= 2 else (2 if ((v >> 16) & 15) >= btop else 1)
                    else:
                        lvl = 0
                    w *= wtab[lvl]
                opps.append(cc)
            if not ok or w <= 0:
                continue
            if need:
                ext = []
                while len(ext) < need:
                    c = deck[int(rand() * LD)]
                    if c not in used:
                        used.add(c)
                        ext.append(c)
                hv = val(hb + ext)
                bd = b0 + ext
            else:
                hv = hv_river
                bd = b0
            top = -1
            ties = 0
            for cc in opps:
                ov = val([cc[0], cc[1]] + bd)
                if ov > top:
                    top = ov
                    ties = 1 if ov == hv else 0
                elif ov == top and ov == hv:
                    ties += 1
            tot_w += w
            if hv > top:
                win_w += w
            elif hv == top:
                win_w += w / (1 + ties)
        if tot_w <= 0:
            return None
        return win_w / tot_w

    def postflop(self, sp, obs):
        t0 = time.perf_counter()
        hist = obs["history"]
        st = sp.street
        pf_raises = {}
        pf_called = set()
        any_raise = False
        aggr_now = {}
        aggr_prev = {}
        called_prev = set()
        n_pf_raise = 0
        for h_st, seat, act, amt in hist:
            if h_st == 0:
                if act == "raise":
                    n_pf_raise += 1
                    pf_raises[seat] = n_pf_raise
                    any_raise = True
                elif act == "call" and any_raise:
                    pf_called.add(seat)
            elif act == "raise":
                if h_st == st:
                    aggr_now[seat] = aggr_now.get(seat, 0) + 1
                else:
                    aggr_prev[seat] = aggr_prev.get(seat, 0) + 1
            elif act == "call" and h_st < st:
                called_prev.add(seat)
        pot = sp.pot
        bet_ratio = sp.to_call / max(pot - sp.to_call, 1)
        raises_now = sum(aggr_now.values())
        opp_info = []
        for j in sp.opps:
            if j in pf_raises:
                if pf_raises[j] >= 2:
                    x = 0.1
                else:
                    x = min(0.6, max(0.1, self.raise_freq(j)))
            elif j in pf_called:
                x = 0.45
            else:
                x = 1.0
            k = min(10, max(1, int(x * 10 + 0.999)))
            if j in aggr_now and sp.to_call > 0:
                if raises_now >= 2:
                    wt = (0.08, 0.25, 0.6, 1.0)
                elif bet_ratio >= 0.8:
                    wt = (0.15, 0.35, 0.8, 1.0)
                else:
                    wt = (0.3, 0.6, 0.9, 1.0)
            elif j in aggr_prev:
                wt = (0.5, 0.8, 1.0, 1.0)
            elif j in called_prev:
                wt = (0.45, 0.9, 1.0, 0.9)
            else:
                wt = None
            if wt is not None:
                af = (self.po_aggr[j] + 0.35 * 6) / (self.po_aggr[j] + self.po_pass[j] + 6)
                if af > 0.45:
                    kf = min(0.7, (af - 0.4) * 1.6)
                    wt = tuple(w + (1 - w) * kf for w in wt)
            opp_info.append((COMBOS[k], wt))
        big = sp.to_call >= 0.4 * (sp.stack + sp.bet)
        e = self.mc(sp, opp_info, t0, budget=0.0004 if big else 0.00025)
        if e is None:
            return self.postflop_h(sp, obs)
        n_opp = sp.n_opp
        my_total = sp.stack + sp.bet
        spr = sp.stack / max(pot, 1)
        if sp.to_call == 0:
            vthr = 0.62 if n_opp == 1 else (0.5 if n_opp == 2 else 0.42)
            ff = sum(self.fold_freq(j) for j in sp.opps) / max(1, n_opp)
            if e >= vthr:
                frac = 0.75 if e >= vthr + 0.15 else 0.6
                if ff < 0.35:
                    frac += 0.15
                return self._bet_frac(sp, frac)
            if n_opp == 1:
                r = self.rng.random()
                if st < 3:
                    if self.pf_aggr_me and st == 1 and r < min(0.8, max(0.1, (ff - 0.2) * 1.8)):
                        return self._bet_frac(sp, 0.45)
                    if 0.35 <= e < vthr and r < min(0.6, max(0.1, ff - 0.1)):
                        return self._bet_frac(sp, 0.5)
                elif e < 0.25 and ff > 0.5 and r < (ff - 0.45) * 1.5:
                    return self._bet_frac(sp, 0.6)
            return {"action": "check"}
        call_amt = min(sp.to_call, sp.stack)
        need = call_amt / (pot + call_amt)
        if call_amt >= 0.25 * my_total:
            n_left = len(obs["alive"])
            T = sum(sp.stacks) + pot
            excess = max(0, sp.to_call - sp.stack)
            need = max(need, self.icm_need(sp, n_left, T, call_amt, excess, n_left))
        rthr = 0.78 if n_opp == 1 else 0.65
        if raises_now >= 2:
            rthr += 0.08
        if e >= rthr and sp.can_raise:
            if spr < 2.2:
                return self._allin(sp)
            return self._raise(sp, sp.bet + sp.to_call + (pot + sp.to_call) * 0.85)
        margin = 0.045 if st == 1 else 0.035
        if e >= need + margin:
            return self._call(sp)
        return self._fold(sp)

    def postflop_h(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        pot = sp.pot
        n_opp = sp.n_opp
        st = sp.street
        my_total = sp.stack + sp.bet
        spr = sp.stack / max(pot, 1)
        # adjust strength for multiway
        adj = s - 0.06 * (n_opp - 1)
        draw_eq = 0.0
        if st == 1:
            draw_eq = min(0.45, outs * 0.04) if sp.stack <= pot else outs * 0.021
        elif st == 2:
            draw_eq = outs * 0.022
        if sp.to_call == 0:
            if adj >= 0.74:
                frac = 0.75 if wet else 0.6
                return self._bet_frac(sp, frac)
            if adj >= 0.58 and n_opp <= 2:
                return self._bet_frac(sp, 0.5)
            if st < 3 and outs >= 8 and n_opp <= 2 and self.rng.random() < 0.55:
                return self._bet_frac(sp, 0.55)
            if self.pf_aggr_me and st == 1 and n_opp == 1 and self.rng.random() < 0.6:
                return self._bet_frac(sp, 0.45)
            if self.pf_aggr_me and st == 1 and n_opp == 2 and adj >= 0.4 and self.rng.random() < 0.5:
                return self._bet_frac(sp, 0.5)
            return {"action": "check"}
        # facing a bet
        call_amt = min(sp.to_call, sp.stack)
        need = call_amt / (pot + call_amt)
        bet_ratio = sp.to_call / max(pot - sp.to_call, 1)  # bet size relative to pot before it
        # opponent bet indicates strength: discount
        eq = adj - 0.08 * min(bet_ratio, 1.5) + draw_eq * (1.0 if cat <= 1 else 0.3)
        if sp.raises >= 2:
            eq -= 0.08
        if adj >= 0.86 or (adj >= 0.78 and spr < 1.5):
            if sp.can_raise:
                if spr < 2.0:
                    return self._allin(sp)
                return self._raise(sp, sp.bet + sp.to_call + (pot + sp.to_call) * 0.9)
            return self._call(sp)
        if eq >= need + 0.02:
            return self._call(sp)
        return self._fold(sp)

    def _bet_frac(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            target = sp.max_to
        return self._raise(sp, target)
