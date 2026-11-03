import os
import random

import numpy as np

from .evalnp import CID, POW5, RANKTAB, eval_cards

_D = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre.npz"))
HU = _D["hu"]
MW = _D["mw"]
COMBOS = _D["combos"]
_TOT = COMBOS.sum()
EQ_RAND = (HU * COMBOS[None, :]).sum(1) / _TOT
_ORDER = np.argsort(-EQ_RAND)
_cum = np.cumsum(COMBOS[_ORDER]) / _TOT
PCT_END = np.zeros(81)
PCT_END[_ORDER] = _cum
PCT_START = PCT_END - COMBOS / _TOT
PCT_MID = (PCT_END + PCT_START) / 2
PGRID = np.linspace(0.02, 1.0, 50)
EQR = np.zeros((81, 50))
for _j, _p in enumerate(PGRID):
    _w = COMBOS * np.clip((_p - PCT_START) / (PCT_END - PCT_START), 0, 1)
    EQR[:, _j] = HU @ _w / _w.sum()
EQR_L = EQR.tolist()
PCT_L = PCT_MID.tolist()
MW_L = MW.tolist()

# class of each 2-card combo
CLS2 = np.zeros((36, 36), dtype=np.int64)
for _a in range(36):
    for _b in range(36):
        _r1, _r2 = _a >> 2, _b >> 2
        _hi, _lo = max(_r1, _r2), min(_r1, _r2)
        if _hi == _lo:
            CLS2[_a, _b] = _hi * 9 + _hi
        elif (_a & 3) == (_b & 3):
            CLS2[_a, _b] = _hi * 9 + _lo
        else:
            CLS2[_a, _b] = _lo * 9 + _hi
PCT_ARR = PCT_MID

_prng = np.random.default_rng(987654)
NPERM = 3000
PERMS = {}
for _n in (29, 30, 31):
    PERMS[_n] = np.argsort(_prng.random((NPERM, _n)), axis=1)[:, :10].astype(np.int64)

NSIM = 160


def cls_of(c1, c2):
    return int(CLS2[c1, c2])


def eq_range(cls, p):
    """HU equity of class vs top-p range."""
    if p <= 0.02:
        return EQR_L[cls][0]
    if p >= 1.0:
        return EQR_L[cls][49]
    x = (p - 0.02) / 0.02
    i = int(x)
    f = x - i
    row = EQR_L[cls]
    return row[i] * (1 - f) + row[min(i + 1, 49)] * f


