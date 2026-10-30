"""Field profile: how each bot plays, from a tournament's hand logs (docs/FIELD_STUDY.md).

The hand log keeps every decision with its street, action, amount and the
amount to call. Replaying each hand's antes, blinds and bets on top of that
tells the situation ("spot") each decision was made in: first in, facing a
steal, facing a shove, holding the preflop raise on the flop, facing a river
bet, and so on. Per bot and spot the profile counts folds, checks, calls and
raises, and sums the big blinds the bot won or lost over those hands, so the
report can set each bot's tendencies against the rest of the field and price
them. For the spots where the bot raised, it also counts how often everyone
else folded.

A spot counts once per player and hand. Filler copies are left out, as in the
summaries. Each tournament's profile is small and is saved next to its hand
log as results/T<k>/profile.json, which git keeps.

    {"version", "entries", "bots": {name: {"hands", "spots": {spot: [n, fold, check, call, raise,
     all-in, bb, bb², took, raise bb, raise bb²]}, "stack": {bucket: [hands, vpip, pfr]},
     "dealt": {group: [hands, vpip, pfr]}, "flop": [saw, showdowns, won], "open_bb": {size: n},
     "bet_pot": {share: n}}}}
"""

from __future__ import annotations

import json
import math
import os

from .handlog import read_index, read_meta, read_table

VERSION = 1
FILE = "profile.json"
N, F, K, C, R, ALLIN, BB, BB2, TOOK, RBB, RBB2 = range(11)
ACTIONS = {"f": F, "k": K, "c": C, "r": R}
LATE = ("CO", "BTN", "SB")
STACKS = ("<10", "10-20", "20-40", "40+")       # chips in big blinds
DEALT = ("7-8", "5-6", "3-4", "2")              # players dealt in
SPOTS = {  # spot: (label, what it is)
    "open_EP": ("Open from early position", "first in, 3+ dealt, not CO/BTN/SB"),
    "open_CO": ("Open from the cutoff", "first in"),
    "open_BTN": ("Open from the button", "first in"),
    "open_SB": ("Open from the small blind", "first in"),
    "steal": ("Steal", "first in from CO, BTN or SB, 3+ dealt"),
    "vs_steal": ("Facing a steal", "SB or BB facing one raise from a late first-in raiser"),
    "vs_open": ("Facing an open", "first decision facing one raise (not a steal on the blinds)"),
    "vs_3bet": ("Facing a 3-bet", "the opener, facing a re-raise"),
    "shove": ("Preflop shove", "any preflop raise all-in"),
    "vs_shove": ("Facing a shove", "preflop, facing an all-in raise"),
    "hu_open": ("Heads-up open", "the button, first decision heads-up"),
    "hu_vs_raise": ("Heads-up vs a raise", "the big blind facing the button's raise"),
    "cbet": ("C-bet", "the preflop raiser's first flop decision, nothing to call"),
    "vs_cbet": ("Facing a c-bet", "facing the preflop raiser's flop bet"),
    "river_bet": ("River bet", "first river decision with nothing to call"),
    "vs_river_bet": ("Facing a river bet", "first river decision facing a bet"),
}
SPOTS.update({f"vs_shove_{b}": (f"Facing a shove with {b} bb", "own chips in big blinds") for b in STACKS})


def _bucket(chips: int, bb: int) -> str:
    x = chips / max(bb, 1)
    return STACKS[0] if x < 10 else STACKS[1] if x < 20 else STACKS[2] if x < 40 else STACKS[3]


def _dealt(n: int) -> str:
    return "2" if n == 2 else "3-4" if n <= 4 else "5-6" if n <= 6 else "7-8"


def _new_bot() -> dict:
    return {"hands": 0, "spots": {}, "stack": {b: [0, 0, 0] for b in STACKS},
            "dealt": {g: [0, 0, 0] for g in DEALT}, "flop": [0, 0, 0], "open_bb": {}, "bet_pot": {}}


