"""One hand of poker for any VariantSpec.

Players are indexed 0..n-1 in seat order (clockwise) and ``button`` is one of
those indices. The hand posts antes and blinds, deals, runs discards and
betting rounds, and settles pots by itself; callers only answer decisions:

    hand = Hand(NLHE, stacks=[2000] * 8, button=0, sb=10, bb=20, rng=rng)
    while hand.to_act is not None:
        legal = hand.legal()
        hand.act("call" if legal.call else "check")
    hand.result.payoffs

Dealer rules (the builder-facing copy is arena/kit/RULES.md). They match
pokerkit's tournament mode except where marked TDA:

- Antes are dead money posted first, then the small and big blind. A player
  who can't cover one posts what they have and is all-in.
- If a blind is all-in for less, the amount to call is the largest blind
  actually posted.
- Heads-up, the button posts the small blind, acts first on the first street
  and last after it.
- Amounts are raise-to totals for the street. "bet" and "raise" mean the same;
  "call" with nothing to call is a check; "allin" is a raise to the maximum,
  or a call when raising isn't allowed.
- No-limit: a raise is at least the largest full raise so far on the street,
  and never less than the big blind. Pot-limit caps a raise at the pot after
  calling. Fixed-limit raises by the street's bet; at most ``fl_cap`` bets
  and raises per street, blinds not counted.
- TDA: an all-in for less than a full raise (at least the big blind, or the
  street's bet in fixed-limit) doesn't reopen the betting. A player who
  already acted may then only call or fold, unless they now face at least a
  full raise since their own last action.
- No one may raise when no other player could call a raise.
- Folding is only legal when facing a bet.
- Uncalled chips go back to the bettor when a betting round ends.
- At showdown, players who win nothing are mucked, pots with the same
  remaining contenders are merged, and each pot splits evenly among its best
  hands; the whole remainder goes to the first winner left of the button.
- Cards are dealt one at a time starting left of the button; there are no
  burn cards. Discards come before that street's cards; a player who must
  discard and fails to choose discards their first hole cards.
"""

from __future__ import annotations

import operator
import random
from typing import NamedTuple

from .evaluate import get_evaluator
from .spec import VariantSpec

FOLD, CHECK, CALL, RAISE, DISCARD = "fold", "check", "call", "raise", "discard"
_ALIASES = {"bet": RAISE, "all-in": "allin", "all_in": "allin"}


class IllegalAction(ValueError):
    pass


class Legal(NamedTuple):
    """The decision facing ``Hand.to_act``. ``call`` is the chips a call adds
    (0 when checking is free). ``raise_min``/``raise_max`` are raise-to totals;
    both are 0 when raising isn't allowed. ``discard`` is the number of hole
    cards to discard in a discard phase, else 0."""

    fold: bool
    check: bool
    call: int
    raise_min: int
    raise_max: int
    discard: int = 0


class Pot(NamedTuple):
    amount: int
    eligible: tuple[int, ...]  # contenders after losers are mucked
    winners: tuple[int, ...]
    shares: tuple[int, ...]    # chips each winner received, aligned with winners


class HandResult(NamedTuple):
    payoffs: list[int]           # net chips per player; sums to zero
    stacks: list[int]            # stacks after the hand
    pots: list[Pot]              # as paid out
    showdown: bool               # True if two or more players reached showdown
    shown: dict[int, list[int]]  # hole cards revealed at showdown
    values: dict[int, int]       # their hand values (see evaluate.py)


