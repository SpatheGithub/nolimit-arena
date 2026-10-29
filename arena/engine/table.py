"""A sit-and-go table: hands until one player holds every chip or the hand cap.

Seats are 0..n_seats-1 and keep their ids for the whole table; each hand is
played by the seats that still have chips, in seat order.

Table rules (the builder-facing copy is arena/kit/RULES.md):

- The first button is drawn at random. After each hand it moves to the next
  seat clockwise that still has chips. This replaces the dead-button rule: there
  is never a dead button or a missed blind, so after an elimination a player
  can occasionally skip a blind or post one twice in a row.
- Hand h (counting from 0) uses level h // level_hands of the blind schedule;
  past the end of the schedule the last level repeats.
- Players who bust in the same hand finish in order of their stacks at the
  start of that hand, larger stack placing higher; exactly equal stacks share
  those places.
- The table ends when one player has every chip (1st place) or after
  ``hand_cap`` hands. Survivors at the cap have no place yet; scoring splits
  the remaining places' points among them by ICM.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from .hand import Hand
from .spec import VariantSpec

# (small blind, big blind, ante) per level: the kit's default "doubling" schedule.
DOUBLING = tuple((10 * 2**k, 20 * 2**k, 0) for k in range(8))


class Table:
    def __init__(self, spec: VariantSpec, n_seats: int = 8, starting_stack: int = 2000,
                 blinds: Sequence[Sequence[int]] = DOUBLING, level_hands: int = 25,
                 hand_cap: int = 200, rng: random.Random | None = None,
                 stacks: Sequence[int] | None = None, button: int | None = None):
        spec.validate(n_seats)
        if not blinds:
            raise ValueError("empty blind schedule")
        self.spec = spec
        self.n_seats = n_seats
        self.starting_stack = starting_stack
        self.stacks = list(stacks) if stacks is not None else [starting_stack] * n_seats
        if len(self.stacks) != n_seats:
            raise ValueError("one stack per seat")
        self.blinds = [tuple(lv) + (0,) * (3 - len(lv)) for lv in blinds]
        self.level_hands = level_hands
        self.hand_cap = hand_cap
        self.rng = rng or random.Random()
        self.hands_played = 0
        self.places: dict[int, tuple[int, int]] = {}  # seat -> (best, worst) place
        self.button: int | None = button
        self.hand: Hand | None = None
        self.seats: list[int] = []                   # hand player index -> seat
        self._first_hand = True

    # ------------------------------------------------------------ queries

    @property
    def alive(self) -> list[int]:
        return [s for s in range(self.n_seats) if self.stacks[s] > 0]

    def over(self) -> bool:
        return len(self.alive) <= 1 or self.hands_played >= self.hand_cap

    def level_index(self, hand_number: int | None = None) -> int:
        h = self.hands_played if hand_number is None else hand_number
        return min(h // self.level_hands, len(self.blinds) - 1)

    def level(self, hand_number: int | None = None) -> tuple[int, int, int]:
        return self.blinds[self.level_index(hand_number)]

    def survivors(self) -> list[int]:
        """Seats still holding chips; at the cap they await the ICM split."""
        return self.alive

    # ------------------------------------------------------------ play

    def start_hand(self, deck: list[int] | None = None) -> Hand:
        """Deal the next hand, from ``deck`` in dealing order if given (tests, replays)."""
        if self.over():
            raise RuntimeError("the table is over")
        if self.hand is not None and self.hand.result is None:
            raise RuntimeError("finish the current hand first")
        alive = self.alive
        if self._first_hand:
            if self.button is None or self.stacks[self.button] <= 0:
                self.button = self.rng.choice(alive)
            self._first_hand = False
        else:
            for k in range(1, self.n_seats + 1):
                s = (self.button + k) % self.n_seats
                if self.stacks[s] > 0:
                    self.button = s
                    break
        self.seats = alive
        sb, bb, ante = self.level()
        self.hand = Hand(self.spec, [self.stacks[s] for s in alive], alive.index(self.button),
                         sb, bb, ante, deck=deck, rng=self.rng)
        return self.hand

    def finish_hand(self) -> list[tuple[int, tuple[int, int]]]:
        """Apply the finished hand; return the seats it eliminated and their places."""
        hand = self.hand
        if hand is None or hand.result is None:
            raise RuntimeError("no finished hand to apply")
        start = {s: hand.start_stacks[i] for i, s in enumerate(self.seats)}
        for i, s in enumerate(self.seats):
            self.stacks[s] = hand.result.stacks[i]
        self.hands_played += 1
        busted = sorted((s for s in self.seats if self.stacks[s] == 0), key=lambda s: -start[s])
        out = []
        place = len(self.alive) + 1
        k = 0
        while k < len(busted):
            group = [s for s in busted[k:] if start[s] == start[busted[k]]]
            span = (place, place + len(group) - 1)
            for s in group:
                self.places[s] = span
                out.append((s, span))
            place += len(group)
            k += len(group)
        if len(self.alive) == 1:
            self.places[self.alive[0]] = (1, 1)
        return out

    def play(self, decide: Callable[[Table, Hand], None]) -> None:
        """Play to the end; ``decide(table, hand)`` must make one action on ``hand``."""
        while not self.over():
            hand = self.start_hand()
            while hand.to_act is not None:
                decide(self, hand)
            self.finish_hand()
