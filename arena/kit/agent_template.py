"""Bot template: copy to bot/agent.py. As written, it is a valid bot that
checks when it can and folds otherwise.

Rules the referee enforces:
- Your bot is the package in bot/, with ``class Agent`` in bot/agent.py.
  Import your own modules relatively (``from .tables import X``) and load
  data files relative to ``__file__``: several bots share one process.
- act() may use at most the configured CPU time (1 ms). Over the limit, an
  exception, or an illegal action becomes a fold, or a check when checking
  is free.
- A fresh Agent is created at every table. Never carry anything from one
  table to the next (no files, class attributes or module globals written at
  runtime). Read-only data loaded at import time is fine.
- Use your own generator, e.g. ``random.Random(config["seed"])``; never the
  global ``random`` module, which other bots share.
- Standard library and numpy only. No network, no subprocesses, no files
  outside bot/.

config, given once per table:
    variant          the variant spec as a dict; EVENT.md explains it in words
    rules            today's rules text
    points           points by finishing place, 1st first, e.g. [100, 60, 40, 25, 15, 10, 5, 0]
    blinds           [[sb, bb, ante], ...], one per level
    level_hands      25        hands per blind level
    hand_cap         200       the table ends after this many hands
    seats            8
    starting_stack   2000
    seat             your seat id (seats are reshuffled at every table)
    decision_limit_ms  1.0
    seed             int for your own random generator

obs, given at every decision (example values):
    hand_id 5, street "flop", street_index 1, phase "bet" (or "discard")
    seat 3, hole ["As", "Kd"], board ["7h", "8h", "9c"]
    pot 340: every chip committed this hand, including this street's bets
    pots [{"amount": 300, "eligible": [1, 3, 5]}, ...]: main pot first
    stacks [1800, 0, 950, ...], bets [20, 0, 40, ...]: by seat; bets = this street
    in_hand [1, 3, 5]: not folded; alive [1, 3, 5, 6]: dealt into this hand
    button 5, sb_seat 6, bb_seat 1
    legal ["fold", "call", "raise"]: or "check", "bet", "discard"
    to_call 20: chips a call adds; min_raise_to 60, max_raise_to 1820
        (raise-to totals for this street; 0 when you can't raise)
    n_discard 0: cards to discard in a discard phase
    history [[street_index, seat, action, amount], ...] for this hand; actions:
        ante, sb, bb, fold, check, call, raise (amount = raise-to total),
        discard, return (uncalled chips handed back)
    hands_played 4, level 0, sb 10, bb 20, ante 0, hands_to_next_level 21,
    hands_left 196 (this hand included), places {2: [8, 8]} (seat -> [best, worst]),
    starting_stack 2000

Return one of:
    {"action": "fold"}  {"action": "check"}  {"action": "call"}
    {"action": "raise", "amount": 300}   # raise-to total; "bet" works the same
    {"action": "allin"}                  # raise to max, or call if you can't raise
    {"action": "discard", "cards": ["2c"]}

observe(event) is called after every hand with
    {"type": "hand_end", "hand_id", "board", "shown": {seat: cards},
     "payoffs": {seat: chips}, "stacks", "pots", "history", "eliminated"}
"""

import random


class Agent:
    def __init__(self, config):
        self.seat = config["seat"]
        self.rng = random.Random(config["seed"])

    def act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        if "check" in obs["legal"]:
            return {"action": "check"}
        return {"action": "fold"}

    def observe(self, event):
        pass