def _betting_streets(variant: dict) -> tuple[int | None, int]:
    bet = [i for i, s in enumerate(variant["streets"]) if s.get("bet")]
    return (bet[1] if len(bet) > 1 else None), bet[-1]


def play_hand(h: list, who: list, first_post: int | None, last: int) -> None:
    """Add one logged hand to the per-seat profiles in ``who`` (None for seats not profiled)."""
    _, button, (sb, bb, ante), dealt, start, _, _, decisions, pay, shown = h
    n = len(dealt)
    idx = {s: i for i, s in enumerate(dealt)}
    bi = idx[button]
    sbi, bbi = (bi, 1 - bi) if n == 2 else ((bi + 1) % n, (bi + 2) % n)
    pos = ["EP"] * n
    if n >= 4:
        pos[(bi - 1) % n] = "CO"
    pos[bi], pos[sbi], pos[bbi] = "BTN", "SB", "BB"
    stack, bet = list(start), [0] * n
    if ante:
        for i in range(n):
            stack[i] -= min(ante, stack[i])
    for i, blind in ((sbi, sb), (bbi, bb)):
        put = min(blind, stack[i])
        stack[i] -= put
        bet[i] += put
    cur = max(bet)
    folded, acted = [False] * n, [False] * n
    vpip, pfr, pre_fold = [False] * n, [False] * n, [False] * n
    raises = limpers = callers = 0
    opener = last_raiser = aggressor = None
    steal = last_allin = cbet_made = False
    street, street_raises = 0, 0
    seen: set = set()
    marks: list[tuple[int, str, int, str]] = []   # (player, spot, decision index, action)

    def rec(i: int, spot: str, j: int, a: str, allin: bool) -> None:
        if who[i] is None or (i, spot) in seen:
            return
        seen.add((i, spot))
        v = who[i]["spots"].setdefault(spot, [0] * 11)
        v[N] += 1
        if a in ACTIONS:
            v[ACTIONS[a]] += 1
        v[ALLIN] += allin
        marks.append((i, spot, j, a))

    for j, d in enumerate(decisions):
        st, seat, a, amt, pot = d[1], d[2], d[3], d[4], d[6]
        if a == "d":
            continue
        if st != street:
            street, street_raises, cur, bet, acted = st, 0, 0, [0] * n, [False] * n
            last_allin = False
        i = idx[seat]
        facing = cur > bet[i]
        put = amt if a == "c" else amt - bet[i] if a == "r" else 0
        allin = a in ("c", "r") and put >= stack[i]
        spots = []
        if street == 0:
            if n == 2:
                if i == bi and not acted[i] and raises == 0:
                    spots.append("hu_open")
                elif i == bbi and not acted[i] and raises == 1 and opener == bi:
                    spots.append("hu_vs_raise")
            elif raises == 0 and limpers == 0:
                spots.append(f"open_{pos[i]}")
                if pos[i] in LATE:
                    spots.append("steal")
            elif raises == 1 and not acted[i] and i != opener:
                stolen = steal and callers == 0 and i in (sbi, bbi)
                spots.append("vs_steal" if stolen else "vs_open")
            if raises == 2 and i == opener:
                spots.append("vs_3bet")
            if last_allin and facing and i != last_raiser:
                spots += ["vs_shove", f"vs_shove_{_bucket(stack[i] + bet[i], bb)}"]
            if a == "r" and allin:
                spots.append("shove")
            if a == "r" and raises == 0 and limpers == 0 and who[i] is not None:
                size = f"{round(amt / bb * 2) / 2:g}"
                who[i]["open_bb"][size] = who[i]["open_bb"].get(size, 0) + 1
        else:
            if street == first_post:
                if i == aggressor and not acted[i] and not facing:
                    spots.append("cbet")
                elif cbet_made and street_raises == 1 and facing and i != aggressor:
                    spots.append("vs_cbet")
            if street == last:
                if facing:
                    spots.append("vs_river_bet")
                elif not acted[i]:
                    spots.append("river_bet")
            if a == "r" and not facing and pot > 0 and who[i] is not None:
                share = f"{round(amt / pot, 1):g}"
                who[i]["bet_pot"][share] = who[i]["bet_pot"].get(share, 0) + 1
        for spot in spots:
            rec(i, spot, j, a, allin)
        # apply the action
        if a == "f":
            folded[i] = True
            pre_fold[i] = street == 0
        elif a == "c":
            stack[i] -= put
            bet[i] += put
            if street == 0:
                vpip[i] = True
                if raises == 0:
                    limpers += 1
                elif raises == 1:
                    callers += 1
        elif a == "r":
            stack[i] -= put
            bet[i] = amt
            cur = max(cur, amt)
            if street == 0:
                vpip[i] = pfr[i] = True
                raises += 1
                if raises == 1:
                    opener = i
                    steal = n >= 3 and limpers == 0 and pos[i] in LATE
                aggressor = last_raiser = i
                last_allin = stack[i] == 0
            else:
                street_raises += 1
                if street == first_post and i == aggressor and street_raises == 1:
                    cbet_made = True
        acted[i] = True

    shown_set = set(shown)
    reached_post = bool(shown_set) or any(d[1] > 0 for d in decisions)
    for i, w in enumerate(who):
        if w is None:
            continue
        w["hands"] += 1
        for key, table in ((_bucket(start[i], bb), w["stack"]), (_dealt(n), w["dealt"])):
            row = table[key]
            row[0] += 1
            row[1] += vpip[i]
            row[2] += pfr[i]
        if reached_post and not pre_fold[i]:
            w["flop"][0] += 1
            if dealt[i] in shown_set:
                w["flop"][1] += 1
                w["flop"][2] += pay[i] > 0
    for i, spot, j, a in marks:
        v = who[i]["spots"][spot]
        x = pay[i] / bb
        v[BB] += x
        v[BB2] += x * x
        if a == "r":
            v[RBB] += x
            v[RBB2] += x * x
            if not shown_set and all(d[3] in ("f", "d") for d in decisions[j + 1:] if d[2] != dealt[i]):
                v[TOOK] += 1


