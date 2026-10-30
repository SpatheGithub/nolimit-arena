"""REPORT.md's field-study sections (docs/FIELD_STUDY.md, milestone 7): the rank
view, the field profile with each bot's biggest leaks, and the exploit board.

The rank view is the Results view's bootstrap over whole tables
(arena/viz/results.py). The profile and the board come from each tournament's
hand log (arena/tournament/profile.py, cached as results/T<k>/profile.json),
pooled over the event's finished tournaments.
"""

from __future__ import annotations

import os

from ..tournament import profile as pf
from ..viz.results import BOOT, event_results

RARE = 300  # rates resting on fewer decisions than this are marked †


def _pct(x: float | None, n: float | None = None) -> str:
    if x is None:
        return "—"
    return f"{x:.0%}" + ("†" if n is not None and n < RARE else "")


def _spot_rate(spots, k):
    def get(b):
        v = pf.spot(b, spots)
        return pf.rate(v, k), v[pf.N]
    return get


def _vpip(b):
    return sum(r[1] for r in b["stack"].values()) / max(b["hands"], 1), b["hands"]


def _pfr(b):
    return sum(r[2] for r in b["stack"].values()) / max(b["hands"], 1), b["hands"]


def _wtsd(b):
    saw, sd, _ = b["flop"]
    return (sd / saw if saw else None), saw


def _wsd(b):
    _, sd, won = b["flop"]
    return (won / sd if sd else None), sd


def _vpip_in(key, group):
    return lambda b: pf.vpip(b, key, group)


PREFLOP = (("VPIP", _vpip), ("PFR", _pfr), ("Steals", _spot_rate("steal", pf.R)),
           ("Folds to a steal", _spot_rate("vs_steal", pf.F)),
           ("3-bets an open", _spot_rate(("vs_open", "vs_steal"), pf.R)),
           ("Folds to a 3-bet", _spot_rate("vs_3bet", pf.F)), ("Calls a shove", _spot_rate("vs_shove", pf.C)))
POSTFLOP = (("C-bets", _spot_rate("cbet", pf.R)), ("Folds to a c-bet", _spot_rate("vs_cbet", pf.F)),
            ("Calls a river bet", _spot_rate("vs_river_bet", pf.C)), ("Went to showdown", _wtsd),
            ("Won at showdown", _wsd), ("Raises first in heads-up", _spot_rate("hu_open", pf.R)),
            ("Folds to a heads-up raise", _spot_rate("hu_vs_raise", pf.F)))
DEPTH = tuple((f"{g.replace('-', '–')} bb", _vpip_in("stack", g)) for g in pf.STACKS) + \
    tuple(("Heads-up" if g == "2" else f"{g.replace('-', '–')} dealt", _vpip_in("dealt", g)) for g in pf.DEALT)
SHOVE_CALLS = tuple((f"{g.replace('-', '–')} bb", _spot_rate(f"vs_shove_{g}", pf.C)) for g in pf.STACKS)
ACTION_WORDS = ((pf.F, "folds"), (pf.C, "calls"), (pf.R, "raises"))


def _table(title: str, cols, order: list[str], bots: dict, field: dict, note: str = "") -> list[str]:
    lines = [f"### {title}", ""] + ([note, ""] if note else [])
    lines += ["| Bot | " + " | ".join(h for h, _ in cols) + " |", "| :- |" + " -: |" * len(cols)]
    for name in order:
        lines.append(f"| {name} | " + " | ".join(_pct(*fn(bots[name])) for _, fn in cols) + " |")
    cells = []
    for _, fn in cols:
        got = [fn(bots[name])[0] for name in order]
        got = [x for x in got if x is not None]
        spread = f" ({min(got):.0%}–{max(got):.0%})" if len(got) > 1 else ""
        cells.append(_pct(fn(field)[0]) + spread)
    return lines + ["| **Field** | " + " | ".join(cells) + " |", ""]


def _why(bots: dict, name: str, spots) -> str:
    """The action whose frequency differs most from the rest of the field's."""
    me = pf.spot(bots[name], spots)
    rest = [sum(x) for x in zip(*(pf.spot(b, spots) for other, b in bots.items() if other != name))]
    best = max(ACTION_WORDS, key=lambda kw: abs((pf.rate(me, kw[0]) or 0) - (pf.rate(rest, kw[0]) or 0)))
    return f"{best[1]} {pf.rate(me, best[0]):.0%} against {pf.rate(rest, best[0]):.0%}"


def leaks(bots: dict, name: str, top: int = 2) -> list[tuple[str, float, float, str]]:
    """The responder spots that cost a bot the most against the rest of the field:
    (spot, bb/100 hands, standard error, what it does differently)."""
    got = []
    for s in pf.RESPONDER:
        c = pf.cost(bots, name, s)
        if c and c[0] < 0:
            got.append((s, c[0], c[1], _why(bots, name, s)))
    return sorted(got, key=lambda x: x[1])[:top]


