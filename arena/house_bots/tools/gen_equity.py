"""Offline: class-vs-class equity matrices and multiway equities, per deck.

Writes eq_<deck>.npz with E (n2 x n2), W (n2 x n2), combos, multi (n2 x kmax).
Run from the repo root with the repo venv.
"""

import multiprocessing as mp
import random
import sys
import time

import numpy as np

sys.path.insert(0, ".")
from arena.engine.fasteval import FastEvaluator  # noqa: E402
from arena.engine.spec import NLHE  # noqa: E402
from arena.engine.xval import ROYAL, SHORTDECK  # noqa: E402

RANKS = "23456789TJQKA"
DECKS = {"std": (NLHE, 2400, 12000, 7), "short": (SHORTDECK, 6000, 16000, 7), "royal": (ROYAL, 20000, 30000, 6)}


def classes(spec):
    dr = sorted(RANKS.index(r) for r in spec.ranks)
    n = len(dr)
    combos = [[] for _ in range(n * n)]
    deck = spec.deck()
    for i, x in enumerate(deck):
        for y in deck[i + 1:]:
            a, b = dr.index(x >> 2), dr.index(y >> 2)
            hi, lo = max(a, b), min(a, b)
            if hi == lo:
                idx = hi * n + hi
            elif (x & 3) == (y & 3):
                idx = hi * n + lo
            else:
                idx = lo * n + hi
            combos[idx].append((x, y))
    return n, combos


def _pair_job(args):
    name, a, b, samples, seed = args
    spec = DECKS[name][0]
    ev = FastEvaluator(spec)
    _, combos = classes(spec)
    deck = spec.deck()
    pairs = [(ca, cb) for ca in combos[a] for cb in combos[b] if not set(ca) & set(cb)]
    if not pairs:
        return a, b, 0.5, 0
    rng = random.Random(seed)
    win = 0.0
    evaluate = ev.evaluate
    for t in range(samples):
        ca, cb = pairs[t % len(pairs)]
        hole = set(ca) | set(cb)
        board = [c for c in rng.sample(deck, 9) if c not in hole][:5]
        va = evaluate(ca, board)
        vb = evaluate(cb, board)
        win += 1.0 if va > vb else 0.5 if va == vb else 0.0
    return a, b, win / samples, len(pairs)


def _multi_job(args):
    name, a, samples, kmax, seed = args
    spec = DECKS[name][0]
    ev = FastEvaluator(spec)
    _, combos = classes(spec)
    deck = spec.deck()
    rng = random.Random(seed)
    acc = [0.0] * kmax
    evaluate = ev.evaluate
    for t in range(samples):
        ca = combos[a][t % len(combos[a])]
        rest = [c for c in deck if c not in ca]
        draw = rng.sample(rest, 2 * kmax + 5)
        board = draw[:5]
        hv = evaluate(ca, board)
        best = -1
        eqc = 0
        for k in range(kmax):
            v = evaluate(draw[5 + 2 * k:7 + 2 * k], board)
            if v > best:
                best = v
            if v == hv:
                eqc += 1
            if hv > best:
                acc[k] += 1.0
            elif hv == best:
                acc[k] += 1.0 / (1 + eqc)
    return a, [x / samples for x in acc]


def compat(combos):
    m = len(combos)
    W = np.zeros((m, m))
    for a in range(m):
        for b in range(m):
            tot = 0
            for ca in combos[a]:
                sa = set(ca)
                tot += sum(1 for cb in combos[b] if not sa & set(cb))
            W[a, b] = tot / len(combos[a])
    return W


def main(name, workers):
    spec, ns, nm, kmax = DECKS[name]
    n, combos = classes(spec)
    m = n * n
    t0 = time.time()
    jobs = [(name, a, b, ns, a * 1000 + b) for a in range(m) for b in range(a + 1, m)]
    E = np.full((m, m), 0.5)
    with mp.Pool(workers) as pool:
        for a, b, e, _ in pool.imap_unordered(_pair_job, jobs, chunksize=64):
            E[a, b] = e
            E[b, a] = 1 - e
        print(name, "pairs done", time.time() - t0, flush=True)
        multi = np.zeros((m, kmax))
        mjobs = [(name, a, nm, kmax, 7_000_000 + a) for a in range(m)]
        for a, row in pool.imap_unordered(_multi_job, mjobs):
            multi[a] = row
    print(name, "multi done", time.time() - t0, flush=True)
    W = compat(combos)
    np.savez(f"{OUT}/eq_{name}.npz", E=E, W=W, combos=np.array([len(c) for c in combos]), multi=multi)


if __name__ == "__main__":
    OUT = sys.argv[1]
    for nm in sys.argv[2:]:
        main(nm, 6)
