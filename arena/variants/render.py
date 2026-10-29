"""EVENT.md: today's complete rules in plain English, rendered from the event card.

A builder should never need the engine source to understand the variant, so
the hand-ranking table shows an example holding per category and the
frequency measured on this deck with this card-use rule. Categories that rank
above more common ones get flagged.
"""

from __future__ import annotations

import random
from collections import Counter

from ..engine.cards import RANKS, card_str
from ..engine.evaluate import get_evaluator
from ..engine.spec import CATEGORIES, STANDARD_ORDER, VariantSpec

CATEGORY_NAMES = {
    "high_card": "High card", "pair": "One pair", "two_pair": "Two pair", "trips": "Three of a kind",
    "straight": "Straight", "flush": "Flush", "full_house": "Full house", "quads": "Four of a kind",
    "straight_flush": "Straight flush",
}
SUIT_NAMES = {"c": "clubs", "d": "diamonds", "h": "hearts", "s": "spades"}
# Exact 7-card frequencies in standard hold'em (%), the intuition builders bring.
HOLDEM_7CARD = {"straight_flush": 0.0311, "quads": 0.168, "full_house": 2.60, "flush": 3.03,
                "straight": 4.62, "trips": 4.83, "two_pair": 23.5, "pair": 43.8, "high_card": 17.4}


def measure_categories(spec: VariantSpec, samples: int = 200_000, seed: int = 1) -> tuple[Counter, dict]:
    """Category counts for one player's final hole cards plus the board, and
    one example holding per category."""
    ev = get_evaluator(spec)
    rng = random.Random(seed)
    deck = spec.deck_tuple()
    h, b = spec.hole_count, spec.board_count
    counts: Counter = Counter()
    examples: dict[str, tuple[list[int], list[int]]] = {}
    for _ in range(samples):
        cs = rng.sample(deck, h + b)
        cat = ev.category(ev.evaluate(cs[:h], cs[h:]))
        counts[cat] += 1
        if cat not in examples:
            examples[cat] = (cs[:h], cs[h:])
    for cat in CATEGORIES:  # look harder for rare categories
        tries = 0
        while cat not in examples and tries < 400_000:
            cs = rng.sample(deck, h + b)
            if ev.category(ev.evaluate(cs[:h], cs[h:])) == cat:
                examples[cat] = (cs[:h], cs[h:])
            tries += 1
    return counts, examples


def _card_use_text(spec: VariantSpec) -> str:
    lo, hi = spec.card_use.hole_min, min(spec.card_use.hole_max, spec.hole_count, 5)
    if (lo, hi) == (max(0, 5 - spec.board_count), min(5, spec.hole_count)) or lo == 0 and hi >= spec.hole_count:
        return "the best five cards out of your hole cards and the board combined, in any mix"
    if lo == hi:
        return (f"exactly {lo} of your hole cards and exactly {5 - lo} board cards; "
                "no other mix counts")
    if hi >= min(5, spec.hole_count):
        return f"the best five cards using at least {lo} of your hole cards"
    return f"the best five cards using between {lo} and {hi} of your hole cards"


def _straights_text(spec: VariantSpec) -> str:
    ranks = [r for r in RANKS if r in spec.ranks]
    if len(ranks) < 5:
        return "Straights are impossible with this deck."
    low = ranks[:5]
    if spec.ranking.ace_low and "A" in ranks and "A" not in ranks[:4]:
        low_text = "A-" + "-".join(ranks[:4])
    else:
        low_text = "-".join(low)
    return (f"A straight is five consecutive ranks of this deck: the lowest is {low_text}, "
            f"the highest {'-'.join(ranks[-5:])}.")


def _betting_text(spec: VariantSpec, card: dict) -> list[str]:
    b = spec.betting
    if b.structure == "no_limit":
        return ["**No-limit.** You may bet or raise any amount from the minimum up to your whole stack. "
                "The minimum raise is the largest full raise so far on the street, never less than the big blind."]
    if b.structure == "pot_limit":
        return ["**Pot-limit.** The largest raise makes your total the current bet plus the pot after you call "
                "(every chip already in, including this street's bets). The minimum raise is as in no-limit."]
    streets = [spec.streets[i].name for i in spec.betting_streets]
    sizes = ", ".join(f"{s} {k} big blind{'s' if k > 1 else ''}" for s, k in zip(streets, b.fl_bets))
    cap = f"at most {b.fl_cap} bets and raises per street (the blinds don't count)" if b.fl_cap else "no raise cap"
    return [f"**Fixed-limit.** Every bet and raise is exactly one bet: {sizes}; {cap}."]


