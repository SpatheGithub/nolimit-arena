"""b05 crazy pineapple bot: precomputed 3-card preflop equities, EV push/fold,
heuristic postflop strength, per-seat opponent stats."""

import json
import os
import random
import time
from itertools import combinations

from ._common import (CARD, Variant, Spot, act_fold, act_call, act_raise, act_allin,
                      features, preflop_pct, safe_default, HIGH, PAIR, TWO_PAIR, TRIPS)

_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_DIR, "pre3.json")) as _f:
        _PRE = json.load(_f)
    EQ1 = _PRE["eq1"]
    PCT = _PRE["pct"]
    RANGES = list(_PRE["ranges"]) + [1.0]
    EQR = list(_PRE["eqr"]) + [EQ1]
except Exception:  # pragma: no cover
    _PRE = None
    EQ1 = PCT = RANGES = EQR = None


def key3(cards):
    cs = sorted(cards, key=lambda c: -(c >> 2))
    r1, r2, r3 = cs[0] >> 2, cs[1] >> 2, cs[2] >> 2
    s1, s2, s3 = cs[0] & 3, cs[1] & 3, cs[2] & 3
    if r1 == r2 == r3:
        pat = 0
    elif r1 == r2:
        pat = 1 if (s3 == s1 or s3 == s2) else 0
    elif r2 == r3:
        pat = 1 if (s1 == s2 or s1 == s3) else 0
    else:
        if s1 == s2 == s3:
            pat = 0
        elif s1 == s2:
            pat = 1
        elif s1 == s3:
            pat = 2
        elif s2 == s3:
            pat = 3
        else:
            pat = 4
    return ((r1 * 13 + r2) * 13 + r3) * 5 + pat


MC_BUDGET = 0.00022
DISC_BUDGET = 0.00025

P = {"push_bb": 16, "open_k": 0.40, "open_exp": 0.6, "three_base": 0.035, "call_base": 0.10,
     "caller_k": 2.0, "w_mult": 0.85, "pr_cap": 4.5, "af_scale": 1, "shove_margin": 0.01, "val_thr": 0.70, "thin_thr": 0.56, "cbet": 0.55,
     "icm_shove": 1, "mw_fix": 0, "sb_limp": 0.60, "sh_k": 0.0, "icm_sm": 0.02, "icm_ce": 0.0, "mc_disc": 0, "open_bb": 2.5, "val_add": 0.0, "auto_steal": 1, "pf_fr": 0, "bb_def": 0.0, "face_pen": 0.14, "face_pen_st": 0.05, "raise_thr": 0.82, "call_margin": 0.05, "deep_guard": 0.08, "vp_floor": 1.0}
try:
    with open(os.path.join(_DIR, "params.json")) as _f:
        P.update(json.load(_f))
except Exception:
    pass


