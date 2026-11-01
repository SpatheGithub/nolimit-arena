import random

import numpy as np

from .evaluator import CARD, STRAIGHT, FLUSH, FULL_HOUSE, TWO_PAIR, TRIPS, board_strength, improve_outs
from .preflop import pre_pct


DEBUG = False


def _safe(obs):
    if obs.get("phase") == "discard":
        return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
    return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}


def _sv(p):
    return 0.17 - 0.32 * (max(0.0, min(1.0, p)) ** 0.6)


def pre_eq_hu(pct, f):
    """Heads-up preflop equity of a hand at percentile pct vs a range of the top f."""
    e = 0.5 + _sv(pct) - _sv(f * 0.5)
    return max(0.25, min(0.75, e))


ICM_PREM = {2: 0.0, 3: 0.05, 4: 0.08, 5: 0.09, 6: 0.09, 7: 0.09, 8: 0.10}


def icm_margin(n_alive, need, to_call, stack, pot, my_total, opp_total):
    """Extra equity required for calls that risk most of our stack (ICM risk premium)."""
    prem = ICM_PREM.get(n_alive, 0.1)
    if prem <= 0 or stack <= 0:
        return 0.0
    left = stack - to_call
    risk = to_call / stack
    if left < 0.5 * (pot + to_call):
        risk = 1.0
    if risk < 0.35:
        return 0.0
    cover = min(1.0, opp_total / max(1.0, my_total))
    return prem * min(1.0, need / 0.4 + 0.25) * risk * cover


