import os
import random
from itertools import combinations

import numpy as np

from .evalcore import CARD, SH, TOP5, value

_HERE = os.path.dirname(os.path.abspath(__file__))
_Z = np.load(os.path.join(_HERE, "ranktab.npz"))
VALS = {k: _Z["v%d" % k] for k in (3, 4, 5)}
INDEX = {}
for _k in (3, 4, 5):
    INDEX[_k] = {tuple(int(x) for x in row): i for i, row in enumerate(_Z["k%d" % _k])}
PAIRS = [(a, b) for a in range(13) for b in range(a, 13)]
PIDX = {}
for _i, (_a, _b) in enumerate(PAIRS):
    PIDX[(_a, _b)] = _i
    PIDX[(_b, _a)] = _i
PA = np.array([p[0] for p in PAIRS])
PB = np.array([p[1] for p in PAIRS])
SAME = PA == PB


def _next_rows(k):
    """For each board of size k, river-table rows for every rank runout and its multiplicity key."""
    out = []
    for key in _Z["k%d" % k]:
        key = tuple(int(x) for x in key)
        need = 5 - k
        rows = []
        runs = []
        if need == 1:
            for r in range(13):
                nk = tuple(sorted(key + (r,)))
                i = INDEX[5].get(nk)
                if i is not None:
                    rows.append(i)
                    runs.append((r,))
        else:
            for r1 in range(13):
                for r2 in range(r1, 13):
                    nk = tuple(sorted(key + (r1, r2)))
                    i = INDEX[5].get(nk)
                    if i is not None:
                        rows.append(i)
                        runs.append((r1, r2))
        out.append((np.array(rows, dtype=np.int64), runs))
    return out


NEXT = {3: _next_rows(3), 4: _next_rows(4)}

# preflop all-in equity: hero percentile bucket x villain percentile bucket (20 x 20), cumulative over villain
_PM = np.load(os.path.join(_HERE, "preeq.npy")).astype(np.float64)
PRE_CUM = (np.cumsum(_PM, axis=1) / np.arange(1, 21)[None, :]).tolist()


def eq_vs_range(pct, w):
    b = min(19, max(0, int(pct * 20)))
    k = min(19, max(0, int(w * 20 + 0.999) - 1))
    return PRE_CUM[b][k]


# ---------------------------------------------------------------- preflop score

def pre_score(hole):
    ranks = [c >> 2 for c in hole]
    suits = [c & 3 for c in hole]
    score = 0.0
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    for r, n in cnt.items():
        if n == 2:
            score += 1.5 + r * 0.65 + (4.0 if r == 12 else 2.0 if r == 11 else 1.0 if r == 10 else 0.0)
        elif n == 3:
            score += 1.0 + r * 0.25
        elif n == 4:
            score -= 4.0
    scnt = [0, 0, 0, 0]
    shigh = [-1, -1, -1, -1]
    for c in hole:
        s = c & 3
        scnt[s] += 1
        if c >> 2 > shigh[s]:
            shigh[s] = c >> 2
    nsuited = 0
    for s in range(4):
        if scnt[s] >= 2:
            nsuited += 1
            h = shigh[s]
            b = 2.0 + (2.5 if h == 12 else 1.2 if h == 11 else 0.6 if h == 10 else 0.0)
            if scnt[s] == 3:
                b *= 0.6
            elif scnt[s] == 4:
                b *= 0.3
            score += b
    distinct = sorted(cnt)
    if 12 in cnt:
        low_ace = [-1] + distinct
    else:
        low_ace = distinct
    conn = 0.0
    for i in range(len(distinct)):
        for j in range(i + 1, len(distinct)):
            d = distinct[j] - distinct[i]
            if d <= 4:
                w = (2.2, 1.8, 1.3, 0.8)[d - 1]
                if distinct[i] < 3 and distinct[j] < 8:
                    w *= 0.8
                conn += w
    if 12 in cnt:
        for r in distinct:
            if r <= 3:
                conn += 0.5
    score += min(conn, 11.0)
    for r in ranks:
        if r >= 8:
            score += (r - 7) * 0.35
    # danglers: a card far from all others and unpaired
    for r in distinct:
        if cnt[r] == 1:
            near = any(abs(r - o) <= 4 for o in distinct if o != r)
            if not near and r < 10:
                score -= 1.0
    return score


