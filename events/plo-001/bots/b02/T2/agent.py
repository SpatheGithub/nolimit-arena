"""b02 PLO bot: nut-aware postflop via precomputed rank tables, heuristic
preflop percentiles, stack-depth/push-fold logic, light opponent model."""

import bisect
import json
import os
import random
from itertools import combinations

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: (i, j) for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}

# ---------------------------------------------------------------- evaluator
WINDOWS = []  # (mask, top)
for _t in range(4, 13):
    WINDOWS.append((sum(1 << r for r in range(_t - 4, _t + 1)), _t))
WINDOWS.append(((1 << 12) | 0b1111, 3))
WINDOWS.sort(key=lambda x: -x[1])


def _stop(mask):
    for w, t in WINDOWS:
        if mask & w == w:
            return t
    return -1


def _pack(lst):
    v = 0
    for r in lst:
        v = v << 4 | r
    return v << 4 * (5 - len(lst))


def _eval_nf(rs):
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    if len(cnt) == 5:
        m = 0
        for r in rs:
            m |= 1 << r
        t = _stop(m)
        if t >= 0:
            return 4 << 20 | t << 16
        return _pack(sorted(rs, reverse=True))
    g = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if g[0][1] >= 5:
        return 0
    if g[0][1] == 4:
        return 7 << 20 | _pack([g[0][0], g[1][0]])
    if g[0][1] == 3:
        if g[1][1] == 2:
            return 6 << 20 | _pack([g[0][0], g[1][0]])
        return 3 << 20 | _pack([g[0][0], g[1][0], g[2][0]])
    if g[1][1] == 2:
        return 2 << 20 | _pack([g[0][0], g[1][0], g[2][0]])
    return 1 << 20 | _pack([g[0][0], g[1][0], g[2][0], g[3][0]])


FL = {}
for _c in combinations(range(13), 5):
    _m = sum(1 << r for r in _c)
    _t = _stop(_m)
    FL[_m] = (8 << 20 | _t << 16) if _t >= 0 else (5 << 20 | _pack(sorted(_c, reverse=True)))

TRI_IDX = {}
_rows = []
for _a in range(13):
    for _b in range(_a, 13):
        for _c in range(_b, 13):
            TRI_IDX[(_a, _b, _c)] = len(_rows)
            row = [0] * 169
            for _r1 in range(13):
                for _r2 in range(_r1, 13):
                    v = _eval_nf([_a, _b, _c, _r1, _r2])
                    row[_r1 * 13 + _r2] = v
                    row[_r2 * 13 + _r1] = v
            _rows.append(row)
NF = np.array(_rows, dtype=np.int64)
del _rows
UPPER = np.zeros((13, 13), dtype=bool)
for _a in range(13):
    for _b in range(_a + 1, 13):
        UPPER[_a, _b] = True


