"""b03 shortdeck bot: precomputed class-vs-class equities, EV-based push/fold,
position-based opening, range-aware calling, heuristic postflop, per-seat reads."""

import json
import os
import random

from ._common import (CARD, FLUSH, FULL_HOUSE, HIGH, PAIR, STRAIGHT, TRIPS, TWO_PAIR, Spot, Variant,
                      act_allin, act_call, act_fold, act_raise, features, safe_default)

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "eqmat.json")) as _f:
    _D = json.load(_f)
EQ = _D["eq"]
NC = _D["ncombo"]
_TOT = float(sum(NC))
ER = [sum(NC[b] * EQ[a][b] for b in range(81)) / _TOT for a in range(81)]
ORDER = sorted(range(81), key=lambda k: -ER[k])
# percentile (0 = best) of each class, midpoint of its combos
PCT = [0.0] * 81
_cum = 0.0
for _k in ORDER:
    PCT[_k] = (_cum + NC[_k] / 2.0) / _TOT
    _cum += NC[_k]


def _eqtop():
    # EQTOP[a][i]: equity of class a vs top i% of hands (i = 1..100)
    out = []
    for a in range(81):
        row = [0.5] * 101
        i = 1
        cw = 0.0
        ce = 0.0
        for k in ORDER:
            w = NC[k]
            # card removal: same class pair has fewer combos
            if k == a:
                w = w * 0.4
            while i <= 100 and cw + w >= i / 100.0 * _TOT:
                need = i / 100.0 * _TOT - cw
                row[i] = (ce + need * EQ[a][k]) / max(1e-9, cw + need)
                i += 1
            cw += w
            ce += w * EQ[a][k]
        while i <= 100:
            row[i] = ce / cw
            i += 1
        row[0] = row[1]
        out.append(row)
    return out


EQTOP = _eqtop()

with open(os.path.join(_DIR, "icmtab.json")) as _f:
    ICMV = {int(k): v for k, v in json.load(_f).items()}


def icm_v(n, x):
    if n < 2:
        return 100.0
    if n > 8:
        n = 8
    row = ICMV[n]
    if x <= 0:
        return row[0]
    if x >= 1:
        return 100.0
    f = x * 100.0
    i = int(f)
    w = f - i
    return row[i] * (1 - w) + row[i + 1] * w


LAM = 0.5
# straight windows as rank-bit masks (rank ids 4..12 = 6..A), A-6-7-8-9 included
_WINDOWS = [(1 << 12) | (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7)] + [sum(1 << r for r in range(lo, lo + 5)) for lo in range(4, 9)]


class Util:
    """Blend of ICM points and chip EV converted at the marginal ICM rate."""
    __slots__ = ("n", "x0", "v0", "d")

    def __init__(self, n, x0):
        self.n = n
        self.x0 = x0
        self.v0 = icm_v(n, x0)
        lo = max(0.0, x0 - 0.02)
        hi = min(1.0, x0 + 0.02)
        self.d = (icm_v(n, hi) - icm_v(n, lo)) / max(1e-9, hi - lo)

    def __call__(self, n2, x):
        return LAM * icm_v(n2, x) + (1 - LAM) * (self.v0 + self.d * (x - self.x0))


def eq_vs(cls, frac):
    i = int(frac * 100 + 0.5)
    if i < 1:
        i = 1
    elif i > 100:
        i = 100
    return EQTOP[cls][i]