def rank_md(res: dict) -> list[str]:
    rows = res["rows"]
    if not rows:
        return []
    method = res.get("rank_method")
    how = (f"{BOOT:,} bootstrap resamples of whole tables: every resample redraws each finished tournament's "
           "tables with replacement, so one bot's points stay another's loss" if method == "bootstrap" else
           "normal draws around each weighted score (no per-table points or hand logs to resample)")
    n = len(rows)
    lines = ["## Rank view", "",
             f"Each bot's final rank across {how}. The top {res['cutoff']} at a regional advance, so P(top "
             f"{res['cutoff']}) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.", ""]
    head = "| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range |"
    if n <= 10:
        head += " " + " | ".join(f"P({r})" for r in range(1, n + 1)) + " |"
    lines += [head, "| :- | -: | -: | -: | -: | :- |" + (" -: |" * n if n <= 10 else "")]
    for r in rows:
        lo, hi = r.get("rank_range") or (None, None)
        line = (f"| {r['team']} | {r['weighted']:.1f} ± {r['ci']:.1f} | {r['p_first']:.0%} | {r['p_top']:.0%} | "
                f"{r.get('rank_median', '—')} | {lo}–{hi} |")
        if n <= 10 and r.get("ranks"):
            line += " " + " | ".join(f"{p:.0%}" if p >= 0.005 else "·" for p in r["ranks"]) + " |"
        lines.append(line)
    return lines + [""]


def profile_md(bots: dict, order: list[str], tournaments: list[int]) -> list[str]:
    field = pf.merge([{"bots": {"field": b}} for b in bots.values()])["field"]
    hands = sum(b["hands"] for b in bots.values())
    lines = ["## Field profile", "",
             f"How the bots played, from the hand logs of T{tournaments[0]}–T{tournaments[-1]} "
             f"({hands:,} bot-hands; every version a team entered, pooled). The field row pools every bot's "
             "decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of "
             f"decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than {RARE}.",
             "",
             "Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; "
             "*folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* "
             "is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting "
             "the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown "
             "rates count hands that saw the flop.", ""]
    lines += _table("Preflop", PREFLOP, order, bots, field)
    lines += _table("After the flop, and heads-up", POSTFLOP, order, bots, field)
    lines += _table("VPIP by stack and by players dealt", DEPTH, order, bots, field,
                    "Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack "
                    "depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own "
                    "chips at the start of the hand.")
    lines += _table("Calls a shove, by own stack", SHOVE_CALLS, order, bots, field)
    lines += ["### Bet sizes", "",
              "Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big "
              "blinds; bets are after the flop with nothing to call, as a share of the pot.", "",
              "| Bot | Usual open | Opens at it | Usual bet | Bets at it |", "| :- | -: | -: | -: | -: |"]
    for name in order:
        b = bots[name]
        (o, os_), (bt, bs) = pf.usual(b["open_bb"]), pf.usual(b["bet_pot"])
        lines.append(f"| {name} | {o + ' bb' if o else '—'} | {_pct(os_)} | "
                     f"{f'{float(bt):.0%} pot' if bt else '—'} | {_pct(bs)} |")
    lines += ["", "### Biggest leaks per bot", "",
              "A leak is a spot where the bot's result as the player facing the action falls below the rest of the "
              "field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). "
              "The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't "
              "points, but the bots that leak chips to pressure bust first.", ""]
    for name in order:
        got = leaks(bots, name)
        if not got:
            lines.append(f"- **{name}**: no spot below the field.")
            continue
        parts = [f"{pf.SPOTS[s][0].lower()}: {c:+.1f} ± {1.96 * se:.1f} bb/100 ({why})"
                 + (" — within noise" if abs(c) < 1.96 * se else "") for s, c, se, why in got]
        lines.append(f"- **{name}**: " + "; ".join(parts) + ".")
    return lines + [""]


def board_md(bots: dict, order: list[str]) -> list[str]:
    lines = ["## Exploit board", "",
             "Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: "
             "how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). "
             "*Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often "
             "everyone folded at once. *Lost most facing it*: the leak measure above for that spot.", "",
             "| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |",
             "| :- | -: | :- | :- |"]
    for label, made, faced in pf.BOARD:
        folds = [(pf.rate(pf.spot(bots[n], faced), pf.F), pf.spot(bots[n], faced)[pf.N]) for n in order]
        pooled = [sum(x) for x in zip(*(pf.spot(bots[n], faced) for n in order))]
        spread = [x for x, k in folds if x is not None and k >= pf.MIN_SPOTS]
        fold_cell = _pct(pf.rate(pooled, pf.F)) + (f" ({min(spread):.0%}–{max(spread):.0%})" if len(spread) > 1 else "")
        gains = sorted(((pf.gain(bots[n], made), n) for n in order), key=lambda x: -x[0][0])
        won = ", ".join(f"{n} {g:+.1f}" + (f" (all fold {t:.0%})" if t is not None else "")
                        for (g, t, _), n in gains[:2])
        costs = sorted(((pf.cost(bots, n, faced), n) for n in order), key=lambda x: x[0][0] if x[0] else 0)
        lost = ", ".join(f"{n} {c[0]:+.1f}" for c, n in costs[:2] if c and c[0] < 0) or "—"
        lines.append(f"| {label} | {fold_cell} | {won} | {lost} |")
    return lines + [""]


def field_md(ev_dir: str) -> list[str]:
    """The rank view, the field profile and the exploit board; [] before any tournament has finished."""
    res = event_results(ev_dir)
    if not res["rows"]:
        return []
    lines = rank_md(res)
    profiles = [p for p in (pf.load(os.path.join(ev_dir, "results", f"T{k}")) for k in res["done"]) if p]
    if not profiles:
        return lines + ["## Field profile", "", "No hand logs or saved profiles for this event.", ""]
    bots = pf.merge(profiles)
    order = [r["team"] for r in res["rows"] if r["team"] in bots] + sorted(set(bots) - {r["team"] for r in res["rows"]})
    return lines + profile_md(bots, order, res["done"]) + board_md(bots, order)