def profile_log(directory: str) -> dict:
    """Profile every entry in one tournament's hand log (fillers left out)."""
    meta = read_meta(directory)
    names = meta["entries"]
    first_post, last = _betting_streets(meta["variant"])
    bots = {name: _new_bot() for name in names}
    for m in read_index(directory):
        seat_bot = [None if filler else bots[names[e]] for e, filler in zip(m["entries"], m["fillers"])]
        for h in read_table(directory, m):
            play_hand(h, [seat_bot[s] for s in h[3]], first_post, last)
    for b in bots.values():
        for v in b["spots"].values():
            for k in (BB, BB2, RBB, RBB2):
                v[k] = round(v[k], 3)
    return {"version": VERSION, "entries": names, "bots": bots}


def load(directory: str) -> dict | None:
    """profile.json, or computed (and saved) from a finished hand log; None without either."""
    path = os.path.join(directory, FILE)
    try:
        with open(path) as f:
            got = json.load(f)
        if got.get("version") == VERSION:
            return got
    except (OSError, ValueError):
        pass
    try:
        if not read_meta(directory).get("finished"):
            return None
        got = profile_log(directory)
    except (OSError, ValueError, KeyError):
        return None
    tmp = f"{path}.{os.getpid()}.tmp"  # the report and the live viewer may both be writing it
    with open(tmp, "w") as f:
        json.dump(got, f, separators=(",", ":"))
    os.replace(tmp, path)
    return got


