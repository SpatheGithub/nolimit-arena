import marshal
import os
import random
import time
from itertools import combinations

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "evtab.bin"), "rb") as _f:
    RANKT, SUITEDT = marshal.load(_f)

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
NAME = [r + s for r in RANKS for s in SUITS]
RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
KEY = tuple((RANK_KEYS[c >> 2] + COUNT) << 16 | 1 << 4 * (c & 3) for c in range(52))
RANK_BIT = tuple(1 << (c >> 2) for c in range(52))
SB_BITS = {8 << 4 * s: tuple(RANK_BIT[c] if c & 3 == s else 0 for c in range(52)) for s in range(4)}


def evaluate(cards):
    s = 0x3333
    for c in cards:
        s += KEY[c]
    if s & 0x8888:
        bits = SB_BITS[s & 0x8888]
        f = SUITEDT[sum([bits[c] for c in cards])]
        r = RANKT[s >> 16]
        return f if f > r else r
    return RANKT[s >> 16]


# ---------------- preflop strength (3-card hands) ----------------

def _chen(a, b):
    ra, rb = a >> 2, b >> 2
    if ra < rb:
        ra, rb = rb, ra
    hi = (10, 8, 7, 6, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1)[12 - ra] if ra >= 0 else 0
    # rank 12 (A)=10, K=8, Q=7, J=6, T=5, 9=4.5 ...
    if ra == rb:
        sc = max(5.0, hi * 2)
        if ra == 3:
            sc = 5.0
        return sc
    sc = hi
    if (a & 3) == (b & 3):
        sc += 2
    gap = ra - rb - 1
    sc -= (0, 1, 2, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5)[gap] if gap < 13 else 5
    if gap <= 1 and ra < 10:
        sc += 1
    return sc


def _pf_score(h):
    a, b, c = h
    pairs = [(_chen(a, b), c), (_chen(a, c), b), (_chen(b, c), a)]
    pairs.sort(key=lambda t: -t[0])
    best, third = pairs[0]
    s2 = pairs[1][0]
    sc = best + 0.25 * max(0.0, s2) + 0.15 * max(0.0, pairs[2][0])
    ranks = sorted([a >> 2, b >> 2, c >> 2])
    if ranks[0] == ranks[2]:
        sc -= 3.0
    return sc


def _build_pf():
    combos = list(combinations(range(52), 3))
    scores = [(_pf_score(h), h) for h in combos]
    scores.sort(key=lambda t: -t[0])
    n = len(scores)
    tab = {}
    for i, (sc, h) in enumerate(scores):
        tab[h] = (i + 0.5) / n  # fraction of hands better or equal (0 = best)
    return tab


PF = _build_pf()


def pf_rank(hole):
    return PF[tuple(sorted(hole))]


# ---------------- helpers ----------------

def keep_score(keep, board, dead):
    """Average strength of keep+board over each possible next card."""
    if len(board) >= 5:
        return evaluate(list(keep) + list(board))
    known = set(dead) | set(board)
    base = list(keep) + list(board)
    tot = 0.0
    n = 0
    for c in range(52):
        if c in known:
            continue
        tot += evaluate(base + [c]) >> 12
        n += 1
    return tot / max(n, 1)


def best_keep(hole, board):
    if len(hole) <= 2:
        return list(hole)
    best = None
    bs = -1.0
    for k in combinations(hole, 2):
        sc = keep_score(k, board, hole)
        if sc > bs:
            bs, best = sc, k
    return list(best)


def quick_keep(hole, board):
    """Cheap keep choice: current made value + draw bonus."""
    if len(hole) <= 2:
        return list(hole)
    best = None
    bs = -1
    for k in combinations(hole, 2):
        cards = list(k) + list(board)
        v = evaluate(cards) if len(cards) >= 5 else 0
        # flush draw bonus
        suits = [0, 0, 0, 0]
        for c in cards:
            suits[c & 3] += 1
        bonus = 0
        if max(suits) == 4:
            bonus += 1 << 19
        m = 0
        for c in cards:
            m |= 1 << (c >> 2)
        if m & (1 << 12):
            m |= 1 << 13
        m <<= 1
        for lo in range(0, 11):
            w = (m >> lo) & 0x1F
            if bin(w).count("1") == 4:
                bonus += 1 << 18
                break
        v += bonus + ((k[0] >> 2) + (k[1] >> 2)) * 16
        if v > bs:
            bs, best = v, k
    return list(best)


