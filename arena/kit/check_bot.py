"""Check bot/ the way submit.py will, plus fuzzing and a timing profile. Submits nothing.

    python kit/check_bot.py [--tables 4]

The fuzz pass replays the smoke match with steep blinds, so all-ins, side
pots, short stacks and heads-up endings come up often. Timings on a busy
machine are higher than the referee's, which re-times bots on an idle one.
"""

import argparse
import os
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(KIT)
sys.path.insert(0, KIT)

from arena.tournament.card import load_card, settings_from_card  # noqa: E402
from arena.tournament.validate import describe, validate  # noqa: E402

STEEP = tuple((25 * 2**k, 50 * 2**k, 5 * 2**k) for k in range(8))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tables", type=int, default=4)
    a = ap.parse_args()
    card = load_card(os.path.join(KIT, "event.json"))
    settings = settings_from_card(card)
    bot, house = os.path.join(WS, "bot"), os.path.join(KIT, "house_bots")
    seed = int(time.time()) % 100_000
    print("Smoke match, as submit.py runs it:", flush=True)
    v = validate(bot, settings, house, tables=a.tables, seed=seed)
    for line in describe(v):
        print(line)
    if not v["reasons"] or v["stats"]:
        print("Fuzz pass (steep blinds, frequent all-ins and short stacks):", flush=True)
        fuzz = validate(bot, settings, house, tables=a.tables, seed=seed + 1,
                        extra_settings=settings_from_card(card, blinds=STEEP, level_hands=10))
        for line in describe(fuzz):
            print(line)
        v["reasons"] += [f"fuzz: {r}" for r in fuzz["reasons"]]
    print("OK: submit.py should accept this bot." if not v["reasons"] else
          "NOT OK: submit.py would reject this bot.")
    return 0 if not v["reasons"] else 1


if __name__ == "__main__":
    sys.exit(main())