def merge(profiles: list[dict]) -> dict[str, dict]:
    """Pool several tournaments' profiles per bot name."""
    out: dict[str, dict] = {}
    for p in profiles:
        for name, b in p["bots"].items():
            o = out.setdefault(name, _new_bot())
            o["hands"] += b["hands"]
            for spot, v in b["spots"].items():
                ov = o["spots"].setdefault(spot, [0] * 11)
                for k, x in enumerate(v):
                    ov[k] += x
            for key in ("stack", "dealt"):
                for g, row in b[key].items():
                    orow = o[key].setdefault(g, [0, 0, 0])
                    for k, x in enumerate(row):
                        orow[k] += x
            for k, x in enumerate(b["flop"]):
                o["flop"][k] += x
            for key in ("open_bb", "bet_pot"):
                for size, c in b[key].items():
                    o[key][size] = o[key].get(size, 0) + c
    return out


# ---------------------------------------------------------------- reading a merged profile

RESPONDER = ("vs_steal", "vs_open", "vs_3bet", "vs_shove", "hu_vs_raise", "vs_cbet", "vs_river_bet")
BOARD = (  # (aggression, spots where a bot made it by raising, spot where the others faced it)
    ("Steal", ("steal",), "vs_steal"),
    ("3-bet", ("vs_open", "vs_steal"), "vs_3bet"),
    ("Preflop shove", ("shove",), "vs_shove"),
    ("Heads-up raise", ("hu_open",), "hu_vs_raise"),
    ("C-bet", ("cbet",), "vs_cbet"),
    ("River bet", ("river_bet",), "vs_river_bet"),
)
MIN_SPOTS = 30  # fewer occurrences than this say nothing about a bot's result in a spot


def spot(b: dict, spots: tuple[str, ...] | str) -> list[float]:
    """One bot's counts over one or more spots, summed."""
    out = [0.0] * 11
    for s in (spots,) if isinstance(spots, str) else spots:
        for k, x in enumerate(b["spots"].get(s, ())):
            out[k] += x
    return out


def rate(v: list[float], k: int) -> float | None:
    return v[k] / v[N] if v[N] else None


def _mean_se(n: float, s: float, s2: float) -> tuple[float, float]:
    m = s / n
    return m, math.sqrt(max(s2 / n - m * m, 0.0) / n)


def cost(bots: dict[str, dict], name: str, spots: tuple[str, ...] | str) -> tuple[float, float] | None:
    """What a bot's results in a spot cost it against the rest of the field's average result
    there, in big blinds per 100 hands it played, with a standard error; None on too few spots."""
    me = spot(bots[name], spots)
    rest = [sum(x) for x in zip(*(spot(b, spots) for other, b in bots.items() if other != name))] or [0.0] * 11
    if me[N] < MIN_SPOTS or rest[N] < MIN_SPOTS or not bots[name]["hands"]:
        return None
    (mb, sb), (mf, sf) = _mean_se(me[N], me[BB], me[BB2]), _mean_se(rest[N], rest[BB], rest[BB2])
    per100 = me[N] / bots[name]["hands"] * 100
    return (mb - mf) * per100, math.hypot(sb, sf) * per100


def gain(b: dict, spots: tuple[str, ...] | str) -> tuple[float, float | None, float]:
    """Big blinds a bot won per 100 hands in the hands where it made this raise, the share of
    those raises everyone folded to, and how many it made per 100 hands."""
    v = spot(b, spots)
    hands = max(b["hands"], 1)
    return v[RBB] / hands * 100, (v[TOOK] / v[R] if v[R] else None), v[R] / hands * 100


def vpip(b: dict, key: str, group: str) -> tuple[float | None, int]:
    hands, v, _ = b[key].get(group, (0, 0, 0))
    return (v / hands if hands else None), hands


def usual(sizes: dict[str, int]) -> tuple[str | None, float | None]:
    """The most common size and the share of raises made at it."""
    if not sizes:
        return None, None
    size, n = max(sizes.items(), key=lambda x: (x[1], -float(x[0])))
    return size, n / sum(sizes.values())
