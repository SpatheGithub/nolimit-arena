import os
import random
from itertools import combinations

import numpy as np

_D = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.npz"))
TURN_VALS = _D["turn_vals"].astype(np.int32)
PRE_EQ = _D["pre_eq"].astype(np.float64)
FLOP_EQ = _D["flop_eq"]
FLOP_STR = _D["flop_str"].astype(np.float32)
TURN_STR = _D["turn_str"].astype(np.float32)
PRE_STR = _D["pre_str"].astype(np.float64)
PRE_MULTI = _D["pre_multi"].astype(np.float64)

RANKS = "TJQKA"
SUITS = "cdhs"
CIDX = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
PAIRS = list(combinations(range(20), 2))
PIDX = [[-1] * 20 for _ in range(20)]
for _k, (_a, _b) in enumerate(PAIRS):
    PIDX[_a][_b] = _k
    PIDX[_b][_a] = _k
PMASK = np.array([(1 << a) | (1 << b) for a, b in PAIRS], dtype=np.int64)
B3IDX = {sum(1 << c for c in b): k for k, b in enumerate(combinations(range(20), 3))}
B4IDX = {sum(1 << c for c in b): k for k, b in enumerate(combinations(range(20), 4))}
# preflop percentile: 0 = best hand
_order = np.argsort(-PRE_STR, kind="stable")
PRE_PCT = np.zeros(190)
_srt = PRE_STR[_order]
for _i in range(190):
    PRE_PCT[_i] = float(np.sum(PRE_STR > PRE_STR[_i] + 1e-9)) / 190.0


_DEBUG = False


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


