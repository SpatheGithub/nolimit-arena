import json
import os
import random

import numpy as np

from . import he

_HERE = os.path.dirname(os.path.abspath(__file__))
_D = json.load(open(os.path.join(_HERE, "pre.json")))
_CLS = {tuple(c): i for i, c in enumerate(_D["classes"])}
_PCT = _D["pct"]
_EQR = _D["eqr"]
_RANGES = _D["ranges"]
_EQ1 = _D["eq1"]

P = dict(open_scale=1.3, push_scale=1.0, push_bb=16.0, pre_margin=0.02, three_eq=0.6,
         flat_p=0.32, vthr1=0.58, vthr2=0.45, vthr3=0.37, cbet=0.55, stab=0.3,
         rthr1=0.8, post_margin=0.1, w_out=0.2, agg_out=0.15, icm4=0.04, icm5=0.01, def_p=0.32, big_v=1.1, cheap=0.3, deep_tight=0.6, deep_bb=40.0, man_pfr=1.0, man_tight=0.6, cb_adj=0.5, obs_w=1.0, icm_exact=1.0, icm_post=1.0)
_pp = os.path.join(_HERE, "params.json")
if os.path.exists(_pp):
    P.update(json.load(open(_pp)))


def _cls_idx(c1, c2):
    a, b = c1 >> 2, c2 >> 2
    if a < b:
        a, b = b, a
    s = 1 if (a != b and (c1 & 3) == (c2 & 3)) else 0
    return _CLS[(a, b, s)]


# percentile of every two-card combo (36 x 36)
PCT36 = np.ones((36, 36))
for _x in range(36):
    for _y in range(36):
        if _x != _y:
            PCT36[_x, _y] = _PCT[_cls_idx(_x, _y)]


def eq_vs_range(ci, w):
    """preflop equity of class ci vs top-w range (heads-up)"""
    rs = _RANGES
    if w <= rs[0]:
        return _EQR[ci][0]
    if w >= rs[-1]:
        return _EQR[ci][-1]
    for k in range(len(rs) - 1):
        if rs[k] <= w <= rs[k + 1]:
            t = (w - rs[k]) / (rs[k + 1] - rs[k])
            return _EQR[ci][k] * (1 - t) + _EQR[ci][k + 1] * t
    return _EQR[ci][-1]


def push_pct(eff_bb, n_behind):
    n = max(1, n_behind)
    a = 0.6 * (10.0 / max(eff_bb, 1.0)) ** 0.75
    return min(1.0, P["push_scale"] * a / n ** 0.9)


def icm_me(st, i, pay):
    """Malmuth-Harville equity of player i (index into st, all > 0) for top-4 payouts."""
    T = float(sum(st))
    n = len(st)
    si = st[i]
    if n == 1:
        return pay[0]
    E = si / T * pay[0]
    if n == 2:
        return E + (1 - si / T) * pay[1]
    for a in range(n):
        if a == i:
            continue
        pa = st[a] / T
        Ta = T - st[a]
        E += pa * si / Ta * pay[1]
        if n == 2:
            continue
        for b in range(n):
            if b == i or b == a:
                continue
            pb = pa * st[b] / Ta
            Tb = Ta - st[b]
            E += pb * si / Tb * pay[2]
            if n <= 3 or len(pay) < 4 or not pay[3]:
                continue
            for c in range(n):
                if c == i or c == a or c == b:
                    continue
                pc = pb * st[c] / Tb
                E += pc * si / (Tb - st[c]) * pay[3]
    return E


