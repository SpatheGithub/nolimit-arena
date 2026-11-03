import json
import os
import random
from itertools import combinations

from .common import (CARD, Variant, Spot, act_fold, act_call, act_raise, act_allin, act_pot,
                     safe_default, features, preflop_pct, HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT,
                     FLUSH)

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_pre3():
    p = os.path.join(_DIR, "pre3.json")
    try:
        with open(p) as f:
            d = json.load(f)
        combo = {}
        for k, v in d["combo"].items():
            a, b, c = k.split(",")
            combo[(int(a), int(b), int(c))] = v
        return combo, d["pct"], d["eq"], d["ks"]
    except Exception:
        return None


PRE3 = _load_pre3()
CALL_TIGHT = 0.75
BLUFF = 0.5
OPEN_K = 1.0
SHOVE_EV = 0.05
PF_DISC = 0.12
MW_DISC = 0.07
PREM = {2: 0.0, 3: 0.071, 4: 0.105, 5: 0.117, 6: 0.113, 7: 0.117, 8: 0.124}
PREM_K = 1.0
POST_PREM = 1.0
BIG_BUMP = 0.05
BET_DISC = 0.02


def _load_pre3r():
    try:
        with open(os.path.join(_DIR, "pre3r.json")) as f:
            d = json.load(f)
        return d["buckets"], d["eqr"]
    except Exception:
        return None


PRE3R = _load_pre3r()


def eq_vs_range(ci, x, eq1):
    """Equity of class ci vs one opponent holding a top-x fraction hand."""
    if PRE3R is None or ci is None:
        return max(0.2, min(0.85, eq1 - 0.25 * (1 - x)))
    bk, eqr = PRE3R
    row = eqr[ci]
    if x <= bk[0]:
        return row[0]
    for i in range(1, len(bk)):
        if x <= bk[i]:
            t = (x - bk[i - 1]) / (bk[i] - bk[i - 1])
            return row[i - 1] + t * (row[i] - row[i - 1])
    return row[-1]