def icm_equity(stacks, payouts):
    """Malmuth-Harville, as kit/icm.py (small n only)."""
    n = len(stacks)
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    memo = {}

    def rest(mask):
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < n and pay[place]:
            total = sum(stacks[i] for i in members)
            for i in members:
                p = stacks[i] / total if total > 0 else 1.0 / len(members)
                if p <= 0:
                    continue
                res[i] += p * pay[place]
                sub = rest(mask & ~(1 << i))
                for j in members:
                    if j != i:
                        res[j] += p * sub[j]
        memo[mask] = res
        return res

    return rest((1 << n) - 1)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class Stats:
    __slots__ = ("hands", "vpip", "pfr", "faced", "ffold", "pagg", "pcall", "pfold", "shoves")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.faced = 0
        self.ffold = 0
        self.pagg = 0
        self.pcall = 0
        self.pfold = 0
        self.shoves = 0

    def vp(self):
        return (self.vpip + 1.0) / (self.hands + 4.0)

    def pr(self):
        return (self.pfr + 0.6) / (self.hands + 4.0)

    def fold_to_raise(self):
        return (self.ffold + 1.2) / (self.faced + 2.0)

    def af(self):
        return (self.pagg + 1.5) / (self.pcall + 1.0)

    def fold_to_bet(self):
        return (self.pfold + 1.0) / (self.pfold + self.pcall + 2.5)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        self.stats = {}
        self.pf_aggr = False

    # ------------------------------------------------------------------ utils
    def st(self, seat):
        s = self.stats.get(seat)
        if s is None:
            s = self.stats[seat] = Stats()
        return s

    def pre_eq_vs(self, key, width):
        """Equity of 3-card class vs a top-`width` range."""
        if EQR is None:
            return 0.5
        width = clamp(width, RANGES[0], 1.0)
        for i in range(len(RANGES) - 1):
            a, b = RANGES[i], RANGES[i + 1]
            if width <= b:
                t = (width - a) / (b - a)
                return EQR[i][key] * (1 - t) + EQR[i + 1][key] * t
        return EQ1[key]

    # -------------------------------------------------------------------- act
    def act(self, obs):
        self.t0 = time.perf_counter()
        try:
            if obs["phase"] == "discard":
                return self.discard(obs)
            sp = Spot(obs, self.var)
            if sp.street == 0:
                return self.preflop(sp, obs)
            return self.postflop(sp, obs)
        except Exception:
            return safe_default(obs)

    def discard(self, obs):
        hole = obs["hole"]
        k = obs.get("n_discard") or 1
        cs = [CARD[c] for c in hole]
        board = [CARD[c] for c in obs.get("board") or []]
        keep = len(cs) - k
        best = None
        bs = -9.0
        keeps = list(combinations(range(len(cs)), keep))
        hs = []
        for ix in keeps:
            kept = [cs[i] for i in ix]
            if board:
                s, outs, _, _ = features(self.var, kept, board)
                sc = s + 0.03 * outs
            else:
                sc = -preflop_pct(self.var, kept)
            hs.append(sc)
            if sc > bs:
                bs = sc
                best = ix
        if P['mc_disc'] and len(board) == 3 and keep == 2 and len(keeps) > 1:
            try:
                ix = self.mc_discard(obs, cs, board, keeps, hs)
                if ix is not None:
                    best = ix
            except Exception:
                pass
        return {"action": "discard", "cards": [hole[i] for i in range(len(hole)) if i not in best]}

    def mc_discard(self, obs, cs, board, keeps, hs):
        t0 = self.t0
        known = set(cs)
        known.update(board)
        deck = [c for c in range(52) if c not in known]
        n_opp = min(2, max(1, len(obs.get("in_hand") or []) - 1))
        kk = 2 + 3 * n_opp
        kl = [[cs[i] for i in ix] for ix in keeps]
        nk = len(kl)
        wins = [0.0] * nk
        sample = self.rng.sample
        val = self.var.ranker.value
        clock = time.perf_counter
        n = 0
        while n < 200:
            cards = sample(deck, kk)
            b = board + cards[:2]
            top = val(cards[2:5] + b)
            if n_opp > 1:
                v2 = val(cards[5:8] + b)
                if v2 > top:
                    top = v2
            for j in range(nk):
                hv = val(kl[j] + b)
                if hv > top:
                    wins[j] += 1.0
                elif hv == top:
                    wins[j] += 0.5
            n += 1
            if (n & 7) == 0 and clock() - t0 > DISC_BUDGET:
                break
        if n < 24:
            return None
        bj = max(range(nk), key=lambda j: wins[j] / n + 0.02 * hs[j])
        return keeps[bj]

    # --------------------------------------------------------------- preflop
    def preflop(self, sp, obs):
        hole = sp.hole
        if len(hole) == 3 and PCT is not None:
            key = key3(hole)
            pct = PCT[key]
        else:
            key = None
            pct = preflop_pct(self.var, hole)
        bb = sp.bb
        me = sp.me
        stack = sp.stack
        n_behind = len(sp.behind)
        n_alive = sp.n_alive
        # chips posted by others / pot
        pot = sp.pot
        to_call = sp.to_call
        my_total = stack + sp.bet
        eff_bb = sp.eff_bb
        raises = sp.raises
        raiser = sp.raiser
        self.pf_aggr = False

        # ICM-ish tightness when few players left
        icm_m = 0.0
        if n_alive <= 5 and n_alive >= 3:
            avg = sum(obs["stacks"]) / max(1, n_alive)
            icm_m = 0.02 + (0.02 if my_total < avg else 0.0)

        if raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= P['push_bb'] or my_total <= P['push_bb'] * bb:
                return self.push_or_fold(sp, obs, key, pct, icm_m)
            limpers = sp.callers
            if sp.can_check:
                # big blind option
                if pct <= 0.12:
                    self.pf_aggr = True
                    return act_raise(sp, sp.bet + (3 + limpers) * bb)
                return act_call(sp)
            steal_bonus = 0.0
            if n_behind <= 3 and limpers == 0:
                fr = [self.st(s).fold_to_raise() for s in sp.behind]
                if fr:
                    steal_bonus = clamp((min(fr) - 0.6) * 0.5, -0.05, 0.12)
            thr = P['open_k'] / max(1, n_behind) ** P['open_exp'] * (1 + P['sh_k'] * max(0, 8 - n_alive)) + steal_bonus
            thr = min(thr, 0.9)
            if limpers:
                thr *= 0.75
            size = (P['open_bb'] if eff_bb > 30 else 2.2) * bb + limpers * bb
            if pct <= thr:
                self.pf_aggr = True
                return act_raise(sp, size)
            if P['auto_steal'] and limpers == 0 and sp.behind:
                pf = 1.0
                for o in sp.behind:
                    so = self.st(o)
                    pf *= so.fold_to_raise() if so.faced >= 4 else 0.5
                risk = size - sp.bet
                if pf * sp.pot > (1.0 - pf) * risk * 1.1:
                    self.pf_aggr = True
                    return act_raise(sp, size)
            if sp.role == "SB" and limpers == 0 and pct <= P['sb_limp'] and eff_bb > 25:
                return act_call(sp)
            return act_fold(sp)

        # facing raise(s)
        rs = self.st(raiser) if raiser >= 0 else Stats()
        raiser_total = obs["stacks"][raiser] + obs["bets"][raiser] if raiser >= 0 else 0
        raiser_allin = raiser >= 0 and obs["stacks"][raiser] == 0
        cost_frac = to_call / max(1, stack)
        # treat as all-in decision if raise commits a big fraction of stacks
        if raiser_allin or cost_frac >= 0.35 or eff_bb <= 14:
            return self.call_or_shove(sp, obs, key, pct, icm_m, rs, raiser_total)
        # deep stack, facing a raise
        open_w = clamp(rs.pr() * 1.3, 0.06, 0.6)
        if raises >= 2:
            open_w = clamp(open_w * 0.4, 0.03, 0.25)
        three_thr = clamp(P['three_base'] + 0.25 * (open_w - 0.12), 0.025, 0.12)
        if raises >= 2:
            three_thr = 0.02
        call_thr = clamp(P['call_base'] + 0.6 * (open_w - 0.12), 0.05, 0.28)
        if raises >= 2:
            call_thr = clamp(open_w * 0.4, 0.03, 0.08)
        # pot odds better in BB
        odds = to_call / (pot + to_call)
        if odds < 0.25:
            call_thr *= 1.3
        if not sp.ip and sp.role != "BB":
            call_thr *= 0.85
        call_thr *= 1 + P['sh_k'] * max(0, 8 - n_alive)
        three_thr *= 1 + 0.5 * P['sh_k'] * max(0, 8 - n_alive)
        if P['bb_def'] and sp.role == "BB" and raises == 1 and odds < 0.3:
            call_thr = max(call_thr, P['bb_def'])
        call_thr = max(0.0, min(0.6, call_thr) - icm_m)
        if pct <= three_thr:
            self.pf_aggr = True
            cur = obs["bets"][raiser] if raiser >= 0 else to_call + sp.bet
            target = cur * (3.0 if sp.ip else 3.5) + sp.callers * cur
            if target - sp.bet >= 0.4 * stack:
                return act_allin(sp)
            return act_raise(sp, target)
        if pct <= call_thr:
            return act_call(sp)
        return act_fold(sp)

    def caller_width(self, s_bb, seats):
        base = clamp(P['caller_k'] / (s_bb + 2.0), 0.05, 0.5)
        if seats:
            vp = sum(self.st(s).vp() for s in seats) / len(seats)
            base *= clamp(vp / 0.30, P['vp_floor'], 1.8)
        return clamp(base, 0.04, 0.7)

    def push_or_fold(self, sp, obs, key, pct, icm_m):
        bb = sp.bb
        stack = sp.stack
        behind = sp.behind
        bets = obs["bets"]
        stacks = obs["stacks"]
        # effective shove amount vs the biggest stack behind
        biggest = max([stacks[s] + bets[s] for s in behind], default=0)
        risk = min(stack, max(0, biggest - sp.bet))
        if not behind:
            return act_call(sp) if sp.can_check else act_fold(sp)
        s_bb = (stack + sp.bet) / bb
        c = self.caller_width(min(s_bb, biggest / bb), behind)
        p_nocall = 1.0
        for s in behind:
            c_s = c
            # players who'd have to call off a big fraction are tighter
            st_s = stacks[s] + bets[s]
            if st_s < stack + sp.bet:
                c_s = clamp(c * 1.2, 0.04, 0.8)
            if P['pf_fr']:
                so = self.st(s)
                if so.faced >= 4:
                    c_s = clamp(0.5 * c_s + 0.5 * (1.0 - so.fold_to_raise()) * c_s / 0.4, 0.02, 0.8)
            p_nocall *= (1 - c_s)
        if key is not None:
            e = self.pre_eq_vs(key, c)
        else:
            e = 0.65 - 0.4 * pct
        p0 = sp.pot
        win_pot = p0 + 2 * risk
        ev_shove = p_nocall * p0 + (1 - p_nocall) * (e * win_pot - risk) - (1 - p_nocall) * 0.0
        margin = (icm_m + P['shove_margin']) * risk
        go = ev_shove > margin
        if P['icm_shove'] and 3 <= sp.n_alive <= 5:
            try:
                d = self.icm_shove(sp, obs, p_nocall, e)
                if d is not None:
                    go = d > P['icm_sm']
            except Exception:
                pass
        if go:
            self.pf_aggr = True
            return act_allin(sp)
        if sp.can_check:
            return act_call(sp)
        # SB complete cheaply with decent hands when very short
        if sp.to_call <= 0.5 * bb and pct < 0.35 and stack > 3 * bb:
            return act_call(sp)
        return act_fold(sp)

    def call_or_shove(self, sp, obs, key, pct, icm_m, rs, raiser_total):
        bb = sp.bb
        stack = sp.stack
        to_call = sp.to_call
        r_bb = raiser_total / bb
        # estimate raiser range width
        w = clamp(0.08 + 2.0 / (r_bb + 4.0), 0.05, 0.7)
        w *= clamp(rs.pr() / 0.18, 0.6, P['pr_cap'])
        if sp.raises >= 2:
            w *= 0.6
        w = clamp(w * P['w_mult'], 0.03, 0.85)
        if key is not None:
            e = self.pre_eq_vs(key, w)
        else:
            e = 0.65 - 0.4 * pct
        # others already in or behind reduce equity
        if P['mw_fix']:
            if sp.callers:
                e *= 0.85 ** sp.callers
            if sp.behind:
                e *= 1.0 - 0.025 * len(sp.behind)
        else:
            extra = max(0, sp.n_opp - 1)
            if extra:
                e *= 0.85 ** extra
        pot = sp.pot
        call_amt = min(to_call, stack)
        need = call_amt / (pot + call_amt)
        commit = call_amt / max(1, stack + sp.bet)
        tax = icm_m * (1.0 if commit > 0.5 else 0.5)
        n_alive = sp.n_alive
        if 2 <= n_alive <= 5 and sp.raiser >= 0 and sp.callers == 0:
            try:
                need_icm = self.icm_need(sp, obs, call_amt)
                if need_icm is not None:
                    need = need_icm + P['icm_ce']
                    tax = 0.0
            except Exception:
                pass
        # reshove if strong and we can and opponents can still fold
        if sp.can_raise and e > need + 0.12 + tax and pct <= 0.08:
            return act_allin(sp)
        if e >= need + tax:
            return act_call(sp)
        return act_fold(sp)

    def icm_shove(self, sp, obs, p_nocall, e):
        """ICM gain (points) of open-shoving vs folding."""
        alive = obs["alive"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        me = sp.me
        behind = sp.behind
        if not behind:
            return None
        bbs = obs["bb_seat"]
        caller = bbs if bbs in behind else max(behind, key=lambda x: stacks[x] + bets[x])
        pot = sp.pot
        order = list(alive)
        i = order.index(me)
        pay = self.points[:len(order)]
        base = {x: stacks[x] for x in order}
        f = dict(base)
        f[caller] += pot
        stl = dict(base)
        stl[me] += pot
        c_tot = stacks[caller] + bets[caller]
        my_tot = stacks[me] + bets[me]
        matched = min(c_tot, my_tot)
        c_add = max(0, matched - bets[caller])
        my_add = max(0, matched - bets[me])
        fp = pot + c_add + my_add
        w = dict(base)
        w[me] = stacks[me] - my_add + fp
        w[caller] = stacks[caller] - c_add
        lo = dict(base)
        lo[me] = stacks[me] - my_add
        lo[caller] = stacks[caller] - c_add + fp

        def eqv(d):
            return icm_equity([max(0, d[x]) for x in order], pay)[i]

        ev = p_nocall * eqv(stl) + (1 - p_nocall) * (e * eqv(w) + (1 - e) * eqv(lo))
        return ev - eqv(f)

    def icm_need(self, sp, obs, call_amt):
        """Equity needed to call an all-in heads-up under ICM."""
        alive = obs["alive"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        me = sp.me
        r = sp.raiser
        pts = self.points
        n = len(alive)
        payouts = pts[:n]
        pot = sp.pot
        my_in = sp.bet + call_amt
        excess = max(0, bets[r] - my_in)
        pot_eff = pot + call_amt - excess
        base = {s: stacks[s] for s in alive}
        # fold: raiser takes the pot
        f = dict(base)
        f[r] = f[r] + pot
        # win: I take pot_eff, raiser gets excess back
        w = dict(base)
        w[me] = stacks[me] - call_amt + pot_eff
        w[r] = stacks[r] + excess
        # lose: raiser takes everything
        lo = dict(base)
        lo[me] = stacks[me] - call_amt
        lo[r] = stacks[r] + pot + call_amt
        # other committed chips (dead money from folded blinds) already in pot
        order = list(alive)
        i = order.index(me)

        def eqv(d):
            return icm_equity([max(0, d[s]) for s in order], payouts)[i]

        ef, ew, el = eqv(f), eqv(w), eqv(lo)
        if ew - el <= 1e-9:
            return None
        return clamp((ef - el) / (ew - el), 0.0, 1.0)

    # -------------------------------------------------------------- postflop
    def hand_strength(self, sp):
        hole = sp.hole
        board = sp.board
        var = self.var
        if len(hole) == 3:
            best = (-1.0, 0, False, HIGH)
            bsc = -9.0
            for sub in ((hole[0], hole[1]), (hole[0], hole[2]), (hole[1], hole[2])):
                f = features(var, list(sub), board)
                sc = f[0] + 0.03 * f[1]
                if sc > bsc:
                    bsc = sc
                    best = f
            s, outs, wet, cat = best
        else:
            s, outs, wet, cat = features(var, hole, board)
        # crazy pineapple: opponents hold stronger hands than in hold'em
        if cat == PAIR:
            s *= 0.86
        elif cat == TWO_PAIR:
            s *= 0.93
        elif cat == TRIPS:
            s *= 0.97
        elif cat == HIGH:
            s *= 0.8
        return s, outs, wet, cat

    def mc_equity(self, sp, t0):
        """Monte Carlo equity vs random 3-card holdings (best 5 of hole+board,
        hindsight for both sides on the flop), wall-time boxed."""
        hole = sp.hole
        board = sp.board
        known = set(hole)
        known.update(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        n_sim = min(max(1, sp.n_opp), 3)
        k = need + 3 * n_sim
        sample = self.rng.sample
        val = self.var.ranker.value
        clock = time.perf_counter
        wins = 0.0
        n = 0
        fixed = hole + board if need == 0 else None
        hv0 = val(fixed) if fixed is not None else 0
        while n < 300:
            cards = sample(deck, k)
            if need:
                b = board + cards[:need]
                hv = val(hole + b)
            else:
                b = board
                hv = hv0
            top = -1
            ties = 0
            for i in range(need, k, 3):
                ov = val(cards[i:i + 3] + b)
                if ov > top:
                    top = ov
                    ties = 1 if ov == hv else 0
                elif ov == hv:
                    ties += 1
            if hv > top:
                wins += 1.0
            elif hv == top:
                wins += 1.0 / (1 + ties)
            n += 1
            if (n & 7) == 0 and clock() - t0 > MC_BUDGET:
                break
        eq = wins / max(1, n)
        if sp.n_opp > n_sim:
            eq = eq ** (sp.n_opp / n_sim)
        return eq, n

    def postflop(self, sp, obs):
        t0 = self.t0
        s, outs, wet, cat = self.hand_strength(sp)
        n_opp = max(1, sp.n_opp)
        eq_h = s ** (n_opp ** 0.75)
        eq_mc, n_mc = self.mc_equity(sp, t0)
        if n_mc >= 16:
            w = 0.65 if n_mc >= 40 else 0.5
            eq = w * eq_mc + (1 - w) * eq_h
        else:
            eq = eq_h
        street = sp.street
        if street == 1:
            draw = min(0.45, outs * 0.04)
        elif street == 2:
            draw = min(0.25, outs * 0.021)
        else:
            draw = 0.0
        pot = sp.pot
        to_call = sp.to_call
        stack = sp.stack
        spr = stack / max(1, pot)
        rng = self.rng
        if sp.can_check:
            # fold-to-bet tendency of the opponents still in
            ftb = 1.0
            for o in sp.opps:
                ftb *= self.st(o).fold_to_bet()
            station = ftb < 0.25
            if eq >= P['val_thr']:
                frac = (0.75 if wet else 0.6) + P['val_add']
                if station:
                    frac += 0.2
                if spr < 1.5:
                    return act_allin(sp)
                return self.bet_frac(sp, frac)
            if eq >= P['thin_thr'] and n_opp <= 2:
                return self.bet_frac(sp, 0.5)
            bluff_m = clamp(ftb / 0.45, 0.3, 1.6)
            if draw >= 0.28 and n_opp <= 2 and rng.random() < 0.6 * bluff_m:
                return self.bet_frac(sp, 0.6)
            if self.pf_aggr and street == 1 and n_opp == 1 and rng.random() < P['cbet'] * bluff_m:
                return self.bet_frac(sp, 0.4)
            if street == 3 and n_opp == 1 and sp.ip and eq < 0.2 and rng.random() < 0.15 * bluff_m:
                return self.bet_frac(sp, 0.6)
            return act_call(sp)
        # facing a bet
        bettor = sp.raiser
        bfrac = to_call / max(1, pot - to_call)
        aggr_adj = 0.0
        pm = 1.0
        if bettor >= 0:
            af = self.st(bettor).af()
            aggr_adj = clamp((af - 1.5) * 0.04, -0.06, 0.08)
            if P['af_scale']:
                pm = clamp(1.5 / af, 0.35, 1.3)
        eq_b = eq - (P['face_pen'] + P['face_pen_st'] * street) * clamp(bfrac, 0.2, 2.0) * pm + aggr_adj
        if sp.raises >= 2:
            eq_b -= 0.10
        need = to_call / (pot + to_call)
        call_amt = min(to_call, stack)
        if eq_b >= P['raise_thr'] and sp.can_raise:
            if spr < 2.5 or call_amt > 0.4 * stack:
                return act_allin(sp)
            return act_raise(sp, sp.bet + to_call + 1.0 * (pot + to_call) + to_call)
        total = eq_b + (draw * 0.9 if street < 3 else 0.0)
        guard = 0.0
        if call_amt > 0.35 * (stack + sp.bet) and sp.eff_bb > 25:
            guard = P['deep_guard']
        if total >= need + P['call_margin'] + guard:
            return act_call(sp)
        return act_fold(sp)

    def bet_frac(self, sp, frac):
        target = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        if sp.stack + sp.bet - target < 0.3 * (sp.pot + 2 * (target - sp.bet)):
            return act_allin(sp)
        return act_raise(sp, target)

    # --------------------------------------------------------------- observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            raised = False
            faced = set()
            ffold = set()
            for h in hist:
                st, seat, act, amt = h[0], h[1], h[2], h[3]
                if act in ("ante", "return", "discard"):
                    if act != "return":
                        seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0:
                    if act in ("sb", "bb"):
                        continue
                    if raised and seat not in pr and seat not in faced:
                        faced.add(seat)
                        if act == "fold":
                            ffold.add(seat)
                    if act == "call":
                        vp.add(seat)
                    elif act == "raise":
                        vp.add(seat)
                        pr.add(seat)
                        raised = True
                else:
                    s = self.st(seat)
                    if act == "raise":
                        s.pagg += 1
                    elif act == "call":
                        s.pcall += 1
                    elif act == "fold":
                        s.pfold += 1
            for seat in seen:
                s = self.st(seat)
                s.hands += 1
                if seat in vp:
                    s.vpip += 1
                if seat in pr:
                    s.pfr += 1
                if seat in faced:
                    s.faced += 1
                    if seat in ffold:
                        s.ffold += 1
        except Exception:
            pass
