import json
import os
import random

import numpy as np

from . import ev

_D = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_D, "pre.json")) as _f:
    _PRE = json.load(_f)
CLS = _PRE["cls"]                      # 36x36 -> class id
CLS_NP = np.array(CLS, dtype=np.int64)
EQK = _PRE["eqk"]                      # class -> [_, eq vs 1..7 random]
PCT = _PRE["pct"]                      # class -> percentile (0 best)
PCT_NP = np.array(PCT)
GRID = _PRE["grid"]
VSR = _PRE["vsr"]                      # class -> eq vs top-x range (grid)
CARD = ev.CARD

NS = 200
SHOVE_BB = 13
SHOVE_MARGIN = 0.1
CALL_K = 0.15
HU_OPEN = 0.8
HU_RX = 0.45
VAL_HU = 0.6
BLUFF_K = 1.6
CALL_MARGIN = 0.09
CALL_PCT = 0.45
VAL_MW = 0.72
STEAL_W = 1.4
POST_MARGIN = 0.04
_brng = np.random.default_rng(12345)
BANK = {m: np.argsort(_brng.random((2048, m)), axis=1).astype(np.int64) for m in (29, 30, 31, 32, 33, 34)}


def vsr(c, x):
    """equity of class c vs top-x range (interpolated)."""
    row = VSR[c]
    if x <= GRID[0]:
        return row[0]
    for i in range(1, len(GRID)):
        if x <= GRID[i]:
            t = (x - GRID[i - 1]) / (GRID[i] - GRID[i - 1])
            return row[i - 1] * (1 - t) + row[i] * t
    return row[-1]


