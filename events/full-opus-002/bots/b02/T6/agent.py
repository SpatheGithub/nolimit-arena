import json
import os
import random

_DIR = os.path.dirname(os.path.abspath(__file__))
RANKS = "23456789TJQKA"
SUITS = "cdhs"
RIDX = {r: i for i, r in enumerate(RANKS)}
SIDX = {s: i for i, s in enumerate(SUITS)}


def _load(name):
    with open(os.path.join(_DIR, name)) as f:
        return json.load(f)


_base = _load("pfbase.json")
PCT = [p / 10000.0 for p in _base["pct"]]  # 0 = best
EQM = [[x / 10000.0 for x in row] for row in _base["eq_multi"]]
try:
    PFEQ = _load("pfeq.json")
except Exception:  # pragma: no cover
    PFEQ = None


def _ncombo(c):
    a, b = divmod(c, 13)
    return 6 if a == b else (4 if a > b else 12)


NCOMBO = [_ncombo(c) for c in range(169)]
ORDER = sorted(range(169), key=lambda c: PCT[c])
# cumulative top fraction for each class (fraction of combos at or above it)
TOPFRAC = [0.0] * 169
_cum = 0
for _c in ORDER:
    _cum += NCOMBO[_c]
    TOPFRAC[_c] = _cum / 1326.0

P = {"shove_bb": 11, "stackoff": 0.4, "stackoff_pen": 0.08, "open_mult": 1.2, "cbet1": 0.6,
     "cbet2": 0.3, "value_e": 0.66, "thin_e": 0.52, "call_margin": 0.02, "cp_k": 1.3, "r_k": 2.2,
     "shove_thr": 0.0, "adapt": 1, "reshove_bb": 16, "fe": 1, "icm": 1, "icm_n": 4, "icm_margin": 0.0, "hu": 1, "late_pen": 0.2, "flop_pen": 0.0, "steal_adapt": 1, "size_adapt": 1, "icm_shove": 1, "icm_shove_n": 3, "rs_fix": 1, "pos_r": 1, "big_r": 1, "early_margin": 0.05, "early_pen": 0.07, "util": 1, "alpha": 0.75, "hu_open": 0.85, "hu_size": 2.5, "def2": 0.75}
try:
    P.update(_load("params.json"))
except Exception:
    pass
HUF = {2: 2.0, 3: 1.4, 4: 1.15}
DEF = {2: P.get("def2", 0.6), 3: 0.4}
SHOVE_BB = P["shove_bb"]
STACKOFF = P["stackoff"]
STACKOFF_PEN = P["stackoff_pen"]

GRID = [0.02, 0.04, 0.06, 0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.75, 1.0]


def _range_weights(x):
    w = [0.0] * 169
    need = x * 1326.0
    acc = 0.0
    for c in ORDER:
        n = NCOMBO[c]
        if acc + n <= need:
            w[c] = n
            acc += n
        else:
            w[c] = max(0.0, need - acc)
            acc = need
            break
    return w


EQTOP = None
if PFEQ is not None:
    EQTOP = [[0.5] * len(GRID) for _ in range(169)]
    for gi, x in enumerate(GRID):
        w = _range_weights(x)
        idx = [(j, w[j]) for j in range(169) if w[j] > 0]
        tot = sum(v for _, v in idx)
        for c in range(169):
            row = PFEQ[c]
            s = 0.0
            for j, v in idx:
                s += row[j] * v
            EQTOP[c][gi] = s / tot


if PFEQ is not None:
    PFEQ = tuple(tuple(r) for r in PFEQ)
if EQTOP is not None:
    EQTOP = tuple(tuple(r) for r in EQTOP)
EQM = tuple(tuple(r) for r in EQM)
PCT = tuple(PCT)
TOPFRAC = tuple(TOPFRAC)


def eq_vs_top(c, x):
    """Equity of class c vs a range of the top x fraction of hands."""
    if EQTOP is None:
        return EQM[c][0] * (0.6 + 0.4 * x)
    if x <= GRID[0]:
        return EQTOP[c][0]
    if x >= 1.0:
        return EQTOP[c][-1]
    for i in range(1, len(GRID)):
        if x <= GRID[i]:
            a, b = GRID[i - 1], GRID[i]
            t = (x - a) / (b - a)
            return EQTOP[c][i - 1] * (1 - t) + EQTOP[c][i] * t
    return EQTOP[c][-1]


