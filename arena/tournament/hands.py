"""Print a tournament's logged hands in plain text (the logs are zlib-compressed JSON).

    python -m arena.tournament.hands events/<id>/results/T<k> [--team NAME] [--table TASK]
                                     [--tables 3] [--hands 20] [--showdown]

With --team, only tables that team played; with --table, one table by task
number. Every seat's hole cards are shown: this is the referee's log, not a
bot's view. A * after a name marks a filler copy, which scores nothing.
"""

from __future__ import annotations

import argparse
import sys

from .handlog import read_index, read_meta, read_table

WORDS = {"f": "folds", "k": "checks", "c": "calls", "d": "discards"}
SUBS = {"T": "timeout", "E": "error", "I": "illegal action", "H": "hang", "F": "frozen seat"}


def _board_by_street(variant: dict, board: str) -> list[str]:
    """The board cards dealt on each street, as text."""
    out, i = [], 0
    for st in variant["streets"]:
        n = st.get("board", 0) * 2
        out.append(" ".join(board[j:j + 2] for j in range(i, min(i + n, len(board)), 2)))
        i += n
    return out


def format_hand(h: list, names: list[str], variant: dict, label: str) -> list[str]:
    hand, button, (sb, bb, ante), dealt, start, holes, board, decisions, pay, shown = h
    streets = variant["streets"]
    cards = _board_by_street(variant, board)
    blinds = f"{sb}/{bb}" + (f" ante {ante}" if ante else "")
    lines = [f"{label} hand {hand} · blinds {blinds} · button {names[button]}",
             "  " + ", ".join(f"{names[s]} {c} [{hc}]" for s, c, hc in zip(dealt, start, holes))]
    street, acts = None, []
    for d in decisions:
        st, seat, a, amt, to_call, pot, sub = d[1], d[2], d[3], d[4], d[5], d[6], d[11]
        if st != street:
            if acts:
                lines.append("    " + " · ".join(acts))
            street, acts = st, []
            name = streets[st]["name"] if st < len(streets) else f"street {st}"
            lines.append(f"  {name}" + (f" [{cards[st]}]" if st < len(cards) and cards[st] else "") + f", pot {pot}:")
        if a == "r":
            what = f"{'raises to' if to_call or st == 0 else 'bets'} {amt}"
        elif a == "c":
            what = f"calls {amt}"
        else:
            what = WORDS.get(a, a) + (f" {amt}" if a == "d" else "")
        acts.append(f"{names[seat]} {what}" + (f" ({SUBS.get(sub, sub)})" if sub else ""))
    if acts:
        lines.append("    " + " · ".join(acts))
    result = ", ".join(f"{names[s]} {p:+d}" for s, p in zip(dealt, pay) if p)
    lines.append(f"  result: {result}" + (f" · showdown: {', '.join(names[s] for s in shown)}" if shown else ""))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m arena.tournament.hands", description=__doc__.splitlines()[0])
    ap.add_argument("results_dir", help="events/<id>/results/T<k>")
    ap.add_argument("--team", help="only tables this team played")
    ap.add_argument("--table", type=int, help="one table, by task number")
    ap.add_argument("--tables", type=int, default=3, help="how many tables (default 3)")
    ap.add_argument("--hands", type=int, default=20, help="hands per table (default 20)")
    ap.add_argument("--showdown", action="store_true", help="only hands that went to showdown")
    a = ap.parse_args(argv)
    meta = read_meta(a.results_dir)
    entries, variant = meta["entries"], meta["variant"]
    want = entries.index(a.team) if a.team in entries else None
    if a.team and want is None:
        print(f"no team {a.team!r} here; entries: {', '.join(entries)}", file=sys.stderr)
        return 2
    shown_tables = 0
    for m in read_index(a.results_dir):
        if a.table is not None and m["task"] != a.table:
            continue
        if want is not None and want not in [e for e, f in zip(m["entries"], m["fillers"]) if not f]:
            continue
        names = [entries[e] + ("*" if f else "") for e, f in zip(m["entries"], m["fillers"])]
        print(f"=== table {m['task']} (iteration {m['iteration']}): {m['hands']} hands; seats "
              + ", ".join(f"{s}={n}" for s, n in enumerate(names)))
        printed = 0
        for h in read_table(a.results_dir, m):
            if a.showdown and not h[9]:
                continue
            print("\n".join(format_hand(h, names, variant, f"table {m['task']}")))
            printed += 1
            if printed >= a.hands:
                break
        shown_tables += 1
        if shown_tables >= a.tables:
            break
    if not shown_tables:
        print("no matching tables", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
