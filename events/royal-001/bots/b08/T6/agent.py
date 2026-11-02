import random
from itertools import product

from .tables import PRE, FLOP, TURN, H2H

RI = {r: i for i, r in enumerate("TJQKA")}
SI = {s: i for i, s in enumerate("cdhs")}
P5 = (1, 5, 25, 125, 625)
_SAFE = True
P = dict(sf_short=0, deep_bb=30, deep_margin=0.04, open_adj=0.15, pf_bb=16, call_pen=0.12, bet_eq=0.58, bet_eq_hu=0.55, cbet=0.55, raise_eq=0.80, post_margin=0.03, call_c0=0.12, call_c1=0.6, ev_margin=0.0, bet_size=0.7, steal_k=0.5)
TYPES = [(a, b) for a in range(5) for b in range(a, 5)]


def _val(cnt):
    rd = (4, 3, 2, 1, 0)
    quads = [r for r in rd if cnt[r] == 4]
    trips = [r for r in rd if cnt[r] == 3]
    pairs = [r for r in rd if cnt[r] == 2]
    present = [r for r in rd if cnt[r] >= 1]
    if quads:
        q = quads[0]
        k = [r for r in present if r != q]
        return (7 << 20) | (q << 16) | ((k[0] if k else 0) << 12)
    if trips:
        t = trips[0]
        rest = [r for r in rd if r != t and cnt[r] >= 2]
        if rest:
            return (6 << 20) | (t << 16) | (rest[0] << 12)
    if all(c >= 1 for c in cnt):
        return 4 << 20
    if trips:
        t = trips[0]
        k = [r for r in present if r != t]
        return (3 << 20) | (t << 16) | (k[0] << 12) | (k[1] << 8)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        k = [r for r in present if r != p1 and r != p2]
        return (2 << 20) | (p1 << 16) | (p2 << 12) | ((k[0] if k else 0) << 8)
    if len(pairs) == 1:
        p = pairs[0]
        k = [r for r in present if r != p]
        v = (1 << 20) | (p << 16)
        for i, r in enumerate(k[:3]):
            v |= r << (12 - 4 * i)
        return v
    v = 0
    for i, r in enumerate(present[:5]):
        v |= r << (16 - 4 * i)
    return v


VAL = {}
for _c in product(range(5), repeat=5):
    if 5 <= sum(_c) <= 6:
        VAL[sum(_c[r] * P5[r] for r in range(5))] = _val(_c)

# preflop HU strength by type code (rank-only, average suited/offsuit)
PRE_T = {}
for (_a, _b, _s), _e in PRE.items():
    PRE_T.setdefault((_a, _b), []).append(_e)
# percentile of each type (fraction of combos with strictly lower HU equity)
_W = {(a, b): (6 if a == b else 16) for a, b in TYPES}
_HU = {t: sum(e[0] for e in PRE_T[t]) / len(PRE_T[t]) for t in TYPES}
PCT = {}
for _t in TYPES:
    PCT[_t] = sum(_W[u] for u in TYPES if _HU[u] < _HU[_t]) / 190.0 + _W[_t] / 380.0
TYPES_BY_STR = sorted(TYPES, key=lambda t: -_HU[t])


def parse(c):
    return RI[c[0]], SI[c[1]]