def _calib():
    rng = random.Random(12345)
    deck = list(range(52))
    xs = []
    for _ in range(6000):
        h = rng.sample(deck, 4)
        xs.append(pre_score(h))
    xs.sort()
    return xs


_PRE_SORTED = _calib()
_NPRE = len(_PRE_SORTED)


def pre_pct(hole):
    """0 = best hand, 1 = worst."""
    import bisect
    s = pre_score(hole)
    i = bisect.bisect_right(_PRE_SORTED, s)
    return 1.0 - i / _NPRE


# ---------------------------------------------------------------- postflop

def _ncomb(avail):
    a = np.array(avail, dtype=np.float64)
    na = a[PA]
    nb = a[PB]
    return np.where(SAME, na * (na - 1) / 2.0, na * nb)


def analyze(hole, board):
    """Equity estimate vs one random 4-card hand, current made value and category, flush draw info."""
    k = len(board)
    bkey = tuple(sorted(c >> 2 for c in board))
    idx = INDEX[k][bkey]
    row = VALS[k][idx]
    hr = [c >> 2 for c in hole]
    hp = sorted({PIDX[(hr[i], hr[j])] for i in range(4) for j in range(i + 1, 4)})
    my_nf = int(row[hp].max())
    avail = [4] * 13
    for c in hole:
        avail[c >> 2] -= 1
    for c in board:
        avail[c >> 2] -= 1
    cw = _ncomb(avail)
    unseen = 52 - 4 - k
    total = unseen * (unseen - 1) / 2.0

    bsuit = [0, 0, 0, 0]
    for c in board:
        bsuit[c & 3] += 1
    hsuit = [0, 0, 0, 0]
    for c in hole:
        hsuit[c & 3] += 1
    fs = max(range(4), key=lambda s: bsuit[s])
    bmax = bsuit[fs]

    # our made flush now?
    my = my_nf
    if bmax >= 3 and hsuit[fs] >= 2:
        hs = [c for c in hole if c & 3 == fs]
        bs = [c for c in board if c & 3 == fs]
        for h2 in combinations(hs, 2):
            for b3 in combinations(bs, 3):
                v = value(list(h2) + list(b3))
                if v > my:
                    my = v
    cat = my >> 20

    # current strength vs random 2-card combos
    beat = float(cw[row > my].sum())
    tie = float(cw[row == my].sum())
    # opponent flush combos (current board)
    opp_flush_frac = 0.0
    if bmax >= 3:
        seen = set(hole) | set(board)
        rem = [c for c in range(fs, 52, 4) if c not in seen]
        bsr = sorted((c >> 2 for c in board if c & 3 == fs), reverse=True)
        top3 = 0
        for r in bsr[:3]:
            top3 |= 1 << r
        nf = 0
        for x, y in combinations(rem, 2):
            nf += 1
            fv = SH[5] | TOP5[top3 | 1 << (x >> 2) | 1 << (y >> 2)]
            if fv > my and row[PIDX[(x >> 2, y >> 2)]] <= my:
                beat += 1
        opp_flush_frac = nf / total
    p_now = min(1.0, (beat + 0.5 * tie) / total)
    eq_now = (1.0 - p_now) ** 6

    if k == 5 or cat >= 5:
        # river, or made flush+: current strength (minus small vulnerability)
        eq = eq_now
        if k < 5 and cat == 5:
            eq *= 0.93 if bkey_paired(bkey) else 0.97
        return eq, eq_now, cat, 0.0, my

    # lookahead over rank runouts for non-flush part
    rows_idx, runs = NEXT[k][idx]
    R = VALS[5][rows_idx]  # (n_runs, 91)
    myv = R[:, hp].max(axis=1)
    beatr = ((R > myv[:, None]) * cw).sum(axis=1) + 0.5 * ((R == myv[:, None]) * cw).sum(axis=1)
    pr = np.minimum(1.0, beatr / total)
    eqr = (1.0 - pr) ** 6
    # weights for runouts
    if k == 4:
        w = np.array([avail[r[0]] for r in runs], dtype=np.float64)
    else:
        w = np.array([avail[a] * avail[b] if a != b else avail[a] * (avail[a] - 1) / 2.0 for a, b in runs],
                     dtype=np.float64)
    ws = w.sum()
    eq_nf = float((eqr * w).sum() / ws) if ws > 0 else eq_now
    mycat_future = float(((myv >> 20) >= 6).astype(np.float64).dot(w) / ws) if ws > 0 else 0.0

    # flush world
    ctc = 5 - k
    rem_cards = unseen
    eq = eq_nf
    fdraw = 0.0
    best_s = -1
    best_p = 0.0
    for s in range(4):
        need = 3 - bsuit[s]
        u = 13 - bsuit[s] - hsuit[s]
        if need <= 0:
            p = 1.0
        elif need > ctc:
            p = 0.0
        elif need == 1 and ctc == 1:
            p = u / rem_cards
        elif need == 1:
            p = 1.0 - (rem_cards - u) * (rem_cards - u - 1) / (rem_cards * (rem_cards - 1))
        else:
            p = u * (u - 1) / (rem_cards * (rem_cards - 1))
        if p > best_p:
            best_p = p
            best_s = s
    if best_s >= 0 and best_p > 0:
        s = best_s
        if hsuit[s] >= 2:
            # our flush draw: nutness by unseen higher suited ranks
            seen = set(hole) | set(board)
            myhi = max(c >> 2 for c in hole if c & 3 == s)
            higher = sum(1 for r in range(myhi + 1, 13) if (r * 4 + s) not in seen)
            feq = (0.93, 0.82, 0.72, 0.62, 0.55)[min(higher, 4)]
            if bkey_paired(bkey):
                feq *= 0.9
            fdraw = best_p
            eq = (1 - best_p) * eq_nf + best_p * max(feq, eq_nf)
        else:
            if bmax >= 3:
                f = (1.0 - opp_flush_frac) ** 6
            else:
                f = 0.80
            # full houses are immune
            imm = mycat_future
            eq = (1 - best_p) * eq_nf + best_p * eq_nf * (imm + (1 - imm) * f)
    return eq, eq_now, cat, fdraw, my