class Agent:
    def __init__(self, config):
        self.seat = config.get("seat", 0)
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        # opponent stats: seat -> [hands, vpip, pfr, aggr_actions, passive_actions, folds_to_bet, faced_bet]
        self.stats = {}
        self.shove_resp = {}  # seat -> [faced preflop all-in, called]
        self.ftb = {}  # seat -> [faced our postflop bet, folded]

    # ---------------------------------------------------------------- utils
    def pre_info(self, hole):
        """(pct 0=best, eq vs 1 random, class idx) for a 3-card (or 2-card) hole."""
        if PRE3 is not None and len(hole) == 3:
            combo, pct, eq, ks = PRE3
            key = tuple(sorted(hole))
            ci = combo.get(key)
            if ci is not None:
                return pct[ci], eq[ci][0], ci
        p = preflop_pct(self.var, hole)
        return p, 0.65 - 0.3 * p, None

    def icm_pen(self, sp):
        """Extra required equity for risking our stack (ICM / survival value)."""
        n = sp.n_alive
        if n <= 2:
            return 0.0
        return {3: 0.04, 4: 0.035, 5: 0.03}.get(n, 0.02)

    def icm_prem(self, sp, me_tot, o_tot):
        base = PREM.get(sp.n_alive, 0.12) * PREM_K
        if me_tot <= 0 or o_tot <= 0:
            return base
        if o_tot < me_tot:
            f = (o_tot / me_tot) ** 1.15
        else:
            f = 0.44 + 0.56 * (me_tot / o_tot)
        return base * f

    def call_range_est(self, seat, e_req):
        """Fraction of hands an opponent calls a shove with, given the equity they need."""
        y = 0.20 - 1.0 * (e_req - 0.40)
        vp, pf = self.looseness(seat)
        y *= max(0.6, min(1.8, vp / 0.25))
        r = self.shove_resp.get(seat)
        if r and r[0]:
            y = (3.0 * y + r[1]) / (3.0 + r[0])
        return max(0.04, min(0.7, y))

    def shove_range_est(self, seat, eff_bb, nb):
        x = 6.0 / (max(eff_bb, 1.0) * max(1, nb) ** 0.75)
        vp, pf = self.looseness(seat)
        x *= max(0.6, min(2.5, pf / 0.15))
        return max(0.05, min(0.85, x))

    def shove_ev(self, sp, ci, eq1):
        """Chip EV (relative to folding) of shoving now, plus risk-weighted EV."""
        pot0 = sp.pot
        me_tot = sp.stack + sp.bet
        p_all_fold = 1.0
        ev_called = 0.0
        p_reach = 1.0
        stacks, bets = sp.stacks, sp.bets
        for s in sp.behind:
            o_tot = stacks[s] + bets[s]
            m = min(me_tot, o_tot)
            call_amt = m - bets[s]
            if call_amt <= 0:
                continue
            final_pot = pot0 + (m - sp.bet) + call_amt
            e_req = call_amt / (pot0 + (m - sp.bet) + call_amt)
            y = self.call_range_est(s, e_req)
            e = eq_vs_range(ci, y, eq1)
            risk = m - sp.bet
            pen = self.icm_prem(sp, me_tot, o_tot) * final_pot
            ev_called += p_reach * y * (e * final_pot - risk - pen)
            p_reach *= (1 - y)
        p_all_fold = p_reach
        return p_all_fold * pot0 + ev_called

    def st(self, seat):
        s = self.stats.get(seat)
        if s is None:
            s = self.stats[seat] = [0, 0, 0, 0, 0, 0, 0]
        return s

    def looseness(self, seat):
        s = self.stats.get(seat)
        if not s or s[0] < 8:
            return 0.25, 0.15
        return s[1] / s[0], s[2] / s[0]

    def aggression(self, seat):
        s = self.stats.get(seat)
        if not s or s[3] + s[4] < 6:
            return 1.0
        return (s[3] + 0.5) / (s[4] + 0.5)

    # ---------------------------------------------------------------- act
    def act(self, obs):
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
        keep_n = len(hole) - k
        cs = [CARD[c] for c in hole]
        board = [CARD[c] for c in obs.get("board") or []]
        best = None
        bscore = -1e9
        left = 2 if len(board) <= 3 else 1
        for ix in combinations(range(len(cs)), keep_n):
            kept = [cs[i] for i in ix]
            s, outs, wet, cat = features(self.var, kept, board)
            score = s + outs * (0.035 if left == 2 else 0.02)
            # small tie-break for high cards / suitedness
            score += 0.001 * sum(c >> 2 for c in kept)
            if score > bscore:
                bscore = score
                best = ix
        return {"action": "discard", "cards": [hole[i] for i in range(len(hole)) if i not in best]}

    # ---------------------------------------------------------------- preflop
    def preflop(self, sp, obs):
        hole = sp.hole
        pct, eq1, ci = self.pre_info(hole)
        bb = sp.bb
        me = obs["seat"]
        stack_tot = sp.stack + sp.bet
        eff_bb = sp.eff_bb
        n_behind = len(sp.behind)
        raises = sp.raises
        n_alive = sp.n_alive
        to_call = sp.to_call
        pot = sp.pot
        if raises == 0:
            limpers = sp.callers
            if eff_bb <= 14 or (stack_tot / bb) <= 14:
                # push / fold by chip EV with an ICM penalty
                if not sp.behind and sp.can_check:
                    # BB vs limpers/complete: shove strong, else check
                    if pct <= min(0.3, 3.0 / max(1.0, eff_bb)):
                        return act_allin(sp)
                    return act_call(sp)
                ev = self.shove_ev(sp, ci, eq1)
                if ev > SHOVE_EV * bb:
                    return act_allin(sp)
                if sp.can_check:
                    return act_call(sp)
                return act_fold(sp)
            # open raise
            nb = n_behind
            open_thr = {0: 0.5, 1: 0.40, 2: 0.32, 3: 0.25, 4: 0.20, 5: 0.17}.get(nb, 0.14)
            open_thr *= OPEN_K
            if n_alive == 2:
                open_thr = 0.7
            elif n_alive == 3:
                open_thr *= 1.2
            if sp.behind:
                vb = [self.looseness(o)[0] for o in sp.behind]
                mvb = max(vb)
                if mvb < 0.2:
                    open_thr = min(0.8, open_thr * 1.4)
                elif mvb > 0.5:
                    open_thr *= 0.8
            if limpers:
                open_thr *= 0.6
            if pct <= open_thr:
                size = (2.5 if eff_bb > 25 else 2.2) * bb + limpers * bb
                if sp.role == "SB" and limpers == 0:
                    size = 3 * bb
                return act_raise(sp, size)
            if sp.can_check:
                return act_call(sp)
            # SB completes cheap sometimes
            if sp.role == "SB" and limpers >= 1 and pct <= 0.45 and to_call <= bb:
                return act_call(sp)
            return act_fold(sp)

        # facing raise(s)
        raiser = sp.raiser
        r_vpip, r_pfr = self.looseness(raiser)
        loose = max(0.6, min(2.2, r_pfr / 0.15))  # >1 when opponent raises a lot
        po = to_call / (pot + to_call)
        call_frac = to_call / max(1, stack_tot)
        allin_faced = sp.max_to <= 0 or to_call >= sp.stack or (sp.stacks[raiser] == 0 if raiser >= 0 else False)

        if eff_bb <= 16 or call_frac >= 0.35 or allin_faced:
            # shove / call-shove by equity vs the raiser's estimated range, with ICM premium
            r_tot = (sp.stacks[raiser] + sp.bets[raiser]) if raiser >= 0 else stack_tot
            r_all = raiser >= 0 and sp.stacks[raiser] == 0
            nb_r = sp.position_of(raiser) if raiser >= 0 else 3
            if raises >= 2:
                x = 0.06 * loose
            elif r_all or (raiser >= 0 and sp.bets[raiser] >= 0.4 * r_tot):
                x = self.shove_range_est(raiser, min(r_tot, stack_tot) / bb, nb_r)
            else:
                x = min(0.6, 0.22 * loose)
            x = max(0.03, min(0.85, x))
            e = eq_vs_range(ci, x, eq1)
            if sp.callers:
                e *= 0.78 ** sp.callers
            prem = self.icm_prem(sp, stack_tot, r_tot) + 0.01 * len(sp.behind)
            if obs.get("level", 9) <= 1:
                prem += 0.05
            if sp.can_raise and not r_all and raises == 1 and raiser >= 0:
                m = min(stack_tot, r_tot)
                call_amt = m - sp.bets[raiser]
                final_pot = pot + (m - sp.bet) + call_amt
                e_req = call_amt / max(1, final_pot)
                y = min(x, self.call_range_est(raiser, e_req))
                p_call = y / x
                e_c = eq_vs_range(ci, y, eq1)
                if sp.callers:
                    e_c *= 0.78 ** sp.callers
                ev_shove = (1 - p_call) * pot + p_call * (e_c * final_pot - (m - sp.bet) - prem * final_pot)
                if ev_shove > 0.1 * bb:
                    return act_allin(sp)
            if (r_all or call_frac >= 0.35 or eff_bb <= 6) and e >= po + prem:
                if call_frac >= 0.4 and sp.can_raise:
                    return act_allin(sp)
                return act_call(sp)
            return act_fold(sp)

        # deep: 3-bet / call / fold
        if raises == 1:
            three_thr = 0.045 * loose
            call_thr = 0.13 * loose
            if sp.role == "BB":
                call_thr = 0.22 * loose if to_call <= 2.5 * bb else 0.15 * loose
            call_thr *= OPEN_K
            if n_alive == 2:
                three_thr = 0.10 * loose
                call_thr = (0.55 if to_call <= 3 * bb else 0.35) * loose
            if to_call > 5 * bb:
                call_thr *= 0.7
            if pct <= three_thr:
                cur = sp.bets[raiser] if raiser >= 0 else to_call
                size = cur * (3.0 if sp.ip else 3.6) + sp.callers * cur
                if size >= 0.4 * stack_tot:
                    return act_allin(sp)
                return act_raise(sp, size)
            if pct <= call_thr and call_frac < 0.2:
                return act_call(sp)
            return act_fold(sp)
        # 3-bet or more faced
        if pct <= 0.02 * loose:
            return act_allin(sp)
        if pct <= 0.05 * loose and call_frac < 0.25:
            return act_call(sp)
        return act_fold(sp)

    # ---------------------------------------------------------------- postflop
    def hand_eval(self, sp):
        hole, board = sp.hole, sp.board
        if len(hole) <= 2:
            s, outs, wet, cat = features(self.var, hole, board)
            return s, outs, wet, cat
        best = None
        for kept in combinations(hole, 2):
            r = features(self.var, list(kept), board)
            if best is None or r[0] + r[1] * 0.02 > best[0] + best[1] * 0.02:
                best = r
        s, outs, wet, cat = best
        return s, outs, wet, cat

    def postflop(self, sp, obs):
        me = obs["seat"]
        s, outs, wet, cat = self.hand_eval(sp)
        n_opp = sp.n_opp
        st = sp.street
        # pineapple: opponents hold stronger hands; discount marginal made hands
        if cat <= TWO_PAIR:
            s -= (PF_DISC if sp.to_call > 0 else BET_DISC)
        elif cat <= FLUSH:
            s += BIG_BUMP
        s -= MW_DISC * (n_opp - 1)
        left = 3 - st  # cards to come: flop 2, turn 1, river 0
        if left >= 2:
            deq = outs * 0.038
        elif left == 1:
            deq = outs * 0.021
        else:
            deq = 0.0
        eq = s + (1 - s) * deq * 0.85
        eq = max(0.0, min(0.99, eq))
        pot = sp.pot
        to_call = sp.to_call
        stack = sp.stack
        rng = self.rng
        aggressor = sp.last_aggr == me
        spr = stack / max(1, pot)

        # opponent type (loose callers -> fewer bluffs, thinner value; nits -> more bluffs)
        bl = BLUFF
        vthr = 0.62
        if sp.opps:
            vps = [self.looseness(o)[0] for o in sp.opps]
            mv = max(vps)
            if mv > 0.45:
                bl = 0.4
                vthr = 0.56
            elif mv < 0.18:
                bl = 1.3
            # measured fold-to-our-bet (prior 2 folds in 4)
            fr = 1.0
            for o in sp.opps:
                r = self.ftb.get(o)
                f = (2.0 + (r[1] if r else 0)) / (4.0 + (r[0] if r else 0))
                fr *= f
            if fr < 0.3:
                bl *= 0.4
                vthr -= 0.03
            elif fr > 0.6:
                bl *= 1.5
        if to_call == 0:
            if s >= 0.72 or (s >= vthr and n_opp == 1):
                frac = 0.75 if st == 3 else 0.6
                if spr < 1.2:
                    return act_allin(sp)
                return act_pot(sp, frac)
            if left >= 1 and outs >= 8 and rng.random() < 0.55 * min(1.0, bl + 0.3):
                return act_pot(sp, 0.55)
            if aggressor and n_opp <= 2 and st == 1 and rng.random() < (0.6 if n_opp == 1 else 0.35) * bl:
                return act_pot(sp, 0.45)
            if n_opp == 1 and st == 3 and aggressor and s < 0.2 and rng.random() < 0.25 * bl:
                return act_pot(sp, 0.6)
            if n_opp == 1 and sp.ip and s >= 0.45 and rng.random() < 0.5:
                return act_pot(sp, 0.5)
            return act_call(sp)

        po = to_call / (pot + to_call)
        bettor = sp.raiser if sp.raiser >= 0 else -1
        ag = self.aggression(bettor) if bettor >= 0 else 1.0
        bluff_adj = 0.04 if ag > 2.5 else (-0.04 if ag < 0.6 else 0.0)
        # bigger bets are stronger; require more
        rel = to_call / max(1, pot - to_call)
        need = po + 0.08 + 0.08 * min(1.5, rel) - bluff_adj
        if sp.raises >= 2:
            need += 0.14
        if obs.get("level", 9) <= 3 and to_call >= 0.3 * stack:
            need += 0.10
        if to_call >= 0.45 * stack and bettor >= 0:
            need += self.icm_prem(sp, stack + sp.bet, sp.stacks[bettor] + sp.bets[bettor]) * POST_PREM
        if s >= 0.88 or (s >= 0.84 and sp.raises <= 1 and n_opp == 1):
            if sp.can_raise:
                if spr < 2 or to_call >= 0.4 * stack:
                    return act_allin(sp)
                return act_pot(sp, 0.9)
            return act_call(sp)
        if eq >= need:
            return act_call(sp)
        # semi-bluff raise with big draws occasionally
        if left >= 1 and outs >= 12 and sp.can_raise and rng.random() < 0.3 and to_call < 0.3 * stack:
            return act_pot(sp, 0.8)
        return act_fold(sp)

    # ---------------------------------------------------------------- observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for h_st, seat, act, amt in hist:
                if act in ("sb", "bb", "ante", "return", "discard"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                s = self.st(seat)
                if h_st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        s[3] += 1
                    elif act in ("call", "check"):
                        s[4] += 1
            for seat in seen:
                s = self.st(seat)
                s[0] += 1
                if seat in vp:
                    s[1] += 1
                if seat in pr:
                    s[2] += 1
            # responses to our postflop bets
            me = self.seat
            cur_st = -1
            pend = False
            seen_st = set()
            for h_st, seat, act, amt in hist:
                if h_st != cur_st:
                    cur_st = h_st
                    pend = False
                    seen_st = set()
                if h_st < 1:
                    continue
                if seat == me:
                    if act == "raise":
                        pend = True
                        seen_st = set()
                    continue
                if pend and seat not in seen_st and act in ("fold", "call", "raise"):
                    seen_st.add(seat)
                    r = self.ftb.setdefault(seat, [0, 0])
                    r[0] += 1
                    if act == "fold":
                        r[1] += 1
            # responses to preflop all-in raises
            stacks = event.get("stacks") or []
            pay = event.get("payoffs") or {}
            start = {}
            for k, v in pay.items():
                k = int(k)
                if 0 <= k < len(stacks):
                    start[k] = stacks[k] - v
            shoved = False
            done = set()
            for h_st, seat, act, amt in hist:
                if h_st != 0:
                    break
                if act == "raise":
                    if shoved and seat not in done:
                        done.add(seat)
                        r = self.shove_resp.setdefault(seat, [0, 0])
                        r[0] += 1
                        r[1] += 1
                    elif not shoved and seat in start and amt >= start[seat]:
                        shoved = True
                        done.add(seat)
                elif shoved and seat not in done and act in ("call", "fold"):
                    done.add(seat)
                    r = self.shove_resp.setdefault(seat, [0, 0])
                    r[0] += 1
                    if act == "call":
                        r[1] += 1
        except Exception:
            pass
