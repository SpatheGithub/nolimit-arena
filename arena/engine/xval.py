"""Cross-validate the engine against pokerkit (a test-only dependency).

Each case plays a random hand in our engine with an exploring random policy
(min-raises, all-ins, short stacks, short blinds and antes), then replays the
same cards and actions in pokerkit's tournament mode and compares, at every
decision, the player to act, the call amount, whether folding and raising are
legal and the raise bounds; at the end, every payoff and every contested pot.

One rule differs on purpose. pokerkit treats an all-in below the big blind
(or below the fixed-limit bet) as a full raise when it is the first wager of
a street; the arena follows TDA and doesn't let it reopen the betting. Those
decisions are counted as ``short_allin_below_floor`` instead of failing.

    python -m arena.engine.xval 100000 [--workers 9] [--seed 1]
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import random
import sys
import time
import warnings
from collections import Counter

from .cards import card_str
from .hand import Hand
from .spec import NLHE, Betting, CardUse, Ranking, Street, VariantSpec

HOLDEM_STREETS = NLHE.streets
FLHE = VariantSpec("flhe", HOLDEM_STREETS, betting=Betting("fixed_limit", (1, 1, 2, 2), 4))
PLO = VariantSpec("plo", (Street("preflop", hole=4), Street("flop", board=3),
                          Street("turn", board=1), Street("river", board=1)),
                  card_use=CardUse(2, 2), betting=Betting("pot_limit"))
SHORTDECK = VariantSpec("shortdeck", HOLDEM_STREETS, ranks="6789TJQKA", ranking=Ranking(order=(
    "high_card", "pair", "two_pair", "trips", "straight",
    "full_house", "flush", "quads", "straight_flush")))
ROYAL = VariantSpec("royal", HOLDEM_STREETS, ranks="TJQKA")

# variant -> (spec, max players, share of cases)
VARIANTS = {
    "nlhe": (NLHE, 8, 0.6),
    "flhe": (FLHE, 8, 0.1),
    "plo": (PLO, 8, 0.1),
    "shortdeck": (SHORTDECK, 8, 0.1),
    "royal": (ROYAL, 7, 0.1),
}
BLINDS = [(1, 2), (5, 10), (10, 20), (15, 30), (25, 50), (50, 100), (100, 200), (200, 400)]


class Mismatch(AssertionError):
    pass


class Diverged(Exception):
    """The hand took an action that only the arena's rules allow."""


