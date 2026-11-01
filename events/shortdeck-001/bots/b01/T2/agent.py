import os
import json
import time
import random

from .ev import KEY, START, NF, FS, SB, CID

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre.json")))
CLASSES = [tuple(c) for c in _D["classes"]]
MULTI = _D["multi"]
HU = _D["hu"]
NCL = len(CLASSES)
NCOMBO = [6 if t == 0 else (4 if t == 1 else 12) for (h, l, t) in CLASSES]
_score = [MULTI[i][0] + MULTI[i][2] for i in range(NCL)]
_order = sorted(range(NCL), key=lambda i: -_score[i])
PCT = [0.0] * NCL
_cum = 0
for _i in _order:
    _cum += NCOMBO[_i]
    PCT[_i] = _cum / 630.0

CLS2 = [[-1] * 36 for _ in range(36)]
for _a in range(36):
    for _b in range(36):
        if _a == _b:
            continue
        ra, rb = _a >> 2, _b >> 2
        hi, lo = max(ra, rb), min(ra, rb)
        t = 0 if ra == rb else (1 if (_a & 3) == (_b & 3) else 2)
        CLS2[_a][_b] = CLASSES.index((hi, lo, t))

GRID = [0.02 * (k + 1) for k in range(50)]
EQR = []
for _i in range(NCL):
    row = []
    for g in GRID:
        num = den = 0.0
        for _j in range(NCL):
            if PCT[_j] <= g + 1e-9 or _j == _order[0]:
                num += HU[_i][_j] * NCOMBO[_j]
                den += NCOMBO[_j]
        row.append(num / den)
    EQR.append(row)


OPEN_EP, OPEN_HJ, OPEN_CO, OPEN_BTN, OPEN_SB = 0.11, 0.14, 0.18, 0.26, 0.32
SB_COMPLETE = 0.0
OPEN_HU = 0.62
BLUFF_MIN_FOLD = 0.38
ADJ0, ADJ1, ADJR = 0.06, 0.11, 0.03
COND_ON = True
RESTEAL = False
ALLIN_TRACK = True
CALLC = (0.17, 0.22, 0.30, 0.45)
ICM_PREM = {8: 0.05, 7: 0.06, 6: 0.07, 5: 0.09, 4: 0.085, 3: 0.07}


def eq_vs_range(ci, r):
    k = int(r / 0.02 + 0.5) - 1
    if k < 0:
        k = 0
    if k > 49:
        k = 49
    return EQR[ci][k]


RB = [0.12, 0.2, 0.3, 0.45, 0.65, 1.0]
RANGE_COMBOS = []
for g in RB:
    lst = []
    for _a in range(36):
        for _b in range(_a + 1, 36):
            if PCT[CLS2[_a][_b]] <= g + 1e-9:
                lst.append((_a, _b, (1 << _a) | (1 << _b)))
    RANGE_COMBOS.append(lst)


def rbucket(r):
    for k, g in enumerate(RB):
        if r <= g + 1e-9:
            return k
    return len(RB) - 1


def val(s, cards):
    if s & 0x8888:
        F = SB[s & 0x8888]
        m = 0
        for c in cards:
            m |= F[c]
        return FS[m]
    return NF[s >> 16]


