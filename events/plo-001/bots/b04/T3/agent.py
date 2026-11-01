"""b04 PLO bot: table-driven evaluator, exact made-hand rank vs all opponent
two-card combos, draw counting, heuristic preflop percentiles, opponent
aggression tracking, stack/ICM-aware commitment."""

import random
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
RK = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)


def _pack(rs):
    v = 0
    for r in rs:
        v = v << 4 | r
    return v << 4 * (5 - len(rs))


def _straight_top(ds):
    # ds: 5 distinct ranks sorted desc
    if ds[0] - ds[4] == 4:
        return ds[0]
    if ds == [12, 3, 2, 1, 0]:
        return 3
    return -1


def _eval_ranks(rs):
    cnt = {}
    for r in rs:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(cnt.items(), key=lambda x: (-x[1], -x[0]))
    ds = sorted(cnt, reverse=True)
    if len(ds) == 5:
        t = _straight_top(ds)
        if t >= 0:
            return 4 << 20 | t << 16
        return _pack(ds)
    c0 = groups[0][1]
    if c0 == 4:
        return 7 << 20 | groups[0][0] << 16 | groups[1][0] << 12
    if c0 == 3:
        if groups[1][1] == 2:
            return 6 << 20 | groups[0][0] << 16 | groups[1][0] << 12
        return 3 << 20 | groups[0][0] << 16 | _pack([groups[1][0], groups[2][0]]) >> 8
    if c0 == 2:
        if groups[1][1] == 2:
            return 2 << 20 | groups[0][0] << 16 | groups[1][0] << 12 | groups[2][0] << 8
        return 1 << 20 | groups[0][0] << 16 | _pack([g[0] for g in groups[1:]]) >> 4
    return _pack(ds)


def _build():
    rt = {}

    def rec(start, left, cur):
        if left == 0:
            rt[sum(RK[r] for r in cur)] = _eval_ranks(cur)
            return
        for r in range(start, 13):
            if cur.count(r) < 4:
                rec(r, left - 1, cur + [r])

    rec(0, 5, [])
    ft = [0] * 8192
    for combo in combinations(range(13), 5):
        m = 0
        for r in combo:
            m |= 1 << r
        ds = sorted(combo, reverse=True)
        t = _straight_top(ds)
        ft[m] = (8 << 20 | t << 16) if t >= 0 else (5 << 20 | _pack(ds))
    return rt, ft


RT, FT = _build()

# straight windows: 5-rank masks
WINDOWS = [sum(1 << r for r in range(lo, lo + 5)) for lo in range(9)] + [(1 << 12) | 0b1111]

# opponent rank pairs
OPP_PAIRS = [(r1, r2, RK[r1] + RK[r2]) for r1 in range(13) for r2 in range(r1, 13)]


# ---------------- preflop heuristic ----------------
PAIR_VAL = (2.0, 2.0, 2.2, 2.4, 2.6, 2.8, 3.2, 3.8, 4.6, 5.6, 6.6, 7.8, 10.5)


def pre_score(hole):
    ranks = [c >> 2 for c in hole]
    suits = [c & 3 for c in hole]
    score = 0.0
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    for r, n in cnt.items():
        if n == 2:
            score += PAIR_VAL[r]
        elif n == 3:
            score += PAIR_VAL[r] * 0.35
        elif n == 4:
            score -= 3.0
    sc = {}
    for c in hole:
        sc.setdefault(c & 3, []).append(c >> 2)
    nsuited = 0
    for s, rs in sc.items():
        n = len(rs)
        if n >= 2:
            hi = max(rs)
            v = 2.2 + (2.8 if hi == 12 else 1.4 if hi == 11 else 0.9 if hi == 10 else 0.5 if hi >= 8 else 0.0)
            if n == 3:
                v *= 0.65
            elif n == 4:
                v *= 0.3
            score += v
            nsuited += 1
    d = sorted(cnt, reverse=True)
    if 12 in cnt:
        dl = d + [-1]
    else:
        dl = d
    conn = 0.0
    for i in range(len(d)):
        for j in range(i + 1, len(dl)):
            gap = d[i] - dl[j]
            if gap <= 4:
                conn += (1.3, 1.3, 1.0, 0.7, 0.35)[gap]
    score += conn
    # coordinated four-card rundowns
    if len(d) == 4 and d[0] - d[3] <= 4:
        score += 1.5
    score += 0.35 * sum(max(0, r - 6) for r in ranks)
    # danglers: card not paired, not within 4 of another, not suited with another
    for c in hole:
        r = c >> 2
        if cnt[r] > 1:
            continue
        near = any(abs(r - r2) <= 3 or (r == 12 and r2 <= 3) or (r2 == 12 and r <= 3) for r2 in d if r2 != r)
        suited = len(sc[c & 3]) >= 2
        if not near and not suited:
            score -= 1.2 if r < 9 else 0.5
    return score


