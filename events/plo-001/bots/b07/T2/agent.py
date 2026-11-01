"""b07 PLO bot: table-driven Omaha evaluation, opponent-pair enumeration for
made-hand strength, bitmask draw outs, heuristic preflop with position,
short-stack commitment logic, per-seat opponent stats."""

import bisect
import random
from itertools import combinations

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}


# ---------------------------------------------------------------- evaluation

def _pack(rs):
    v = 0
    for r in rs:
        v = v << 4 | r
    return v << 4 * (5 - len(rs))


_WIN = [(t, 0b11111 << (t - 4)) for t in range(12, 3, -1)] + [(3, (1 << 12) | 0b1111)]


def _stop(m):
    for t, w in _WIN:
        if m & w == w:
            return t
    return -1


def _ev5(rs):
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(cnt.items(), key=lambda t: (-t[1], -t[0]))
    shape = [c for _, c in groups]
    order = [r for r, _ in groups]
    if len(shape) == 5:
        m = 0
        for r in rs:
            m |= 1 << r
        t = _stop(m)
        if t >= 0:
            return 4 << 20 | t << 16
        return _pack(order)
    if shape[0] >= 4:
        return 7 << 20 | _pack(order)
    if shape[0] == 3:
        return (6 if shape[1] == 2 else 3) << 20 | _pack(order)
    if shape[1] == 2:
        return 2 << 20 | _pack(order)
    return 1 << 20 | _pack(order)


V2 = np.zeros(169 * 2197, dtype=np.int32)
for _a in range(13):
    for _b in range(_a, 13):
        _pi = (_a * 13 + _b) * 2197
        for _c in range(13):
            for _d in range(_c, 13):
                for _e in range(_d, 13):
                    V2[_pi + _c * 169 + _d * 13 + _e] = _ev5((_a, _b, _c, _d, _e))
V2L = V2.tolist()

SUITED = [0] * 8192
for _m in range(8192):
    if bin(_m).count("1") == 5:
        _t = _stop(_m)
        if _t >= 0:
            SUITED[_m] = 8 << 20 | _t << 16
        else:
            SUITED[_m] = 5 << 20 | _pack([r for r in range(12, -1, -1) if _m >> r & 1])
SUITED_NP = np.array(SUITED, dtype=np.int32)

_pa, _pb = [], []
for _x in range(52):
    for _y in range(_x + 1, 52):
        _pa.append(_x)
        _pb.append(_y)
PA = np.array(_pa, dtype=np.int64)
PB = np.array(_pb, dtype=np.int64)
_ra, _rb = PA >> 2, PB >> 2
P_IDX = (np.minimum(_ra, _rb) * 13 + np.maximum(_ra, _rb)) * 2197
P_SUIT = np.where((PA & 3) == (PB & 3), PA & 3, -1)
P_MASK = (np.left_shift(1, _ra) | np.left_shift(1, _rb)).astype(np.int64)


def _tidx(t):
    a, b, c = sorted((t[0] >> 2, t[1] >> 2, t[2] >> 2))
    return a * 169 + b * 13 + c


def _pidx(a, b):
    ra, rb = a >> 2, b >> 2
    if ra > rb:
        ra, rb = rb, ra
    return (ra * 13 + rb) * 2197


def hero_value(hole, board):
    best = -1
    pairs = [(a, b) for a, b in combinations(hole, 2)]
    for t in combinations(board, 3):
        tk = _tidx(t)
        s = t[0] & 3
        mono = (t[1] & 3) == s and (t[2] & 3) == s
        tm = (1 << (t[0] >> 2)) | (1 << (t[1] >> 2)) | (1 << (t[2] >> 2))
        for a, b in pairs:
            if mono and (a & 3) == s and (b & 3) == s:
                v = SUITED[tm | (1 << (a >> 2)) | (1 << (b >> 2))]
            else:
                v = V2L[_pidx(a, b) + tk]
            if v > best:
                best = v
    return best


