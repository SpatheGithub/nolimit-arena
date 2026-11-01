"""b01 PLO bot: exact made-hand strength vs random 2-card combos, draw outs,
heuristic preflop percentiles, pot-odds + aggression rules, short-stack commit."""

import random
from itertools import combinations
from collections import Counter

AGG_W = 1.2
PFR_W = 0.6
OPEN_MULT = 1.35
CALL_MULT = 1.3
K_BASE = 1.6
CBET = 0.95
VAL_TH = 0.80
SHORT_BB = 12
EQ_SCALE = 0.9
ICM_PREM = 0.04
W1 = 0.5
USE_EQ = 1
EXPLOIT = 1
SPR_COMMIT = 0.0
EARLY_F = 0.55
EARLY_K = 0.6
EARLY_BB = 40
POST_PREM = 0.0
WEAK_PAIR = 0.4
WEAK_2P = 0.7
RANKS = "23456789TJQKA"
SUITS = "cdhs"
CID = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
RK = [RANK_KEYS[c >> 2] for c in range(52)]
RB = [1 << (c >> 2) for c in range(52)]


def _eval5(rs, flush):
    cnt = Counter(rs)
    groups = sorted(cnt.items(), key=lambda x: (-x[1], -x[0]))
    distinct = sorted(set(rs), reverse=True)
    st = -1
    if len(distinct) == 5:
        if distinct[0] - distinct[4] == 4:
            st = distinct[0]
        elif distinct == [12, 3, 2, 1, 0]:
            st = 3
    if flush and st >= 0:
        cat, tb = 8, [st]
    elif groups[0][1] == 4:
        cat, tb = 7, [groups[0][0], groups[1][0]]
    elif groups[0][1] == 3 and groups[1][1] == 2:
        cat, tb = 6, [groups[0][0], groups[1][0]]
    elif flush:
        cat, tb = 5, distinct
    elif st >= 0:
        cat, tb = 4, [st]
    elif groups[0][1] == 3:
        cat, tb = 3, [g[0] for g in groups]
    elif groups[0][1] == 2 and groups[1][1] == 2:
        cat, tb = 2, [g[0] for g in groups]
    elif groups[0][1] == 2:
        cat, tb = 1, [g[0] for g in groups]
    else:
        cat, tb = 0, distinct
    v = cat << 20
    for i, r in enumerate(tb):
        v |= r << (4 * (4 - i))
    return v


RT = {}
for _combo in __import__("itertools").combinations_with_replacement(range(13), 5):
    if max(Counter(_combo).values()) > 4:
        continue
    RT[sum(RANK_KEYS[r] for r in _combo)] = _eval5(list(_combo), False)
FT = {}
for _combo in combinations(range(13), 5):
    FT[sum(1 << r for r in _combo)] = _eval5(list(_combo), True)

# straight windows as rank masks (ace-low included)
WINDOWS = [sum(1 << r for r in range(lo, lo + 5)) for lo in range(9)] + [(1 << 12) | 0b1111]


def popcount(x):
    return bin(x).count("1")


# ---------------- preflop heuristic ----------------
def pre_score(cards):
    ranks = [c >> 2 for c in cards]
    suits = [c & 3 for c in cards]
    score = 0.0
    cnt = Counter(ranks)
    for r, n in cnt.items():
        if n == 2:
            score += 7.0 + r * 1.25
        elif n == 3:
            score += 1.0 + r * 0.3
        elif n == 4:
            score -= 4.0
    scnt = Counter(suits)
    nsuited = 0
    for s, n in scnt.items():
        if n >= 2:
            top = max(r for r, su in zip(ranks, suits) if su == s)
            base = 3.0 + top * 0.45
            if n == 3:
                base *= 0.75
            elif n == 4:
                base *= 0.45
            score += base
            nsuited += 1
    d = sorted(set(ranks), reverse=True)
    for i in range(len(d)):
        for j in range(i + 1, len(d)):
            gap = d[i] - d[j]
            if gap <= 4:
                score += (5 - gap) * 0.85 * (1.0 if d[j] >= 3 else 0.8)
    if 12 in d:
        for r in d:
            if r <= 3 and r != 12:
                score += 0.4
    score += sum(max(0, r - 7) for r in ranks) * 0.75
    if len(d) == 4 and d[0] - d[3] <= 4:
        score += 2.0
    return score