def icm_equity(stacks, payouts):
    n = len(stacks)
    if n == 0:
        return []
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    paid = max((k + 1 for k, p in enumerate(pay) if p), default=0)
    if paid == 0:
        return [0.0] * n
    full = (1 << n) - 1
    memo = {}

    def rest(mask):
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < paid:
            total = 0.0
            for i in members:
                total += stacks[i]
            for i in members:
                p = stacks[i] / total if total > 0 else 1.0 / len(members)
                if p <= 0:
                    continue
                res[i] += p * pay[place]
                sub = rest(mask & ~(1 << i))
                for j in members:
                    if j != i:
                        res[j] += p * sub[j]
        memo[mask] = res
        return res

    return rest(full)


def hand_class(r1, s1, r2, s2):
    hi, lo = (r1, r2) if r1 >= r2 else (r2, r1)
    if hi == lo:
        return hi * 13 + hi
    if s1 == s2:
        return hi * 13 + lo
    return lo * 13 + hi


def parse(c):
    return RIDX[c[0]], SIDX[c[1]]


# ---------------------------------------------------------------- evaluator
def _straight_top(mask):
    # mask: 13-bit rank mask; returns top rank of best straight or -1
    m = mask | ((mask >> 12) & 1) << 13  # ace also low -> bit 13 placeholder handled below
    best = -1
    # ranks 0..12; wheel A-2-3-4-5 top = 3
    for top in range(12, 3, -1):
        need = 0b11111 << (top - 4)
        if mask & need == need:
            return top
    if mask & 0b1000000001111 == 0b1000000001111:
        return 3
    return best


def evaluate(cards):
    """cards: list of (rank, suit). Returns comparable int; category = v >> 20."""
    cnt = [0] * 13
    suits = [[], [], [], []]
    mask = 0
    for r, s in cards:
        cnt[r] += 1
        suits[s].append(r)
        mask |= 1 << r
    fl = None
    for s in range(4):
        if len(suits[s]) >= 5:
            fl = suits[s]
            break
    if fl is not None:
        fm = 0
        for r in fl:
            fm |= 1 << r
        st = _straight_top(fm)
        if st >= 0:
            return (8 << 20) | st
    quads = []
    trips = []
    pairs = []
    singles = []
    for r in range(12, -1, -1):
        c = cnt[r]
        if c == 4:
            quads.append(r)
        elif c == 3:
            trips.append(r)
        elif c == 2:
            pairs.append(r)
        elif c == 1:
            singles.append(r)
    if quads:
        q = quads[0]
        k = max([r for r in range(13) if cnt[r] and r != q] or [0])
        return (7 << 20) | (q << 4) | k
    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        p = max(trips[1] if len(trips) > 1 else -1, pairs[0] if pairs else -1)
        return (6 << 20) | (t << 4) | p
    if fl is not None:
        fs = sorted(fl, reverse=True)[:5]
        v = 0
        for r in fs:
            v = (v << 4) | r
        return (5 << 20) | v
    st = _straight_top(mask)
    if st >= 0:
        return (4 << 20) | st
    if trips:
        t = trips[0]
        ks = [r for r in range(12, -1, -1) if cnt[r] and r != t][:2]
        v = t
        for r in ks:
            v = (v << 4) | r
        return (3 << 20) | v
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        k = max([r for r in range(13) if cnt[r] and r != p1 and r != p2] or [0])
        return (2 << 20) | (p1 << 8) | (p2 << 4) | k
    if pairs:
        p = pairs[0]
        ks = [r for r in range(12, -1, -1) if cnt[r] and r != p][:3]
        v = p
        for r in ks:
            v = (v << 4) | r
        return (1 << 20) | v
    ks = [r for r in range(12, -1, -1) if cnt[r]][:5]
    v = 0
    for r in ks:
        v = (v << 4) | r
    return v


def straight_outs(hole_ranks, board_ranks):
    """Number of missing ranks that would complete a straight using a hole card."""
    allm = 0
    for r in hole_ranks + board_ranks:
        allm |= 1 << r
    bm = 0
    for r in board_ranks:
        bm |= 1 << r
    if _straight_top(allm) >= 0:
        return 0
    n = 0
    for x in range(13):
        if allm >> x & 1:
            continue
        t = _straight_top(allm | 1 << x)
        if t >= 0 and _straight_top(bm | 1 << x) < 0:
            n += 1
    return n