def _pct_table():
    rng = random.Random(12345)
    deck = list(range(52))
    vals = []
    for _ in range(12000):
        vals.append(pre_score(rng.sample(deck, 4)))
    vals.sort()
    return vals


PRE_VALS = _pct_table()
NPRE = len(PRE_VALS)


def pre_pct(hole):
    """fraction of random hands better than this one (0 = best)."""
    s = pre_score(hole)
    lo, hi = 0, NPRE
    while lo < hi:
        mid = (lo + hi) // 2
        if PRE_VALS[mid] <= s:
            lo = mid + 1
        else:
            hi = mid
    return 1.0 - lo / NPRE


# ---------------- postflop analysis ----------------

def analyze(hole, board):
    """Return (hero_value, p_beat, p_tie, straight_out_ranks, flush_info)."""
    trip_list = []
    for t in combinations(board, 3):
        tk = RK[t[0] >> 2] + RK[t[1] >> 2] + RK[t[2] >> 2]
        s0 = t[0] & 3
        if (t[1] & 3) == s0 and (t[2] & 3) == s0:
            tm = (1 << (t[0] >> 2)) | (1 << (t[1] >> 2)) | (1 << (t[2] >> 2))
            trip_list.append((tk, s0, tm))
        else:
            trip_list.append((tk, -1, 0))
    tks = [x[0] for x in trip_list]
    # hero
    hv = 0
    for a, b in combinations(hole, 2):
        pk = RK[a >> 2] + RK[b >> 2]
        sa = a & 3
        suited = sa == (b & 3)
        pm = (1 << (a >> 2)) | (1 << (b >> 2))
        for tk, ts, tm in trip_list:
            v = RT[pk + tk]
            if suited and ts == sa:
                fv = FT[pm | tm]
                if fv > v:
                    v = fv
            if v > hv:
                hv = v
    # availability
    cnt = [4] * 13
    seen = set(hole) | set(board)
    for c in seen:
        cnt[c >> 2] -= 1
    beats = 0
    ties = 0
    total = 0
    uval = {}
    for r1, r2, pk in OPP_PAIRS:
        if r1 == r2:
            w = cnt[r1] * (cnt[r1] - 1) // 2
        else:
            w = cnt[r1] * cnt[r2]
        if w <= 0:
            continue
        total += w
        u = max([RT[pk + tk] for tk in tks])
        uval[(r1, r2)] = u
        if u > hv:
            beats += w
        elif u == hv:
            ties += w
    # flushes
    bsuit = [0, 0, 0, 0]
    for c in board:
        bsuit[c & 3] += 1
    for s in range(4):
        if bsuit[s] >= 3:
            avail = [r for r in range(13) if (4 * r + s) not in seen]
            st = [(tm) for tk, ts, tm in trip_list if ts == s]
            for i in range(len(avail)):
                x = avail[i]
                for j in range(i + 1, len(avail)):
                    y = avail[j]
                    pm = (1 << x) | (1 << y)
                    fv = max([FT[pm | tm] for tm in st])
                    u = uval.get((x, y), 0)
                    if fv > u:
                        if fv > hv:
                            if u <= hv:
                                beats += 1
                                if u == hv:
                                    ties -= 1
                        elif fv == hv and u < hv:
                            ties += 1
    total = max(total, 1)
    return hv, beats / total, ties / total, bsuit


