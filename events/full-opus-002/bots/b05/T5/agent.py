import json
import os
import random

from .hcommon import (CARD, HIGH, PAIR, Spot, Variant, features, safe_default)

_HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_HERE, "eqmat.json")) as _f:
    _EQ = json.load(_f)
_M = _EQ["M"]
_NC = _EQ["ncombo"]

_V = Variant(None)
_PRE = _V.pre
_PCT = _PRE.pct
_EQK = _PRE.eq_multi

# classes sorted best-first by percentile
_ORDER = sorted(range(169), key=lambda c: _PCT[c])
_GRID = (0.02, 0.04, 0.06, 0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.85, 1.0)


def _build_eqr():
    tot = float(sum(_NC))
    res = [[0.5] * len(_GRID) for _ in range(169)]
    for gi, x in enumerate(_GRID):
        need = x * tot
        w = [0.0] * 169
        acc = 0.0
        for d in _ORDER:
            if acc >= need:
                break
            take = min(_NC[d], need - acc)
            w[d] = take
            acc += take
        sw = sum(w)
        nz = [(d, w[d]) for d in range(169) if w[d] > 0]
        for c in range(169):
            row = _M[c]
            s = 0.0
            for d, wd in nz:
                s += wd * row[d]
            res[c][gi] = s / sw
    return res


_EQR = _build_eqr()


def eq_vs_range(c, x):
    """Equity of class c vs top-x fraction range."""
    g = _GRID
    if x <= g[0]:
        return _EQR[c][0]
    if x >= 1.0:
        return _EQR[c][-1]
    row = _EQR[c]
    for i in range(1, len(g)):
        if x <= g[i]:
            t = (x - g[i - 1]) / (g[i] - g[i - 1])
            return row[i - 1] + t * (row[i] - row[i - 1])
    return row[-1]


_BF_BASE = {2: 1.0, 3: 1.3, 4: 1.45, 5: 1.5, 6: 1.5, 7: 1.5, 8: 1.55}
_ICM_W = 0.5


def _bf(n_alive):
    return 1.0 + _ICM_W * (_BF_BASE.get(n_alive, 1.4) - 1.0) * 0.85


def bf_pair(n_alive, my_total, opp_total, avg):
    """ICM risk factor for me vs one opponent (loss weight relative to win)."""
    base = _BF_BASE.get(n_alive, 1.4)
    if n_alive <= 2:
        return 1.0
    if opp_total < my_total * 0.9:
        f = 0.75 if opp_total < avg * 0.7 else 0.82
    elif my_total < avg * 0.6:
        f = 0.88
    elif opp_total > my_total * 1.1:
        f = 1.12
    else:
        f = 1.0
    return 1.0 + _ICM_W * (base * f - 1.0)


