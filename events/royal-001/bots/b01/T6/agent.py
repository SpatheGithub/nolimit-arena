import random

from .tables import (RIDX, FLOP, TURN, PRELIST, PRE1, PRE_TOP, eq_vs_top)

DEBUG = False
AGGR = True
FIX = True
WIDE_OPEN = False
LOOSE_CALL = True
SHORTHAND = False


def _cls(r1, r2):
    return (r1, r2) if r1 <= r2 else (r2, r1)


PAY = (100.0, 25.0, 5.0)


def _icm(st):
    """Malmuth-Harville for few players (<= 4), payouts PAY."""
    n = len(st)
    res = [0.0] * n

    def rec(rem, place, prob):
        tot = sum(st[i] for i in rem)
        if place >= len(PAY) or not rem:
            return
        if tot <= 0:
            return
        for i in rem:
            p = prob * st[i] / tot
            if p <= 0:
                continue
            res[i] += p * PAY[place]
            rec([j for j in rem if j != i], place + 1, p)
    rec(list(range(n)), 0, 1.0)
    return res


def icm_req(obs, me, opp, x):
    """Equity needed to call x chips (all-in-ish) vs opp, by ICM. None if not applicable."""
    alive = [s for s in obs["alive"] if obs["stacks"][s] + obs["bets"][s] > 0 or s == me]
    if len(alive) > 4 or len(alive) < 3:
        return None
    stacks = obs["stacks"]
    pot = obs["pot"]
    idx = {s: i for i, s in enumerate(alive)}
    if opp not in idx or me not in idx:
        return None
    base = [float(stacks[s]) for s in alive]
    fold = list(base)
    fold[idx[opp]] += pot
    win = list(base)
    win[idx[me]] += pot
    win[idx[opp]] = max(0.0, win[idx[opp]] - max(0, x - obs["bets"][opp]) * 0)
    lose = list(base)
    lose[idx[me]] -= x
    lose[idx[opp]] += pot + x
    ef = _icm(fold)[idx[me]]
    ew = _icm(win)[idx[me]]
    el = _icm(lose)[idx[me]]
    if ew - el <= 1e-9:
        return None
    return (ef - el) / (ew - el)


