"""b01 NLHE sit-and-go bot: preflop equity tables + push/fold EV + ICM,
postflop Monte Carlo vs range-weighted opponents, simple opponent stats."""

import os
import pickle
import random
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "data.pkl"), "rb") as _f:
    _D = pickle.load(_f)
RANKT = _D["rank"]
SUITEDT = _D["suited"]
PCT = _D["pct"]
EQM = _D["eqm"]

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
START = 0x3333
KEY = tuple((RANK_KEYS[c >> 2] + COUNT) << 16 | 1 << 4 * (c & 3) for c in range(52))
RANK_BIT = tuple(1 << (c >> 2) for c in range(52))
SB_BITS = {8 << 4 * s: tuple(RANK_BIT[c] if c & 3 == s else 0 for c in range(52)) for s in range(4)}


def cls_of(c1, c2):
    a, b = c1 >> 2, c2 >> 2
    if a == b:
        return a * 13 + a
    hi, lo = (a, b) if a > b else (b, a)
    return hi * 13 + lo if (c1 & 3) == (c2 & 3) else lo * 13 + hi


# class -> pct (0 best). combos per class
_CW = [0] * 169
for _a in range(13):
    for _b in range(13):
        _CW[_a * 13 + _b] = 6 if _a == _b else (4 if _a > _b else 12)
CLS_PCT = PCT  # indexed by class
_ORDER = sorted(range(169), key=lambda c: PCT[c])
NB = 100
# EQR[c][k]: equity of class c vs the top (k+1)% of hands
EQR = []
for _c in range(169):
    row = EQM[_c]
    out = []
    cum_w = 0.0
    cum_e = 0.0
    j = 0
    for k in range(NB):
        target = 1326.0 * (k + 1) / NB
        while j < 169 and cum_w < target:
            b = _ORDER[j]
            w = _CW[b]
            cum_w += w
            cum_e += w * row[b]
            j += 1
        out.append(cum_e / cum_w if cum_w else 0.5)
    EQR.append(out)


USE_CAP = False
RK = tuple(RANK_KEYS[r] + COUNT for r in range(13))
CLASS_COMBOS = [[] for _ in range(169)]
for _c1 in range(52):
    for _c2 in range(_c1 + 1, 52):
        CLASS_COMBOS[cls_of(_c1, _c2)].append((_c1, _c2))


def eq_vs(c, w):
    k = int(w * NB + 0.5) - 1
    if k < 0:
        k = 0
    elif k >= NB:
        k = NB - 1
    return EQR[c][k]


HU_CALL = ((1, 0.95), (2, 0.9), (3, 0.8), (5, 0.6), (8, 0.45), (10, 0.38), (15, 0.28), (20, 0.22),
           (30, 0.15), (50, 0.1), (200, 0.05))
NB_CALL = (1.0, 1.0, 0.68, 0.5, 0.4, 0.33, 0.29, 0.26)
POS_MULT = (1.0, 1.8, 1.4, 1.1, 0.9, 0.8, 0.7, 0.65)
# approx Nash first-in push widths by stack (bb) for nb players behind
PUSH_W = {
    1: ((2, 1.0), (5, 0.75), (8, 0.62), (10, 0.56), (15, 0.44), (20, 0.36), (30, 0.25)),
    2: ((2, 0.8), (5, 0.5), (10, 0.33), (15, 0.25), (20, 0.18), (30, 0.12)),
    3: ((2, 0.6), (5, 0.38), (10, 0.25), (15, 0.18), (20, 0.13), (30, 0.09)),
    4: ((2, 0.5), (5, 0.3), (10, 0.19), (15, 0.14), (20, 0.1), (30, 0.07)),
    5: ((2, 0.45), (5, 0.25), (10, 0.15), (15, 0.11), (20, 0.08), (30, 0.06)),
    6: ((2, 0.4), (5, 0.22), (10, 0.13), (15, 0.09), (20, 0.07), (30, 0.05)),
    7: ((2, 0.38), (5, 0.2), (10, 0.11), (15, 0.08), (20, 0.06), (30, 0.04)),
}