def opp_values(dead_cards, board):
    dead = np.zeros(52, dtype=bool)
    dead[dead_cards] = True
    ok = ~(dead[PA] | dead[PB])
    idx = P_IDX[ok]
    trips = list(combinations(board, 3))
    tk = np.array([_tidx(t) for t in trips], dtype=np.int64)
    vals = V2[idx[:, None] + tk[None, :]]
    ps = pm = None
    for j, t in enumerate(trips):
        s = t[0] & 3
        if (t[1] & 3) == s and (t[2] & 3) == s:
            if ps is None:
                ps = P_SUIT[ok]
                pm = P_MASK[ok]
            rows = np.nonzero(ps == s)[0]
            if rows.size:
                tm = (1 << (t[0] >> 2)) | (1 << (t[1] >> 2)) | (1 << (t[2] >> 2))
                vals[rows, j] = SUITED_NP[pm[rows] | tm]
    return vals.max(axis=1)


def omaha_straight_top(hm, bm):
    for t, w in _WIN:
        need = w & ~bm
        if need & ~hm:
            continue
        if bin(need).count("1") > 2:
            continue
        if bin(w & hm).count("1") < 2:
            continue
        return t
    return -1


def nut_straight_top(bm):
    for t, w in _WIN:
        if bin(w & bm).count("1") >= 3:
            return t
    return -1


def draw_outs(hole, board):
    """Effective outs (nut-weighted) for flush and straight draws."""
    outs = 0.0
    hs = [0, 0, 0, 0]
    bs = [0, 0, 0, 0]
    htop = [-1, -1, -1, -1]
    seen = set(hole) | set(board)
    for c in hole:
        hs[c & 3] += 1
        if c >> 2 > htop[c & 3]:
            htop[c & 3] = c >> 2
    for c in board:
        bs[c & 3] += 1
    flush_outs = 0
    for s in range(4):
        if hs[s] >= 2 and bs[s] == 2:
            n = 13 - hs[s] - bs[s]
            top_missing = -1
            for r in range(12, -1, -1):
                if (4 * r + s) not in board and (4 * r + s) not in hole:
                    top_missing = r
                    break
            if htop[s] > top_missing:
                q = 1.0
            elif htop[s] >= 10:
                q = 0.55
            else:
                q = 0.3
            outs += n * q
            flush_outs = n
    hm = 0
    for c in hole:
        hm |= 1 << (c >> 2)
    bm = 0
    for c in board:
        bm |= 1 << (c >> 2)
    paired = bin(bm).count("1") < len(board)
    cur = omaha_straight_top(hm, bm)
    so = 0.0
    for r in range(13):
        if bm >> r & 1:
            continue
        nb = bm | 1 << r
        t = omaha_straight_top(hm, nb)
        if t > cur:
            n = 4 - sum(1 for c in hole if c >> 2 == r)
            if t >= nut_straight_top(nb):
                so += n
            else:
                so += 0.45 * n
    if flush_outs:
        so *= 0.75
    if paired:
        so *= 0.6
    outs += so
    return min(outs, 20.0)


# ---------------------------------------------------------------- preflop

W1 = [0.40105, -0.04071, -0.02649, -0.01351, -1e-05, 0.00329, 0.00979, 0.01504, 0.01953, 0.03033, 0.02922, 0.03162, 0.03963, 0.05292, -0.0419, -0.02145, 0.00085, 0.01916, 0.04087, 0.0591, 0.07917, 0.09445, 0.12382, 0.13502, 0.15492, 0.18213, 0.21451, -0.0122, -0.15083, 0.00278, 0.04278, 0.02203, 0.01172, 0.00019, 0.0, 0.01013, 0.01193, 0.01213, 0.00777, 0.00821, 0.00509, 0.00914, 0.0065, 0.00869, 0.0136, 0.01387, 0.01242, 0.00398, 0.00431, 0.00661, 0.00542, 0.0043, 0.00022, 0.00408, -0.00656, -0.00423, -0.00833, 0.0058]


