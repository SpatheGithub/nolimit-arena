"""b07: precomputed-equity NLHE bot (preflop tables + coarse postflop features)."""

import json
import os
import random

from ._common import CARD, Variant, features

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "_common.json")) as _f:
    _PRE = json.load(_f)["decks"]["std"]
PCT = tuple(x / 1e4 for x in _PRE["pct"])
EQM = tuple(tuple(x / 1e4 for x in row) for row in _PRE["eq_multi"])
try:
    with open(os.path.join(_DIR, "rangeeq.json")) as _f:
        _R = json.load(_f)
    RWS = tuple(_R["ws"])
    REQ = tuple(tuple(r) for r in _R["eq"])
except Exception:  # pragma: no cover
    RWS = None
    REQ = None

VAR = Variant(None)


def cls_of(c1, c2):
    a, b = c1 >> 2, c2 >> 2
    if a == b:
        return a * 13 + a
    hi, lo = (a, b) if a > b else (b, a)
    return hi * 13 + lo if (c1 & 3) == (c2 & 3) else lo * 13 + hi


def eq_vs_range(c, w):
    """Equity of class c vs top-w fraction of hands (interpolated)."""
    if REQ is None:
        # fallback: crude
        return max(0.05, min(0.95, 0.5 + (w * 0.5 - PCT[c]) * 0.6))
    ws = RWS
    row = REQ[c]
    if w <= ws[0]:
        return row[0]
    if w >= ws[-1]:
        return row[-1]
    for i in range(1, len(ws)):
        if w <= ws[i]:
            t = (w - ws[i - 1]) / (ws[i] - ws[i - 1])
            return row[i - 1] + t * (row[i] - row[i - 1])
    return row[-1]


PREM = 3.0  # scale of the ICM risk premium


def premium(n_alive, risk_frac, S):
    base = 0.0 if n_alive <= 2 else 0.035 if n_alive == 3 else 0.10
    if S < 10:
        base *= max(0.3, S / 10.0)
    return PREM * base * min(1.0, risk_frac)