def draw_outs(hole, board, bsuit):
    """Return (outs_equiv, nut_flush_draw, flush_draw, straight_out_ranks)."""
    bm = 0
    for c in board:
        bm |= 1 << (c >> 2)
    hranks = [c >> 2 for c in hole]
    out_ranks = 0
    made_straight = False
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = hranks[i], hranks[j]
            if a == b:
                continue
            pm = (1 << a) | (1 << b)
            for W in WINDOWS:
                if W & pm != pm:
                    continue
                need = W & ~pm
                miss = need & ~bm
                if miss == 0:
                    made_straight = True
                elif miss & (miss - 1) == 0:
                    out_ranks |= miss
    seen = set(hole) | set(board)
    cnt = [4] * 13
    for c in seen:
        cnt[c >> 2] -= 1
    s_outs = 0
    r = 0
    m = out_ranks
    while m:
        if m & 1:
            s_outs += cnt[r]
        m >>= 1
        r += 1
    # flush draws
    f_outs = 0
    nut_fd = False
    fd = False
    for s in range(4):
        if bsuit[s] == 2:
            mine = [c >> 2 for c in hole if c & 3 == s]
            if len(mine) >= 2:
                fd = True
                remaining = 13 - 2 - len(mine)
                f_outs = max(f_outs, remaining)
                top_missing = max(rr for rr in range(13) if (4 * rr + s) not in set(board))
                if max(mine) == top_missing or max(mine) >= top_missing:
                    nut_fd = True
                else:
                    # second nut-ish still decent
                    pass
    outs = f_outs * (1.0 if nut_fd else 0.6) + s_outs * 0.85
    if f_outs and s_outs:
        outs -= 2
    return outs, nut_fd, fd, made_straight


