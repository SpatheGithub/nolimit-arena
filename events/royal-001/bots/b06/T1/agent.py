"""b06 royal bot: rank-only exact equity tables + range narrowing + push/fold EV."""
import json
import os
import random

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.json")))
HOLES = [tuple(h) for h in _D["holes"]]
PRE_EQ = _D["pre_eq"]
PRE_W = _D["pre_w"]
PRE_MULTI = _D["pre_multi"]
POST = {int(k): (v[0], v[1]) for k, v in _D["post"].items()}
del _D
RIDX = {"T": 0, "J": 1, "Q": 2, "K": 3, "A": 4}
P5 = (1, 5, 25, 125, 625)


def _code(c):
    return c[0] + 5 * c[1] + 25 * c[2] + 125 * c[3] + 625 * c[4]


HCODE = [_code(h) for h in HOLES]
HIDX = {HCODE[i]: i for i in range(15)}
# strength of each (hole, board) vs a random hand
STR = {}
for _k, (_e, _w) in POST.items():
    _s = sum(_w)
    STR[_k] = sum(a * b for a, b in zip(_e, _w) if b) / _s if _s else 0.5
# preflop order by heads-up equity vs random
ORDER = sorted(range(15), key=lambda i: -PRE_MULTI[i][1])
NCOMBO = [6 if max(h) == 2 else 16 for h in HOLES]
# percentile (top fraction at the end of class) for each class
PCT = [0.0] * 15
_c = 0
for _i in ORDER:
    _c += NCOMBO[_i]
    PCT[_i] = _c / 190.0