def bkey_paired(bkey):
    return len(set(bkey)) < len(bkey)


# ---------------------------------------------------------------- agent

P = {"open_mult": 1.0, "pf_bb": 14, "spr_commit": 1.8, "commit_eq": 0.15, "val_eq": 0.2, "bluff": 1.0,
     "call_add": 0.0, "push_add": 0.08, "call_narrow": 0.92, "pf_open_bb": 0.0, "eq_def": 0, "call_mult": 1.0, "icm": 0.03, "icm_mid": 0.0, "raise_eq": 0.72}

class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]
        n = config.get("seats", 8) + 2
        self.n = n
        # opponent stats
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.pagg = [0] * 16   # postflop bets/raises
        self.ppas = [0] * 16   # postflop checks/calls
        self.fold_vs = [0] * 16
        self.face = [0] * 16
        self.wtsd = [0] * 16
        self.cache_key = None
        self.cache_val = None

    # ------------------------------------------------------------ stats
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            for st, seat, act, amt in hist:
                if seat is None or seat < 0 or seat >= 16:
                    continue
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    if act == "raise":
                        self.pagg[seat] += 1
                    elif act in ("check", "call"):
                        self.ppas[seat] += 1
            # fold vs bet: per street, if a raise happened before a player's fold
            facing = set()
            last_st = -1
            for st, seat, act, amt in hist:
                if st != last_st:
                    facing = set()
                    last_st = st
                if seat is None or seat < 0 or seat >= 16:
                    continue
                if st > 0:
                    if act == "raise":
                        facing = {"x"}
                    elif facing and act in ("fold", "call", "raise"):
                        self.face[seat] += 1
                        if act == "fold":
                            self.fold_vs[seat] += 1
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass

    def vp(self, s):
        return (self.vpip[s] + 2.0) / (self.hands[s] + 5.0)

    def pf(self, s):
        return (self.pfr[s] + 1.0) / (self.hands[s] + 5.0)

    def af(self, s):
        return (self.pagg[s] + 3.0) / (self.pagg[s] + self.ppas[s] + 6.0)

    def fv(self, s):
        return (self.fold_vs[s] + 2.0) / (self.face[s] + 5.0)

    # ------------------------------------------------------------ helpers
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def _raise(self, obs, target):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            t = int(target)
            lo, hi = obs["min_raise_to"], obs["max_raise_to"]
            if t < lo:
                t = lo
            if t > hi:
                t = hi
            return {"action": "raise", "amount": t}
        return self._call(obs)

    def _call(self, obs):
        if obs["to_call"] == 0 or "call" not in obs["legal"]:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return {"action": "call"}

    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _pot(self, obs, frac):
        me = obs["seat"]
        mybet = obs["bets"][me]
        tc = obs["to_call"]
        target = mybet + tc + frac * (obs["pot"] + tc)
        stack = obs["stacks"][me]
        if stack + mybet - target < 0.3 * (obs["pot"] + 2 * (target - mybet)):
            target = obs["max_raise_to"]
        return self._raise(obs, target)

    # ------------------------------------------------------------ decide
    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs["n_discard"]])}
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if not board:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    def ctx(self, obs):
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        bb = obs["bb"] or 1
        my_total = stacks[me] + bets[me]
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_total, other)
        return me, opps, bb, eff

    def preflop(self, obs, hole):
        me, opps, bb, eff = self.ctx(obs)
        pct = pre_pct(hole)
        hist = obs["history"]
        raises = 0
        raisers = []
        limpers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises += 1
                raisers.append(seat)
            elif act == "call":
                limpers += 1
        alive = obs["alive"]
        n_alive = len(alive)
        # players yet to act behind me preflop
        bbs = obs["bb_seat"]
        if bbs in alive:
            j = (alive.index(bbs) + 1) % n_alive
            order = alive[j:] + alive[:j]
        else:
            order = alive
        if n_alive == 2:
            btn = obs["button"]
            order = [btn] + [s for s in alive if s != btn]
        i = order.index(me) if me in order else 0
        behind = len([s for s in order[i + 1:] if s in obs["in_hand"]])
        to_call = obs["to_call"]
        pot = obs["pot"]
        eff_bb = eff / bb
        stack = obs["stacks"][me]
        can_check = "check" in obs["legal"]
        # tournament pressure: fewer players -> looser
        loosen = (8 - n_alive) * 0.025

        if eff_bb <= P["pf_bb"]:
            return self.pushfold(obs, pct, raises, behind, eff_bb, n_alive, raisers)

        if raises == 0:
            if can_check:
                # BB option
                if pct <= 0.08:
                    return self._pot(obs, 1.0)
                return {"action": "check"}
            th = {0: 0.40, 1: 0.36, 2: 0.30, 3: 0.24, 4: 0.19, 5: 0.15}.get(behind, 0.13) * P["open_mult"] + loosen
            # steal more vs tight blinds
            if behind <= 2:
                ftight = np.mean([1.0 - self.vp(s) for s in order[i + 1:]]) if order[i + 1:] else 0.6
                th += 0.12 * (ftight - 0.6)
            if limpers:
                th += 0.03
            if pct <= th:
                return self._pot(obs, 1.0 if limpers == 0 else 0.8)
            if limpers and pct <= th + 0.10:
                return self._call(obs)
            if obs["sb_seat"] == me and pct <= th + 0.15 and limpers == 0:
                return self._call(obs)
            return self._fold(obs)

        # facing raise(s)
        r = raisers[-1]
        rloose = self.pf(r)
        odds = to_call / (pot + to_call)
        if raises == 1:
            three = 0.035 + (0.03 if rloose > 0.3 else 0.0) + loosen * 0.5
            if pct <= three:
                return self._pot(obs, 1.0)
            call_th = 0.13 + (0.06 if obs["bb_seat"] == me else 0.0) + (0.04 if behind == 0 else 0.0)
            call_th += 0.15 * max(0.0, rloose - 0.2) + loosen
            if to_call > 0.25 * stack:
                call_th *= 0.6
            if odds < 0.2:
                call_th += 0.05
            call_th *= P["call_mult"]
            if pct <= call_th:
                return self._call(obs)
            # short-handed / blind defense: price the call with the equity matrix
            cold = limpers > 0
            if P["eq_def"] and not cold and (n_alive <= 3 or obs["bb_seat"] == me) and to_call <= 0.3 * stack:
                rng_w = min(0.85, 0.15 + 1.2 * rloose + loosen)
                eq = eq_vs_range(pct, rng_w)
                ip = obs["bb_seat"] == me and r == obs["sb_seat"]
                real = 0.92 if ip else 0.82
                if eq * real >= odds + 0.02 and pct <= (0.8 if n_alive <= 2 else 0.6):
                    return self._call(obs)
            return self._fold(obs)
        # 3bet+
        four = 0.015 + (0.02 if rloose > 0.35 else 0.0)
        if pct <= four:
            return self._pot(obs, 1.0)
        if pct <= 0.05 + (0.04 if rloose > 0.35 else 0.0) and to_call <= 0.35 * stack:
            return self._call(obs)
        if pct <= 0.08 and odds < 0.3:
            return self._call(obs)
        return self._fold(obs)

    def pushfold(self, obs, pct, raises, behind, eff_bb, n_alive, raisers):
        me = obs["seat"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        can_check = "check" in obs["legal"]
        stack = obs["stacks"][me]
        if raises == 0:
            if can_check:
                if pct <= 0.25:
                    return self._raise(obs, obs["max_raise_to"])
                return {"action": "check"}
            # open-shove ranges, wider when shorter and fewer behind
            th = 0.22 + 0.06 * max(0, 5 - behind) + 0.012 * max(0.0, 14 - eff_bb)
            if n_alive <= 3:
                th += 0.1
            th = min(th + P["push_add"], 0.8)
            if pct <= th:
                return self._raise(obs, obs["max_raise_to"])
            if obs["sb_seat"] == me and pct <= th + 0.15:
                return self._call(obs)
            return self._fold(obs)
        # facing a raise: call/reraise all-in with equity margin
        odds = to_call / (pot + to_call)
        r = raisers[-1]
        rl = self.pf(r)
        # approximate equity vs raiser range by percentile
        rng_w = min(0.8, 0.15 + 1.2 * rl)
        if raises >= 2:
            rng_w *= 0.6
        if obs["stacks"][r] == 0 and to_call <= 0.5 * pot:
            rng_w = max(rng_w, 0.5)
        eq = eq_vs_range(pct, rng_w)
        # extra players already in the pot cut our equity
        hist = obs["history"]
        seen_raise = False
        others = set()
        for st, seat, act, amt in hist:
            if st != 0 or seat == me:
                continue
            if act == "raise":
                seen_raise = True
                others.add(seat)
            elif act == "call" and seen_raise:
                others.add(seat)
        extra = max(0, len(others) - 1)
        if extra:
            eq *= 0.72 ** extra
        need = odds + 0.03 + P["call_add"] + self.risk(obs, r)
        if eq >= need or pct <= 0.06:
            if obs["max_raise_to"] > 0 and pct <= 0.2:
                return self._raise(obs, obs["max_raise_to"])
            return self._call(obs)
        return self._fold(obs)

    def postflop(self, obs, hole, board):
        me, opps, bb, eff = self.ctx(obs)
        key = (obs["hand_id"], len(board))
        if self.cache_key == key:
            eq, eq_now, cat, fdraw, my = self.cache_val
        else:
            eq, eq_now, cat, fdraw, my = analyze(hole, board)
            self.cache_key = key
            self.cache_val = (eq, eq_now, cat, fdraw, my)
        street = obs["street_index"]
        hist = obs["history"]
        to_call = obs["to_call"]
        pot = obs["pot"]
        stack = obs["stacks"][me]
        can_check = "check" in obs["legal"]
        # opponent ranges
        pre_raiser = -1
        vol = set()
        for st, seat, act, amt in hist:
            if st == 0 and act == "raise":
                pre_raiser = seat
            if st == 0 and act in ("call", "raise"):
                vol.add(seat)
        st_raises = {}
        st_size = {}
        prev_aggr = set()
        prev_call = {}
        level = 0
        pot_before = pot - sum(obs["bets"])
        run_pot = pot_before
        for st, seat, act, amt in hist:
            if st == street and act == "raise":
                st_raises[seat] = st_raises.get(seat, 0) + 1
                # size of this raise relative to the pot it faced
                st_size[seat] = max(0, amt - level) / max(1.0, run_pot + level)
                level = max(level, amt)
                run_pot += amt
            elif st == street and act == "call":
                run_pot += level
            elif 0 < st < street and act == "raise":
                prev_aggr.add(seat)
            elif 0 < st < street and act == "call":
                prev_call[seat] = prev_call.get(seat, 0) + 1
        total_raises = sum(st_raises.values())
        stacks_now = obs["stacks"]
        eq_r = 1.0
        for s in opps:
            t = 0.6 if s in vol else 0.8
            if s == pre_raiser:
                t = 0.5
            if s in prev_aggr:
                t *= 0.85 + 0.25 * self.af(s)
            nc = prev_call.get(s, 0)
            if nc:
                t *= P["call_narrow"] ** nc
            nr = st_raises.get(s, 0)
            if nr:
                a = self.af(s)
                m = min(0.9, 0.45 + 0.6 * a) if nr == 1 else min(0.65, 0.25 + 0.5 * a)
                b = st_size.get(s, 1.0)
                soft = max(0.0, min(0.8, 1.0 - b / 0.7))
                m = m + (1.0 - m) * soft
                t *= m
                if stacks_now[s] == 0 and b < 0.5:
                    t = max(t, 0.6 if b > 0.25 else 0.8)
            t = max(0.08, min(1.0, t))
            eq_r *= eq ** (1.0 / t)
        n_opp = len(opps)
        spr = stack / max(pot, 1)

        if to_call > 0:
            odds = to_call / (pot + to_call)
            # implied/realization tweaks
            need = odds
            if street < 3 and fdraw > 0:
                need -= 0.03
            if total_raises >= 2:
                need += 0.04
            if odds < 0.2:
                need = min(need, odds * 0.85)
            if to_call >= 0.5 * stack and odds >= 0.2:
                bettor = max(opps, key=lambda s: obs["bets"][s])
                need += self.risk(obs, bettor)
            # value raise
            if eq_r >= P["raise_eq"] and (eq_now >= P["raise_eq"] + 0.03 or street == 3):
                return self._pot(obs, 1.0)
            if eq_r >= need + (0.02 if odds >= 0.2 else 0.0):
                # semi-bluff raise with strong draws when heads-up, deep
                if street == 1 and fdraw > 0 and eq >= 0.6 and n_opp == 1 and total_raises == 1 and self.rng.random() < 0.3:
                    return self._pot(obs, 1.0)
                return self._call(obs)
            return self._fold(obs)

        # checked to us / first to act
        # value bet
        val_eq = eq_r
        if spr <= P["spr_commit"] and n_opp <= 2 and val_eq >= P["commit_eq"] * (1.0 if n_opp == 1 else 0.7):
            return self._pot(obs, 1.0)
        if val_eq >= P["val_eq"] or (eq_now >= 0.85 and val_eq >= 0.5):
            frac = 0.75 if street < 3 else 0.7
            if eq_now >= 0.9:
                frac = 1.0
            return self._pot(obs, frac)
        # semi-bluff with draws
        if street < 3 and fdraw > 0 and eq >= 0.55 and n_opp <= 2 and self.rng.random() < 0.5:
            return self._pot(obs, 0.66)
        # bluff / c-bet based on fold rates
        if n_opp <= 2:
            fold_p = 1.0
            for s in opps:
                fold_p *= self.fv(s)
            is_pfr = pre_raiser == me
            last_to_act = self._last_to_act(obs, opps)
            bluff_ok = fold_p > 0.45 and (is_pfr or last_to_act)
            if street == 1 and is_pfr and n_opp == 1:
                bluff_ok = bluff_ok or fold_p > 0.35
            if bluff_ok and eq < 0.5 and self.rng.random() < P["bluff"]:
                return self._pot(obs, 0.6)
        return {"action": "check"}

    def risk(self, obs, villain):
        """ICM-style extra equity needed to call off a large part of our stack."""
        k = P["icm"]
        if not k:
            return 0.0
        n = len(obs["alive"])
        if n <= 2:
            return 0.0
        me = obs["seat"]
        mine = obs["stacks"][me] + obs["bets"][me]
        his = obs["stacks"][villain] + obs["bets"][villain]
        f = 1.0 if n >= 4 else 0.7
        if his < mine:
            f *= 0.3
        return k * f + (P["icm_mid"] if n >= 5 and his >= mine else 0.0)

    def _last_to_act(self, obs, opps):
        alive = obs["alive"]
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in obs["in_hand"]]
        return bool(live) and live[-1] == obs["seat"]
