"""Card encoding shared by every variant.

A card is an int in 0..51: ``rank * 4 + suit``, with ranks 2..A as 0..12 and
suits c, d, h, s as 0..3. Ids don't depend on the variant; a variant's deck is
a subset of them. Bots see cards as two-character strings such as "As" or "Td".
"""

from __future__ import annotations

from collections.abc import Iterable

RANKS = "23456789TJQKA"
SUITS = "cdhs"

CARD_STR: tuple[str, ...] = tuple(r + s for r in RANKS for s in SUITS)
STR_CARD: dict[str, int] = {s: i for i, s in enumerate(CARD_STR)}


def card(text: str) -> int:
    """Parse one card, e.g. ``card("As") == 51``."""
    try:
        return STR_CARD[text]
    except KeyError:
        raise ValueError(f"not a card: {text!r}") from None


def cards(text: str | Iterable[str]) -> list[int]:
    """Parse ``"AsKd"``, ``"As Kd"`` or ``["As", "Kd"]``."""
    if isinstance(text, str):
        s = text.replace(" ", "").replace(",", "")
        if len(s) % 2:
            raise ValueError(f"not a card list: {text!r}")
        return [card(s[i:i + 2]) for i in range(0, len(s), 2)]
    return [card(t) for t in text]


def card_str(c: int) -> str:
    return CARD_STR[c]


def cards_str(cs: Iterable[int]) -> list[str]:
    return [CARD_STR[c] for c in cs]


def rank(c: int) -> int:
    return c >> 2


def suit(c: int) -> int:
    return c & 3


def make_deck(ranks: str = RANKS, suits: str = SUITS) -> list[int]:
    """Card ids for a deck with the given rank and suit characters, ascending."""
    return sorted(RANKS.index(r) * 4 + SUITS.index(s) for r in ranks for s in suits)