def analyze(hole, board):
    """hole, board: lists of (rank, suit). Returns dict with my value,
    fraction of unseen 2-card combos that beat/tie me, outs info."""
    nb = len(board)
    tris = list(combinations(board, 3))
    idx = [TRI_IDX[tuple(sorted((a[0], b[0], c[0])))] for a, b, c in tris]
    best = NF[idx].max(axis=0)  # (169,)
    bsuit = [0, 0, 0, 0]
    for r, s in board:
        bsuit[s] += 1
    fsuit = -1
    for s in range(4):
        if bsuit[s] >= 3:
            fsuit = s
    # my value
    V = 0
    hp = list(combinations(hole, 2))
    for a, b in hp:
        v = int(best[a[0] * 13 + b[0]])
        if v > V:
            V = v
    if fsuit >= 0:
        stris = [t for t in tris if t[0][1] == fsuit and t[1][1] == fsuit and t[2][1] == fsuit]
        smasks = [(1 << t[0][0]) | (1 << t[1][0]) | (1 << t[2][0]) for t in stris]
        for a, b in hp:
            if a[1] == fsuit and b[1] == fsuit:
                hm = (1 << a[0]) | (1 << b[0])
                for m in smasks:
                    v = FL[m | hm]
                    if v > V:
                        V = v
    # unseen counts
    seen = set(hole) | set(board)
    cnt = np.full(13, 4, dtype=np.int64)
    for r, s in seen:
        cnt[r] -= 1
    W = np.outer(cnt, cnt)
    W = np.where(UPPER, W, 0)
    W[np.arange(13), np.arange(13)] = cnt * (cnt - 1) // 2
    best2 = best.reshape(13, 13)
    beat = int(W[best2 > V].sum())
    tie = int(W[best2 == V].sum())
    n_un = 52 - len(seen)
    total = n_un * (n_un - 1) // 2
    if fsuit >= 0:
        us = [r for r in range(13) if (r, fsuit) not in seen]
        for i in range(len(us)):
            for j in range(i + 1, len(us)):
                hm = (1 << us[i]) | (1 << us[j])
                fv = 0
                for m in smasks:
                    v = FL[m | hm]
                    if v > fv:
                        fv = v
                nfv = int(best2[us[i], us[j]])
                if fv > nfv:
                    if nfv <= V < fv:
                        beat += 1
                        if nfv == V:
                            tie -= 1
                    elif fv == V and nfv < V:
                        tie += 1
    fb = beat / total
    ft = tie / total
    # draws (flop/turn)
    outs = 0
    nut_draw = 0
    if nb < 5:
        # flush draws
        for s in range(4):
            if bsuit[s] == nb - 1 or (nb == 3 and bsuit[s] == 2) or (nb == 4 and bsuit[s] == 2):
                pass
            if bsuit[s] == 2 and fsuit < 0:
                mine = [r for r, ss in hole if ss == s]
                if len(mine) >= 2:
                    unseen_s = [r for r in range(13) if (r, s) not in seen]
                    fo = len(unseen_s)
                    outs += fo
                    if unseen_s and max(mine) > max(unseen_s):
                        nut_draw += 2
                    elif unseen_s and max(mine) >= 10:
                        nut_draw += 1
        # straight draws
        bm = 0
        for r, s in board:
            bm |= 1 << r
        hpm = [(1 << a[0]) | (1 << b[0]) for a, b in hp if a[0] != b[0]]
        cur_top = -1
        if V >> 20 == 4:
            cur_top = (V >> 16) & 15
        so = 0
        for r in range(13):
            if bm >> r & 1 or cnt[r] == 0:
                continue
            bm2 = bm | 1 << r
            my_top = -1
            for w, t in WINDOWS:
                if t <= my_top:
                    break
                for h in hpm:
                    if h & w == h and (w & ~h) & ~bm2 == 0:
                        my_top = t
                        break
            if my_top > cur_top and my_top >= 0:
                nut_top = -1
                for w, t in WINDOWS:
                    if bin(w & bm2).count("1") >= 3:
                        nut_top = t
                        break
                so += int(cnt[r]) * (1.0 if my_top >= nut_top else 0.5)
        outs += so
    return V, fb, ft, outs, nut_draw, fsuit, bsuit


