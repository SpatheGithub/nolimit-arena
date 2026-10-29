"""The bot interface: what a bot receives and what it returns.

A bot is a package (a directory with ``agent.py``) defining:

    class Agent:
        def __init__(self, config: dict): ...        # once per table
        def act(self, obs: dict) -> dict: ...        # each decision, 1 ms CPU
        def observe(self, event: dict) -> None: ...  # optional, after each hand

Everything passed in is plain Python data (dicts, lists, ints, strs). Cards
are two-character strings: rank "23456789TJQKA", suit "cdhs", e.g. "As".
Seat ids are table seats 0..seats-1; they are reshuffled at every table.

config (built by table_config):
    variant          the variant spec as a dict (streets, deck, card use, ranking, betting)
    rules            today's rules text (EVENT.md), "" when unavailable
    points           points by finishing place, 1st first: [100, 60, 40, 25, 15, 10, 5, 0]
    blinds           blind schedule, one [sb, bb, ante] per level: [[10, 20, 0], [15, 30, 0], ...]
    level_hands      hands per blind level: 25
    hand_cap         the table ends after this many hands: 200
    seats            seats at the table: 8
    starting_stack   2000
    seat             your seat id: 3
    decision_limit_ms  CPU time allowed per act() call: 1.0
    seed             an int for your own random.Random / numpy generator

obs (built by build_obs), for example:
    hand_id          5               this table's hand number, from 1
    street           "flop"          current street's name (variant streets)
    street_index     1
    phase            "bet"           "bet", or "discard" in variants with discards
    seat             3               you
    hole             ["As", "Kd"]
    board            ["7h", "8h", "9c"]
    pot              340             all chips committed this hand, this street's bets included
    pots             [{"amount": 300, "eligible": [1, 3, 5]}, {"amount": 40, "eligible": [3, 5]}]
                                     main pot first; eligible = seats still in that contributed
    stacks           [1800, 0, 950, ...]  chips behind, by seat (0 = busted or all-in)
    bets             [20, 0, 40, ...]     chips put in on this street, by seat
    in_hand          [1, 3, 5]       seats that haven't folded (all-in players included)
    alive            [1, 3, 5, 6]    seats dealt into this hand
    button           5
    sb_seat          6
    bb_seat          1
    legal            ["fold", "call", "raise"]   or ["check", "bet"], ["discard"], ...
    to_call          20              chips a call adds (0 when you can check)
    min_raise_to     60              raise-to bounds for this street (0 when you can't raise)
    max_raise_to     1820
    n_discard        0               hole cards to discard in a discard phase
    history          [[0, 6, "sb", 10], [0, 1, "bb", 20], [0, 3, "raise", 60], ...]
                                     this hand: [street_index, seat, action, amount]; actions
                                     are ante, sb, bb, fold, check, call, raise, discard and
                                     return (uncalled chips handed back). A raise's amount is
                                     the raise-to total; a call's is the chips added.
    hands_played     4               hands finished at this table before this one
    level            0               current blind level, from 0
    sb, bb, ante     10, 20, 0       this hand's blinds and ante
    hands_to_next_level  21          hands before the blinds go up (after this one)
    hands_left       196             hands left at this table, this one included
    places           {2: [8, 8]}     places decided so far: seat -> [best, worst]
                                     (equal unless players tied)
    starting_stack   2000

action (returned by act):
    {"action": "fold"} / {"action": "check"} / {"action": "call"}
    {"action": "raise", "amount": 300}   raise-to total for this street; "bet" is the same
    {"action": "allin"}                  raise to your maximum, or call if you can't raise
    {"action": "discard", "cards": ["2c"]}   in a discard phase
Anything else, an exception, or more than the CPU limit becomes a fold, or a
check when checking is free (in a discard phase: your first hole cards).

event (passed to observe after every hand):
    type             "hand_end"
    hand_id          5
    board            ["7h", "8h", "9c", "Kd", "2s"]
    shown            {3: ["As", "Kd"], 5: ["Qh", "Qc"]}   hands revealed at showdown
    payoffs          {1: -20, 3: 340, 5: -320}           net chips by seat, for seats dealt in
    stacks           [1800, 0, 950, ...]                 after the hand, by seat
    pots             [{"amount": 640, "winners": [3], "shares": [640]}]
    history          the hand's full history, as in obs
    eliminated       [[5, [7, 7]]]                       seats that busted, with their places
"""

from __future__ import annotations

from collections.abc import Sequence

from ..engine.cards import CARD_STR, STR_CARD
from ..engine.hand import Hand, Legal, _as_int
from ..engine.spec import VariantSpec
from ..engine.table import Table