def _feats(hole):
    ranks = [c >> 2 for c in hole]
    suits = [c & 3 for c in hole]
    cnt = [0] * 13
    for r in ranks:
        cnt[r] += 1
    f = [0.0] * 58
    f[0] = 1.0
    for r in range(13):
        if cnt[r] == 1:
            f[1 + r] += 1
        elif cnt[r] == 2:
            f[14 + r] = 1
        elif cnt[r] == 3:
            f[27] = 1
            f[1 + r] += 1
        elif cnt[r] == 4:
            f[28] = 1
    npairs = sum(1 for r in range(13) if cnt[r] == 2)
    if npairs == 2:
        f[29] = 1
    sc = [suits.count(s) for s in range(4)]
    g2 = sum(1 for k in sc if k == 2)
    if g2 == 2:
        f[30] = 1
    elif g2 == 1:
        f[31] = 1
    if 3 in sc:
        f[32] = 1
    if 4 in sc:
        f[33] = 1
    for s in range(4):
        if sc[s] >= 2:
            top = max(ranks[i] for i in range(4) if suits[i] == s)
            f[34 + top] += 1
    d = sorted(set(ranks))
    best = 0
    for lo in range(-1, 9):
        wn = sum(1 for r in d if lo <= r <= lo + 4 or (lo == -1 and r == 12))
        if wn > best:
            best = wn
    if best == 4:
        f[47] = 1
    elif best == 3:
        f[48] = 1
    elif best == 2:
        f[49] = 1
    for i in range(len(d)):
        for j in range(i + 1, len(d)):
            g = d[j] - d[i]
            if g == 1:
                f[50] += 1
            elif g == 2:
                f[51] += 1
            elif g == 3:
                f[52] += 1
    if 12 in d:
        for r in d:
            if r <= 3:
                f[53] += 1
    dang = 0
    for i, r in enumerate(ranks):
        if cnt[r] > 1 or sc[suits[i]] > 1:
            continue
        if all(abs(r - o) >= 4 for o in d if o != r):
            dang += 1
    f[54] = dang
    f[55] = min(d) if d else 0
    f[56] = 1.0 if (npairs == 1 and cnt[12] == 2) and g2 >= 1 else 0.0
    f[57] = 1.0 if cnt[12] == 2 and best >= 3 else 0.0
    return f, best, g2


def pre_eval(hole):
    """(equity vs one random hand, playability score)."""
    f, best, g2 = _feats(hole)
    e = 0.0
    for a, b in zip(W1, f):
        e += a * b
    play = e + (0.02 if best == 4 else 0.008 if best == 3 else 0.0) + (0.01 if g2 == 2 else 0.0)
    return e, play


def _build_pct():
    rng = random.Random(7)
    deck = list(range(52))
    xs = []
    for _ in range(12000):
        xs.append(pre_eval(rng.sample(deck, 4))[1])
    xs.sort()
    return xs


_PCT = _build_pct()


def pre_pct(hole):
    e, p = pre_eval(hole)
    return e, bisect.bisect_left(_PCT, p) / len(_PCT)


OPEN_HU, OPEN_3, OPEN_4 = 0.3, 0.45, 0.5
DEF_HU, DEF_3, DEF_4 = 0.35, 0.5, 0.58
BLUFF_F = 0.45
CHECK_M = 0.8
VAL_M, VAL_HU = 0.6, 0.52
RIVER_K = 2
STATION_F, STATION_THIN = 0.3, 0.06
LIMP = False
SB_COMPLETE = 0.6
DEF_FULL = 0.08
SEMI_F = 0.3
RISK_BASE = {3: 0.07, 4: 0.1, 5: 0.12}
FOLD_PRIOR = 0.42
CALL1 = 0.84


