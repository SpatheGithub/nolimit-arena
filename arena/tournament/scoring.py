"""Points for one table, and summary statistics across tables.

A bot that busts scores the points of its place; bots that bust in the same
hand with exactly equal starting stacks share their places' points evenly.
Survivors at the hand cap split the points of the places still open by ICM
(arena/kit/icm.py, the calculator builders get).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ..kit.icm import icm_equity


def table_points(places: Mapping[int, tuple[int, int]], survivors: Sequence[int],
                 stacks: Sequence[int], points: Sequence[float]) -> list[float]:
    """Points per seat. ``places`` maps busted seats (and a lone winner) to
    (best, worst) place; unplaced ``survivors`` share the open places by ICM."""
    n = len(stacks)
    pts = list(points)[:n] + [0.0] * max(0, n - len(points))
    out = [0.0] * n
    for seat, (best, worst) in places.items():
        out[seat] = sum(pts[best - 1:worst]) / (worst - best + 1)
    open_seats = [s for s in survivors if s not in places]
    if open_seats:
        eq = icm_equity([stacks[s] for s in open_seats], pts[:len(open_seats)])
        for s, e in zip(open_seats, eq):
            out[s] = e
    return out


def mean_ci(values: Sequence[float], z: float = 1.959964) -> tuple[float, float, float, float]:
    """Mean, standard error and a normal 95% interval."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    m = sum(values) / n
    if n < 2:
        return m, 0.0, m, m
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    se = math.sqrt(var / n)
    return m, se, m - z * se, m + z * se
