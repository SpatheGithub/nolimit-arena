"""Engine and evaluator throughput.

    python -m arena.bench [--seconds 3] [--workers 1,4,9]

Engine numbers are hands per second on one core while playing full 8-seat
sit-and-go tables with trivial policies that work straight off
``Hand.legal()``, so they exclude bot time. With --workers, the random-policy
table loop also runs in that many processes at once, and per-process
throughput is reported.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import random
import time

from .engine.evaluate import get_evaluator
from .engine.spec import NLHE
from .engine.table import Table


def call_station(rng):
    def decide(table, hand):
        hand.act("call" if hand.legal().call else "check")
    return decide


def check_fold(rng):
    def decide(table, hand):
        hand.act("check" if hand.legal().check else "fold")
    return decide


def random_policy(rng):
    def decide(table, hand):
        lg = hand.legal()
        r = rng.random()
        if lg.raise_max and r < 0.15:
            hand.act("raise", lg.raise_min if r < 0.1 else lg.raise_max)
        elif lg.fold and r < 0.5:
            hand.act("fold")
        else:
            hand.act("call" if lg.call else "check")
    return decide


POLICIES = {"call station": call_station, "random": random_policy, "check/fold": check_fold}


def bench_tables(policy: str, seconds: float, seed: int = 0) -> tuple[float, float]:
    """Hands per second and the share of hands that reached showdown."""
    rng = random.Random(seed)
    decide = POLICIES[policy](rng)
    hands = showdowns = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        t = Table(NLHE, rng=rng)
        while not t.over():
            h = t.start_hand()
            while h.to_act is not None:
                decide(t, h)
            showdowns += h.result.showdown
            t.finish_hand()
            hands += 1
    return hands / (time.perf_counter() - t0), showdowns / max(hands, 1)


def bench_evaluator(seconds: float) -> tuple[float, float]:
    """7-card evaluations per second, and microseconds per 8-player showdown."""
    ev = get_evaluator(NLHE)
    rng = random.Random(1)
    deck = NLHE.deck()
    hands = [rng.sample(deck, 7) for _ in range(20000)]
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds / 2:
        for c in hands:
            ev.evaluate(c[:2], c[2:])
        n += len(hands)
    rate = n / (time.perf_counter() - t0)
    deals = []
    for _ in range(5000):
        d = rng.sample(deck, 21)
        deals.append(([d[2 * i:2 * i + 2] for i in range(8)], d[16:]))
    showdown = getattr(ev, "showdown", None) or (lambda holes, board: [ev.evaluate(h, board) for h in holes])
    m = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds / 2:
        for holes, board in deals:
            showdown(holes, board)
        m += len(deals)
    return rate, 1e6 * (time.perf_counter() - t0) / m


def _worker(args):
    seconds, seed = args
    return bench_tables("random", seconds, seed)[0]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--workers", default="", help="comma-separated process counts, e.g. 1,4,9")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    get_evaluator(NLHE)
    build = time.perf_counter() - t0
    rate, sd = bench_evaluator(a.seconds)
    print(f"evaluator  {type(get_evaluator(NLHE)).__name__}: {rate / 1e6:.2f}M 7-card evals/s, "
          f"8-player showdown {sd:.1f} µs, tables built in {build:.2f}s")
    print("engine     8-seat sit-and-go tables, one core, excluding bot time:")
    for name in POLICIES:
        hps, share = bench_tables(name, a.seconds)
        print(f"  {name:<13} {hps:>8,.0f} hands/s  ({share:.0%} reach showdown)")
    for w in [int(x) for x in a.workers.split(",") if x]:
        with mp.get_context("spawn").Pool(w) as pool:
            rates = pool.map(_worker, [(a.seconds, s) for s in range(w)])
        print(f"  random x{w:<3} {sum(rates) / w:>8,.0f} hands/s per process, {sum(rates):,.0f} total")


if __name__ == "__main__":
    main()