class Hand:
    def __init__(self, spec: VariantSpec, stacks: list[int], button: int, sb: int, bb: int,
                 ante: int = 0, deck: list[int] | None = None, rng: random.Random | None = None):
        n = len(stacks)
        if n < 2:
            raise ValueError("a hand needs at least two players")
        if any(s <= 0 for s in stacks):
            raise ValueError("every player needs chips")
        if not 0 <= button < n:
            raise ValueError("button out of range")
        if not 0 < sb <= bb or ante < 0:
            raise ValueError("need 0 < sb <= bb and ante >= 0")
        if not spec.streets[0].bet:
            raise ValueError("the first street must have a betting round")
        self.spec = spec
        self.n = n
        self.button = button
        self.sb_amount, self.bb_amount, self.ante = sb, bb, ante
        self.start_stacks = list(stacks)
        self.stack = list(stacks)
        self.bet = [0] * n        # this street
        self.total = [0] * n      # this hand, net of returned uncalled chips
        self.folded = [False] * n
        self.hole: list[list[int]] = [[] for _ in range(n)]
        self.board: list[int] = []
        self.history: list[tuple[int, int, str, int]] = []  # (street, player, action, amount)
        self.result: HandResult | None = None
        self.to_act: int | None = None
        self.phase = "bet"
        self.street = 0
        if deck is None:
            deck = (rng or random).sample(spec.deck_tuple(), spec.cards_needed(n))
        elif len(deck) < spec.cards_needed(n):
            raise ValueError("deck too short for this hand")
        self._deck = deck
        self._next_card = 0
        self._discard_queue: list[int] = []
        self._structure = spec.betting.structure

        if n == 2:
            self.sb_index, self.bb_index = button, 1 - button
        else:
            self.sb_index, self.bb_index = (button + 1) % n, (button + 2) % n
        if ante:
            for i in self._order_from(button + 1):
                self._post(i, ante, "ante", dead=True)
        self._post(self.sb_index, sb, "sb")
        self._post(self.bb_index, bb, "bb")
        self._begin_street(0)

    # ------------------------------------------------------------ queries

    def legal(self) -> Legal:
        p = self.to_act
        if p is None:
            raise IllegalAction("the hand is over")
        if self.phase == DISCARD:
            return Legal(False, False, 0, 0, 0, self.spec.streets[self.street].discard)
        to_call = self.current_bet - self.bet[p]
        stack = self.stack[p]
        lo = hi = 0
        if stack > to_call and self._may_raise(p):
            allin = self.bet[p] + stack
            if self._structure == "fixed_limit":
                lo = hi = min(self.current_bet + self.street_bet, allin)
            else:
                lo = min(self.current_bet + self.raise_size, allin)
                hi = allin
                if self._structure == "pot_limit":
                    pot_max = self.current_bet + sum(self.total) + to_call
                    hi = min(allin, max(lo, pot_max))
        return Legal(to_call > 0, to_call == 0, min(to_call, stack), lo, hi, 0)

    def pot_total(self) -> int:
        return sum(self.total)

    def live_pots(self) -> list[tuple[int, tuple[int, ...]]]:
        """Main and side pots as committed so far: (amount, non-folded contributors)."""
        return _layers(self.total, self.folded)

    def in_hand(self) -> list[int]:
        return [i for i in range(self.n) if not self.folded[i]]

    # ------------------------------------------------------------ actions

    def act(self, action: str, amount: int = 0, cards: list[int] | None = None) -> None:
        p = self.to_act
        if p is None:
            raise IllegalAction("the hand is over")
        action = _ALIASES.get(action, action)
        if self.phase == DISCARD:
            if action != DISCARD:
                raise IllegalAction(f"expected a discard, got {action!r}")
            self._discard(p, cards)
            return
        legal = self.legal()
        if action == "allin":
            if legal.raise_max:
                action, amount = RAISE, legal.raise_max
            else:
                action = CALL
        if action == CALL and legal.check:
            action = CHECK
        if action == FOLD:
            if not legal.fold:
                raise IllegalAction("fold with nothing to call")
            self.folded[p] = True
            self.history.append((self.street, p, FOLD, 0))
        elif action == CHECK:
            if not legal.check:
                raise IllegalAction(f"check facing {legal.call}")
            self._acted[p] = True
            self._seen[p] = self.current_bet
            self.history.append((self.street, p, CHECK, 0))
        elif action == CALL:
            self._put(p, legal.call)
            self._acted[p] = True
            self._seen[p] = self.current_bet
            self.history.append((self.street, p, CALL, legal.call))
        elif action == RAISE:
            if not legal.raise_max:
                raise IllegalAction("raising is not allowed here")
            amount = _as_int(amount)
            if amount is None or not legal.raise_min <= amount <= legal.raise_max:
                raise IllegalAction(f"raise to {amount!r} outside {legal.raise_min}..{legal.raise_max}")
            increment = amount - self.current_bet
            if increment >= self.raise_size:
                self.raise_size = increment
            self.n_raises += 1
            self.current_bet = amount
            self._put(p, amount - self.bet[p])
            self._acted[p] = True
            self._seen[p] = amount
            self.history.append((self.street, p, RAISE, amount))
        else:
            raise IllegalAction(f"unknown action {action!r}")
        self._advance(p)

    def act_default(self) -> None:
        """The substitution for a failed decision: check if free, else fold;
        in a discard phase, discard the first hole cards."""
        legal = self.legal()
        if legal.discard:
            self.act(DISCARD, cards=self.hole[self.to_act][:legal.discard])
        else:
            self.act(CHECK if legal.check else FOLD)

    # ------------------------------------------------------------ internals

    def _order_from(self, start: int) -> list[int]:
        n = self.n
        return [(start + k) % n for k in range(n)]

    def _post(self, i: int, amount: int, label: str, dead: bool = False) -> None:
        amount = min(amount, self.stack[i])
        if amount == 0:
            return
        self.stack[i] -= amount
        self.total[i] += amount
        if not dead:
            self.bet[i] += amount
        self.history.append((0, i, label, amount))

    def _put(self, i: int, chips: int) -> None:
        self.stack[i] -= chips
        self.bet[i] += chips
        self.total[i] += chips

    def _may_raise(self, p: int) -> bool:
        cb = self.current_bet
        folded, bet, stack = self.folded, self.bet, self.stack
        for j in range(self.n):
            if j != p and not folded[j] and bet[j] + stack[j] > cb:
                break
        else:
            return False  # nobody could call a raise
        if self._structure == "fixed_limit":
            cap = self.spec.betting.fl_cap
            if cap and self.n_raises >= cap:
                return False
        return not self._acted[p] or cb - self._seen[p] >= self.raise_size

    def _needs_action(self, i: int) -> bool:
        if self.folded[i] or self.stack[i] == 0:
            return False
        if self.bet[i] < self.current_bet:
            return True
        if self._acted[i]:
            return False
        folded, stack = self.folded, self.stack
        for j in range(self.n):
            if j != i and not folded[j] and stack[j] > 0:
                return True
        return False

    def _begin_street(self, s: int) -> None:
        self.street = s
        st = self.spec.streets[s]
        if st.discard:
            self.phase = DISCARD
            self._discard_queue = [i for i in self._order_from(self.button + 1) if not self.folded[i]]
            self.to_act = self._discard_queue.pop(0)
            return
        self._deal_and_bet(s)

    def _deal_and_bet(self, s: int) -> None:
        st = self.spec.streets[s]
        self.phase = "bet"
        deck = self._deck
        if st.hole:
            order = [i for i in self._order_from(self.button + 1) if not self.folded[i]]
            for _ in range(st.hole):
                for i in order:
                    self.hole[i].append(deck[self._next_card])
                    self._next_card += 1
        if st.board:
            self.board.extend(deck[self._next_card:self._next_card + st.board])
            self._next_card += st.board
        first_street = s == 0
        if first_street:
            self.current_bet = max(self.bet)
        else:
            self.bet = [0] * self.n
            self.current_bet = 0
        if st.bet and self._structure == "fixed_limit":
            k = self.spec.betting_streets.index(s)
            self.street_bet = self.spec.betting.fl_bets[k] * self.bb_amount
            self.raise_size = self.street_bet
        else:
            self.raise_size = self.bb_amount
        self.n_raises = 0
        self._acted = [False] * self.n
        self._seen = [0] * self.n
        if not st.bet:
            self._end_round()
            return
        if first_street:
            first = self.button if self.n == 2 else self.bb_index + 1
        else:
            first = self.button + 1
        for i in self._order_from(first):
            if self._needs_action(i):
                self.to_act = i
                return
        self._end_round()

    def _advance(self, p: int) -> None:
        if self.folded.count(False) == 1:
            self._end_round()
            return
        n = self.n
        for k in range(1, n + 1):
            i = (p + k) % n
            if self._needs_action(i):
                self.to_act = i
                return
        self._end_round()

    def _discard(self, p: int, cards: list[int] | None) -> None:
        k = self.spec.streets[self.street].discard
        hole = self.hole[p]
        if cards is None or len(cards) != k or len(set(cards)) != k or any(c not in hole for c in cards):
            raise IllegalAction(f"discard exactly {k} of your hole cards")
        for c in cards:
            hole.remove(c)
        self.history.append((self.street, p, DISCARD, k))
        if self._discard_queue:
            self.to_act = self._discard_queue.pop(0)
        else:
            self._deal_and_bet(self.street)

    def _end_round(self) -> None:
        self.to_act = None
        bet = self.bet
        top = max(range(self.n), key=bet.__getitem__)
        second = max((bet[i] for i in range(self.n) if i != top), default=0)
        excess = bet[top] - second
        if excess > 0:
            bet[top] -= excess
            self.total[top] -= excess
            self.stack[top] += excess
            self.history.append((self.street, top, "return", excess))
        if self.folded.count(False) == 1:
            self._settle(showdown=False)
        elif self.street + 1 < len(self.spec.streets):
            self._begin_street(self.street + 1)
        else:
            self._settle(showdown=True)

    def _settle(self, showdown: bool) -> None:
        self.phase = "done"
        self.to_act = None
        live = self.in_hand()
        values: dict[int, int] = {}
        shown: dict[int, list[int]] = {}
        if showdown:
            vals = get_evaluator(self.spec).showdown([self.hole[i] for i in live], self.board)
            values = dict(zip(live, vals))
            shown = {i: list(self.hole[i]) for i in live}
        seat_rank = {p: k for k, p in enumerate(self._order_from(self.button + 1))}
        layers = _layers(self.total, self.folded)
        if showdown:
            wins = []
            for _, eligible in layers:
                best = max(values[i] for i in eligible)
                wins.append(tuple(i for i in eligible if values[i] == best))
            winners_any = {i for w in wins for i in w}
        else:
            wins = [tuple(live)] * len(layers)
            winners_any = set(live)
        merged: list[list] = []
        for (amount, eligible), win in zip(layers, wins):
            contenders = tuple(i for i in eligible if i in winners_any)
            if merged and merged[-1][1] == contenders:
                merged[-1][0] += amount
            else:
                merged.append([amount, contenders, win])
        pots = []
        for amount, contenders, win in merged:
            win = tuple(sorted(win, key=seat_rank.__getitem__))
            share, odd = divmod(amount, len(win))
            shares = tuple(share + (odd if k == 0 else 0) for k in range(len(win)))
            for i, s in zip(win, shares):
                self.stack[i] += s
            pots.append(Pot(amount, contenders, win, shares))
        self.result = HandResult(
            payoffs=[self.stack[i] - self.start_stacks[i] for i in range(self.n)],
            stacks=list(self.stack), pots=pots, showdown=showdown, shown=shown, values=values)


def _as_int(x) -> int | None:
    """Accept ints, numpy integers and integral floats; anything else is None."""
    if isinstance(x, bool):
        return None
    try:
        return operator.index(x)
    except TypeError:
        if isinstance(x, float) and x.is_integer():
            return int(x)
        return None


def _layers(total: list[int], folded: list[bool]) -> list[tuple[int, tuple[int, ...]]]:
    """Split committed chips into a main pot and side pots by all-in level.
    Chips of folded players count toward every level they reached; any chips
    above the highest live level join the last pot."""
    live = [i for i in range(len(total)) if not folded[i]]
    levels = sorted({total[i] for i in live if total[i] > 0})
    pots: list[list] = []
    prev = 0
    for lv in levels:
        amount = sum(min(t, lv) - min(t, prev) for t in total)
        eligible = tuple(i for i in live if total[i] >= lv)
        if amount:
            pots.append([amount, eligible])
        prev = lv
    extra = sum(t - min(t, prev) for t in total)
    if extra:
        if pots:
            pots[-1][0] += extra
        else:
            pots.append([extra, tuple(live)])
    return [(a, e) for a, e in pots]
