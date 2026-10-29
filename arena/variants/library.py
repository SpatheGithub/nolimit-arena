"""Variant, points-table and blind-schedule libraries the referee draws from.

Variants are 8-seat playable. Royal (T-A, 20 cards) can't deal 8 players two
hole cards plus a 5-card board, so the arena's royal uses a 4-card board
(flop and turn, no river): 8 x 2 + 4 = 20 cards exactly.
"""

from __future__ import annotations

from ..engine.spec import NLHE, Betting, CardUse, Ranking, Street, VariantSpec

_HOLDEM = NLHE.streets


def _streets(hole: int = 2, discard_on: str | None = None) -> tuple[Street, ...]:
    names = ("preflop", "flop", "turn", "river")
    boards = (0, 3, 1, 1)
    return tuple(Street(n, hole=hole if n == "preflop" else 0, board=b, discard=1 if n == discard_on else 0)
                 for n, b in zip(names, boards))


SHORTDECK_ORDER = ("high_card", "pair", "two_pair", "trips", "straight",
                   "full_house", "flush", "quads", "straight_flush")

VARIANTS: dict[str, VariantSpec] = {
    "nlhe": NLHE,
    "shortdeck": VariantSpec("shortdeck", _HOLDEM, ranks="6789TJQKA", ranking=Ranking(order=SHORTDECK_ORDER)),
    "plo": VariantSpec("plo", _streets(hole=4), card_use=CardUse(2, 2), betting=Betting("pot_limit")),
    "pineapple": VariantSpec("pineapple", _streets(hole=3, discard_on="flop")),
    "crazy_pineapple": VariantSpec("crazy_pineapple", _streets(hole=3, discard_on="turn")),
    "royal": VariantSpec("royal", (Street("preflop", hole=2), Street("flop", board=3), Street("turn", board=1)),
                         ranks="TJQKA"),
}

ONE_LINERS = {
    "nlhe": "No-limit Texas hold'em: 2 hole cards, a 5-card board, best five of seven.",
    "shortdeck": "No-limit hold'em with a 36-card deck (6 to A): a flush beats a full house and A-6-7-8-9 is a straight.",
    "plo": "Pot-limit Omaha: 4 hole cards; a hand uses exactly 2 of them and exactly 3 board cards.",
    "pineapple": "No-limit hold'em with 3 hole cards; everyone discards one before the flop.",
    "crazy_pineapple": "No-limit hold'em with 3 hole cards; everyone discards one after the flop betting.",
    "royal": "No-limit hold'em with only T-J-Q-K-A (20 cards) and a 4-card board (no river).",
}

POINTS: dict[str, tuple[float, ...]] = {
    "flat": (7, 6, 5, 4, 3, 2, 1, 0),
    "standard": (100, 60, 40, 25, 15, 10, 5, 0),
    "top_heavy": (100, 45, 20, 8, 0, 0, 0, 0),
    "winner_take_most": (100, 25, 5, 0, 0, 0, 0, 0),
    "castle": (9, 4, 2, 0, 0, 0, 0, 0),
}

BLINDS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "doubling": tuple((10 * 2**k, 20 * 2**k, 0) for k in range(8)),
    "sng_standard": ((10, 20, 0), (15, 30, 0), (25, 50, 0), (50, 100, 0),
                     (75, 150, 15), (100, 200, 20), (150, 300, 30), (200, 400, 40)),
    "slow": ((10, 20, 0), (15, 30, 0), (20, 40, 0), (30, 60, 0),
             (40, 80, 0), (50, 100, 0), (60, 120, 0), (80, 160, 0)),
}