class Stats:
    __slots__ = ("hands", "vpip", "pfr", "pf_fold_vs_raise", "pf_faced_raise", "agg", "pas", "fold_post",
                 "faced_post", "shoves")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.pf_fold_vs_raise = 0
        self.pf_faced_raise = 0
        self.agg = 0
        self.pas = 0
        self.fold_post = 0
        self.faced_post = 0
        self.shoves = 0


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])
        self.points = config.get("points", [100, 25, 5, 0, 0, 0, 0, 0])
        self.st = {}
        self.pf_aggr = False
        self.hid = None
        self.start = {}

    # ------------------------------------------------------------------ stats
    def S(self, s):
        x = self.st.get(s)
        if x is None:
            x = self.st[s] = Stats()
        return x

    def observe(self, ev):
        try:
            if ev.get("type") != "hand_end":
                return
            hist = ev.get("history") or []
            seen = set()
            raised = False
            vp = set()
            pr = set()
            for st_i, s, a, amt in hist:
                if a in ("ante", "sb", "bb", "return", "discard"):
                    if a in ("sb", "bb"):
                        seen.add(s)
                    continue
                seen.add(s)
                x = self.S(s)
                if st_i == 0:
                    if raised:
                        if a == "fold":
                            x.pf_fold_vs_raise += 1
                            x.pf_faced_raise += 1
                        elif a in ("call", "raise"):
                            x.pf_faced_raise += 1
                    if a in ("call", "raise"):
                        vp.add(s)
                    if a == "raise":
                        pr.add(s)
                        raised = True
                        if ev.get("hand_id") == self.hid and s in self.start and amt >= 0.95 * self.start[s]:
                            x.shoves += 1
                else:
                    if a == "raise":
                        x.agg += 1
                    elif a == "call":
                        x.pas += 1
                    elif a == "fold":
                        x.fold_post += 1
                    if a in ("call", "fold", "raise"):
                        x.faced_post += 1 if a != "raise" else 0
            for s in seen:
                x = self.S(s)
                x.hands += 1
                if s in vp:
                    x.vpip += 1
                if s in pr:
                    x.pfr += 1
        except Exception:
            pass

    def vpip(self, s):
        x = self.S(s)
        return (x.vpip + 3 * 0.35) / (x.hands + 3)

    def pfr(self, s):
        x = self.S(s)
        return (x.pfr + 3 * 0.18) / (x.hands + 3)

    def fold_vs_raise(self, s):
        x = self.S(s)
        return (x.pf_fold_vs_raise + 4 * 0.6) / (x.pf_faced_raise + 4)

    def fold_post_rate(self, s):
        x = self.S(s)
        return (x.fold_post + 2 * 0.45) / (x.faced_post + 2)

    def aggr(self, s):
        x = self.S(s)
        return (x.agg + 2 * 0.4) / (x.agg + x.pas + 2)

    # ------------------------------------------------------------------ helpers
    def act(self, obs):
        if not _SAFE:
            return self._act(obs)
        try:
            a = self._act(obs)
        except Exception:
            a = None
        if a is None:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return a

    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _call(self, obs):
        if "call" in obs["legal"]:
            return {"action": "call"}
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _raise(self, obs, to):
        legal = obs["legal"]
        if "raise" not in legal and "bet" not in legal:
            return self._call(obs)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        to = int(to)
        if to >= hi * 0.85:
            to = hi
        to = max(lo, min(hi, to))
        return {"action": "raise" if "raise" in legal else "bet", "amount": to}

    def _act(self, obs):
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if obs["hand_id"] != self.hid:
            self.hid = obs["hand_id"]
            st, bt = obs["stacks"], obs["bets"]
            self.start = {s: st[s] + bt[s] for s in obs["alive"]}
        if obs["street_index"] == 0:
            return self.preflop(obs)
        return self.postflop(obs)

    # ------------------------------------------------------------------ preflop
    def range_eq(self, mytype, frac, deck):
        """equity of mytype vs top-frac of hands (by HU strength), with card removal."""
        mc = P5[mytype[0]] + P5[mytype[1]]
        need = frac
        tot = 0.0
        acc = 0.0
        wsum = 0.0
        ws = []
        for t in TYPES_BY_STR:
            a, b = t
            if a == b:
                w = deck[a] * (deck[a] - 1) / 2.0
            else:
                w = deck[a] * deck[b]
            ws.append((t, w))
            wsum += w
        if wsum <= 0:
            return 0.5
        lim = max(frac, 0.02) * wsum
        for t, w in ws:
            if w <= 0:
                continue
            take = min(w, lim - tot)
            if take <= 0:
                break
            e = H2H.get((mc, P5[t[0]] + P5[t[1]]))
            if e is None:
                continue
            acc += take * e
            tot += take
        return acc / tot if tot > 0 else 0.5

    def preflop(self, obs):
        me = self.seat
        hole = [parse(c) for c in obs["hole"]]
        r1, r2 = sorted((hole[0][0], hole[1][0]))
        suited = 1 if (hole[0][1] == hole[1][1] and r1 != r2) else 0
        t = (r1, r2)
        hu = PRE[(r1, r2, suited)][0]
        pct = PCT[t]  # 0..1, higher better
        deck = [4] * 5
        deck[r1] -= 1
        deck[r2] -= 1
        bb = obs["bb"] or 1
        stacks, bets = obs["stacks"], obs["bets"]
        stack = stacks[me]
        mybet = bets[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        opps = [s for s in obs["in_hand"] if s != me]
        if not opps:
            return self._call(obs)
        eff = min(stack + mybet, max(stacks[s] + bets[s] for s in opps))
        eff_bb = eff / bb
        hist = obs["history"]
        raises = [h for h in hist if h[0] == 0 and h[2] == "raise"]
        nr = len(raises)
        # players still to act after me (who haven't voluntarily acted or need to respond)
        alive = sorted(obs["alive"])
        n = len(alive)
        bbs = obs["bb_seat"]
        # preflop order: starting after bb
        if bbs in alive:
            i0 = (alive.index(bbs) + 1) % n
        else:
            i0 = 0
        order = [alive[(i0 + k) % n] for k in range(n)]
        acted = set(h[1] for h in hist if h[0] == 0 and h[2] in ("call", "raise", "fold", "check"))
        myi = order.index(me) if me in order else 0
        behind = [s for s in order[myi + 1:] if s in obs["in_hand"] and s not in acted and stacks[s] > 0]
        nb = len(behind)
        limpers = [h for h in hist if h[0] == 0 and h[2] == "call"]
        self.pf_aggr = False

        if nr == 0:
            # unopened (maybe limpers) -- open / steal / push
            if eff_bb <= P['pf_bb']:
                ev = self.shove_ev(obs, t, deck, behind, pot, min(stack, eff - mybet), eff_bb)
                if ev > P['ev_margin'] * pot:
                    self.pf_aggr = True
                    return self._raise(obs, stack + mybet)
                if to_call == 0:
                    return self._call(obs)
                # limp-call option small: complete in SB with decent hand
                return self._fold(obs)
            # deep: threshold on percentile by number behind
            need = {0: 0.0, 1: 0.35, 2: 0.42, 3: 0.50, 4: 0.58, 5: 0.64, 6: 0.68}.get(nb, 0.70) + P['open_adj']
            if n == 2:
                need = 0.12 + P['open_adj']
            elif n == 3 and nb <= 2:
                need -= 0.08
            if limpers:
                need += 0.06 * min(len(limpers), 2)
            # steal adjustment: average fold rate of players behind
            if behind:
                fr = sum(self.fold_vs_raise(s) for s in behind) / nb
                need -= (fr - 0.6) * P['steal_k']
            if pct >= need:
                self.pf_aggr = True
                size = (2.5 if eff_bb > 30 else 2.2) * P.get('open_x', 1.0) * bb + len(limpers) * bb
                if pct > 0.93 and eff_bb < 20:
                    size = stack + mybet
                return self._raise(obs, size)
            if to_call == 0:
                return self._call(obs)
            # SB complete with ok hands when cheap
            if to_call <= bb / 2 and pct >= 0.3 and nb <= 1:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        raise_to = last[3]
        rstack = stacks[raiser] + bets[raiser]
        is_allin = stacks[raiser] == 0
        # estimate raiser range fraction
        base = {1: 0.30, 2: 0.14}.get(nr, 0.08)
        pf = self.pfr(raiser)
        base *= max(0.5, min(2.5, pf / 0.18))
        r_bb = raise_to / bb
        if is_allin:
            # shoves: wider when short
            base = max(base, min(0.9, 0.08 + 1.4 * pf + (0.5 if r_bb <= 10 else 0.25 if r_bb <= 20 else 0.0)))
            xs = self.S(raiser)
            if xs.hands >= 8:
                sr = (xs.shoves + 0.3) / (xs.hands + 2.0)
                est = min(1.0, max(0.08, sr * (2.0 + 0.6 * (8 - min(n, 8)))))
                base = 0.5 * base + 0.5 * est
            if n == 2:
                base = max(base, 0.45)
        if r_bb > P['deep_bb'] and n > 2:
            base = min(base, max(0.08, 0.12 + 0.8 * (pf - 0.18)))
        base = max(0.05, min(1.0, base))
        eq = self.range_eq(t, base, deck)
        # multiway: other callers reduce
        callers = [h[1] for h in hist if h[0] == 0 and h[2] == "call" and h[1] in obs["in_hand"]]
        # pot odds
        need = to_call / float(pot + to_call)
        allin_call = to_call >= stack
        if nb > 0:
            eq_adj = eq * (0.93 ** nb)
        else:
            eq_adj = eq
        if len(callers) > 0:
            eq_adj *= 0.9 ** len(callers)
        # re-raise decision
        stack_after = stack - to_call
        if eq >= 0.60 and pct >= 0.85:
            self.pf_aggr = True
            if eff_bb <= 30 or nr >= 2:
                return self._raise(obs, stack + mybet)
            return self._raise(obs, raise_to * 3 + pot * 0.3)
        if allin_call or to_call >= 0.4 * (stack + mybet):
            # effectively committing
            if eq_adj >= need + 0.02 + (P['deep_margin'] if eff_bb > P['deep_bb'] and n > 2 else 0.0):
                return self._raise(obs, stack + mybet) if not allin_call else self._call(obs)
            return self._fold(obs)
        # light 3-bet shove when short with good fold equity
        if eff_bb <= 22 and nr == 1 and pct >= 0.65 and not is_allin:
            fr = self.fold_vs_raise(raiser)
            if fr > 0.5 or eq >= 0.52:
                self.pf_aggr = True
                return self._raise(obs, stack + mybet)
        # flat call: need odds plus realization penalty, implied odds when deep
        pen = P['call_pen'] if eff_bb > 25 else P['call_pen'] / 2
        sfm = P.get('sf_short', 0)
        if sfm == 1 and eff_bb <= P['pf_bb'] and nr == 1 and not is_allin and eq_adj >= need + pen:
            self.pf_aggr = True
            return self._raise(obs, stack + mybet)
        if sfm == 2 and eff_bb <= P['pf_bb'] and nr == 1 and not is_allin:
            # EV of re-shoving vs calling vs folding
            fp = min(0.85, max(0.25, self.fold_vs_raise(raiser)))
            for s in behind:
                fp *= 1.0 - min(0.5, P['call_c0'] + P['call_c1'] * self.vpip(s)) * 0.5
            crange = max(0.04, base * (1.0 - fp))
            eqc = self.range_eq(t, crange, deck)
            eff_tot = min(stack + mybet, stacks[raiser] + bets[raiser])
            mine = eff_tot - mybet
            final = pot + mine + max(0, eff_tot - bets[raiser])
            ev_shove = fp * pot + (1.0 - fp) * (eqc * final - mine)
            ev_call = (eq_adj - pen) * (pot + to_call) - to_call
            if ev_shove > 0 and ev_shove > ev_call:
                self.pf_aggr = True
                return self._raise(obs, stack + mybet)
        if eq_adj >= need + pen and to_call <= 0.25 * (stack + mybet):
            return self._call(obs)
        return self._fold(obs)

    def shove_ev(self, obs, t, deck, behind, pot, risk, eff_bb):
        """EV (chips) of shoving vs folding, given players behind may call."""
        if not behind:
            # everyone already folded / limped: treat limpers as callers
            pass
        pfold = 1.0
        ev_called = 0.0
        stacks = obs["stacks"]
        bb = obs["bb"] or 1
        players = list(behind)
        # limpers also may call
        for h in obs["history"]:
            if h[0] == 0 and h[2] == "call" and h[1] in obs["in_hand"] and h[1] != self.seat and h[1] not in players:
                players.append(h[1])
        if not players:
            return pot
        evc = 0.0
        for i, s in enumerate(players):
            # call fraction depends on their looseness and our shove size relative to their stack
            v = self.vpip(s)
            c = P['call_c0'] + P['call_c1'] * v
            sz = min(risk, stacks[s]) / bb
            if sz > 15:
                c *= 0.75
            elif sz < 6:
                c *= 1.3
            if s == obs["bb_seat"]:
                c *= 1.25
            if P.get('hu_c', 0) and len(obs["alive"]) == 2:
                c = max(c, P['hu_c'])
            c = max(0.05, min(0.85, c))
            eq = self.range_eq(t, c, deck)
            # multiway penalty for more players behind
            callsize = min(risk, stacks[s] + obs["bets"][s])
            win = pot + callsize
            ev_if = eq * (win + risk) - risk if callsize >= risk else eq * (pot + 2 * callsize) - callsize
            evc += pfold * c * ev_if
            pfold *= (1 - c)
        return pfold * pot + evc

    # ------------------------------------------------------------------ postflop
    def opp_types(self, deck):
        out = []
        for a, b in TYPES:
            if a == b:
                w = deck[a] * (deck[a] - 1) / 2.0
            else:
                w = deck[a] * deck[b]
            if w > 0:
                out.append((a, b, w))
        return out

    def postflop(self, obs):
        me = self.seat
        hole = [parse(c) for c in obs["hole"]]
        board = [parse(c) for c in obs["board"]]
        hr = sorted(r for r, _ in hole)
        br = [r for r, _ in board]
        deck = [4] * 5
        for r in hr + br:
            deck[r] -= 1
        bcode = sum(P5[r] for r in br)
        mcode = P5[hr[0]] + P5[hr[1]]
        street = obs["street_index"]
        stacks, bets = obs["stacks"], obs["bets"]
        stack = stacks[me]
        mybet = bets[me]
        to_call = obs["to_call"]
        pot = obs["pot"]
        bb = obs["bb"] or 1
        opps = [s for s in obs["in_hand"] if s != me]
        if not opps:
            return self._call(obs)
        hist = obs["history"]
        cur = [h for h in hist if h[0] == street]
        # opponent range fractions
        types = self.opp_types(deck)
        # strength of each opp type on this board (for range ordering)
        tab = FLOP if len(br) == 3 else TURN
        strength = []
        for a, b, w in types:
            e = tab.get((P5[a] + P5[b], bcode))
            strength.append((e[0] if e else 0.5, a, b, w))
        strength.sort(reverse=True)
        wsum = sum(x[3] for x in strength)
        # my outcome vs each opp type
        res = {}
        if len(br) == 4:
            mv = VAL.get(mcode + bcode, 0)
            for _, a, b, w in strength:
                ov = VAL.get(P5[a] + P5[b] + bcode, 0)
                res[(a, b)] = 1.0 if mv > ov else (0.5 if mv == ov else 0.0)
        else:
            for _, a, b, w in strength:
                d2 = deck[:]
                d2[a] -= 1
                d2[b] -= 1
                tw = te = 0.0
                oc = P5[a] + P5[b] + bcode
                mc = mcode + bcode
                for tr in range(5):
                    k = d2[tr]
                    if k <= 0:
                        continue
                    mv = VAL.get(mc + P5[tr], 0)
                    ov = VAL.get(oc + P5[tr], 0)
                    tw += k
                    te += k * (1.0 if mv > ov else (0.5 if mv == ov else 0.0))
                res[(a, b)] = te / tw if tw > 0 else 0.5

        def eq_vs(frac):
            lim = max(frac, 0.03) * wsum
            tot = acc = 0.0
            for _, a, b, w in strength:
                take = min(w, lim - tot)
                if take <= 0:
                    break
                acc += take * res[(a, b)]
                tot += take
            return acc / tot if tot > 0 else 0.5

        # per-opponent range
        fr = {}
        for s in opps:
            f = 1.0
            prev = [h for h in hist if h[1] == s and h[0] < street and h[0] >= 1]
            if any(h[2] == "raise" for h in prev):
                f = 0.55
            elif any(h[2] == "call" for h in prev):
                f = 0.7
            pre = [h for h in hist if h[1] == s and h[0] == 0]
            if street == 1 and any(h[2] == "raise" for h in pre):
                f = min(f, 1.0)
            pn = P.get('pf_narrow', 0)
            if pn:
                if any(h[2] == "raise" for h in pre):
                    f = min(f, 1.0 - pn * (1.0 - self.pfr(s)))
                elif any(h[2] == "call" for h in pre):
                    f = min(f, 1.0 - pn * (1.0 - self.vpip(s)))
            mine = [h for h in cur if h[1] == s and h[2] == "raise"]
            if mine:
                amt = mine[-1][3]
                prior_pot = max(1, pot - sum(bets))
                ratio = amt / float(prior_pot)
                ag = self.aggr(s)
                fb = 0.5 - 0.15 * min(ratio, 2.0) + (ag - 0.4) * 0.6
                if len(mine) >= 2 or len([h for h in cur if h[2] == "raise"]) >= 2:
                    fb *= 0.6
                f = min(f, max(0.1, min(0.8, fb)))
            fr[s] = f
        if to_call > 0 and to_call >= 0.45 * stack and stack > P['deep_bb'] * bb and len(obs['alive']) > 2:
            for s in opps:
                if any(h[1] == s and h[2] == 'raise' for h in cur):
                    fr[s] *= 0.75
        eqs = [eq_vs(fr[s]) for s in opps]
        eq_all = 1.0
        for e in eqs:
            eq_all *= e
        # tie-heavy: product underestimates a bit when many chop; fine
        eq_min = min(eqs)
        n_opp = len(opps)
        spr = stack / float(max(pot, 1))

        if to_call == 0:
            # check or bet
            fpr = sum(self.fold_post_rate(s) for s in opps) / n_opp
            vadj = 0.04 if fpr < 0.3 else (-0.02 if fpr > 0.6 else 0.0)
            if eq_all >= P['bet_eq'] - vadj or (n_opp == 1 and eq_all >= P['bet_eq_hu'] - vadj):
                size = P['bet_size'] * pot
                if spr < 1.3:
                    size = stack + mybet
                return self._raise(obs, mybet + size)
            # c-bet / bluff
            r = self.rng.random()
            if n_opp == 1 and street == 1 and self.pf_aggr and r < min(0.85, max(0.2, P['cbet'] + (fpr - 0.45) * 1.2)):
                return self._raise(obs, mybet + 0.5 * pot)
            if n_opp == 1 and street == 2 and eq_all >= 0.45 and r < 0.3:
                return self._raise(obs, mybet + 0.55 * pot)
            if n_opp == 1 and street == 2 and eq_all < 0.3 and r < max(0.0, min(0.5, (fpr - 0.4) * 1.5)):
                return self._raise(obs, mybet + 0.6 * pot)
            if n_opp == 2 and street == 1 and self.pf_aggr and fpr > 0.55 and r < 0.35:
                return self._raise(obs, mybet + 0.5 * pot)
            return self._call(obs)
        # facing a bet
        need = to_call / float(pot + to_call)
        allin = to_call >= stack
        if eq_all >= P['raise_eq'] and not allin:
            return self._raise(obs, mybet + to_call + max(pot + to_call, 0) * 0.9)
        margin = 0.0 if street == 2 else P['post_margin']
        if eq_all >= need + margin:
            return self._call(obs)
        return self._fold(obs)