# ---------------------------------------------------------------- agent

class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.n = config.get("seats", 8)
        self.hands = [0] * 16
        self.vpip = [0] * 16
        self.pfr = [0] * 16
        self.agg = [0] * 16
        self.pas = [0] * 16
        self.ftb_f = [0] * 16
        self.ftb_c = [0] * 16
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])

    # ---------------- safe actions
    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _call(self, obs):
        if obs["to_call"] == 0:
            return {"action": "check"}
        return {"action": "call"}

    def _raise(self, obs, amount):
        legal = obs["legal"]
        if not ("raise" in legal or "bet" in legal) or obs["max_raise_to"] <= 0:
            return self._call(obs)
        a = int(amount)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        return {"action": "raise", "amount": a}

    def _pot(self, obs, frac):
        me = obs["seat"]
        bet = obs["bets"][me]
        stack = obs["stacks"][me]
        tc = obs["to_call"]
        pot = obs["pot"]
        target = bet + tc + frac * (pot + tc)
        if stack + bet - target < 0.3 * (pot + 2 * (target - bet)):
            target = obs["max_raise_to"]
        return self._raise(obs, target)

    def _risk(self, obs):
        """ICM risk premium on the equity needed to call, scaled by the share
        of our stack at risk (full-stack flips need ~0.6 with 4+ players)."""
        n = len(obs["alive"])
        if n <= 2:
            return 0.0
        base = RISK_BASE[min(n, 5)]
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        s = stacks[me]
        tc = obs["to_call"]
        if s <= 0 or tc <= 0:
            return 0.0
        r = min(1.0, tc / s)
        mine = s + bets[me]
        big = max([stacks[o] + bets[o] for o in obs["in_hand"] if o != me] or [0])
        if big < mine:
            r *= big / mine
        return base * r

    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return self._fold(obs)

    # ---------------- opponent model
    def _aggr(self, s):
        return (self.agg[s] + 1.0) / (self.agg[s] + self.pas[s] + 3.0)

    def _pfr(self, s):
        return (self.pfr[s] + 0.6) / (self.hands[s] + 3.0)

    def _fold_rate(self, s):
        return (self.ftb_f[s] + FOLD_PRIOR * 3.0) / (self.ftb_f[s] + self.ftb_c[s] + 3.0)

    def _vpip(self, s):
        return (self.vpip[s] + 1.0) / (self.hands[s] + 3.0)

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            v = set()
            p = set()
            cur_st = -1
            bet_on = False
            for st, seat, act, amt in hist:
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0:
                    if act in ("call", "raise"):
                        v.add(seat)
                    if act == "raise":
                        p.add(seat)
                else:
                    if act == "raise":
                        self.agg[seat] += 1
                    elif act in ("call", "check"):
                        self.pas[seat] += 1
                    if st != cur_st:
                        cur_st = st
                        bet_on = False
                    if bet_on:
                        if act == "fold":
                            self.ftb_f[seat] += 1
                        elif act in ("call", "raise"):
                            self.ftb_c[seat] += 1
                    if act == "raise":
                        bet_on = True
            for s in seen:
                if s < 16:
                    self.hands[s] += 1
            for s in v:
                self.vpip[s] += 1
            for s in p:
                self.pfr[s] += 1
        except Exception:
            pass

    # ---------------- decision
    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs["n_discard"]])}
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs)

    def preflop(self, obs):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        eqr, pct = pre_pct(hole)
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        stack = stacks[me]
        mybet = bets[me]
        opps = [s for s in in_hand if s != me]
        eff = min(stack + mybet, max([stacks[s] + bets[s] for s in opps] or [0]))
        eff_bb = eff / bb
        tc = obs["to_call"]
        pot = obs["pot"]
        hist = obs["history"]
        raises = 0
        limpers = 0
        raiser = -1
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act == "raise":
                raises += 1
                raiser = seat
            elif act == "call" and raises == 0:
                limpers += 1
        n = len(alive)
        # position: players acting after me preflop
        btn = obs["button"]
        bbs = obs["bb_seat"]
        if n == 2:
            order = [btn, [s for s in alive if s != btn][0]] if btn in alive else alive
        else:
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = n - 1 - i
        short_table = n <= 4
        stack_frac_call = tc / max(1, stack)

        if raises == 0:
            if tc == 0:
                # big blind, limped pot
                if pct >= 0.9 or (short_table and pct >= 0.8):
                    return self._raise(obs, obs["max_raise_to"])
                return {"action": "check"}
            # open or iso
            thr = {0: 0.6, 1: 0.58, 2: 0.6, 3: 0.66, 4: 0.72}.get(behind, 0.76)
            if n == 2:
                thr = OPEN_HU
            elif n == 3:
                thr = OPEN_3 + (0.05 if behind == 1 else 0.0)
            elif n == 4:
                thr = OPEN_4 + (0.05 if behind == 3 else 0.0)
            if eff_bb < 12:
                thr -= 0.05
            if stack < 6 * bb:
                thr -= 0.12
            if limpers:
                thr += 0.04
            if pct >= thr:
                return self._raise(obs, obs["max_raise_to"])
            # cheap limp with playable hands
            if LIMP and tc <= bb and pct >= thr - 0.12 and eff_bb > 15:
                return self._call(obs)
            if obs["sb_seat"] == me and tc <= bb / 2 + 1 and pct >= SB_COMPLETE:
                return self._call(obs)
            return self._fold(obs)

        # facing raise(s)
        loose = self._pfr(raiser) if raiser >= 0 else 0.15
        widen = max(0.0, min(0.3, (loose - 0.15) * 0.5))
        po = tc / (pot + tc)
        committed = mybet > 0.35 * (stack + mybet)
        # opponents contesting: raisers and callers so far
        contest = set()
        first = False
        for h_st, seat, act, amt in hist:
            if h_st == 0 and seat != me:
                if act == "raise":
                    first = True
                    contest.add(seat)
                elif act == "call" and first:
                    contest.add(seat)
        k = max(1, len([s for s in contest if s in in_hand]))
        pen = (0.05 if raises == 1 else 0.09) * max(0.0, 1.0 - widen * 4)
        if raiser >= 0 and stacks[raiser] == 0 and bets[raiser] < 10 * bb:
            pen *= 0.5
        eq_vs = max(0.05, eqr - pen) ** (1 + 0.75 * (k - 1))
        if raises == 1:
            three = 0.955 - widen * 0.6
            call_thr = CALL1 - widen
            if short_table:
                three -= 0.03
                call_thr -= 0.06
        else:
            three = 0.985 - widen * 0.3
            call_thr = 0.92 - widen
        if pct >= three:
            return self._raise(obs, obs["max_raise_to"])
        # all-in or huge call: equity vs pot odds
        if stack_frac_call >= 0.35 or committed:
            margin = self._risk(obs)
            if eq_vs >= po + margin:
                return self._call(obs)
            return self._fold(obs)
        if pct >= call_thr and (tc <= 0.2 * stack or pct >= call_thr + 0.06):
            return self._call(obs)
        # blind defence vs a single raise at a good price
        if raises == 1 and (me == bbs or me == obs["sb_seat"]) and po <= 0.4:
            dthr = DEF_HU if n == 2 else DEF_3 if n == 3 else DEF_4 if n == 4 else call_thr - DEF_FULL
            if me != bbs:
                dthr += 0.08
            dthr -= widen
            if pct >= dthr:
                return self._call(obs)
        return self._fold(obs)

    def postflop(self, obs):
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        st = obs["street_index"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        stack = stacks[me]
        mybet = bets[me]
        tc = obs["to_call"]
        pot = obs["pot"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        n_opp = max(1, len(opps))
        hist = obs["history"]

        hv = hero_value(hole, board)
        ov = opp_values(hole + board, board)
        tot = ov.size
        f_beat = np.count_nonzero(ov > hv) / tot
        f_tie = np.count_nonzero(ov == hv) / tot
        f = f_beat + 0.5 * f_tie

        # range multipliers per opponent from this hand's action
        pre_raiser = -1
        street_aggr = {}
        checked = set()
        for h_st, seat, act, amt in hist:
            if act == "raise":
                if h_st == 0:
                    pre_raiser = seat
                else:
                    street_aggr[seat] = street_aggr.get(seat, 0) + ((RIVER_K if st == 3 else 2) if h_st == st else 1)
            elif act == "check" and h_st == st:
                checked.add(seat)
        p_now = 1.0
        for s in opps:
            m = CHECK_M if (s in checked and s not in street_aggr) else 1.0
            if s == pre_raiser:
                m *= 1.15
            k = street_aggr.get(s, 0)
            if k:
                a = self._aggr(s)
                m *= 1.0 + (0.1 + 1.6 * (1 - a) ** 1.2) * min(k, 3)
            fi = min(0.95, f * m)
            p_now *= (1 - fi) ** 6
        if st < 3:
            outs = draw_outs(hole, board)
            left = 52 - 4 - len(board)
            p1 = outs / left
            # vulnerability of made hands
            bsu = [0, 0, 0, 0]
            for c in board:
                bsu[c & 3] += 1
            bm = 0
            for c in board:
                bm |= 1 << (c >> 2)
            wet = (max(bsu) >= 2) + (nut_straight_top(bm) >= 0 or any(bin((bm >> lo) & 0x1F).count("1") >= 2 for lo in range(9)))
            vul = (0.10 + 0.07 * wet) * (1.0 if st == 1 else 0.6) * min(3, n_opp) ** 0.5
            all_in_call = tc >= 0.8 * stack
            if st == 1:
                p_hit = min(0.7, 1 - (1 - p1) * (1 - outs / (left - 1)))
            else:
                p_hit = min(0.6, p1 * (1.0 if all_in_call else 1.15))
            eq = p_now * (1 - vul) + (1 - p_now) * p_hit * 0.92
        else:
            outs = 0.0
            eq = p_now

        po = tc / (pot + tc) if tc else 0.0
        spr = stack / max(1, pot)
        aggressor = pre_raiser == me
        rnd = self.rng.random()

        if tc == 0:
            fall = 1.0
            station = True
            for s in opps:
                fr = self._fold_rate(s)
                fall *= fr
                if fr >= STATION_F:
                    station = False
            thin = STATION_THIN if station else 0.0
            if eq >= VAL_M - thin or (n_opp == 1 and eq >= VAL_HU - thin):
                return self._pot(obs, 1.0 if (spr <= 1 or fall < 0.33) else 0.75)
            if st < 3 and outs >= 8 and rnd < 0.55 and n_opp <= 2 and fall >= SEMI_F and (spr >= 1.5 or outs >= 12):
                return self._pot(obs, 0.66)
            if aggressor and n_opp == 1 and st == 1 and rnd < 0.5 and (spr >= 1.5 or eq >= 0.3) and not station:
                return self._pot(obs, 0.5)
            if n_opp <= 2 and fall >= BLUFF_F and (spr >= 1.2 or eq >= 0.3):
                if self.rng.random() < min(0.75, (fall - 0.3) * 2.5):
                    return self._pot(obs, 0.6)
            if n_opp == 1 and st == 3 and rnd < 0.12 and not street_aggr:
                return self._pot(obs, 0.6)
            return {"action": "check"}

        # facing a bet
        risk = self._risk(obs)
        if eq >= 0.8 or (eq >= 0.7 and n_opp == 1):
            return self._pot(obs, 1.0)
        if eq >= po + 0.02 + risk:
            return self._call(obs)
        return self._fold(obs)
