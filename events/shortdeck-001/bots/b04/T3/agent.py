import os
import json
import random
from time import perf_counter

from .ev import CARD, KEY, START, T, S, RBIT, cls_of, ALL_COMBOS

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre.json")))
HU = _D["hu"]
MW = _D["mw"]
NC = _D["ncombo"]
TOTAL = 630.0
ORDER = sorted(range(81), key=lambda c: -MW[c][0])
PCT = [0.0] * 81
_cum = 0
for _c in ORDER:
    PCT[_c] = (_cum + NC[_c] / 2.0) / TOTAL
    _cum += NC[_c]
SORTED_COMBOS = sorted(ALL_COMBOS, key=lambda ab: PCT[cls_of(ab[0], ab[1])])
PGRID = [0.02, 0.04, 0.06, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.85, 1.0]


def _eq_vs_top(c, p):
    num = den = 0.0
    cum = 0.0
    lim = p * TOTAL
    for j in ORDER:
        if cum >= lim:
            break
        w = min(NC[j], lim - cum)
        num += w * HU[c][j]
        den += w
        cum += NC[j]
    return num / den if den else 0.5


EQR = [[_eq_vs_top(c, p) for p in PGRID] for c in range(81)]


def eq_vs(c, p):
    if p <= PGRID[0]:
        return EQR[c][0]
    if p >= 1.0:
        return EQR[c][-1]
    row = EQR[c]
    for i in range(1, len(PGRID)):
        if p <= PGRID[i]:
            a, b = PGRID[i - 1], PGRID[i]
            t = (p - a) / (b - a)
            return row[i - 1] * (1 - t) + row[i] * t
    return row[-1]


# fraction of hands that call a shove, as a function of the caller's required equity
# (caller assumes a ~35% shoving range)
_EQ35 = sorted(((eq_vs(c, 0.35), NC[c]) for c in range(81)), reverse=True)
NEED_GRID = [0.2 + 0.02 * i for i in range(21)]
Q_OF_NEED = []
for _nd in NEED_GRID:
    Q_OF_NEED.append(sum(n for e, n in _EQ35 if e >= _nd + 0.02) / TOTAL)


def q_of_need(nd):
    if nd <= NEED_GRID[0]:
        return Q_OF_NEED[0]
    if nd >= NEED_GRID[-1]:
        return Q_OF_NEED[-1]
    i = int((nd - 0.2) / 0.02)
    t = (nd - NEED_GRID[i]) / 0.02
    return Q_OF_NEED[i] * (1 - t) + Q_OF_NEED[min(i + 1, 20)] * t


PREM = {2: 0.0, 3: 0.068, 4: 0.084, 5: 0.093, 6: 0.072, 7: 0.06, 8: 0.05}
PREM_SCALE = 0.75
EARLY_MULT = 1.0
VAL_HU = 0.58
CBET_BASE = 0.35
CALL_MARGIN = 0.0
PUSH_BB = 14
RAISE_THR = 0.72
OPEN_SIZE = 2.5
KSCALE = 1.4


def prem(n_alive, risk_frac):
    """ICM risk premium (extra equity needed) for risking risk_frac of my stack."""
    if risk_frac <= 0:
        return 0.0
    return PREM.get(n_alive, 0.05) * min(1.0, risk_frac) * PREM_SCALE


def icm_equity(stacks, payouts):
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

    return rest((1 << n) - 1)


def _flushval(s, cards):
    for su in range(4):
        if (s >> (4 * su)) & 8:
            m = 0
            for c in cards:
                if c & 3 == su:
                    m |= RBIT[c]
            return S[m]
    return T[s >> 16]


