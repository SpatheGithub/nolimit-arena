import os
import random
import time

import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
_D = np.load(os.path.join(_DIR, "data.npz"))
TAB = np.concatenate([_D["tab"], np.full(5 ** 9, -1, dtype=np.int32)])
SUITED = _D["suited"].astype(np.int32)
EQM = _D["eqm"]
PAIRC = _D["pairc"]
NCOMBO = _D["ncombo"]
CCLS = _D["ccls"].astype(np.int64)
CARDS = _D["cards"].astype(np.int64)
MW = _D["mw"]

RANKS = "6789TJQKA"
SUITS = "cdhs"
CID = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
P5 = np.array([5 ** (c >> 2) for c in range(36)], dtype=np.int64)
P5L = [5 ** (c >> 2) for c in range(36)]
RBIT = np.array([1 << (c >> 2) for c in range(36)], dtype=np.int64)
C1, C2 = CARDS[:, 0], CARDS[:, 1]
CMASK = (np.int64(1) << C1) | (np.int64(1) << C2)
CCODE = P5[C1] + P5[C2]
CSUITCNT = [((C1 & 3) == s).astype(np.int64) + ((C2 & 3) == s).astype(np.int64) for s in range(4)]
CSUITBITS = [np.where((C1 & 3) == s, RBIT[C1], 0) | np.where((C2 & 3) == s, RBIT[C2], 0) for s in range(4)]

# strength order of classes: equity vs random hand (HU)
EQR = (EQM * PAIRC).sum(1) / PAIRC.sum(1)
_ORDER = np.argsort(-EQR)
_cum = np.cumsum(NCOMBO[_ORDER]) / NCOMBO.sum()
CUM_HI = np.zeros(81)
CUM_LO = np.zeros(81)
CUM_HI[_ORDER] = _cum
CUM_LO[_ORDER] = _cum - NCOMBO[_ORDER] / NCOMBO.sum()
PCT = (CUM_HI + CUM_LO) / 2  # percentile (0 best)
XGRID = np.linspace(0.02, 1.0, 50)
INC = np.clip((XGRID[:, None] - CUM_LO[None, :]) / (CUM_HI - CUM_LO)[None, :], 0, 1)  # 50x81
_num = (EQM * PAIRC) @ INC.T
_den = PAIRC @ INC.T
EVT = _num / np.maximum(_den, 1e-9)  # 81x50: equity of class vs top-x range


def xi(x):
    i = int(round((min(max(x, 0.02), 1.0) - 0.02) / 0.02))
    return 0 if i < 0 else 49 if i > 49 else i


def cls_of(a, b):
    ra, rb = a >> 2, b >> 2
    hi, lo = (ra, rb) if ra >= rb else (rb, ra)
    if hi == lo:
        return hi
    k = hi * (hi - 1) // 2 + lo
    return 9 + k if (a & 3) == (b & 3) else 45 + k


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


# default fraction of hands that call an all-in of E big blinds
CALL_X = ([1.5, 3, 5, 8, 10, 15, 20, 30, 60], [0.95, 0.7, 0.5, 0.36, 0.3, 0.22, 0.17, 0.12, 0.07])
# default fraction of hands that shove at E big blinds (first in)
SHOVE_X = ([2, 5, 8, 10, 15, 20, 30, 60], [0.8, 0.6, 0.45, 0.38, 0.28, 0.2, 0.13, 0.08])


PF_BB = 14
OPEN_MULT = 1.0
ICM_M4 = 0.03
ICM_M6 = 0.015
BLUFF = 0.55
VALUE_HU = 0.58
NSUB = 100
FLOP_R = 31
CALL_NARROW = 0.0
RESTEAL = True
WIDEN = 0.3
THIN = False