# ---------------------------------------------------------------- agent
class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.n_seats = config.get("seats", 8)
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        n = self.n_seats
        self.hands = [0] * n
        self.vpip = [0] * n
        self.pfr = [0] * n
        self.shoves = [0] * n
        self.agg = [0] * n
        self.pas = [0] * n
        self.faced = [0] * n
        self.folded = [0] * n
        self.cur_hand = -1
        self.start_stacks = None
        self.pf_aggressor = False

    # ------------------------------------------------------------ helpers
    def _act_raise(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        legal = obs["legal"]
        if hi and lo and ("raise" in legal or "bet" in legal):
            amt = int(amt)
            if amt < lo:
                amt = lo
            if amt >= hi * 0.8:
                amt = hi
            if amt > hi:
                amt = hi
            return {"action": "raise", "amount": amt}
        return self._act_call(obs)

    def _act_allin(self, obs):
        hi = obs["max_raise_to"]
        legal = obs["legal"]
        if hi and ("raise" in legal or "bet" in legal):
            return {"action": "raise", "amount": hi}
        return self._act_call(obs)

    def _act_call(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "call"}

    def _act_fold(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "fold"}

    def _opp_vpip(self, s):
        h = self.hands[s]
        return (self.vpip[s] + 0.25 * 6) / (h + 6)

    def _opp_shove(self, s):
        h = self.hands[s]
        return (self.shoves[s] + 0.03 * 10) / (h + 10)

    def _opp_fold(self, s):
        return (self.folded[s] + 0.4 * 5) / (self.faced[s] + 5)

    def _opp_af(self, s):
        return (self.agg[s] + 1.0) / (self.agg[s] + self.pas[s] + 3.0)

    # ------------------------------------------------------------ main
    def act(self, obs):
        if P.get("debug"):
            return self._act(obs)
        try:
            return self._act(obs)
        except Exception:
            if obs.get("to_call", 0) <= 0:
                return {"action": "check"}
            return {"action": "fold"}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["hand_id"] != self.cur_hand:
            self.cur_hand = obs["hand_id"]
            self.pf_aggressor = False
            if obs["street_index"] == 0:
                self.start_stacks = [obs["stacks"][i] + obs["bets"][i] for i in range(len(obs["stacks"]))]
            else:
                self.start_stacks = None
        if obs["street_index"] == 0:
            return self._preflop(obs)
        return self._postflop(obs)

    # ------------------------------------------------------------ preflop
    def _preflop(self, obs):
        me = self.seat
        (r1, s1), (r2, s2) = parse(obs["hole"][0]), parse(obs["hole"][1])
        c = hand_class(r1, s1, r2, s2)
        top = TOPFRAC[c]
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        mybet = bets[me]
        mystack = stacks[me]
        alive = obs["alive"]
        in_hand = obs["in_hand"]
        hist = obs["history"]

        # preflop action order: left of BB clockwise
        n = self.n_seats
        order = []
        bbs = obs["bb_seat"]
        for k in range(1, n + 1):
            s = (bbs + k) % n
            if s in alive:
                order.append(s)
        my_i = order.index(me) if me in order else 0
        behind = [s for s in order[my_i + 1:] if s in in_hand and stacks[s] > 0]
        # also players who acted before but can still act (limpers) - not counted

        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        n_raises = len(raises)
        cur_bet = max(bets) if bets else 0
        limpers = [h[1] for h in hist if h[0] == 0 and h[2] == "call"]
        my_total = mystack + mybet  # chips I have in this street + behind
        eff_stack = 0
        for s in in_hand:
            if s != me:
                eff_stack = max(eff_stack, stacks[s] + bets[s])
        eff = min(my_total, eff_stack) if eff_stack > 0 else my_total
        eff_bb = eff / bb
        n_players = len(alive)

        # unopened pot (no raise above the big blind)
        if n_raises == 0:
            if eff_bb <= SHOVE_BB or (n_players <= 3 and eff_bb <= SHOVE_BB + 4):
                resp = behind + [s for s in set(limpers) if s in in_hand and s != me and stacks[s] > 0]
                if P["icm_shove"] and n_players <= P["icm_shove_n"] and resp:
                    if self._shove_icm(obs, c, resp, pot, mybet, mystack) > 0:
                        return self._act_allin(obs)
                    if to_call == 0:
                        return {"action": "check"}
                    return self._act_fold(obs)
                ev = self._shove_ev(obs, c, resp, pot, mybet, mystack)
                thr = P["shove_thr"] * mystack if n_players > 4 else -0.02 * mystack
                if ev > thr:
                    return self._act_allin(obs)
                if to_call == 0:
                    return {"action": "check"}
                return self._act_fold(obs)
            nb = len(behind)
            open_tbl = {0: 1.0, 1: 0.45, 2: 0.33, 3: 0.25, 4: 0.20, 5: 0.16, 6: 0.13, 7: 0.11}
            thr = open_tbl.get(nb, 0.11) * P["open_mult"]
            if P["steal_adapt"] and behind:
                av = sum(self._opp_vpip(x) for x in behind) / len(behind)
                thr *= min(1.35, max(0.85, 1 + 1.5 * (0.25 - av)))
            if limpers:
                thr *= 0.8
            if P["hu_open"] and n_players == 2 and not limpers:
                thr = max(thr, P["hu_open"])
            # loosen when blinds are behind tight players? keep simple
            if to_call == 0:
                # big blind option
                if top <= 0.10:
                    return self._act_raise(obs, cur_bet + (3 + len(limpers)) * bb)
                return {"action": "check"}
            if top <= thr:
                size = (2.5 if n_players > 3 else 2.2) * bb + len(limpers) * bb
                if mybet > 0 and nb == 1:
                    size = (P["hu_size"] if (P["hu_open"] and n_players == 2) else 3) * bb
                return self._act_raise(obs, size)
            # small blind completing in a limped pot / heads-up
            if nb == 1 and to_call <= 0.5 * bb + 1 and top <= 0.6:
                return self._act_call(obs)
            if limpers and to_call <= bb and top <= 0.22 and eff_bb > 25:
                return self._act_call(obs)
            return self._act_fold(obs)

        # facing a raise
        raiser = raises[-1][1]
        raise_to = raises[-1][3]
        raiser_total = stacks[raiser] + bets[raiser]
        raiser_allin = stacks[raiser] == 0
        call_amt = min(to_call, mystack)
        # estimate raiser range
        if raiser_allin or raise_to >= 0.5 * raiser_total:
            sb_ = raiser_total / bb
            hf = HUF.get(n_players, 1.0) if P["hu"] else 1.0
            r = P["r_k"] * hf / max(1.0, sb_) + 0.05 * hf
            if P["pos_r"] and n_raises == 1 and raiser in order:
                left = len(order) - 1 - order.index(raiser)
                r *= {1: 1.6, 2: 1.3, 3: 1.1}.get(left, 1.0)
            r = max(r, 1.4 * self._opp_shove(raiser))
            r = min(0.7, max(0.04, r))
        else:
            v = self._opp_vpip(raiser)
            r = min(0.6, max(0.05, 0.55 * v + 0.02))
            if P["big_r"]:
                rb = raise_to / bb
                if rb >= 6:
                    r = min(r, max(0.04, 0.6 / rb + 0.03))
        if n_raises >= 2:
            if P["rs_fix"] and raiser_allin and raiser_total <= 25 * bb:
                i_raised = any(h[0] == 0 and h[1] == me and h[2] == "raise" for h in hist)
                r = max(0.04, r * (0.8 if i_raised else 0.6))
            else:
                r = min(r, 0.06)
        last_i = max(i for i, h in enumerate(hist) if h[0] == 0 and h[2] == "raise")
        n_callers = sum(1 for h in hist[last_i + 1:] if h[0] == 0 and h[2] == "call" and h[1] != me)
        # pot-committing decision?
        commit = raise_to >= 0.33 * my_total or eff_bb <= P["reshove_bb"] or raiser_allin
        if commit:
            # all-in or fold based on EV against raiser's range (assume called if we shove)
            eq = eq_vs_top(c, r)
            if n_callers:
                eq = eq ** (1 + 0.6 * n_callers)
            # amount we'd invest if we shove and they call
            their_total = raiser_total
            inv = min(my_total, their_total) - mybet
            dead = pot - bets[raiser] - mybet
            win = dead + min(my_total, their_total) + mybet
            ev = eq * win - (1 - eq) * inv
            if (P["fe"] and not raiser_allin and raise_to < 0.4 * raiser_total and n_callers == 0
                    and n_raises == 1 and stacks[me] > to_call):
                pc = 0.45
                if P["big_r"]:
                    pc = min(0.9, 0.45 + 1.5 * raise_to / max(1, raiser_total))
                eq2 = eq_vs_top(c, r * pc)
                ev2 = (1 - pc) * pot + pc * (eq2 * win - (1 - eq2) * inv)
                ev = max(ev, ev2) if P["fe"] == 2 else ev2
                fe_on = True
            else:
                fe_on = False
            if P["util"] and n_players > P["icm_n"]:
                a_ = P["alpha"]
                base = max(1.0, float(mystack))
                u0 = base ** a_

                def U(x):
                    return max(0.0, x) ** a_ - u0
                ev_u = eq * U(mystack + win) + (1 - eq) * U(mystack - inv)
                if fe_on:
                    ev_u = (1 - pc) * U(mystack + pot) + pc * (eq2 * U(mystack + win) + (1 - eq2) * U(mystack - inv))
                du = a_ * base ** (a_ - 1)
                if ev_u > du * (0.03 * inv * len(behind) + P["call_margin"] * inv):
                    return self._act_allin(obs)
                return self._act_fold(obs)
            if (P["icm"] and n_players <= P["icm_n"] and n_callers == 0
                    and (n_raises == 1 or (P["rs_fix"] and len(in_hand) == 2))
                    and (raiser_allin or stacks[raiser] <= 0.15 * raiser_total)):
                pay = self.points[:n_players]
                seats = [s_ for s_ in alive if stacks[s_] + bets[s_] > 0]
                C = min(to_call, mystack)
                excess = max(0, bets[raiser] - (mybet + mystack))

                def eqm(mine, rs):
                    st = [mine if s_ == me else (rs if s_ == raiser else stacks[s_]) for s_ in seats]
                    return icm_equity(st, pay)[seats.index(me)]
                e_fold = eqm(mystack, stacks[raiser] + pot)
                e_win = eqm(mystack + pot - excess, stacks[raiser] + excess)
                e_lose = eqm(mystack - C, stacks[raiser] + pot + C)
                if eq * e_win + (1 - eq) * e_lose > e_fold + P["icm_margin"]:
                    return self._act_allin(obs)
                return self._act_fold(obs)
            # other players behind could wake up; tighten
            margin = 0.03 * inv * len(behind) + P["call_margin"] * inv
            if P["big_r"] and n_players >= 6:
                margin += P["early_margin"] * inv
            if n_players <= 3:
                margin *= 0.5
            if ev > margin:
                return self._act_allin(obs)
            return self._act_fold(obs)
        # deep: 3-bet / call / fold
        if n_raises == 1:
            if top <= 0.035 or (top <= 0.06 and r >= 0.25) or (P["hu"] and n_players == 2 and top <= 0.12):
                return self._act_raise(obs, raise_to * 3 + len(limpers) * bb)
            price_ok = to_call <= 0.08 * my_total
            if top <= min(0.13, r * 0.6) and price_ok:
                return self._act_call(obs)
            # set mining with pairs
            if r1 == r2 and to_call * 15 <= eff:
                return self._act_call(obs)
            if mybet == bb and to_call <= 2 * bb and top <= (DEF.get(n_players, 0.3) if P["hu"] else 0.3):
                return self._act_call(obs)
            return self._act_fold(obs)
        # facing a 3-bet or more
        if top <= 0.025:
            return self._act_allin(obs)
        if top <= 0.05 and to_call <= 0.2 * my_total:
            return self._act_call(obs)
        return self._act_fold(obs)

    def _cp(self, obs, s, x):
        hf = HUF.get(len(obs["alive"]), 1.0) if P["hu"] else 1.0
        cp = P["cp_k"] * hf / max(x, 1.0) + 0.05 * hf
        v = self._opp_vpip(s)
        cp *= 0.7 + 1.2 * v
        return min(0.75, max(0.04, cp))

    def _shove_icm(self, obs, c, resp, pot, mybet, mystack):
        me = self.seat
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        alive = obs["alive"]
        seats = [s for s in alive if stacks[s] + bets[s] > 0]
        if me not in seats:
            return 0.0
        mi = seats.index(me)
        pay = self.points[:len(alive)]

        def eqm(mod):
            st = [mod.get(s, stacks[s]) for s in seats]
            return icm_equity(st, pay)[mi]
        others = [s for s in obs["in_hand"] if s != me]
        if others:
            tgt = max(others, key=lambda s: bets[s])
            e_fold = eqm({tgt: stacks[tgt] + pot})
        else:
            e_fold = eqm({})
        my_total = mystack + mybet
        ev = 0.0
        p_nocall = 1.0
        for s in resp:
            their_total = stacks[s] + bets[s]
            f = min(my_total, their_total)
            cp = self._cp(obs, s, f / bb)
            eq = eq_vs_top(c, cp)
            e_win = eqm({me: mystack + pot - bets[s] + f, s: their_total - f})
            e_lose = eqm({me: mystack - (f - mybet), s: their_total + (pot - mybet - bets[s]) + f})
            ev += p_nocall * cp * (eq * e_win + (1 - eq) * e_lose)
            p_nocall *= 1 - cp
        ev += p_nocall * eqm({me: mystack + pot})
        return ev - e_fold

    def _shove_ev(self, obs, c, behind, pot, mybet, mystack):
        bb = max(1, obs["bb"])
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_total = mystack + mybet
        ev = 0.0
        p_nocall = 1.0
        for s in behind:
            their_total = stacks[s] + bets[s]
            f = min(my_total, their_total)
            x = f / bb
            hf = HUF.get(len(obs["alive"]), 1.0) if P["hu"] else 1.0
            cp = P["cp_k"] * hf / max(x, 1.0) + 0.05 * hf
            v = self._opp_vpip(s)
            cp *= 0.7 + 1.2 * v
            # getting a price: big blind calls wider
            cp = min(0.75, max(0.04, cp))
            eq = eq_vs_top(c, cp)
            dead = pot - mybet - bets[s]
            win = dead + f + mybet
            lose = f - mybet
            ev += p_nocall * cp * (eq * win - (1 - eq) * lose)
            p_nocall *= (1 - cp)
        ev += p_nocall * pot
        if P["util"] and len(obs["alive"]) > P["icm_n"]:
            a_ = P["alpha"]
            base = max(1.0, float(mystack))
            u0 = base ** a_
            evu = 0.0
            pn = 1.0
            for s in behind:
                their_total = stacks[s] + bets[s]
                f = min(my_total, their_total)
                cp = self._cp(obs, s, f / bb)
                eq = eq_vs_top(c, cp)
                dead = pot - mybet - bets[s]
                evu += pn * cp * (eq * ((mystack + dead + f + mybet) ** a_ - u0)
                                  + (1 - eq) * (max(0.0, mystack - (f - mybet)) ** a_ - u0))
                pn *= (1 - cp)
            evu += pn * ((mystack + pot) ** a_ - u0)
            return evu / (a_ * base ** (a_ - 1))
        return ev

    # ------------------------------------------------------------ postflop
    def _postflop(self, obs):
        me = self.seat
        hole = [parse(x) for x in obs["hole"]]
        board = [parse(x) for x in obs["board"]]
        street = obs["street_index"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        mystack = stacks[me]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        hist = obs["history"]
        bb = max(1, obs["bb"])

        S, D = self._strength(hole, board)
        E = S + (1 - S) * D
        if n_opp > 1:
            E = E ** (1 + 0.55 * (n_opp - 1))

        # who bet into us
        bettor = None
        for h in reversed(hist):
            if h[0] == street and h[2] in ("raise", "bet") and h[1] != me:
                bettor = h[1]
                break
        pf_raiser = None
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                pf_raiser = h[1]
        i_was_aggr = pf_raiser == me
        n_my_raises_street = sum(1 for h in hist if h[0] == street and h[1] == me and h[2] in ("raise", "bet"))
        n_raises_street = sum(1 for h in hist if h[0] == street and h[2] in ("raise", "bet"))
        r = self.rng.random()
        if opps:
            fr = sum(self._opp_fold(s) for s in opps) / len(opps)
        else:
            fr = 0.4
        bm = min(1.8, max(0.3, fr / 0.4)) if P["adapt"] else 1.0

        if to_call <= 0:
            # we can check or bet
            if E >= P["value_e"]:
                size = 0.7 * pot
                if P["size_adapt"] and fr < 0.3:
                    size = 0.9 * pot
                if mystack <= 1.3 * pot:
                    return self._act_allin(obs)
                return self._act_raise(obs, size)
            if E >= P["thin_e"] and n_opp <= 2:
                return self._act_raise(obs, 0.5 * pot)
            if D >= 0.28 and n_opp <= 2 and r < 0.6 * min(1.3, bm):
                return self._act_raise(obs, 0.55 * pot)
            if street == 1 and i_was_aggr and n_opp <= 2 and r < (P["cbet1"] if n_opp == 1 else P["cbet2"]) * bm:
                return self._act_raise(obs, 0.45 * pot)
            if n_opp == 1 and street >= 2 and r < 0.15 * bm and S < 0.3:
                return self._act_raise(obs, 0.5 * pot)
            return {"action": "check"}

        # facing a bet
        call_amt = min(to_call, mystack)
        pot_odds = call_amt / (pot + call_amt)
        af = self._opp_af(bettor) if bettor is not None else 0.4
        # bet size tells strength
        rel = to_call / max(1, pot - to_call)
        adj = 0.10 * min(2.0, rel) * (1.3 - af) + (0.08 if n_raises_street >= 2 else 0.0)
        Ec = E - adj
        if street >= 2 and S < 0.85:
            Ec -= P["late_pen"] * (1.0 if street == 3 else 0.5) * (1.6 - 2 * af)
        elif street == 1 and S < 0.85:
            Ec -= P["flop_pen"] * (1.6 - 2 * af)
        if n_my_raises_street >= 1:
            Ec -= 0.05
        # implied odds for draws
        need = pot_odds
        if D > 0 and street < 3 and mystack > 3 * pot:
            need *= 0.8
        if S < 0.8 and call_amt > STACKOFF * (mystack + bets[me]):
            need += STACKOFF_PEN
            if P["big_r"] and len(obs["alive"]) >= 6:
                need += P["early_pen"]
        if Ec >= 0.8 and n_raises_street < 3:
            if mystack <= 2.5 * (pot + to_call):
                return self._act_allin(obs)
            cur = max(bets)
            return self._act_raise(obs, cur * 2.8 + (pot - sum(bets)) * 0.3)
        if Ec >= need + 0.02:
            return self._act_call(obs)
        return self._act_fold(obs)

    def _strength(self, hole, board):
        """S: chance our made hand is best vs one opponent; D: draw equity."""
        allc = hole + board
        v = evaluate(allc)
        cat = v >> 20
        nb = len(board)
        bv = evaluate(board) if nb >= 5 else None
        if bv is not None and bv >= v:
            return 0.12, 0.0
        br = sorted([r for r, _ in board], reverse=True)
        bcnt = [0] * 13
        for r, _ in board:
            bcnt[r] += 1
        bsuit = [0] * 4
        for _, s in board:
            bsuit[s] += 1
        max_bsuit = max(bsuit)
        board_paired = max(bcnt) >= 2
        h1, h2 = hole[0][0], hole[1][0]
        hi, lo = max(h1, h2), min(h1, h2)
        pocket = h1 == h2
        # straightiness of board
        bm = 0
        for r in br:
            bm |= 1 << r
        S = 0.1
        if cat == 8:
            S = 1.0
        elif cat == 7:
            S = 0.99 if max(bcnt) < 4 else 0.5
        elif cat == 6:
            if max(bcnt) >= 3 and not (pocket or bcnt[h1] or bcnt[h2]):
                S = 0.5
            else:
                S = 0.93
        elif cat == 5:
            # find flush suit
            fs = None
            for s in range(4):
                if bsuit[s] + sum(1 for _, x in hole if x == s) >= 5:
                    fs = s
            mine = [r for r, x in hole if x == fs]
            top_mine = max(mine) if mine else -1
            missing_higher = sum(1 for rr in range(top_mine + 1, 13)
                                 if not any(br_ == rr and bs_ == fs for br_, bs_ in board))
            if bsuit[fs] >= 4:
                S = 0.95 - 0.08 * missing_higher
                S = max(0.55, S)
            else:
                S = 0.97 - 0.04 * missing_higher
                S = max(0.75, S)
            if board_paired:
                S -= 0.1
        elif cat == 4:
            S = 0.86
            if max_bsuit >= 3:
                S -= 0.18
            if board_paired:
                S -= 0.08
            # one-card straight on 4-straight boards weaker
            if nb >= 4 and straight_outs([], br) == 0 and _straight_top(bm) < 0:
                pass
        elif cat == 3:
            if pocket and bcnt[h1] == 1:
                S = 0.92
            elif bcnt[h1] == 2 or bcnt[h2] == 2:
                k = lo if bcnt[hi] == 2 else hi
                S = 0.74 + 0.1 * k / 12.0
            else:
                S = 0.3 + 0.2 * hi / 12.0
            if max_bsuit >= 3:
                S -= 0.1
        elif cat == 2:
            p1 = (v >> 8) & 15
            p2 = (v >> 4) & 15
            if not pocket and bcnt[h1] >= 1 and bcnt[h2] >= 1:
                S = 0.84 if hi == br[0] else 0.77
            elif pocket and board_paired:
                S = 0.72 if hi > br[0] else 0.42
            elif (bcnt[h1] >= 1 or bcnt[h2] >= 1) and board_paired:
                pr = h1 if bcnt[h1] >= 1 else h2
                kick = h2 if pr == h1 else h1
                if pr == br[0] or pr > max([x for x in br if bcnt[x] >= 2] or [0]):
                    S = 0.6 + 0.1 * kick / 12.0
                else:
                    S = 0.45
            else:
                S = 0.15 + 0.15 * (hi / 12.0)
            if max_bsuit >= 3 and S > 0.5:
                S -= 0.08
        elif cat == 1:
            if pocket:
                if hi > br[0]:
                    S = 0.68 + 0.012 * (hi - 7)
                elif nb >= 2 and hi > br[1]:
                    S = 0.45
                else:
                    S = 0.3
            elif bcnt[h1] or bcnt[h2]:
                pr = h1 if bcnt[h1] else h2
                kick = h2 if pr == h1 else h1
                if pr == br[0]:
                    S = 0.58 + 0.14 * kick / 12.0
                elif nb >= 2 and pr == br[1]:
                    S = 0.44 + 0.06 * kick / 12.0
                else:
                    S = 0.32
            else:
                S = 0.12 + 0.12 * hi / 12.0
            if max_bsuit >= 3 and nb >= 4:
                S -= 0.06
        else:
            S = 0.05 + 0.15 * (hi / 12.0) * (lo / 12.0 + 0.5)
        S = max(0.0, min(1.0, S))
        D = 0.0
        if nb < 5 and S < 0.85:
            outs = 0
            for s in range(4):
                hs = sum(1 for _, x in hole if x == s)
                if hs >= 1 and bsuit[s] + hs == 4:
                    outs += 9 if hs == 2 or max(r for r, x in hole if x == s) >= 10 else 6
            so = straight_outs([h1, h2], br)
            outs += 4 * min(2, so)
            if outs:
                if nb == 3:
                    D = 1 - (1 - outs / 47.0) * (1 - outs / 46.0)
                else:
                    D = outs / 46.0
                D *= 0.85
        return S, D

    # ------------------------------------------------------------ observe
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            cur_st = -1
            bet_open = False
            vp = set()
            pr = set()
            for h in hist:
                st, s, a, amt = h[0], h[1], h[2], h[3]
                if s is None or not isinstance(s, int) or s < 0 or s >= self.n_seats:
                    continue
                seen.add(s)
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                        if self.start_stacks and self.start_stacks[s] > 0 and amt >= 0.9 * self.start_stacks[s]:
                            self.shoves[s] += 1
                else:
                    if st != cur_st:
                        cur_st = st
                        bet_open = False
                    if a in ("raise", "bet"):
                        self.agg[s] += 1
                        if bet_open:
                            self.faced[s] += 1
                        bet_open = True
                    elif a in ("call",):
                        self.pas[s] += 1
                        if bet_open:
                            self.faced[s] += 1
                    elif a == "fold":
                        self.faced[s] += 1
                        self.folded[s] += 1
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass
