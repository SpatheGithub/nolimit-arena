"""Offline: percentiles, equity vs top-x% ranges and chip-EV push/fold charts.

Reads eq_<deck>.npz from gen_equity.py; prints the encoded data block for _common.py.

Push/fold model (chip EV, all stacks S big blinds, blinds 0.5/1, no antes): the
pusher has k players behind; callers act in order and the first caller ends
the action. Roles behind: 'other' x (k-2), SB, BB (k = 1: the pusher is the
SB and only the BB is behind). Strategies come from fictitious play.
"""

import base64
import sys
from array import array

import numpy as np

GRID = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.18, 0.22,
        0.26, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.85, 1.0]
SGRID = [s / 2 for s in range(2, 41)]   # 1.0 .. 20.0 big blinds
POST = {"other": 0.0, "SB": 0.5, "BB": 1.0}
ROLES = ("other", "SB", "BB")


def range_weights(order, combos, x):
    """Per-class weight (0..1) of the top-x fraction of combos in ``order``."""
    total = combos.sum()
    need = x * total
    r = np.zeros(len(combos))
    for a in order:
        if need <= 0:
            break
        take = min(combos[a], need)
        r[a] = take / combos[a]
        need -= take
    return r


def eq_vs(E, W, a_weights_rows, r):
    """Equity of each class vs range weights r (card removal through W)."""
    num = (W * E) @ r
    den = W @ r
    out = np.where(den > 1e-12, num / np.maximum(den, 1e-12), 0.5)
    return out


def solve(E, W, combos, k, S, iters=500):
    m = len(combos)
    roles = ["BB"] if k == 1 else ["other"] * (k - 2) + ["SB", "BB"]
    post_p = 0.5 if k == 1 else 0.0
    D = 1.5
    WE = W * E
    wtot = W.sum(1)
    P = np.zeros(m)
    eqr = (WE.sum(1) / wtot)
    order = np.argsort(-eqr)
    P[order[: m // 3]] = 1.0
    C = {r: np.zeros(m) for r in set(roles)}
    for r in C:
        C[r][order[: m // 10]] = 1.0
    for t in range(1, iters + 1):
        # callers' best responses vs P
        num = WE @ P          # sum_a W[b][a] P[a] E[b][a]: rows b of W and E
        den = W @ P
        eqc = np.where(den > 1e-12, num / np.maximum(den, 1e-12), 0.0)
        brc = {}
        for r in C:
            pot = 2 * S + D - post_p - POST[r]
            brc[r] = (eqc * pot - S >= -POST[r]).astype(float)
        # pusher's best response vs C
        nocall = np.ones(m)
        ev = np.zeros(m)
        for r in roles:
            pot = 2 * S + D - post_p - POST[r]
            dc = W @ C[r]
            c = dc / wtot
            eqv = np.where(dc > 1e-12, (WE @ C[r]) / np.maximum(dc, 1e-12), 0.5)
            ev += nocall * c * (eqv * pot - S)
            nocall = nocall * (1 - c)
        ev += nocall * (D - post_p) + post_p
        brp = (ev > 0).astype(float)
        f = 1.0 / (t + 1)
        P += (brp - P) * f
        for r in C:
            C[r] += (brc[r] - C[r]) * f
    return P, C


def charts(E, W, combos, kmax):
    m = len(combos)
    push = np.zeros((kmax, m), dtype=int)
    call = np.zeros((kmax, 3, m), dtype=int)
    for k in range(1, kmax + 1):
        alive_p = np.ones(m, dtype=bool)
        alive_c = np.ones((3, m), dtype=bool)
        for S in SGRID:
            P, C = solve(E, W, combos, k, S)
            code = int(round(2 * S))
            pushed = (P >= 0.5) & alive_p
            push[k - 1][pushed] = code
            alive_p &= P >= 0.5
            for ri, r in enumerate(ROLES):
                if r in C:
                    called = (C[r] >= 0.5) & alive_c[ri]
                    call[k - 1][ri][called] = code
                    alive_c[ri] &= C[r] >= 0.5
        push[k - 1][alive_p] = 255
        present = {"BB"} if k == 1 else ({"SB", "BB"} | ({"other"} if k >= 3 else set()))
        for ri, r in enumerate(ROLES):
            if r in present:
                call[k - 1][ri][alive_c[ri]] = 255
        print("k", k, "push frac at 10bb", combos[push[k - 1] >= 20].sum() / combos.sum(), file=sys.stderr)
    return push, call


def b64(typecode, values):
    return base64.b64encode(array(typecode, values).tobytes()).decode()


def build(name, path, kmax):
    d = np.load(path)
    E, W, combos, multi = d["E"], d["W"], d["combos"].astype(float), d["multi"]
    m = len(combos)
    eqr = multi[:, 0]
    order = list(np.argsort(-eqr, kind="stable"))
    cum = 0.0
    pct = np.zeros(m)
    total = combos.sum()
    for a in order:
        pct[a] = (cum + combos[a] / 2) / total
        cum += combos[a]
    eqtop = np.zeros((m, len(GRID)))
    for gi, x in enumerate(GRID):
        r = range_weights(order, combos, x)
        eqtop[:, gi] = eq_vs(E, W, None, r)
    push, call = charts(E, W, combos, kmax)
    q = lambda v: [int(round(min(max(float(x), 0.0), 1.0) * 10000)) for x in v]  # noqa: E731
    ranks = {"std": "23456789TJQKA", "short": "6789TJQKA", "royal": "TJQKA"}[name]
    out = {
        "ranks": ranks,
        "kmax": kmax,
        "pct": q(pct),
        "eq_top": [q(row) for row in eqtop],
        "eq_multi": [q(row) for row in multi],
        "push": [[int(x) for x in row] for row in push],
        "call": [[[int(x) for x in row] for row in rows] for rows in call],
    }
    return out, (eqr, order, pct, eqtop, push, call)


if __name__ == "__main__":
    sp = sys.argv[1]
    import json
    res = {}
    for name, kmax in (("std", 7), ("short", 7), ("royal", 6)):
        out, _ = build(name, f"{sp}/eq_{name}.npz", kmax)
        res[name] = out
    doc = {
        "about": "Preflop tables for the house bots, generated offline with arena.engine's evaluator "
                 "by Monte Carlo (class vs class: 2400/6000/20000 boards per pair for std/short/royal; "
                 "class vs k random hands: 12000/16000/30000 deals). Classes: pair hi*n+hi, suited hi*n+lo, "
                 "offsuit lo*n+hi, with hi/lo the rank positions within the deck. Values x 1e-4. "
                 "pct: midpoint percentile by equity vs one random hand (0 = best). eq_top[c][g]: equity vs "
                 "a random hand from the top grid[g] of combos, card removal included. eq_multi[c][k-1]: "
                 "equity vs k random hands. push[k-1][c] / call[k-1][role][c] (role: other, SB, BB): chip-EV "
                 "push/fold equilibrium (fictitious play; stacks S big blinds, blinds 0.5/1, no antes, one "
                 "caller at most) with k players behind the pusher; the hand is pushed/called at every S up "
                 "to code/2 big blinds; 255 = at every S up to 20; 0 = never.",
        "grid": GRID,
        "decks": res,
    }
    json.dump(doc, open(f"{sp}/_common.json", "w"), separators=(",", ":"))
    import os
    print("ok", os.path.getsize(f"{sp}/_common.json"))