def random_hand(rng: random.Random, variant: str) -> tuple[Hand, list]:
    """Play one random hand; return it and its decisions [(player, Legal, action)]."""
    spec, max_n, _ = VARIANTS[variant]
    n = rng.randint(2, max_n)
    sb, bb = rng.choice(BLINDS)
    ante = rng.choice([0, 0, 0, max(1, bb // 10), max(1, bb // 4), sb])
    stacks = []
    for _ in range(n):
        r = rng.random()
        if r < 0.12:
            stacks.append(rng.randint(1, max(1, sb + ante)))      # all-in on the ante or a blind
        elif r < 0.35:
            stacks.append(rng.randint(1, 4 * bb))                 # short
        else:
            stacks.append(rng.randint(5 * bb, 150 * bb))
    button = rng.randrange(n)
    deck = spec.deck()
    rng.shuffle(deck)
    hand = Hand(spec, stacks, button, sb, bb, ante, deck=deck)
    decisions = []
    while hand.to_act is not None:
        p, legal = hand.to_act, hand.legal()
        opts = [("cc",)] * 4
        if legal.fold:
            opts += [("f",)] * 2
        if legal.raise_max:
            opts += [("r", legal.raise_min)] * 2 + [("r", legal.raise_max)]
            opts += [("r", rng.randint(legal.raise_min, legal.raise_max))] * 2
        a = rng.choice(opts)
        decisions.append((p, legal, a))
        if a[0] == "f":
            hand.act("fold")
        elif a[0] == "cc":
            hand.act("call" if legal.call else "check")
        else:
            hand.act("raise", a[1])
    return hand, decisions


def _pk_game(variant: str):
    import pokerkit as pk
    return {"nlhe": pk.NoLimitTexasHoldem, "flhe": pk.FixedLimitTexasHoldem, "plo": pk.PotLimitOmahaHoldem,
            "shortdeck": pk.NoLimitShortDeckHoldem, "royal": pk.NoLimitRoyalHoldem}[variant]


def _floor_breach(hand: Hand, upto: int, street: int) -> bool:
    """True if, before decision ``upto``, this street's largest raise increment
    was positive but below the full-raise floor: pokerkit's CBRA < bb case."""
    floor = hand.bb_amount
    if hand.spec.betting.structure == "fixed_limit":
        k = hand.spec.betting_streets.index(street)
        floor = hand.spec.betting.fl_bets[k] * hand.bb_amount
    cur = 0
    if street == 0:
        cur = max((a for (s, _, act, a) in hand.history if s == 0 and act in ("sb", "bb")), default=0)
    largest = seen = 0
    for s, _, act, amount in hand.history:
        if act not in ("fold", "check", "call", "raise"):
            continue
        if seen == upto:
            break
        seen += 1
        if s == street and act == "raise":
            largest = max(largest, amount - cur)
            cur = amount
    return 0 < largest < floor


def _cumulative_short_allins(hand: Hand, upto: int, street: int, player: int) -> bool:
    """True if ``player`` already acted this street and, since their last
    action, faces two or more short all-ins and no full raise that together
    add up to a full raise. TDA reopens the betting for them; pokerkit
    re-closes it after the next short all-in."""
    cur = 0
    if street == 0:
        cur = max((a for (s, _, act, a) in hand.history if s == 0 and act in ("sb", "bb")), default=0)
    raise_size = hand.bb_amount
    since: list[tuple[int, bool]] | None = None
    seen = 0
    for s, p, act, amount in hand.history:
        if act not in ("fold", "check", "call", "raise"):
            continue
        if seen == upto:
            break
        seen += 1
        if s != street:
            continue
        if p == player:
            since = []
        if act == "raise":
            inc = amount - cur
            full = inc >= raise_size
            if full:
                raise_size = inc
            cur = amount
            if since is not None and p != player:
                since.append((inc, full))
    return (since is not None and len(since) >= 2 and not any(f for _, f in since)
            and sum(i for i, _ in since) >= raise_size)


def replay(hand: Hand, decisions: list, variant: str) -> Counter:
    """Replay in pokerkit; raise Mismatch on any disagreement. Returns tallies."""
    import pokerkit as pk
    tally: Counter = Counter()
    n, b = hand.n, hand.button
    order = [(b + 1 + k) % n for k in range(n)]        # pokerkit index k -> our player
    ours = {p: k for k, p in enumerate(order)}
    automations = (pk.Automation.ANTE_POSTING, pk.Automation.BET_COLLECTION,
                   pk.Automation.BLIND_OR_STRADDLE_POSTING, pk.Automation.HAND_KILLING,
                   pk.Automation.CHIPS_PULLING)
    game = _pk_game(variant)
    bets = (hand.bb_amount, 2 * hand.bb_amount) if variant == "flhe" else (hand.bb_amount,)
    holes = ["".join(card_str(c) for c in hand.hole[p]) for p in order]
    board = [card_str(c) for c in hand.board]
    pos, k = 0, 0
    pots_pk = None
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        state = game.create_state(automations, True, hand.ante, (hand.sb_amount, hand.bb_amount), *bets,
                                  [hand.start_stacks[p] for p in order], n, mode=pk.Mode.TOURNAMENT)
        street_of = []  # our street index per decision, from our history
        for s, _, act, _ in hand.history:
            if act in ("fold", "check", "call", "raise"):
                street_of.append(s)
        while state.status:
            if state.card_burning_status and state.can_burn_card("??"):
                state.burn_card("??")
            elif state.hole_dealee_index is not None:
                i = state.hole_dealee_index
                state.deal_hole(holes[i], i)
            elif state.board_dealing_count is not None:
                c = state.board_dealing_count
                if pos + c > len(board):
                    raise Mismatch(f"pokerkit wants board card {pos + c}; we dealt {len(board)}")
                state.deal_board("".join(board[pos:pos + c]))
                pos += c
            elif state.actor_index is not None:
                to_call = state.checking_or_calling_amount
                lo = state.min_completion_betting_or_raising_to_amount
                hi = state.max_completion_betting_or_raising_to_amount
                if (to_call == 0 and lo is None and not state.can_fold()
                        and (k >= len(decisions) or street_of[k] != state.street_index
                             or ours[decisions[k][0]] != state.actor_index)):
                    # pokerkit asks for a decision whose only legal move is a check;
                    # the arena skips it.
                    state.check_or_call()
                    tally["pointless_check"] += 1
                    continue
                if k >= len(decisions):
                    raise Mismatch(f"pokerkit expects a decision from {state.actor_index}; our hand ended")
                p, legal, a = decisions[k]
                if state.actor_index != ours[p]:
                    raise Mismatch(f"decision {k}: pokerkit actor {state.actor_index}, ours {ours[p]}")
                if to_call != legal.call or state.can_fold() != legal.fold:
                    raise Mismatch(f"decision {k}: pokerkit call {to_call} fold {state.can_fold()}; ours {legal}")
                if (lo is not None) != bool(legal.raise_max):
                    if lo is not None and _floor_breach(hand, k, street_of[k]):
                        tally["short_allin_below_floor"] += 1
                    elif lo is None and _cumulative_short_allins(hand, k, street_of[k], p):
                        tally["cumulative_short_allins"] += 1
                        if a[0] == "r":
                            raise Diverged  # our raise is illegal in pokerkit; stop here
                    else:
                        raise Mismatch(f"decision {k}: pokerkit raise {lo}..{hi}; ours {legal}")
                elif lo is not None and (lo, hi) != (legal.raise_min, legal.raise_max):
                    raise Mismatch(f"decision {k}: pokerkit raise {lo}..{hi}; ours {legal}")
                if a[0] == "f":
                    state.fold()
                elif a[0] == "cc":
                    state.check_or_call()
                else:
                    state.complete_bet_or_raise_to(a[1])
                k += 1
                tally["decisions"] += 1
            elif state.showdown_index is not None:
                if pots_pk is None:
                    pots_pk = [(pot.amount, tuple(order[i] for i in pot.player_indices)) for pot in state.pots]
                state.show_or_muck_hole_cards(True)
            elif state.can_push_chips():
                state.push_chips()
            else:
                raise Mismatch("pokerkit is waiting on an operation the replay doesn't handle")
    if k != len(decisions):
        raise Mismatch(f"{len(decisions) - k} of our decisions left over")
    pk_payoffs = [0] * n
    for kk, p in enumerate(order):
        pk_payoffs[p] = state.payoffs[kk]
    if pk_payoffs != hand.result.payoffs:
        raise Mismatch(f"payoffs: pokerkit {pk_payoffs}, ours {hand.result.payoffs}")
    if pots_pk is not None:
        contested = lambda pots: sorted((a, tuple(sorted(e))) for a, e in pots if len(e) > 1)
        if contested(pots_pk) != contested(hand.live_pots()):
            raise Mismatch(f"pots: pokerkit {pots_pk}, ours {hand.live_pots()}")
        tally["showdowns"] += 1
    tally["hands"] += 1
    return tally


def run_cases(seed: int, count: int) -> tuple[Counter, list[str]]:
    rng = random.Random(seed)
    names = list(VARIANTS)
    weights = [VARIANTS[v][2] for v in names]
    tally: Counter = Counter()
    failures: list[str] = []
    for i in range(count):
        variant = rng.choices(names, weights)[0]
        case_seed = rng.randrange(2**63)
        try:
            hand, decisions = random_hand(random.Random(case_seed), variant)
            t = replay(hand, decisions, variant)
        except Diverged:
            tally["diverged_hands"] += 1
            continue
        except Exception as e:  # a crash on either side is a failure too
            failures.append(f"{variant} case_seed={case_seed}: {type(e).__name__}: {e}")
            if len(failures) >= 20:
                break
            continue
        tally.update(t)
        tally[f"hands_{variant}"] += 1
    return tally, failures


def _job(args):
    return run_cases(*args)


def run(total: int, workers: int = 0, seed: int = 1) -> tuple[Counter, list[str]]:
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    chunks = [(seed * 1_000_003 + w, total // workers + (1 if w < total % workers else 0)) for w in range(workers)]
    if workers == 1:
        results = [run_cases(*chunks[0])]
    else:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = pool.map(_job, chunks)
    tally: Counter = Counter()
    failures: list[str] = []
    for t, f in results:
        tally.update(t)
        failures.extend(f)
    return tally, failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("hands", type=int, nargs="?", default=100_000)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    t0 = time.time()
    tally, failures = run(a.hands, a.workers, a.seed)
    print(f"{tally['hands']:,} hands, {tally['decisions']:,} decisions, {tally['showdowns']:,} showdowns "
          f"in {time.time() - t0:.1f}s")
    print("  by variant: " + ", ".join(f"{v} {tally[f'hands_{v}']:,}" for v in VARIANTS))
    print(f"  known differences: short all-in below the floor {tally['short_allin_below_floor']:,}, "
          f"cumulative short all-ins {tally['cumulative_short_allins']:,}, "
          f"pointless checks pokerkit asks for {tally['pointless_check']:,}; "
          f"hands stopped at a divergence {tally['diverged_hands']:,}")
    print(f"  mismatches: {len(failures)}")
    for f in failures[:10]:
        print("   ", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