class Opp:
    __slots__ = ("hands", "vpip", "pfr", "agg", "pas", "fold", "allin", "sd", "faced", "called")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.agg = 0
        self.pas = 0
        self.fold = 0
        self.allin = 0
        self.sd = 0
        self.faced = 0
        self.called = 0


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nseats = config.get("seats", 8)
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        self.opp = [Opp() for _ in range(max(self.nseats, 10))]
        self.start_stack = config.get("starting_stack", 2000)
        self.last_stacks = None

    # ---------- opponent model ----------
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
                if a in ("ante", "sb", "bb", "return", "discard"):
                    seen.add(s)
                    continue
                seen.add(s)
                o = self.opp[s]
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                else:
                    if a == "raise":
                        o.agg += 1
                    elif a == "call":
                        o.pas += 1
                    elif a == "fold":
                        o.fold += 1
            for s in seen:
                self.opp[s].hands += 1
            for s in vp:
                self.opp[s].vpip += 1
            for s in pr:
                self.opp[s].pfr += 1
        except Exception:
            pass
        try:
            self.track_allins(event)
        except Exception:
            pass

    def track_allins(self, event):
        hist = event.get("history") or []
        n = len(self.opp)
        start = self.last_stacks
        if start is None:
            start = [self.start_stack] * n
        prev = [0] * n
        sb = [0] * n
        cur = 0
        pending = None
        responded = set()
        for h in hist:
            st, s, a, amt = h[0], h[1], h[2], h[3]
            if st != cur:
                for j in range(n):
                    prev[j] += sb[j]
                sb = [0] * n
                cur = st
                pending = None
            if a in ("sb", "bb"):
                sb[s] = amt
            elif a == "raise":
                if pending is not None and s != pending and s not in responded:
                    self.opp[s].faced += 1
                    self.opp[s].called += 1
                    responded.add(s)
                sb[s] = amt
                if prev[s] + amt >= start[s] > 0:
                    pending = s
                    responded = set()
            elif a == "call":
                mx = max(sb)
                sb[s] = min(mx, start[s] - prev[s])
                if pending is not None and s != pending and s not in responded:
                    self.opp[s].faced += 1
                    self.opp[s].called += 1
                    responded.add(s)
            elif a == "fold":
                if pending is not None and s != pending and s not in responded:
                    self.opp[s].faced += 1
                    responded.add(s)
        st2 = event.get("stacks")
        if st2:
            self.last_stacks = list(st2) + [0] * max(0, n - len(st2))

    def pfr_of(self, s):
        o = self.opp[s]
        return (o.pfr + 1.5) / (o.hands + 10.0)

    def vpip_of(self, s):
        o = self.opp[s]
        return (o.vpip + 3.0) / (o.hands + 10.0)

    def win_pot(self, obs, call_amt):
        me = self.seat
        bets = obs["bets"]
        cap = bets[me] + call_amt
        tot = obs["pot"] - sum(bets) + cap
        for j in range(len(bets)):
            if j != me:
                b = bets[j]
                tot += b if b < cap else cap
        return max(tot, call_amt + 1)

    def icm_prem(self, obs, opp):
        n = len(obs["alive"])
        if n <= 2 or opp is None:
            return 0.0
        st, bt = obs["stacks"], obs["bets"]
        me = self.seat
        my = st[me] + bt[me]
        their = st[opp] + bt[opp]
        base = ICM_PREM.get(n, 0.05)
        if their >= my * 0.95:
            return base
        return 0.022

    def foldrate_of(self, s):
        o = self.opp[s]
        return (o.fold + 2.0) / (o.fold + o.pas + 0.5 * o.agg + 5.0)

    def aggr_of(self, s):
        o = self.opp[s]
        return (o.agg + 2.0) / (o.agg + o.pas + o.fold + 6.0)

    # ---------- helpers ----------
    def raise_to(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0 or ("raise" not in obs["legal"] and "bet" not in obs["legal"]):
            return self.call_or_check(obs)
        amt = int(amt)
        if amt >= hi * 0.85:
            amt = hi
        if amt < lo:
            amt = lo
        if amt > hi:
            amt = hi
        return {"action": "raise", "amount": amt}

    def call_or_check(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "fold"}

    def fold(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def allin(self, obs):
        if obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self.call_or_check(obs)

    # ---------- main ----------
    def act(self, obs):
        self.t0 = time.thread_time()
        try:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
            if obs["street_index"] == 0:
                return self.preflop(obs)
            return self.postflop(obs)
        except Exception:
            return self.fold(obs)

    def preflop(self, obs):
        me = self.seat
        hole = [CID[c] for c in obs["hole"]]
        ci = CLS2[hole[0]][hole[1]]
        pct = PCT[ci]
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_total = stacks[me] + bets[me]
        opps = [s for s in in_hand if s != me]
        eff = min(my_total, max([stacks[s] + bets[s] for s in opps] or [0]))
        eff_bb = eff / bb
        my_bb = my_total / bb
        n_alive = len(obs["alive"])

        hist = [h for h in obs["history"] if h[0] == 0]
        raises = [h for h in hist if h[2] == "raise"]
        nraise = len(raises)
        limpers = len([h for h in hist if h[2] == "call"]) if nraise == 0 else 0

        # preflop order: from seat after bb, clockwise
        alive = sorted(obs["alive"])
        bbs = obs["bb_seat"]
        order = [s for s in alive if s > bbs] + [s for s in alive if s <= bbs]
        acted = set(h[1] for h in hist if h[2] in ("call", "raise", "fold", "check"))
        pos = order.index(me) if me in order else 0
        behind = [s for s in order[pos + 1:] if s in in_hand and stacks[s] > 0 and s not in acted]
        if me != bbs and bbs in in_hand and bbs not in behind and nraise == 0 and bbs not in acted and bbs != me:
            pass
        n_behind = len(behind)
        is_bb = (me == bbs)
        is_sb = (me == obs["sb_seat"])

        # table-size adjustment: fewer players -> wider
        short_table = max(0, 8 - n_alive)

        if nraise == 0:
            # unopened or limped
            if to_call == 0 and is_bb:
                # option
                if pct <= 0.10 + 0.02 * short_table:
                    if eff_bb <= 12:
                        return self.allin(obs)
                    return self.raise_to(obs, bets[me] + (3 + limpers) * bb)
                return {"action": "check"}
            # push/fold zone
            if eff_bb <= 13 or my_bb <= 13:
                if self.shove_ev(obs, ci, behind, eff, pot) > 0:
                    return self.allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                return self.fold(obs)
            open_th = {0: 0.0, 1: OPEN_SB, 2: OPEN_BTN, 3: OPEN_CO, 4: OPEN_HJ}.get(n_behind, OPEN_EP)
            open_th += 0.012 * short_table
            if n_alive == 2:
                open_th = OPEN_HU
            # steal more vs tight players behind
            if behind and not limpers:
                tight = sum(1 for s in behind if self.opp[s].hands >= 12 and self.vpip_of(s) < 0.2)
                if tight == len(behind):
                    open_th = min(0.6, open_th * 1.5)
            if limpers:
                open_th *= 0.75
            if pct <= open_th:
                size = (2.2 if eff_bb < 25 else 2.5) * bb + limpers * bb
                if is_sb:
                    size = 3 * bb
                return self.raise_to(obs, size)
            # limp behind / complete with cheap speculative hands
            if limpers and pct <= open_th * 1.4 and to_call <= bb and eff_bb > 30:
                return self.call_or_check(obs)
            if is_sb and to_call <= bb / 2 + 1 and pct <= SB_COMPLETE and eff_bb > 20:
                return self.call_or_check(obs)
            return self.fold(obs)

        # facing raise(s)
        last = raises[-1]
        raiser = last[1]
        cur = max(bets)
        raiser_total = stacks[raiser] + bets[raiser]
        raiser_allin = stacks[raiser] == 0
        # estimated raiser range
        base = self.pfr_of(raiser)
        if nraise == 1:
            r = min(0.6, max(0.08, base * 1.3))
            if raiser_allin:
                rbb = raiser_total / bb
                rpos = order.index(raiser) if raiser in order else 0
                rbehind = len(order) - 1 - rpos
                rm = max(0.08, min(0.6, 0.55 - 0.07 * rbehind))
                rm *= 1.25 if rbb < 6 else (1.0 if rbb < 12 else (0.7 if rbb < 20 else 0.45))
                if self.opp[raiser].hands >= 15:
                    rm = 0.5 * rm + 0.5 * min(0.7, base * 1.5)
                r = min(0.75, max(0.05, rm))
        elif nraise == 2:
            r = min(0.3, max(0.04, base * 0.5))
            if raiser_allin:
                r = max(r, 0.08)
        else:
            r = min(0.15, max(0.03, base * 0.3))
        # multiple callers tighten
        li = max(i for i, h in enumerate(hist) if h[2] == "raise")
        call_seats = [h[1] for h in hist[li + 1:] if h[2] == "call" and h[1] in in_hand and h[1] != me]
        callers = len(call_seats)
        eq = eq_vs_range(ci, r)
        if callers:
            for cs in call_seats:
                eq *= eq_vs_range(ci, min(r, 0.15 if raiser_allin else 0.3))
            eq = eq ** 0.85

        call_amt = min(to_call, stacks[me])
        commit = (bets[me] + call_amt) / max(1, my_total)
        # amount needed to see showdown if we call and get it in
        remaining_after = stacks[me] - call_amt
        big = raiser_allin or commit > 0.4 or remaining_after < 6 * bb
        po = call_amt / self.win_pot(obs, call_amt)
        margin = 0.01 + self.icm_prem(obs, raiser)
        if big:
            # all-in decision: compute stake if we shove/call all-in
            if raiser_allin or cur >= my_total * 0.9:
                if eq >= po + margin:
                    return self.allin(obs) if not raiser_allin else self.call_or_check(obs)
                return self.fold(obs)
            # we can shove over
            stake = my_total - bets[me]
            win_pot = pot + min(stake, raiser_total - bets[raiser]) + 0
            po2 = stake / (pot + stake + max(0, min(raiser_total, my_total) - cur))
            if eq >= po2 + margin or pct <= 0.04:
                return self.allin(obs)
            return self.fold(obs)
        # deep: 3bet / call / fold
        # re-steal shove at mid stacks over a single open
        if RESTEAL and nraise == 1 and callers == 0 and eff_bb <= 25 and not raiser_allin:
            r_call = max(0.03, r * 0.35)
            fold_p = (1.0 - r_call / max(r, r_call + 1e-9)) * (1.0 - 0.06 * n_behind)
            stake = stacks[me]
            their_call = max(0, min(raiser_total, my_total) - bets[raiser])
            eq_c = eq_vs_range(ci, r_call) - self.icm_prem(obs, raiser)
            ev_rs = fold_p * pot + (1 - fold_p) * (eq_c * (pot + their_call + stake) - stake)
            if ev_rs > 0.05 * pot:
                return self.allin(obs)
        three_th = 0.055 if nraise == 1 else 0.025
        if pct <= three_th or (nraise == 1 and pct <= r * 0.3):
            if eff_bb <= 30:
                return self.allin(obs)
            size = cur * (3.0 if n_behind == 0 else 3.5) + callers * (cur - bets[me])
            return self.raise_to(obs, size)
        # call when equity * implied factor beats price
        implied = 1.0 + min(0.08, 0.004 * (eff_bb - 20)) if eff_bb > 20 else 1.0
        need = po + (0.04 if not is_bb else 0.0)
        if eq * implied >= need + 0.08 and to_call <= 0.15 * my_total:
            return self.call_or_check(obs)
        if is_bb and eq >= po + 0.09 and to_call <= 3 * bb:
            return self.call_or_check(obs)
        return self.fold(obs)

    def shove_ev(self, obs, ci, behind, eff, pot):
        bb = obs["bb"]
        stacks, bets = obs["stacks"], obs["bets"]
        me = self.seat
        stake = stacks[me]
        p_all_fold = 1.0
        ev_called = 0.0
        for s in behind:
            their = stacks[s] + bets[s]
            risk = min(stake + bets[me], their) / bb
            # calling range by how much of their stack the call costs
            c = CALLC[0] if risk > 12 else (CALLC[1] if risk > 8 else (CALLC[2] if risk > 5 else CALLC[3]))
            c *= (0.7 + 0.6 * self.vpip_of(s) / 0.3) if self.opp[s].hands > 10 else 1.0
            o = self.opp[s]
            if ALLIN_TRACK and o.faced >= 2:
                w = o.faced / (o.faced + 5.0)
                c = (1 - w) * c + w * ((o.called + 0.3) / (o.faced + 1.0))
            if len(obs["alive"]) == 2:
                c *= 1.3
            if s == obs["bb_seat"] and risk <= 6:
                c = max(c, 0.45)
            c = min(0.8, max(0.06, c))
            eq = eq_vs_range(ci, c)
            amt = min(stake, their - bets[s] + bets[me]) if their > 0 else stake
            ev_c = (eq - self.icm_prem(obs, s)) * (pot + amt + amt) - amt
            ev_called += p_all_fold * c * ev_c
            p_all_fold *= (1 - c)
        ev = p_all_fold * pot + ev_called
        return ev

    def postflop(self, obs):
        me = self.seat
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        stacks, bets = obs["stacks"], obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        pot = obs["pot"]
        to_call = obs["to_call"]
        bb = max(1, obs["bb"])
        st = obs["street_index"]
        hist = obs["history"]

        # opponent ranges from preflop action
        pre = [h for h in hist if h[0] == 0]
        pre_raisers = [h[1] for h in pre if h[2] == "raise"]
        last_pre_raiser = pre_raisers[-1] if pre_raisers else None
        npre = len(pre_raisers)
        ranges = []
        for s in opps:
            if s in pre_raisers:
                r = 0.2 if npre == 1 else 0.12
                r = max(r, min(0.6, self.pfr_of(s) * 1.4))
            elif any(h[1] == s and h[2] == "call" for h in pre):
                r = 0.45 if npre else 0.65
                r = max(r, min(1.0, self.vpip_of(s) * 1.3))
            else:
                r = 1.0
            ranges.append(r)

        # current street aggression
        cur_hist = [h for h in hist if h[0] == st]
        conds = None
        if to_call > 0 and COND_ON:
            aggrs = set(h[1] for h in cur_hist if h[2] == "raise" and h[1] != me)
            if aggrs:
                # board pairs -> threshold category for "has a real hand"
                rc = {}
                for c in board:
                    rc[c >> 2] = rc.get(c >> 2, 0) + 1
                npair = sum(1 for v in rc.values() if v >= 2)
                thr = min(3, 1 + npair) << 20
                conds = []
                for s in opps:
                    if s in aggrs:
                        afs = self.aggr_of(s)
                        pb = min(0.8, max(0.12, 1.4 * afs - 0.2))
                        conds.append((thr, pb))
                    else:
                        conds.append(None)
        eq = self.equity(hole, board, ranges, conds)
        n_raises = len([h for h in cur_hist if h[2] == "raise"])
        my_stack = stacks[me]
        spr = my_stack / max(1, pot)
        rnd = self.rng.random()
        we_aggr = (last_pre_raiser == me)

        if to_call == 0:
            # betting decision
            vth = 0.62 if n_opp == 1 else (0.5 if n_opp == 2 else 0.42)
            if eq >= vth:
                frac = 0.75 if st < 3 else 0.7
                if eq >= 0.85:
                    frac += 0.15
                fro = sum(self.foldrate_of(s) for s in opps) / max(1, n_opp)
                if fro < 0.3:
                    frac += 0.2
                elif fro > 0.55:
                    frac -= 0.15
                if spr < 1.2:
                    return self.allin(obs)
                return self.raise_to(obs, pot * frac)
            if n_opp == 1 and eq >= 0.5 and rnd < 0.4:
                return self.raise_to(obs, pot * 0.5)
            # bluff / c-bet only vs opponents who fold enough
            fr = 1.0
            for s in opps:
                fr *= self.foldrate_of(s)
            if n_opp <= 2 and fr >= BLUFF_MIN_FOLD:
                if we_aggr and st == 1 and rnd < 0.7:
                    return self.raise_to(obs, pot * 0.45)
                if st < 3 and eq >= 0.3 and rnd < 0.3:
                    return self.raise_to(obs, pot * 0.55)
                if st == 3 and eq < 0.25 and rnd < 0.2 and n_opp == 1:
                    return self.raise_to(obs, pot * 0.6)
            return {"action": "check"}

        # facing a bet
        call_amt = min(to_call, my_stack)
        po = call_amt / self.win_pot(obs, call_amt)
        bettor = None
        for h in reversed(cur_hist):
            if h[2] == "raise":
                bettor = h[1]
                break
        af = self.aggr_of(bettor) if bettor is not None else 0.35
        # stronger ranges when bets are large / raised; loosen vs aggressive players
        wp = self.win_pot(obs, call_amt)
        betfrac = call_amt / max(1, wp - 2 * call_amt)
        if conds:
            adj = 0.02 + 0.05 * min(2.0, betfrac) + 0.05 * (n_raises - 1)
        else:
            adj = ADJ0 + ADJ1 * min(2.0, betfrac) + 0.08 * (n_raises - 1) + (ADJR if st == 3 else 0.0)
            adj -= 0.25 * (af - 0.35)
        adj = max(0.0, adj)
        eq_adj = eq - adj
        if eq >= 0.85 or (eq >= 0.78 and n_raises <= 1):
            if spr < 2 or n_raises >= 2:
                return self.allin(obs)
            return self.raise_to(obs, obs["bets"][bettor] * 3 if bettor is not None else pot)
        if (bets[me] + call_amt) > 0.45 * (my_stack + bets[me]) and bettor is not None:
            eq_adj -= self.icm_prem(obs, bettor)
        if eq_adj >= po:
            return self.call_or_check(obs)
        return self.fold(obs)

    def equity(self, hole, board, ranges, conds=None):
        rng = self.rng.random
        dead = 0
        for c in hole:
            dead |= 1 << c
        for c in board:
            dead |= 1 << c
        deck = [c for c in range(36) if not (dead >> c) & 1]
        nd = len(deck)
        need = 5 - len(board)
        nopp = len(ranges)
        sim = min(nopp, 3)
        # pick most-restrictive ranges first
        if conds is None:
            conds = [None] * nopp
        idx = sorted(range(nopp), key=lambda k: (conds[k] is None, ranges[k]))[:sim]
        lists = []
        cl = []
        for k in idx:
            L = [x for x in RANGE_COMBOS[rbucket(ranges[k])] if not (x[2] & dead)]
            if len(L) < 5:
                L = [x for x in RANGE_COMBOS[-1] if not (x[2] & dead)]
            lists.append(L)
            cl.append(conds[k])
        bs = START
        for c in board:
            bs += KEY[c]
        ms = bs + KEY[hole[0]] + KEY[hole[1]]
        mycards = hole + board
        wins = 0.0
        n = 0
        t_end = self.t0 + 0.00040
        clock = time.thread_time
        if need == 0:
            hv = val(ms, mycards)
            if sim == 1:
                L = lists[0]
                cd = cl[0]
                tot = 0.0
                wsum = 0.0
                for (a, b, m) in L:
                    v = val(bs + KEY[a] + KEY[b], board + [a, b])
                    w = 1.0 if (cd is None or v >= cd[0]) else cd[1]
                    wsum += w
                    tot += w if hv > v else (0.5 * w if hv == v else 0.0)
                return tot / max(1e-9, wsum)
        while True:
            for _ in range(4):
                used = dead
                if need == 2:
                    i = int(rng() * nd)
                    j = int(rng() * (nd - 1))
                    if j >= i:
                        j += 1
                    x, y = deck[i], deck[j]
                    used |= (1 << x) | (1 << y)
                    run = [x, y]
                    s_add = KEY[x] + KEY[y]
                elif need == 1:
                    x = deck[int(rng() * nd)]
                    used |= 1 << x
                    run = [x]
                    s_add = KEY[x]
                else:
                    run = []
                    s_add = 0
                fb = board + run
                hv = val(ms + s_add, mycards + run)
                best = -1
                ties = 0
                for li in range(sim):
                    L = lists[li]
                    cd = cl[li]
                    nl = len(L)
                    fo = None
                    for _t in range(12):
                        o = L[int(rng() * nl)]
                        if not (o[2] & used):
                            fo = o
                            if cd is None or rng() < cd[1]:
                                break
                            if val(bs + KEY[o[0]] + KEY[o[1]], board + [o[0], o[1]]) >= cd[0]:
                                break
                    if o[2] & used:
                        o = fo
                        if o is None:
                            for o in L:
                                if not (o[2] & used):
                                    break
                            if o[2] & used:
                                continue
                    used |= o[2]
                    v = val(bs + s_add + KEY[o[0]] + KEY[o[1]], fb + [o[0], o[1]])
                    if v > best:
                        best = v
                        ties = 1 if v == hv else 0
                    elif v == best and v == hv:
                        ties += 1
                if hv > best:
                    wins += 1.0
                elif hv == best:
                    wins += 1.0 / (1 + ties)
                n += 1
            if clock() > t_end or n >= 2000:
                break
        e = wins / n
        if nopp > sim:
            e = e ** (nopp / sim)
        return e
