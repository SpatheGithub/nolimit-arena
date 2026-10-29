"""Untimed, in-process table play for tests and quick experiments.

No CPU limits, watchdog or isolation: an exception or a malformed or illegal
action is substituted (fold, or check when free) and counted, nothing more.
Tournaments use arena.tournament instead.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence

from ..engine.hand import IllegalAction
from ..engine.spec import NLHE, VariantSpec
from ..engine.table import DOUBLING, Table
from .obs import BadAction, build_obs, hand_end_event, parse_action, table_config

POINTS = (100, 60, 40, 25, 15, 10, 5, 0)


def play_local_table(agent_classes: Sequence[Callable[[dict], object]], *, seed: int = 0,
                     spec: VariantSpec = NLHE, points: Sequence[float] = POINTS,
                     blinds: Sequence[Sequence[int]] = DOUBLING, level_hands: int = 25,
                     hand_cap: int = 200, starting_stack: int = 2000) -> tuple[Table, list[Counter]]:
    """Seat one agent per class (seat i = agent_classes[i]) and play the table out.

    Returns the finished table and, per seat, a Counter of decisions and
    substitutions ("error", "illegal")."""
    rng = random.Random(seed)
    n = len(agent_classes)
    table = Table(spec, n_seats=n, starting_stack=starting_stack, blinds=blinds,
                  level_hands=level_hands, hand_cap=hand_cap, rng=random.Random(rng.randrange(2**63)))
    agents = []
    for s, cls in enumerate(agent_classes):
        cfg = table_config(spec, seat=s, seed=rng.randrange(2**31), points=points, blinds=blinds,
                           level_hands=level_hands, hand_cap=hand_cap, seats=n,
                           starting_stack=starting_stack, decision_limit_ms=1.0)
        agents.append(cls(cfg))
    counts = [Counter() for _ in range(n)]
    while not table.over():
        hand = table.start_hand()
        while hand.to_act is not None:
            seat = table.seats[hand.to_act]
            counts[seat]["decisions"] += 1
            legal = hand.legal()
            try:
                name, amount, cards = parse_action(agents[seat].act(build_obs(table, hand, legal)))
                hand.act(name, amount, cards)
            except (BadAction, IllegalAction):
                counts[seat]["illegal"] += 1
                hand.act_default()
            except Exception:
                counts[seat]["error"] += 1
                hand.act_default()
        dealt = list(table.seats)
        out = table.finish_hand()
        event = hand_end_event(table, hand, out)
        for seat in dealt:
            obs_fn = getattr(agents[seat], "observe", None)
            if obs_fn is not None:
                try:
                    obs_fn(event)
                except Exception:
                    counts[seat]["observe_error"] += 1
    return table, counts