def hand_value(cards):
    code = 0
    for c in cards:
        code += P5L[c]
    v = int(TAB[code])
    sc = [0, 0, 0, 0]
    for c in cards:
        sc[c & 3] += 1
    for s in range(4):
        if sc[s] >= 5:
            m = 0
            for c in cards:
                if c & 3 == s:
                    m |= 1 << (c >> 2)
            f = int(SUITED[m])
            if f > v:
                v = f
    return v


class Stats:
    __slots__ = ("hands", "vpip", "pfr", "fr_opp", "fr_fold", "pf_bets", "pf_acts", "fb_opp", "fb_fold",
                 "shoves", "big_opp", "big_call")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.fr_opp = 0
        self.fr_fold = 0
        self.pf_bets = 0
        self.pf_acts = 0
        self.fb_opp = 0
        self.fb_fold = 0
        self.shoves = 0
        self.big_opp = 0
        self.big_call = 0

    def vpip_rate(self):
        return (self.vpip + 0.35 * 6) / (self.hands + 6)

    def pfr_rate(self):
        return (self.pfr + 0.2 * 6) / (self.hands + 6)

    def fold_to_raise(self):
        return (self.fr_fold + 0.6 * 5) / (self.fr_opp + 5)

    def fold_to_bet(self):
        return (self.fb_fold + 0.45 * 5) / (self.fb_opp + 5)

    def agg(self):
        return (self.pf_bets + 0.35 * 5) / (self.pf_acts + 5)

    def big_call_rate(self, prior):
        return (self.big_call + prior * 4) / (self.big_opp + 4)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nseats = config.get("seats", 8)
        self.stats = [Stats() for _ in range(max(self.nseats, 10))]
        self.points = config.get("points", [100, 45, 20, 8, 0, 0, 0, 0])
        self.pf_aggr = False
        self.cur_hand = -1
        self.t0 = time.thread_time()
        self.nrng = np.random.default_rng(config["seed"] if isinstance(config.get("seed"), int) else 1)

    # ------------------------------------------------------------------ utils
    def order_from(self, start_after, seats):
        n = self.nseats
        return sorted(seats, key=lambda s: (s - start_after - 1) % n)

    def act(self, obs):
        self.t0 = time.thread_time()
        try:
            return self.decide(obs)
        except Exception:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def can_raise(self, obs):
        legal = obs["legal"]
        return ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0

    def a_fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def a_call(self, obs):
        if obs["to_call"] == 0:
            return {"action": "check"}
        return {"action": "call"}

    def a_raise(self, obs, amt):
        if not self.can_raise(obs):
            return self.a_call(obs)
        a = int(amt)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        my_bet = obs["bets"][obs["seat"]]
        my_stack = obs["stacks"][obs["seat"]]
        # if leaving little behind, just shove
        if (my_stack + my_bet) - a < 0.2 * (obs["pot"] + 2 * (a - my_bet)):
            a = hi
        return {"action": "raise", "amount": a}

    def a_allin(self, obs):
        if self.can_raise(obs):
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self.a_call(obs)

    # ------------------------------------------------------------ decision
    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["hand_id"] != self.cur_hand:
            self.cur_hand = obs["hand_id"]
            self.pf_aggr = False
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        if obs["street_index"] == 0 or not board:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    def tightness_icm(self, obs, risk_frac):
        """extra equity needed to risk risk_frac of our stack, from the points table"""
        alive = len(obs["alive"])
        if alive <= 2:
            return 0.0
        m = 0.0
        if alive <= 4:
            m = ICM_M4
        elif alive <= 6:
            m = ICM_M6
        return m * min(1.0, risk_frac)

    # ------------------------------------------------------------ preflop
    def preflop(self, obs, hole):
        me = obs["seat"]
        bb = max(obs["bb"], 1)
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        hist = obs["history"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        c = cls_of(hole[0], hole[1])
        pct = PCT[c]
        my_total = stacks[me] + bets[me]
        order = self.order_from(obs["bb_seat"], alive)
        if len(alive) == 2:
            order = [obs["sb_seat"], obs["bb_seat"]] if obs["sb_seat"] != obs["bb_seat"] else order
        myi = order.index(me) if me in order else 0
        acted = set()
        raises = []
        limpers = 0
        for h in hist:
            if h[0] != 0:
                continue
            a = h[2]
            if a in ("sb", "bb", "ante"):
                continue
            acted.add(h[1])
            if a == "raise":
                raises.append((h[1], h[3]))
            elif a == "call" and not raises:
                limpers += 1
        behind = [s for s in order[myi + 1:] if s in in_hand and s != me]
        # players yet to act after me (includes blinds who haven't acted voluntarily)
        others = [s for s in in_hand if s != me]
        eff_all = max([stacks[s] + bets[s] for s in others] or [0])
        eff = min(my_total, eff_all)
        eff_bb = eff / bb

        if not raises:
            # unopened (maybe limpers)
            if to_call == 0:
                # BB option facing limpers / SB complete
                if pct <= 0.12 + 0.04 * (len(alive) <= 4):
                    if eff_bb <= 12:
                        return self.a_allin(obs)
                    self.pf_aggr = True
                    return self.a_raise(obs, bets[me] + (3 + limpers) * bb)
                return {"action": "check"}
            n_behind = len(behind)
            # push/fold zone
            if eff_bb <= PF_BB:
                ev = self.shove_ev(obs, c, others, pot, my_total, bets[me], len(behind))
                if ev > 0:
                    return self.a_allin(obs)
                # with limpers and decent stack, fold
                return self.a_fold(obs)
            # open raise ranges by number of players behind
            base = {0: 0.6, 1: 0.55, 2: 0.42, 3: 0.32, 4: 0.25, 5: 0.2, 6: 0.17, 7: 0.15}.get(n_behind, 0.15) * OPEN_MULT
            # steal more vs tight blinds
            if n_behind <= 3:
                ftr = np.mean([self.stats[s].fold_to_raise() for s in behind]) if behind else 0.6
                base *= 0.75 + 0.6 * ftr
            if limpers:
                base *= 0.6
            if pct <= base:
                self.pf_aggr = True
                size = (2.3 if eff_bb > 30 else 2.1) * bb + limpers * bb
                if n_behind == 1 and obs["sb_seat"] == me:
                    size = 2.5 * bb
                return self.a_raise(obs, size)
            # SB complete with okay hand vs BB when cheap
            if n_behind == 1 and obs["sb_seat"] == me and pct <= 0.75 and to_call <= 0.5 * bb:
                return self.a_call(obs)
            return self.a_fold(obs)

        # facing raise(s)
        nr = len(raises)
        rseat, rto = raises[-1]
        st = self.stats[rseat]
        r_total = stacks[rseat] + bets[rseat]
        r_allin = stacks[rseat] == 0
        r_bb = r_total / bb
        # estimate raiser range
        n_after_r = len(order) - 1 - order.index(rseat) if rseat in order else 3
        pos_widen = 1.0 + 0.3 * max(0, 4 - n_after_r)
        if nr == 1:
            x = st.pfr_rate()
            if r_allin or rto >= 0.5 * r_total:
                dflt = min(0.85, interp(min(r_bb, my_total / bb), *SHOVE_X) * 0.8 * pos_widen)
                obs_sh = (st.shoves * 1.25 + dflt * 4) / (st.hands + 4)
                x = max(dflt, min(obs_sh, 0.9))
                if r_bb <= 12:
                    x = max(x, min(st.pfr_rate(), 0.9))
            else:
                x = min(0.75, x * (0.8 + 0.2 * pos_widen))
            x = min(max(x, 0.06), 0.85)
        elif nr == 2:
            x = min(max(st.pfr_rate() * 0.45, 0.05), 0.35)
            if r_allin:
                x = max(x, interp(r_bb, *SHOVE_X) * 0.5)
        else:
            x = 0.05
            if r_allin:
                x = max(x, interp(r_bb, *SHOVE_X) * 0.35)
        # multiple players involved -> stronger
        callers_after = len([h for h in hist if h[0] == 0 and h[2] == "call" and raises and True])
        eq = EVT[c, xi(x)]
        vol = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise") and h[1] != me and h[1] in in_hand)
        n_yet = len([s for s in behind if s not in vol])
        n_live = max(1, len(vol))
        expo = 1.0 + 0.6 * (n_live - 1) + 0.08 * n_yet
        if expo > 1.0:
            eq = eq ** expo
        need = to_call / (pot + to_call)
        risk = to_call / max(my_total, 1)
        commit = to_call >= 0.4 * stacks[me] or eff_bb <= 15
        # resteal: shove over a single raise using the raiser's fold rate
        if RESTEAL and nr == 1 and not r_allin and self.can_raise(obs) and 15 < eff_bb <= 40 and n_live == 1:
            ftr = st.fold_to_raise() * 0.8
            if rto >= 0.35 * r_total:
                ftr *= 0.5
            pf = ftr
            for s2 in behind:
                pf *= 0.93
            xc = max(0.03, x * (1 - ftr))
            eqc = EVT[c, xi(xc)]
            e = min(my_total, r_total)
            final_pot = pot + (e - bets[me]) + (e - bets[rseat])
            ev_shove = pf * pot + (1 - pf) * (eqc * final_pot - (e - bets[me]))
            ev_shove -= self.tightness_icm(obs, 1.0) * e * 0.5
            ev_call = eq * (pot + to_call) - to_call
            if ev_shove > 0 and (ev_shove >= ev_call or commit):
                self.pf_aggr = True
                return self.a_allin(obs)
        # strong: re-raise / shove
        reraise_th = 0.6 if nr == 1 else 0.62
        if eq >= reraise_th and self.can_raise(obs):
            self.pf_aggr = True
            if eff_bb <= 28 or nr >= 2:
                return self.a_allin(obs)
            return self.a_raise(obs, 3.0 * rto + (pot - rto - bets[me]) * 0.5)
        if commit:
            # call-off decision vs all the chips
            # compute call of effective amount: if we call, we may be committed: use full eff
            call_amt = min(to_call, stacks[me])
            need2 = call_amt / (pot + call_amt)
            if r_allin or to_call >= 0.4 * stacks[me]:
                if eq >= need2 + self.tightness_icm(obs, risk):
                    return self.a_call(obs)
                return self.a_fold(obs)
            # raise not all-in but we're short: shove (with fold equity) or fold
            if self.can_raise(obs):
                ftr = st.fold_to_raise() * 0.6
                if rto >= 0.35 * r_total:
                    ftr *= 0.5
                pf = ftr
                for s2 in behind:
                    pf *= 0.93
                xc = max(0.03, x * (1 - ftr))
                eqc = EVT[c, xi(xc)]
                if n_live > 1:
                    eqc = eqc ** (1.0 + 0.3 * (n_live - 1))
                e = min(my_total, r_total)
                final_pot = pot + (e - bets[me]) + (e - bets[rseat])
                ev_shove = pf * pot + (1 - pf) * (eqc * final_pot - (e - bets[me]))
                ev_shove -= self.tightness_icm(obs, 1.0) * e * 0.5
                if ev_shove > 0:
                    self.pf_aggr = True
                    return self.a_allin(obs)
            if eq >= need + 0.05 and to_call <= 0.15 * stacks[me]:
                return self.a_call(obs)
            return self.a_fold(obs)
        # deep: call with implied odds
        btn = obs["button"]
        n = self.nseats
        mypos = (me - btn - 1) % n
        ip = all((s2 - btn - 1) % n < mypos for s2 in in_hand if s2 != me)
        margin = -0.03 if ip else 0.03
        if nr >= 2:
            margin += 0.03
        real = 0.95 if ip else 0.82
        if eq * real >= need + margin and to_call <= 0.25 * stacks[me]:
            return self.a_call(obs)
        return self.a_fold(obs)

    def shove_ev(self, obs, c, behind, pot, my_total, my_bet, n_behind):
        bb = max(obs["bb"], 1)
        stacks = obs["stacks"]
        bets = obs["bets"]
        ev_called = 0.0
        p_reach = 1.0
        widen = 1.0 + WIDEN * max(0, 4 - n_behind)
        for s in behind:
            opp_total = stacks[s] + bets[s]
            e = min(my_total, opp_total)
            x = min(0.95, interp(e / bb, *CALL_X) * widen)
            st = self.stats[s]
            pc = st.big_call_rate(x)
            pc = min(max(pc, 0.03), 0.95)
            eqv = EVT[c, xi(pc)]
            final_pot = pot + (e - my_bet) + (e - bets[s])
            ev_c = eqv * final_pot - (e - my_bet)
            ev_called += p_reach * pc * ev_c
            p_reach *= (1 - pc)
        ev = p_reach * pot + ev_called
        # risk adjustment
        ev -= self.tightness_icm(obs, 1.0) * my_total * 0.5
        return ev

    # ------------------------------------------------------------ postflop
    def opp_weights(self, obs, s, hole_mask):
        """class weight vector (81) of opponent s from its preflop action this hand"""
        hist = obs["history"]
        raised = 0
        called_raise = False
        nraise = 0
        for h in hist:
            if h[0] != 0:
                continue
            if h[2] == "raise":
                nraise += 1
                if h[1] == s:
                    raised = nraise
            elif h[2] == "call" and h[1] == s and nraise > 0:
                called_raise = True
        st = self.stats[s]
        if raised == 1:
            x = min(max(st.pfr_rate(), 0.1), 0.6)
        elif raised >= 2:
            x = min(max(st.pfr_rate() * 0.5, 0.06), 0.35)
        elif called_raise:
            x = min(max(st.vpip_rate() * 1.1, 0.2), 0.8)
        else:
            x = 1.0
        w = INC[xi(x)] * 0.9 + 0.1
        if not raised and not called_raise:
            w = np.ones(81)
        return w

    def postflop(self, obs, hole, board):
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        street = obs["street_index"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        hist = obs["history"]
        bb = max(obs["bb"], 1)
        if not opps:
            return self.a_call(obs)
        eq_list = self.equities(obs, hole, board, opps)
        eq = 1.0
        for e in eq_list:
            eq *= e
        my_stack = stacks[me]
        # aggression on this street by others
        n_opp = len(opps)
        live_opp_stack = max(stacks[s] for s in opps)
        spr = min(my_stack, live_opp_stack) / max(pot, 1)
        rnd = self.rng.random()
        ftb1 = self.stats[opps[0]].fold_to_bet() if n_opp == 1 else 0.45
        if to_call == 0:
            thin = VALUE_HU if ftb1 >= 0.35 or not THIN else 0.53
            if eq >= 0.68 or (eq >= thin and n_opp == 1):
                frac = 0.75 if eq > 0.8 else 0.6
                if ftb1 < 0.35 and THIN:
                    frac += 0.15
                if spr <= 1.3:
                    return self.a_allin(obs)
                return self.a_raise(obs, frac * pot)
            # bluff / semi-bluff heads-up
            if n_opp == 1 and live_opp_stack > 0:
                ftb = self.stats[opps[0]].fold_to_bet()
                pb = 0.0
                if self.pf_aggr and street == 1:
                    pb = BLUFF
                elif street >= 2:
                    pb = BLUFF * 0.36
                pb *= 0.5 + ftb
                if eq >= 0.35 and street < 3:
                    pb += 0.2
                if rnd < pb:
                    return self.a_raise(obs, 0.5 * pot)
            return {"action": "check"}
        need = to_call / (pot + to_call)
        if eq >= 0.8 and self.can_raise(obs):
            if spr <= 2.0:
                return self.a_allin(obs)
            cur = max(bets)
            return self.a_raise(obs, cur * 2.5 + (pot - sum(bets)) * 0.5)
        margin = 0.02 if street == 3 else 0.04
        risk = to_call / max(my_stack + bets[me], 1)
        margin += self.tightness_icm(obs, risk) if risk > 0.3 else 0.0
        if eq >= need + margin:
            return self.a_call(obs)
        return self.a_fold(obs)

    def equities(self, obs, hole, board, opps):
        dead = 0
        for c in hole + board:
            dead |= 1 << c
        valid = np.nonzero((CMASK & dead) == 0)[0]
        nb = len(board)
        rng = self.rng
        late = time.thread_time() - self.t0 > 0.0002
        if nb < 5:
            msub = 70 if late else NSUB
            if len(valid) > msub:
                valid = valid[self.nrng.choice(len(valid), msub, replace=False)]
        cm = CMASK[valid]
        cc = CCODE[valid]
        cls = CCLS[valid]
        deck = [c for c in range(36) if not dead >> c & 1]
        if nb == 5:
            runs = [[]]
        elif nb == 4:
            runs = [[c] for c in deck]
        else:
            n = len(deck)
            runs = []
            idxs = rng.sample(range(n), min(FLOP_R, n)) if not late else rng.sample(range(n), min(8, n))
            for i in idxs:
                j = rng.randrange(n - 1)
                if j >= i:
                    j += 1
                runs.append([deck[i], deck[j]])
        R = len(runs)
        bcode = sum(P5L[c] for c in board)
        if nb == 5:
            RA = np.zeros((1, 0), dtype=np.int64)
        else:
            RA = np.array(runs, dtype=np.int64)
        rcode = bcode + P5[RA].sum(1)
        rmask = (np.int64(1) << RA).sum(1)
        RS = RA & 3
        hcode = P5L[hole[0]] + P5L[hole[1]]
        vals = TAB[rcode[:, None] + cc[None, :]]
        hero = TAB[rcode + hcode]
        # flushes
        bsc = [0, 0, 0, 0]
        bsm = [0, 0, 0, 0]
        for c in board:
            bsc[c & 3] += 1
            bsm[c & 3] |= 1 << (c >> 2)
        for s in range(4):
            if bsc[s] + (5 - nb) < 3:
                continue
            m_s = RS == s
            rs = bsc[s] + m_s.sum(1)
            if rs.max() < 3:
                continue
            rm = bsm[s] | np.where(m_s, RBIT[RA], 0).sum(1)
            tot = rs[:, None] + CSUITCNT[s][valid][None, :]
            F = tot >= 5
            if F.any():
                sv = SUITED[rm[:, None] | CSUITBITS[s][valid][None, :]]
                vals = np.where(F & (sv > vals), sv, vals)
            hs = sum(1 for c in hole if c & 3 == s)
            hb = sum(1 << (c >> 2) for c in hole if c & 3 == s)
            hf = (rs + hs) >= 5
            if hf.any():
                hv = SUITED[rm | hb]
                hero = np.where(hf & (hv > hero), hv, hero)
        ok = (cm[None, :] & rmask[:, None]) == 0
        hcol = hero[:, None]
        win = ((hcol > vals).astype(np.float64) + 0.5 * (hcol == vals)) * ok
        okc = ok.sum(0)
        per = win.sum(0) / np.maximum(okc, 1)
        # opponents' current made-hand strength (for narrowing by aggression)
        aggr = {}
        for h in hist_iter(obs["history"]):
            if h[0] >= 1:
                if h[2] == "raise":
                    aggr[h[1]] = aggr.get(h[1], 0) + 1
                elif h[2] == "call":
                    aggr[h[1]] = aggr.get(h[1], 0) + CALL_NARROW
        cur_pct = None
        out = []
        for s in opps:
            w = self.opp_weights(obs, s, dead)[cls] * (okc > 0)
            k = aggr.get(s, 0)
            if k and time.thread_time() - self.t0 > 0.00062:
                k = 0
            if k:
                if cur_pct is None:
                    cv = TAB[bcode + cc]
                    for s2 in range(4):
                        if bsc[s2] >= 3:
                            F2 = (bsc[s2] + CSUITCNT[s2][valid]) >= 5
                            if F2.any():
                                sv2 = SUITED[bsm[s2] | CSUITBITS[s2][valid]]
                                cv = np.where(F2 & (sv2 > cv), sv2, cv)
                    order = np.argsort(cv, kind="stable")
                    ranks = np.empty(len(cv))
                    ranks[order] = np.arange(len(cv))
                    cur_pct = (ranks + 1) / len(cv)
                agg = self.stats[s].agg()
                expo = 1.3 * k * min(1.6, max(0.5, 0.35 / agg))
                w = w * (cur_pct ** expo + 0.03)
            tw = w.sum()
            out.append(float((w * per).sum() / tw) if tw > 0 else 0.5)
        return out

    # ------------------------------------------------------------ observe
    def observe(self, event):
        if event.get("type") != "hand_end":
            return
        try:
            self.update_stats(event)
        except Exception:
            pass

    def update_stats(self, ev):
        hist = ev.get("history") or []
        seen = set()
        for h in hist:
            if h[2] in ("sb", "bb", "ante"):
                seen.add(h[1])
        for h in hist:
            seen.add(h[1])
        for s in seen:
            if s != self.seat and s < len(self.stats):
                self.stats[s].hands += 1
        nraise = 0
        vp = set()
        pr = set()
        street = -1
        bet_on = False
        for h in hist:
            st_i, s, a = h[0], h[1], h[2]
            if a in ("sb", "bb", "ante", "return", "discard"):
                continue
            if s >= len(self.stats):
                continue
            S = self.stats[s]
            if st_i != street:
                street = st_i
                bet_on = (st_i == 0)
                nraise = 0
            if st_i == 0:
                if nraise > 0 and s != self.seat:
                    S.fr_opp += 1
                    if a == "fold":
                        S.fr_fold += 1
                if a in ("call", "raise"):
                    vp.add(s)
                if a == "raise":
                    pr.add(s)
                    nraise += 1
            else:
                if a in ("raise", "bet"):
                    S.pf_bets += 1
                    S.pf_acts += 1
                    if bet_on and s != self.seat:
                        S.fb_opp += 1
                    bet_on = True
                elif a in ("call", "check"):
                    S.pf_acts += 1
                    if bet_on and a == "call":
                        S.fb_opp += 1
                elif a == "fold":
                    S.pf_acts += 1
                    if bet_on:
                        S.fb_opp += 1
                        S.fb_fold += 1
        for s in vp:
            self.stats[s].vpip += 1
        for s in pr:
            self.stats[s].pfr += 1
        # big bets (all-in-ish raises preflop): who called
        stacks_end = ev.get("stacks")
        # approximate: a preflop raise to >= 40% of the start-of-hand stack is "big"
        start = {}
        if stacks_end is not None:
            pay = ev.get("payoffs") or {}
            for s in seen:
                try:
                    start[s] = stacks_end[s] - pay.get(s, pay.get(str(s), 0))
                except Exception:
                    pass
        big = False
        for h in hist:
            if h[0] != 0 or h[2] in ("sb", "bb", "ante", "return"):
                continue
            s, a = h[1], h[2]
            if big and s != self.seat and s < len(self.stats):
                self.stats[s].big_opp += 1
                if a == "call" or a == "raise":
                    self.stats[s].big_call += 1
            if a == "raise" and s in start and start[s] > 0 and h[3] >= 0.4 * start[s]:
                big = True
                if h[3] >= 0.95 * start[s] and s < len(self.stats):
                    self.stats[s].shoves += 1


def hist_iter(h):
    return h
