import os
import random

import numpy as np

_D = os.path.join(os.path.dirname(__file__), "data")
H7 = np.load(os.path.join(_D, "h7.npy"))
BIN = np.load(os.path.join(_D, "binom.npy"))
PRE = np.load(os.path.join(_D, "pre.npy"))
HU = np.load(os.path.join(_D, "hu.npy"))
CL = np.load(os.path.join(_D, "cls.npy"))
COLS = np.arange(1, 8)
RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NC = np.array([6.0 if i == j else (4.0 if i > j else 12.0) for i in range(9) for j in range(9)])

# preflop ordering: blend of heads-up and 3-way equity vs random hands
_SCORE = PRE[1] * 0.7 + PRE[2] * 0.3
_ORDER = np.argsort(-_SCORE)
PCT = np.zeros(81)
_cum = 0.0
for _c in _ORDER:
    _cum += NC[_c]
    PCT[_c] = _cum / 630.0
del _cum, _c


P = {"VB_HU": 0.58, "VB_MW": 0.68, "CBET": 0.55, "PUSH_BB": 16, "OPEN": 1.0, "CALLM": 0.01,
     "QS": 1.0, "DISC": 1.6, "ICM": 1.0, "CALLCAP": 0.30, "CBIP": 1, "CAPB": 0.0, "RW": 0.08, "BARREL": 0.07, "MSC": 0, "EP": 1, "SH": 0, "AGA": 1.5}
ICM_M = {2: 0.0, 3: 0.068, 4: 0.084, 5: 0.093, 6: 0.072, 7: 0.06, 8: 0.049}


def eff_pot(obs, me, call_amt):
    """Pot we can actually win if we call: other players' bets above our
    total after calling are returned to them."""
    if not P["EP"]:
        return obs["pot"]
    cap = obs["bets"][me] + call_amt
    return obs["pot"] - sum(max(0, b - cap) for b in obs["bets"])


def cls_of(a, b):
    return int(CL[a, b])


_PS = np.arange(101) / 100.0
RW = 1.0 / (1.0 + np.exp((PCT[None, :] - np.maximum(0.02, _PS)[:, None]) / 0.025))  # 101 x 81
_RWN = RW * NC[None, :]
EQR = (HU @ _RWN.T) / _RWN.sum(axis=1)[None, :]  # 81 x 101: class vs top-p range


# QR[x, r]: fraction of hands with equity >= r/100 against a top-x% range
QR = (((EQR.T[:, None, :] >= (np.arange(101) / 100.0)[None, :, None]) * NC[None, None, :]).sum(-1) / 630.0)


COMBOS = np.array([(a, b) for a in range(36) for b in range(a + 1, 36)])
RWC = RW[:, CL[COMBOS[:, 0], COMBOS[:, 1]]]  # 101 x 630 combo weights


def range_w(p):
    """Weights over the 81 classes for a 'top p' range (smooth edge)."""
    return RW[int(min(1.0, max(0.0, p)) * 100 + 0.5)]


def eq_vs_range(c, p):
    return float(EQR[c, int(min(1.0, max(0.0, p)) * 100 + 0.5)])


def call_range(r):
    """Fraction of hands a typical opponent calls a shove with, given the
    equity r it needs."""
    pts = ((0.25, 0.80), (0.30, 0.62), (0.35, 0.48), (0.40, 0.36), (0.45, 0.27),
           (0.50, 0.19), (0.55, 0.12), (0.60, 0.08))
    if r <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if r <= x1:
            return y0 + (y1 - y0) * (r - x0) / (x1 - x0)
    return 0.06