def _build_pct():
    rng = random.Random(987654)
    deck = list(range(52))
    vals = []
    for _ in range(20000):
        vals.append(pre_score(rng.sample(deck, 4)))
    vals.sort()
    return vals


_PRE_VALS = _build_pct()
_N_PRE = len(_PRE_VALS)

import json as _json
import os as _os
from itertools import permutations as _perms

_PERMS = list(_perms(range(4)))
_EQ = {}
try:
    with open(_os.path.join(_os.path.dirname(__file__), "pre_eq.json")) as _f:
        for _k, _v in _json.load(_f).items():
            _EQ[tuple(int(x) for x in _k.split(","))] = (_v[0], _v[1], _v[2])
except Exception:
    _EQ = {}
_PCT = {}
_TOPAVG = [0.5] * 101
if _EQ:
    _tot = float(sum(v[2] for v in _EQ.values()))
    _ent = sorted(((v[0] / 0.076 * W1 + v[1] / 0.058 * (1 - W1), k, v[2]) for k, v in _EQ.items()), reverse=True)
    _cum = 0.0
    for _sc, _k, _c in _ent:
        _PCT[_k] = (_cum + _c / 2.0) / _tot
        _cum += _c
    _e1 = sorted(((v[0], v[2]) for v in _EQ.values()), reverse=True)
    _cum = 0.0
    _acc = 0.0
    _i = 1
    for _e, _c in _e1:
        _cum += _c
        _acc += _e * _c
        while _i <= 100 and _cum >= _tot * _i / 100.0:
            _TOPAVG[_i] = _acc / _cum
            _i += 1
    _TOPAVG[0] = _e1[0][0]


def canon(hole):
    best = None
    for p in _PERMS:
        t = tuple(sorted([(c >> 2) * 4 + p[c & 3] for c in hole]))
        if best is None or t < best:
            best = t
    return best


def pre_info(hole):
    """(percentile 0=best, eq1 vs random)"""
    k = canon(hole)
    v = _EQ.get(k)
    if v is None:
        p = pre_pct(hole)
        return p, 0.65 - 0.3 * p
    return _PCT[k], v[0]


def top_avg(R):
    i = int(R * 100)
    if i < 0:
        i = 0
    if i > 100:
        i = 100
    return _TOPAVG[i]


def pre_pct(cards):
    """fraction of random hands that score >= this hand (0 = best)."""
    s = pre_score(cards)
    lo, hi = 0, _N_PRE
    while lo < hi:
        mid = (lo + hi) // 2
        if _PRE_VALS[mid] < s:
            lo = mid + 1
        else:
            hi = mid
    return 1.0 - lo / _N_PRE


# ---------------- postflop evaluation ----------------
def board_triples(board):
    out = []
    for x, y, z in combinations(board, 3):
        s = x & 3
        fs = s if (y & 3) == s and (z & 3) == s else -2
        out.append((RK[x] + RK[y] + RK[z], fs, RB[x] | RB[y] | RB[z]))
    return out


def best_value(hole, triples):
    best = 0
    for a, b in combinations(hole, 2):
        hk = RK[a] + RK[b]
        hs = (a & 3) if (a & 3) == (b & 3) else -1
        hm = RB[a] | RB[b]
        for bk, bs, bm in triples:
            if hs == bs:
                v = FT[hm | bm]
            else:
                v = RT[hk + bk]
            if v > best:
                best = v
    return best


def beat_fraction(myv, hole, board, triples):
    """fraction of unseen 2-card combos that beat myv (ties half)."""
    seen = hole + board
    cnt = [4] * 13
    for c in seen:
        cnt[c >> 2] -= 1
    tks = [t[0] for t in triples]
    beat = 0.0
    rv = {}
    for a in range(13):
        ca = cnt[a]
        if ca == 0:
            continue
        ka = RANK_KEYS[a]
        for b in range(a, 13):
            if a == b:
                w = ca * (ca - 1) / 2
            else:
                w = ca * cnt[b]
            if w == 0:
                continue
            pk = ka + RANK_KEYS[b]
            v = max([RT[pk + tk] for tk in tks])
            rv[(a, b)] = v
            if v > myv:
                beat += w
            elif v == myv:
                beat += w * 0.5
    # flush combos
    sc = [0, 0, 0, 0]
    for c in board:
        sc[c & 3] += 1
    seenset = set(seen)
    for s in range(4):
        if sc[s] >= 3:
            ftr = [t[2] for t in triples if t[1] == s]
            unseen = [r for r in range(13) if (4 * r + s) not in seenset]
            for i in range(len(unseen)):
                x = unseen[i]
                for j in range(i + 1, len(unseen)):
                    y = unseen[j]
                    m = (1 << x) | (1 << y)
                    fv = max([FT[m | bm] for bm in ftr])
                    r0 = rv.get((x, y), 0)
                    if fv > r0 and fv > myv:
                        if r0 > myv:
                            continue
                        elif r0 == myv:
                            beat += 0.5
                        else:
                            beat += 1.0
                    elif fv > r0 and fv == myv and r0 < myv:
                        beat += 0.5
    n = 52 - len(seen)
    total = n * (n - 1) / 2
    return beat / total