def counts(cards):
    c = [0, 0, 0, 0, 0]
    for x in cards:
        c[RIDX[x[0]]] += 1
    return c


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        n = config.get("seats", 8)
        self.n = n
        # per-seat stats
        self.hands = [0] * n
        self.vpip = [0] * n
        self.pfr = [0] * n
        self.aggr = [0] * n  # postflop bets/raises
        self.pas = [0] * n   # postflop calls/checks
        self.shoves = [0] * n
        # fold-to-bet tracking: [folds, continues] preflop vs raise, postflop vs bet
        self.pf_fold = [0] * n
        self.pf_cont = [0] * n
        self.po_fold = [0] * n
        self.po_cont = [0] * n

    # ---------------- opponent model ----------------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            vp = set()
            pr = set()
            cur_st = -1
            bet_open = False
            for h in hist:
                st, s, a = h[0], h[1], h[2]
                if st != cur_st:
                    cur_st = st
                    bet_open = False
                if s is None or not (0 <= s < self.n):
                    continue
                if a in ("sb", "bb", "ante"):
                    seen.add(s)
                    continue
                seen.add(s)
                if st == 0:
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                    if bet_open and s != self.seat:
                        if a == "fold":
                            self.pf_fold[s] += 1
                        elif a in ("call", "raise"):
                            self.pf_cont[s] += 1
                else:
                    if a == "raise":
                        self.aggr[s] += 1
                    elif a in ("call", "check"):
                        self.pas[s] += 1
                    if bet_open and s != self.seat:
                        if a == "fold":
                            self.po_fold[s] += 1
                        elif a in ("call", "raise"):
                            self.po_cont[s] += 1
                if a == "raise":
                    bet_open = True
            for s in seen:
                self.hands[s] += 1
            for s in vp:
                self.vpip[s] += 1
            for s in pr:
                self.pfr[s] += 1
        except Exception:
            pass

    def pfr_rate(self, s):
        return (self.pfr[s] + 0.22 * 4) / (self.hands[s] + 4)

    def vpip_rate(self, s):
        return (self.vpip[s] + 0.35 * 4) / (self.hands[s] + 4)

    def aggr_rate(self, s):
        return (self.aggr[s] + 0.4 * 4) / (self.aggr[s] + self.pas[s] + 4)

    def po_fold_rate(self, s):
        return (self.po_fold[s] + 0.3 * 4) / (self.po_fold[s] + self.po_cont[s] + 4)

    def pf_fold_rate(self, s):
        return (self.pf_fold[s] + 0.6 * 4) / (self.pf_fold[s] + self.pf_cont[s] + 4)

    # ---------------- equity helpers ----------------
    def pre_eq_range(self, i, frac):
        """Equity of class i vs top-frac of preflop classes (blocker weighted)."""
        frac = max(0.03, min(1.0, frac))
        num = 0.0
        den = 0.0
        cum = 0.0
        row_e = PRE_EQ[i]
        row_w = PRE_W[i]
        for j in ORDER:
            nc = NCOMBO[j] / 190.0
            if cum >= frac:
                break
            part = 1.0 if cum + nc <= frac else (frac - cum) / nc
            cum += nc
            w = row_w[j] * part
            num += w * row_e[j]
            den += w
        return num / den if den > 0 else PRE_MULTI[i][1]

    def post_eq(self, hc, bc, opp_ranges):
        """hc/bc: count lists. opp_ranges: list of (pre_frac, post_frac).
        Returns approx equity vs all opponents."""
        key = _code(hc) * 3125 + _code(bc)
        ent = POST.get(key)
        if ent is None:
            return 0.5
        eqs, ws = ent
        bcode = _code(bc)
        # strengths of opp classes on this board
        strs = []
        for j in range(15):
            if ws[j]:
                strs.append((STR.get(HCODE[j] * 3125 + bcode, 0.5), j))
        strs.sort(reverse=True)
        total = 1.0
        for pre_frac, post_frac in opp_ranges:
            # weight = combos * preflop membership
            wl = []
            tw = 0.0
            for sv, j in strs:
                pm = 1.0
                if pre_frac < 1.0:
                    p = PCT[j]
                    lo = p - NCOMBO[j] / 190.0
                    if lo >= pre_frac:
                        pm = 0.15  # outside range: small residual weight
                    elif p > pre_frac:
                        pm = 0.15 + 0.85 * (pre_frac - lo) / (p - lo)
                w = ws[j] * pm
                wl.append((w, j))
                tw += w
            if tw <= 0:
                continue
            # keep top post_frac of weight (by board strength)
            keep = post_frac * tw
            cum = 0.0
            num = 0.0
            den = 0.0
            for w, j in wl:
                if cum >= keep:
                    # residual weight for bluffs
                    w2 = w * 0.12
                else:
                    w2 = w if cum + w <= keep else (keep - cum) + (w - (keep - cum)) * 0.12
                cum += w
                num += w2 * eqs[j]
                den += w2
            e = num / den if den > 0 else 0.5
            total *= e
        return total

    # ---------------- action helpers ----------------
    def raise_to(self, obs, amt):
        legal = obs["legal"]
        mx = obs.get("max_raise_to", 0) or 0
        mn = obs.get("min_raise_to", 0) or 0
        if mx <= 0 or not ("raise" in legal or "bet" in legal):
            if "call" in legal:
                return {"action": "call"}
            return {"action": "check"}
        amt = int(amt)
        if amt >= mx * 0.8:
            amt = mx
        amt = max(mn, min(mx, amt))
        name = "raise" if "raise" in legal else "bet"
        return {"action": name, "amount": amt}

    def passive(self, obs):
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"}

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if "check" in obs.get("legal", []):
                return {"action": "check"}
            return {"action": "fold"}

    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs)

    # ---------------- preflop ----------------
    def preflop(self, obs):
        me = self.seat
        hc = counts(obs["hole"])
        i = HIDX[_code(hc)]
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        alive = obs["alive"]
        in_hand = obs["in_hand"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        my_stack = stacks[me]
        my_bet = bets[me]
        n_alive = len(alive)
        # order of action preflop: left of BB
        srt = sorted(alive)
        if n_alive == 2:
            first = obs["button"]
        else:
            k = srt.index(obs["bb_seat"]) if obs["bb_seat"] in srt else 0
            first = srt[(k + 1) % n_alive]
        fi = srt.index(first)
        order = srt[fi:] + srt[:fi]
        my_pos = order.index(me)
        behind = [s for s in order[my_pos + 1:] if s in in_hand]
        # raisers this hand (preflop)
        raises = [h for h in obs["history"] if h[0] == 0 and h[2] == "raise"]
        n_raises = len(raises)
        others_in = [s for s in in_hand if s != me]
        max_opp = max([stacks[s] + bets[s] for s in others_in] or [0])
        eff = min(my_stack + my_bet, max_opp)
        eff_bb = eff / bb
        pct = PCT[i]

        if n_raises == 0:
            # unopened (maybe limpers)
            limpers = [h[1] for h in obs["history"] if h[0] == 0 and h[2] == "call"]
            nb = len(behind)
            if to_call == 0:
                # BB option
                if pct <= 0.16 + 0.04 * (n_alive <= 4):
                    if eff_bb <= 12:
                        return self.raise_to(obs, obs["max_raise_to"])
                    return self.raise_to(obs, pot + bb * 2)
                return {"action": "check"}
            # push/fold zone
            if eff_bb <= 14 + 2 * (nb <= 2):
                ev = self.push_ev(i, obs, behind, pot, eff)
                if ev > 0:
                    return self.raise_to(obs, obs["max_raise_to"])
                if not limpers and nb <= 1 and pct <= 0.65 and eff_bb > 8:
                    pass
                return self.passive(obs)
            # open thresholds by players behind
            thr = {0: 1.0, 1: 0.72, 2: 0.52, 3: 0.42, 4: 0.34, 5: 0.28, 6: 0.24}.get(nb, 0.22)
            thr -= 0.06 * len(limpers)
            if behind:
                favg = sum(self.pf_fold_rate(s) for s in behind) / len(behind)
                thr += (favg - 0.6) * 0.6
            if pct <= thr:
                size = bb * (2.5 + len(limpers)) if nb > 1 else bb * 3
                return self.raise_to(obs, size)
            # complete SB cheaply with decent hands vs passive BB
            if nb == 1 and to_call <= bb / 2 and pct <= 0.85:
                return self.call(obs)
            return self.passive(obs)

        # facing raise(s)
        last_raiser = raises[-1][1]
        rf = self.pfr_rate(last_raiser)
        rng_frac = min(1.0, max(0.06, rf * 1.1))
        if n_raises >= 2:
            rng_frac *= 0.45
        # all-in raise: shoving range often wider at short stacks
        raiser_allin = stacks[last_raiser] == 0
        raise_amt = raises[-1][3]
        if raiser_allin:
            rbb = raise_amt / bb
            if rbb <= 15:
                rng_frac = max(rng_frac, min(0.7, 0.18 + 2.0 / max(rbb, 1)))
        e = self.pre_eq_range(i, rng_frac)
        # other callers already in pot
        callers = [s for s in others_in if s != last_raiser and bets[s] > 0 and s not in (obs["sb_seat"], obs["bb_seat"])]
        n_opp = 1 + len(callers)
        if n_opp > 1:
            e = e * PRE_MULTI[i][n_opp] / PRE_MULTI[i][1]
        call_amt = min(to_call, my_stack)
        pot_after = pot + call_amt
        need = call_amt / pot_after if pot_after > 0 else 0
        risk_frac = call_amt / max(1, my_stack + my_bet)
        nb = len(behind)
        margin = 0.02 * nb
        # commit if calling puts in most of the stack
        if risk_frac > 0.4 or eff_bb <= 18:
            # consider re-shove
            if obs["max_raise_to"] > 0 and not raiser_allin and e > need + margin - 0.02:
                # shoving gives fold equity
                return self.raise_to(obs, obs["max_raise_to"])
            if e > need + margin:
                return self.call(obs)
            return self.passive(obs)
        # deep: 3bet value / call / fold
        if e >= 0.60 and obs["max_raise_to"] > 0:
            return self.raise_to(obs, raise_amt * 3 + bb * len(callers))
        # implied: call if equity decent and price ok
        if e > need + 0.06 + margin and call_amt <= 0.2 * (my_stack + my_bet):
            return self.call(obs)
        return self.passive(obs)

    def push_ev(self, i, obs, behind, pot, eff):
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        me = self.seat
        R = eff - bets[me]
        if R <= 0:
            return 1.0
        pnc = 1.0
        qsum = 0.0
        for s in behind:
            rbb = max(1.0, R / bb)
            q = 0.08 + 0.9 / rbb
            if s == obs["bb_seat"]:
                q += 0.06
            v = self.vpip_rate(s)
            cf = (1.0 - self.pf_fold_rate(s)) / 0.4
            q *= max(0.5, min(2.0, 0.5 * (v / 0.35 + cf)))
            q = min(0.85, q)
            pnc *= (1 - q)
            qsum += q
        qavg = qsum / max(1, len(behind))
        e = self.pre_eq_range(i, qavg)
        ev = pnc * pot + (1 - pnc) * (e * (pot + 2 * R) - R)
        return ev

    # ---------------- postflop ----------------
    def postflop(self, obs):
        me = self.seat
        hc = counts(obs["hole"])
        bc = counts(obs["board"])
        street = obs["street_index"]
        stacks = obs["stacks"]
        bets = obs["bets"]
        pot = obs["pot"]
        to_call = obs["to_call"]
        bb = obs["bb"] or 1
        in_hand = obs["in_hand"]
        others = [s for s in in_hand if s != me]
        hist = obs["history"]
        my_stack = stacks[me]
        # preflop ranges
        pre_r = {}
        for s in others:
            pr = [h for h in hist if h[0] == 0 and h[1] == s and h[2] == "raise"]
            if pr:
                pre_r[s] = min(1.0, max(0.08, self.pfr_rate(s) * 1.1))
            else:
                pre_r[s] = min(1.0, max(0.3, self.vpip_rate(s) * 1.3))
        # postflop aggression of each opponent on current & previous streets
        ranges = []
        for s in others:
            pf = 1.0
            for h in hist:
                if h[0] >= 1 and h[1] == s:
                    if h[2] == "raise":
                        ar = self.aggr_rate(s)
                        # aggressive players have wider betting ranges
                        f = 0.45 + 0.5 * (ar - 0.4)
                        if h[0] == street:
                            pf *= max(0.25, min(0.8, f))
                        else:
                            pf *= max(0.4, min(0.9, f + 0.15))
                    elif h[2] == "call":
                        pf *= 0.8
            if stacks[s] == 0:
                pf = max(pf, 0.3)
            ranges.append((pre_r[s], max(0.12, pf)))
        e = self.post_eq(hc, bc, ranges)
        n_opp = len(others)
        # straight flush check (suited royal in my 6 cards) -> nuts
        if len(obs["board"]) == 4:
            allc = obs["hole"] + obs["board"]
            for su in "cdhs":
                if sum(1 for x in allc if x[1] == su) >= 5:
                    e = 1.0
        eff = min(my_stack, max([stacks[s] for s in others] or [0]))
        spr = eff / max(1, pot)
        acted_after = self._in_position(obs, others)
        fr = min(self.po_fold_rate(s) for s in others) if others else 0.3
        if to_call == 0:
            vthr = 0.60 + 0.06 * (n_opp - 1)
            if e >= vthr:
                frac = 0.6 if e < 0.8 else 0.8
                if fr < 0.25:
                    frac += 0.2  # calling stations: bet bigger
                amt = int(pot * frac)
                if spr < 1.3 or amt > eff * 0.6:
                    return self.raise_to(obs, obs["max_raise_to"])
                return self.raise_to(obs, max(amt, bb))
            # bluff only vs opponents that fold enough
            if n_opp <= 2 and e < 0.5:
                need_f = 0.55 / 1.55 + 0.05
                if n_opp == 2:
                    fr = fr * fr
                pb = 0.0
                if fr > need_f:
                    pb = 0.6 if acted_after else 0.35
                elif street == 1 and e > 0.33 and n_opp == 1:
                    pb = 0.08
                if pb and self.rng.random() < pb:
                    amt = int(pot * 0.55)
                    if amt > eff * 0.6:
                        return {"action": "check"}
                    return self.raise_to(obs, max(amt, bb))
            return {"action": "check"}
        # facing a bet
        call_amt = min(to_call, my_stack)
        need = call_amt / (pot + call_amt)
        margin = 0.03 if street == 1 else 0.0
        if n_opp > 1:
            margin += 0.03
        if e >= 0.78 and obs["max_raise_to"] > 0:
            cur = max(bets)
            amt = cur * 2.5 + pot * 0.3
            if amt > eff * 0.5:
                return self.raise_to(obs, obs["max_raise_to"])
            return self.raise_to(obs, amt)
        if e > need + margin:
            return self.call(obs)
        return self.passive(obs)

    def _in_position(self, obs, others):
        btn = obs["button"]
        n = self.n
        # postflop order starts left of button; last = in position
        def dist(s):
            return (s - btn - 1) % n
        me_d = dist(self.seat)
        return all(dist(s) < me_d for s in others)