def shove_range(bb_stack):
    """Fraction of hands an opponent shoves with at a stack of bb_stack BBs."""
    pts = ((3, 0.70), (5, 0.55), (8, 0.40), (10, 0.32), (15, 0.22), (20, 0.14), (30, 0.08), (50, 0.05))
    if bb_stack <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if bb_stack <= x1:
            return y0 + (y1 - y0) * (bb_stack - x0) / (x1 - x0)
    return 0.04


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nrng = np.random.default_rng(config["seed"])
        self.points = list(config.get("points") or [100, 45, 20, 8, 0, 0, 0, 0])
        # opponent stats: seat -> [hands, vpip, pfr, shoves]
        self.stats = {}

    # ------------------------------------------------------------ helpers
    def st(self, s):
        v = self.stats.get(s)
        if v is None:
            v = self.stats[s] = [0, 0, 0, 0, 0, 0, 0, 0]
        return v

    def raise_p(self, s, base):
        v = self.stats.get(s)
        if not v:
            return base
        h = v[0]
        return (v[2] + base * 8) / (h + 8)

    def shove_p(self, s, base):
        v = self.stats.get(s)
        if not v:
            return base
        h = v[0]
        est = (v[3] + base * 6) / (h + 6)
        return max(base * 0.7, est)

    @staticmethod
    def a_fold(obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    @staticmethod
    def a_call(obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def a_raise(self, obs, amt):
        legal = obs["legal"]
        if "raise" in legal or "bet" in legal:
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            amt = int(amt)
            if amt >= hi * 0.8:
                amt = hi
            amt = max(lo, min(hi, amt))
            return {"action": "raise" if "raise" in legal else "bet", "amount": amt}
        return self.a_call(obs)

    def a_allin(self, obs):
        legal = obs["legal"]
        if "raise" in legal or "bet" in legal:
            return {"action": "raise" if "raise" in legal else "bet", "amount": obs["max_raise_to"]}
        return self.a_call(obs)

    # ------------------------------------------------------------ act
    def act(self, obs):
        try:
            if obs["phase"] == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
            if obs["street_index"] == 0:
                return self.preflop(obs)
            return self.postflop(obs)
        except Exception:
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    # ------------------------------------------------------------ preflop
    def preflop(self, obs):
        me = self.seat
        hole = [CID[c] for c in obs["hole"]]
        c = cls_of(hole[0], hole[1])
        pct = PCT[c]
        bb = obs["bb"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        alive = obs["alive"]
        in_hand = obs["in_hand"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        mytot = stacks[me] + bets[me]
        hist = [h for h in obs["history"] if h[0] == 0]
        raises = [h for h in hist if h[2] == "raise"]
        limpers = [h[1] for h in hist if h[2] == "call"]
        # preflop action order
        n = len(alive)
        bi = alive.index(obs["bb_seat"])
        order = [alive[(bi + 1 + k) % n] for k in range(n)]
        myi = order.index(me)
        acted = set(h[1] for h in hist if h[2] in ("fold", "call", "raise", "check"))
        left = [s for s in order[myi + 1:] if s in in_hand and s not in acted]
        if me == obs["sb_seat"] and obs["bb_seat"] in in_hand and obs["bb_seat"] not in left and not raises:
            left = [obs["bb_seat"]]
        others = [s for s in in_hand if s != me]
        eff = min(mytot, max((stacks[s] + bets[s]) for s in others)) if others else mytot
        effbb = eff / bb
        n_players = len(alive)

        if not raises:
            # unopened (maybe limpers)
            lim = [s for s in limpers if s != me and s in in_hand]
            if effbb <= P["PUSH_BB"] or mytot / bb <= 12:
                ev = self.shove_ev(obs, c, left + lim, pot, mytot, bets[me], lim)
                if ev > 0.0:
                    return self.a_allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                return self.a_fold(obs)
            if lim:
                if pct <= 0.13 * P["OPEN"]:
                    return self.a_raise(obs, bb * (3.5 + len(lim)))
                if to_call == 0:
                    return {"action": "check"}
                if to_call <= bb * 0.5 + 0.01 and pct <= 0.45:
                    return self.a_call(obs)
                if to_call <= bb and pct <= 0.22:
                    return self.a_call(obs)
                return self.a_fold(obs)
            nleft = len(left)
            base = {0: 1.0, 1: 0.55, 2: 0.42, 3: 0.32, 4: 0.26, 5: 0.22, 6: 0.18}.get(nleft, 0.16) * P["OPEN"]
            if P["SH"] and n_players <= 3:
                base = max(base, 0.85 if n_players == 2 else {1: 0.65, 2: 0.5}.get(nleft, base))
            if pct <= base:
                amt = bb * 2.5 if nleft > 1 else bb * 3
                return self.a_raise(obs, amt)
            if to_call == 0:
                return {"action": "check"}
            if to_call <= bb * 0.5 + 0.01 and pct <= (0.95 if P["SH"] and n_players == 2 else 0.6):
                return self.a_call(obs)
            return self.a_fold(obs)

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        nraises = len(raises)
        rstack = stacks[raiser] + bets[raiser]
        allin = stacks[raiser] == 0
        call_amt = min(to_call, stacks[me])
        # raiser range estimate
        rbb = rstack / bb
        # late-position first raises (steals) are wider
        behind = n - 1 - order.index(raiser) if raiser in order else 9
        if nraises == 1 and not limpers:
            pos_sh = {1: 1.6, 2: 1.35, 3: 1.15}.get(behind, 1.0)
            pos_op = {1: 2.2, 2: 1.7, 3: 1.3}.get(behind, 1.0)
        else:
            pos_sh = pos_op = 1.0
        if allin or bets[raiser] >= 0.45 * rstack:
            p = min(1.0, self.shove_p(raiser, min(1.0, shove_range(min(rbb, effbb)) * pos_sh)))
            if nraises >= 2:
                p *= 0.6
        else:
            p = min(0.8, self.raise_p(raiser, 0.22 * pos_op))
            if nraises >= 2:
                p = min(p, 0.08)
            if nraises >= 3:
                p = min(p, 0.04)
        # extra players already in the pot reduce equity
        callers_after = [h[1] for h in hist if h[2] == "call" and hist.index(h) > hist.index(last)]
        eq = eq_vs_range(c, p)
        if callers_after:
            eq *= 0.75 ** len(callers_after)
        if len(left) > 0:
            eq *= 0.95 ** len(left)

        commit = call_amt >= 0.4 * mytot or (bets[me] + call_amt) >= 0.5 * mytot
        if allin or commit:
            need = call_amt / (eff_pot(obs, me, call_amt) + call_amt)
            margin = P["CALLM"] + self.icm_margin(obs, call_amt)
            if eq >= need + margin:
                return self.a_allin(obs) if not allin and eq > 0.55 else self.a_call(obs)
            return self.a_fold(obs)

        # non-committing raise
        raise_to = bets[raiser]
        # strong: re-raise
        if pct <= min(0.045, p * 0.4) or (nraises == 1 and pct <= 0.03) or \
                (P["SH"] and n_players == 2 and nraises == 1 and pct <= min(0.12, p * 0.3)):
            if effbb <= 30:
                return self.a_allin(obs)
            return self.a_raise(obs, raise_to * 3 + sum(bets[s] for s in in_hand if s not in (me, raiser)))
        # resteal shove when short
        if effbb <= 22 and nraises == 1:
            need = (eff - bets[me]) / (pot + eff - bets[me])
            fe = 0.45 if p > 0.25 else 0.3
            ev_sh = fe * pot + (1 - fe) * (eq * (pot + eff - bets[me]) - (eff - bets[me]) * (1 - eq) - eq * 0)
            # simplified: shove when equity vs calling range is decent
            eqc = eq_vs_range(c, p * 0.5)
            ev_sh = fe * pot + (1 - fe) * (eqc * (pot + (eff - bets[me])) - (1 - eqc) * (eff - bets[me]))
            if ev_sh > 0 and pct <= 0.2:
                return self.a_allin(obs)
        # call
        need = call_amt / (eff_pot(obs, me, call_amt) + call_amt)
        implied = 0.06 if effbb > 25 else 0.0
        cap = P["CALLCAP"]
        if P["SH"] and n_players <= 3:
            cap = 0.8 if n_players == 2 else 0.5
        if eq + implied >= need + 0.04 and call_amt <= (0.3 if P["SH"] and n_players <= 3 else 0.2) * mytot \
                and pct <= max(cap, p * 1.1):
            return self.a_call(obs)
        return self.a_fold(obs)

    def icm_margin(self, obs, risk):
        """Extra equity needed to risk `risk` chips, calibrated on exact ICM
        breakevens for this points table (full-stack flips)."""
        alive = obs["alive"]
        n = len(alive)
        base = ICM_M.get(n, 0.05)
        if base <= 0:
            return 0.0
        mytot = obs["stacks"][self.seat] + obs["bets"][self.seat]
        avg = sum(obs["stacks"][s] + obs["bets"][s] for s in alive) / n
        frac = min(1.0, risk / max(1, mytot))
        m = base * (0.3 + 0.7 * frac)
        if mytot < 0.5 * avg:
            m *= 0.7
        if P["MSC"]:
            # blind pressure: folding is not free when the average stack is short
            mavg = avg / max(1, obs["sb"] + obs["bb"])
            if mavg < P["MSC"]:
                m *= max(0.25, mavg / P["MSC"])
        return m * P["ICM"]

    def shove_ev(self, obs, c, left, pot, mytot, mybet, lim=()):
        bb = obs["bb"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        ev = 0.0
        pf = 1.0
        myx = min(1.0, shove_range(mytot / bb) * (1.6 if len(left) <= 2 else 1.0))
        for s in left:
            st = stacks[s] + bets[s]
            A = min(mytot, st)
            risk_them = A - bets[s]
            potafter = pot + (A - mybet) + risk_them
            r = risk_them / max(1, potafter)
            q0 = call_range(r)
            qr = float(QR[int(myx * 100 + 0.5), min(100, int(r * 100 + 0.5))])
            q = 0.5 * q0 + 0.5 * qr
            q = min(1.0, q * P["QS"] * (1.3 if s in lim else 1.0))
            v = self.stats.get(s)
            if v and v[0] >= 8:
                vp = (v[1] + 0.3 * 8) / (v[0] + 8)
                q = min(1.0, q * (0.7 + 1.0 * vp))
            if v and v[4] >= 1:
                q = (v[5] + q * 3) / (v[4] + 3)
            E = eq_vs_range(c, q) - self.icm_margin(obs, A)
            dead = pot - mybet - bets[s]
            win = A + dead + mybet
            lose = A - mybet
            ev += pf * q * (E * (win + lose) - lose)
            pf *= 1 - q
        ev += pf * pot
        return ev

    # ------------------------------------------------------------ postflop
    def opp_range(self, obs, s):
        hist = [h for h in obs["history"] if h[0] == 0]
        raised = any(h[1] == s and h[2] == "raise" for h in hist)
        called = any(h[1] == s and h[2] == "call" for h in hist)
        nr = sum(1 for h in hist if h[2] == "raise")
        if raised:
            p = self.raise_p(s, 0.22)
            if nr >= 2:
                p = min(p, 0.12)
            return p
        if called:
            return 0.45 if nr else 0.6
        return 1.0

    def equity(self, obs, hole, board, opps, T=None):
        if len(opps) > 3:
            opps = opps[:3]
        if T is None:
            T = (0, 128, 96, 72)[len(opps)]
        nrng = self.nrng
        dead = np.zeros(36, dtype=bool)
        dead[hole] = True
        dead[board] = True
        okc = ~(dead[COMBOS[:, 0]] | dead[COMBOS[:, 1]])
        deck = np.flatnonzero(~dead)
        pos = np.full(36, -1)
        pos[deck] = np.arange(len(deck))
        need = 5 - len(board)
        r = nrng.random((T, len(deck)))
        ar = np.arange(T)
        valid = np.ones(T, dtype=bool)
        ocs = []
        for s in opps:
            p = self.opp_range(obs, s)
            w = RWC[int(min(1.0, max(0.0, p)) * 100 + 0.5)] * okc
            cum = np.cumsum(w)
            idx = np.searchsorted(cum, nrng.random(T) * cum[-1], side="right")
            np.minimum(idx, 629, out=idx)
            oc = COMBOS[idx]
            p0 = pos[oc[:, 0]]
            p1 = pos[oc[:, 1]]
            valid &= (r[ar, p0] < 1.5) & (r[ar, p1] < 1.5)
            r[ar, p0] = 2.0
            r[ar, p1] = 2.0
            ocs.append(oc)
        if need:
            run = deck[np.argpartition(r, need, axis=1)[:, :need]]
            bfull = np.concatenate([np.broadcast_to(np.array(board), (T, len(board))), run], axis=1)
        else:
            bfull = np.broadcast_to(np.array(board), (T, 5))
        k = len(ocs)
        allh = np.empty((k + 1, T, 7), dtype=np.int64)
        allh[0, :, :2] = hole
        for j, oc in enumerate(ocs):
            allh[j + 1, :, :2] = oc
        allh[:, :, 2:] = bfull
        allh.sort(axis=2)
        vals = H7[BIN[allh, COLS].sum(axis=2)]
        mv = vals[0]
        best = vals[1:].max(axis=0)
        sc = (mv > best) + 0.5 * (mv == best)
        nv = valid.sum()
        if nv < 10:
            return float(sc.mean())
        return float(sc[valid].sum() / nv)

    def postflop(self, obs):
        me = self.seat
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        in_hand = obs["in_hand"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        opps = [s for s in in_hand if s != me]
        live_opps = [s for s in opps if stacks[s] > 0 or bets[s] > 0]
        eq = self.equity(obs, hole, board, opps if opps else live_opps)
        pot = obs["pot"]
        to_call = obs["to_call"]
        mystack = stacks[me]
        street = obs["street_index"]
        hist = obs["history"]
        # was I the last preflop aggressor
        pre_r = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        aggressor = bool(pre_r) and pre_r[-1][1] == me
        n_opp = len(opps)
        cur = [h for h in hist if h[0] == street]
        if to_call == 0:
            # betting decision; an opponent who checked to us is capped
            if cur and n_opp == 1 and all(h[2] == "check" for h in cur):
                eq += P["CAPB"]
            if eq >= P["VB_MW"] or (n_opp == 1 and eq >= P["VB_HU"]):
                frac = 0.66 if eq < 0.85 else 0.75
                return self.a_raise(obs, max(obs["bb"], pot * frac))
            if n_opp == 1 and aggressor and street == 1 and (P["CBIP"] or not cur) and self.rng.random() < P["CBET"]:
                return self.a_raise(obs, max(obs["bb"], pot * 0.4))
            if n_opp == 1 and street >= 2 and not cur and eq >= 0.5 and self.rng.random() < 0.3:
                return self.a_raise(obs, max(obs["bb"], pot * 0.5))
            return {"action": "check"}
        # facing a bet
        call_amt = min(to_call, mystack)
        epot = eff_pot(obs, me, call_amt)
        need = call_amt / (epot + call_amt)
        betfrac = call_amt / max(1, epot - call_amt)
        # opponents' bets mean strength: discount equity
        disc = (0.06 + 0.08 * min(1.5, betfrac)) * P["DISC"]
        if street == 3:
            disc += 0.03
        # barrels: the bettor also bet/raised on earlier postflop streets
        if P["BARREL"]:
            rs = [h for h in cur if h[2] == "raise"]
            bettor = rs[-1][1] if rs else None
            if bettor is not None:
                prev = set(h[0] for h in hist if 1 <= h[0] < street and h[1] == bettor and h[2] == "raise")
                disc += P["BARREL"] * len(prev)
            if street == 3 and betfrac > 1.0:
                disc += 0.04
        # opponent-adaptive: aggressive bettors bluff more, passive ones bet value
        if P["AGA"]:
            rs = [h for h in cur if h[2] == "raise"]
            if rs:
                v = self.stats.get(rs[-1][1])
                if v:
                    afq = (v[6] + 0.4 * 20) / (v[6] + v[7] + 20)
                    disc *= min(1.2, max(0.6, 1.0 - (afq - 0.4) * P["AGA"]))
        # raise wars: every extra raise on this street means a much stronger range
        nr_cur = sum(1 for h in cur if h[2] == "raise")
        if P["RW"] and nr_cur >= 2:
            disc += P["RW"] * (nr_cur - 1)
        eqa = eq - disc
        spr_after = (mystack - call_amt) / max(1, pot + call_amt)
        if P["RW"]:
            if call_amt >= 0.3 * mystack or spr_after < 1.0:
                m = self.icm_margin(obs, max(call_amt, min(mystack, pot)))
                eqa -= m
                eq -= m
            if eqa >= 0.80 or (eqa >= 0.70 and n_opp == 1):
                if "raise" in obs["legal"]:
                    return self.a_raise(obs, bets[max(opps, key=lambda s: bets[s])] * 2.8 + (pot - sum(bets)))
                return self.a_call(obs)
        else:
            if eq >= 0.85 or (eq >= 0.75 and n_opp == 1):
                if "raise" in obs["legal"]:
                    return self.a_raise(obs, bets[max(opps, key=lambda s: bets[s])] * 2.8 + (pot - sum(bets)))
                return self.a_call(obs)
            if call_amt >= 0.3 * mystack:
                m = self.icm_margin(obs, call_amt)
                eqa -= m
                eq -= m
        if eqa >= need or (spr_after < 0.3 and eq >= need):
            return self.a_call(obs)
        return self.a_fold(obs)

    # ------------------------------------------------------------ observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            sh = set()
            for h in hist:
                s = h[1]
                seen.add(s)
                if h[0] == 0:
                    if h[2] in ("call", "raise"):
                        vp.add(s)
                    if h[2] == "raise":
                        pr.add(s)
            stacks_end = event.get("stacks") or []
            pay = event.get("payoffs") or {}
            # shoves: preflop raise-to equal to the stack the player started with
            for h in hist:
                if h[0] == 0 and h[2] == "raise":
                    s = h[1]
                    if s < len(stacks_end):
                        start = stacks_end[s] - pay.get(s, 0)
                        if h[3] >= start > 0:
                            sh.add(s)
            # responses to preflop shoves
            shoved = False
            for h in hist:
                if h[0] != 0:
                    break
                s = h[1]
                if shoved and s != self.seat and h[2] in ("fold", "call", "raise"):
                    v = self.st(s)
                    v[4] += 1
                    if h[2] != "fold":
                        v[5] += 1
                if h[2] == "raise" and s in sh:
                    shoved = True
            # postflop aggression: bets/raises vs checks/calls
            for h in hist:
                if h[0] >= 1 and h[1] != self.seat and h[2] in ("raise", "call", "check"):
                    v = self.st(h[1])
                    if h[2] == "raise":
                        v[6] += 1
                    else:
                        v[7] += 1
            for s in seen:
                if s == self.seat:
                    continue
                v = self.st(s)
                v[0] += 1
                if s in vp:
                    v[1] += 1
                if s in pr:
                    v[2] += 1
                if s in sh:
                    v[3] += 1
        except Exception:
            pass