def render_event_md(card: dict, samples: int = 200_000) -> str:
    spec = VariantSpec.from_dict(card["variant"])
    counts, examples = measure_categories(spec, samples)
    total = sum(counts.values())
    order = list(spec.ranking.order)
    ranks = [r for r in RANKS if r in spec.ranks]
    lines = [f"# Today's event: {card['event']}", "",
             "Everything about today's rules is in this file. `kit/RULES.md` has the dealer's rules for every "
             "variant (blinds, all-ins, side pots, ties), and `kit/event.json` has the same facts as data.", "",
             f"## The variant: {spec.name}", ""]
    deck_note = "" if spec.deck_size == 52 else f" This is not the standard 52-card deck."
    lines += [f"**Deck.** {spec.deck_size} cards: ranks {' '.join(ranks)} (low to high), suits "
              f"{', '.join(SUIT_NAMES[s] for s in spec.suits)}.{deck_note}", ""]
    lines += ["**Streets.** In order, each street does the following:", "",
              "| Street | Discard first | Hole cards dealt | Board cards dealt | Betting round |",
              "| :- | -: | -: | -: | :- |"]
    for st in spec.streets:
        lines.append(f"| {st.name} | {st.discard or ''} | {st.hole or ''} | {st.board or ''} | {'yes' if st.bet else 'no'} |")
    lines += ["", f"Each player ends with {spec.hole_count} hole cards; the board ends with {spec.board_count} cards."]
    if any(st.discard for st in spec.streets):
        lines.append("Discards happen at the start of their street, before that street's cards, for every player "
                     "still in the hand. Return `{\"action\": \"discard\", \"cards\": [...]}` with the cards you throw away.")
    lines += ["", f"**Making a hand.** Your hand is {_card_use_text(spec)}.", "",
              f"**Hand rankings, strongest first.** {_straights_text(spec)}"
              + (" **The order differs from standard hold'em**: check it." if tuple(order) != STANDARD_ORDER else ""), "",
              f"| Rank | Hand | Example (hole · board) | How often a player ends with it |", "| -: | :- | :- | -: |"]
    for i, cat in enumerate(reversed(order), 1):
        ex = examples.get(cat)
        ex_text = (" ".join(card_str(c) for c in ex[0]) + " · " + " ".join(card_str(c) for c in ex[1])) if ex else "not possible"
        freq = f"{100 * counts[cat] / total:.3f}%" if counts[cat] else "0% (impossible here)"
        lines.append(f"| {i} | {CATEGORY_NAMES[cat]} | {ex_text} | {freq} |")
    flags = []
    for i, hi_cat in enumerate(order):
        for lo_cat in order[:i]:
            surprising = HOLDEM_7CARD[hi_cat] < HOLDEM_7CARD[lo_cat]
            if surprising and counts[lo_cat] and counts[hi_cat] > counts[lo_cat] * 1.05:
                flags.append(f"{CATEGORY_NAMES[hi_cat]} ranks above {CATEGORY_NAMES[lo_cat].lower()} "
                             f"but is more common here ({100 * counts[hi_cat] / total:.2f}% vs "
                             f"{100 * counts[lo_cat] / total:.2f}%), unlike hold'em")
    for cat in order:
        if not counts[cat]:
            flags.append(f"{CATEGORY_NAMES[cat]} can't be made with this deck")
    lines += ["", f"Frequencies were measured on {total:,} random deals of this variant: one player's final cards."]
    if flags:
        lines += ["", "**Watch out:**"] + [f"- {f}." for f in flags]
    lines += [""] + _betting_text(spec, card)
    lines += ["", "## Table and scoring", "",
              f"- **Seats and stacks.** {card['seats']} seats, {card['starting_stack']:,} chips each.",
              f"- **End of a table.** One player has every chip, or {card['hand_cap']} hands have been played. "
              "At the cap, the survivors split the points of the places still open by ICM (exactly `kit/icm.py`).",
              f"- **Blinds.** They rise every {card['level_hands']} hands; past the last level, it repeats.", "",
              "| Level | Hands | Small blind | Big blind | Ante |", "| -: | :- | -: | -: | -: |"]
    for k, (sb, bb, ante) in enumerate(card["blinds"]):
        a, z = k * card["level_hands"] + 1, (k + 1) * card["level_hands"]
        lines.append(f"| {k + 1} | {a}–{z} | {sb} | {bb} | {ante or ''} |")
    pts = card["points"]
    lines += ["", "**Points by finishing place.** Players eliminated in the same hand place by their stacks at the "
              "start of that hand; exactly equal stacks share those places' points.", "",
              "| " + " | ".join(f"{k + 1}{'st' if k == 0 else 'nd' if k == 1 else 'rd' if k == 2 else 'th'}"
                                 for k in range(len(pts))) + " |",
              "|" + " -: |" * len(pts), "| " + " | ".join(f"{p:g}" for p in pts) + " |", ""]
    t = card["tournaments"]
    lines += ["## Tournament plan", "",
              f"- **Build window.** {card['build_minutes']:g} minutes. Submit with `python kit/submit.py`; at most one "
              f"accepted submission every {card['cooldown_seconds']:g} seconds, and your latest accepted one plays.",
              f"- **Tournaments.** {t}: " + ", ".join(f"T{k} weight {k}" for k in range(1, t + 1))
              + f". Each is {card['iterations']} iterations; every iteration seats every bot once at random tables. "
              "Your score is your average points per table.",
              (f"- **Between tournaments.** A {card['patch_minutes']:g}-minute patch window to submit fixes; "
               "the bot that plays a tournament is frozen when it starts.") if t > 1 else "",
              f"- **Limits.** {card['decision_limit_ms']:g} ms of CPU per `act()` call; `__init__` "
              f"{card['init_limit_s']:g} s per table; import {card['import_limit_s']:g} s; "
              f"`bot/` at most {card['bot_size_limit_mb']:g} MB; standard library plus "
              f"{', '.join(card['allowed_packages']) or 'nothing else'}.", ""]
    return "\n".join(line for line in lines if line is not None)