class Stat:
    __slots__ = ("hands", "vpip", "pfr", "fr_opp", "fr_fold", "pf_bet_opp", "pf_fold", "agg", "pas", "shove",
                 "big", "sh_hands", "sh_big")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.fr_opp = 0
        self.fr_fold = 0
        self.pf_bet_opp = 0
        self.pf_fold = 0
        self.agg = 0
        self.pas = 0
        self.shove = 0
        self.big = 0
        self.sh_hands = 0
        self.sh_big = 0

    def vpip_rate(self):
        return (self.vpip + 0.3 * 6) / (self.hands + 6)

    def pfr_rate(self):
        return (self.pfr + 0.18 * 6) / (self.hands + 6)

    def fold_to_raise(self):
        return (self.fr_fold + 0.6 * 5) / (self.fr_opp + 5)

    def fold_to_bet(self):
        return (self.pf_fold + 0.45 * 5) / (self.pf_bet_opp + 5)

    def big_rate(self, prior, short):
        if short:
            return (self.sh_big + prior * 6) / (self.sh_hands + 6)
        return (self.big + prior * 8) / (self.hands + 8)

    def aggression(self):
        return (self.agg + 1.0 * 3) / (self.pas + self.agg + 6)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.pre = self.var.pre
        self.points = config.get("points") or [100, 45, 20, 8, 0, 0, 0, 0]
        self.stats = {}
        self.prev_stacks = None
        self.start_stack = config.get("starting_stack", 2000)

    def st(self, seat):
        s = self.stats.get(seat)
        if s is None:
            s = self.stats[seat] = Stat()
        return s

    # ------------------------------------------------------------------ act
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

    # ------------------------------------------------------------- preflop
    def call_range(self, seat, my_total_bb, opp_total_bb, is_bb):
        """Estimated fraction of hands `seat` calls an all-in of size my_total_bb with."""
        risk = min(my_total_bb, opp_total_bb)
        base = 1.6 / max(1.0, risk) ** 0.75
        if is_bb:
            base *= 1.5
        s = self.stats.get(seat)
        if s is not None:
            base *= 0.6 + 1.4 * s.vpip_rate()
        return min(0.75, max(0.04, base))

    def risk_margin(self, sp, obs):
        n = sp.n_alive
        if n == 5:
            return 0.035
        if n <= 4:
            return 0.015
        return 0.0

    def shove_ev(self, sp, obs, cls):
        bb = sp.bb
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_bet = sp.bet
        my_total = sp.stack + my_bet
        pot0 = sp.pot
        bbseat = obs["bb_seat"]
        p_reach = 1.0
        ev = 0.0
        T = float(sum(stacks) + pot0)
        n = len(obs["alive"])
        S = sp.stack
        u = Util(n, S / T)
        v_fold = u(n, S / T)
        for s in sp.behind + [x for x in sp.opps if x not in sp.behind and stacks[x] > 0]:
            if stacks[s] <= 0:
                continue
            t_i = stacks[s] + bets[s]
            c = self.call_range(s, my_total / bb, t_i / bb, s == bbseat)
            if bets[s] > bb:  # a limper/raiser behind already has chips in: calls wider
                c = min(0.8, c * 1.3)
            M = min(my_total, t_i)
            potc = pot0 - my_bet - bets[s] + 2 * M
            e = eq_vs(cls, c)
            lose = S - (M - my_bet)
            v_w = u(n - 1 if t_i <= my_total else n, (lose + potc) / T)
            v_l = u(n, lose / T)
            ev += p_reach * c * (e * v_w + (1 - e) * v_l - v_fold)
            p_reach *= (1 - c)
        ev += p_reach * (u(n, (S + pot0) / T) - v_fold)
        return ev, my_total - my_bet

    def call_ok(self, sp, obs, eq, opp):
        """ICM check for calling (all-in or committing) with equity eq vs seat opp."""
        stacks = obs["stacks"]
        T = float(sum(stacks) + sp.pot)
        n = len(obs["alive"])
        S = sp.stack
        matched = min(sp.to_call, S)
        excess = sp.to_call - matched
        t_o = stacks[opp] + obs["bets"][opp] if opp >= 0 else 0
        opp_bust = opp >= 0 and t_o <= S + sp.bet
        u = Util(n, S / T)
        v_fold = u(n, S / T)
        v_w = u(n - 1 if opp_bust and stacks[opp] == 0 else n, (S + sp.pot - excess) / T)
        v_l = u(n, (S - matched) / T)
        return eq * v_w + (1 - eq) * v_l > v_fold

    def preflop(self, sp, obs):
        cls = self.pre.cls(sp.hole[0], sp.hole[1])
        pct = PCT[cls]
        bb = sp.bb
        stacks = obs["stacks"]
        hist = obs["history"]
        eff_bb = sp.eff_bb
        n_behind = len(sp.behind)
        limpers = sum(1 for h in hist if h[0] == 0 and h[2] == "call")
        margin = self.risk_margin(sp, obs)

        if sp.raises == 0:
            # unopened (maybe limpers) or BB option
            if eff_bb <= 13 or (eff_bb <= 18 and pct > 0.06):
                ev, risk = self.shove_ev(sp, obs, cls)
                if ev > 0:
                    return act_allin(sp)
                if eff_bb <= 13 or pct > 0.45:
                    return act_fold(sp) if sp.to_call > 0 else {"action": "check"}
            # open-raise ranges by players behind
            base = {0: 0.0, 1: 0.55, 2: 0.38, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.15}.get(n_behind, 0.13)
            if sp.role == "BB":
                base = 0.10
            # behind folds a lot -> widen
            if sp.behind:
                fr = sum(self.st(s).fold_to_raise() for s in sp.behind) / len(sp.behind)
                base *= 0.6 + 0.7 * fr / 0.6 * 0.6 + 0.0
            base *= 0.85 ** limpers
            # steal: raise any non-trash hand when the players behind fold enough
            if limpers == 0 and sp.role != "BB" and sp.behind and pct > base and pct <= 0.8:
                p_af = 1.0
                for s in sp.behind:
                    p_af *= self.st(s).fold_to_raise()
                size = (2.8 if sp.role == "SB" else 2.4) * bb
                be = size / (size + sp.pot)
                if p_af >= be - 0.05:
                    base = pct
            if pct <= base:
                size = (2.4 + 1.0 * limpers) * bb
                if sp.role == "SB":
                    size = 2.8 * bb
                if size > 0.4 * (sp.stack + sp.bet):
                    return act_allin(sp)
                return act_raise(sp, size)
            if sp.to_call == 0:
                return {"action": "check"}
            # SB completing / limping is rarely good: fold
            if sp.role == "SB" and pct < 0.6 and limpers > 0 and sp.to_call <= 0.5 * bb:
                return act_call(sp)
            return act_fold(sp)

        # facing raise(s)
        raiser = sp.raiser
        rs = self.st(raiser)
        to_call = sp.to_call
        pot = sp.pot
        req = to_call / float(pot + to_call)
        raiser_allin = stacks[raiser] == 0
        n_raises = sp.raises
        pfr = rs.pfr_rate()
        raise_to = max(obs["bets"])
        if n_raises == 1 and raise_to >= 7 * bb:
            # big raise / shove: range from depth, position, observed frequency
            t_r = (stacks[raiser] + obs["bets"][raiser]) / float(bb)
            prior = 2.0 / max(1.0, t_r) ** 0.8
            pos_behind = 0
            order = sp.order
            if raiser in order:
                pos_behind = len(order) - 1 - order.index(raiser)
            prior *= {1: 1.4, 2: 1.15, 3: 1.0, 4: 0.9}.get(pos_behind, 0.8)
            prior = min(0.75, max(0.05, prior))
            r = min(0.8, max(0.05, rs.big_rate(prior, t_r <= 25)))
        elif n_raises == 1:
            r = min(0.7, max(0.07, pfr * 1.1))
        elif n_raises == 2:
            r = min(0.35, max(0.04, pfr * 0.45))
        else:
            r = min(0.2, max(0.03, pfr * 0.25))
        # multiway: other players who called the raise
        n_in = len(sp.opps)
        e = eq_vs(cls, r)
        if n_in > 1:
            e = e ** (1 + 0.55 * (n_in - 1)) * (1 + 0.1 * (n_in - 1))
        my_total = sp.stack + sp.bet
        commit = to_call >= 0.45 * sp.stack or raiser_allin or to_call >= sp.stack
        if commit:
            if self.call_ok(sp, obs, e, raiser):
                return act_allin(sp) if e > 0.55 and sp.can_raise and not raiser_allin else act_call(sp)
            return act_fold(sp)
        # strong hands: re-raise
        value_cut = 0.035 if n_raises == 1 else 0.02
        if pct <= value_cut or (e > 0.58 and pct <= 0.08):
            size = max(obs["bets"]) * (3.2 if not sp.ip else 2.8) + limpers * bb
            if size > 0.35 * my_total or eff_bb < 25:
                return act_allin(sp)
            return act_raise(sp, size)
        # re-shove with medium-short stacks for fold equity
        if eff_bb <= 22 and n_raises == 1 and n_in == 1:
            fold_p = min(0.8, max(0.2, rs.fold_to_raise() * 0.8))
            q = r * (1 - fold_p)
            eqc = eq_vs(cls, max(0.03, q))
            t_r = stacks[raiser] + obs["bets"][raiser]
            M = min(my_total, t_r)
            potc = pot - sp.bet - obs["bets"][raiser] + 2 * M
            T = float(sum(stacks) + pot)
            n = len(obs["alive"])
            S = sp.stack
            u = Util(n, S / T)
            v_fold = u(n, S / T)
            lose = S - (M - sp.bet)
            ev = fold_p * u(n, (S + pot) / T) + (1 - fold_p) * (
                eqc * u(n - 1 if t_r <= my_total else n, (lose + potc) / T) + (1 - eqc) * u(n, lose / T))
            if ev > v_fold and pct < 0.35:
                return act_allin(sp)
        # call
        realize = 0.92 if sp.ip else 0.82
        if eff_bb > 40:
            realize += 0.04
        if e * realize >= req + 0.02 and pct <= 0.45:
            return act_call(sp)
        return act_fold(sp)

    # ------------------------------------------------------------ postflop
    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        nb = len(sp.board)
        unseen = 36 - 2 - nb
        k = 5 - nb
        p_hit = 0.0
        if outs > 0 and k > 0:
            miss = 1.0
            for j in range(k):
                miss *= 1.0 - outs / float(unseen - j)
            p_hit = 1.0 - miss
        n_opp = max(1, sp.n_opp)
        # board dangers features() misses
        bm = 0
        bsu = [0, 0, 0, 0]
        for c in sp.board:
            bm |= 1 << (c >> 2)
            bsu[c & 3] += 1
        sd = 0
        for w in _WINDOWS:
            x = (bm & w).bit_count()
            if x > sd:
                sd = x
        paired = bm.bit_count() < nb
        fl = max(bsu)
        if cat < STRAIGHT and cat > HIGH:
            if sd >= 4:
                s -= 0.12 if cat == PAIR else 0.18
            elif sd >= 3 and nb == 5:
                s -= 0.03
            if fl >= 4:
                s -= 0.15
            elif fl >= 3 and cat == TWO_PAIR:
                s -= 0.06
            elif fl >= 3 and cat == PAIR:
                s -= 0.04
            if cat == TRIPS and paired:
                hr = [c >> 2 for c in sp.hole]
                if hr[0] != hr[1]:
                    kick = hr[1] if bm >> hr[0] & 1 else hr[0]
                    if kick < 8:
                        s -= 0.07
        elif cat == STRAIGHT:
            if paired:
                s -= 0.07
                if nb - bm.bit_count() >= 2:
                    s -= 0.15
            if fl >= 4:
                s -= 0.15
        if s < 0.02:
            s = 0.02
        made = s ** (1.0 + (0.7 - 0.6 * max(0.0, s - 0.6)) * (n_opp - 1))
        eq = made + (1 - made) * p_hit * 0.75
        pot = sp.pot
        to_call = sp.to_call
        stack = sp.stack
        hist = obs["history"]
        pf_aggr = -1
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                pf_aggr = h[1]
        i_aggr = pf_aggr == self.seat
        spr = stack / float(max(1, pot))
        opp_raised_post = False
        barrels = 0
        bettor = sp.raiser
        seen_st = set()
        raised_on = set()
        for h in hist:
            if h[0] >= 1 and h[2] == "raise":
                if h[1] != self.seat:
                    if h[0] < sp.street and h[1] == bettor and h[0] not in seen_st:
                        seen_st.add(h[0])
                        barrels += 1
                    # an opponent raising over someone's bet
                    if h[0] in raised_on:
                        opp_raised_post = True
                raised_on.add(h[0])

        if to_call == 0:
            if eq >= 0.72:
                frac = 0.75 if wet or nb == 5 else 0.6
                if eq >= 0.85:
                    frac = 0.85
                return self.bet_pot(sp, frac, eq >= 0.8)
            if eq >= 0.58 and (n_opp == 1 or sp.ip) and not opp_raised_post:
                return self.bet_pot(sp, 0.5, False)
            # c-bet / bluff
            if n_opp == 1 and sp.street == 1 and i_aggr:
                opp = sp.opps[0]
                ftb = self.st(opp).fold_to_bet()
                if p_hit > 0.25 or self.rng.random() < ftb * 1.1:
                    return self.bet_pot(sp, 0.45, False)
            if n_opp == 1 and p_hit > 0.3 and sp.street < 3 and self.rng.random() < 0.5:
                return self.bet_pot(sp, 0.55, False)
            if n_opp == 1 and sp.ip and nb == 5 and eq < 0.2:
                opp = sp.opps[0]
                if self.rng.random() < 0.25 * self.st(opp).fold_to_bet() / 0.45:
                    return self.bet_pot(sp, 0.6, False)
            return {"action": "check"}

        # facing a bet
        req = to_call / float(pot + to_call)
        bet_frac = to_call / float(max(1, pot - to_call))
        aggr = 0.5
        if sp.raiser >= 0:
            aggr = self.st(sp.raiser).aggression()
        # opponent betting range is stronger than random: discount
        disc = (0.07 + 0.13 * min(1.5, bet_frac) + 0.07 * barrels) * (1.0, 1.0, 1.15, 1.35)[min(3, sp.street)] * (1.3 - aggr)
        eq_b = made - disc
        if eq_b < 0:
            eq_b = 0.0
        eq_b = eq_b + (1 - eq_b) * p_hit * (0.85 if nb < 5 else 0.0)
        if sp.raises >= 2:
            eq_b -= 0.06
        if eq_b >= 0.76 and sp.can_raise:
            if spr < 2.5:
                return act_allin(sp)
            return act_raise(sp, sp.bet + to_call + 1.0 * (pot + to_call) + to_call)
        if to_call >= stack or to_call >= 0.5 * stack:
            return act_call(sp) if self.call_ok(sp, obs, eq_b, sp.raiser) else act_fold(sp)
        if eq_b >= req + 0.03:
            return act_call(sp)
        return act_fold(sp)

    def bet_pot(self, sp, frac, shove_ok=True):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if shove_ok and sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            return act_allin(sp)
        return act_raise(sp, max(target, sp.min_to))

    # ------------------------------------------------------------- observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            raised = False
            bet_street = {}
            bbv = 0
            for h in hist:
                if h[2] == "bb":
                    bbv = h[3]
            prev = self.prev_stacks
            self.prev_stacks = list(event.get("stacks") or [])
            for st, seat, a, amt in hist:
                if a in ("sb", "bb", "ante", "return"):
                    continue
                s = self.st(seat)
                if st == 0:
                    if seat not in seen and a in ("fold", "check", "call", "raise"):
                        seen.add(seat)
                        s.hands += 1
                        if a in ("call", "raise"):
                            s.vpip += 1
                        if a == "raise":
                            s.pfr += 1
                        start = prev[seat] if prev and seat < len(prev) else self.start_stack
                        short = bbv > 0 and start <= 25 * bbv
                        if short:
                            s.sh_hands += 1
                            if a == "raise" and amt >= 7 * bbv:
                                s.sh_big += 1
                        if raised:
                            s.fr_opp += 1
                            if a == "fold":
                                s.fr_fold += 1
                    if a == "raise" and bbv > 0 and amt >= 7 * bbv:
                        s.big += 1
                    if a == "raise":
                        raised = True
                else:
                    if a == "raise":
                        s.agg += 1
                        bet_street[st] = True
                    elif a == "call":
                        s.pas += 1
                        s.pf_bet_opp += 1
                    elif a == "fold":
                        s.pf_bet_opp += 1
                        s.pf_fold += 1
        except Exception:
            pass