class Stats:
    __slots__ = ("hands", "vpip", "pfr", "allin", "agg", "pas", "fold_to_bet", "faced_bet")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.allin = 0
        self.agg = 0
        self.pas = 0
        self.fold_to_bet = 0
        self.faced_bet = 0


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nseats = config.get("seats", 8)
        self.stats = [Stats() for _ in range(self.nseats)]
        self.points = config.get("points", [100, 25, 5, 0, 0, 0, 0, 0])
        self.allin_seen = set()

    # ------------------------------------------------------------------ utils
    def _open_width(self, s):
        st = self.stats[s]
        return min(0.9, max(0.06, (st.pfr + 2.5) / (st.hands + 10.0)))

    def _call_width(self, s):
        st = self.stats[s]
        return min(0.95, max(0.15, (st.vpip + 4.5) / (st.hands + 10.0)))

    def _aggr(self, s):
        st = self.stats[s]
        return (st.agg + 2.0) / (st.agg + st.pas + 6.0)

    def _ranges(self, obs, known_mask, b3i, b4i):
        """Weight vectors over the 190 hole pairs for each opponent in hand."""
        valid = ((PMASK & known_mask) == 0).astype(np.float64)
        bb = max(obs["bb"], 1)
        ranges = {}
        for s in obs["in_hand"]:
            if s != self.seat:
                ranges[s] = valid.copy()
        hist = obs["history"]
        nraise = 0
        cur_street = -1
        to_match = 0
        street_bets = {}
        fstr = FLOP_STR[b3i] if b3i is not None else None
        tstr = TURN_STR[b4i] if b4i is not None else None
        stacks = obs["stacks"]
        for st_i, seat, act, amt in hist:
            if st_i != cur_street:
                cur_street = st_i
                street_bets = {}
                to_match = 0
            if act in ("sb", "bb"):
                street_bets[seat] = amt
                to_match = max(to_match, amt)
                continue
            if act == "ante" or act == "return":
                continue
            w = ranges.get(seat)
            if act == "raise":
                prev = street_bets.get(seat, 0)
                street_bets[seat] = amt
                big = amt
                to_match_before = to_match
                to_match = max(to_match, amt)
                if w is None:
                    nraise += 1 if st_i == 0 else 0
                    continue
                if st_i == 0:
                    nraise += 1
                    X = self._open_width(seat)
                    if nraise == 2:
                        X *= 0.45
                    elif nraise >= 3:
                        X *= 0.25
                    # all-in / big shove: width by stack depth
                    rem = stacks[seat] if seat < len(stacks) else 0
                    if rem == 0:
                        self.allin_seen.add(seat)
                        depth = amt / bb
                        st = self.stats[seat]
                        xa = (st.allin + 1.0) / (st.hands + 8.0)
                        if depth <= 8:
                            xd = 0.55
                        elif depth <= 15:
                            xd = 0.35
                        elif depth <= 25:
                            xd = 0.2
                        else:
                            xd = 0.1
                        X = max(X * 0.6, xa, xd)
                    X = max(0.03, min(0.95, X))
                    w *= 0.01 + _sig((X - PRE_PCT) / 0.05)
                else:
                    sv = fstr if st_i == 1 else tstr
                    if sv is None:
                        continue
                    ag = self._aggr(seat)
                    thr = 0.62 - 0.35 * (ag - 0.33) + (0.08 if to_match_before > 0 else 0.0)
                    floor = 0.06 + 0.35 * max(0.0, ag - 0.3)
                    w *= floor + _sig((sv - thr) / 0.07)
            elif act == "call":
                street_bets[seat] = to_match
                if w is None:
                    continue
                if st_i == 0:
                    if nraise == 0:
                        X = min(0.95, self._call_width(seat) * 1.2)
                        w *= 0.05 + _sig((X - PRE_PCT) / 0.08)
                    else:
                        X = min(0.95, self._call_width(seat) * (0.8 if nraise == 1 else 0.45))
                        w *= 0.02 + _sig((X - PRE_PCT) / 0.06)
                else:
                    sv = fstr if st_i == 1 else tstr
                    if sv is None:
                        continue
                    w *= 0.15 + _sig((sv - 0.42) / 0.09)
            elif act == "check":
                if w is None or st_i == 0:
                    continue
                sv = fstr if st_i == 1 else tstr
                if sv is None:
                    continue
                w *= 1.0 - 0.6 * _sig((sv - 0.8) / 0.05)
        return ranges

    # ------------------------------------------------------------------ act
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if _DEBUG:
                raise
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    def _raise_to(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0 or ("raise" not in obs["legal"] and "bet" not in obs["legal"]):
            if obs["to_call"] > 0:
                return {"action": "call"}
            return {"action": "check"}
        amt = int(max(lo, min(hi, amt)))
        if amt >= hi * 0.85:
            amt = hi
        return {"action": "raise", "amount": amt}

    def _passive(self, obs, call):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        if call:
            return {"action": "call"}
        return {"action": "fold"}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        me = self.seat
        hole = [CIDX[c] for c in obs["hole"]]
        board = [CIDX[c] for c in obs["board"]]
        hm = (1 << hole[0]) | (1 << hole[1])
        bm = 0
        for c in board:
            bm |= 1 << c
        mi = PIDX[hole[0]][hole[1]]
        street = obs["street_index"]
        b3i = B3IDX.get((1 << board[0]) | (1 << board[1]) | (1 << board[2])) if len(board) >= 3 else None
        b4i = B4IDX.get(bm) if len(board) == 4 else None
        ranges = self._ranges(obs, hm | bm, b3i, b4i)
        bb = max(obs["bb"], 1)
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks = obs["stacks"]
        S = stacks[me]
        my_bet = obs["bets"][me]
        opps = [s for s in obs["in_hand"] if s != me]
        n_opp = len(opps)
        if n_opp == 0:
            return self._passive(obs, True)

        # equity vs each opponent's range
        eqs = {}
        if street == 0:
            row = PRE_EQ[mi]
        elif street == 1:
            row = FLOP_EQ[b3i, mi].astype(np.float64) * (1.0 / 255.0)
        else:
            v = TURN_VALS[b4i]
            mv = v[mi]
            row = (v < mv) + 0.5 * (v == mv)
        for s, w in ranges.items():
            tw = w.sum()
            eqs[s] = float(np.dot(row, w) / tw) if tw > 1e-9 else 0.5
        eq = 1.0
        for s in eqs:
            eq *= eqs[s]
        # effective stack vs opponents still in
        opp_max = max((stacks[s] + obs["bets"][s]) for s in opps)
        eff = min(S + my_bet, opp_max)
        eff_bb = eff / bb

        if street == 0:
            return self._preflop(obs, mi, eq, eqs, ranges, eff, eff_bb, opps)
        return self._postflop(obs, mi, eq, eqs, eff, opps)

    # ------------------------------------------------------------------ preflop
    def _preflop(self, obs, mi, eq, eqs, ranges, eff, eff_bb, opps):
        me = self.seat
        bb = max(obs["bb"], 1)
        pot = obs["pot"]
        to_call = obs["to_call"]
        S = obs["stacks"][me]
        my_bet = obs["bets"][me]
        hist = obs["history"]
        nraise = sum(1 for h in hist if h[0] == 0 and h[2] == "raise")
        pct = PRE_PCT[mi]
        # players still to act after me (preflop order ends at bb)
        alive = obs["alive"]
        n = len(alive)
        bb_seat = obs["bb_seat"]
        order = []
        if bb_seat in alive:
            k = alive.index(bb_seat)
            order = [alive[(k + 1 + i) % n] for i in range(n)]
        else:
            order = list(alive)
        acted = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise", "fold", "check"))
        if me in order:
            pos = order.index(me)
            behind = [s for s in order[pos + 1:] if s in obs["in_hand"] and obs["stacks"][s] > 0]
        else:
            behind = []
        nb = len(behind)
        limpers = sum(1 for h in hist if h[0] == 0 and h[2] == "call")

        if nraise == 0:
            # unopened or limped pot
            if eff_bb <= 16:
                return self._shove_or_fold(obs, mi, pot, eff, behind, opps)
            if to_call == 0:
                # big blind, limped pot
                if pct <= 0.2 + 0.05 * (nb == 0):
                    return self._raise_to(obs, bb * (3 + limpers))
                return {"action": "check"}
            thr = {0: 0.55, 1: 0.55, 2: 0.45, 3: 0.38, 4: 0.33}.get(nb, 0.28)
            if limpers:
                thr *= 0.75
            elif behind:
                # widen steals when everyone behind is tight
                tight = all(self.stats[s].hands >= 12 and self._call_width(s) < 0.28 for s in behind)
                if tight:
                    thr = min(0.9, thr + 0.25)
            if pct <= thr:
                size = bb * (2.5 + limpers) if eff_bb > 30 else bb * (2.2 + limpers)
                return self._raise_to(obs, size)
            # small blind complete with decent hands
            if to_call <= bb / 2 and pct <= 0.6:
                return {"action": "call"}
            return self._passive(obs, False)

        # facing a raise
        last_raise = max(h[3] for h in hist if h[0] == 0 and h[2] == "raise")
        raisers = [h[1] for h in hist if h[0] == 0 and h[2] == "raise"]
        main = raisers[-1]
        eq_main = eqs.get(main, eq)
        pot_after = pot + to_call
        odds = to_call / pot_after if pot_after > 0 else 0
        commit = to_call >= 0.4 * (S + 0) or eff_bb <= 20
        multi_pen = 0.02 * (len(opps) - 1)
        if commit or obs["max_raise_to"] == 0:
            # all-in-ish decision: shove/call vs fold by chip EV with risk margin
            if obs["max_raise_to"] > 0 and to_call < S and eff_bb <= 25:
                # consider jamming
                risk = eff - my_bet
                fe = self._fold_eq_vs(main, nraise) if to_call < 0.5 * S else 0.0
                ev_jam = fe * pot + (1 - fe) * (eq * 0.93 * (pot + 2 * risk - to_call) - risk)
                ev_call = eq * pot_after - to_call
                margin = 0.01 * eff
                if ev_jam > margin and ev_jam >= ev_call:
                    return {"action": "allin"}
                if ev_call > margin and to_call <= S:
                    return {"action": "call"}
                return self._passive(obs, False)
            ev_call = eq * pot_after - to_call
            if eq > odds + 0.02 + multi_pen:
                return {"action": "call"}
            return self._passive(obs, False)
        # deep: 3bet strong, call medium
        if eq_main >= 0.6 and eq >= 0.45 and nraise <= 2:
            target = last_raise * 3 + (pot - last_raise - my_bet) * 0.5
            if target >= 0.4 * (S + my_bet):
                return {"action": "allin"}
            return self._raise_to(obs, target)
        if eq_main >= 0.66 and nraise >= 3:
            return {"action": "allin"}
        real = 0.82 if len(behind) or len(opps) > 1 else 0.88
        if eq * real > odds + 0.03 + multi_pen and to_call <= 0.25 * S:
            return {"action": "call"}
        return self._passive(obs, False)

    def _fold_eq_vs(self, s, nraise):
        st = self.stats[s]
        x = self._open_width(s)
        # chance the raiser folds to a jam: rough
        base = 0.45 if nraise == 1 else 0.25
        if x > 0.4:
            base += 0.1
        return base

    def _shove_or_fold(self, obs, mi, pot, eff, behind, opps):
        me = self.seat
        to_call = obs["to_call"]
        my_bet = obs["bets"][me]
        bb = max(obs["bb"], 1)
        risk = eff - my_bet
        # opponents call a shove with the top c of hands
        callers = behind if behind else opps
        best_ev = -1e9
        # per-caller call width depending on our shove size relative to bb
        depth = eff / bb
        c0 = 0.18 if depth > 10 else (0.24 if depth > 6 else 0.33)
        nc = max(1, len(callers))
        p_fold_all = 1.0
        cs = []
        for s in callers:
            st = self.stats[s]
            cw = self._call_width(s)
            k = min(1.0, st.hands / 30.0)
            ci = (1 - k) * c0 + k * max(0.08, min(0.6, cw * 0.6))
            cs.append(ci)
            p_fold_all *= (1 - ci)
        c = sum(cs) / len(cs) if cs else c0
        if not cs:
            p_fold_all = (1 - c) ** nc
        # equity vs top-c range
        w = 0.01 + _sig((c - PRE_PCT) / 0.04)
        eq_called = float(np.dot(PRE_EQ[mi], w) / w.sum())
        if nc >= 2:
            eq_called *= 0.93
        ev_shove = p_fold_all * pot + (1 - p_fold_all) * (eq_called * (pot + 2 * risk - to_call + 0) - risk)
        ev_fold = 0.0
        if to_call == 0:
            # BB option: check is free
            if ev_shove > 0.15 * bb * 4 and PRE_PCT[mi] <= 0.3:
                return {"action": "allin"}
            return {"action": "check"}
        if ev_shove > ev_fold + 0.05 * bb:
            return {"action": "allin"}
        return self._passive(obs, False)

    # ------------------------------------------------------------------ postflop
    def _postflop(self, obs, mi, eq, eqs, eff, opps):
        me = self.seat
        pot = obs["pot"]
        to_call = obs["to_call"]
        S = obs["stacks"][me]
        my_bet = obs["bets"][me]
        street = obs["street_index"]
        n_opp = len(opps)
        r = self.rng.random()
        if to_call == 0:
            vthr = 0.58 if n_opp == 1 else 0.5
            if eq >= vthr:
                if S <= 1.1 * pot:
                    return {"action": "allin"}
                frac = 0.75 if eq < 0.8 else 0.6
                return self._raise_to(obs, my_bet + max(obs["bb"], pot * frac))
            if n_opp == 1:
                opp = opps[0]
                fold_rate = self._fold_rate(opp)
                bluff_p = 0.15 + 0.4 * max(0.0, fold_rate - 0.3)
                if street == 1 and eq >= 0.38:
                    bluff_p += 0.15
                if r < bluff_p:
                    if S <= 0.8 * pot:
                        return {"action": "allin"}
                    return self._raise_to(obs, my_bet + max(obs["bb"], pot * 0.6))
            return {"action": "check"}
        pot_after = pot + to_call
        odds = to_call / pot_after
        if eq >= 0.78 or (eq >= 0.68 and n_opp == 1):
            if obs["max_raise_to"] > 0:
                if S <= 2.5 * pot_after or eq >= 0.85:
                    return {"action": "allin"}
                return self._raise_to(obs, my_bet + to_call + pot_after * 0.9)
            return {"action": "call"}
        margin = 0.02 if street == 2 else 0.0
        if eq > odds + margin:
            return {"action": "call"}
        return self._passive(obs, False)

    def _fold_rate(self, s):
        st = self.stats[s]
        return (st.fold_to_bet + 1.0) / (st.faced_bet + 3.0)

    # ------------------------------------------------------------------ observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            ai = set()
            facing = {}
            last_aggr_street = {}
            for st_i, seat, act, amt in hist:
                if seat is None or seat < 0 or seat >= self.nseats:
                    continue
                seen.add(seat)
                if st_i == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    stt = self.stats[seat]
                    if act == "raise":
                        stt.agg += 1
                    elif act in ("call", "check"):
                        stt.pas += 1
                    if act in ("call", "fold", "raise") and last_aggr_street.get(st_i) not in (None, seat):
                        stt.faced_bet += 1
                        if act == "fold":
                            stt.fold_to_bet += 1
                    if act == "raise":
                        last_aggr_street[st_i] = seat
            stacks = event.get("stacks")
            for seat in seen:
                stt = self.stats[seat]
                stt.hands += 1
                if seat in vp:
                    stt.vpip += 1
                if seat in pr:
                    stt.pfr += 1
            for seat in self.allin_seen:
                if 0 <= seat < self.nseats:
                    self.stats[seat].allin += 1
            self.allin_seen = set()
        except Exception:
            pass