class OppStats:
    __slots__ = ("hands", "vpip", "pfr", "pf_opp", "aggr", "passive", "fold_vs_raise", "faced_raise",
                 "shoves", "wtsd", "faced_shove", "called_shove", "faced_post", "fold_post", "pf_hands", "faced3", "fold3")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.pf_opp = 0
        self.aggr = 0
        self.passive = 0
        self.fold_vs_raise = 0
        self.faced_raise = 0
        self.shoves = 0
        self.wtsd = 0
        self.faced_shove = 0
        self.called_shove = 0
        self.faced_post = 0
        self.fold_post = 0
        self.pf_hands = 0
        self.faced3 = 0
        self.fold3 = 0

    def post_fold_rate(self):
        return (self.fold_post + 0.45 * 5) / (self.faced_post + 5)

    def pfr_rate(self):
        return (self.pfr + 0.16 * 6) / (self.hands + 6)

    def vpip_rate(self):
        return (self.vpip + 0.25 * 6) / (self.hands + 6)

    def af(self):
        return (self.aggr + 1.0) / (self.passive + 2.0)

    def fold_rate(self):
        return (self.fold_vs_raise + 0.5 * 4) / (self.faced_raise + 4)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.var = Variant(config.get("variant"))
        self.stats = {}
        self.pf_aggr_hand = -1
        self.hand_seen = -1
        self.shove_hand = -1
        self.shove_amt = 10 ** 9
        self.ss_hand = -1
        self.start_stacks = None

    # ---------- bookkeeping ----------
    def st(self, seat):
        s = self.stats.get(seat)
        if s is None:
            s = self.stats[seat] = OppStats()
        return s

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            raised_pf = False
            ss = self.start_stacks if self.ss_hand == event.get("hand_id") else None
            if ss is not None:
                for seat0 in range(len(ss)):
                    if ss[seat0] > 0 and seat0 != self.seat:
                        self.st(seat0).pf_hands += 1
            pf_last = {}
            pf_nr = 0
            cur_st = -1
            bet_on = False
            last_bettor = -1
            for h in hist:
                stt, seat, act, amt = h[0], h[1], h[2], h[3]
                if act in ("sb", "bb", "ante", "return", "discard"):
                    continue
                s = self.st(seat)
                if stt == 0:
                    if seat in pf_last and pf_last[seat] < pf_nr and act in ("fold", "call", "raise"):
                        s.faced3 += 1
                        if act == "fold":
                            s.fold3 += 1
                        del pf_last[seat]
                    if act == "raise":
                        pf_nr += 1
                        pf_last[seat] = pf_nr
                    if seat not in seen:
                        seen.add(seat)
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                    if raised_pf and act in ("fold", "call", "raise"):
                        s.faced_raise += 1
                        if act == "fold":
                            s.fold_vs_raise += 1
                    if act == "raise":
                        raised_pf = True
                        if ss is not None and seat < len(ss) and amt >= ss[seat] * 0.9:
                            s.shoves += 1
                else:
                    if stt != cur_st:
                        cur_st = stt
                        bet_on = False
                    if bet_on and seat != last_bettor and act in ("fold", "call", "raise"):
                        s.faced_post += 1
                        if act == "fold":
                            s.fold_post += 1
                    if act == "raise":
                        s.aggr += 1
                        bet_on = True
                        last_bettor = seat
                    elif act in ("call", "check"):
                        s.passive += 1
            if self.shove_hand == event.get("hand_id") or self.shove_hand == -2:
                after = False
                done = set()
                for h in hist:
                    if h[0] != 0:
                        break
                    if h[1] == self.seat and h[2] == "raise" and h[3] >= self.shove_amt:
                        after = True
                        continue
                    if after and h[1] != self.seat and h[1] not in done and h[2] in ("call", "fold", "raise"):
                        done.add(h[1])
                        so = self.st(h[1])
                        so.faced_shove += 1
                        if h[2] != "fold":
                            so.called_shove += 1
            self.shove_hand = -1
            for seat in seen:
                s = self.st(seat)
                s.hands += 1
                if seat in vp:
                    s.vpip += 1
                if seat in pr:
                    s.pfr += 1
        except Exception:
            pass

    # ---------- main ----------
    def act(self, obs):
        try:
            if obs.get("phase") == "discard":
                return safe_default(obs)
            sp = Spot(obs, self.var)
            if sp.street == 0 and self.ss_hand != obs.get("hand_id"):
                self.ss_hand = obs.get("hand_id")
                self.start_stacks = [obs["stacks"][i] + obs["bets"][i] for i in range(len(obs["stacks"]))]
            if sp.street == 0:
                a = self.preflop(sp, obs)
            else:
                a = self.postflop(sp, obs)
            a = self.legalize(a, obs)
            if sp.street == 0 and a.get("action") == "raise" and a["amount"] >= obs["max_raise_to"]:
                self.shove_hand = obs.get("hand_id", -2)
                self.shove_amt = a["amount"]
            return a
        except Exception:
            return safe_default(obs)

    def legalize(self, a, obs):
        legal = obs["legal"]
        k = a.get("action")
        if k == "fold" and "check" in legal:
            return {"action": "check"}
        if k == "check" and "check" not in legal:
            return {"action": "fold"}
        if k == "call" and "call" not in legal:
            return {"action": "check"} if "check" in legal else {"action": "fold"}
        if k == "raise":
            if not ("raise" in legal or "bet" in legal) or obs["max_raise_to"] <= 0:
                if "call" in legal:
                    return {"action": "call"}
                return {"action": "check"} if "check" in legal else {"action": "fold"}
            amt = int(a["amount"])
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if amt < lo:
                amt = lo
            if amt > hi:
                amt = hi
            return {"action": "raise", "amount": amt}
        return a

    def raise_to(self, sp, total):
        # shove if the raise would leave little behind
        my_total = sp.stack + sp.bet
        if total >= 0.7 * my_total:
            total = sp.max_to
        return {"action": "raise", "amount": int(total)}

    def allin(self, sp):
        if sp.can_raise:
            return {"action": "raise", "amount": sp.max_to}
        return {"action": "call"} if sp.to_call > 0 else {"action": "check"}

    def fold(self, sp):
        return {"action": "check"} if sp.can_check else {"action": "fold"}

    def call(self, sp):
        return {"action": "call"} if sp.to_call > 0 else {"action": "check"}

    def avg_stack(self, sp):
        tot = 0
        n = 0
        for s in sp.obs["alive"]:
            tot += sp.stacks[s] + sp.bets[s]
            n += 1
        return tot / max(1, n)

    # ---------- preflop ----------
    def calling_range(self, seat, shove_bb, is_bb, hu=False):
        if shove_bb <= 4:
            c = 0.45
        elif shove_bb <= 7:
            c = 0.30
        elif shove_bb <= 10:
            c = 0.22
        elif shove_bb <= 14:
            c = 0.17
        elif shove_bb <= 20:
            c = 0.13
        else:
            c = 0.10
        if is_bb:
            c *= 1.35
        if hu:
            c *= 1.3
        s = self.stats.get(seat)
        if s is not None:
            if s.faced_shove >= 3:
                obs_c = (s.called_shove + c * 3) / (s.faced_shove + 3)
                c = obs_c
            elif s.hands >= 8:
                v = s.vpip_rate()
                c *= max(0.7, min(1.6, v / 0.25))
        return max(0.03, min(0.95, c))

    def push_ev(self, sp, obs, cls, bf):
        """Chip EV (relative to fold) of shoving now, assuming each player behind calls with a top range."""
        me = sp.me
        my_total = sp.stack + sp.bet
        pot = sp.pot
        bb = sp.bb
        pfold = 1.0
        ev_called = 0.0
        wsum = 0.0
        for s in sp.opps:
            st = sp.stacks[s] + sp.bets[s]
            if sp.stacks[s] <= 0:
                continue
            E = min(my_total, st)
            c = self.calling_range(s, E / bb, s == obs["bb_seat"], sp.n_alive == 2)
            eq = eq_vs_range(cls, c)
            F = pot + (E - sp.bet) + (E - sp.bets[s])
            risk = E - sp.bet
            k = bf_pair(sp.n_alive, my_total, st, self.avg_stack(sp))
            win = eq * (F - risk) - (1 - eq) * risk * k
            pc = pfold * c
            ev_called += pc * win
            wsum += pc
            pfold *= (1 - c)
        return pfold * pot + ev_called

    def preflop(self, sp, obs):
        hole = sp.hole
        cls = _PRE.cls(hole[0], hole[1])
        pct = _PCT[cls]
        bb = sp.bb
        my_total = sp.stack + sp.bet
        n_alive = sp.n_alive
        bf = _bf(n_alive)
        # effective stack vs remaining opponents
        eff = sp.eff
        eff_bb = eff / bb
        n_behind = len(sp.behind)
        raises = sp.raises
        to_call = sp.to_call
        r = self.rng.random()

        if raises == 0:
            # unopened (maybe limpers)
            limpers = sum(1 for h in sp.hist if h[0] == 0 and h[2] == "call")
            if eff_bb <= 15:
                ev = self.push_ev(sp, obs, cls, bf)
                if ev > 0.05 * bb:
                    return self.allin(sp)
                if sp.can_check:
                    return {"action": "check"}
                return self.fold(sp)
            # open raise thresholds by players behind
            thr = {0: 0.0, 1: 0.45, 2: 0.32, 3: 0.24, 4: 0.19, 5: 0.15, 6: 0.13, 7: 0.12}.get(n_behind, 0.12)
            if n_alive == 2:
                thr = 0.75
            elif n_alive <= 3:
                thr *= 1.15
            if limpers:
                thr = min(thr, 0.15)
            # exploit tight blinds: widen when players behind fold a lot
            folders = [self.stats.get(s) for s in sp.behind]
            fr = [f.fold_rate() for f in folders if f is not None and f.faced_raise >= 4]
            if fr and n_behind <= 3:
                avg = sum(fr) / len(fr)
                thr *= max(0.8, min(1.5, 0.6 + avg * 0.8))
            if sp.can_check:
                # BB option
                if pct <= 0.12:
                    return self.raise_to(sp, sp.bet + (3 + limpers) * bb)
                return {"action": "check"}
            if pct <= thr:
                size = (2.5 if eff_bb > 40 else 2.2) * bb + limpers * bb
                return self.raise_to(sp, size)
            # SB complete vs BB with decent hands when cheap
            if sp.role == "SB" and limpers == 0 and n_behind == 1 and pct <= 0.6 and eff_bb > 25:
                return self.call(sp)
            return self.fold(sp)

        # facing a raise
        raiser = sp.raiser
        rst = self.stats.get(raiser)
        rstack = sp.stacks[raiser] if raiser >= 0 else 1
        raiser_total = (sp.stacks[raiser] + sp.bets[raiser]) if raiser >= 0 else eff
        pfr = rst.pfr_rate() if rst is not None else 0.16
        # estimated range width of the raiser
        if raises == 1:
            rng_w = max(0.05, min(0.6, pfr * 1.1))
        elif raises == 2:
            rng_w = max(0.03, min(0.3, pfr * 0.45))
        else:
            rng_w = max(0.02, min(0.15, pfr * 0.25))
        raise_amt = sp.bets[raiser] if raiser >= 0 else to_call
        is_shove = rstack == 0 or raise_amt >= 0.6 * raiser_total
        if is_shove and raises == 1:
            # shoves from short stacks are wider
            sb_bb = raiser_total / bb
            if sb_bb <= 10:
                rng_w = max(rng_w, 0.30)
            elif sb_bb <= 15:
                rng_w = max(rng_w, 0.20)
            elif sb_bb <= 25:
                rng_w = max(rng_w, 0.12)
            if rst is not None and rst.pf_hands >= 8 and rst.shoves >= 1:
                obs_w = min(0.85, max(0.04, 1.7 * rst.shoves / rst.pf_hands))
                k = min(1.0, rst.pf_hands / 30.0)
                rng_w = (1 - k) * rng_w + k * max(obs_w, rng_w * 0.6)
            if n_alive == 2:
                rng_w = max(rng_w, 0.55 if sb_bb <= 10 else 0.42 if sb_bb <= 15 else 0.30 if sb_bb <= 25 else 0.15)
            elif n_alive == 3 and len(sp.behind) == 0:
                rng_w = max(rng_w, 0.35 if sb_bb <= 10 else 0.26 if sb_bb <= 15 else 0.18)
        eq = eq_vs_range(cls, rng_w)
        # callers of the raise: much tighter, multiway equity
        ncall = sp.callers
        if ncall > 0:
            e2 = eq_vs_range(cls, max(0.03, min(rng_w, 0.10)))
            for _ in range(ncall):
                eq = min(eq, eq * e2 * 1.25)
        # players still to act behind
        nb = len([x for x in sp.behind if x != raiser])
        if nb > 0:
            eq *= 0.975 ** nb
        call_amt = min(to_call, sp.stack)
        my_total = sp.stack + sp.bet
        # big commitment decisions: treat as all-in
        commit = call_amt >= 0.35 * my_total or is_shove or eff_bb <= 18 or (raises == 1 and eff_bb <= 22)
        if commit:
            # option: shove / call / fold by equity
            E = min(my_total, max([sp.stacks[s] + sp.bets[s] for s in sp.opps] or [0]))
            kf = bf_pair(sp.n_alive, my_total, raiser_total, self.avg_stack(sp))
            excess = max(0, sp.bets[raiser] - (sp.bet + call_amt))
            c_risk = call_amt * kf
            c_need = c_risk / (c_risk + sp.pot - excess)
            risk = E - sp.bet
            win_amt = sp.pot + max(0, E - sp.bets[raiser])
            risk_w = risk * kf
            need = risk_w / (risk_w + win_amt)
            if is_shove or not sp.can_raise:
                if eq >= c_need:
                    return self.call(sp)
                return self.fold(sp)
            # we can re-shove: add fold equity
            fe = 0.0
            if rst is not None and rst.faced3 >= 3:
                fe = max(0.0, min(0.7, (rst.fold3 + 1.5) / (rst.faced3 + 3) * 0.9))
            elif rst is not None and rst.faced_raise >= 3:
                fe = max(0.0, min(0.5, rst.fold_rate() * 0.6))
            else:
                fe = 0.35 if raises == 1 else 0.2
            # once committed (raiser put in big chunk), less fold equity
            if raise_amt >= 0.35 * raiser_total:
                fe *= 0.3
            ev_shove = fe * sp.pot + (1 - fe) * (eq * win_amt - (1 - eq) * risk_w)
            if ev_shove > 0 and (eq >= need - 0.04 or fe > 0.25):
                return self.allin(sp)
            if eq >= c_need and call_amt <= 0.2 * my_total:
                return self.call(sp)
            return self.fold(sp)

        # deep: 3bet / call / fold
        three_thr = 0.025 + rng_w * 0.12
        if raises >= 2:
            # facing 3bet+: value 4-bet vs its range, call by equity when the price is small
            if pct <= max(0.02, rng_w * 0.25):
                return self.raise_to(sp, sp.bets[raiser] * 2.3)
            pot_odds = call_amt / (sp.pot + call_amt)
            pen = 0.06 if sp.ip else 0.10
            if call_amt <= 0.25 * my_total and eq >= pot_odds + pen:
                return self.call(sp)
            return self.fold(sp)
        if pct <= three_thr:
            mult = 3.0 if sp.ip else 3.6
            return self.raise_to(sp, raise_amt * mult + sp.callers * raise_amt)
        pot_odds = call_amt / (sp.pot + call_amt)
        # implied odds for pairs / suited connectors when deep
        is_pair = (hole[0] >> 2) == (hole[1] >> 2)
        if is_pair and call_amt <= eff / 15.0:
            return self.call(sp)
        margin = 0.0 if sp.ip or sp.role == "BB" else 0.05
        if eq - margin >= max(pot_odds + 0.04, 0.42 if sp.role != "BB" else pot_odds + 0.02):
            return self.call(sp)
        # light 3-bet bluff vs loose opener in position
        if sp.ip and pfr > 0.3 and pct <= 0.25 and r < 0.2 and sp.callers == 0:
            return self.raise_to(sp, raise_amt * 3.0)
        # light 3-bet vs openers seen folding to 3-bets a lot
        if (rst is not None and rst.faced3 >= 3 and sp.callers == 0 and pct <= 0.35
                and (rst.fold3 + 1.5) / (rst.faced3 + 3) >= 0.6 and r < 0.6):
            mult = 3.0 if sp.ip else 3.6
            return self.raise_to(sp, raise_amt * mult)
        return self.fold(sp)

    # ---------- postflop ----------
    def postflop(self, sp, obs):
        s, outs, wet, cat = features(self.var, sp.hole, sp.board)
        street = sp.street
        n_opp = max(1, sp.n_opp)
        cards_left = 2 if street == 1 else (1 if street == 2 else 0)
        draw = 0.0
        if cards_left == 2:
            draw = min(0.6, outs * 0.04)
        elif cards_left == 1:
            draw = min(0.4, outs * 0.022)
        eq1 = s + (1 - s) * draw
        eq = eq1 ** (1 + 0.75 * (n_opp - 1))
        pot = sp.pot
        to_call = sp.to_call
        my_total = sp.stack + sp.bet
        bb = sp.bb
        r = self.rng.random()
        n_alive = sp.n_alive
        bf = _bf(n_alive)
        # was I preflop aggressor / last aggressor
        last_aggr = sp.last_aggr
        me = sp.me
        i_aggr = last_aggr == me
        spr = sp.stack / max(1, pot)

        if to_call == 0:
            # opponents' postflop fold-to-bet tendency
            fmin = 1.0
            for o in sp.opps:
                so = self.stats.get(o)
                fr = so.post_fold_rate() if so is not None else 0.45
                if fr < fmin:
                    fmin = fr
            station = fmin < 0.3
            folder = fmin > 0.55
            if eq >= 0.78:
                frac = 0.75 if (wet or station) else 0.6
                if spr <= 1.3:
                    return self.allin(sp)
                return self.bet_pot(sp, frac)
            if eq >= (0.52 if station else 0.58) and n_opp <= 2:
                return self.bet_pot(sp, 0.6 if station else 0.5)
            bl = 0.4 if station else (1.4 if folder else 1.0)
            if outs >= 8 and cards_left > 0 and r < 0.55 * min(1.2, bl + 0.3):
                return self.bet_pot(sp, 0.6)
            if i_aggr and n_opp == 1 and street == 1 and r < (0.45 if wet else 0.65) * bl:
                return self.bet_pot(sp, 0.45)
            if i_aggr and n_opp == 1 and street == 2 and r < 0.25 * bl and s > 0.3:
                return self.bet_pot(sp, 0.5)
            # position steal when checked to
            if sp.ip and n_opp == 1 and r < 0.25 * bl and street >= 2:
                return self.bet_pot(sp, 0.5)
            return {"action": "check"}

        # facing a bet
        bettor = sp.raiser
        bst = self.stats.get(bettor)
        af = bst.af() if bst is not None else 0.6
        call_amt = min(to_call, sp.stack)
        pot_odds = call_amt / (pot + call_amt)
        bet_frac = to_call / max(1, pot - to_call)
        # threshold model of the bettor's range (in strength units)
        T = 0.30 + 0.15 * min(1.5, bet_frac)
        if sp.raises >= 2:
            T += 0.15
        cnt = {}
        pfr_n = 0
        for h in sp.hist:
            if h[2] == "raise" and h[0] == 0 and h[1] == bettor:
                pfr_n += 1
            if h[2] == "raise" and 0 < h[0] < street:
                k = cnt.get(h[0], 0) + 1
                cnt[h[0]] = k
                if h[1] == bettor:
                    T += 0.12 if k >= 2 else 0.08
        if street == 3:
            T += 0.05
        n3 = sum(1 for h in sp.hist if h[0] == 0 and h[2] == "raise")
        if pfr_n >= 1:
            T += 0.06 if n3 >= 2 else 0.02
        T += 0.05 * sp.callers
        if T > 0.85:
            T = 0.85
        beta = 0.12
        if af > 2.0:
            beta = 0.25
        elif af > 1.3:
            beta = 0.18
        elif af < 0.6:
            beta = 0.06
        sv = eq1
        bw = min(1.0, 0.25 + sv * 1.5)
        eqd = beta * bw + (1 - beta) * max(0.0, (sv - T) / (1 - T))
        if n_opp > 1:
            eqd = eqd ** (1 + 0.5 * (n_opp - 1))
        # raise with monsters
        if eq >= 0.88 and sp.can_raise:
            if spr <= 2.5 or call_amt >= 0.3 * sp.stack:
                return self.allin(sp)
            return self.raise_to(sp, sp.bets[bettor] * 2.8 + (pot - to_call) * 0.3 if bettor >= 0 else to_call * 3)
        all_in_call = call_amt >= sp.stack * 0.95
        # semi-bluff shove with big draws at low SPR on the flop
        if (cards_left == 2 and outs >= 12 and sp.can_raise and n_opp == 1 and spr <= 4
                and sp.raises <= 1 and not all_in_call):
            return self.allin(sp)
        need = pot_odds
        if all_in_call or call_amt >= 0.4 * my_total:
            risk_w = call_amt * bf
            need = risk_w / (risk_w + pot)
        # all-in (or nearly): we see every card, so a draw has its full equity
        if cards_left > 0 and outs >= 4 and (all_in_call or call_amt >= 0.6 * sp.stack):
            if cards_left == 2:
                dea = 1.0 - (1.0 - outs / 47.0) * (1.0 - outs / 46.0)
            else:
                dea = outs / 46.0
            eqd = max(eqd, dea * 0.85)
        # draws: direct odds plus small implied
        if cards_left > 0 and outs >= 8 and not all_in_call:
            de = outs * 0.022 * (1.25 if cards_left == 2 and spr > 3 else 1.0)
            if de + 0.05 >= need:
                return self.call(sp)
        if eqd >= need:
            return self.call(sp)
        return self.fold(sp)

    def bet_pot(self, sp, frac):
        amt = sp.bet + sp.to_call + frac * (sp.pot + sp.to_call)
        amt = max(amt, sp.min_to)
        return self.raise_to(sp, amt)