class Opp:
    __slots__ = ("hands", "vpip", "pfr", "agg", "pas", "allin_pf", "faced_bet", "fold_bet")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.agg = 0
        self.pas = 0
        self.allin_pf = 0
        self.faced_bet = 0
        self.fold_bet = 0

    def vpip_est(self):
        return (self.vpip + 0.4 * 6) / (self.hands + 6)

    def pfr_est(self):
        return (self.pfr + 0.2 * 6) / (self.hands + 6)

    def af(self):
        return (self.agg + 1.0) / (self.agg + self.pas + 3.0)

    def fold_to_bet(self):
        return (self.fold_bet + 0.45 * 4) / (self.faced_bet + 4)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = list(config.get("points", [100, 45, 20, 8, 0, 0, 0, 0]))
        self.opp = {}
        self.limit_s = 0.00025

    # ------------------------------------------------------------------ utils
    def o(self, s):
        x = self.opp.get(s)
        if x is None:
            x = self.opp[s] = Opp()
        return x

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            last_aggr_street = {}
            for st, seat, act, amt in hist:
                if seat is None or seat < 0:
                    continue
                if st == 0:
                    if act in ("sb", "bb", "ante", "fold", "check", "call", "raise", "bet"):
                        seen.add(seat)
                    if act in ("call", "raise", "bet"):
                        vp.add(seat)
                    if act in ("raise", "bet"):
                        pr.add(seat)
                else:
                    ob = self.o(seat)
                    if act in ("raise", "bet"):
                        ob.agg += 1
                        last_aggr_street[st] = seat
                    elif act in ("call", "check"):
                        ob.pas += 1
                        if act == "call":
                            ob.faced_bet += 1
                    elif act == "fold":
                        ob.faced_bet += 1
                        ob.fold_bet += 1
            for s in seen:
                if s == self.seat:
                    continue
                ob = self.o(s)
                ob.hands += 1
                if s in vp:
                    ob.vpip += 1
                if s in pr:
                    ob.pfr += 1
        except Exception:
            pass

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def _check_fold(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _raise_to(self, obs, amt):
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if hi <= 0 or not ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return self._call(obs)
        amt = int(amt)
        if amt >= hi * 0.8:
            amt = hi
        if amt < lo:
            amt = lo
        if amt > hi:
            amt = hi
        return {"action": "raise", "amount": amt}

    def _allin(self, obs):
        if obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"]):
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self._call(obs)

    # ---------------------------------------------------------------- main
    def _act(self, obs):
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if obs["street_index"] == 0 or not board:
            return self.preflop(obs, hole)
        return self.postflop(obs, hole, board)

    def preflop_order(self, obs):
        alive = sorted(obs["alive"])
        n = len(alive)
        if n == 2:
            b = obs["button"]
            other = alive[0] if alive[1] == b else alive[1]
            return [b, other]
        bb = obs["bb_seat"]
        if bb in alive:
            i = alive.index(bb)
        else:
            i = 0
            for k, s in enumerate(alive):
                if s < bb:
                    i = k
        return [alive[(i + 1 + k) % n] for k in range(n)]

    def call_range(self, x_bb, seat, nd=None):
        if nd is not None:
            q = q_of_need(nd)
        else:
            q = 0.07 + 1.7 / max(x_bb, 1.0)
        if seat is not None:
            ob = self.opp.get(seat)
            if ob is not None and ob.hands >= 8:
                q *= max(0.6, min(1.8, ob.vpip_est() / 0.35))
        return max(0.08, min(0.75, q))

    def icm_need(self, obs, me, vill, risk_me, win_amt):
        """Required equity to call all-in by ICM. risk_me: chips I lose if lose;
        win_amt: chips I gain if win (from villain + dead)."""
        stacks = obs["stacks"]
        bets = obs["bets"]
        alive = [s for s in obs["alive"]]
        base = {s: stacks[s] + bets[s] for s in alive}
        if len(alive) > 6 or len(alive) < 3:
            return None
        pot_dead = obs["pot"] - sum(bets[s] for s in alive)
        # fold: I lose my bet; others: approximate dead money goes to villain
        seats = alive
        f = dict(base)
        f[me] = base[me] - bets[me]
        f[vill] = base[vill] + bets[me] + pot_dead
        w = dict(base)
        w[me] = base[me] + win_amt
        w[vill] = base[vill] - (win_amt - pot_dead - sum(bets[s] for s in alive if s not in (me, vill)))
        l = dict(base)
        l[me] = base[me] - risk_me
        l[vill] = base[vill] + risk_me + pot_dead
        pts = self.points

        def u(d):
            st = [max(0.0, float(d[s])) for s in seats]
            if st[seats.index(me)] <= 0:
                # busted now: rank among busted by start stacks ~ ignore
                return pts[min(len(seats) - 1, len(pts) - 1)] if len(seats) - 1 < len(pts) else 0.0
            eq = icm_equity(st, pts[:len(seats)])
            return eq[seats.index(me)]

        uf, uw, ul = u(f), u(w), u(l)
        if uw - ul <= 1e-9:
            return None
        return (uf - ul) / (uw - ul)

    def preflop(self, obs, hole):
        me = obs["seat"]
        bb = max(1, obs["bb"])
        stacks, bets = obs["stacks"], obs["bets"]
        my_total = stacks[me] + bets[me]
        c = cls_of(hole[0], hole[1])
        pct = PCT[c]
        hist = obs["history"]
        raises = []
        limpers = 0
        for st, seat, act, amt in hist:
            if st != 0:
                continue
            if act in ("raise", "bet"):
                raises.append((seat, amt))
            elif act == "call" and not raises:
                limpers += 1
        nr = len(raises)
        to_call = obs["to_call"]
        pot = obs["pot"]
        in_hand = obs["in_hand"]
        opps = [s for s in in_hand if s != me]
        if not opps:
            return self._call(obs)
        opp_max = max(stacks[s] + bets[s] for s in opps)
        eff = min(my_total, opp_max)
        eff_bb = eff / bb
        order = self.preflop_order(obs)
        idx = order.index(me) if me in order else 0
        behind = [s for s in order[idx + 1:] if s in in_hand and stacks[s] > 0]
        n_alive = len(obs["alive"])
        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])

        if nr == 0:
            # unopened (maybe limpers)
            if to_call == 0:
                # BB option
                if pct <= 0.10 and can_raise:
                    if eff_bb <= 12:
                        return self._allin(obs)
                    return self._raise_to(obs, bb * (3.5 + limpers))
                return {"action": "check"}
            # push/fold zone
            if eff_bb <= PUSH_BB or (my_total / bb) <= PUSH_BB:
                ev = self.push_ev(obs, c, me, my_total, pot, bets[me], behind, bb)
                margin = 0.15 * bb
                if ev > margin:
                    return self._allin(obs)
                # SB complete cheap vs BB with decent hands? no: fold
                return self._check_fold(obs)
            nb = len(behind)
            base = {0: 1.0, 1: 0.50, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14, 7: 0.12}.get(nb, 0.12)
            if n_alive <= 3:
                base *= 1.15
            if obs.get("level", 0) <= 1 and n_alive >= 6:
                base *= EARLY_MULT
            # adjust by blinds' tendencies: if players behind fold a lot, widen
            if limpers:
                base *= 0.6
            elif 1 <= nb <= 3:
                vs = [self.o(x).vpip_est() for x in behind]
                avgv = sum(vs) / len(vs)
                if avgv < 0.3:
                    base *= 1.25
                elif avgv > 0.5:
                    base *= 0.85
            if pct <= base:
                size = bb * (OPEN_SIZE + limpers) if nb > 1 else bb * (OPEN_SIZE + 0.5)
                if eff_bb <= 20 and pct <= base * 0.35:
                    return self._raise_to(obs, size)
                return self._raise_to(obs, size)
            return self._check_fold(obs)

        # facing raise(s)
        raiser, raise_to = raises[-1]
        rob = self.o(raiser)
        p_open = max(0.05, min(0.85, rob.pfr_est() * 1.1))
        if nr == 1:
            p_r = p_open
        elif nr == 2:
            p_r = max(0.03, p_open * 0.35)
        else:
            p_r = max(0.02, p_open * 0.18)
        raiser_allin = stacks[raiser] == 0
        if raiser_allin:
            rt_bb = (stacks[raiser] + bets[raiser]) / bb
            if nr == 1:
                pw = 0.06 + 1.8 / max(rt_bb, 1.0)
                if n_alive == 2 or raiser == obs["sb_seat"]:
                    pw *= 1.6
                elif raiser in order[-4:-2]:
                    pw *= 1.25
                p_r = max(p_r, min(0.75, pw))
        eq = eq_vs(c, p_r)
        # multiway: other callers already in
        last_r = max(i for i, h in enumerate(hist) if h[0] == 0 and h[2] in ("raise", "bet"))
        n_other = len({h[1] for h in hist[last_r + 1:] if h[0] == 0 and h[2] == "call" and h[1] != me})
        if n_other:
            eq *= 0.85 ** n_other
        call_amt = min(to_call, stacks[me])
        final_pot = pot + call_amt
        need = call_amt / max(1, final_pot)
        commit = call_amt >= 0.35 * stacks[me] or (stacks[me] - call_amt) / bb < 8
        if commit or raiser_allin:
            # all-in style decision
            need2 = None
            if raiser_allin or call_amt >= stacks[me] * 0.95:
                vill_total = stacks[raiser] + bets[raiser]
                risk = min(my_total, vill_total)
                need2 = self.icm_need(obs, me, raiser, risk, min(my_total, vill_total) + (pot - bets[me] - bets[raiser]))
            risk = min(my_total, max(stacks[s] + bets[s] for s in opps))
            pr = prem(n_alive, risk / max(1, my_total))
            if need2 is not None:
                need = max(need + pr * 0.5, need2 * PREM_SCALE + need * (1 - PREM_SCALE))
            else:
                need += pr
            if eq >= need:
                if can_raise and not raiser_allin and eq >= need + 0.05:
                    return self._allin(obs)
                return self._call(obs)
            return self._check_fold(obs)
        # 3-bet / 4-bet for value
        if can_raise and (pct <= p_r * 0.3 or pct <= 0.025):
            ip = len(behind) == 0 or me == obs["button"]
            mult = 3.0 if ip else 3.6
            target = raise_to * mult + bb * 0 + sum(bets[s] for s in opps if s != raiser)
            if target >= my_total * 0.4 or eff_bb <= 25:
                return self._allin(obs)
            return self._raise_to(obs, target)
        # light 3-bet steal vs loose openers
        if can_raise and nr == 1 and p_open >= 0.35 and pct <= 0.22 and not n_other and self.rng.random() < 0.5:
            target = raise_to * 3.2
            if target >= my_total * 0.4:
                return self._allin(obs)
            return self._raise_to(obs, target)
        # call
        implied = 0.06 if eff_bb > 30 else 0.02
        oop_pen = 0.0 if (len(behind) == 0 or me == obs["button"]) else 0.04
        if me == obs["bb_seat"] and nr == 1:
            oop_pen = 0.0
        maxpct = 0.55 if me == obs["bb_seat"] else (0.42 if me == obs["sb_seat"] else 0.35)
        if eq + implied - oop_pen >= need + 0.05 and pct <= maxpct:
            return self._call(obs)
        return self._check_fold(obs)

    def push_ev(self, obs, c, me, my_total, pot, my_bet, behind, bb):
        stacks, bets = obs["stacks"], obs["bets"]
        ev = 0.0
        reach = 1.0
        for s in behind:
            their = stacks[s] + bets[s]
            X = min(my_total, their)
            pot_dead0 = pot - my_bet - bets[s]
            nd = (X - bets[s]) / max(1.0, pot_dead0 + 2 * X)
            q = self.call_range(X / bb, s, nd + 0.03 * (len(behind) - 1))
            eqc = eq_vs(c, q) - prem(len(obs["alive"]), X / max(1, my_total))
            pot_dead = pot - my_bet - bets[s]
            gain = eqc * (pot_dead + 2 * X) - (X - my_bet)
            ev += reach * q * gain
            reach *= (1 - q)
        ev += reach * pot
        return ev

    # --------------------------------------------------------------- postflop
    def opp_range(self, obs, s):
        hist = obs["history"]
        raised = 0
        called = False
        for st, seat, act, amt in hist:
            if st == 0 and seat == s:
                if act in ("raise", "bet"):
                    raised += 1
                elif act == "call":
                    called = True
        ob = self.o(s)
        if raised >= 2:
            return max(0.04, ob.pfr_est() * 0.4)
        if raised == 1:
            return max(0.06, min(0.9, ob.pfr_est() * 1.1))
        if called:
            return max(0.15, min(1.0, ob.vpip_est() * 1.1))
        return 1.0

    def mc(self, hole, board, ps, budget, maxn=400):
        rnd = self.rng.random
        known = set(hole) | set(board)
        deck = [c for c in range(36) if c not in known]
        nd = len(deck)
        need = 5 - len(board)
        bs0 = START
        for cc in board:
            bs0 += KEY[cc]
        hk = KEY[hole[0]] + KEY[hole[1]]
        lims = [max(20, int(p * 630)) for p in ps]
        combos = SORTED_COMBOS
        wins = 0.0
        n = 0
        t_end = perf_counter() + budget
        while n < maxn:
            used = set(known)
            hands = []
            for lim in lims:
                for _ in range(30):
                    a, b = combos[int(rnd() * lim)]
                    if a not in used and b not in used:
                        break
                else:
                    while True:
                        a, b = combos[int(rnd() * 630)]
                        if a not in used and b not in used:
                            break
                used.add(a)
                used.add(b)
                hands.append((a, b))
            bs = bs0
            extra = []
            while len(extra) < need:
                x = deck[int(rnd() * nd)]
                if x not in used:
                    used.add(x)
                    extra.append(x)
                    bs += KEY[x]
            s = bs + hk
            if s & 0x8888:
                hv = _flushval(s, board + extra + hole)
            else:
                hv = T[s >> 16]
            res = 1.0
            ties = 0
            for a, b in hands:
                s2 = bs + KEY[a] + KEY[b]
                if s2 & 0x8888:
                    ov = _flushval(s2, board + extra + [a, b])
                else:
                    ov = T[s2 >> 16]
                if ov > hv:
                    res = 0.0
                    break
                if ov == hv:
                    ties += 1
            if res > 0 and ties:
                res = 1.0 / (1 + ties)
            wins += res
            n += 1
            if (n & 3) == 0 and perf_counter() > t_end:
                break
        return wins / n if n else 0.5

    def postflop(self, obs, hole, board):
        me = obs["seat"]
        stacks, bets = obs["stacks"], obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        street = obs["street_index"]
        bb = max(1, obs["bb"])
        opps = [s for s in obs["in_hand"] if s != me]
        if not opps:
            return self._call(obs)
        ps = [self.opp_range(obs, s) for s in opps]
        eq = self.mc(hole, board, ps, self.limit_s)
        hist = obs["history"]
        pfa = None
        for st, seat, act, amt in hist:
            if st == 0 and act in ("raise", "bet"):
                pfa = seat
        street_aggr = [(seat, amt) for st, seat, act, amt in hist if st == street and act in ("raise", "bet")]
        my_stack = stacks[me]
        can_raise = obs["max_raise_to"] > 0 and ("raise" in obs["legal"] or "bet" in obs["legal"])
        n = len(opps)
        spr = my_stack / max(1, pot)
        if to_call == 0:
            thr = VAL_HU if n == 1 else (VAL_HU - 0.13 if n == 2 else VAL_HU - 0.2)
            if eq >= thr and can_raise:
                frac = 0.6 if eq < 0.8 else 0.75
                if spr <= 1.3:
                    return self._allin(obs)
                return self._raise_to(obs, pot * frac)
            # c-bet / bluff
            if can_raise and n == 1 and pfa == me and street == 1:
                fb = self.o(opps[0]).fold_to_bet()
                if self.rng.random() < CBET_BASE + 0.6 * fb * (1.0 if eq > 0.3 else 0.8):
                    return self._raise_to(obs, pot * 0.45)
            if can_raise and n == 1 and street >= 2 and eq >= 0.35 and pfa == me and self.rng.random() < 0.25:
                return self._raise_to(obs, pot * 0.55)
            return {"action": "check"}
        # facing a bet
        pot_before = pot - to_call - bets[me] if False else max(1, pot - sum(bets))
        last_bet = max(bets)
        f = to_call / max(1, pot - to_call)
        aggressor = street_aggr[-1][0] if street_aggr else opps[0]
        afx = self.o(aggressor).af()
        k = 0.55 * KSCALE * (1.3 - afx)
        if len(street_aggr) >= 2:
            k += 0.35
        eq_adj = eq ** (1.0 + k * min(f, 2.0) + (0.1 if street == 3 else 0.0))
        call_amt = min(to_call, my_stack)
        need = call_amt / max(1, pot + call_amt) + CALL_MARGIN
        my_total = my_stack + bets[me]
        if call_amt >= 0.3 * my_stack:
            need += prem(len(obs["alive"]), (call_amt + bets[me]) / max(1, my_total + obs["pot"] * 0))
        if can_raise and eq_adj >= RAISE_THR:
            target = last_bet * 2.8 + (pot - sum(bets))
            if spr <= 2.5 or target >= (my_stack + bets[me]) * 0.45:
                return self._allin(obs)
            return self._raise_to(obs, target)
        if eq_adj >= need:
            return self._call(obs)
        return self._check_fold(obs)
