"""b07 shortdeck bot: table-driven preflop (class-vs-class equity matrix,
push/fold EV), numpy Monte Carlo postflop equity vs range-weighted opponents,
per-seat VPIP/PFR/aggression reads, ICM-ish risk margins."""

import os
import random

import numpy as np

_D = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.npz"))
RT = _D["RT"].astype(np.int64)
FT = _D["FT"].astype(np.int64)
E = _D["E"]
EQM = _D["EQM"]
PCT = _D["PCT"]

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
P5 = np.array([5 ** (c // 4) for c in range(36)], dtype=np.int64)
SB = np.array([1 << (9 * (c % 4) + c // 4) for c in range(36)], dtype=np.int64)
P5L = [5 ** (c // 4) for c in range(36)]
SBL = [1 << (9 * (c % 4) + c // 4) for c in range(36)]


def _cls(c1, c2):
    a, b = c1 // 4, c2 // 4
    if a == b:
        return a * 9 + a
    hi, lo = (a, b) if a > b else (b, a)
    return hi * 9 + lo if c1 % 4 == c2 % 4 else lo * 9 + hi


CLS = np.zeros((36, 36), dtype=np.int64)
for _i in range(36):
    for _j in range(36):
        if _i != _j:
            CLS[_i, _j] = _cls(_i, _j)
# hand percentile (0 best) per card pair
HPCT = PCT[CLS]
CMB = np.zeros(81)
for _a in range(9):
    for _b in range(9):
        CMB[_a * 9 + _b] = 6 if _a == _b else 4 if _a > _b else 12
# equity of class c vs top-X range, X grid
XG = np.linspace(0.02, 1.0, 50)
_ORD = np.argsort(PCT)
EQR = np.zeros((81, 50))
for _k, _x in enumerate(XG):
    _m = (PCT <= _x).astype(float) * CMB
    if _m.sum() == 0:
        _m[_ORD[0]] = 1.0
    EQR[:, _k] = (E * _m[None, :]).sum(1) / _m.sum()
EQRL = EQR.tolist()
PCTL = PCT.tolist()
EQML = EQM.tolist()

# random index tables for postflop sampling: key (n_unknown, m) -> (M, m)
_rng0 = np.random.default_rng(12345)
IDX = {}
MS = 360
for _n in (29, 30, 31):
    for _m in range(2, 9):
        if _m <= _n:
            IDX[(_n, _m)] = np.argsort(_rng0.random((MS, _n)), axis=1)[:, :_m].astype(np.int64)


def eqr(c, x):
    k = int(round((x - 0.02) / 0.02))
    if k < 0:
        k = 0
    elif k > 49:
        k = 49
    return EQRL[c][k]


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        n = config.get("seats", 8)
        self.n = n
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.aggr = [0] * 16
        self.passv = [0] * 16
        self.allin_calls = [0] * 16
        self.allin_faced = [0] * 16
        self.faced = [0] * 16
        self.folded = [0] * 16
        self.shoves = [0] * 16
        self.start_stacks = [config.get("starting_stack", 2000)] * 16
        self.cbet_plan = False

    def shove_rate(self, s):
        return (self.shoves[s] + 0.3) / (self.hands[s] + 6)

    def fold_rate(self, s):
        return (self.folded[s] + 0.45 * 5) / (self.faced[s] + 5)

    # ---------------- opponent stats ----------------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            bet_street = -1
            bettor = None
            shv = set()
            for h in hist:
                st, s, a = h[0], h[1], h[2]
                if s is None or not isinstance(s, int) or s < 0 or s >= 16:
                    continue
                seen.add(s)
                if st > 0:
                    if bet_street == st and s != bettor and a in ("fold", "call", "raise"):
                        self.faced[s] += 1
                        if a == "fold":
                            self.folded[s] += 1
                    if a == "raise":
                        bet_street = st
                        bettor = s
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                        try:
                            if h[3] >= 0.97 * self.start_stacks[s] and s not in shv:
                                shv.add(s)
                                self.shoves[s] += 1
                        except Exception:
                            pass
                else:
                    if a in ("raise", "bet"):
                        self.aggr[s] += 1
                    elif a == "call":
                        self.passv[s] += 1
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
            stk = event.get("stacks")
            if stk:
                for i, v in enumerate(stk):
                    if i < 16:
                        self.start_stacks[i] = v
        except Exception:
            pass

    def vp_rate(self, s):
        return (self.vpip[s] + 0.35 * 6) / (self.hands[s] + 6)

    def pfr_rate(self, s):
        return (self.pfr[s] + 0.18 * 6) / (self.hands[s] + 6)

    def af(self, s):
        return (self.aggr[s] + 1.0) / (self.passv[s] + 1.5)

    # ---------------- main ----------------
    def act(self, obs):
        try:
            a = self._act(obs)
            return self._legal(a, obs)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def _legal(self, a, obs):
        legal = obs["legal"]
        act = a["action"]
        if act == "raise":
            if "raise" not in legal and "bet" not in legal:
                return {"action": "call"} if "call" in legal else {"action": "check"}
            amt = int(a["amount"])
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if amt >= hi or hi - amt < obs["bb"] * 0.6:
                amt = hi
            if amt < lo:
                amt = lo
            return {"action": "raise" if "raise" in legal else "bet", "amount": int(amt)}
        if act == "fold" and "check" in legal:
            return {"action": "check"}
        if act == "check" and "check" not in legal:
            return {"action": "fold"}
        if act == "call" and "call" not in legal:
            return {"action": "check"} if "check" in legal else {"action": "fold"}
        return a

    def _act(self, obs):
        me = obs["seat"]
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        stacks = obs["stacks"]
        bets = obs["bets"]
        bb = max(1, obs["bb"])
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        if not opps:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "call"}
        if obs["street_index"] == 0:
            return self.preflop(obs, me, hole, stacks, bets, bb, opps)
        return self.postflop(obs, me, hole, board, stacks, bets, bb, opps)

    # ---------------- helpers ----------------
    def risk_margin(self, obs, me, stacks):
        """Extra equity needed to risk tournament life (ICM-ish)."""
        alive = [s for s in obs["alive"]]
        n_alive = len([s for s in range(len(stacks)) if stacks[s] > 0 or s in alive])
        total = sum(stacks) + obs["pot"]
        avg = total / max(1, n_alive)
        mine = stacks[me] + obs["bets"][me]
        m = 0.0
        if n_alive >= 5:
            m += 0.02 + 0.015 * (8 - n_alive) if n_alive <= 6 else 0.02
        elif n_alive >= 3:
            m += 0.02
        # big stacks can gamble less needed; short stacks less margin (blinds eat them)
        if mine > 1.6 * avg:
            m -= 0.01
        if mine < 0.5 * avg:
            m -= 0.02
        return max(0.0, m)

    def preflop_order(self, obs):
        alive = sorted(obs["alive"])
        bbs = obs["bb_seat"]
        n = len(alive)
        if n == 2:
            first = obs["button"] if obs["button"] in alive else obs["sb_seat"]
        else:
            # first alive seat after bb
            first = None
            for k in range(1, 17):
                s = (bbs + k) % max(16, 1)
                if s in alive:
                    first = s
                    break
            cand = [s for s in alive if s > bbs]
            first = cand[0] if cand else alive[0]
        i = alive.index(first)
        return alive[i:] + alive[:i]

    def call_range_for_shove(self, s, shove_bb):
        base = 0.22 if shove_bb >= 15 else 0.27 if shove_bb >= 9 else 0.34 if shove_bb >= 5 else 0.45
        v = self.vp_rate(s)
        return min(0.85, max(0.06, base * (0.6 + 1.15 * v)))

    def shove_gain(self, c, obs, me, stacks, bets, callers):
        pot = obs["pot"]
        my_total = stacks[me] + bets[me]
        ev = 0.0
        rem = 1.0
        bbv = obs["bb"]
        for s in callers:
            their = stacks[s] + bets[s]
            risk = min(my_total, their)
            x = self.call_range_for_shove(s, my_total / bbv)
            eq = eqr(c, x)
            p = rem * x
            rem *= (1 - x)
            final_pot = pot - bets[me] - bets[s] + 2 * risk
            ev += p * (eq * final_pot - risk + bets[me])
        ev += rem * pot
        return ev

    # ---------------- preflop ----------------
    def preflop(self, obs, me, hole, stacks, bets, bb, opps):
        c = _cls(hole[0], hole[1])
        pct = PCTL[c]
        hist = obs["history"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        legal = obs["legal"]
        can_raise = "raise" in legal or "bet" in legal
        my_total = stacks[me] + bets[me]
        eff = min(my_total, max(stacks[s] + bets[s] for s in opps))
        eff_bb = eff / bb
        raisers = [h[1] for h in hist if h[0] == 0 and h[2] == "raise"]
        n_raises = len(raisers)
        limpers = [h[1] for h in hist if h[0] == 0 and h[2] == "call"]
        order = self.preflop_order(obs)
        idx = order.index(me) if me in order else 0
        behind = [s for s in order[idx + 1:] if s in obs["in_hand"] and stacks[s] > 0]
        acted = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise", "fold", "check"))
        if me == obs["bb_seat"] or me == obs["sb_seat"]:
            pass
        n_alive = len(obs["alive"])
        rm = self.risk_margin(obs, me, stacks)

        if n_raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= 13 and can_raise:
                callers = [s for s in opps if s not in acted or s in limpers]
                g = self.shove_gain(c, obs, me, stacks, bets, callers)
                if g > ((0.15 + rm * 3) if n_alive > 3 else 0.0) * bb:
                    return {"action": "allin"}
                if "check" in legal:
                    return {"action": "check"}
                # limp with tiny call in SB when very cheap? fold
                if to_call <= 0:
                    return {"action": "check"}
                return {"action": "fold"}
            nb = len(behind)
            thr = {0: 0.6, 1: 0.55, 2: 0.42, 3: 0.32, 4: 0.25, 5: 0.21, 6: 0.18, 7: 0.16}.get(nb, 0.15)
            if n_alive <= 4:
                thr += 0.06
            if n_alive <= 3:
                thr += 0.08
            if n_alive == 2:
                thr = max(thr, 0.85)
            thr -= 0.03 * len(limpers)
            if behind:
                avp = sum(self.vp_rate(s) for s in behind) / len(behind)
                if avp < 0.25:
                    thr += 0.08 if nb <= 3 else 0.04
                elif avp > 0.5:
                    thr -= 0.04
            # loose-passive table: slightly tighter when many limpers
            if pct <= thr and can_raise:
                size = (2.3 if nb > 2 else 2.5) * bb + len(limpers) * bb
                if me == obs["sb_seat"] and nb == 1:
                    size = 3 * bb
                if eff_bb <= 22 and pct <= 0.10:
                    return {"action": "allin"} if eff_bb <= 16 else {"action": "raise", "amount": bets[me] + size}
                return {"action": "raise", "amount": size}
            if "check" in legal:
                return {"action": "check"}
            # SB complete with decent hands vs BB
            if me == obs["sb_seat"] and nb == 1 and to_call <= bb * 0.5 and pct <= 0.75:
                return {"action": "call"}
            if limpers and to_call <= bb and pct <= 0.30 and nb <= 2:
                return {"action": "call"}
            return {"action": "fold"}

        # facing raise(s)
        last = raisers[-1]
        last_amt = max(h[3] for h in hist if h[0] == 0 and h[2] == "raise")
        raiser_total = stacks[last] + bets[last]
        raiser_allin = stacks[last] == 0
        # raiser's range
        x = self.pfr_rate(last)
        if n_raises >= 2:
            x *= 0.45
        size_bb = last_amt / bb
        if size_bb > 6:
            x *= 0.8
        if raiser_allin:
            rbb = raiser_total / bb
            sr = self.shove_rate(last)
            if n_raises == 1:
                if rbb <= 16:
                    pr = 0.55 if rbb <= 5 else 0.42 if rbb <= 8 else 0.32 if rbb <= 12 else 0.24
                    pr *= 0.7 + 0.9 * self.vp_rate(last)
                else:
                    pr = 0.06
                x = max(pr, sr * 1.3)
            else:
                x = max(0.12 if rbb <= 12 else 0.05, sr)
        x = min(0.9, max(0.03, x))
        eq = eqr(c, x)
        # multiway: equity vs each opponent who has put money in voluntarily
        last_i = max(i for i, h in enumerate(hist) if h[0] == 0 and h[2] == "raise")
        prod_eq = eq
        n_vs = 1
        for s in opps:
            if s == last:
                continue
            acts = [(i, h[2]) for i, h in enumerate(hist) if h[0] == 0 and h[1] == s and h[2] in ("call", "raise")]
            if not acts:
                continue
            i_s, a_s = acts[-1]
            if a_s == "raise":
                xs = self.pfr_rate(s)
            elif i_s > last_i:
                xs = 0.10 if raiser_allin else min(0.5, self.vp_rate(s) * 0.6)
            else:
                xs = min(0.9, self.vp_rate(s) * 1.1)
            prod_eq *= eqr(c, min(0.9, max(0.04, xs)))
            n_vs += 1
        if n_vs > 1:
            eq = prod_eq ** 0.8
        po = to_call / (pot + to_call)
        commit_frac = to_call / max(1, my_total)
        # 3bet / shove with strong hands
        strong = eq >= 0.60 or pct <= 0.035
        if strong and can_raise:
            if eff_bb <= 25 or commit_frac > 0.3 or n_raises >= 2:
                return {"action": "allin"}
            return {"action": "raise", "amount": int(last_amt * 3 + (pot - sum(bets)) )}
        # short: reshove vs open
        if can_raise and eff_bb <= 16 and n_raises == 1 and not raiser_allin:
            # reshove if fold equity + equity good
            fe = 1 - min(0.9, max(0.15, 0.55 - 0.5 * x)) if False else 0.45
            win_now = pot
            risk = min(my_total, raiser_total)
            final_pot = pot - bets[me] - bets[last] + 2 * risk
            g = fe * win_now + (1 - fe) * (eqr(c, x * 0.6) * final_pot - risk + bets[me])
            if g > (0.3 + rm * 3) * bb and eq > 0.47:
                return {"action": "allin"}
        need = po + 0.02 + (rm if commit_frac > 0.25 else 0.0)
        if commit_frac < 0.25 and not raiser_allin:
            # implied/position
            closing = not [s for s in behind if s != last]
            need = po + (0.05 if closing else 0.08)
            if eq >= need and pct <= (0.40 if closing else 0.33):
                return {"action": "call"}
            return {"action": "fold"}
        if eq >= need:
            return {"action": "call"}
        return {"action": "fold"}

    # ---------------- postflop ----------------
    def equity(self, hole, board, opps_info):
        """opps_info: list of (range_x, aggressive_weight) for up to 3 opps."""
        known = set(hole) | set(board)
        rem = np.array([c for c in range(36) if c not in known], dtype=np.int64)
        need = 5 - len(board)
        k = len(opps_info)
        m = need + 2 * k
        idx = IDX[(len(rem), m)]
        cards = rem[idx]
        bp = sum(P5L[c] for c in board)
        bs = sum(SBL[c] for c in board)
        if need:
            run = cards[:, :need]
            rp = P5[run].sum(1) + bp
            rs = SB[run].sum(1) + bs
        else:
            rp = np.full(MS, bp, dtype=np.int64)
            rs = np.full(MS, bs, dtype=np.int64)
        hp = rp + (P5L[hole[0]] + P5L[hole[1]])
        hs = rs + (SBL[hole[0]] + SBL[hole[1]])
        hv = RT[hp]
        for s in range(4):
            hv = np.maximum(hv, FT[(hs >> (9 * s)) & 511])
        w = np.ones(MS)
        best = np.full(MS, -1, dtype=np.int64)
        ties = np.zeros(MS)
        cbp = sum(P5L[c] for c in board)
        cbs = sum(SBL[c] for c in board)
        for j in range(k):
            o1 = cards[:, need + 2 * j]
            o2 = cards[:, need + 2 * j + 1]
            op = rp + P5[o1] + P5[o2]
            os_ = rs + SB[o1] + SB[o2]
            ov = RT[op]
            for s in range(4):
                ov = np.maximum(ov, FT[(os_ >> (9 * s)) & 511])
            x, ag = opps_info[j]
            hp_ = HPCT[o1, o2]
            if x < 0.99:
                w = w * np.where(hp_ <= x, 1.0, 0.12)
            if ag > 0 and len(board) >= 3:
                # current strength of opp on present board
                cp = cbp + P5[o1] + P5[o2]
                cs = cbs + SB[o1] + SB[o2]
                cv = RT[cp]
                for s in range(4):
                    cv = np.maximum(cv, FT[(cs >> (9 * s)) & 511])
                r = np.argsort(np.argsort(cv)) / MS
                r2 = r * r
                w = w * (0.04 + ag * r2 * r2 * 4.0 + (1 - ag) * 0.7)
            ties = np.where(ov == best, ties + 1, np.where(ov > best, 0, ties))
            best = np.maximum(best, ov)
        win = np.where(hv > best, 1.0, np.where(hv == best, 1.0 / (ties + 2), 0.0))
        sw = w.sum()
        if sw <= 0:
            return float(win.mean())
        return float((win * w).sum() / sw)

    def postflop(self, obs, me, hole, board, stacks, bets, bb, opps):
        hist = obs["history"]
        st = obs["street_index"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        bet_ratio = to_call / max(1, pot - to_call)
        legal = obs["legal"]
        can_raise = "raise" in legal or "bet" in legal
        my_stack = stacks[me]
        # preflop info per opp
        pf_raisers = [h[1] for h in hist if h[0] == 0 and h[2] == "raise"]
        pf_aggr = pf_raisers[-1] if pf_raisers else None
        live = [s for s in opps if stacks[s] > 0 or True]
        infos = []
        # aggression this street & previous
        street_aggr = {}
        for h in hist:
            if h[0] == st and h[2] in ("raise", "bet"):
                street_aggr[h[1]] = street_aggr.get(h[1], 0) + 1
        prev_aggr = {}
        for h in hist:
            if 0 < h[0] < st and h[2] in ("raise", "bet"):
                prev_aggr[h[1]] = prev_aggr.get(h[1], 0) + 1
        ranked = []
        for s in live:
            if s in pf_raisers:
                x = self.pfr_rate(s) * (0.7 if len(pf_raisers) >= 2 and s == pf_aggr else 1.0)
            else:
                vp = self.vp_rate(s)
                x = vp if any(h[0] == 0 and h[1] == s and h[2] == "call" for h in hist) else 1.0
            x = min(1.0, max(0.08, x * 1.1))
            ag = 0.0
            if s in street_aggr:
                a_f = self.af(s)
                ag = 0.85 if a_f < 1.0 else 0.65 if a_f < 2.5 else 0.4
                if street_aggr[s] >= 2:
                    ag = min(1.0, ag + 0.2)
                if st == 3:
                    ag = min(1.0, ag + 0.15)
                if s in prev_aggr:
                    ag = min(1.0, ag + 0.1 * prev_aggr[s])
                # small bets say less about strength
                ag *= min(1.0, 0.35 + 1.3 * bet_ratio)
            elif s in prev_aggr:
                ag = 0.25
            ranked.append((ag, x, s))
        ranked.sort(reverse=True)
        infos = [(x, ag) for ag, x, s in ranked[:3]]
        eq = self.equity(hole, board, infos)
        n_opp = len(opps)
        if n_opp > 3:
            eq = eq ** (n_opp / 3.0)
        rm = self.risk_margin(obs, me, stacks)
        pot_after = pot + to_call
        if to_call == 0:
            if not can_raise:
                return {"action": "check"}
            fe = 1.0
            for s in opps:
                fe *= self.fold_rate(s)
            vb = 0.62 if n_opp == 1 else 0.70 if n_opp == 2 else 0.76
            if st == 3:
                vb += 0.04
            if fe < 0.33:
                vb -= 0.03
            elif fe > 0.55:
                vb += 0.02
            if eq >= vb:
                frac = 0.65 if eq < 0.85 else 0.8
                if fe < 0.33:
                    frac += 0.15
                amt = int(pot * frac)
                if my_stack <= pot * 1.1:
                    return {"action": "allin"}
                return {"action": "raise", "amount": max(obs["min_raise_to"], amt)}
            # c-bet / probe bluff, scaled by how often they fold to bets
            iam_aggr = pf_aggr == me
            pb = min(0.85, max(0.1, 1.7 * fe - 0.25))
            if n_opp == 1 and st == 1 and iam_aggr and eq >= 0.25 and self.rng.random() < pb:
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(pot * 0.5))}
            if n_opp == 2 and st == 1 and iam_aggr and eq >= 0.4 and self.rng.random() < pb:
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(pot * 0.5))}
            if n_opp == 1 and st >= 2 and eq >= 0.45 and self.rng.random() < 0.6 * pb:
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(pot * 0.55))}
            if n_opp == 1 and st == 2 and iam_aggr and eq >= 0.30 and self.rng.random() < 0.5 * pb:
                return {"action": "raise", "amount": max(obs["min_raise_to"], int(pot * 0.55))}
            return {"action": "check"}
        po = to_call / (pot_after)
        allin_call = to_call >= my_stack
        big = to_call > 0.4 * (my_stack + bets[me])
        rv = 0.78 if n_opp == 1 else 0.84
        if eq >= rv and can_raise:
            if my_stack <= pot_after * 1.2 or st == 3 and eq > 0.9:
                return {"action": "allin"}
            cur = max(bets)
            amt = int(cur * 2.5 + (pot - sum(bets)) * 0.5)
            return {"action": "raise", "amount": max(obs["min_raise_to"], amt)}
        margin = 0.03 + (0.0, 0.05, 0.07, 0.09)[st]
        bettor = None
        for h in hist:
            if h[0] == st and h[2] == "raise" and h[1] != me:
                bettor = h[1]
        if bettor is not None:
            a_f = self.af(bettor)
            if a_f < 0.8:
                margin += 0.03
            elif a_f > 2.5:
                margin -= 0.03
        margin *= min(1.0, bet_ratio / 0.6)
        need = po + margin + (rm if (allin_call or big) else 0.0)
        if eq >= need:
            if eq >= 0.55 and my_stack <= pot_after * 0.5 and can_raise:
                return {"action": "allin"}
            return {"action": "call"}
        return {"action": "fold"}