def icm_after(stacks, me, pay):
    """my points given post-hand stacks (dict seat->chips)"""
    alive = [s for s in stacks if stacks[s] > 0]
    if stacks.get(me, 0) <= 0:
        place = len(alive) + 1
        return pay[place - 1] if place - 1 < len(pay) else 0.0
    st = [stacks[s] for s in alive]
    return icm_me(st, alive.index(me), pay)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nrng = np.random.default_rng(config["seed"])
        self.nseats = config.get("seats", 8)
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        # opponent stats per seat
        self.hands = [0] * 8
        self.vpip = [0] * 8
        self.pfr = [0] * 8
        self.agg = [0] * 8
        self.pas = [0] * 8
        # warm up numpy paths (first calls are slow)
        try:
            fake = {"history": [[0, 1, "raise", 60], [1, 1, "raise", 100]], "street_index": 1}
            for b in ([0, 5, 9], [0, 5, 9, 13], [0, 5, 9, 13, 20]):
                self._equity(fake, [30, 34], b, [1, 2])
        except Exception:
            pass

    # ------------------------------------------------------------------ utils
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for h in hist:
                st, s, a = h[0], h[1], h[2]
                if s is None or not (0 <= s < 8):
                    continue
                if st == 0:
                    if a in ("fold", "call", "raise", "check"):
                        seen.add(s)
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        self.agg[s] += 1
                    elif a in ("call", "check"):
                        self.pas[s] += 1
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass

    def pfr_rate(self, s):
        n = self.hands[s]
        return (self.pfr[s] + 0.2 * 6) / (n + 6)

    def raise_w(self, s, prior):
        n = self.hands[s]
        ow = min(0.95, max(0.03, self.pfr[s] / max(1, n) * 1.15))
        lam = n / (n + 12.0)
        return (1 - lam) * prior + lam * ow

    def vpip_rate(self, s):
        n = self.hands[s]
        return (self.vpip[s] + 0.3 * 6) / (n + 6)

    def act(self, obs):
        try:
            a = self._act(obs)
        except Exception:
            a = None
        if a is None:
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}
        return a

    def _raise_to(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if "raise" not in obs["legal"] and "bet" not in obs["legal"]:
            if obs["to_call"] > 0:
                return {"action": "call"}
            return {"action": "check"}
        me = obs["seat"]
        total = obs["stacks"][me] + obs["bets"][me]
        amt = int(amt)
        if amt >= 0.6 * total:
            amt = hi
        amt = max(lo, min(hi, amt))
        if amt >= hi:
            return {"action": "allin"}
        return {"action": "raise", "amount": amt}

    def _call(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "call"}

    def _fold(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "fold"}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [he.CID[c] for c in obs["hole"]]
        board = [he.CID[c] for c in obs["board"]]
        if obs["street_index"] == 0 or not board:
            return self._preflop(obs, hole)
        return self._postflop(obs, hole, board)

    # --------------------------------------------------------------- preflop
    def _preflop(self, obs, hole):
        me = obs["seat"]
        bb = max(obs["bb"], 1)
        stacks, bets = obs["stacks"], obs["bets"]
        total = stacks[me] + bets[me]
        opps = [s for s in obs["in_hand"] if s != me]
        if not opps:
            return self._call(obs)
        opp_tot = max(stacks[o] + bets[o] for o in opps)
        eff = min(total, opp_tot)
        eff_bb = eff / bb
        to_call = obs["to_call"]
        pot = obs["pot"]
        ci = _cls_idx(hole[0], hole[1])
        p = _PCT[ci]
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        nr = len(raises)
        # players to act after me
        alive = obs["alive"]
        n = self.nseats
        order = []
        bbs = obs["bb_seat"]
        for k in range(1, n + 1):
            s = (bbs + k) % n
            if s in alive:
                order.append(s)
        in_hand = set(obs["in_hand"])
        acted = set(h[1] for h in hist if h[0] == 0 and h[2] in ("fold", "call", "raise", "check"))
        if me in order:
            idx = order.index(me)
            behind = [s for s in order[idx + 1:] if s in in_hand and stacks[s] > 0]
        else:
            behind = []
        if nr == 0:
            behind_all = len(behind)
        else:
            behind_all = len([s for s in in_hand if s != me and stacks[s] > 0])
        nb = len(behind)
        limpers = len([h for h in hist if h[0] == 0 and h[2] == "call"])

        if nr == 0:
            # unopened (maybe limped)
            if eff_bb <= P["push_bb"]:
                pp = push_pct(eff_bb, max(nb, 1)) * (0.75 if limpers else 1.0)
                if p <= pp:
                    return {"action": "allin"} if "raise" in obs["legal"] else self._call(obs)
                if to_call == 0:
                    return {"action": "check"}
                # SB completing cheap vs BB only
                if nb == 1 and to_call <= bb / 2 and p <= 0.55 and eff_bb > 6:
                    return self._call(obs)
                return self._fold(obs)
            open_tab = {0: 0.5, 1: 0.45, 2: 0.36, 3: 0.3, 4: 0.25, 5: 0.21, 6: 0.18, 7: 0.15}
            op = open_tab.get(nb, 0.15) * P["open_scale"]
            if limpers:
                op *= 0.7
            if eff_bb > P["deep_bb"]:
                op *= P["deep_tight"]
            mx = max([self.pfr_rate(s) for s in behind if self.hands[s] >= 10] or [0.0])
            if mx > P["man_pfr"]:
                op *= P["man_tight"]
            if p <= op:
                size = (2.5 if eff_bb > 25 else 2.2) * bb + limpers * bb
                if to_call == 0 and bets[me] > 0:  # BB option
                    size = max(size, 3 * bb + limpers * bb)
                if eff_bb <= 20 and p <= op * 0.5:
                    return {"action": "allin"}
                return self._raise_to(obs, size)
            if to_call == 0:
                return {"action": "check"}
            if nb == 1 and to_call <= bb / 2 and p <= 0.6:
                return self._call(obs)
            if limpers and to_call <= bb / 2 and p <= 0.45:
                return self._call(obs)
            return self._fold(obs)

        # facing raise(s)
        last = raises[-1]
        rs = last[1]
        raiser_tot = stacks[rs] + bets[rs]
        raiser_allin = stacks[rs] == 0
        if nr == 1:
            w = 0.25
            # open shove / short-stack raise: widen
            if raiser_allin or raiser_tot <= 15 * bb:
                n_after = len(order) - order.index(rs) - 1 if rs in order else 3
                w = max(w, push_pct(raiser_tot / bb, max(1, n_after)) * 1.1)
            if P["obs_w"]:
                w = max(self.raise_w(rs, w), w * 0.6 if (raiser_allin or raiser_tot <= 15 * bb) else 0.0)
            else:
                w = 0.5 * w + 0.5 * min(0.9, self.pfr_rate(rs) * 1.3)
        elif nr == 2:
            w = 0.1
            if raiser_allin:
                w = 0.14
            if P["obs_w"]:
                w = min(0.6, max(0.04, self.raise_w(rs, 0.25) * 0.45))
            else:
                w = 0.6 * w + 0.4 * min(0.6, self.pfr_rate(rs) * 0.6)
        else:
            w = 0.05
        w = max(0.04, min(1.0, w))
        eq = eq_vs_range(ci, w)
        # multiway adjustment: other callers already in
        callers = len([s for s in in_hand if s != me and s != rs and bets[s] > 0 and stacks[s] >= 0]) - 0
        n_others_in = len([h for h in hist if h[0] == 0 and h[2] == "call" and h[1] != me])
        eq_adj = eq * (0.85 ** max(0, n_others_in))
        need = to_call / max(1, pot + to_call)
        committed = (to_call >= 0.35 * total) or (eff_bb <= 16) or raiser_allin
        if committed:
            margin = P["pre_margin"] + self._icm_margin(obs)
            if P["icm_exact"]:
                ne = self._icm_need(obs, rs)
                if ne is not None:
                    margin = P["pre_margin"] + max(0.0, ne - need)
            if eq_adj >= need + margin:
                return {"action": "allin"} if ("raise" in obs["legal"] and not raiser_allin) else {"action": "call"}
            # super strong anyway
            if p <= 0.02:
                return {"action": "allin"} if "raise" in obs["legal"] else {"action": "call"}
            return self._fold(obs)
        cur = bets[rs]
        if eq >= P["three_eq"] or p <= 0.015 or (nr == 1 and p <= 0.05):
            size = 3 * cur + (pot - cur - bets[me]) * 0.5
            if nr >= 2:
                size = 2.4 * cur
            return self._raise_to(obs, size)
        implied = 0.08 if eff_bb > 40 else 0.03
        fp = P["flat_p"] if need > P["cheap"] else max(P["flat_p"], P["def_p"])
        if eff_bb > P["deep_bb"]:
            fp *= P["deep_tight"]
        if p <= fp and eq_adj >= need - implied and to_call <= 0.2 * total:
            return self._call(obs)
        return self._fold(obs)

    def _icm_need(self, obs, opp):
        stacks = obs["stacks"]
        me = obs["seat"]
        alive = [s for s in obs["alive"] if stacks[s] > 0 or s in obs["in_hand"]]
        if len(alive) <= 2:
            return None
        pay = list(self.points[:4]) + [0] * 4
        pot = obs["pot"]
        to_call = obs["to_call"]
        put = min(to_call, stacks[me])
        excess = to_call - put
        base = {s: stacks[s] for s in alive}
        f = dict(base)
        f[opp] = f[opp] + pot
        w = dict(base)
        w[me] = w[me] + pot - excess
        w[opp] = w[opp] + excess
        l = dict(base)
        l[me] = l[me] - put
        l[opp] = l[opp] + pot + put
        ef = icm_after(f, me, pay)
        ew = icm_after(w, me, pay)
        el = icm_after(l, me, pay)
        if ew - el <= 1e-9:
            return None
        return (ef - el) / (ew - el)

    def _icm_margin(self, obs):
        alive = [s for s in obs["alive"]]
        k = len(alive)
        if k <= 2:
            return 0.0
        if k <= 4:
            return P["icm4"]
        return P["icm5"]

    # -------------------------------------------------------------- postflop
    def _equity(self, obs, hole, board, opps, S=240):
        known = hole + board
        ks = set(known)
        deck = np.array([c for c in range(36) if c not in ks], dtype=np.int64)
        nd = len(deck)
        nopp = min(len(opps), 3)
        nb = 5 - len(board)
        need = nb + 2 * nopp
        pool = he.POOL[nd]
        st = self.rng.randrange(0, pool.shape[0] - S)
        cards = deck[pool[st:st + S, :need]]
        bd = np.array(board, dtype=np.int64)
        fullb = np.concatenate([np.broadcast_to(bd, (S, len(board))), cards[:, :nb]], axis=1) if nb else np.broadcast_to(bd, (S, 5))
        # which suits can make flushes
        cnt = [0, 0, 0, 0]
        for c in board:
            cnt[c & 3] += 1
        need_s = 5 - nb
        suits = [s for s in range(4) if cnt[s] + nb >= 3]
        myc = np.concatenate([np.broadcast_to(np.array(hole, dtype=np.int64), (S, 2)), fullb], axis=1)
        my = he.eval_mat(myc, suits)
        best = np.zeros(S, dtype=np.int64)
        wt = np.ones(S)
        cur_suits = [s for s in range(4) if cnt[s] >= 3]
        hist = obs["history"]
        street = obs["street_index"]
        for i in range(nopp):
            o = opps[i]
            oh = cards[:, nb + 2 * i: nb + 2 * i + 2]
            ov = he.eval_mat(np.concatenate([oh, fullb], axis=1), suits)
            best = np.maximum(best, ov)
            # preflop range weight
            pf_r = sum(1 for h in hist if h[0] == 0 and h[1] == o and h[2] == "raise")
            pf_c = sum(1 for h in hist if h[0] == 0 and h[1] == o and h[2] == "call")
            if pf_r:
                if P["obs_w"]:
                    wr = self.raise_w(o, 0.3)
                else:
                    wr = 0.5 * 0.3 + 0.5 * min(0.9, self.pfr_rate(o) * 1.3)
                wr = wr if pf_r == 1 else wr * 0.5
            elif pf_c:
                wr = 0.55
            else:
                wr = 1.0
            if wr < 0.99:
                pc = PCT36[oh[:, 0], oh[:, 1]]
                wt = wt * np.where(pc <= wr, 1.0, P["w_out"])
            # postflop aggression
            aggr_now = sum(1 for h in hist if h[0] == street and h[1] == o and h[2] == "raise")
            aggr_prev = sum(1 for h in hist if 0 < h[0] < street and h[1] == o and h[2] == "raise")
            if aggr_now or aggr_prev:
                q = 0.5
                if aggr_now >= 2:
                    q = 0.25
                elif aggr_now == 1:
                    q = 0.45 if aggr_prev == 0 else 0.35
                else:
                    q = 0.65
                arate = (self.agg[o] + 1) / (self.agg[o] + self.pas[o] + 3)
                q = min(0.9, q * (0.7 + arate))
                curc = np.concatenate([oh, np.broadcast_to(bd, (S, len(board)))], axis=1)
                cv = he.eval_mat(curc, cur_suits)
                thr = np.quantile(cv, 1 - q)
                wt = wt * np.where(cv >= thr, 1.0, P["agg_out"])
        win = (my > best) + 0.5 * (my == best)
        e = float((win * wt).sum() / max(1e-9, wt.sum()))
        # account for additional opponents beyond 3
        if len(opps) > 3:
            e = e ** (len(opps) / 3.0)
        return e

    def _postflop(self, obs, hole, board):
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        opps = [s for s in obs["in_hand"] if s != me]
        if not opps:
            return self._call(obs)
        to_call = obs["to_call"]
        pot = obs["pot"]
        total = stacks[me] + bets[me]
        # opponents with chips left matter for betting
        e = self._equity(obs, hole, board, opps, 200 if len(opps) < 3 else 160)
        nopp = len(opps)
        street = obs["street_index"]
        hist = obs["history"]
        pf_raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        i_aggr = bool(pf_raises) and pf_raises[-1][1] == me
        live_opps = [s for s in opps if stacks[s] > 0]
        r = self.rng.random()
        maxbet = max(bets[s] for s in obs["in_hand"])
        spr = stacks[me] / max(1, pot)
        if to_call <= 0:
            vthr = {1: P["vthr1"], 2: P["vthr2"], 3: P["vthr3"]}.get(nopp, P["vthr3"] - 0.05)
            if not live_opps:
                return {"action": "check"}
            if e >= vthr:
                frac = 0.75 if e >= vthr + 0.15 else 0.6
                if e >= P["big_v"]:
                    frac = 1.0
                if spr < 1.2:
                    return {"action": "allin"}
                return self._raise_to(obs, max(obs["min_raise_to"], frac * pot))
            o0 = opps[0]
            ar = (self.agg[o0] + 1) / (self.agg[o0] + self.pas[o0] + 3)
            cb = P["cbet"] * (1 - P["cb_adj"] * ar)
            if nopp == 1 and i_aggr and street == 1 and e >= 0.3 and r < cb:
                return self._raise_to(obs, max(obs["min_raise_to"], 0.5 * pot))
            if nopp == 1 and street >= 2 and e >= 0.35 and r < P["stab"]:
                return self._raise_to(obs, max(obs["min_raise_to"], 0.55 * pot))
            return {"action": "check"}
        need = to_call / max(1, pot + to_call)
        rthr = {1: P["rthr1"], 2: P["rthr1"] - 0.15, 3: P["rthr1"] - 0.25}.get(nopp, P["rthr1"] - 0.3)
        if e >= rthr and live_opps and ("raise" in obs["legal"]):
            if spr < 2.0 or to_call >= 0.3 * total:
                return {"action": "allin"}
            return self._raise_to(obs, 2.8 * maxbet + (pot - maxbet) * 0.3)
        margin = P["post_margin"] if street < 3 else P["post_margin"] - 0.01
        if P["icm_post"] and to_call >= 0.4 * stacks[me]:
            bettor = None
            for h in reversed(hist):
                if h[0] == street and h[2] == "raise" and h[1] != me:
                    bettor = h[1]
                    break
            if bettor is not None:
                ne = self._icm_need(obs, bettor)
                if ne is not None:
                    margin = max(margin, P["post_margin"] * 0.5 + (ne - need))
        if e >= need + margin:
            return {"action": "call"}
        return self._fold(obs)
