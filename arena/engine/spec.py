"""Variant specs: the data that tells the engine how a poker variant plays.

One engine plays every variant from a VariantSpec:

- the deck: subsets of ranks and suits;
- the streets: per street, discards, then hole cards, then board cards, then
  an optional betting round;
- the card-use rule: how many hole cards a five-card hand may or must use;
- the ranking: category order and ace-low straights;
- the betting structure: no-limit, pot-limit or fixed-limit.

Specs are frozen and hashable. ``to_dict()`` gives plain primitives for bot
configs and event cards, and ``VariantSpec.from_dict()`` reverses it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .cards import RANKS, SUITS, make_deck

CATEGORIES = (
    "high_card", "pair", "two_pair", "trips", "straight",
    "flush", "full_house", "quads", "straight_flush",
)
STANDARD_ORDER = CATEGORIES
STRUCTURES = ("no_limit", "pot_limit", "fixed_limit")


@dataclass(frozen=True)
class Street:
    """One street. In order: every player still in the hand discards
    ``discard`` hole cards, every player is dealt ``hole`` hole cards,
    ``board`` board cards are dealt, then a betting round runs if ``bet``."""

    name: str
    discard: int = 0
    hole: int = 0
    board: int = 0
    bet: bool = True


@dataclass(frozen=True)
class CardUse:
    """A made hand is five cards using between ``hole_min`` and ``hole_max``
    hole cards, the rest from the board. Hold'em: 0..5, i.e. best five of
    any. Omaha: exactly 2. "At least one hole card": 1..5."""

    hole_min: int = 0
    hole_max: int = 5


@dataclass(frozen=True)
class Ranking:
    """``order`` lists the nine categories, weakest first. Straights are five
    consecutive ranks of the deck's own rank list; with ``ace_low`` the ace
    also plays below the deck's four lowest ranks (A-2-3-4-5, or A-6-7-8-9
    in short deck)."""

    order: tuple[str, ...] = STANDARD_ORDER
    ace_low: bool = True


@dataclass(frozen=True)
class Betting:
    """``structure``: no_limit, pot_limit or fixed_limit. For fixed-limit,
    ``fl_bets`` is the bet size of each betting street in big blinds
    (hold'em: 1, 1, 2, 2) and ``fl_cap`` the maximum number of bets plus
    raises per street (0 = uncapped)."""

    structure: str = "no_limit"
    fl_bets: tuple[int, ...] = ()
    fl_cap: int = 4


@dataclass(frozen=True)
class VariantSpec:
    name: str
    streets: tuple[Street, ...]
    ranks: str = RANKS
    suits: str = SUITS
    card_use: CardUse = CardUse()
    ranking: Ranking = Ranking()
    betting: Betting = Betting()

    def deck(self) -> list[int]:
        return make_deck(self.ranks, self.suits)

    @property
    def deck_size(self) -> int:
        return len(self.ranks) * len(self.suits)

    @property
    def hole_count(self) -> int:
        """Hole cards each player holds at showdown."""
        return sum(s.hole - s.discard for s in self.streets)

    @property
    def board_count(self) -> int:
        return sum(s.board for s in self.streets)

    @property
    def betting_streets(self) -> tuple[int, ...]:
        return tuple(i for i, s in enumerate(self.streets) if s.bet)

    def cards_needed(self, n_players: int) -> int:
        return n_players * sum(s.hole for s in self.streets) + self.board_count

    def max_players(self) -> int:
        per_player = sum(s.hole for s in self.streets)
        return (self.deck_size - self.board_count) // per_player if per_player else 0

    def hole_splits(self) -> tuple[tuple[int, int], ...]:
        """Allowed (hole cards used, board cards used) pairs for a five-card hand."""
        h, b = self.hole_count, self.board_count
        lo, hi = self.card_use.hole_min, min(self.card_use.hole_max, h, 5)
        return tuple((k, 5 - k) for k in range(lo, hi + 1) if 5 - k <= b)

    def validate(self, n_players: int | None = None) -> None:
        """Raise ValueError if the spec can't be played (by ``n_players``)."""
        err = _problems(self, n_players)
        if err:
            raise ValueError(f"variant {self.name!r}: " + "; ".join(err))

    def to_dict(self) -> dict:
        return _listify(asdict(self))

    @classmethod
    def from_dict(cls, d: dict) -> VariantSpec:
        return cls(
            name=d["name"],
            streets=tuple(Street(**s) for s in d["streets"]),
            ranks=d.get("ranks", RANKS),
            suits=d.get("suits", SUITS),
            card_use=CardUse(**d.get("card_use", {})),
            ranking=Ranking(**{**d.get("ranking", {}),
                               "order": tuple(d.get("ranking", {}).get("order", STANDARD_ORDER))}),
            betting=Betting(**{**d.get("betting", {}),
                               "fl_bets": tuple(d.get("betting", {}).get("fl_bets", ()))}),
        )


def _listify(x):
    if isinstance(x, dict):
        return {k: _listify(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_listify(v) for v in x]
    return x


def _problems(spec: VariantSpec, n_players: int | None) -> list[str]:
    err = []
    if not spec.ranks or any(r not in RANKS for r in spec.ranks) \
            or list(spec.ranks) != sorted(set(spec.ranks), key=RANKS.index):
        err.append(f"ranks must be distinct characters of {RANKS!r} in that order")
    if not spec.suits or any(s not in SUITS for s in spec.suits) \
            or list(spec.suits) != sorted(set(spec.suits), key=SUITS.index):
        err.append(f"suits must be distinct characters of {SUITS!r} in that order")
    if sorted(spec.ranking.order) != sorted(CATEGORIES):
        err.append("ranking.order must list each category exactly once")
    if not spec.streets:
        err.append("no streets")
    if not spec.betting_streets:
        err.append("no betting round")
    held = 0
    for s in spec.streets:
        if min(s.discard, s.hole, s.board) < 0:
            err.append(f"street {s.name!r}: negative card count")
        if s.discard > held:
            err.append(f"street {s.name!r}: discards {s.discard} of {held} hole cards")
        held += s.hole - s.discard
    if held < 1:
        err.append("players end with no hole cards")
    cu = spec.card_use
    if not 0 <= cu.hole_min <= cu.hole_max:
        err.append("card_use needs 0 <= hole_min <= hole_max")
    elif not spec.hole_splits():
        err.append("card_use can't make a five-card hand from these hole and board counts")
    b = spec.betting
    if b.structure not in STRUCTURES:
        err.append(f"betting.structure must be one of {STRUCTURES}")
    elif b.structure == "fixed_limit":
        if len(b.fl_bets) != len(spec.betting_streets) or any(x <= 0 for x in b.fl_bets):
            err.append("fixed_limit needs one positive fl_bets entry per betting street")
        if b.fl_cap < 0:
            err.append("fl_cap must be >= 0")
    if n_players is not None and spec.cards_needed(n_players) > spec.deck_size:
        err.append(f"{n_players} players need {spec.cards_needed(n_players)} cards; "
                   f"the deck has {spec.deck_size}")
    return err


NLHE = VariantSpec(
    name="nlhe",
    streets=(
        Street("preflop", hole=2),
        Street("flop", board=3),
        Street("turn", board=1),
        Street("river", board=1),
    ),
)