def interp(tab, x):
    if x <= tab[0][0]:
        return tab[0][1]
    for i in range(1, len(tab)):
        x1, y1 = tab[i]
        if x <= x1:
            x0, y0 = tab[i - 1]
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tab[-1][1]


def icm(stacks, pay):
    n = len(stacks)
    memo = {}
    full = (1 << n) - 1

    def rest(mask):
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < len(pay) and pay[place] > 0:
            total = 0.0
            for i in members:
                total += stacks[i]
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

    return rest(full)


class Opp:
    __slots__ = ("hands", "vpip", "pfr", "shove", "pf_aggr", "pf_pass", "fold_to_cbet", "cbet_faced",
                 "sh_faced", "sh_called")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.shove = 0
        self.pf_aggr = 0
        self.pf_pass = 0
        self.fold_to_cbet = 0
        self.cbet_faced = 0
        self.sh_faced = 0
        self.sh_called = 0

    def vpip_rate(self):
        return (self.vpip + 0.28 * 6) / (self.hands + 6)

    def pfr_rate(self):
        return (self.pfr + 0.16 * 6) / (self.hands + 6)

    def fold_rate(self):
        return (self.fold_to_cbet + 0.45 * 6) / (self.cbet_faced + 6)

    def aggr(self):
        return (self.pf_aggr + 0.35 * 5) / (self.pf_aggr + self.pf_pass + 5)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = list(config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0])
        self.opp = {}
        self.n_seats = config.get("seats", 8)
        self.prev_stacks = None

    # ---------------- helpers ----------------
    def o(self, s):
        x = self.opp.get(s)
        if x is None:
            x = self.opp[s] = Opp()
        return x

    @staticmethod
    def _raise(obs, amount):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            a = int(amount)
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if a < lo:
                a = lo
            if a > hi:
                a = hi
            return {"action": "raise", "amount": a}
        return Agent._call(obs)

    @staticmethod
    def _call(obs):
        if obs["to_call"] <= 0 or "call" not in obs["legal"]:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return {"action": "call"}

    @staticmethod
    def _fold(obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _allin(self, obs):
        if obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self._call(obs)

    # ---------------- main ----------------
    def act(self, obs):
        t0 = time.perf_counter()
        try:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
            if obs["street_index"] == 0:
                return self.preflop(obs)
            return self.postflop(obs, t0)
        except Exception:
            return self._fold(obs)

    # utility of final stack vector (ICM when few players)
    def _util_fn(self, obs):
        alive = obs["alive"]
        n = len(alive)
        if 2 < n <= 4:
            places_left = n
            pay = self.points[len(self.points) - (8 - n) - places_left:] if False else None
            # points still open: places 1..n -> points[0:n]
            pay = self.points[:n]
            return pay
        return None

    def preflop(self, obs):
        me = self.seat
        hole = [CARD[c] for c in obs["hole"]]
        c = cls_of(hole[0], hole[1])
        pct = PCT[c]
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_stack = stacks[me]
        my_bet = bets[me]
        my_tot = my_stack + my_bet
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        n_alive = len(alive)
        opps = [s for s in in_hand if s != me]
        hist = obs["history"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        max_bet = max(bets) if bets else 0

        # who raised
        raisers = []
        callers = []
        for st, s, a, amt in hist:
            if st != 0:
                continue
            if a == "raise":
                raisers.append((s, amt))
            elif a == "call":
                callers.append(s)
        n_raises = len(raisers)

        # players to act behind me (still in hand, with chips)
        order = self._preflop_order(obs)
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        # BB acts last; if I'm in order, players before me who haven't acted are none
        # effective stack vs opponents still in hand
        opp_tot = [stacks[s] + bets[s] for s in opps]
        eff = min(my_tot, max(opp_tot) if opp_tot else my_tot)
        eff_bb = eff / bb

        if n_raises == 0:
            return self._first_in(obs, c, pct, behind, eff_bb, my_tot, bb, callers)
        return self._facing_raise(obs, c, pct, behind, raisers, callers, my_tot, bb)

    def _preflop_order(self, obs):
        alive = obs["alive"]
        n = len(alive)
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        if n == 2:
            return [alive[bi], alive[1 - bi]]
        bbs = obs["bb_seat"]
        j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
        return alive[j:] + alive[:j]

    def _call_width(self, s, risk_bb, obs, nb=1):
        """Fraction of hands opponent s calls an all-in of risk_bb with."""
        base = interp(HU_CALL, risk_bb) * NB_CALL[min(nb, 7)]
        if s == obs["bb_seat"]:
            pass
        elif s == obs["sb_seat"]:
            base *= 0.8
        else:
            base *= 0.75
        op = self.opp.get(s)
        if op is not None and op.sh_faced >= 3:
            r = ((op.sh_called + 0.2 * 3) / (op.sh_faced + 3)) / 0.2
            base *= max(0.4, min(2.5, r)) ** 0.7
        elif op is not None and op.hands >= 8:
            r = op.vpip_rate() / 0.28
            base *= max(0.6, min(1.8, r)) ** 0.5
        return max(0.03, min(0.9, base))

    def _shove_ev(self, obs, c, behind, my_tot, bb):
        """EV (chips or ICM points) of shoving minus folding."""
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        my_bet = bets[me]
        my_stack = stacks[me]
        p_all_fold = 1.0
        ev_called = 0.0
        p_reach = 1.0
        pay = self.points[:len(obs["alive"])] if 2 < len(obs["alive"]) <= 4 else None
        alive = obs["alive"]
        base_stacks = {s: stacks[s] for s in alive}

        def util(final):
            if pay is None:
                return final[me]
            arr = [max(0.0, final[s]) for s in alive]
            e = icm(arr, pay)
            return e[alive.index(me)]

        # fold baseline: blinds/bets in pot go to... approximate: we lose our bet, pot goes elsewhere
        fold_state = dict(base_stacks)
        # give pot to a random opponent (bb usually); approximate to the bb seat
        winner = obs["bb_seat"] if obs["bb_seat"] != me and obs["bb_seat"] in alive else (behind[0] if behind else None)
        if pay is not None and winner is not None:
            fold_state[winner] = fold_state.get(winner, 0) + pot
        u_fold = util(fold_state)

        win_all = dict(base_stacks)
        win_all[me] = my_stack + pot
        # remove opponents' bets from their stacks already done (stacks exclude bets)
        u_allfold = util(win_all)
        ev = 0.0
        for s in behind:
            opp_tot = stacks[s] + bets[s]
            risk = min(my_tot, opp_tot)
            w = self._call_width(s, risk / bb, obs, len(behind))
            e = eq_vs(c, w)
            p_call = p_reach * w
            # outcome states
            win = dict(base_stacks)
            win[me] = my_stack + pot + (risk - bets[s])
            win[s] = stacks[s] - (risk - bets[s])
            lose = dict(base_stacks)
            lose[me] = my_stack - (risk - my_bet)
            lose[s] = stacks[s] + pot + (risk - my_bet)
            ev += p_call * (e * util(win) + (1 - e) * util(lose))
            p_reach *= (1 - w)
        ev += p_reach * u_allfold
        return ev - u_fold, (u_allfold - u_fold)

    def _first_in(self, obs, c, pct, behind, eff_bb, my_tot, bb, callers):
        me = self.seat
        to_call = obs["to_call"]
        nb = len(behind)
        # push/fold zone
        if eff_bb <= 14 or my_tot / bb <= 14:
            ev, gain = self._shove_ev(obs, c, [s for s in callers if s != me] + behind, my_tot, bb)
            # margin: prefer shove slightly if positive
            if ev > 0:
                return self._allin(obs)
            if to_call == 0:
                return {"action": "check"}
            # limp/complete from SB with cheap price only if decent
            return self._fold(obs)
        # deeper: open raise ranges by number of players behind
        thr = {0: 0.0, 1: 0.55, 2: 0.42, 3: 0.30, 4: 0.22, 5: 0.17, 6: 0.14, 7: 0.12}.get(nb, 0.12)
        if callers:
            thr *= 0.7
        if eff_bb < 25:
            thr *= 0.9
        if behind and nb <= 3:
            vs = 0.0
            for s in behind:
                op = self.opp.get(s)
                vs += op.vpip_rate() if op is not None else 0.28
            thr *= max(0.75, min(1.35, (0.28 / max(0.05, vs / nb)) ** 0.4))
        if to_call == 0:
            # BB option facing limps
            if pct <= 0.12:
                return self._raise(obs, obs["bets"][me] + (3 + len(callers)) * bb)
            return {"action": "check"}
        if pct <= thr:
            size = 2.5 * bb + len(callers) * bb
            if nb == 1:
                size = 3 * bb
            return self._raise(obs, size)
        # SB complete vs BB with cheap price
        if obs["sb_seat"] == me and nb == 1 and pct <= 0.6 and to_call <= bb / 2 + 1:
            return self._call(obs)
        return self._fold(obs)

    def _raiser_width(self, s, amt, bb, n_raises_before, obs):
        op = self.opp.get(s)
        pfr = op.pfr_rate() if op is not None else 0.16
        stacks = obs["stacks"]
        bets = obs["bets"]
        tot = stacks[s] + bets[s]
        allin = stacks[s] == 0
        if n_raises_before == 0:
            order = self._preflop_order(obs)
            nb_s = len(order) - 1 - order.index(s) if s in order else 3
            nb_s = max(1, min(7, nb_s))
            known = op is not None and op.hands >= 10
            w = pfr * POS_MULT[nb_s]
            if allin:
                wn = interp(PUSH_W[nb_s], tot / bb)
                w = max(wn * 0.8, w) if known else max(wn, w)
        else:
            w = pfr * 0.35
            if allin:
                w = max(w, min(0.4, 1.2 / max(tot / bb, 1.0)))
        return max(0.02, min(0.9, w))

    def _facing_raise(self, obs, c, pct, behind, raisers, callers, my_tot, bb):
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_stack = stacks[me]
        my_bet = bets[me]
        n_raises = len(raisers)
        last_raiser, last_amt = raisers[-1]
        w = self._raiser_width(last_raiser, last_amt, bb, n_raises - 1, obs)
        # multiple raisers: tighten
        e = eq_vs(c, w)
        cold = []
        seen_last = False
        for h in obs["history"]:
            if h[0] != 0:
                continue
            if h[2] == "raise":
                seen_last = (h[1] == last_raiser and h[3] == last_amt)
                if seen_last:
                    cold = []
            elif h[2] == "call" and seen_last:
                cold.append(h[1])
        for s in cold:
            e *= eq_vs(c, max(0.03, 0.6 * w)) * 1.15
        if n_raises > 1:
            e *= 0.95
        if e > 0.97:
            e = 0.97
        alive = obs["alive"]
        n_alive = len(alive)
        # all-in / commitment decision
        commit = to_call >= 0.4 * my_stack or my_tot / bb <= 16
        if commit:
            # option A: shove (if can raise) - treat raiser calling with top part of range
            # option B: call; option C: fold
            risk = min(my_tot, stacks[last_raiser] + bets[last_raiser])
            pot_if_call = pot + min(to_call, my_stack)
            # chip-EV of calling all in (or calling then getting it in)
            need = (risk - my_bet) / (pot + (risk - my_bet) + (risk - bets[last_raiser]))
            premium = 0.0
            if 2 < n_alive <= 6:
                premium = 0.03 + 0.01 * (6 - n_alive)
            if 2 < n_alive <= 5:
                # ICM exact
                pay = self.points[:n_alive]
                base = {s: stacks[s] for s in alive}
                win = dict(base)
                win[me] = my_stack + pot + (risk - bets[last_raiser])
                win[last_raiser] = stacks[last_raiser] - (risk - bets[last_raiser])
                lose = dict(base)
                lose[me] = my_stack - (risk - my_bet)
                lose[last_raiser] = stacks[last_raiser] + pot + (risk - my_bet)
                fold = dict(base)
                fold[last_raiser] += pot
                idx = alive.index(me)
                uf = icm([max(0, fold[s]) for s in alive], pay)[idx]
                uw = icm([max(0, win[s]) for s in alive], pay)[idx]
                ul = icm([max(0, lose[s]) for s in alive], pay)[idx]
                if uw - ul > 1e-9:
                    need = (uf - ul) / (uw - ul)
                premium = 0.0
            if behind:
                premium += 0.02 * len(behind)
            if e >= need + premium:
                if obs["max_raise_to"] > 0 and e >= need + premium + 0.04:
                    return self._allin(obs)
                if to_call >= my_stack:
                    return self._call(obs)
                return self._allin(obs)
            # resteal shove with fold equity vs a single non-all-in raiser
            if (n_raises == 1 and not cold and stacks[last_raiser] > 0 and obs["max_raise_to"] > 0
                    and my_tot <= 0.7 * (stacks[last_raiser] + bets[last_raiser]) + 30 * bb):
                cost = risk - my_bet
                inv = bets[last_raiser]
                q = 0.3 + 0.5 * min(1.0, inv / max(1.0, risk))
                op = self.opp.get(last_raiser)
                if op is not None and op.hands >= 10:
                    q *= max(0.7, min(1.5, op.vpip_rate() / 0.28)) ** 0.5
                q = min(0.9, q)
                e_c = eq_vs(c, max(0.02, w * q))
                win_pot = pot + cost + (risk - inv)
                p_f = (1 - q) * (0.9 ** len(behind))
                ev = p_f * pot + (1 - p_f) * (e_c * win_pot - cost)
                if ev > (premium + 0.02) * cost + 0.5 * bb:
                    return self._allin(obs)
            return self._fold(obs)
        # deep stacks facing a raise
        if n_raises == 1:
            if pct <= 0.035:
                return self._raise(obs, 3 * last_amt + to_call * 0 + sum(bets[s] for s in callers))
            # call: pairs and strong broadways at a reasonable price
            price_ok = to_call <= 0.08 * my_stack
            pair = c // 13 == c % 13
            if price_ok and (pct <= 0.11 or (pair and to_call <= 0.06 * my_stack)):
                return self._call(obs)
            dthr = 0.30
            if not cold:
                order = self._preflop_order(obs)
                nb_r = len(order) - 1 - order.index(last_raiser) if last_raiser in order else 3
                if len(obs["alive"]) == 2:
                    dthr = 0.6
                elif nb_r <= 2:
                    dthr = 0.42
            if me == obs["bb_seat"] and to_call <= 2.5 * bb and pct <= dthr:
                return self._call(obs)
            return self._fold(obs)
        # facing 3-bet or more
        if pct <= 0.012:
            return self._allin(obs) if to_call > 0.25 * my_stack else self._raise(obs, 2.5 * last_amt)
        if pct <= 0.03 and to_call <= 0.2 * my_stack:
            return self._call(obs)
        return self._fold(obs)

    # ---------------- postflop ----------------
    def _opp_width(self, s, obs):
        hist = obs["history"]
        raised = 0
        called = False
        for st, seat, a, amt in hist:
            if st != 0:
                continue
            if a == "raise":
                if seat == s:
                    raised += 1
                    called = False
                else:
                    pass
            elif a == "call" and seat == s:
                called = True
        op = self.opp.get(s)
        pfr = op.pfr_rate() if op else 0.16
        vpip = op.vpip_rate() if op else 0.28
        if raised >= 2:
            return max(0.02, pfr * 0.3)
        if raised == 1:
            return max(0.04, min(0.7, pfr))
        n_pf_raises = sum(1 for h in hist if h[0] == 0 and h[2] == "raise")
        if called and n_pf_raises > 0:
            return max(0.08, min(0.7, vpip))
        return 1.0

    def postflop(self, obs, t0):
        me = self.seat
        rng = self.rng
        hole = [CARD[x] for x in obs["hole"]]
        board = [CARD[x] for x in obs["board"]]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        bb = obs["bb"] or 1
        st = obs["street_index"]
        hist = obs["history"]
        top = max(c >> 2 for c in board)
        ranks_b = [c >> 2 for c in board]
        paired = len(set(ranks_b)) < len(ranks_b)
        specs = []
        for s in opps:
            w = self._opp_width(s, obs)
            A = RR = C = 0
            cur = -1
            bet_seen = False
            for h in hist:
                if h[0] == 0:
                    continue
                if h[0] != cur:
                    cur = h[0]
                    bet_seen = False
                if h[2] == "raise":
                    if h[1] == s:
                        A += 1
                        if bet_seen:
                            RR += 1
                    bet_seen = True
                elif h[2] == "call" and h[1] == s:
                    C += 1
            op = self.opp.get(s)
            bm = max(0.5, min(2.0, op.aggr() / 0.35)) if op is not None else 1.0
            pair_v = (2 << 20) if paired else (1 << 20)
            tp_v = (2 << 20) if paired else ((1 << 20) | (top << 16))
            tw_v = (3 << 20) if paired else (2 << 20)
            if RR >= 2 or (RR == 1 and st == 3):
                req, ps = tw_v, 0.12 * bm
            elif RR == 1:
                req, ps = tp_v, 0.15 * bm
            elif A >= 2:
                req, ps = tp_v, 0.25 * bm
            elif A == 1:
                req, ps = pair_v, 0.35 * bm
            elif C >= 1:
                req, ps = pair_v, 0.45
            else:
                req, ps = 0, 1.0
            cap = 0
            if USE_CAP and A == 0 and C == 0:
                for h in hist:
                    if h[0] == st and h[1] == s and h[2] == "check":
                        cap = tw_v
                        break
            specs.append((w, req, min(0.9, ps), cap))
        eq = self.mc(hole, board, specs, t0 + 0.00042)
        # aggression on this street
        street_raises = 0
        last_aggr = None
        for h in hist:
            if h[0] == st and h[2] == "raise":
                street_raises += 1
                last_aggr = h[1]
        pf_aggr = None
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                pf_aggr = h[1]
        prev_aggr = None
        for h in hist:
            if 0 < h[0] < st and h[2] == "raise":
                prev_aggr = h[1]
        i_was_aggr = (prev_aggr == me) if st > 1 and prev_aggr is not None else (pf_aggr == me)
        pot_before = pot - sum(bets)
        eff = min(my_stack + bets[me], max(stacks[s] + bets[s] for s in opps)) if opps else my_stack
        spr = eff / max(1, pot)
        r = rng.random()

        if to_call > 0:
            # facing a bet
            my_max = bets[me] + my_stack
            excess = 0
            for s in opps:
                if bets[s] > my_max:
                    excess += bets[s] - my_max
            pot_eff = pot - excess
            call_amt = min(to_call, my_stack)
            bet_frac = call_amt / max(1.0, pot_eff - call_amt)
            disc = 0.07 * min(1.5, bet_frac) + 0.05 * max(0, street_raises - 1)
            if last_aggr is not None:
                op = self.opp.get(last_aggr)
                if op is not None:
                    a = op.aggr()
                    disc *= max(0.4, min(1.4, (0.7 - a) / 0.35))
            if st == 3:
                disc *= 1.15
            eq_adj = eq - disc * eq
            odds = call_amt / (pot_eff + call_amt)
            # raise for value
            if eq_adj >= 0.72 and street_raises <= 2:
                if spr < 1.5 or to_call >= 0.4 * my_stack:
                    return self._allin(obs)
                tgt = max(bets) + 0.85 * (pot + to_call)
                return self._raise(obs, max(tgt, 2.5 * max(bets)))
            if eq_adj >= odds + 0.02:
                return self._call(obs)
            return self._fold(obs)

        # no bet to us
        fr = 1.0
        for s in opps:
            op = self.opp.get(s)
            fr *= op.fold_rate() if op is not None else 0.45
        fmult = max(0.3, min(1.8, (fr ** (1.0 / max(1, n_opp))) / 0.45))
        share = eq * (n_opp + 1)
        vthr = 0.58 + 0.04 * (n_opp - 1) + 0.06 * (fmult - 1.0)
        if eq >= vthr or share >= 1.45:
            frac = 0.7 if eq < 0.8 else 0.8
            amt = frac * pot
            if my_stack - amt < 0.6 * pot or spr < 1.2:
                return self._allin(obs)
            return self._raise(obs, amt)
        # c-bet / probe bluffs (scaled by opponents' fold-to-bet rate)
        if i_was_aggr and n_opp <= 2 and st <= 2:
            p = 0.6 if n_opp == 1 else 0.3
            if st == 2:
                p = 0.4 if n_opp == 1 else 0.0
            if r < min(0.9, p * fmult) and eq >= 0.2:
                return self._raise(obs, 0.5 * pot)
        if n_opp == 1 and eq >= 0.3 and r < min(0.6, 0.25 * fmult):
            return self._raise(obs, 0.5 * pot)
        return {"action": "check"}

    def _build_lists(self, hole, board, widths):
        dead = set(hole) | set(board)
        base_r = 0
        for c in board:
            base_r += RK[c >> 2]
        avail = [[] for _ in range(13)]
        for c in range(52):
            if c not in dead:
                avail[c >> 2].append(c)
        RT = RANKT
        out = []
        qcache = {}
        rcache = {}
        for w, req, ps, cap in widths:
            lr = rcache.get(w)
            if lr is None and w < 0.2:
                lr = []
                for cl in _ORDER:
                    if PCT[cl] > w:
                        break
                    for x, y in CLASS_COMBOS[cl]:
                        if x not in dead and y not in dead:
                            lr.append((x, y))
                if not lr:
                    lr = None
                rcache[w] = lr
            lq = None
            if req > 0:
                q = qcache.get(req)
                if q is None:
                    q = []
                    for r1 in range(13):
                        a1 = avail[r1]
                        if not a1:
                            continue
                        for r2 in range(r1, 13):
                            a2 = avail[r2]
                            if r1 == r2:
                                if len(a1) < 2:
                                    continue
                            elif not a2:
                                continue
                            v = RT.get(base_r + RK[r1] + RK[r2], -1)
                            if v >= req:
                                if r1 == r2:
                                    for i in range(len(a1)):
                                        for j in range(i + 1, len(a1)):
                                            q.append((a1[i], a1[j]))
                                else:
                                    for x in a1:
                                        for y in a2:
                                            q.append((x, y))
                    qcache[req] = q
                if q:
                    if w < 0.99:
                        wl = max(0.3, 1.6 * w)
                        qi = [pq for pq in q if PCT[cls_of(pq[0], pq[1])] <= wl]
                        lq = qi if len(qi) >= 4 else q
                    else:
                        lq = q
            out.append((w, lq, lr, ps, cap))
        return out

    def mc(self, hole, board, widths, deadline):
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        L = len(deck)
        need = 5 - len(board)
        K = KEY
        RT = RANKT
        ST = SUITEDT
        SBB = SB_BITS
        base = START
        for c in board:
            base += K[c]
        hk = K[hole[0]] + K[hole[1]]
        rand = self.rng.random
        clock = time.perf_counter
        wins = 0.0
        n = 0
        nopp = len(widths)
        pct = PCT
        specs = self._build_lists(hole, board, widths)
        while n < 400:
            used = set()
            b = []
            bs = base
            while len(b) < need:
                x = deck[int(rand() * L)]
                if x not in used:
                    used.add(x)
                    b.append(x)
                    bs += K[x]
            cards_b = board + b
            s = bs + hk
            if s & 0x8888:
                bits = SBB[s & 0x8888]
                allc = cards_b + hole
                f = ST[sum([bits[q] for q in allc])]
                hv = RT[s >> 16]
                if f > hv:
                    hv = f
            else:
                hv = RT[s >> 16]
            best = -1
            ties = 0
            for w, lq, lr, pskip, cap in specs:
                lst0 = lq if (lq is not None and rand() >= pskip) else lr
                for _ct in range(3 if cap else 1):
                    lst = lst0
                    if lst is not None:
                        nl = len(lst)
                        for _t in range(8):
                            x, y = lst[int(rand() * nl)]
                            if x not in used and y not in used:
                                break
                        else:
                            lst = None
                    if lst is None:
                        tries = 0
                        while True:
                            x = deck[int(rand() * L)]
                            if x in used:
                                continue
                            y = deck[int(rand() * L)]
                            if y in used or y == x:
                                continue
                            tries += 1
                            if w < 0.99 and tries <= 8 and pct[cls_of(x, y)] > w:
                                continue
                            break
                    if not cap:
                        break
                    sc = base + K[x] + K[y]
                    if sc & 0x8888:
                        bits = SBB[sc & 0x8888]
                        vc = ST[sum([bits[q] for q in board]) + bits[x] + bits[y]]
                        v0 = RT[sc >> 16]
                        if v0 > vc:
                            vc = v0
                    else:
                        vc = RT[sc >> 16]
                    if vc < cap or rand() < 0.3:
                        break
                used.add(x)
                used.add(y)
                s2 = bs + K[x] + K[y]
                if s2 & 0x8888:
                    bits = SBB[s2 & 0x8888]
                    f = ST[sum([bits[q] for q in cards_b]) + bits[x] + bits[y]]
                    v = RT[s2 >> 16]
                    if f > v:
                        v = f
                else:
                    v = RT[s2 >> 16]
                if v > best:
                    best = v
                    ties = 1 if v == hv else 0
                elif v == best and v == hv:
                    ties += 1
                if best > hv:
                    break
            if hv > best:
                wins += 1.0
            elif hv == best:
                wins += 1.0 / (1 + ties)
            n += 1
            if (n & 3) == 0 and clock() > deadline:
                break
        return wins / n if n else 0.5

    # ---------------- observation ----------------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            pf_raised = set()
            vp = set()
            for st, s, a, amt in hist:
                if s is None or s == self.seat:
                    continue
                if a in ("sb", "bb", "ante"):
                    seen.add(s)
                    continue
                seen.add(s)
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pf_raised.add(s)
                else:
                    op = self.o(s)
                    if a == "raise":
                        op.pf_aggr += 1
                    elif a in ("call", "check"):
                        op.pf_pass += 1
            # postflop fold-to-bet
            cur = -1
            active = False
            for st, s, a, amt in hist:
                if st == 0:
                    continue
                if st != cur:
                    cur = st
                    active = False
                if a == "raise":
                    if active and s != self.seat:
                        self.o(s).cbet_faced += 1
                    active = True
                elif a == "call" and active and s != self.seat:
                    self.o(s).cbet_faced += 1
                elif a == "fold" and active and s != self.seat:
                    op = self.o(s)
                    op.cbet_faced += 1
                    op.fold_to_cbet += 1
            # calls vs preflop all-ins
            ps = self.prev_stacks
            if ps is not None:
                shoved = False
                for st, s, a, amt in hist:
                    if st != 0:
                        continue
                    if a == "raise" and s < len(ps) and amt >= ps[s] > 0:
                        if shoved and s != self.seat:
                            op = self.o(s)
                            op.sh_faced += 1
                            op.sh_called += 1
                        shoved = True
                    elif shoved and s != self.seat and a in ("call", "fold"):
                        op = self.o(s)
                        op.sh_faced += 1
                        if a == "call":
                            op.sh_called += 1
            st_end = event.get("stacks")
            if st_end is not None:
                self.prev_stacks = list(st_end)
            for s in seen:
                op = self.o(s)
                op.hands += 1
                if s in vp:
                    op.vpip += 1
                if s in pf_raised:
                    op.pfr += 1
        except Exception:
            pass