def table_config(spec: VariantSpec, *, seat: int, seed: int, points: Sequence[float],
                 blinds: Sequence[Sequence[int]], level_hands: int, hand_cap: int,
                 seats: int, starting_stack: int, decision_limit_ms: float,
                 rules: str = "") -> dict:
    return {
        "variant": spec.to_dict(), "rules": rules, "points": list(points),
        "blinds": [list(lv) + [0] * (3 - len(lv)) for lv in blinds],
        "level_hands": level_hands, "hand_cap": hand_cap, "seats": seats,
        "starting_stack": starting_stack, "seat": seat,
        "decision_limit_ms": decision_limit_ms, "seed": seed,
    }


def legal_names(hand: Hand, legal: Legal) -> list[str]:
    if legal.discard:
        return ["discard"]
    names = []
    if legal.fold:
        names.append("fold")
    if legal.check:
        names.append("check")
    if legal.call:
        names.append("call")
    if legal.raise_max:
        names.append("raise" if hand.current_bet else "bet")
    return names


def build_obs(table: Table, hand: Hand, legal: Legal | None = None) -> dict:
    """The observation for ``hand.to_act`` at ``table``."""
    if legal is None:
        legal = hand.legal()
    p = hand.to_act
    seats = table.seats
    n = table.n_seats
    stacks = [0] * n
    bets = [0] * n
    for i, s in enumerate(seats):
        stacks[s] = hand.stack[i]
        bets[s] = hand.bet[i]
    level = table.level_index()
    sb, bb, ante = table.level()
    played = table.hands_played
    st = hand.street
    return {
        "hand_id": played + 1,
        "street": hand.spec.streets[st].name,
        "street_index": st,
        "phase": hand.phase,
        "seat": seats[p],
        "hole": [CARD_STR[c] for c in hand.hole[p]],
        "board": [CARD_STR[c] for c in hand.board],
        "pot": sum(hand.total),
        "pots": [{"amount": a, "eligible": [seats[i] for i in e]} for a, e in hand.live_pots()],
        "stacks": stacks,
        "bets": bets,
        "in_hand": [seats[i] for i in range(hand.n) if not hand.folded[i]],
        "alive": list(seats),
        "button": seats[hand.button],
        "sb_seat": seats[hand.sb_index],
        "bb_seat": seats[hand.bb_index],
        "legal": legal_names(hand, legal),
        "to_call": legal.call,
        "min_raise_to": legal.raise_min,
        "max_raise_to": legal.raise_max,
        "n_discard": legal.discard,
        "history": [[s_, seats[i], a, amt] for s_, i, a, amt in hand.history],
        "hands_played": played,
        "level": level,
        "sb": sb, "bb": bb, "ante": ante,
        "hands_to_next_level": table.level_hands - 1 - played % table.level_hands,
        "hands_left": table.hand_cap - played,
        "places": {s: list(span) for s, span in table.places.items()},
        "starting_stack": table.starting_stack,
    }


def hand_end_event(table: Table, hand: Hand, eliminated: Sequence[tuple[int, tuple[int, int]]]) -> dict:
    seats = table.seats
    res = hand.result
    stacks = [0] * table.n_seats
    for i, s in enumerate(seats):
        stacks[s] = res.stacks[i]
    return {
        "type": "hand_end",
        "hand_id": table.hands_played,
        "board": [CARD_STR[c] for c in hand.board],
        "shown": {seats[i]: [CARD_STR[c] for c in cs] for i, cs in res.shown.items()},
        "payoffs": {seats[i]: res.payoffs[i] for i in range(hand.n)},
        "stacks": stacks,
        "pots": [{"amount": p.amount, "winners": [seats[i] for i in p.winners], "shares": list(p.shares)}
                 for p in res.pots],
        "history": [[s_, seats[i], a, amt] for s_, i, a, amt in hand.history],
        "eliminated": [[s, list(span)] for s, span in eliminated],
    }


class BadAction(ValueError):
    pass


_NAMES = {"fold", "check", "call", "raise", "bet", "allin", "all-in", "all_in", "discard"}


def parse_action(ret: object) -> tuple[str, int, list[int] | None]:
    """Turn a bot's return value into (action, amount, cards) for Hand.act.
    Raises BadAction for anything malformed; legality is the engine's job."""
    if not isinstance(ret, dict):
        raise BadAction(f"act() must return a dict, got {type(ret).__name__}")
    name = ret.get("action")
    if not isinstance(name, str) or name.lower() not in _NAMES:
        raise BadAction(f"unknown action {name!r}")
    name = name.lower()
    amount = 0
    if name in ("raise", "bet"):
        amount = _as_int(ret.get("amount"))
        if amount is None:
            raise BadAction(f"raise amount {ret.get('amount')!r} is not an integer")
    cards = None
    if name == "discard":
        raw = ret.get("cards")
        if not isinstance(raw, (list, tuple)) or not all(isinstance(c, str) and c in STR_CARD for c in raw):
            raise BadAction(f"discard cards {raw!r} are not a list of cards")
        cards = [STR_CARD[c] for c in raw]
    return name, amount, cards