def mc_equity(hole, board, n_opp, rng, budget=0.00030, max_iter=400):
    known = set(hole) | set(board)
    deck = [c for c in range(52) if c not in known]
    need = 5 - len(board)
    n_opp = max(1, min(n_opp, 6))
    draw = need + 2 * n_opp
    base = list(hole) + list(board)
    bkeys = 0x3333
    for c in board:
        bkeys += KEY[c]
    wins = 0.0
    it = 0
    sample = rng.sample
    clock = time.perf_counter
    t0 = clock()
    while it < max_iter:
        cards = sample(deck, draw)
        run = cards[:need]
        bcards = list(board) + run
        hv = evaluate(base + run)
        best_o = -1
        tie = 0
        j = need
        for _ in range(n_opp):
            ov = evaluate([cards[j], cards[j + 1]] + bcards)
            j += 2
            if ov > best_o:
                best_o = ov
        if hv > best_o:
            wins += 1.0
        elif hv == best_o:
            wins += 0.5
        it += 1
        if (it & 7) == 0 and clock() - t0 > budget:
            break
    return wins / max(it, 1)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.n = config.get("seats", 8)
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        # opponent stats: seat -> [hands dealt, vpip, pfr, shoves]
        self.st = {}
        self.keep = None
        self.pf_aggr = False
        self.cur_hand = -1

    # ---------- stats ----------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for h in hist:
                st, seat, act, amt = h[0], h[1], h[2], h[3]
                if st != 0:
                    continue
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if act in ("call", "raise"):
                    vp.add(seat)
                if act == "raise":
                    pr.add(seat)
            for s in seen:
                if s == self.seat:
                    continue
                d = self.st.setdefault(s, [0, 0, 0])
                d[0] += 1
                if s in vp:
                    d[1] += 1
                if s in pr:
                    d[2] += 1
        except Exception:
            pass

    def pfr(self, seat):
        d = self.st.get(seat)
        if not d:
            return 0.2
        return (d[2] + 0.2 * 6) / (d[0] + 6)

    # ---------- main ----------
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": obs["hole"][:obs.get("n_discard", 1)]}
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    def _act(self, obs):
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if obs["hand_id"] != self.cur_hand:
            self.cur_hand = obs["hand_id"]
            self.pf_aggr = False
        if obs["phase"] == "discard":
            nd = obs.get("n_discard", 1)
            keep = best_keep(hole, board)
            disc = [NAME[c] for c in hole if c not in keep][:nd]
            if len(disc) < nd:
                disc = obs["hole"][:nd]
            return {"action": "discard", "cards": disc}
        if obs["street_index"] == 0:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    # ---------- action helpers ----------
    def do_raise(self, obs, amount):
        legal = obs["legal"]
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        can = ("raise" in legal or "bet" in legal) and hi > 0
        if not can:
            if "call" in legal:
                return {"action": "call"}
            return {"action": "check"}
        amount = int(max(lo, min(hi, amount)))
        # if raise would leave us with little behind, just shove
        my_total = obs["stacks"][self.seat] + obs["bets"][self.seat]
        if amount > 0.7 * my_total:
            amount = hi
        return {"action": "raise", "amount": amount}

    def do_call(self, obs):
        if obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "call"}

    def do_fold(self, obs):
        if "check" in obs["legal"] or obs["to_call"] <= 0:
            return {"action": "check"}
        return {"action": "fold"}

    # ---------- preflop ----------
    def preflop(self, obs, hole):
        seat = self.seat
        bb = max(obs["bb"], 1)
        stacks = obs["stacks"]
        bets = obs["bets"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        my_stack = stacks[seat]
        my_total = my_stack + bets[seat]
        alive = obs["alive"]
        in_hand = obs["in_hand"]
        n_alive = len(alive)
        button = obs["button"]
        p = pf_rank(hole)
        hist = obs["history"]

        raises = []
        callers = 0
        for h in hist:
            if h[0] == 0 and h[2] == "raise":
                raises.append((h[1], h[3]))
            elif h[0] == 0 and h[2] == "call":
                callers += 1
        nr = len(raises)

        # players acting after me this round (not folded)
        bb_seat = obs["bb_seat"]
        order = sorted(alive, key=lambda s: (s - bb_seat - 1) % self.n)
        if seat in order:
            idx = order.index(seat)
            behind = [s for s in order[idx + 1:] if s in in_hand]
        else:
            behind = []
        nb = len(behind)

        others = [stacks[s] + bets[s] for s in in_hand if s != seat]
        eff = min(my_total, max(others) if others else my_total)
        M = eff / bb

        # base opening range by players behind, widened as the table shrinks
        open_frac = {0: 0.5, 1: 0.40, 2: 0.32, 3: 0.25, 4: 0.20, 5: 0.17, 6: 0.15, 7: 0.14}.get(nb, 0.14)

        is_bb = seat == bb_seat
        if nr == 0:
            if M <= 13:
                # push/fold
                f = open_frac * (1.0 + max(0.0, (13 - M)) / 5.0)
                if nb <= 1:
                    f *= 1.25
                f = min(f, 0.85)
                if p <= f:
                    return {"action": "allin"}
                if to_call <= 0:
                    return {"action": "check"}
                return self.do_fold(obs)
            if to_call <= 0:
                # BB option with limpers
                if p <= open_frac * 0.6 and callers > 0:
                    return self.do_raise(obs, (3 + callers) * bb + bets[seat])
                return {"action": "check"}
            if p <= open_frac:
                self.pf_aggr = True
                size = (2.5 + callers) * bb
                if nb <= 1:
                    size = 3 * bb
                return self.do_raise(obs, size)
            # cheap completion / limp-behind
            if callers > 0 and to_call <= bb and p <= open_frac * 1.6:
                return self.do_call(obs)
            if seat == obs["sb_seat"] and to_call <= bb / 2 + 0.01 and p <= 0.45:
                return self.do_call(obs)
            return self.do_fold(obs)

        # facing a raise
        rseat, rto = raises[-1]
        r_total = stacks[rseat] + bets[rseat]
        r_allin = stacks[rseat] == 0
        price = to_call / (pot + to_call)
        # estimate raiser's range width
        w = self.pfr(rseat)
        if r_allin:
            rM = r_total / bb
            w = max(w, 0.10 + 0.5 * max(0.0, (15 - rM)) / 15)
        if nr >= 2:
            w *= 0.5
        w = max(0.03, min(0.7, w))
        s_me = 1 - p
        s_opp = 1 - w / 2
        eq = 0.5 + 0.55 * (s_me - s_opp)
        eq = max(0.2, min(0.85, eq))
        n_in = len([s for s in in_hand if s != seat])
        if n_in >= 2:
            eq *= 0.85 ** (n_in - 1)

        commit = to_call >= 0.4 * my_stack or M <= 13
        if commit:
            margin = 0.04
            # ICM caution: busting costs more when the field is small
            if n_alive <= 4:
                margin += 0.03
            if eq > price + margin:
                if p <= 0.05 or M <= 13:
                    return {"action": "allin"} if not r_allin or to_call < my_stack else self.do_call(obs)
                return self.do_call(obs)
            return self.do_fold(obs)

        # deep: 3-bet / call / fold
        if nr == 1:
            if p <= 0.035:
                self.pf_aggr = True
                return self.do_raise(obs, 3 * rto + callers * rto)
            if p <= 0.11 and to_call <= 0.12 * my_stack:
                return self.do_call(obs)
            if is_bb and to_call <= 3 * bb and p <= 0.28:
                return self.do_call(obs)
            return self.do_fold(obs)
        # 4-bet+
        if p <= 0.015:
            return {"action": "allin"}
        if p <= 0.04 and to_call <= 0.2 * my_stack:
            return self.do_call(obs)
        return self.do_fold(obs)

    # ---------- postflop ----------
    def postflop(self, obs, hole, board):
        seat = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        to_call = obs["to_call"]
        pot = max(obs["pot"], 1)
        my_stack = stacks[seat]
        in_hand = obs["in_hand"]
        n_opp = len([s for s in in_hand if s != seat])
        street = obs["street_index"]
        hist = obs["history"]

        if len(hole) > 2:
            keep = quick_keep(hole, board)
        else:
            keep = hole
        eq = mc_equity(keep, board, n_opp, self.rng)
        if len(hole) > 2:
            eq = eq ** 1.15  # opponents still hold 3 cards on the flop

        st_raises = 0
        for h in hist:
            if h[0] == street and h[2] == "raise":
                st_raises += 1

        rng = self.rng
        if to_call <= 0:
            vt = max(0.42, 0.62 - 0.08 * (n_opp - 1))
            if eq >= vt:
                frac = 0.66 if street < 3 else (0.8 if eq > 0.8 else 0.55)
                amt = int(frac * pot)
                if my_stack <= 1.3 * pot:
                    return {"action": "allin"}
                return self.do_raise(obs, max(amt, obs["min_raise_to"]))
            # c-bet / bluff
            if n_opp == 1 and self.pf_aggr and street == 1 and rng.random() < 0.55:
                return self.do_raise(obs, int(0.5 * pot))
            if n_opp == 1 and street >= 2 and eq > 0.3 and rng.random() < 0.15:
                return self.do_raise(obs, int(0.5 * pot))
            return {"action": "check"}

        # facing a bet
        bet_frac = to_call / pot
        pen = 0.04 + 0.10 * min(bet_frac, 1.5) + 0.06 * max(0, st_raises - 1)
        eqa = eq - pen
        price = to_call / (pot + to_call)
        if eqa > 0.72 and obs["max_raise_to"] > 0:
            if my_stack <= 1.5 * (pot + to_call):
                return {"action": "allin"}
            return self.do_raise(obs, int(bets[seat] + to_call + (pot + to_call)))
        if eqa >= price:
            if to_call >= my_stack and eqa < price + 0.03:
                return self.do_fold(obs)
            return self.do_call(obs)
        return self.do_fold(obs)