def straight_ranks_possible(hole_mask, board_mask):
    """True if 2 hole ranks + 3 board ranks make a straight."""
    for w in WINDOWS:
        miss = w & ~board_mask
        nm = popcount(miss)
        if nm > 2:
            continue
        if miss & ~hole_mask:
            continue
        if nm == 2:
            return True
        hin = popcount(hole_mask & w)
        if nm == 1 and hin >= 2:
            return True
        if nm == 0 and hin >= 2:
            return True
    return False


def draw_info(hole, board):
    """outs for straight (by rank) and flush; nut-flush-draw flag."""
    hole_mask = 0
    for c in hole:
        hole_mask |= RB[c]
    board_mask = 0
    for c in board:
        board_mask |= RB[c]
    seen = set(hole + board)
    made_st = straight_ranks_possible(hole_mask, board_mask)
    st_outs = 0
    if not made_st:
        for r in range(13):
            if board_mask >> r & 1:
                continue
            if straight_ranks_possible(hole_mask, board_mask | (1 << r)):
                st_outs += sum(1 for s in range(4) if (4 * r + s) not in seen)
    fl_outs = 0
    nut_fd = False
    sc = [0, 0, 0, 0]
    for c in board:
        sc[c & 3] += 1
    for s in range(4):
        if sc[s] == 2:
            mine = [c >> 2 for c in hole if c & 3 == s]
            if len(mine) >= 2:
                fl_outs = max(fl_outs, 13 - 2 - len(mine) - sum(1 for c in board if False))
                fl_outs = 13 - sc[s] - len(mine)
                top_unseen = max(r for r in range(13) if (4 * r + s) not in seen)
                if max(mine) > top_unseen or max(mine) == 12:
                    nut_fd = True
                elif max(mine) >= 10:
                    nut_fd = nut_fd or False
    return st_outs, fl_outs, nut_fd


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.nseats = config.get("seats", 8)
        self.cache_key = None
        self.cache_val = None
        # opponent stats: seat -> [hands_dealt, vpip, pfr, aggr_actions, passive_actions]
        self.stats = {}

    # ---------------- helpers ----------------
    def order_from(self, start, seats):
        ss = sorted(seats)
        n = len(ss)
        idx = 0
        for i, s in enumerate(ss):
            if s >= start:
                idx = i
                break
        else:
            idx = 0
        return [ss[(idx + k) % n] for k in range(n)]

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs["legal"]:
                return {"action": "check"}
            return {"action": "fold"}

    def _raise(self, obs, amount):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if "raise" not in obs["legal"] and "bet" not in obs["legal"] or hi <= 0:
            if "call" in obs["legal"]:
                return {"action": "call"}
            return {"action": "check"}
        amt = int(max(lo, min(hi, amount)))
        act = "raise" if "raise" in obs["legal"] else "bet"
        return {"action": act, "amount": amt}

    def _passive(self, obs, want_call):
        if "check" in obs["legal"]:
            return {"action": "check"}
        if want_call and "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "fold"}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [CID[c] for c in obs["hole"]]
        board = [CID[c] for c in obs["board"]]
        if obs["street_index"] == 0 or len(board) < 3:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    # ---------------- preflop ----------------
    def preflop(self, obs, hole):
        me = self.seat
        bb = max(obs["bb"], 1)
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_stack = stacks[me]
        my_bet = bets[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        hist = obs["history"]
        if USE_EQ:
            pct, e1 = pre_info(hole)
        else:
            pct = pre_pct(hole)
            e1 = 0.65 - 0.3 * pct
        n_alive = len(alive)

        raises = 0
        limpers = 0
        for st, seat, a, amt in hist:
            if st != 0:
                continue
            if a == "raise":
                raises += 1
            elif a == "call" and raises == 0:
                limpers += 1
        # position: preflop order from left of BB
        order = self.order_from(obs["bb_seat"] + 1, alive) if n_alive > 2 else self.order_from(obs["button"], alive)
        pos = order.index(me) if me in order else 0
        behind = len(order) - 1 - pos
        # effective stack in bb
        others = [stacks[s] + bets[s] for s in in_hand if s != me]
        eff = min(my_stack + my_bet, max(others) if others else 0)
        eff_bb = eff / bb
        # tighten for multiway/full tables, loosen shorthanded
        short_handed = n_alive <= 4

        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        pot_after_call = pot + to_call
        # commit when stack small relative to pot
        commit_ratio = (my_stack) / max(pot_after_call, 1)

        if raises == 0:
            # unopened (maybe limpers)
            if behind >= 5:
                th = 0.13
            elif behind == 4:
                th = 0.17
            elif behind == 3:
                th = 0.22
            elif behind == 2:
                th = 0.32
            elif behind == 1:
                th = 0.38  # SB
            else:
                th = 0.10  # BB raise option
            if short_handed:
                th *= 1.3
            if n_alive <= 2:
                th = 0.60 if me != obs["bb_seat"] else 0.25
            if eff_bb < SHORT_BB:
                th = max(th, 0.30 if behind <= 2 else 0.22)
            th -= 0.02 * limpers
            th *= OPEN_MULT
            if bb <= EARLY_BB:
                th *= EARLY_F
            if EXPLOIT and limpers == 0 and 1 <= behind <= 3:
                vb = [self.vpip(s_) for s_ in order[pos + 1:]]
                if vb:
                    avg_v = sum(vb) / len(vb)
                    th *= min(1.6, max(0.8, 1.0 + (0.3 - avg_v) * 2.0))
            if pct <= th and can_raise:
                return self._raise(obs, obs["max_raise_to"])
            # limp/complete options
            if to_call == 0:
                return {"action": "check"}
            if me == obs["sb_seat"] and pct <= 0.55 and to_call <= bb / 2 + 1:
                return {"action": "call"}
            if limpers >= 1 and pct <= th + 0.10 and to_call <= bb:
                return {"action": "call"}
            return self._passive(obs, False)

        # facing raise(s)
        price = to_call / max(pot_after_call, 1)
        if to_call >= 0.35 * my_stack or (my_stack - to_call) <= pot_after_call * 0.7:
            # effectively an all-in decision: equity vs estimated range
            raiser = None
            for st, seat, a, amt in hist:
                if st == 0 and a == "raise":
                    raiser = seat
            R = self.pfr(raiser) * 1.3 if raiser is not None else 0.3
            if raises >= 2:
                R *= 0.5
            if raiser is not None and stacks[raiser] == 0:
                R *= 1.4  # all-in raisers (often short) are wider
            R = min(0.7, max(0.04, R))
            if USE_EQ:
                eq = 0.5 + EQ_SCALE * (e1 - top_avg(R))
            else:
                s_me = 0.17 * (1 - 2 * pct)
                s_r = 0.17 * (1 - R)
                eq = 0.5 + EQ_SCALE * (s_me - s_r)
            n_live = sum(1 for s in in_hand if s != me and (stacks[s] > 0 or bets[s] > 0))
            if n_live >= 2:
                eq *= 2.0 / (n_live + 1)
            risk_bust = to_call >= 0.8 * my_stack and max(others) >= my_stack + my_bet
            prem = ICM_PREM if risk_bust else ICM_PREM * 0.4
            if n_alive <= 4 and risk_bust:
                prem += 0.02
            if eq >= price + prem:
                if can_raise and eq >= price + prem + 0.06:
                    return self._raise(obs, obs["max_raise_to"])
                return {"action": "call"}
            return self._passive(obs, False)
        if raises == 1:
            three_th = 0.035 if not short_handed else 0.06
            if eff_bb < 15:
                three_th = 0.10
            call_th = 0.12 + (0.10 if me == obs["bb_seat"] else 0.0) + (0.05 if short_handed else 0.0)
            raiser = None
            for st, seat, a, amt in hist:
                if st == 0 and a == "raise":
                    raiser = seat
            if raiser is not None:
                fac = min(2.0, max(0.8, self.pfr(raiser) / 0.15)) ** PFR_W
                call_th *= fac
                three_th *= fac
            if price < 0.25:
                call_th += 0.06
            if to_call > 0.5 * my_stack:
                call_th = min(call_th, 0.10 if eff_bb > 12 else 0.22)
            call_th *= CALL_MULT
            if bb <= EARLY_BB:
                call_th *= EARLY_F
            if pct <= three_th and can_raise:
                return self._raise(obs, obs["max_raise_to"])
            if pct <= call_th:
                if commit_ratio < 1.0 and can_raise and pct <= call_th * 0.8:
                    return self._raise(obs, obs["max_raise_to"])
                return {"action": "call"}
            return self._passive(obs, False)
        # 2+ raises
        four_th = 0.02
        call_th = 0.05 if eff_bb > 15 else 0.10
        if to_call >= my_stack:
            call_th = 0.07 if eff_bb > 15 else 0.14
        if pct <= four_th and can_raise:
            return self._raise(obs, obs["max_raise_to"])
        if pct <= call_th:
            return {"action": "call"}
        return self._passive(obs, False)

    # ---------------- postflop ----------------
    def postflop(self, obs, hole, board):
        me = self.seat
        stacks = obs["stacks"]
        bets = obs["bets"]
        my_stack = stacks[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        in_hand = obs["in_hand"]
        hist = obs["history"]
        street = obs["street_index"]
        n_opp = max(1, len(in_hand) - 1)

        key = (tuple(hole), tuple(board))
        if self.cache_key == key:
            myv, bf, st_outs, fl_outs, nut_fd = self.cache_val
        else:
            triples = board_triples(board)
            myv = best_value(hole, triples)
            bf = beat_fraction(myv, hole, board, triples)
            if len(board) < 5:
                st_outs, fl_outs, nut_fd = draw_info(hole, board)
            else:
                st_outs, fl_outs, nut_fd = 0, 0, False
            self.cache_key = key
            self.cache_val = (myv, bf, st_outs, fl_outs, nut_fd)
        cat = myv >> 20
        # prob a random opponent 4-card hand is currently not ahead
        ahead1 = (1.0 - bf) ** 6
        # draw equity
        unseen = 52 - len(hole) - len(board)
        outs = min(st_outs + fl_outs, 20)
        if len(board) == 3:
            draw_eq = 1.0 - (1.0 - outs / unseen) * (1.0 - outs / (unseen - 1))
            vuln = 0.72
        elif len(board) == 4:
            draw_eq = outs / unseen
            vuln = 0.85
        else:
            draw_eq = 0.0
            vuln = 1.0
        draw_eq *= 0.8 if not nut_fd else 0.9
        # equity vs one random hand
        if ahead1 >= 0.5:
            eq1 = ahead1 * (vuln + (1 - vuln) * ahead1) + (1 - ahead1) * draw_eq
        else:
            eq1 = ahead1 * vuln + (1 - ahead1 * vuln) * draw_eq
        eq1 = min(max(eq1, 0.0), 1.0)

        # betting on this street
        raises = 0
        aggressor_pre = None
        for st, seat, a, amt in hist:
            if st == street and a == "raise":
                raises += 1
            if st == 0 and a == "raise":
                aggressor_pre = seat
        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        # position: last to act postflop?
        order = self.order_from(obs["button"] + 1, obs["alive"])
        live_order = [s for s in order if s in in_hand]
        in_pos = live_order[-1] == me if live_order else False

        if to_call == 0:
            # equity vs field (random hands)
            eqn = eq1 ** n_opp
            if (ahead1 ** n_opp) >= VAL_TH and cat >= 2:
                frac = 0.75 if ahead1 ** n_opp < 0.93 else 1.0
                return self._raise(obs, pot * frac)
            if eqn >= 0.62 and cat >= 2:
                return self._raise(obs, pot * 0.66)
            # low SPR: commit with decent equity
            if my_stack <= pot * SPR_COMMIT and eqn >= 0.42 + 0.04 * (n_opp - 1):
                return self._raise(obs, obs["max_raise_to"])
            # exploit frequent folders
            if n_opp <= 2 and EXPLOIT:
                fp = 1.0
                for s_ in in_hand:
                    if s_ != me:
                        fp *= self.ftb(s_)
                if fp >= 0.5 and self.rng.random() < min(0.85, fp + 0.15):
                    return self._raise(obs, pot * 0.6)
            # semi-bluff with strong draws
            if len(board) < 5 and draw_eq >= 0.30 and n_opp <= 2 and self.rng.random() < 0.6:
                return self._raise(obs, pot * 0.75)
            # c-bet heads-up as preflop aggressor
            if aggressor_pre == me and n_opp == 1 and len(board) == 3 and self.rng.random() < CBET:
                return self._raise(obs, pot * 0.5)
            if n_opp == 1 and in_pos and len(board) == 5 and eq1 < 0.15 and self.rng.random() < 0.15:
                return self._raise(obs, pot * 0.6)
            return {"action": "check"}

        # facing a bet
        pot_after = pot + to_call
        need = to_call / pot_after
        # range adjustment: bettors are stronger than random
        bet_frac = to_call / max(pot - to_call, 1)
        k = K_BASE + 0.6 * min(bet_frac, 1.5) + (EARLY_K if obs["bb"] <= EARLY_BB else 0.0) + 0.8 * (raises - 1)
        last_aggr = None
        for st, seat, a, amt in hist:
            if st == street and a == "raise":
                last_aggr = seat
        if last_aggr is not None:
            af = self.aggr(last_aggr)
            k *= min(1.4, max(0.55, 1.0 - (af - 0.33) * AGG_W))
        ahead_vs = ahead1 ** (k * (1 + (n_opp - 1) * 0.6))
        afb = self.aggr(last_aggr) if last_aggr is not None else 0.33
        tw = min(1.0, max(0.0, (afb - 0.2) / 0.3))
        if cat <= 1:
            ahead_vs *= WEAK_PAIR + (1.0 - WEAK_PAIR) * tw
        elif cat == 2 and len(set(c >> 2 for c in board)) < len(board):
            ahead_vs *= WEAK_2P + (1.0 - WEAK_2P) * tw
        if len(board) < 5:
            eq_vs = ahead_vs * vuln + (1 - ahead_vs * vuln) * draw_eq
        else:
            eq_vs = ahead_vs
        # all-in for less / committed adjustments
        if to_call >= my_stack:
            pass
        if ahead_vs >= 0.70 and can_raise and cat >= 3:
            return self._raise(obs, obs["max_raise_to"])
        prem = 0.0
        if to_call >= 0.5 * my_stack:
            for s_ in in_hand:
                if s_ != me and stacks[s_] + bets[s_] >= my_stack + bets[me]:
                    prem = POST_PREM
                    break
        if eq_vs >= need * 1.05 + prem:
            return {"action": "call"}
        return self._passive(obs, False)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur_st = -1
            facing = False
            for st, seat, a, amt in hist:
                if st != cur_st:
                    cur_st = st
                    facing = False
                if seat is None:
                    continue
                if seat == self.seat:
                    if a == "raise" and st >= 1:
                        facing = True
                    continue
                d = self.stats.get(seat)
                if d is None:
                    d = self.stats[seat] = [0, 0, 0, 0, 0, 0, 0]
                if seat not in seen:
                    seen.add(seat)
                    d[0] += 1
                if st == 0:
                    if a == "raise":
                        pr.add(seat)
                        vp.add(seat)
                    elif a == "call":
                        vp.add(seat)
                else:
                    if facing and a in ("fold", "call", "raise"):
                        d[5] += 1
                        if a == "fold":
                            d[6] += 1
                    if a == "raise":
                        d[3] += 1
                        facing = True
                    elif a in ("call", "check"):
                        d[4] += 1
            for seat in vp:
                self.stats[seat][1] += 1
            for seat in pr:
                self.stats[seat][2] += 1
        except Exception:
            pass

    def ftb(self, seat):
        d = self.stats.get(seat)
        if d is None:
            return 0.45
        return (d[6] + 1.35) / (d[5] + 3.0)

    def vpip(self, seat):
        d = self.stats.get(seat)
        if d is None:
            return 0.3
        return (d[1] + 1.2) / (d[0] + 4.0)

    def aggr(self, seat):
        d = self.stats.get(seat)
        if d is None:
            return 0.33
        return (d[3] + 1.0) / (d[3] + d[4] + 3.0)

    def pfr(self, seat):
        d = self.stats.get(seat)
        if d is None:
            return 0.15
        return (d[2] + 0.6) / (d[0] + 4.0)
