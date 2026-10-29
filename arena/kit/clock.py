"""Time left in the current window, and what happens when it ends.

    python kit/clock.py
"""

import os
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(KIT)
sys.path.insert(0, KIT)

from arena.tournament.card import load_card  # noqa: E402
from arena.tournament.wsstate import (fmt_clock, fmt_duration, last_accepted, next_allowed,  # noqa: E402
                                      read_windows, window_at)


def main() -> int:
    now = time.time()
    card = load_card(os.path.join(KIT, "event.json"))
    windows = read_windows(WS)
    current, upcoming = window_at(windows, now)
    if not windows:
        print("Practice mode: no event windows are set, so submissions are always open.")
    elif current:
        print(f"{current['name']}: {fmt_duration(current['end'] - now)} left (ends {fmt_clock(current['end'])}).")
        if current.get("then"):
            print(f"Then: {current['then']}")
    elif upcoming:
        print(f"No window is open. Next: {upcoming['name']} at {fmt_clock(upcoming['start'])} "
              f"(in {fmt_duration(upcoming['start'] - now)}).")
    else:
        print("All of this event's windows are over.")
    last = last_accepted(WS)
    if last:
        print(f"Active submission: {last['id']} (accepted {fmt_clock(last['time'])}).")
    else:
        print("No accepted submission yet: a team without one doesn't play.")
    wait = next_allowed(WS, card["cooldown_seconds"]) - now
    print("Next submission allowed now." if wait <= 0 else f"Next submission allowed in {fmt_duration(wait)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
