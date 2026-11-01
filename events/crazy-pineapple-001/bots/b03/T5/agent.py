import json
import os
import random
import time
from itertools import combinations, permutations

from .rank import Ranker

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CARD = {r + s: 4 * i + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre3.json")) as _f:
    PRE = json.load(_f)

PERMS = list(permutations(range(4)))
RANKER = Ranker()
VAL = RANKER.value


def pre_key(cards):
    best = None
    for perm in PERMS:
        k = tuple(sorted(((c >> 2), perm[c & 3]) for c in cards))
        if best is None or k < best:
            best = k
    return "".join("%x%d" % (rk, su) for rk, su in sorted(best, reverse=True))


def two_card_pct(cards):
    # rough strength for 2 cards (used only if table lookup fails)
    a, b = sorted((c >> 2 for c in cards), reverse=True)
    s = a + b + (8 if a == b else 0) + (2 if (cards[0] & 3) == (cards[1] & 3) else 0)
    return max(0.02, min(0.98, 1.0 - s / 40.0))


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config.get("seed", 0))
        self.points = config.get("points") or [100, 60, 40, 25, 15, 10, 5, 0]

    # ---------- helpers ----------
    def _safe(self, obs):
        if obs.get("phase") == "discard":
            return {"action": "discard", "cards": list(obs["hole"][:obs.get("n_discard") or 1])}
        return {"action": "check"} if "check" in obs.get("legal", ()) else {"action": "fold"}

    def act(self, obs):
        try:
            return self._act(obs)
        except Exception:
            return self._safe(obs)

    def observe(self, event):
        pass

    def _fold(self, obs):
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}

    def _call(self, obs):
        if obs["to_call"] == 0 or "call" not in obs["legal"]:
            return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
        return {"action": "call"}

    def _raise(self, obs, amount):
        legal = obs["legal"]
        if ("raise" not in legal and "bet" not in legal) or obs["max_raise_to"] <= 0:
            return self._call(obs)
        a = int(amount)
        lo, hi = obs["min_raise_to"], obs["max_raise_to"]
        if a < lo:
            a = lo
        if a > hi:
            a = hi
        # if most of the stack would go in, just shove
        me = obs["seat"]
        if a > 0.6 * (obs["stacks"][me] + obs["bets"][me]):
            a = hi
        return {"action": "raise", "amount": a}

    def _allin(self, obs):
        legal = obs["legal"]
        if ("raise" in legal or "bet" in legal) and obs["max_raise_to"] > 0:
            return {"action": "raise", "amount": obs["max_raise_to"]}
        return self._call(obs)

    # ---------- main ----------
    def _act(self, obs):
        t0 = time.perf_counter()
        hole = [CARD[c] for c in obs["hole"]]
        board = [CARD[c] for c in obs["board"]]
        if obs["phase"] == "discard":
            return self._discard(obs, hole, board)
        if obs["street_index"] == 0:
            return self._preflop(obs, hole)
        return self._postflop(obs, hole, board, t0)

    def _discard(self, obs, hole, board):
        k = obs.get("n_discard") or 1
        keepn = len(hole) - k
        if keepn <= 0:
            return {"action": "discard", "cards": list(obs["hole"][:k])}
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = max(0, 5 - len(board))
        rng = self.rng
        samples = [rng.sample(deck, need) for _ in range(24)] if need else [[]]
        best_ix, best_s = None, -1.0
        for ix in combinations(range(len(hole)), keepn):
            kept = [hole[i] for i in ix]
            s = 0.0
            for smp in samples:
                v = VAL(kept + board + smp)
                s += (v >> 20) * 1.0 + ((v >> 16) & 15) / 16.0
            if s > best_s:
                best_s, best_ix = s, ix
        return {"action": "discard", "cards": [obs["hole"][i] for i in range(len(hole)) if i not in best_ix]}

    def _hand_info(self, hole):
        if len(hole) == 3:
            v = PRE.get(pre_key(hole))
            if v:
                return v[0], v[1], v[2]
        p = two_card_pct(hole[:2])
        return 0.5, 0.35, p

    def _preflop(self, obs, hole):
        me = obs["seat"]
        bb = obs["bb"] or 1
        stacks, bets = obs["stacks"], obs["bets"]
        alive = obs["alive"]
        in_hand = obs["in_hand"]
        e1, e2, pct = self._hand_info(hole)
        mystack = stacks[me] + bets[me]
        opp_max = max([stacks[s] + bets[s] for s in in_hand if s != me] or [0])
        eff = min(mystack, opp_max)
        eff_bb = eff / bb
        to_call = obs["to_call"]
        pot = obs["pot"]

        # raises this street (excluding blinds)
        raises = 0
        for st, seat, act, amt in obs["history"]:
            if st == 0 and act == "raise":
                raises += 1
        # players yet to act behind me
        n = len(alive)
        bbs = obs["bb_seat"]
        if n == 2:
            btn = obs["button"]
            order = [btn] + [s for s in alive if s != btn]
        else:
            j = (alive.index(bbs) + 1) % n if bbs in alive else 0
            order = alive[j:] + alive[:j]
        i = order.index(me) if me in order else 0
        behind = len([s for s in order[i + 1:] if s in in_hand])
        is_bb = me == bbs

        req = to_call / float(pot + to_call) if to_call > 0 else 0.0
        # fewer players -> wider
        n_left = len([s for s in alive if stacks[s] + bets[s] > 0])

        if raises == 0:
            # unopened (maybe limpers)
            if eff_bb <= 13:
                push_pct = 0.94 / (behind + 0.8) * (10.0 / max(eff_bb, 2.0)) ** 0.6
                push_pct = min(1.0, max(0.05, push_pct))
                if pct <= push_pct:
                    return self._allin(obs)
                return self._fold(obs)
            open_pct = {0: 0.5, 1: 0.42, 2: 0.30, 3: 0.23, 4: 0.18, 5: 0.15}.get(behind, 0.12)
            if to_call == 0:
                # BB option
                if pct <= 0.10:
                    return self._raise(obs, 3.5 * bb + pot)
                return {"action": "check"}
            if pct <= open_pct:
                limpers = max(0, int(pot / bb) - 1.5)
                return self._raise(obs, 2.5 * bb + limpers * bb)
            if obs["sb_seat"] == me and pct <= 0.55 and n_left > 2:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        call_cost_frac = to_call / float(max(1, stacks[me]))
        if raises >= 2:
            if pct <= 0.025:
                return self._allin(obs)
            if pct <= 0.06 and req < 0.4:
                return self._call(obs)
            return self._fold(obs)
        # single raise
        if pct <= 0.035:
            if eff_bb <= 25:
                return self._allin(obs)
            raiser_to = max(bets)
            return self._raise(obs, 3 * raiser_to)
        if call_cost_frac >= 0.33 or eff_bb <= 13:
            # effectively push/fold call
            call_pct = 0.08 + max(0.0, 0.5 - req) * 1.1
            if n_left <= 3:
                call_pct += 0.05
            if pct <= call_pct:
                return self._allin(obs) if call_cost_frac > 0.5 else self._call(obs)
            return self._fold(obs)
        call_pct = 0.10 + max(0.0, 0.3 - req) * 0.5
        if is_bb:
            call_pct += 0.08
        if pct <= call_pct:
            return self._call(obs)
        return self._fold(obs)

    def _equity(self, hole, board, n_opp, t0):
        known = set(hole) | set(board)
        deck = [c for c in range(52) if c not in known]
        need = 5 - len(board)
        sim = max(1, min(n_opp, 2))
        flop = len(board) == 3
        oh = 3 if flop else 2
        draw = need + oh * sim
        sample = self.rng.sample
        clock = time.perf_counter
        wins = 0.0
        n = 0
        hole_pairs = list(combinations(hole, 2)) if len(hole) == 3 else [tuple(hole)]
        while n < 200:
            cards = sample(deck, draw)
            b = board + cards[:need]
            hv = max(VAL(list(p) + b) for p in hole_pairs)
            top = -1
            ties = 0
            for k in range(need, draw, oh):
                o = cards[k:k + oh]
                if oh == 3:
                    v = max(VAL([o[0], o[1]] + b), VAL([o[0], o[2]] + b), VAL([o[1], o[2]] + b))
                else:
                    v = VAL(o + b)
                if v > top:
                    top = v
                    ties = 1 if v == hv else 0
                elif v == top and v == hv:
                    ties += 1
            if hv > top:
                wins += 1.0
            elif hv == top:
                wins += 1.0 / (1 + ties)
            n += 1
            if n >= 12 and clock() - t0 > 0.00045:
                break
        eq = wins / n
        if n_opp > sim:
            eq = eq ** (n_opp / float(sim))
        return eq

    def _postflop(self, obs, hole, board, t0):
        me = obs["seat"]
        in_hand = obs["in_hand"]
        n_opp = max(1, len(in_hand) - 1)
        eq = self._equity(hole, board, n_opp, t0)
        to_call = obs["to_call"]
        pot = obs["pot"]
        stacks = obs["stacks"]
        st = obs["street_index"]
        share = eq * (n_opp + 1)
        # aggression: was I the last preflop/previous street raiser?
        last_aggr = -1
        bets_this = 0
        for h_st, seat, act, amt in obs["history"]:
            if act == "raise":
                if h_st < st:
                    last_aggr = seat
                else:
                    bets_this += 1
        if to_call == 0:
            if share >= 1.45 or eq >= 0.72:
                return self._raise(obs, 0.7 * pot)
            if last_aggr == me and n_opp == 1 and st == 1 and self.rng.random() < 0.55:
                return self._raise(obs, 0.5 * pot)
            if n_opp == 1 and eq >= 0.55 and self.rng.random() < 0.4:
                return self._raise(obs, 0.5 * pot)
            return {"action": "check"}
        req = to_call / float(pot + to_call)
        # opponent range is stronger when betting: discount equity
        bet_frac = to_call / float(max(1, pot - to_call))
        adj = eq - 0.06 - 0.06 * min(1.5, bet_frac) - 0.04 * max(0, bets_this - 1)
        if adj >= 0.72 and share >= 1.5:
            return self._raise(obs, max(obs["bets"]) * 2.5 + (pot - sum(obs["bets"])) * 0.3)
        if adj >= req:
            return self._call(obs)
        return self._fold(obs)
