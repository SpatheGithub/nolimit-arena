"""Play sit-and-gos with bot/ against house bots or copies of itself.

    python kit/localsim.py [--opponents zoo|self|name,name,...] [--tables 50] [--seed 1]

Uses one core under nice, today's rules from kit/event.json, and the real
runner (timing, substitutions). Capped at the event's localsim limits because
other teams share the machine.
"""

import argparse
import os
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(KIT)
sys.path.insert(0, KIT)

from arena.tournament.card import load_card, settings_from_card  # noqa: E402
from arena.tournament.pool import Entry  # noqa: E402
from arena.tournament.tournament import run_tournament  # noqa: E402
from arena.tournament.validate import house_opponents  # noqa: E402


def main() -> int:
    card = load_card(os.path.join(KIT, "event.json"))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--opponents", default="zoo", help="zoo, self, or comma-separated house bot names")
    ap.add_argument("--tables", type=int, default=min(50, card["localsim_max_tables"]))
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    try:
        os.nice(10)
    except OSError:
        pass
    bot, house = os.path.join(WS, "bot"), os.path.join(KIT, "house_bots")
    n_opp = card["seats"] - 1
    if a.opponents == "self":
        opponents = [Entry(f"self_{i + 1}", bot) for i in range(n_opp)]
    elif a.opponents == "zoo":
        opponents = house_opponents(house, bot, n_opp)
    else:
        names = [x.strip() for x in a.opponents.split(",") if x.strip()]
        missing = [n for n in names if not os.path.isfile(os.path.join(house, n, "agent.py"))]
        if missing:
            print(f"unknown house bots: {', '.join(missing)}; see kit/house_bots/")
            return 2
        opponents = [Entry(f"{names[i % len(names)]}_{i + 1}", os.path.join(house, names[i % len(names)]))
                     for i in range(n_opp)]
    tables = max(1, min(a.tables, card["localsim_max_tables"]))
    settings = settings_from_card(card, hand_logs=False)
    t0 = time.time()
    res = run_tournament([Entry("you", bot)] + opponents, settings, iterations=tables, seed=a.seed,
                         workers=1, time_budget_s=card["localsim_max_seconds"])
    rows = sorted(res["entries"], key=lambda r: r["rank"])
    me = next(r for r in rows if r["name"] == "you")
    print(f"{res['meta']['tables']} tables in {time.time() - t0:.0f}s"
          + (" (stopped at the time limit)" if res["meta"]["tables"] < tables else ""))
    for r in rows:
        mark = "  <- you" if r["name"] == "you" else ""
        print(f"{r['rank']:>2}. {r['name']:<16} {r['mean']:7.2f} ± {1.96 * r['se']:5.2f} points/table{mark}")
    print(f"you: vpip {me['vpip']:.0%}, pfr {me['pfr']:.0%}, showdowns {me['wtsd']:.0%}; "
          f"timing p50 {me['cpu_p50_us']:.0f} µs, p99 {me['cpu_p99_us']:.0f} µs, max {me['cpu_max_us']:.0f} µs; "
          f"substitutions {me['timeouts']} timeout, {me['errors']} error, {me['illegal']} illegal, {me['hangs']} hang")
    for line in me["output"][:5]:
        print(f"  your output: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