# ---------------------------------------------------------------- preflop
def pre_score(hole):
    rs = [c[0] for c in hole]
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    score = 0.0
    for r, n in cnt.items():
        if n == 2:
            score += 5.0 + r * 0.85
        elif n == 3:
            score += 1.0 + r * 0.25
        elif n == 4:
            score -= 3.0
    by = {}
    for r, s in hole:
        by.setdefault(s, []).append(r)
    suited_cards = set()
    for s, lst in by.items():
        if len(lst) >= 2:
            top = max(lst)
            score += 2.5 + (3.0 if top == 12 else 1.5 if top == 11 else 0.8 if top == 10 else 0.3 * (top >= 8))
            if len(lst) == 3:
                score -= 1.5
            elif len(lst) == 4:
                score -= 3.5
            for r in lst:
                suited_cards.add((r, s))
    d = sorted(cnt, reverse=True)
    dl = list(d)
    if 12 in cnt:
        dl_low = [-1] + [x for x in d if x != 12]
    conn = {r: 0 for r in d}
    for i in range(len(d)):
        for j in range(i + 1, len(d)):
            g = d[i] - d[j]
            w = 2.0 if g == 1 else 1.5 if g == 2 else 0.8 if g == 3 else 0.2 if g == 4 else 0.0
            if w:
                score += w
                conn[d[i]] += 1
                conn[d[j]] += 1
    if len(d) == 4 and d[0] - d[3] <= 4:
        score += 2.5
    elif len(d) >= 3 and d[0] - d[-1] <= 4:
        score += 0.8
    score += sum(max(0, r - 7) for r in rs) * 0.5
    # danglers
    for r, s in hole:
        if cnt[r] == 1 and conn[r] == 0 and (r, s) not in suited_cards:
            score -= 2.0 if r < 12 else 0.8
    # small cards
    score -= 0.4 * sum(1 for r in rs if r <= 2)
    return score


def _build_pct():
    rng = random.Random(20261031)
    deck = [(r, s) for r in range(13) for s in range(4)]
    xs = sorted(pre_score(rng.sample(deck, 4)) for _ in range(12000))
    return xs


PRE_SORTED = _build_pct()


def _load_table():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre_pct.json")) as f:
            # floats only: a dict of str -> float is not tracked by the garbage collector
            return {k: float(v[0]) for k, v in json.load(f).items()}
    except Exception:
        return {}


# canonical (suit-isomorphic) hand key -> [percentile by MC equity vs a random hand, equity]
PRE_TABLE = _load_table()


def canon(cards):
    by = {}
    for r, s in cards:
        by.setdefault(s, []).append(r)
    groups = [tuple(sorted(v, reverse=True)) for v in by.values()]
    groups.sort(key=lambda g: (len(g), g), reverse=True)
    return "|".join("".join(RANKS[r] for r in g) for g in groups)


def pre_pct(hole):
    e = PRE_TABLE.get(canon(hole))
    if e is not None:
        return e
    x = pre_score(hole)
    return bisect.bisect_left(PRE_SORTED, x) / len(PRE_SORTED)


def icm_equity(stacks, payouts):
    """Malmuth-Harville expected payout per player (same as the referee's)."""
    n = len(stacks)
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    paid = max((k + 1 for k, p in enumerate(pay) if p), default=0)
    if paid == 0:
        return [0.0] * n
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