class Opp:
    __slots__ = ("hands", "vpip", "pfr", "bets", "calls", "faced", "folded", "allin_pre")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.bets = 0      # postflop bets/raises
        self.calls = 0     # postflop calls
        self.faced = 0     # postflop times faced a bet
        self.folded = 0    # postflop folds to a bet
        self.allin_pre = 0

    def vpip_rate(self):
        return (self.vpip + 3.0 * 0.35) / (self.hands + 3.0)

    def pfr_rate(self):
        return (self.pfr + 3.0 * 0.18) / (self.hands + 3.0)

    def fold_rate(self):
        return (self.folded + 3.0 * 0.4) / (self.faced + 3.0)

    def agg(self):
        # share of postflop actions that are bets/raises
        return (self.bets + 2.0 * 0.4) / (self.bets + self.calls + 2.0)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.nseats = config.get("seats", 8)
        self.opp = {}

    # ------------------------------------------------------------------
    def _o(self, s):
        o = self.opp.get(s)
        if o is None:
            o = self.opp[s] = Opp()
        return o

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur_bet = {}
            street_bet = 0
            last_street = -1
            for st, s, a, amt in hist:
                if st != last_street:
                    last_street = st
                    street_bet = 0
                if a in ("sb", "bb", "ante"):
                    seen.add(s)
                    if a != "ante":
                        street_bet = max(street_bet, amt)
                    continue
                if s == self.seat:
                    continue
                seen.add(s)
                o = self._o(s)
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                        street_bet = max(street_bet, amt)
                else:
                    if a == "raise":
                        if street_bet > 0:
                            o.faced += 1
                        o.bets += 1
                        street_bet = max(street_bet, amt)
                    elif a == "call":
                        o.faced += 1
                        o.calls += 1
                    elif a == "fold":
                        o.faced += 1
                        o.folded += 1
            for s in seen:
                if s == self.seat:
                    continue
                o = self._o(s)
                o.hands += 1
                if s in vp:
                    o.vpip += 1
                if s in pr:
                    o.pfr += 1
        except Exception:
            pass

    # ------------------------------------------------------------------
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if DEBUG:
                import traceback
                print("ERR", traceback.format_exc().replace("\n", " | "))
            if "check" in obs.get("legal", ()):
                return {"action": "check"}
            return {"action": "fold"}

    def _passive(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _call(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "call"}

    def _raise(self, obs, amt):
        legal = obs["legal"]
        mx = obs.get("max_raise_to", 0) or 0
        mn = obs.get("min_raise_to", 0) or 0
        if mx <= 0 or not ("raise" in legal or "bet" in legal):
            return self._call(obs)
        amt = int(amt)
        if amt >= mx * 0.85:
            amt = mx
        if amt < mn:
            amt = mn
        if amt > mx:
            amt = mx
        return {"action": "raise" if "raise" in legal else "bet", "amount": amt}

    def _allin(self, obs):
        legal = obs["legal"]
        mx = obs.get("max_raise_to", 0) or 0
        if mx > 0 and ("raise" in legal or "bet" in legal):
            return {"action": "raise" if "raise" in legal else "bet", "amount": mx}
        return self._call(obs)

    # ------------------------------------------------------------------
    def _act(self, obs):
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        me = obs["seat"]
        self.seat = me
        hole = obs["hole"]
        board = obs["board"]
        hr = [RIDX[c[0]] for c in hole]
        br = [RIDX[c[0]] for c in board]
        h = _cls(hr[0], hr[1])
        street = obs["street_index"]
        # straight flush check
        allc = hole + board
        if len(allc) >= 5:
            for su in "cdhs":
                if sum(1 for c in allc if c[1] == su) >= 5 and \
                        len(set(c[0] for c in allc if c[1] == su)) >= 5:
                    return self._allin(obs)
        if street == 0:
            return self._preflop(obs, h)
        return self._postflop(obs, h, br, street)

    # ------------------------------------------------------------------
    def _ranges_pre(self, obs):
        """Per-opponent preflop range fraction from this hand's actions."""
        me = obs["seat"]
        fr = {}
        nraise = {}
        for st, s, a, amt in obs["history"]:
            if st != 0 or s == me:
                continue
            if a == "raise":
                nraise[s] = nraise.get(s, 0) + 1
                fr[s] = "r"
            elif a == "call":
                if s not in fr:
                    fr[s] = "c"
        out = {}
        na = len(obs["alive"])
        # short-handed: raise/call ranges are much wider than 8-handed stats suggest
        floor = (0.55 if na == 2 else (0.35 if na == 3 else 0.0)) if SHORTHAND else 0.0
        for s in obs["in_hand"]:
            if s == me:
                continue
            o = self._o(s)
            t = fr.get(s)
            if t == "r":
                f = min(0.6, max(0.1, o.pfr_rate() * 1.2))
                if nraise.get(s, 0) >= 2:
                    f *= 0.5
                    f = max(f, floor * 0.6)
                else:
                    f = max(f, floor)
            elif t == "c":
                f = min(0.85, max(0.2, o.vpip_rate() * 1.1))
                f = max(f, min(0.9, floor + 0.2) if floor else f)
            else:
                f = 1.0
            out[s] = f
        return out

    def _preflop(self, obs, h):
        me = obs["seat"]
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        my_total = my_stack + bets[me]
        others = [s for s in obs["in_hand"] if s != me]
        if not others:
            return self._call(obs)
        opp_max = max(stacks[s] + bets[s] for s in others)
        eff = min(my_total, opp_max)
        M = eff / bb
        hist = obs["history"]
        raises = [(s, amt) for st, s, a, amt in hist if st == 0 and a == "raise"]
        acted = set(s for st, s, a, amt in hist if st == 0 and a in ("call", "raise", "fold", "check"))
        behind = [s for s in others if s not in acted]
        callers = [s for st, s, a, amt in hist if st == 0 and a == "call"]
        top = PRE_TOP[h]       # fraction of hands at least as strong (smaller = better)
        lst = PRELIST[h]
        ranges = self._ranges_pre(obs)
        nr = len(raises)

        if nr == 0:
            # unopened or limped pot
            n_behind = len(behind)
            if M <= (12 if AGGR else 13):
                return self._pushfold(obs, h, behind + callers, M, pot, my_stack)
            if WIDE_OPEN:
                thr = {0: 0.7, 1: 0.7, 2: 0.6, 3: 0.52, 4: 0.44, 5: 0.35}.get(n_behind, 0.32)
            else:
                thr = {0: 0.6, 1: 0.6, 2: 0.52, 3: 0.44, 4: 0.35, 5: 0.32}.get(n_behind, 0.25)
            if callers:
                thr = min(thr, 0.35)
            if top <= thr:
                size = bb * (2.5 + len(callers)) + (0.5 * bb if obs["sb_seat"] == me else 0)
                if M <= 22:
                    size = bb * (2.2 + len(callers))
                return self._raise(obs, size)
            if to_call == 0:
                return {"action": "check"}
            # limp/complete from SB with decent hands when cheap
            if to_call <= bb * 0.5 + 1 and top <= 0.8 and not behind[1:]:
                return self._call(obs)
            if callers and to_call <= bb and top <= 0.6:
                return self._call(obs)
            return self._passive(obs)

        # facing raise(s)
        last_raiser, last_amt = raises[-1]
        po = to_call / float(pot + to_call)
        eq = 1.0
        n_b = 0
        for s in others:
            f = ranges.get(s, 1.0)
            if s in behind:
                n_b += 1
                continue
            # adjust for all-in shoves by short stacks: wider
            rs = stacks[s] + bets[s]
            if s == last_raiser and rs <= 12 * bb and stacks[s] == 0:
                f = max(f, 0.35)
            e = eq_vs_top(lst, f)
            eq *= e if (s == last_raiser or not FIX) else e ** 0.6
        if n_b:
            if FIX:
                # chance someone behind wakes up with a top-8% hand
                pw = 1.0 - 0.92 ** n_b
                eq *= (1.0 - pw) + pw * eq_vs_top(lst, 0.08)
            else:
                eq *= (0.8 + 0.2 * eq_vs_top(lst, 0.2)) ** n_b
        raiser_all_in = stacks[last_raiser] == 0
        commit_frac = to_call / float(max(1, my_stack))
        # short effective stack: shove or fold
        if M <= 18 or commit_frac >= 0.35:
            need = po + (0.02 if commit_frac > 0.5 else 0.0)
            if commit_frac >= 0.3:
                r = icm_req(obs, me, last_raiser, min(to_call, my_stack))
                if r is not None:
                    need = max(po, r)
            if raiser_all_in or (stacks[me] <= to_call):
                return self._call(obs) if eq >= need else self._passive(obs)
            # 3-bet shove: fold equity from raiser
            fr = ranges.get(last_raiser, 0.3)
            fold_p = 0.0 if nr >= 2 else max(0.0, min(0.6, 1.0 - min(1.0, 0.45 / max(fr, 0.05))))
            risk = my_stack
            win_pot = pot + min(my_stack, opp_max)
            ev_shove = fold_p * pot + (1 - fold_p) * (eq * (win_pot + min(risk, opp_max)) - min(risk, opp_max))
            if eq >= 0.55 or ev_shove > 0:
                return self._allin(obs)
            if eq >= need and commit_frac < 0.3:
                return self._call(obs)
            return self._passive(obs)
        # deep
        if nr == 1:
            if eq >= 0.6 or (top <= 0.07):
                size = last_amt * 3 + bb * len(callers)
                return self._raise(obs, size)
            if eq >= po + 0.04 and to_call <= 0.12 * my_stack:
                return self._call(obs)
            return self._passive(obs)
        # facing a 3-bet or more
        if top <= 0.04 or eq >= 0.62:
            return self._allin(obs) if M <= 40 else self._raise(obs, last_amt * 2.5)
        if eq >= po + 0.06 and to_call <= 0.2 * my_stack:
            return self._call(obs)
        return self._passive(obs)

    def _pushfold(self, obs, h, threats, M, pot, my_stack):
        lst = PRELIST[h]
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        p_all_fold = 1.0
        cf = []
        for s in threats:
            o = self._o(s)
            st = stacks[s] + bets[s]
            # calling range: tighter when our shove is big relative to their stack
            c = (0.15 if AGGR else 0.18) + 0.25 * (o.vpip_rate() - 0.35)
            if st < my_stack:
                c += 0.05
            c = min(0.5, max(0.08, c))
            if SHORTHAND:
                na = len(obs["alive"])
                if na == 2:
                    c = max(c, 0.45)
                elif na == 3:
                    c = max(c, 0.28)
            cf.append(c)
            p_all_fold *= (1 - c)
        cmean = sum(cf) / len(cf) if cf else 0.2
        eq = eq_vs_top(lst, cmean)
        risk = my_stack
        call_size = min(risk, max([stacks[s] + bets[s] for s in threats] or [risk]))
        ev = p_all_fold * pot + (1 - p_all_fold) * (eq * (pot + call_size + min(risk, call_size)) - min(risk, call_size))
        if ev > 0.0 * bb or PRE_TOP[h] <= 0.15:
            return self._allin(obs)
        if obs["to_call"] == 0:
            return {"action": "check"}
        return self._passive(obs)

    # ------------------------------------------------------------------
    def _postflop(self, obs, h, br, street):
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        others = [s for s in obs["in_hand"] if s != me]
        if not others:
            return self._call(obs)
        bkey = tuple(sorted(br))
        if street == 1:
            ent = FLOP.get((h, bkey))
        else:
            ent = TURN.get((h, bkey[:4]))
        if ent is None:
            return self._call(obs) if to_call == 0 else self._passive(obs)
        eq_rand, lst = ent
        pre_r = self._ranges_pre(obs)
        # postflop narrowing per opponent
        nb = {}
        nc = {}
        for st, s, a, amt in obs["history"]:
            if st == 0 or s == me:
                continue
            if a == "raise":
                nb[s] = nb.get(s, 0) + 1
            elif a == "call":
                nc[s] = nc.get(s, 0) + 1
        eq = 1.0
        eq_call = 1.0
        bettor = None
        cur = max(bets) if bets else 0
        for s in others:
            f = pre_r.get(s, 1.0) ** 0.5
            o = self._o(s)
            ag = o.agg()
            bf = (0.65 if LOOSE_CALL else 0.35) + 0.5 * ag  # aggressive players bet wider
            f *= bf ** nb.get(s, 0)
            f *= 0.8 ** nc.get(s, 0)
            if bets[s] == cur and cur > 0:
                bettor = s
            if stacks[s] == 0 and nb.get(s, 0) > 0:
                f = max(f, 0.08)
            eq *= eq_vs_top(lst, f)
            c = max(0.25, min(0.9, 1.0 - o.fold_rate()))
            eq_call *= eq_vs_top(lst, f * c)
        n = len(others)
        share = eq * (n + 1)
        bb = max(1, obs["bb"])
        if to_call == 0:
            # check or bet: value judged against the calling part of their range
            value = (eq_call >= 0.5) if n == 1 else (eq_call * (n + 1) >= 1.3)
            if value or (street == 1 and share >= 1.45 and eq >= 0.45):
                frac = 0.8 if eq_call >= 0.68 else 0.6
                amt = frac * pot
                if my_stack <= 1.4 * pot:
                    return self._allin(obs) if (eq_call >= 0.55 or share >= 1.5) else self._raise(obs, amt)
                return self._raise(obs, amt)
            if n == 1:
                o = self._o(others[0])
                fr = o.fold_rate()
                if AGGR and street == 1 and nb.get(others[0], 0) == 0:
                    pre_raisers = [s for st, s, a, amt in obs["history"] if st == 0 and a == "raise"]
                    if pre_raisers and pre_raisers[-1] == me and fr >= 0.3 and self.rng.random() < 0.8:
                        return self._raise(obs, 0.5 * pot)
                if eq < 0.35 and fr >= 0.45 and self.rng.random() < 0.5:
                    return self._raise(obs, 0.5 * pot)
                if 0.35 <= eq < 0.5 and street == 1 and fr >= 0.5 and self.rng.random() < 0.3:
                    return self._raise(obs, 0.5 * pot)
            return {"action": "check"}
        # facing a bet
        po = to_call / float(pot + to_call)
        commit = to_call / float(max(1, my_stack))
        if share >= 1.75 and eq >= 0.8:
            amt = cur + 0.9 * (pot + to_call)
            if amt >= 0.5 * (my_stack + bets[me]):
                return self._allin(obs)
            return self._raise(obs, amt)
        margin = 0.02 + (0.03 if commit > 0.5 else 0.0)
        need = po + margin
        if commit >= 0.3 and bettor is not None:
            r = icm_req(obs, me, bettor, min(to_call, my_stack))
            if r is not None:
                need = max(po, r)
        if eq >= need:
            return self._call(obs)
        return self._passive(obs)