def multi_eq(e, k):
    if k <= 1:
        return e
    return e / (e + (1 - e) * k)


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.st = {}  # seat -> stats list
        self.hands_seen = 0
        self.dlog = []
        self.dbg = {}

    # ---------- opponent stats ----------
    def _s(self, seat):
        s = self.st.get(seat)
        if s is None:
            # hands, vpip, pfr, post_aggr, post_pass, faced_bet, folded_to_bet
            s = self.st[seat] = [0, 0, 0, 0, 0, 0, 0]
        return s

    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            if DEBUG:
                pay = event.get("payoffs", {}).get(self.seat, event.get("payoffs", {}).get(str(self.seat), 0))
                stk = event.get("stacks") or {}
                mine = stk[self.seat] if isinstance(stk, list) else stk.get(self.seat, 1)
                if mine == 0:
                    print("BUST hand", event.get("hand_id"), "board", " ".join(event.get("board") or []), "shown", {k: " ".join(v) for k, v in (event.get("shown") or {}).items()})
                    for d in self.dlog:
                        print("  D st%d %s pot%d tc%d stk%d %s %s" % (d[0], " ".join(d[2]), d[3], d[4], d[5], d[6], {k: float(v) for k, v in d[7].items()}))
                self.dlog = []
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur_street = -1
            raised = False
            for h in hist:
                st, seat, act = h[0], h[1], h[2]
                if act in ("ante", "sb", "bb", "return", "discard"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st != cur_street:
                    cur_street = st
                    raised = False
                if st == 0:
                    if act in ("call", "raise"):
                        vp.add(seat)
                    if act == "raise":
                        pr.add(seat)
                else:
                    s = self._s(seat)
                    if act == "raise":
                        s[3] += 1
                    elif act in ("call", "check"):
                        s[4] += 1
                    if raised and act in ("fold", "call", "raise"):
                        s[5] += 1
                        if act == "fold":
                            s[6] += 1
                if act == "raise":
                    raised = True
            for seat in seen:
                s = self._s(seat)
                s[0] += 1
                if seat in vp:
                    s[1] += 1
                if seat in pr:
                    s[2] += 1
        except Exception:
            pass

    def vpip(self, seat):
        s = self._s(seat)
        return (s[1] + 0.3 * 6) / (s[0] + 6)

    def pfr(self, seat):
        s = self._s(seat)
        return (s[2] + 0.15 * 6) / (s[0] + 6)

    def aggr(self, seat):
        s = self._s(seat)
        return (s[3] + 0.35 * 8) / (s[3] + s[4] + 8)

    def fold_to_bet(self, seat):
        s = self._s(seat)
        return (s[6] + 0.45 * 6) / (s[5] + 6)

    # ---------- action helpers ----------
    def act(self, obs):
        try:
            r = self._act(obs)
            if DEBUG:
                self.dlog.append((obs["street_index"], obs["board"], obs["hole"], obs["pot"], obs["to_call"], obs["stacks"][obs["seat"]], r, dict(self.dbg)))
            return r
        except Exception:
            if DEBUG:
                import traceback
                print(traceback.format_exc().replace("\n", " | "))
            return _safe(obs)

    def _raise(self, amount):
        o = self.o
        legal = o["legal"]
        if ("raise" in legal or "bet" in legal) and o["max_raise_to"] > 0:
            a = int(amount)
            lo, hi = o["min_raise_to"], o["max_raise_to"]
            if a < lo:
                a = lo
            if a > hi:
                a = hi
            return {"action": "raise" if "raise" in legal else "bet", "amount": a}
        return self._call()

    def _call(self):
        legal = self.o["legal"]
        if "call" in legal:
            return {"action": "call"}
        return {"action": "check"}

    def _fold(self):
        if "check" in self.o["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def _pot(self, frac):
        o = self.o
        me = o["seat"]
        mybet = o["bets"][me]
        to_call = o["to_call"]
        pot = o["pot"]
        target = mybet + to_call + frac * (pot + to_call)
        stack_total = o["stacks"][me] + mybet
        new_pot = pot + to_call + 2 * (target - mybet - to_call)
        if stack_total - target < 0.35 * new_pot:
            target = o["max_raise_to"]
        return self._raise(target)

    # ---------- main ----------
    def _act(self, obs):
        self.o = obs
        if obs["phase"] == "discard":
            return _safe(obs)
        me = obs["seat"]
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        street = obs["street_index"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        bb = obs["bb"] or 1
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        my_total = stacks[me] + bets[me]
        opp_max = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_total, opp_max)
        self.eff_bb = eff / bb
        # order of action
        n = len(alive)
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        if street == 0:
            if n == 2:
                order = [alive[bi], alive[1 - bi]]
            else:
                bbs = obs["bb_seat"]
                j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
                order = alive[j:] + alive[:j]
        else:
            order = alive[bi + 1:] + alive[:bi + 1]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        post = alive[bi + 1:] + alive[:bi + 1]
        live = [s for s in post if s in in_hand and (stacks[s] > 0 or s == me)]
        ip = bool(live) and live[-1] == me
        hist = obs["history"]
        if street == 0:
            return self.preflop(obs, hole, me, opps, behind, ip, hist, bb, eff)
        return self.postflop(obs, hole, board, me, opps, behind, ip, hist, bb, eff, street)

    # ---------- preflop ----------
    def preflop(self, obs, hole, me, opps, behind, ip, hist, bb, eff):
        pct = pre_pct(hole)
        self.dbg = {"pct": round(pct, 3)}
        to_call = obs["to_call"]
        pot = obs["pot"]
        stack = obs["stacks"][me]
        raises = 0
        limpers = 0
        last_raiser = -1
        for h in hist:
            if h[0] != 0:
                continue
            if h[2] == "raise":
                raises += 1
                last_raiser = h[1]
            elif h[2] == "call" and raises == 0:
                limpers += 1
        nb = len(behind)
        eff_bb = eff / bb
        n_opp = len(opps)
        is_bb = me == obs["bb_seat"]
        n_al = len(obs["alive"])
        wm = {2: 2.2, 3: 1.6, 4: 1.3, 5: 1.12}.get(n_al, 1.0)

        # big decision: calling commits a large part of our stack
        commit = to_call >= 0.4 * stack or eff_bb <= 12
        if raises == 0:
            if eff_bb <= 12:
                # push/fold style: raise max with a range by depth/position
                th = {0: 0.0}.get(nb, None)
                base = 0.22 + 0.06 * max(0, 3 - nb) + (12 - eff_bb) * 0.025
                base = min(0.8, base * wm)
                if limpers:
                    base *= 0.8
                if pct <= base:
                    return self._raise(obs["max_raise_to"])
                if to_call == 0:
                    return self._call()
                if to_call <= 0.5 * bb and pct <= min(0.9, 0.55 * wm):
                    return self._call()
                return self._fold()
            open_th = {0: 0.30, 1: 0.40, 2: 0.32, 3: 0.24, 4: 0.19, 5: 0.16}.get(nb, 0.14)
            open_th = min(0.75, open_th * wm)
            if nb <= 3 and behind and max(self.vpip(x) for x in behind) < 0.25:
                open_th *= 1.3
            if limpers:
                iso = open_th * 0.7
                if pct <= iso:
                    return self._pot(1.0)
                if to_call == 0:
                    return self._call()
                if to_call <= bb and pct <= min(0.45 * wm, open_th * 1.6):
                    return self._call()
                return self._fold()
            if to_call == 0:  # BB unraised
                if pct <= 0.08 * wm:
                    return self._pot(1.0)
                return self._call()
            if pct <= open_th:
                return self._pot(1.0)
            if to_call <= 0.5 * bb and pct <= min(0.95, 0.45 * wm):  # SB complete
                return self._call()
            return self._fold()

        # facing raises
        lr_pfr = self.pfr(last_raiser) if last_raiser >= 0 else 0.15
        loose = max(0.0, min(0.25, lr_pfr - 0.15))
        f_range = max(0.06, min(0.8, lr_pfr * (1.0 if raises == 1 else 0.45) * wm))
        if commit:
            # equity-based all-in decision
            invested = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise") and h[1] != me)
            k = max(1.0, len([x for x in opps if x in invested]) + 0.25 * len([x for x in behind if x not in invested]))
            e = multi_eq(pre_eq_hu(pct, f_range), k)
            final_pot = pot + to_call
            if to_call < stack:
                # assume rest goes in later: use effective stacks
                final_pot = pot + to_call + (eff - obs["bets"][me] - to_call) * 0  # conservative
            need = to_call / (pot + to_call)
            opp_total = max([obs["stacks"][x] + obs["bets"][x] for x in opps], default=0)
            im = icm_margin(len(obs["alive"]), need, to_call, stack, pot, stack + obs["bets"][me], opp_total)
            if e >= need + 0.03 + im:
                if pct <= 0.10 or e >= 0.55:
                    return self._raise(obs["max_raise_to"])
                return self._call()
            return self._fold()
        if raises == 1:
            th3 = (0.035 + loose * 0.4) * wm
            if pct <= th3:
                return self._pot(1.0)
            call_th = (0.12 if ip else 0.085) + loose * 0.5
            if is_bb:
                if to_call <= 3 * bb and n_opp <= 2:
                    call_th = max(call_th, 0.30 + loose * 0.4)
                else:
                    call_th += 0.05
            if lr_pfr < 0.10:
                call_th *= 0.7
            # price: to_call relative to stack
            if to_call > 0.2 * stack:
                call_th *= 0.6
            call_th = min(0.75, call_th * wm)
            if pct <= call_th:
                return self._call()
            return self._fold()
        # 3-bet or more
        aces = sum(1 for c in hole if c >> 2 == 12) >= 2
        if aces or pct <= 0.004 + loose * 0.05:
            return self._raise(obs["max_raise_to"])
        if pct <= 0.03 + loose * 0.2 and to_call <= 0.3 * stack:
            return self._call()
        return self._fold()

    # ---------- postflop ----------
    def postflop(self, obs, hole, board, me, opps, behind, ip, hist, bb, eff, street):
        to_call = obs["to_call"]
        pot = obs["pot"]
        stack = obs["stacks"][me]
        mine, beat, tie, unseen, tri = board_strength(hole, board)
        cat = mine >> 20
        b = beat + 0.5 * tie
        q = 1.0 - (1.0 - b) ** 5.5  # prob a random 4-card hand beats us now

        # who bet this street, who called before
        aggr_now = {}
        bet_level = 0
        n_raises = 0
        pf_raiser = -1
        prev_callers = set()
        prev_aggr = set()
        callers_now = set()
        for h in hist:
            st, seat, act, amt = h[0], h[1], h[2], h[3]
            if st == 0 and act == "raise":
                pf_raiser = seat
            if st == street:
                if act == "raise":
                    n_raises += 1
                    aggr_now[seat] = n_raises
                    bet_level = amt
                elif act == "call":
                    callers_now.add(seat)
            elif st >= 1 and st < street:
                if act == "call":
                    prev_callers.add(seat)
                elif act == "raise":
                    prev_aggr.add(seat)
        base_f = {1: 0.32, 2: 0.25, 3: 0.20}[street] * {2: 1.5, 3: 1.25, 4: 1.1}.get(len(obs["alive"]), 1.0)
        pot_before = max(1, pot - sum(obs["bets"]))
        size = (bet_level - obs["bets"][me]) / pot_before if bet_level else 0.0
        p_nb = 1.0
        for s in opps:
            if s in aggr_now:
                f = base_f if aggr_now[s] == 1 else base_f * 0.35
                a = self.aggr(s)
                f *= max(0.6, min(2.2, a / 0.35))
                if size >= 0.8:
                    f *= 0.85
                elif size <= 0.4:
                    f *= 1.3
                f = max(0.02, min(1.0, f))
                w = 0.85 if a < 0.5 else 0.7
                pb = w * min(1.0, q / f) + (1 - w) * q
            elif s in callers_now:
                f = 0.45
                pb = 0.85 * min(1.0, q / f) + 0.15 * q
            elif s in prev_aggr or s in prev_callers or s == pf_raiser:
                f = 0.65
                pb = 0.85 * min(1.0, q / f) + 0.15 * q
            else:
                pb = q
            p_nb *= (1.0 - pb)

        # draws
        draw_eq = 0.0
        if street < 3:
            vals = improve_outs(hole, board, unseen)
            nx = len(unseen)
            outs = 0.0
            bsu = [0, 0, 0, 0]
            for c in board:
                bsu[c & 3] += 1
            brm = 0
            for c in board:
                brm |= 1 << (c >> 2)
            newcat = np.maximum(vals, mine) >> 20
            hole_by_suit = [[c >> 2 for c in hole if c & 3 == su] for su in range(4)]
            board_by_suit = [[c >> 2 for c in board if c & 3 == su] for su in range(4)]
            for idx in range(nx):
                nc = int(newcat[idx])
                if nc <= cat:
                    continue
                x = int(unseen[idx])
                if nc >= STRAIGHT:
                    wgt = 1.0
                    if nc == FLUSH:
                        su = x & 3
                        used_r = set(board_by_suit[su]) | {x >> 2}
                        missing = [r for r in range(12, -1, -1) if r not in used_r]
                        mytop = max(hole_by_suit[su]) if hole_by_suit[su] else -1
                        if missing and mytop == missing[0]:
                            wgt = 1.0
                        elif len(missing) > 1 and mytop == missing[1]:
                            wgt = 0.6
                        else:
                            wgt = 0.3
                    elif nc == STRAIGHT:
                        nm = brm | (1 << (x >> 2))
                        nut_top = -1
                        for top in range(12, 2, -1):
                            win = 0
                            for r in range(top - 4, top + 1):
                                win |= 1 << (r if r >= 0 else 12)
                            if bin(nm & win).count("1") >= 3:
                                nut_top = top
                                break
                        my_top = (int(max(vals[idx], mine)) >> 16) & 15
                        wgt = 1.0 if my_top >= nut_top else 0.55
                    if nc < FLUSH and bsu[x & 3] + 1 >= 3:
                        wgt *= 0.4
                    if nc < FULL_HOUSE and ((brm >> (x >> 2)) & 1 or len(board) - bin(brm).count("1") > 0):
                        wgt *= 0.6
                    outs += wgt
                elif nc >= TWO_PAIR and cat < TWO_PAIR:
                    outs += 0.25
                elif nc >= TRIPS:
                    outs += 0.35
            cards = 2 if street == 1 else 1
            draw_eq = 1.0 - (1.0 - min(outs, nx * 0.6) / nx) ** cards
        risk = {1: 0.20, 2: 0.10, 3: 0.0}[street]
        if q < 0.02:
            risk *= 0.5
        eq = p_nb * (1.0 - risk) + (1.0 - p_nb) * draw_eq
        self.dbg = {"eq": round(eq, 3), "q": round(q, 3), "pnb": round(p_nb, 3), "draw": round(draw_eq, 3), "cat": cat}
        n_opp = len(opps)

        if to_call == 0:
            # betting decision
            vt = 0.52 if n_opp == 1 else 0.50
            if len(obs["alive"]) == 2:
                vt = 0.50
            if eq >= vt:
                frac = 0.75 if street < 3 else 0.8
                if eq >= 0.8:
                    frac = 1.0
                return self._pot(frac)
            if draw_eq >= 0.30 and n_opp <= 2 and street < 3:
                return self._pot(0.75)
            if n_opp == 1:
                opp = opps[0]
                ftb = self.fold_to_bet(opp)
                if pf_raiser == me and self.rng.random() < max(0.0, min(0.75, (ftb - 0.2) * 1.8)):
                    return self._pot(0.6)
                if self.rng.random() < max(0.0, min(0.6, (ftb - 0.3) * 1.6)):
                    return self._pot(0.6)
            elif n_opp == 2 and street < 3:
                mf = min(self.fold_to_bet(x) for x in opps)
                if self.rng.random() < max(0.0, min(0.4, (mf - 0.35) * 1.2)):
                    return self._pot(0.6)
            return self._call()

        # facing a bet
        need = to_call / (pot + to_call)
        margin = 0.03
        if to_call >= 0.5 * stack:
            margin += 0.03
        bettor_total = max([obs["stacks"][x] + obs["bets"][x] for x in opps if x in aggr_now] or [0])
        margin += icm_margin(len(obs["alive"]), need, to_call, stack, pot, stack + obs["bets"][me], bettor_total)
        if eq >= 0.72 and ("raise" in obs["legal"]):
            return self._pot(1.0)
        if eq >= need + margin:
            return self._call()
        # implied odds for nut-ish draws when deep
        if street == 1 and draw_eq >= 0.28 and to_call <= 0.15 * stack and eq >= need - 0.06:
            return self._call()
        return self._fold()
