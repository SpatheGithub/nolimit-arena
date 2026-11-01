"""Independent Chip Model (Malmuth-Harville), exactly as the referee scores it.

At the 200-hand cap the surviving bots split the points of the places still
open: a player's chance of finishing next is its share of the remaining
chips, place by place.

    icm_equity([5000, 3000, 2000], [100, 60, 40])  ->  [76.79, 65.50, 57.71] (rounded)

Standard library only, safe to copy into bot/. Cost grows with 2**players
over the paid places, so cache results if you call it at decision time.
"""

from __future__ import annotations

from collections.abc import Sequence


def icm_equity(stacks: Sequence[float], payouts: Sequence[float]) -> list[float]:
    """Expected payout per player. ``payouts[k]`` is the prize for finishing
    (k+1)-th among these players; missing places pay 0. Players with no chips
    finish after everyone with chips, sharing their places evenly."""
    n = len(stacks)
    if n == 0:
        return []
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    paid = max((k + 1 for k, p in enumerate(pay) if p), default=0)
    if paid == 0:
        return [0.0] * n
    full = (1 << n) - 1
    memo: dict[int, list[float]] = {}

    def rest(mask: int) -> list[float]:
        """Expected payouts of the players in ``mask``, who hold the places
        from n - len(mask) onward."""
        got = memo.get(mask)
        if got is not None:
            return got
        res = [0.0] * n
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        if members and place < paid:
            total = sum(stacks[i] for i in members)
            for i in members:
                p = stacks[i] / total if total > 0 else 1 / len(members)
                if p <= 0:
                    continue
                res[i] += p * pay[place]
                sub = rest(mask & ~(1 << i))
                for j in members:
                    if j != i:
                        res[j] += p * sub[j]
        memo[mask] = res
        return res

    return rest(full)