# ---------------------------------------------------------------- agent
class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        self.stats = {}  # seat -> [hands, vpip, pfr, aggr, passive, fold_to_bet, faced_bet]
        self.pre_cache = None
        self.last_hand = -1

    # ------------------------------------------------------------ stats
    def _st(self, s):
        st = self.stats.get(s)
        if st is None:
            st = self.stats[s] = [0, 0, 0, 0, 0, 0, 0]
        return st

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen_pre = set()
            vp = set()
            pr = set()
            for st_i, seat, act, amt in hist:
                if seat == self.seat:
                    continue
                if act in ("sb", "bb", "ante", "return", "discard"):
                    if act in ("sb", "bb"):
                        seen_pre.add(seat)
                    continue
                seen_pre.add(seat)
                if st_i == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    s = self._st(seat)
                    if act == "raise":
                        s[3] += 1
                    elif act in ("call", "check"):
                        s[4] += 1
            # fold to bets: approximate via sequence
            facing = {}
            for st_i, seat, act, amt in hist:
                if st_i == 0 or seat == self.seat:
                    continue
                if act == "fold":
                    s = self._st(seat)
                    s[5] += 1
                    s[6] += 1
                elif act in ("call", "raise") and st_i > 0:
                    pass
            for seat in seen_pre:
                s = self._st(seat)
                s[0] += 1
                if seat in vp:
                    s[1] += 1
                if seat in pr:
                    s[2] += 1
        except Exception:
            pass

    def vpip(self, s):
        st = self.stats.get(s)
        if not st or st[0] < 6:
            return 0.3
        return (st[1] + 1.0) / (st[0] + 3.0)

    def pfr(self, s):
        st = self.stats.get(s)
        if not st or st[0] < 6:
            return 0.15
        return (st[2] + 0.5) / (st[0] + 3.0)

    def aggr(self, s):
        st = self.stats.get(s)
        if not st:
            return 0.35
        return (st[3] + 1.0) / (st[3] + st[4] + 3.0)

    # ------------------------------------------------------------ helpers
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", ()):
                return {"action": "check"}
            return {"action": "fold"}

    def _raise(self, obs, to):
        legal = obs["legal"]
        if ("raise" not in legal and "bet" not in legal) or obs["max_raise_to"] <= 0:
            return self._call(obs)
        to = int(to)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        me = obs["seat"]
        stack = obs["stacks"][me] + obs["bets"][me]
        # if leftover would be small relative to the pot, go max
        if stack - to < 0.35 * (obs["pot"] + 2 * to):
            to = hi
        to = max(lo, min(hi, to))
        return {"action": "raise", "amount": to}

    def _pot_to(self, obs, frac):
        me = obs["seat"]
        cur = obs["bets"][me] + obs["to_call"]
        return cur + frac * (obs["pot"] + obs["to_call"])

    def _call(self, obs):
        if obs["to_call"] == 0 or "call" not in obs["legal"]:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return {"action": "call"}

    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def icm_need(self, obs, to_call, villain):
        """Equity needed to call an all-in under ICM (<= 4 alive), or None."""
        alive = obs["alive"]
        n = len(alive)
        if n > 4 or n < 3 or villain is None or villain < 0:
            return None
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        if not (to_call >= stacks[me] or stacks[villain] == 0):
            return None
        pot = obs["pot"]
        call = min(to_call, stacks[me])
        excess = to_call - call  # returned to the villain when we're all-in for less
        base = {s: stacks[s] for s in alive}
        fold = dict(base)
        fold[villain] += pot  # villain takes the pot (incl. any uncalled part)
        win = dict(base)
        win[me] = stacks[me] + pot - excess
        win[villain] += excess
        lose = dict(base)
        lose[me] = stacks[me] - call
        lose[villain] += pot + call
        pts = list(self.points[:n])
        i = alive.index(me)
        ef = icm_equity([fold[s] for s in alive], pts)[i]
        ew = icm_equity([win[s] for s in alive], pts)[i]
        el = icm_equity([lose[s] for s in alive], pts)[i]
        if ew - el <= 1e-9:
            return None
        return max(0.0, min(1.0, (ef - el) / (ew - el)))

    def icm_margin(self, obs, risk_frac):
        """Extra equity needed for risking a big part of the stack."""
        alive = obs["alive"]
        n = len(alive)
        if risk_frac < 0.3:
            return 0.0
        base = {8: 0.02, 7: 0.03, 6: 0.035, 5: 0.04, 4: 0.05, 3: 0.05, 2: 0.0}.get(n, 0.03)
        return base * min(1.0, risk_frac)

    # ------------------------------------------------------------ main
    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if not board:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    # ------------------------------------------------------------ preflop
    def preflop(self, obs, hole):
        me = obs["seat"]
        bb = obs["bb"] or 1
        stacks, bets = obs["stacks"], obs["bets"]
        pct = pre_pct(hole)
        hist = obs["history"]
        raises = 0
        limpers = 0
        raiser = -1
        for st_i, seat, act, amt in hist:
            if st_i != 0:
                continue
            if act == "raise":
                raises += 1
                raiser = seat
                limpers = 0
            elif act == "call":
                limpers += 1
        alive = obs["alive"]
        in_hand = obs["in_hand"]
        n = len(alive)
        # players behind me preflop
        bbs = obs["bb_seat"]
        if n == 2:
            btn = obs["button"]
            order = [btn] + [s for s in alive if s != btn]
        else:
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand]
        nb = len(behind)
        my_stack = stacks[me] + bets[me]
        opps = [s for s in in_hand if s != me]
        eff = min(my_stack, max([stacks[s] + bets[s] for s in opps], default=0))
        eff_bb = eff / bb
        to_call = obs["to_call"]
        pot = obs["pot"]
        is_bb = me == bbs

        # open thresholds (fraction of hands to play) by players behind
        open_top = {0: 0.6, 1: 0.45, 2: 0.38, 3: 0.28, 4: 0.23, 5: 0.19, 6: 0.16, 7: 0.14}.get(nb, 0.14)
        if n <= 4:
            open_top += 0.06
        # loose/tight table adjustment: blinds who fold a lot -> steal more
        if nb <= 2 and behind:
            fold_rate = sum(1 - self.vpip(s) for s in behind) / len(behind)
            open_top += 0.15 * (fold_rate - 0.7)
        if n == 2:
            open_top = max(open_top, 0.72)
        elif n == 3:
            open_top += 0.08
        short = eff_bb <= 12

        if raises == 0:
            if to_call == 0:  # BB option (limped) or everyone folded to... can check
                if pct >= 1 - 0.18 and obs["max_raise_to"] > 0:
                    return self._raise(obs, self._pot_to(obs, 1.0 if short else 0.75))
                return {"action": "check"}
            if limpers == 0:
                top = open_top + (0.05 if short else 0.0)
                if pct >= 1 - top:
                    return self._raise(obs, self._pot_to(obs, 1.0))
                if me == obs["sb_seat"] and not short and pct >= (0.12 if n == 2 else 0.55):
                    return self._call(obs)
                return self._fold(obs)
            # limpers ahead
            if pct >= 1 - open_top * 0.8:
                return self._raise(obs, self._pot_to(obs, 1.0))
            if pct >= 1 - min(0.35, open_top + 0.05) and to_call <= bb and not short:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        raise_to = max(bets)
        rv = self.vpip(raiser) if raiser >= 0 else 0.3
        rp = self.pfr(raiser) if raiser >= 0 else 0.15
        # the raiser's range width (fraction of hands), from observed raise frequency
        if raises == 1:
            rng_w = 0.10 + 0.8 * max(0.0, rp - 0.1) + 0.2 * max(0.0, rv - 0.3)
            rng_w = min(0.8, max(0.06, rng_w))
        else:
            rng_w = min(0.6, max(0.03, rp * 0.55))
        # equity vs range: compress percentile gap
        opp_center = 1 - rng_w / 2
        eq = 0.5 + 0.30 * (pct - opp_center) / max(0.1, 1 - opp_center + 0.05) * 0.5
        eq = 0.5 + 0.32 * (pct - opp_center)
        eq = max(0.30, min(0.68, eq))
        if len(opps) >= 2:
            eq *= 0.92 ** (len(opps) - 1)
        pot_after = pot + to_call
        odds = to_call / max(1, pot_after)
        risk = to_call / max(1, my_stack)
        committed = to_call >= 0.4 * my_stack
        my_in = bets[me]
        start_stack = my_stack
        # already invested a big part of the stack: don't fold to a shove
        if my_in >= 0.3 * start_stack and odds <= 0.42:
            return self._call(obs)
        # 3bet / 4bet (re-raise pot) with top hands
        if eff_bb <= 20:
            reraise_cut = 1 - max(0.06, min(0.22, rng_w * 0.45))
        elif eff_bb <= 40:
            reraise_cut = 1 - max(0.03, min(0.08, rng_w * 0.25))
        else:
            reraise_cut = 0.975 if raises == 1 else 0.99
        if raises >= 2 and eff_bb > 20:
            reraise_cut = max(reraise_cut, 0.99)
        if n == 2 and raises == 1:
            reraise_cut = min(reraise_cut, 0.80 if eff_bb <= 20 else 0.88 if eff_bb <= 40 else 0.93)
        if pct >= reraise_cut and obs["max_raise_to"] > 0:
            return self._raise(obs, self._pot_to(obs, 1.0))
        need = odds + self.icm_margin(obs, risk)
        icm_req = self.icm_need(obs, to_call, raiser)
        if icm_req is not None:
            need = icm_req
        if committed:
            # deep all-in preflop: PLO equities run close, demand a real edge
            if eff_bb > 30:
                need = max(need, 0.5)
            if eq >= need:
                return self._call(obs)
            return self._fold(obs)
        # implied odds / playability for flat calls
        if raises == 1:
            call_top = 0.10 + (0.12 if is_bb else 0.0) + (0.04 if nb == 0 else 0.0)
            if n == 2:
                call_top = 0.55 if is_bb else 0.45
            elif n == 3:
                call_top += 0.12
            if to_call <= 2 * bb:
                call_top += 0.1
            if risk > 0.15:
                call_top *= 0.6
            if pct >= 1 - call_top and eq >= need - 0.05:
                return self._call(obs)
            return self._fold(obs)
        # facing 3bet+
        floor = 0.72 if eff_bb > 25 else 0.6
        if pct >= max(floor, 1 - max(0.03, rng_w * 0.9)) and eq >= need + 0.03:
            return self._call(obs)
        if odds <= 0.2 and pct >= 0.85:
            return self._call(obs)
        return self._fold(obs)

    # ------------------------------------------------------------ postflop
    def postflop(self, obs, hole, board):
        me = obs["seat"]
        V, fb, ft, outs, nut_draw, fsuit, bsuit = analyze(hole, board)
        nb = len(board)
        rel1 = max(0.0, 1.0 - fb - 0.5 * ft) ** 6  # vs one random 4-card hand
        stacks, bets = obs["stacks"], obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        n_opp = max(1, len(opps))
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        bb = obs["bb"] or 1
        # draw equity
        unseen = 52 - 4 - nb
        if nb == 3:
            p_hit = 1 - (1 - outs / unseen) * (1 - outs / (unseen - 1))
        elif nb == 4:
            p_hit = outs / unseen
        else:
            p_hit = 0.0
        p_hit = min(0.75, p_hit)
        # vulnerability of made hands to future cards
        wet = 0.0
        if nb < 5:
            if max(bsuit) == 2:
                wet += 0.10
            if max(bsuit) >= 3:
                wet += 0.05
            bm = 0
            for r, s in board:
                bm |= 1 << r
            conn = max(bin((bm >> lo) & 0x1F).count("1") for lo in range(9))
            if conn >= 2:
                wet += 0.05 * (conn - 1)
            if nb == 4:
                wet *= 0.6
        hist = obs["history"]
        st_idx = obs["street_index"]
        # aggression this street
        raises = 0
        aggressor = -1
        for h_st, seat, act, amt in hist:
            if h_st == st_idx and act == "raise":
                raises += 1
                aggressor = seat
        # who was the last aggressor preflop / previous street
        prev_aggr = -1
        prev_bets = {}  # seat -> postflop streets (before this one) where it bet/raised
        called_streets = set()  # earlier postflop streets with a bet that got called
        for h_st, seat, act, amt in hist:
            if h_st < st_idx and act == "raise":
                prev_aggr = seat
                if h_st >= 1:
                    prev_bets[seat] = prev_bets.get(seat, 0) + 1
            if 1 <= h_st < st_idx and act == "call":
                called_streets.add(h_st)
        i_was_aggr = prev_aggr == me

        if to_call == 0:
            # checked to me / first to act: value vs the range that will call
            q_c = 0.85 * 0.8 ** len(called_streets)
            if nb == 5:
                q_c *= 0.9
            win_c = max(0.0, min(1.0, (rel1 - (1 - q_c)) / q_c))
            eq_now = win_c ** n_opp
            strength = eq_now * (1 - wet) + (1 - eq_now * (1 - wet)) * p_hit * 0.9
            # low SPR: commit with any reasonable piece or draw (not on the river)
            if nb < 5 and my_stack <= 0.8 * pot and n_opp <= 2 and (
                    strength >= 0.3 or outs >= 6 or rel1 >= 0.6):
                return self._raise(obs, obs["max_raise_to"])
            # value bet
            if fb < 0.004 and rel1 > 0.9:
                frac = 1.0 if nb < 5 or n_opp == 1 else 0.85
                return self._raise(obs, self._pot_to(obs, frac))
            if strength >= 0.6:
                return self._raise(obs, self._pot_to(obs, 0.75))
            if strength >= 0.48 and n_opp == 1:
                return self._raise(obs, self._pot_to(obs, 0.6))
            # semibluff with strong draws
            if nb < 5 and (outs >= 12 or (nut_draw >= 2 and outs >= 8)) and n_opp <= 2:
                return self._raise(obs, self._pot_to(obs, 0.75))
            # c-bet bluff heads-up
            if i_was_aggr and n_opp == 1 and nb == 3:
                opp = opps[0]
                fold_like = 1 - self.vpip(opp)
                if self.rng.random() < 0.35 + 0.4 * (fold_like - 0.6) and (rel1 > 0.3 or outs >= 4):
                    return self._raise(obs, self._pot_to(obs, 0.55))
            # everyone checked to us (we act last): passive fields fold a lot -> stab
            live = [s for s in opps if stacks[s] > 0]
            checked = {seat for h_st, seat, act, amt in hist if h_st == st_idx and act == "check"}
            if live and all(s in checked for s in live):
                tight = sum(1 - self.vpip(s) for s in live) / len(live)
                if nb < 5:
                    p = {1: 0.5, 2: 0.3}.get(len(live), 0.15) + 0.5 * (tight - 0.7)
                    if self.rng.random() < p and (rel1 > 0.15 or outs >= 4):
                        return self._raise(obs, self._pot_to(obs, 0.5))
                elif len(live) == 1 and rel1 < 0.35:
                    if self.rng.random() < 0.3 + 0.5 * (tight - 0.7):
                        return self._raise(obs, self._pot_to(obs, 0.6))
            return {"action": "check"}

        # facing a bet
        bet_frac = to_call / max(1, pot - to_call)
        q = 0.40 if bet_frac < 0.6 else 0.28
        if raises >= 2:
            q = 0.08
        if raises >= 3:
            q = 0.04
        a = self.aggr(aggressor) if aggressor >= 0 else 0.35
        q *= 0.5 + 1.4 * min(a, 0.9)  # aggressive players bet wider
        q *= 0.8 ** prev_bets.get(aggressor, 0)  # multi-street aggression narrows
        if nb == 5:
            q *= 0.85
        q = max(0.02, min(0.85, q))
        win = (rel1 - (1 - q)) / q
        win = max(0.0, min(1.0, win))
        # part of a betting range is bluffs / weak hands
        bl = 0.06 + 0.5 * max(0.0, a - 0.3)
        if raises >= 2:
            bl *= 0.4
        if bet_frac < 0.35:
            bl += 0.1
        bl = min(0.45, bl)
        win = bl * min(1.0, rel1 + 0.35) + (1 - bl) * win
        eq = win * (1 - wet * 0.8) + (1 - win * (1 - wet * 0.8)) * p_hit * 0.85
        # others still in (callers or yet to act) reduce equity
        if n_opp >= 2:
            eq *= rel1 ** (0.5 * (n_opp - 1))
        pot_after = pot + to_call
        odds = to_call / pot_after
        risk = to_call / max(1, my_stack + 0)
        need = odds + self.icm_margin(obs, risk)
        icm_req = self.icm_need(obs, to_call, aggressor)
        if icm_req is not None:
            need = icm_req
        if eq >= 0.72 and obs["max_raise_to"] > 0:
            return self._raise(obs, self._pot_to(obs, 1.0))
        if eq >= need:
            return self._call(obs)
        return self._fold(obs)


# Import-time tables are read-only: keep them out of garbage-collector scans so a
# collection triggered during act() stays cheap.
try:
    import gc as _gc

    _gc.freeze()
except Exception:
    pass