# open-raise thresholds (percentile, 0 = best) by number of players behind
OPEN = {0: 0.34, 1: 0.48, 2: 0.37, 3: 0.29, 4: 0.23, 5: 0.19, 6: 0.16, 7: 0.14}


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.n_seats = config.get("seats", 8)
        # per-seat stats within this table
        self.dealt = {}
        self.pfr = {}      # preflop raises (hands with a raise)
        self.vpip = {}
        self.shove = {}    # preflop all-in raises
        self.aggr = {}     # postflop bets/raises
        self.passive = {}  # postflop calls/checks
        self.pf_aggr = False
        self.faced = {}    # postflop: times facing a bet
        self.folded = {}   # postflop: folds when facing a bet

    # ------------------------------------------------------------------
    def observe(self, event):
        try:
            if event.get("type") != "hand_end":
                return
            hist = event.get("history") or []
            seen = set()
            raised = set()
            vp = set()
            live_st = -1
            for st, seat, act, amt in hist:
                if st >= 1 and act in ("fold", "call", "raise"):
                    if live_st == st:
                        self.faced[seat] = self.faced.get(seat, 0) + 1
                        if act == "fold":
                            self.folded[seat] = self.folded.get(seat, 0) + 1
                    if act == "raise":
                        live_st = st
                if act in ("sb", "bb", "ante"):
                    seen.add(seat)
                    continue
                seen.add(seat)
                if st == 0:
                    if act == "raise":
                        raised.add(seat)
                        vp.add(seat)
                    elif act == "call":
                        vp.add(seat)
                else:
                    if act == "raise":
                        self.aggr[seat] = self.aggr.get(seat, 0) + 1
                    elif act in ("call", "check"):
                        self.passive[seat] = self.passive.get(seat, 0) + 1
            for s in seen:
                self.dealt[s] = self.dealt.get(s, 0) + 1
            for s in raised:
                self.pfr[s] = self.pfr.get(s, 0) + 1
            for s in vp:
                self.vpip[s] = self.vpip.get(s, 0) + 1
        except Exception:
            pass

    def _rate(self, d, seat, prior, n0=6.0):
        n = self.dealt.get(seat, 0)
        return (d.get(seat, 0) + prior * n0) / (n + n0)

    # ------------------------------------------------------------------
    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            if obs.get("phase") == "discard":
                return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
            return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    # helpers -------------------------------------------------------------
    def _fold(self):
        return {"action": "check"} if self.can_check else {"action": "fold"}

    def _call(self):
        return {"action": "check"} if self.to_call == 0 else {"action": "call"}

    def _raise_to(self, amt):
        if not self.can_raise:
            return self._call()
        a = int(amt)
        if a < self.min_to:
            a = self.min_to
        if a > self.max_to:
            a = self.max_to
        # if raise leaves us with little behind, just shove
        if self.max_to - a < 0.3 * a:
            a = self.max_to
        return {"action": "raise", "amount": a}

    def _allin(self):
        if self.can_raise:
            return {"action": "raise", "amount": self.max_to}
        return self._call()

    # ------------------------------------------------------------------
    def _act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs["n_discard"]])}
        legal = obs["legal"]
        self.can_check = "check" in legal
        self.can_raise = ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0
        self.to_call = obs["to_call"]
        self.min_to = obs["min_raise_to"]
        self.max_to = obs["max_raise_to"]
        me = obs["seat"]
        self.me = me
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if obs["street_index"] == 0:
            return self._preflop(obs, hole)
        return self._postflop(obs, hole, board)

    # ------------------------------------------------------------------
    def _preflop(self, obs, hole):
        me = self.me
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        alive = obs["alive"]
        my_total = stacks[me] + bets[me]
        opps = [s for s in in_hand if s != me]
        opp_max = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_total, opp_max)
        S = eff / bb
        c = cls_of(hole[0], hole[1])
        pct = PCT[c]
        pot = obs["pot"]
        to_call = self.to_call

        # parse history
        raises = 0
        raiser = -1
        limpers = 0
        callers_after = 0
        last_raise_to = bb
        for st, seat, act, amt in obs["history"]:
            if st != 0:
                continue
            if act == "raise":
                raises += 1
                raiser = seat
                last_raise_to = amt
                callers_after = 0
            elif act == "call":
                if raises == 0:
                    limpers += 1
                else:
                    callers_after += 1

        # players yet to act behind me
        n = len(alive)
        btn = obs["button"]
        bi = alive.index(btn) if btn in alive else 0
        if n == 2:
            order = [alive[bi], alive[1 - bi]]
        else:
            bbs = obs["bb_seat"]
            j = (alive.index(bbs) + 1) % n if bbs in alive else (bi + 3) % n
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = [s for s in order[i + 1:] if s in in_hand and stacks[s] > 0]
        nb = len(behind)
        is_bb = me == obs["bb_seat"]

        if raises == 0:
            # unopened or limped pot
            n_al = len(alive)
            if S <= 13 or (n_al == 2 and S <= 16):
                k = nb + limpers
                if k == 0:
                    # BB vs limps / SB completes: iso-shove strong
                    if pct <= 0.25 and self.can_raise:
                        return self._allin()
                    return self._call() if to_call == 0 else (self._call() if pct < 0.5 else self._fold())
                thr = (4.0 if n_al >= 4 else 6.0) / (S * (k ** 0.75))
                if pct <= thr:
                    return self._allin()
                if to_call == 0:
                    return self._call()
                # SB completing cheaply vs only BB
                if nb == 1 and limpers == 0 and to_call <= 0.5 * bb and pct < 0.35 and S > 8:
                    return self._call()
                return self._fold()
            thr = OPEN.get(nb, 0.12)
            if n_al == 2 and not is_bb:
                thr = 0.80
            elif n_al == 3 and not is_bb:
                thr = max(thr, 0.50 if nb == 2 else 0.60)
            if limpers:
                thr *= 0.7
            if pct <= thr:
                size = 2.5 * bb + limpers * bb
                if nb == 1 and not is_bb:
                    size = 3 * bb
                if is_bb:
                    size = 3.5 * bb + limpers * bb
                self.pf_aggr = True
                return self._raise_to(size)
            if to_call == 0:
                return self._call()
            if nb == 1 and limpers == 0 and to_call <= 0.5 * bb and pct < 0.45:
                return self._call()
            if limpers and to_call <= bb and pct < 0.3 and S > 25:
                return self._call()
            return self._fold()

        # facing a raise
        r_total = stacks[raiser] + bets[raiser] if raiser >= 0 else 0
        raiser_allin = raiser >= 0 and stacks[raiser] == 0
        r_bb = max(1.0, last_raise_to / bb)
        # estimate raiser's range width
        if raises == 1:
            w = 0.22
        elif raises == 2:
            w = 0.08
        else:
            w = 0.04
        if raiser >= 0:
            pfr = self._rate(self.pfr, raiser, 0.18)
            if raises == 1:
                w = max(w, min(1.0, pfr * 1.1))
            else:
                w = max(w, min(1.0, pfr * 0.5))
            rS = r_total / bb
            if raiser_allin and rS <= 15:
                w = max(w, min(1.0, 4.0 / rS))
        # bigger raise -> tighter (unless loose raiser)
        if r_bb > 6 and not raiser_allin:
            w *= 0.8
        if len(alive) == 2 and raises == 1:
            w = max(w, 0.6)
        w = max(0.02, min(1.0, w))
        eq = eq_vs_range(c, w)
        # multiway: other callers reduce equity
        extra = callers_after + max(0, nb - 0) * 0.15
        if callers_after:
            eq *= 0.85 ** callers_after
        need_total = my_total  # chips at risk if all-in
        call_amt = min(to_call, stacks[me])
        pot_after = pot + call_amt
        need = call_amt / pot_after if pot_after > 0 else 1.0

        # all-in situations: either facing all-in or we will be all-in by calling
        if raiser_allin or call_amt >= stacks[me] or eff <= last_raise_to * 1.0:
            # simple chip-EV with a small risk premium
            margin = 0.01 + premium(len(alive), eff / max(1, my_total), S)
            if eq >= need + margin:
                if self.can_raise and nb > 0 and eq > 0.6:
                    return self._allin()
                return self._call()
            return self._fold()

        # short: re-shove
        if S <= 25:
            # shove if good vs range considering fold equity
            if eq >= (0.46 if len(alive) <= 3 else 0.52) + 0.5 * premium(len(alive), 1.0, S) or pct <= 0.04:
                return self._allin()
            if call_amt <= 0.08 * eff and pct <= 0.30 and eq > need + 0.05:
                return self._call()
            return self._fold()

        # deep
        if pct <= 0.025 or (raises == 1 and eq >= 0.60):
            # 3-bet / 4-bet
            if raises >= 3:
                return self._allin()
            return self._raise_to(last_raise_to * 3 + callers_after * last_raise_to)
        is_pair = (hole[0] >> 2) == (hole[1] >> 2)
        if is_pair and call_amt <= 0.07 * eff:
            return self._call()
        if eq >= need + 0.08 and pct <= 0.15 and call_amt <= 0.15 * eff:
            return self._call()
        if is_bb and raises == 1 and len(alive) <= 3 and eq >= need + 0.02 and call_amt <= 3 * bb:
            return self._call()
        if is_bb and raises == 1 and eq >= need + 0.05 and pct <= 0.50 and call_amt <= 3 * bb:
            return self._call()
        return self._fold()

    # ------------------------------------------------------------------
    def _postflop(self, obs, hole, board):
        me = self.me
        bb = obs["bb"] or 1
        stacks = obs["stacks"]
        bets = obs["bets"]
        in_hand = obs["in_hand"]
        pot = obs["pot"]
        to_call = self.to_call
        st = obs["street_index"]
        opps = [s for s in in_hand if s != me]
        n_opp = len(opps)
        live_opps = [s for s in opps if stacks[s] > 0]
        my_stack = stacks[me]
        opp_max = max([stacks[s] + bets[s] for s in opps], default=0)
        eff = min(my_stack + bets[me], opp_max)

        s, outs, wet, cat = features(VAR, hole, board)
        # draw equity
        cards_left = 5 - len(board)
        if cards_left == 2:
            deq1 = outs * 0.021
            deq2 = outs * 0.04
        elif cards_left == 1:
            deq1 = deq2 = outs * 0.022
        else:
            deq1 = deq2 = 0.0
        # multiway discount
        sm = s - 0.07 * max(0, n_opp - 1)

        # history this street
        hist = obs["history"]
        bettor = -1
        n_raises = 0
        pf_raiser = -1
        for h_st, seat, act, amt in hist:
            if act == "raise":
                if h_st == st:
                    bettor = seat
                    n_raises += 1
                elif h_st == 0:
                    pf_raiser = seat
        i_was_aggr = pf_raiser == me

        spr = eff / max(1, pot)
        # opponents' fold-to-bet rate (min over opponents = stickiest caller)
        fr = 1.0
        for o in opps:
            f = (self.folded.get(o, 0) + 1.6) / (self.faced.get(o, 0) + 4.0)
            if f < fr:
                fr = f
        bluff_mult = 0.0 if fr < 0.28 else 0.6 if fr < 0.4 else 1.0 if fr < 0.55 else 1.4
        vsize = 0.85 if fr < 0.3 else 0.7 if fr < 0.45 else 0.6

        if to_call == 0:
            # betting decision
            if not self.can_raise:
                return self._call()
            if sm >= 0.80:
                frac = 0.75 if spr > 1.2 else 1.0
                if spr <= 1.0:
                    return self._allin()
                return self._raise_to(frac * pot)
            if sm >= 0.58:
                if n_opp <= 2 or sm >= 0.66:
                    return self._raise_to(vsize * pot)
                return self._call()
            if outs >= 8 and cards_left > 0 and n_opp <= 2 and self.rng.random() < 0.6 * max(0.5, bluff_mult):
                return self._raise_to(0.6 * pot)
            if i_was_aggr and st == 1 and n_opp == 1 and not wet and self.rng.random() < 0.55 * bluff_mult:
                return self._raise_to(0.45 * pot)
            if st == 3 and n_opp == 1 and sm >= 0.45 and self.rng.random() < 0.3 * bluff_mult:
                return self._raise_to(0.4 * pot)
            return self._call()

        # facing a bet
        call_amt = min(to_call, my_stack)
        pot_after = pot + call_amt
        need = call_amt / pot_after
        bet_frac = to_call / max(1, pot - to_call)
        # tighten vs large bets and raises; loosen vs maniacs
        agg = 0.0
        if bettor >= 0:
            a = self.aggr.get(bettor, 0)
            p = self.passive.get(bettor, 0)
            agg = (a + 1.0) / (a + p + 4.0)  # postflop aggression freq
        penalty = 0.08 + 0.06 * min(2.0, bet_frac) + 0.08 * (n_raises - 1)
        penalty -= 0.25 * max(0.0, agg - 0.35)
        if penalty < 0:
            penalty = 0
        all_in_call = call_amt >= my_stack
        draw_eq = deq2 if all_in_call else deq1
        eq_est = max(sm - penalty, 0) + draw_eq * (1 - sm)
        if sm >= 0.86 or (sm >= 0.76 and n_raises <= 1 and bet_frac <= 0.8):
            if self.can_raise and (n_raises < 3 or sm >= 0.94):
                if spr <= 2.5 or sm >= 0.94:
                    return self._allin()
                return self._raise_to(to_call * 3 + pot * 0.3)
            return self._call()
        if call_amt > 0.25 * (my_stack + bets[me]):
            need += premium(len(obs["alive"]), min(1.0, eff / max(1, my_stack + bets[me])), eff / bb)
        if eq_est >= need:
            return self._call()
        return self._fold()
