import json
import os
import random

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.json")))
CLASSES = [tuple(c) for c in _D["classes"]]
CI = {c: i for i, c in enumerate(CLASSES)}
PRE = _D["pre"]
PRE_RAND = _D["pre_rand"]
POST = _D["post"]
RK = {"T": 0, "J": 1, "Q": 2, "K": 3, "A": 4}
# preflop class prior frequency (combos)
PRIOR = [6.0 if a == b else 16.0 for (a, b) in CLASSES]
ORDER = sorted(range(15), key=lambda i: -PRE_RAND[i])
# cumulative percentile of each class (top fraction including itself)
PCT = [0.0] * 15
_c = 0.0
for _i in ORDER:
    _c += PRIOR[_i] / 190.0
    PCT[_i] = _c


_HU_PUSH = ((4.5, 0.80), (6.5, 0.75), (8.5, 0.68), (14.5, 0.61), (99.0, 0.52))
_HU_CALL = ((4.5, 0.92), (6.5, 0.67), (8.5, 0.54), (10.5, 0.47), (12.5, 0.41), (14.5, 0.35), (18.0, 0.30), (999.0, 0.26))


def _hu_push(bbs):
    for lim, f in _HU_PUSH:
        if bbs <= lim:
            return f
    return 0.52


def _hu_call(bbs):
    for lim, f in _HU_CALL:
        if bbs <= lim:
            return f
    return 0.26