def icm(stacks, payouts):
    n = len(stacks)
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    paid = max((k + 1 for k, p in enumerate(pay) if p), default=0)
    memo = {}

    def rest(mask):
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < paid:
            total = sum(stacks[i] for i in members)
            for i in members:
                p = stacks[i] / total if total > 0 else 1 / len(members)
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


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nrng = np.random.default_rng(config["seed"])
        self.points = config.get("points") or [100, 45, 20, 8, 0, 0, 0, 0]
        self.st = {}  # seat -> stats
        self.pf_aggr = False

    # ---------- stats ----------
    def S(self, s):
        d = self.st.get(s)
        if d is None:
            d = self.st[s] = {"h": 0, "vp": 0, "pfr": 0, "agg": 0, "pas": 0, "sd": 0, "ff": 0, "fc": 0}
        return d

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            facing = {}
            for st, s, a, amt in hist:
                if st > 0:
                    if a == "raise":
                        facing[st] = True
                    elif facing.get(st) and s != self.seat:
                        if a == "fold":
                            self.S(s)["ff"] += 1
                        elif a == "call":
                            self.S(s)["fc"] += 1
                if s == self.seat:
                    continue
                seen.add(s)
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        self.S(s)["agg"] += 1
                    elif a in ("call", "check"):
                        self.S(s)["pas"] += 1
            for s in seen:
                d = self.S(s)
                d["h"] += 1
                if s in vp:
                    d["vp"] += 1
                if s in pr:
                    d["pfr"] += 1
        except Exception:
            pass

    def pfr(self, s):
        d = self.st.get(s)
        if not d:
            return 0.2
        return (d["pfr"] + 0.2 * 5) / (d["h"] + 5)

    def vpip(self, s):
        d = self.st.get(s)
        if not d:
            return 0.35
        return (d["vp"] + 0.35 * 5) / (d["h"] + 5)

    def foldf(self, s):
        d = self.st.get(s)
        if not d:
            return 0.45
        return (d["ff"] + 0.45 * 4) / (d["ff"] + d["fc"] + 4)

    def aggf(self, s):
        d = self.st.get(s)
        if not d:
            return 0.35
        return (d["agg"] + 0.35 * 4) / (d["agg"] + d["pas"] + 4)

    # ---------- helpers ----------
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
        if act in ("raise", "bet"):
            if "raise" not in legal and "bet" not in legal:
                return {"action": "call"} if "call" in legal else {"action": "check"}
            amt = int(a["amount"])
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            amt = max(lo, min(hi, amt))
            # if the raise would leave tiny stack behind, just go all-in
            if hi - amt < 0.15 * amt:
                amt = hi
            return {"action": "raise" if "raise" in legal else "bet", "amount": amt}
        if act == "fold":
            if "check" in legal:
                return {"action": "check"}
            return a
        if act == "check":
            if "check" in legal:
                return a
            return {"action": "fold"}
        if act == "call":
            if "call" in legal:
                return a
            return {"action": "check"}
        return a

    def raise_to(self, obs, amt):
        return {"action": "raise", "amount": int(amt)}

    def allin(self, obs):
        if obs["max_raise_to"] and ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return {"action": "call"}

    def _order(self, obs):
        alive = sorted(obs["alive"])
        n = len(alive)
        b = obs["button"]
        # seats after button in clockwise (increasing id) order
        after = [s for s in alive if s > b] + [s for s in alive if s <= b]
        return after  # sb first ... button last

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs)

    # ---------- ICM ----------
    def icm_req(self, obs, risk, win_amt, lim=5):
        """Required equity to put `risk` more chips in to win `win_amt` (others' chips),
        by ICM over alive players. Returns None if not computed."""
        alive = obs["alive"]
        if len(alive) > lim or len(alive) <= 2:
            return None
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        # current stacks behind (chips not yet committed are in stacks). Use total chips = stack + committed in pot
        base = {s: stacks[s] for s in alive}
        pot = obs["pot"]
        idx = {s: i for i, s in enumerate(alive)}
        # fold: we lose what we've put already; the pot goes to someone else (approx: biggest opponent bettor)
        # approximation: treat pot as going to the villain on fold
        vill = None
        mb = -1
        for s in obs["in_hand"]:
            if s != me and bets[s] + 0 >= mb:
                mb = bets[s]
                vill = s
        if vill is None:
            return None
        f = dict(base)
        f[vill] += pot
        w = dict(base)
        w[me] += pot + win_amt
        w[vill] -= win_amt
        l = dict(base)
        l[me] -= risk
        l[vill] += pot + risk
        def eq(d):
            st = [max(0.0, d[s]) for s in alive]
            return icm(st, self.points)[idx[me]]
        ef, ew, el = eq(f), eq(w), eq(l)
        if ew - el <= 1e-9:
            return None
        return (ef - el) / (ew - el)

    def call_range(self, s, risk_bb):
        """estimated fraction of hands seat s calls an all-in with, risking risk_bb."""
        base = CALL_K * (20.0 / max(risk_bb, 1.0)) ** 0.55
        vp = self.vpip(s)
        base *= (0.6 + vp * 1.15)
        return max(0.05, min(0.85, base))

    def shove_ev(self, obs, c, behind, my_total):
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        bb = obs["bb"] or 1
        pot = obs["pot"]
        my_bet = bets[me]
        ev_ = 0.0
        p_none = 1.0
        for s in behind:
            st = stacks[s] + bets[s]
            R = min(my_total, st)
            x = self.call_range(s, (R - bets[s]) / bb)
            eq = vsr(c, x)
            # more players still behind -> caller's range is a bit tighter / multiway risk
            final_pot = pot + (R - my_bet) + (R - bets[s])
            # excess beyond R that I shove is returned if caller is shorter
            ev_call = eq * final_pot - (R - my_bet)
            ev_ += p_none * x * ev_call
            p_none *= (1 - x)
        ev_ += p_none * pot
        return ev_

    # ---------- preflop ----------
    def preflop(self, obs):
        me = self.seat
        hole = obs["hole"]
        c1, c2 = CARD[hole[0]], CARD[hole[1]]
        c = CLS[c1][c2]
        pct = PCT[c]
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_total = stacks[me] + bets[me]
        in_hand = obs["in_hand"]
        opp_tot = [stacks[s] + bets[s] for s in in_hand if s != me]
        eff = min(my_total, max(opp_tot)) if opp_tot else my_total
        eff_bb = eff / bb
        hist = [h for h in obs["history"] if h[0] == 0]
        raises = [h for h in hist if h[2] == "raise"]
        nraise = len(raises)
        order = self._order(obs)
        n = len(order)
        if n == 2:
            pre_order = order[1:] + order[:1]  # button(sb) first? heads-up: button posts sb, acts first
            pre_order = [obs["sb_seat"], obs["bb_seat"]]
        else:
            i_bb = order.index(obs["bb_seat"]) if obs["bb_seat"] in order else 1
            pre_order = order[i_bb + 1:] + order[:i_bb + 1]
        if me in pre_order:
            mi = pre_order.index(me)
            behind = [s for s in pre_order[mi + 1:] if s in in_hand and stacks[s] > 0]
        else:
            behind = []
        nb = len(behind)
        nopp = len(in_hand) - 1
        self.pf_aggr = False

        if nraise == 0:
            # unopened (maybe limpers)
            limpers = len([h for h in hist if h[2] == "call" and h[1] != me])
            if eff_bb <= SHOVE_BB:
                if self.shove_ev(obs, c, behind, my_total) > SHOVE_MARGIN * bb:
                    self.pf_aggr = True
                    return self.allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                return {"action": "fold"}
            open_thr = {0: 0.6, 1: 0.5, 2: 0.42, 3: 0.32, 4: 0.26, 5: 0.21, 6: 0.17, 7: 0.15}.get(nb, 0.15)
            if n == 2:
                open_thr = HU_OPEN
            open_thr *= 0.8 ** limpers
            if behind and limpers == 0 and max(self.vpip(s) for s in behind) < 0.25:
                open_thr = min(0.9, open_thr * STEAL_W)
            if to_call == 0:
                # BB option
                if pct <= 0.12 or (pct <= 0.25 and limpers <= 1 and self.rng.random() < 0.5):
                    self.pf_aggr = True
                    return self.raise_to(obs, bets[me] + pot * 1.0 + bb)
                return {"action": "check"}
            if pct <= open_thr:
                self.pf_aggr = True
                size = (2.5 if eff_bb > 30 else 2.2) * bb + limpers * bb
                return self.raise_to(obs, size)
            # limp/complete from SB with cheap price
            if obs["sb_seat"] == me and limpers == 0 and nb == 1 and pct <= 0.75 and eff_bb > 20:
                return {"action": "call"}
            if limpers >= 1 and pct <= 0.55 and to_call <= bb and eff_bb > 25:
                return {"action": "call"}
            return {"action": "fold"}

        # facing raise(s)
        last = raises[-1]
        raiser = last[1]
        raise_to_amt = last[3]
        rbb = raise_to_amt / bb
        rp = self.pfr(raiser)
        # raiser's range width
        if nraise == 1:
            x = max(0.06, min(0.6, rp * 1.1))
            if rbb > 4:
                x *= 0.8
            if raise_to_amt >= (stacks[raiser] + bets[raiser]) * 0.9:
                # all-in raise: shoves from short stacks are wider
                rbb_stack = (stacks[raiser] + bets[raiser]) / bb
                x = max(x, min(0.7, 0.12 * (12 / max(rbb_stack, 2)) ** 0.8 + rp * 0.5))
        elif nraise == 2:
            x = max(0.04, min(0.25, rp * 0.45))
        else:
            x = max(0.025, min(0.12, rp * 0.25))
        if n == 2:
            x = max(x, HU_RX / nraise)
        elif n == 3:
            x = max(x, 0.6 * HU_RX / nraise)
        eq = vsr(c, x)
        # multiway adjustment: other callers already in
        li = max(i for i, h in enumerate(hist) if h[2] == "raise")
        callers = len(set(h[1] for h in hist[li + 1:] if h[2] == "call" and h[1] != me))
        if callers:
            eq *= 0.88 ** callers
        call_amt = min(to_call, stacks[me])
        pot_after = pot + call_amt
        po = call_amt / pot_after if pot_after > 0 else 0
        all_in_call = call_amt >= stacks[me] * 0.9 or eff_bb <= 13 or (bets[me] + call_amt) >= my_total * 0.45

        if all_in_call:
            # decide shove/call vs fold by equity
            req = po
            ir = None
            try:
                win_amt = min(stacks[raiser] + bets[raiser], my_total) - min(bets[raiser], my_total)
                ir = self.icm_req(obs, call_amt, 0)
            except Exception:
                ir = None
            if ir is not None:
                req = max(po, min(ir, po + 0.15))
            # we can shove over a raise: if raiser has more behind, shoving gives fold equity
            can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"])
            if eq >= req + 0.02:
                if can_raise and nraise == 1 and stacks[me] < 1.5 * (raise_to_amt + pot):
                    self.pf_aggr = True
                    return self.allin(obs)
                if can_raise and eq > 0.6:
                    self.pf_aggr = True
                    return self.allin(obs)
                return {"action": "call"}
            # resteal shove with decent hands vs a wide raiser when we cover enough fold equity
            if can_raise and nraise == 1 and eff_bb <= 18 and x >= 0.3 and pct <= 0.2 and callers == 0:
                self.pf_aggr = True
                return self.allin(obs)
            return {"action": "fold"}

        # deep: 3-bet / call / fold
        top = pct <= max(0.035, x * 0.25)
        if top or (eq >= 0.6 and nraise <= 2):
            self.pf_aggr = True
            if nraise >= 2 and eq >= 0.62:
                return self.allin(obs) if eff_bb < 40 else self.raise_to(obs, raise_to_amt * 2.4)
            return self.raise_to(obs, raise_to_amt * 3 + callers * raise_to_amt)
        implied = 0.04 if eff_bb > 40 else 0.0
        if eq >= po + CALL_MARGIN - implied and pct <= CALL_PCT:
            return {"action": "call"}
        return {"action": "fold"}

    # ---------- postflop ----------
    def weights_for(self, s, obs):
        """per-class weight array for opponent s from preflop action."""
        hist = obs["history"]
        raised = any(h[0] == 0 and h[1] == s and h[2] == "raise" for h in hist)
        if raised:
            x = max(0.08, min(0.6, self.pfr(s) * 1.2))
        else:
            vp = self.vpip(s)
            x = max(0.2, min(0.9, vp * 1.1))
            if s == obs["bb_seat"]:
                x = 1.0
        w = np.where(PCT_NP <= x, 1.0, 0.12)
        return w

    def equity(self, obs, opps):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        known = set(hole + board)
        R = np.array([c for c in range(36) if c not in known], dtype=np.int64)
        m = len(R)
        k = len(opps)
        nb = 5 - len(board)
        need = nb + 2 * k
        bank = BANK[m]
        NS = 170 if k <= 1 else (130 if k == 2 else 96)
        s0 = int(self.nrng.integers(0, bank.shape[0] - NS))
        smp = R[bank[s0:s0 + NS, :need]]
        bd = np.tile(np.array(board, dtype=np.int64), (NS, 1))
        full = np.concatenate([bd, smp[:, :nb]], axis=1) if nb else bd
        hv = ev.value_np(np.concatenate([np.tile(np.array(hole, dtype=np.int64), (NS, 1)), full], axis=1))
        w = np.ones(NS)
        best = np.zeros(NS, dtype=np.int64)
        hist = obs["history"]
        street = obs["street_index"]
        for j, s in enumerate(opps):
            oc = smp[:, nb + 2 * j: nb + 2 * j + 2]
            ov = ev.value_np(np.concatenate([oc, full], axis=1))
            best = np.maximum(best, ov)
            wc = self.weights_for(s, obs)[CLS_NP[oc[:, 0], oc[:, 1]]]
            # postflop aggression: weight by current strength percentile
            agg_now = [h for h in hist if h[0] == street and h[1] == s and h[2] == "raise"]
            agg_prev = [h for h in hist if 0 < h[0] < street and h[1] == s and h[2] == "raise"]
            called_prev = [h for h in hist if 0 < h[0] < street and h[1] == s and h[2] == "call"]
            f = 1.0
            if agg_now:
                amt = agg_now[-1][3]
                potb = max(1, obs["pot"] - amt)
                f = 0.5 if amt < 0.6 * potb else 0.38
                if len(agg_now) > 1:
                    f = 0.25
            elif agg_prev:
                f = 0.65
            elif called_prev:
                f = 0.8
            if f < 1.0:
                af = self.aggf(s)
                f = min(1.0, f * (0.75 + af))
                cur = ev.value_np(np.concatenate([oc, bd], axis=1))
                rk = np.argsort(np.argsort(cur)) / NS
                wc = wc * np.where(rk >= 1.0 - f, 1.0, 0.1)
            w = w * wc
        win = np.where(hv > best, 1.0, np.where(hv == best, 0.5, 0.0))
        sw = w.sum()
        if sw <= 0:
            return float(win.mean())
        return float((win * w).sum() / sw)

    def postflop(self, obs):
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        bb = obs["bb"] or 1
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        # simulate up to 3 opponents, prefer those with chips/aggression
        sim = opps[:3] if len(opps) <= 3 else sorted(opps, key=lambda s: -bets[s])[:3]
        eq = self.equity(obs, sim)
        if len(opps) > 3:
            eq = eq ** (1.0 + 0.25 * (len(opps) - 3))
        street = obs["street_index"]
        my_stack = stacks[me]
        can_raise = ("raise" in obs["legal"] or "bet" in obs["legal"]) and obs["max_raise_to"] > 0
        nop = len(opps)
        spr = my_stack / max(1, pot)
        if to_call == 0:
            if not can_raise:
                return {"action": "check"}
            ff = min(self.foldf(s) for s in opps)
            vthr = VAL_HU if nop == 1 else VAL_MW
            if ff < 0.25 and nop == 1:
                vthr -= 0.03
            if eq >= vthr:
                frac = 0.75 if eq >= 0.8 else 0.6
                if spr < 1.3:
                    return self.allin(obs)
                return self.raise_to(obs, bets[me] + max(bb, pot * frac))
            # c-bet / bluff
            if self.pf_aggr and nop == 1 and street == 1 and eq >= 0.3 and self.rng.random() < 0.6:
                return self.raise_to(obs, bets[me] + max(bb, pot * 0.4))
            if nop == 1 and street >= 2 and eq < 0.3 and self.rng.random() < 0.12:
                return self.raise_to(obs, bets[me] + max(bb, pot * 0.55))
            # exploit opponents shown to fold a lot to bets
            if nop == 1 and ff >= 0.55 and self.rng.random() < (ff - 0.45) * BLUFF_K:
                return self.raise_to(obs, bets[me] + max(bb, pot * 0.5))
            return {"action": "check"}
        call_amt = min(to_call, my_stack)
        po = call_amt / (pot + call_amt)
        # raise for value
        if can_raise and (eq >= 0.82 or (eq >= 0.72 and nop == 1)):
            cur = max(bets)
            tgt = cur * 2.8 + (pot - sum(bets)) * 0.3
            if spr < 2.0 or tgt > my_stack * 0.5:
                return self.allin(obs)
            return self.raise_to(obs, tgt)
        margin = 0.0
        if call_amt >= my_stack * 0.9:
            ir = None
            try:
                ir = self.icm_req(obs, call_amt, 0, 4)
            except Exception:
                ir = None
            if ir is not None:
                margin = max(0.0, min(0.15, ir - po))
        if street < 3 and spr > 2:
            margin += POST_MARGIN
        if eq >= po + margin:
            return {"action": "call"}
        return {"action": "fold"}