class Opp:
    __slots__ = ("hands", "vpip", "pfr", "agg", "pas", "shove", "fold_to_bet", "faced_bet")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.agg = 0
        self.pas = 0
        self.shove = 0
        self.fold_to_bet = 0
        self.faced_bet = 0

    def vpip_rate(self):
        return (self.vpip + 0.3 * 6) / (self.hands + 6)

    def pfr_rate(self):
        return (self.pfr + 0.18 * 6) / (self.hands + 6)

    def fold_rate(self):
        return (self.fold_to_bet + 0.45 * 4) / (self.faced_bet + 4)

    def shove_rate(self):
        return (self.shove + 0.03 * 8) / (self.hands + 8)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        self.opp = {}
        self.cur_hand = -1
        self.start_stacks = None
        self.pf_aggr = False

    # ------------------------------------------------------------ helpers
    def o(self, s):
        x = self.opp.get(s)
        if x is None:
            x = self.opp[s] = Opp()
        return x

    def legalize(self, obs, kind, amount=0):
        legal = obs["legal"]
        if kind == "raise":
            rk = "raise" if "raise" in legal else ("bet" if "bet" in legal else None)
            if rk is None:
                kind = "call"
            else:
                lo, hi = obs["min_raise_to"], obs["max_raise_to"]
                amt = int(max(lo, min(hi, amount)))
                if amt >= hi * 0.9 or amt >= hi:
                    amt = hi
                return {"action": rk, "amount": amt}
        if kind == "call":
            if "call" in legal:
                return {"action": "call"}
            if "check" in legal:
                return {"action": "check"}
            return {"action": "fold"}
        if kind == "check":
            if "check" in legal:
                return {"action": "check"}
            return {"action": "fold"}
        if "check" in legal:
            return {"action": "check"}
        return {"action": "fold"}

    def act(self, obs):
        try:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs.get("n_discard", 0)]}
            if obs["hand_id"] != self.cur_hand:
                self.cur_hand = obs["hand_id"]
                self.pf_aggr = False
            if obs["street_index"] == 0:
                r = self.preflop(obs)
            else:
                r = self.postflop(obs)
            if r.get("action") in ("raise", "bet") and obs["street_index"] == 0:
                self.pf_aggr = True
            return r
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    # ------------------------------------------------------------ stage / risk
    def risk_lambda(self, obs):
        # ~75% of the ICM bubble factor minus one (equal stacks, 100/45/20/8)
        n = len(obs["alive"])
        return {2: 0.0, 3: 0.17, 4: 0.21, 5: 0.24, 6: 0.18, 7: 0.13}.get(n, 0.11)

    # ------------------------------------------------------------ preflop
    def preflop(self, obs):
        me = obs["seat"]
        hole = [CID[c] for c in obs["hole"]]
        cls = cls_of(hole[0], hole[1])
        pct = PCT_L[cls]
        bb = obs["bb"]
        stacks, bets = obs["stacks"], obs["bets"]
        my_total = stacks[me] + bets[me]
        pot = obs["pot"]
        to_call = obs["to_call"]
        hist = obs["history"]
        acted = set()
        raises = 0
        raisers = []
        limpers = 0
        for st, s, a, amt in hist:
            if st != 0:
                continue
            if a in ("call", "raise", "check", "fold"):
                acted.add(s)
            if a == "raise":
                raises += 1
                raisers.append((s, amt))
            elif a == "call" and raises == 0:
                limpers += 1
        in_hand = obs["in_hand"]
        behind = [s for s in in_hand if s != me and s not in acted and stacks[s] > 0]
        opps_live = [s for s in in_hand if s != me]
        # effective stack vs biggest other stack in hand
        max_other = max([stacks[s] + bets[s] for s in opps_live] or [0])
        eff = min(my_total, max_other)
        eff_bb = eff / bb
        lam = self.risk_lambda(obs)
        n_behind = len(behind)

        if raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= 14 or (eff_bb <= 20 and limpers > 0):
                ev = self.shove_ev(obs, cls, behind, my_total, pot, lam)
                if ev > 0.0:
                    return self.legalize(obs, "raise", obs["max_raise_to"])
                if to_call == 0:
                    return self.legalize(obs, "check")
                # SB complete small for cheap in late push/fold? fold
                return self.legalize(obs, "fold")
            th = {7: 0.13, 6: 0.15, 5: 0.18, 4: 0.22, 3: 0.27, 2: 0.38, 1: 0.52}.get(n_behind, 0.12)
            n_alive = len(obs["alive"])
            if n_alive == 2:
                th = 0.80
            elif n_alive == 3:
                th = max(th, 0.48 if n_behind == 2 else 0.62)
            # widen vs tight blinds: average fold tendency of players behind
            if behind and not limpers:
                tight = sum(1.0 for s in behind if self.o(s).vpip_rate() < 0.2 and self.o(s).hands >= 10)
                th *= 1.0 + 0.25 * tight / len(behind)
            if limpers:
                th = min(th * 0.8, 0.22)
            # steal when the players behind fold a lot
            if not limpers and behind and n_behind <= 4:
                p_steal = 1.0
                for s in behind:
                    cont = self.o(s).vpip_rate() * 0.6
                    if s == obs.get("bb_seat"):
                        cont *= 1.3
                    p_steal *= 1.0 - min(0.8, max(0.03, cont))
                if p_steal >= 0.75:
                    th = max(th, 0.9)
                elif p_steal >= 0.66:
                    th = max(th, 0.6)
            if pct <= th:
                size = (2.5 + limpers) * bb if n_behind > 1 else 3 * bb
                if size >= 0.4 * my_total:
                    return self.legalize(obs, "raise", obs["max_raise_to"])
                return self.legalize(obs, "raise", size)
            if to_call == 0:
                return self.legalize(obs, "check")
            # limp-complete from SB with decent hands when cheap
            if n_behind == 1 and to_call <= 0.5 * bb and pct <= 0.7 and eff_bb > 20:
                return self.legalize(obs, "call")
            return self.legalize(obs, "fold")

        # facing raise(s)
        last_raiser, last_amt = raisers[-1]
        ro = self.o(last_raiser)
        raiser_total = stacks[last_raiser] + bets[last_raiser]
        is_shove = stacks[last_raiser] == 0
        if is_shove:
            p = max(0.15, 1.4 * ro.shove_rate()) + 0.4 * max(0.0, ro.vpip_rate() - 0.3)
            sb_bb = raiser_total / bb
            if sb_bb < 12:
                p += 0.12
            if sb_bb < 6:
                p += 0.15
            na = len(obs["alive"])
            if na == 2:
                p += 0.2
            elif na == 3:
                p += 0.1
            if raises == 1 and limpers == 0 and last_raiser == obs.get("sb_seat") and na > 2:
                p += 0.1
        else:
            p = ro.pfr_rate() * 1.1
            if raises == 1:
                alive = sorted(obs["alive"])
                bbs = obs.get("bb_seat", alive[-1])
                order = [x for x in alive if x > bbs] + [x for x in alive if x <= bbs]
                if last_raiser in order:
                    n_after = len(order) - 1 - order.index(last_raiser)
                    p *= {1: 2.0, 2: 1.5, 3: 1.15, 4: 0.95}.get(n_after, 0.8)
            if raises >= 2:
                p *= 0.35 ** (raises - 1)
                p = max(p, 0.04)
        p = min(max(p, 0.03), 0.9)
        eq = eq_range(cls, p)
        n_other = max(1, len(opps_live))
        if n_other >= 2:
            # discount for extra players in pot (callers / behind)
            extra = len([s for s in opps_live if s != last_raiser and (s in behind or bets[s] > 0)])
            eq = eq * (0.88 ** min(extra, 3))
        call_cost = min(to_call, stacks[me])
        commit = call_cost >= 0.45 * my_total or is_shove or (stacks[me] - call_cost) < 3 * bb
        final_pot = pot + call_cost
        if commit or eff_bb <= 18:
            # all-in decision: shove or call off (chip EV vs the raiser)
            matched = min(my_total, raiser_total)
            fin = pot - bets[last_raiser] - bets[me] + 2 * matched
            ev = eq * fin - (matched - bets[me])
            ev -= lam * min(1.0, matched / my_total) * (1 - eq) * (matched - bets[me])
            can_shove = "raise" in obs["legal"] and not is_shove and stacks[me] > to_call
            if can_shove and raises == 1:
                # fold equity: raiser continues with top c of its range p
                cf = min(0.85, max(0.35, 0.55 * (ro.vpip_rate() / 0.3) ** 0.5))
                if len(obs["alive"]) == 2:
                    cf = min(0.85, cf + 0.15)
                c = max(0.03, p * cf)
                pf = 1.0 - cf
                for s2 in behind:
                    pf *= 1.0 - min(0.5, self.call_prob(s2, (min(my_total, stacks[s2] + bets[s2]) - bets[s2]) / bb, 0, len(obs["alive"])) * 0.7)
                eq_c = eq_range(cls, c)
                if n_other >= 2:
                    eq_c *= 0.95
                ev_c = eq_c * fin - (matched - bets[me]) - lam * min(1.0, matched / my_total) * (1 - eq_c) * (matched - bets[me])
                ev_shove = pf * pot + (1 - pf) * ev_c
                if ev_shove > 0.15 * pot and ev_shove >= ev:
                    return self.legalize(obs, "raise", obs["max_raise_to"])
            if ev > 0:
                if can_shove:
                    return self.legalize(obs, "raise", obs["max_raise_to"])
                return self.legalize(obs, "call")
            return self.legalize(obs, "fold")
        # deep: 3-bet / call / fold
        if eq >= 0.60 and raises <= 2:
            size = 3.0 * last_amt if n_behind > 0 else 2.7 * last_amt
            if size >= 0.35 * my_total:
                return self.legalize(obs, "raise", obs["max_raise_to"])
            return self.legalize(obs, "raise", size)
        pot_odds = call_cost / (final_pot)
        implied = 0.06 if (call_cost < 0.1 * my_total and eff_bb > 30) else 0.0
        if eq >= pot_odds + 0.04 - implied and eq >= 0.38:
            return self.legalize(obs, "call")
        return self.legalize(obs, "fold")

    def call_prob(self, s, call_amt_bb, n_after, n_alive=8):
        o = self.o(s)
        if n_alive <= 3:
            if call_amt_bb <= 3:
                p = 0.65
            elif call_amt_bb <= 6:
                p = 0.5
            elif call_amt_bb <= 10:
                p = 0.4
            elif call_amt_bb <= 16:
                p = 0.32
            elif call_amt_bb <= 30:
                p = 0.22
            else:
                p = 0.15
            if n_alive == 3:
                p *= 0.8
        elif call_amt_bb <= 3:
            p = 0.42
        elif call_amt_bb <= 6:
            p = 0.32
        elif call_amt_bb <= 10:
            p = 0.24
        elif call_amt_bb <= 16:
            p = 0.17
        elif call_amt_bb <= 30:
            p = 0.12
        else:
            p = 0.08
        v = o.vpip_rate()
        p *= min(2.0, max(0.5, v / 0.3))
        return min(0.9, max(0.03, p))

    def shove_ev(self, obs, cls, behind, my_total, pot, lam):
        stacks, bets, me, bb = obs["stacks"], obs["bets"], obs["seat"], obs["bb"]
        p_nf = 1.0
        ev = 0.0
        for s in behind:
            tot = stacks[s] + bets[s]
            matched = min(my_total, tot)
            call_amt = matched - bets[s]
            c = self.call_prob(s, call_amt / bb, 0, len(obs["alive"]))
            eq = eq_range(cls, c)
            fin = pot - bets[me] - bets[s] + 2 * matched
            risk = matched - bets[me]
            e = eq * fin - risk - lam * min(1.0, matched / max(1, my_total)) * (1 - eq) * risk
            ev += p_nf * c * e
            p_nf *= (1 - c)
        ev += p_nf * pot
        return ev

    # ------------------------------------------------------------ postflop
    def equity(self, obs, hole, board):
        me = obs["seat"]
        opps = [s for s in obs["in_hand"] if s != me]
        k = len(opps)
        known = set(hole) | set(board)
        deck = np.array([c for c in range(36) if c not in known], dtype=np.int64)
        nd = len(deck)
        nb = len(board)
        need = 5 - nb
        ksim = min(k, 3)
        # pick opponents to simulate: the most aggressive ones first
        hist = obs["history"]
        aggr = {}
        calls = {}
        pfr = {}
        aggr_cur = {}
        for st, s, a, amt in hist:
            if a == "raise":
                if st >= 1:
                    aggr[s] = aggr.get(s, 0) + 1
                    if st == obs["street_index"]:
                        aggr_cur[s] = aggr_cur.get(s, 0) + 1
                else:
                    pfr[s] = pfr.get(s, 0) + 1
            elif a == "call" and st >= 1:
                calls[s] = calls.get(s, 0) + 1
        opps.sort(key=lambda s: -(aggr.get(s, 0) * 2 + calls.get(s, 0)))
        sim = opps[:ksim]
        N = 320 if ksim == 1 else (240 if ksim == 2 else 192)
        off = self.rng.randrange(NPERM - N)
        idx = PERMS[nd][off:off + N, :need + 2 * ksim]
        cards = deck[idx]
        bfix = np.array(board, dtype=np.int64)
        runb = np.concatenate([np.broadcast_to(bfix, (N, nb)), cards[:, :need]], axis=1)
        hands = [np.broadcast_to(np.array(hole, dtype=np.int64), (N, 2))]
        for i in range(ksim):
            hands.append(cards[:, need + 2 * i:need + 2 * i + 2])
        allrows = np.concatenate([np.concatenate([h, runb], axis=1) for h in hands], axis=0)
        vals = eval_cards(allrows).reshape(ksim + 1, N)
        hv = vals[0]
        ov = vals[1:]
        best = ov.max(axis=0)
        nt = (ov == hv[None, :]).sum(axis=0)
        share = np.where(hv > best, 1.0, np.where(hv == best, 1.0 / (1 + nt), 0.0))
        # weights
        w = np.ones(N)
        bcode = int(POW5[bfix].sum())
        bcat = int(RANKTAB[bcode]) >> 20
        cur = np.concatenate([np.concatenate([hands[i + 1], np.broadcast_to(bfix, (N, nb))], axis=1)
                              for i in range(ksim)], axis=0)
        cvals = eval_cards(cur).reshape(ksim, N)
        ccat = (cvals >> 20) - bcat
        street = obs["street_index"]
        for i, s in enumerate(sim):
            o = self.o(s)
            h = hands[i + 1]
            pc = PCT_ARR[CLS2[h[:, 0], h[:, 1]]]
            if pfr.get(s, 0) >= 2:
                rp = 0.10
            elif pfr.get(s, 0) == 1:
                rp = max(0.08, min(0.6, o.pfr_rate() * 1.2))
            else:
                rp = max(0.2, min(0.85, o.vpip_rate() * 1.3))
            wi = np.where(pc <= rp, 1.0, 0.15)
            a = aggr.get(s, 0)
            ac = aggr_cur.get(s, 0)
            ap = a - ac
            c = calls.get(s, 0)
            rel = ccat[i]
            af = (o.agg + 1.0) / (o.agg + o.pas + 4.0)
            if ac > 0:
                top = (0.55, 0.55, 0.45, 0.35)[street]
                if af < 0.15:
                    top *= 0.6
                elif af < 0.25:
                    top *= 0.8
                elif af > 0.5:
                    top *= 1.4
                top *= 0.6 ** (min(ac, 3) - 1)
                tc = obs["to_call"]
                if tc > 0 and tc >= 0.8 * (obs["pot"] - tc):
                    top *= 0.8
                shoved = obs["stacks"][s] == 0
                if shoved and tc > 0:
                    top *= 0.75
                top = min(0.9, max(0.08, top))
                rank = cvals[i].argsort().argsort() / (N - 1.0)
                low = (0.3, 0.3, 0.2, 0.1)[street]
                if af > 0.5:
                    low *= 2
                if shoved and tc > 0:
                    low *= 0.6
                wi = wi * np.where(rank >= 1.0 - top, 1.0, low)
            if ap > 0:
                f = np.where(rel <= 0, 0.35, np.where(rel == 1, 0.65, 1.0))
                if af > 0.5:
                    f = np.sqrt(f)
                wi = wi * f ** min(ap, 2)
            if c > 0:
                f = np.where(rel <= 0, 0.45, np.where(rel == 1, 0.8, 1.0))
                wi = wi * f ** min(c, 2)
            w = w * wi
        eq = float((w * share).sum() / w.sum())
        if k > ksim:
            eq = eq ** (k / ksim)
        return eq, k

    def postflop(self, obs):
        me = obs["seat"]
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        eq, k = self.equity(obs, hole, board)
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks = obs["stacks"]
        my_stack = stacks[me]
        street = obs["street_index"]
        lam = self.risk_lambda(obs)
        r = self.rng.random()
        if to_call == 0:
            vb = {1: 0.58, 2: 0.50, 3: 0.45}.get(k, 0.42)
            if k == 1:
                vill = [x for x in obs["in_hand"] if x != me]
                if vill:
                    fr = self.o(vill[0]).fold_rate()
                    if fr < 0.3:
                        vb -= 0.04
                    elif fr > 0.6:
                        vb += 0.03
            if eq >= vb:
                frac = 0.6 if eq < 0.8 else (0.8 if eq < 0.9 else 1.0)
                amt = frac * pot
                if amt >= 0.6 * my_stack:
                    return self.legalize(obs, "raise", obs["max_raise_to"])
                return self.legalize(obs, "raise", max(amt, obs["min_raise_to"]))
            if k == 1:
                bluff_p = 0.0
                if street == 1 and self.pf_aggr:
                    bluff_p = 0.45 if eq > 0.3 else 0.3
                elif street == 2 and eq > 0.3:
                    bluff_p = 0.25
                elif street == 3 and eq < 0.2:
                    bluff_p = 0.15
                vill = [x for x in obs["in_hand"] if x != me]
                if vill:
                    fr = self.o(vill[0]).fold_rate()
                    bluff_p *= min(1.8, max(0.3, fr / 0.45))
                if r < bluff_p:
                    amt = 0.5 * pot
                    if amt >= 0.6 * my_stack:
                        return self.legalize(obs, "check")
                    return self.legalize(obs, "raise", max(amt, obs["min_raise_to"]))
            return self.legalize(obs, "check")
        call_cost = min(to_call, my_stack)
        pot_odds = call_cost / (pot + call_cost)
        commit = call_cost >= 0.5 * my_stack
        rth = {1: 0.78, 2: 0.7, 3: 0.65}.get(k, 0.6)
        if eq >= rth and "raise" in obs["legal"]:
            bet_now = obs["bets"]
            cur = max(bet_now)
            amt = cur * 3 + (pot - sum(bet_now)) * 0.5
            if amt >= 0.5 * (my_stack + obs["bets"][me]):
                return self.legalize(obs, "raise", obs["max_raise_to"])
            return self.legalize(obs, "raise", amt)
        margin = 0.02 + (lam * 0.3 * min(1.0, call_cost / max(1, my_stack + obs["bets"][me])) if commit else 0.0) + (0.03 if street == 3 else 0.0)
        if street < 3 and not commit and my_stack - call_cost > pot:
            margin += 0.03
        if eq >= pot_odds + margin:
            return self.legalize(obs, "call")
        return self.legalize(obs, "fold")

    # ------------------------------------------------------------ observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for st, s, a, amt in hist:
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
                        self.o(s).agg += 1
                    elif a in ("call", "check"):
                        self.o(s).pas += 1
            bet_on = {}
            done = set()
            for st, s, a, amt in hist:
                if st < 1:
                    continue
                if a == "raise":
                    if bet_on.get(st) is not None and s != self.seat and (st, s) not in done:
                        done.add((st, s))
                        self.o(s).faced_bet += 1
                    bet_on[st] = s
                elif a in ("call", "fold") and bet_on.get(st) is not None and s != self.seat and (st, s) not in done:
                    done.add((st, s))
                    o2 = self.o(s)
                    o2.faced_bet += 1
                    if a == "fold":
                        o2.fold_to_bet += 1
            stacks = event.get("stacks") or []
            for s in seen:
                o = self.o(s)
                o.hands += 1
                if s in vp:
                    o.vpip += 1
                if s in pr:
                    o.pfr += 1
            # shoves preflop: raise-to equal to the whole starting stack
            ss = self.start_stacks
            for st, s, a, amt in hist:
                if st == 0 and a == "raise" and s != self.seat:
                    if ss is not None and s < len(ss) and ss[s] > 0 and amt >= 0.97 * ss[s]:
                        self.o(s).shove += 1
                    elif ss is None:
                        bbv = 0
                        for st2, s2, a2, amt2 in hist:
                            if a2 == "bb":
                                bbv = amt2
                                break
                        if bbv and amt >= 8 * bbv:
                            self.o(s).shove += 1
            if stacks:
                self.start_stacks = list(stacks)
        except Exception:
            pass