def range_weights(frac):
    """weights over classes for a 'top frac' range (smooth edge)."""
    frac = max(0.04, min(1.0, frac))
    w = [0.0] * 15
    prev = 0.0
    for i in ORDER:
        p = PRIOR[i] / 190.0
        lo = prev
        hi = prev + p
        if hi <= frac:
            w[i] = PRIOR[i]
        elif lo < frac:
            w[i] = PRIOR[i] * (frac - lo) / p
        prev = hi
    return w


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 25, 5, 0, 0, 0, 0, 0])
        n = config.get("seats", 8)
        # per-seat stats
        self.hands = {}
        self.vpip = {}
        self.pfr = {}
        self.shove = {}
        self.pf_opps = {}
        self.post_aggr = {}
        self.post_pass = {}
        self.post_cache = {}
        self.pending_shoves = set()

    # ---------------- opponent model ----------------
    def _stat(self, d, s):
        return d.get(s, 0)

    def raise_frac(self, s):
        """estimated fraction of hands seat s raises preflop with."""
        h = self.pf_opps.get(s, 0)
        r = self.pfr.get(s, 0)
        return (r + 2.0 * 0.22) / (h + 2.0)

    def shove_frac(self, s):
        h = self.pf_opps.get(s, 0)
        r = self.shove.get(s, 0)
        return (r + 3.0 * 0.12) / (h + 3.0)

    def vpip_frac(self, s):
        h = self.pf_opps.get(s, 0)
        r = self.vpip.get(s, 0)
        return (r + 3.0 * 0.35) / (h + 3.0)

    def aggr(self, s):
        a = self.post_aggr.get(s, 0)
        p = self.post_pass.get(s, 0)
        return (a + 1.5) / (a + p + 3.0)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history", [])
            seen = set()
            vp = set()
            pr = set()
            sh = set()
            stacks0 = {}
            for st, seat, act, amt in hist:
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                if st == 0:
                    seen.add(seat)
                    if act in ("call", "raise", "allin"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        self.post_aggr[seat] = self.post_aggr.get(seat, 0) + 1
                    elif act in ("check", "call"):
                        self.post_pass[seat] = self.post_pass.get(seat, 0) + 1
            # shove detection: preflop raise amount >= start stack of player (approx via final stacks unknown) skip
            for s in seen:
                self.pf_opps[s] = self.pf_opps.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
            for s in pr:
                self.pfr[s] = self.pfr.get(s, 0) + 1
            for s in self.pending_shoves:
                self.shove[s] = self.shove.get(s, 0) + 1
        except Exception:
            pass
        self.pending_shoves = set()

    # ---------------- helpers ----------------
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    def _act(self, obs):
        legal = obs["legal"]
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [RK[c[0]] for c in obs["hole"]]
        a, b = min(hole), max(hole)
        hc = CI[(a, b)]
        board = [RK[c[0]] for c in obs["board"]]
        self._track_shoves(obs)
        if obs["street_index"] == 0:
            return self._preflop(obs, hc, legal)
        return self._postflop(obs, hc, hole, board, legal)

    def _track_shoves(self, obs):
        # record preflop all-in raises by others this hand
        stacks = obs["stacks"]
        for st, seat, act, amt in obs["history"]:
            if st == 0 and act == "raise" and seat != self.seat:
                if stacks[seat] == 0:
                    self.pending_shoves.add(seat)

    def _ret_raise(self, obs, amt):
        legal = obs["legal"]
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if ("raise" in legal or "bet" in legal) and hi > 0:
            amt = int(max(lo, min(hi, amt)))
            if amt >= hi * 0.85:
                amt = hi
            return {"action": "raise", "amount": amt}
        if "call" in legal:
            return {"action": "call"}
        return {"action": "check"}

    def _passive(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def _icm_pressure(self, obs):
        """factor > 0 increasing the equity needed to call all-ins when few players left."""
        alive = obs["alive"]
        n = len(alive)
        if n <= 2:
            return 0.0
        if n == 3:
            return 0.04
        if n == 4:
            return 0.03
        return 0.015

    # ---------------- preflop ----------------
    def _preflop(self, obs, hc, legal):
        me = self.seat
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_stack = stacks[me]
        my_bet = bets[me]
        in_hand = obs["in_hand"]
        others = [s for s in in_hand if s != me]
        max_other = max((stacks[s] + bets[s] for s in others), default=0)
        eff = min(my_stack + my_bet, max_other)
        eff_bb = eff / bb
        to_call = obs["to_call"]
        pot = obs["pot"]
        hist = obs["history"]
        raisers = [seat for st, seat, act, amt in hist if st == 0 and act == "raise"]
        n_raises = len(raisers)
        # players to act after me (approx by position): count seats in hand that haven't acted voluntarily yet
        acted = set(seat for st, seat, act, amt in hist if st == 0 and act not in ("sb", "bb", "ante"))
        behind = [s for s in others if s not in acted]
        n_behind = len(behind)
        n_alive = len(obs["alive"])
        s_rand = PRE_RAND[hc]
        pct = PCT[hc]

        if n_raises == 0:
            # unopened (maybe limpers)
            limpers = [s for s in acted if s != me and s in in_hand]
            # target opening fraction by number behind
            if n_behind <= 0:
                # BB option facing limpers: isolate with the top only
                open_frac = 0.5 if (n_alive == 2) else 0.30
            elif n_behind == 1:
                open_frac = 0.85 if n_alive == 2 else 0.62  # SB vs BB
            elif n_behind == 2:
                open_frac = 0.60
            elif n_behind == 3:
                open_frac = 0.46
            elif n_behind == 4:
                open_frac = 0.32
            else:
                open_frac = 0.24
            if limpers and n_behind > 0:
                open_frac *= 0.8
            if eff_bb <= 17:
                # push/fold
                push_frac = open_frac * (1.0 + max(0.0, 14 - eff_bb) / 14.0 * 0.6)
                if eff_bb <= 6 and n_behind > 0:
                    push_frac = max(push_frac, 0.55)
                push_frac = min(push_frac, 1.0 if n_behind > 0 else 0.6)
                if n_alive == 2 and n_behind == 1:
                    push_frac = _hu_push(eff_bb)
                if pct <= push_frac + 1e-9:
                    return {"action": "allin"}
                if "check" in legal:
                    return {"action": "check"}
                return {"action": "fold"}
            if pct <= open_frac + 1e-9:
                size = bb * (2.5 + len(limpers))
                if n_behind <= 2:
                    size = bb * (2.3 + len(limpers))
                if size >= eff * 0.35:
                    return {"action": "allin"}
                return self._ret_raise(obs, size)
            if "check" in legal:
                return {"action": "check"}
            # limp rarely: complete SB with decent hands when cheap
            if to_call <= bb * 0.5 and pct <= 0.8 and n_behind == 1:
                return self._call(obs)
            return {"action": "fold"}

        # facing raise(s)
        last_raiser = raisers[-1]
        # estimate range of raisers
        allin_raisers = [s for s in set(raisers) if stacks[s] == 0]
        w = [0.0] * 15
        frac = 1.0
        for s in set(raisers):
            if stacks[s] == 0:
                f = self.shove_frac(s)
                sbb = (bets[s]) / bb
                if sbb <= 8:
                    f = max(f, 0.45)
                elif sbb <= 15:
                    f = max(f, 0.30)
                elif sbb <= 30:
                    f = max(f, 0.18)
                else:
                    f = max(f, 0.08)
            else:
                f = max(self.raise_frac(s), self._pos_prior(obs, s))
            if n_alive == 2:
                f = max(f, 0.65 if stacks[s] == 0 else 0.55)
            elif n_alive == 3:
                f = max(f, 0.35)
            if n_raises >= 2:
                f *= 0.65 if n_alive == 2 else 0.45
            frac = min(frac, f)
        frac = max(0.04, min(1.0, frac))
        w = range_weights(frac)
        eq = self._eq_pre(hc, w)
        vol = set(seat for st, seat, act, amt in hist if st == 0 and act in ("call", "raise"))
        n_opp_in = len([s for s in others if s in vol]) + 0.3 * len([s for s in others if s not in vol and bets[s] > 0])
        n_opp_in = max(1.0, n_opp_in)
        # multiway approx
        eq_m = eq ** (1.0 + 0.7 * (n_opp_in - 1))
        call_amt = min(to_call, my_stack)
        pot_after = pot + call_amt
        need = call_amt / pot_after if pot_after > 0 else 0
        commit = (my_bet + call_amt) >= 0.5 * (my_stack + my_bet) or eff_bb <= 18
        if commit or allin_raisers and call_amt >= my_stack * 0.6:
            # all-in decision
            need_ai = need + self._icm_pressure(obs)
            # want to re-shove with strong ones if possible
            hu_floor = n_alive == 2 and allin_raisers and pct <= _hu_call(eff_bb) + 1e-9
            if eq_m >= need_ai + 0.02 or hu_floor:
                if "raise" in legal and obs["max_raise_to"] > 0 and eq >= 0.55:
                    return {"action": "allin"}
                return self._call(obs) if call_amt < my_stack else {"action": "allin"}
            return self._passive(obs)
        # deep: 3bet / call / fold
        if eq >= 0.58 or hc in (CI[(4, 4)],):
            target = obs["bets"][last_raiser] * 3 + (pot - sum(bets))
            if target >= eff * 0.4:
                return {"action": "allin"}
            return self._ret_raise(obs, target)
        implied = 0.06 if eff_bb > 40 else 0.03
        floor = 0.38
        if n_alive == 2:
            floor = 0.30
        elif me == obs["bb_seat"] and n_raises == 1:
            floor = 0.34
        if n_raises >= 2:
            floor = 0.38 if n_alive == 2 else 0.45
        if eq_m + implied >= need and eq >= floor:
            return self._call(obs)
        return self._passive(obs)

    def _pos_prior(self, obs, s):
        alive = obs["alive"]
        n = len(alive)
        bbs = obs["bb_seat"]
        order = sorted(alive)
        if bbs in order:
            k = order.index(bbs)
            order = order[k + 1:] + order[:k + 1]
        if s not in order:
            return 0.25
        behind = n - 1 - order.index(s)
        if behind >= 5:
            return 0.25
        return (0.5, 0.6, 0.48, 0.38, 0.30)[behind]

    def _eq_pre(self, hc, w):
        a, b = CLASSES[hc]
        tot = 0.0
        s = 0.0
        row = PRE[hc]
        for j in range(15):
            wj = w[j]
            if wj <= 0:
                continue
            x, y = CLASSES[j]
            # card removal
            rem_x = 4 - (a == x) - (b == x)
            rem_y = 4 - (a == y) - (b == y)
            if x == y:
                cw = rem_x * (rem_x - 1) / 2.0 / 6.0
            else:
                cw = rem_x * rem_y / 16.0
            ww = wj * cw
            if ww <= 0 or row[j] is None:
                continue
            tot += ww
            s += ww * row[j]
        return s / tot if tot > 0 else 0.5

    # ---------------- postflop ----------------
    def _post_eq(self, hc, hole, board, opp_w, aggr_pow):
        cnt = [0] * 5
        for r in board:
            cnt[r] += 1
        key = "".join(str(x) for x in cnt)
        row = POST.get("%d|%s" % (hc, key))
        if row is None:
            return 0.5
        used = list(cnt)
        for r in hole:
            used[r] += 1
        rem = [4 - u for u in used]
        tot = 0.0
        s = 0.0
        for j in range(15):
            e = row[j]
            if e is None:
                continue
            x, y = CLASSES[j]
            if x == y:
                cw = rem[x] * (rem[x] - 1) / 2.0
            else:
                cw = rem[x] * rem[y]
            if cw <= 0:
                continue
            ww = cw * opp_w[j]
            if aggr_pow > 0:
                ww *= (1.0 - e + 0.02) ** aggr_pow
            if ww <= 0:
                continue
            tot += ww
            s += ww * e
        return s / tot if tot > 0 else 0.5

    def _postflop(self, obs, hc, hole, board, legal):
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        in_hand = obs["in_hand"]
        others = [s for s in in_hand if s != me]
        n_opp = max(1, len(others))
        hist = obs["history"]
        # opponent preflop range: if someone raised preflop use tighter
        pf_raisers = set(seat for st, seat, act, amt in hist if st == 0 and act == "raise")
        opp_w = [1.0] * 15
        if any(s in pf_raisers for s in others):
            f = min(self.raise_frac(s) for s in others if s in pf_raisers)
            rw = range_weights(max(0.15, f))
            opp_w = [rw[i] / PRIOR[i] + 0.05 for i in range(15)]
        else:
            vf = max(0.3, min(1.0, sum(self.vpip_frac(s) for s in others) / n_opp))
            rw = range_weights(vf)
            opp_w = [rw[i] / PRIOR[i] + 0.1 for i in range(15)]
        street = obs["street_index"]
        hu = len(obs["alive"]) == 2
        # aggression this street & previous postflop
        aggr_events = 0
        for st, seat, act, amt in hist:
            if st >= 1 and seat != me and act == "raise":
                aggr_events += 1
        facing = to_call > 0
        bet_frac = to_call / max(1, pot - to_call) if facing else 0
        # aggressive opponents' bets mean less
        agg_factor = 1.0
        if others:
            ag = max(self.aggr(s) for s in others)
            agg_factor = 1.3 - ag  # 0.3..1.3
        pw = 0.0
        if aggr_events:
            pw = (0.6 + 0.6 * min(bet_frac, 1.5)) * aggr_events * max(0.3, agg_factor)
            if hu:
                pw *= 0.6
        eq = self._post_eq(hc, hole, board, opp_w, pw)
        eq_m = eq ** (1.0 + 0.75 * (n_opp - 1))
        spr = my_stack / max(1, pot)
        if not facing:
            if eq_m >= 0.80:
                if spr <= 1.5:
                    return {"action": "allin"}
                return self._ret_raise(obs, max(obs["bb"], pot * 0.9))
            if eq_m >= (0.58 if hu else 0.62):
                if spr <= 0.9:
                    return {"action": "allin"}
                return self._ret_raise(obs, max(obs["bb"], pot * 0.6))
            # bluff/stab when heads-up and checked to
            if n_opp == 1 and ((eq >= 0.42 and self.rng.random() < 0.2) or (hu and eq >= 0.33 and self.rng.random() < 0.45)):
                return self._ret_raise(obs, max(obs["bb"], pot * 0.5))
            return {"action": "check"}
        call_amt = min(to_call, my_stack)
        need = call_amt / (pot + call_amt)
        if eq_m >= 0.82 and "raise" in legal and obs["max_raise_to"] > 0:
            if spr <= 2.5:
                return {"action": "allin"}
            return self._ret_raise(obs, obs["bets"][max(others, key=lambda s: bets[s])] * 3 + pot - sum(bets))
        margin = 0.0 if hu else (0.03 if street == 1 else 0.01)
        if eq_m >= need + margin:
            return self._call(obs)
        return self._passive(obs)