RISK_BUST = {8: 0.085, 7: 0.085, 6: 0.075, 5: 0.07, 4: 0.06, 3: 0.045}
RISK_SCALE = 1.0
LOW_SPR = 1.0
H_BET = 1.0
H_CALL = 0.45
H_PF = 0.4
K_CALL = 2.0
CBET = 0.4
HU_SHOVE = 0.80
HU_CALL = 0.60
HU_OPEN = 0.50
HU_LIMP = 0.85
HU_DEF = 0.65


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 60, 40, 25, 15, 10, 5, 0])
        self.stats = {}  # seat -> [hands, vpip, pfr, aggr_actions, passive_actions]
        self.hand_seen = -1

    # ---------------- helpers ----------------
    def _st(self, seat):
        st = self.stats.get(seat)
        if st is None:
            st = self.stats[seat] = [0, 0, 0, 0, 0, 0, 0]
        return st

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            bet_open = -1
            for st_i, seat, act, amt in hist:
                if act in ("sb", "bb", "ante", "return"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                s = self._st(seat)
                if st_i >= 1:
                    if bet_open == st_i and act in ("fold", "call", "raise"):
                        s[5] += 1
                        if act == "fold":
                            s[6] += 1
                    if act == "raise":
                        bet_open = st_i
                if act == "raise":
                    s[3] += 1
                    if st_i == 0:
                        vp.add(seat)
                        pr.add(seat)
                elif act == "call":
                    s[4] += 1
                    if st_i == 0:
                        vp.add(seat)
                elif act == "check":
                    s[4] += 1
            for seat in seen:
                s = self._st(seat)
                s[0] += 1
                if seat in vp:
                    s[1] += 1
                if seat in pr:
                    s[2] += 1
        except Exception:
            pass

    def _last_to_act(self, obs, me):
        alive = obs["alive"]
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        post = alive[bi + 1:] + alive[:bi + 1]
        ih = obs["in_hand"]
        live = [x for x in post if x in ih and (obs["stacks"][x] > 0 or x == me)]
        return bool(live) and live[-1] == me

    def fold_rate(self, seat):
        s = self.stats.get(seat)
        if not s:
            return 0.4, 0
        return (s[6] + 1.0) / (s[5] + 2.5), s[5]

    def aggr(self, seat):
        s = self.stats.get(seat)
        if not s:
            return 0.3
        a, p = s[3], s[4]
        return (a + 1.0) / (a + p + 3.3)

    def vpip(self, seat):
        s = self.stats.get(seat)
        if not s or s[0] < 3:
            return 0.35
        return (s[1] + 1.0) / (s[0] + 3.0)

    # ---------------- actions ----------------
    def act(self, obs):
        try:
            return self.decide(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _call(self, obs):
        if obs["to_call"] == 0:
            return {"action": "check"}
        return {"action": "call"}

    def _raise_to(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0 or not ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return self._call(obs)
        a = int(amt)
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        return {"action": "raise", "amount": a}

    def _pot_frac(self, obs, frac):
        me = obs["seat"]
        bet = obs["bets"][me]
        stack = obs["stacks"][me]
        tc = obs["to_call"]
        target = bet + tc + frac * (obs["pot"] + tc)
        # shove if little would be left behind
        if stack + bet - target < 0.3 * (obs["pot"] + 2 * (target - bet)):
            target = obs["max_raise_to"]
        return self._raise_to(obs, target)

    # ---------------- decision ----------------
    def decide(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs["n_discard"]])}
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if not board:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    def _ctx(self, obs):
        me = obs["seat"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        my_total = stacks[me] + bets[me]
        other = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_total, other)
        return me, opps, eff

    def preflop(self, obs, hole):
        me, opps, eff = self._ctx(obs)
        bb = obs["bb"] or 1
        pct = pre_pct(hole)
        hist = obs["history"]
        raises = 0
        last_raiser = -1
        callers = 0
        for st_i, seat, act, amt in hist:
            if st_i != 0:
                continue
            if act == "raise":
                raises += 1
                last_raiser = seat
                callers = 0
            elif act == "call":
                callers += 1
        tc = obs["to_call"]
        stack = obs["stacks"][me]
        my_bet = obs["bets"][me]
        pot = obs["pot"]
        alive = obs["alive"]
        n_alive = len(alive)
        eff_bb = eff / bb
        my_bb = (stack + my_bet) / bb
        # position: number of players to act after me preflop
        btn = obs["button"]
        bbs = obs["bb_seat"]
        if n_alive == 2:
            order = [btn] + [s for s in alive if s != btn]
        else:
            j = (alive.index(bbs) + 1) % n_alive if bbs in alive else 0
            order = alive[j:] + alive[:j]
        idx = order.index(me) if me in order else 0
        behind = n_alive - 1 - idx
        is_bb = me == bbs
        is_sb = me == obs["sb_seat"]
        # table-size adjustment: fewer players -> wider
        width = 1.0 + 0.10 * max(0, 8 - n_alive)
        r = self.rng.random()

        # facing an all-in raise: call on pot odds vs an estimated equity
        if raises >= 1 and last_raiser >= 0 and obs["stacks"][last_raiser] == 0 and tc > 0:
            p_odds = tc / (pot + tc)
            eq_est = 0.62 - 0.25 * pct
            if self.vpip(last_raiser) < 0.2:
                eq_est -= 0.06
            elif self.vpip(last_raiser) > 0.45:
                eq_est += 0.03
            others = [x for x in obs["in_hand"] if x != me and x != last_raiser]
            if others:
                eq_est -= 0.1 * len(others)
            if raises >= 2:
                eq_est -= 0.04
            risk = 0.0
            if tc >= 0.5 * stack and n_alive > 2:
                if obs["stacks"][last_raiser] + obs["bets"][last_raiser] >= stack + my_bet:
                    risk = RISK_BUST.get(n_alive, 0.06)
                else:
                    risk = 0.01
            if eq_est >= p_odds + risk:
                return self._call(obs)
            if pct < 0.03 and not others:
                return self._call(obs)
            return self._fold(obs)

        # short-stack mode: commit with decent hands
        if my_bb <= 12:
            short_bonus = 0.12 if my_bb <= 5 else 0.0
            if raises == 0:
                if n_alive == 2:
                    thr = HU_SHOVE
                elif n_alive == 3:
                    thr = 0.45 if behind <= 2 else 0.35
                else:
                    thr = (0.30 if behind <= 2 else 0.22) * width
                thr += short_bonus
                if is_bb and tc == 0:
                    return self._raise_to(obs, obs["max_raise_to"]) if pct < 0.20 * width + short_bonus else self._call(obs)
                if pct < thr:
                    return {"action": "allin"}
                if is_sb and tc <= bb * 0.5 + 1 and pct < 0.5:
                    return self._call(obs)
                return self._fold(obs)
            # facing raise(s)
            commit_odds = tc / (pot + tc)
            if n_alive == 2:
                thr = HU_CALL if raises == 1 else HU_CALL - 0.15
            else:
                thr = (0.22 if raises == 1 else 0.12) * width
            if commit_odds < 0.3:
                thr += 0.1
            thr += short_bonus
            if pct < thr:
                return {"action": "allin"}
            return self._fold(obs)

        if raises == 0:
            if tc == 0:  # BB option, limped pot
                if pct < 0.08 * width:
                    return self._pot_frac(obs, 1.0)
                return self._call(obs)
            # unopened (maybe limpers)
            if n_alive == 2:
                if pct < HU_OPEN:
                    return self._pot_frac(obs, 1.0)
                if pct < HU_LIMP:
                    return self._call(obs)
                return self._fold(obs)
            base = {0: 0.40, 1: 0.32, 2: 0.26, 3: 0.22}.get(behind, 0.18)
            if is_sb:
                base = 0.30
            thr = base * width
            if callers:
                thr *= 0.85
            elif behind <= 3:
                later = order[idx + 1:]
                if later and max(self.vpip(x) for x in later) < 0.22:
                    thr *= 1.35
            if pct < thr:
                return self._pot_frac(obs, 1.0)
            if is_sb and pct < 0.45:
                return self._call(obs)
            if callers >= 1 and pct < thr + 0.08 and tc <= bb:
                return self._call(obs)
            return self._fold(obs)

        # facing raises
        frac_stack = tc / max(1, stack)
        rag = self.aggr(last_raiser)
        loose_adj = 0.06 if rag > 0.45 else 0.0

        if raises == 1:
            three_thr = (0.035 + loose_adj * 0.5) * width
            call_thr = (0.16 + loose_adj) * width
            if is_bb:
                call_thr += 0.06
            if n_alive == 2:
                three_thr = 0.08
                call_thr = HU_DEF
            # cheap raises (min-raises) -> defend wider
            price_bb = tc / bb
            if price_bb <= 2.5 and frac_stack < 0.15:
                call_thr *= 1.35
            if frac_stack > 0.35:
                call_thr *= 0.6
            if pct < three_thr:
                return self._pot_frac(obs, 1.0)
            if pct < call_thr and frac_stack < 0.5:
                return self._call(obs)
            if frac_stack >= 0.5 and pct < 0.06 * width:
                return {"action": "allin"}
            return self._fold(obs)
        # 3-bet or more: continue with aces / the very top only
        has_aa = sum(1 for c in hole if c >> 2 == 12) >= 2
        if has_aa or pct < 0.008 * width:
            return self._pot_frac(obs, 1.0)
        if pct < (0.02 + loose_adj * 0.2) * width and frac_stack < 0.2:
            return self._call(obs)
        if frac_stack < 0.08 and pct < 0.12:
            return self._call(obs)
        return self._fold(obs)

    def postflop(self, obs, hole, board):
        me, opps, eff = self._ctx(obs)
        n_opp = max(1, len(opps))
        hv, p_beat, p_tie, bsuit = analyze(hole, board)
        street = obs["street_index"]
        if len(board) < 5:
            outs, nut_fd, fd, made_st = draw_outs(hole, board, bsuit)
        else:
            outs, nut_fd, fd, made_st = 0.0, False, False, False
        tc = obs["to_call"]
        pot = obs["pot"]
        stack = obs["stacks"][me]
        my_bet = obs["bets"][me]
        hist = obs["history"]
        in_hand = set(obs["in_hand"])
        # action analysis
        aggressor = -1
        nraises = 0
        pf_aggr = -1
        hist_k = 0.0
        pf_opp_raises = 0
        for st_i, seat, act, amt in hist:
            if act == "raise":
                if st_i == street:
                    aggressor = seat
                    nraises += 1
                if st_i == 0:
                    pf_aggr = seat
                    if seat != me and seat in in_hand:
                        pf_opp_raises += 1
                elif st_i < street and seat != me and seat in in_hand:
                    hist_k += H_BET
            elif act == "call" and 0 < st_i < street and seat != me and seat in in_hand:
                hist_k += H_CALL
        hist_k += H_PF * min(pf_opp_raises, 2)
        hist_k = min(hist_k, 3.0)
        q = 1.0 - p_beat - 0.5 * p_tie
        cards_left = 5 - len(board)
        # board texture: how drawable is it
        bm = 0
        for c in board:
            bm |= 1 << (c >> 2)
        conn = 0
        for lo in range(-1, 9):
            w = ((bm << 1 | (bm >> 12 & 1)) >> (lo + 1)) & 0x1F
            cn = bin(w).count("1")
            if cn > conn:
                conn = cn
        two_tone = max(bsuit) == 2
        if cards_left == 2:
            d_eq = 1 - (1 - outs / 45.0) * (1 - outs / 44.0)
            vul = 0.86 - (0.07 if two_tone else 0.0) - (0.08 if conn >= 3 else 0.03 if conn == 2 else 0.0)
        elif cards_left == 1:
            d_eq = outs / 44.0
            vul = 0.93 - (0.04 if two_tone else 0.0) - (0.04 if conn >= 3 else 0.0)
        else:
            d_eq = 0.0
            vul = 1.0
        if p_beat < 0.002:
            vul = 1.0 - (1.0 - vul) * 0.6

        def equity(k):
            made = q ** (6 * n_opp * k)
            e = made * vul + (1 - made * vul) * d_eq * 0.85
            return min(e, 0.99)

        spr = eff / max(1, pot)
        r = self.rng.random()
        n_alive = len(obs["alive"])

        if tc == 0:
            # value: equity against the range that calls a bet
            kc = K_CALL
            if n_opp == 1:
                fr0, nf0 = self.fold_rate(opps[0])
                if nf0 >= 5:
                    if fr0 < 0.3:
                        kc = K_CALL - 0.5
                    elif fr0 > 0.6:
                        kc = K_CALL + 0.4
            eq_call = equity(kc + hist_k)
            eq_now = equity(1.0 + hist_k)
            if cards_left > 0 and spr < LOW_SPR and (eq_now >= 0.45 or (pf_aggr == me and eq_now >= 0.3) or d_eq >= 0.25):
                return self._pot_frac(obs, 1.0)
            if eq_call >= 0.55:
                return self._pot_frac(obs, 0.75)
            if eq_call >= 0.45 and cards_left > 0:
                return self._pot_frac(obs, 0.6)
            if cards_left > 0 and d_eq >= 0.30 and r < 0.6:
                return self._pot_frac(obs, 0.7)
            # bluffs heads-up, sized by how often this opponent folds to bets
            if n_opp == 1:
                fr, nf = self.fold_rate(opps[0])
                if pf_aggr == me and street == 1 and hist_k < 1.0:
                    pc = min(0.8, max(0.15, CBET + (fr - 0.4) * 1.5))
                    if r < pc:
                        return self._pot_frac(obs, 0.5)
                elif street >= 2 and nf >= 5 and fr > 0.5 and eq_now < 0.35:
                    if r < (fr - 0.4) * 0.8:
                        return self._pot_frac(obs, 0.6)
                elif nf >= 5 and fr > 0.45 and self._last_to_act(obs, me) and r < (fr - 0.3):
                    return self._pot_frac(obs, 0.5)
            return self._call(obs)

        # facing a bet
        bet_frac = tc / max(1, pot - tc)
        ag = self.aggr(aggressor) if aggressor >= 0 else 0.3
        tight = 2.0 * min(bet_frac, 1.2) + 1.0 * (nraises - 1) + hist_k
        if ag > 0.45:
            tight *= 0.6
        elif ag < 0.2:
            tight *= 1.3
        eq = equity(1.0 + tight)
        pot_odds = tc / (pot + tc)
        risk = 0.0
        if tc > 0.35 * stack and n_alive > 2:
            my_total = stack + my_bet
            would_bust = any(obs["stacks"][s] + obs["bets"][s] >= my_total for s in opps)
            risk = (RISK_BUST.get(n_alive, 0.06) if would_bust else 0.02) * RISK_SCALE
        committed = tc >= 0.8 * stack or (my_bet + tc) >= 0.6 * (stack + my_bet)
        need = pot_odds + risk
        if obs["max_raise_to"] > 0:
            eq_r = equity(1.0 + tight + 1.0)
            if eq_r >= (0.62 if cards_left == 0 else 0.66):
                return self._pot_frac(obs, 1.0)
        # draw-calling using implied odds
        if cards_left > 0:
            implied = min(0.08, 0.02 * spr) if nut_fd or outs >= 10 else 0.0
            need = need - implied
        if eq >= need:
            return self._call(obs)
        if committed and eq >= need - 0.05:
            return self._call(obs)
        return self._fold(obs)
