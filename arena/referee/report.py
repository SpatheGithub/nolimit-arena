"""REPORT.md for an event, and the feedback teams get between tournaments."""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict

from ..tournament.handlog import bot_view
from ..variants.library import ONE_LINERS
from .prompts import points_text


def _ci(row: dict) -> str:
    return f"{row['mean']:.2f} ± {1.96 * row['se']:.2f}"


def leaderboard_md(summary: dict, teams: dict | None = None) -> list[str]:
    rows = sorted(summary["entries"], key=lambda r: r["rank"])
    out = ["| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |",
           "| -: | :- | :- | -: | -: | -: | -: | -: |"]
    for i, r in enumerate(rows):
        noise = ""
        if i + 1 < len(rows) and r["lo"] <= rows[i + 1]["hi"]:
            noise = " ≈"  # within noise of the next rank
        subs = r["timeouts"] + r["errors"] + r["illegal"] + r["hangs"]
        out.append(f"| {r['rank']}{noise} | {r['name']} | {_ci(r)} | {r['tables']} | {r['vpip']:.0%} | "
                   f"{r['pfr']:.0%} | {subs} | {r['cpu_p99_us']:.0f} |")
    out.append("")
    out.append("≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.")
    return out


def _group_stats(values: list[float]) -> str:
    n = len(values)
    if not n:
        return "n=0"
    m = sum(values) / n
    se = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1) / n) if n > 1 else 0.0
    return f"{m:.1f} ± {1.96 * se:.1f} (n={n})"


def write_report(ev) -> str:
    card, T = ev.card, ev.card["tournaments"]
    teams = {t.team: t for t in ev.teams}
    summaries = {k: ev.summary(k) for k in range(1, T + 1)}
    weighted = ev.weighted(T)
    lines = [f"# Report: {ev.id}", "",
             "## Event card", "",
             f"- **Variant:** {card['variant']['name']}: {ONE_LINERS.get(card['variant']['name'], '')}",
             f"- **Points table ({card.get('points_name', 'custom')}):** {points_text(card['points'])}",
             f"- **Blinds ({card.get('blinds_name', 'custom')}):** "
             + ", ".join(f"{sb}/{bb}" + (f"+{a}" if a else "") for sb, bb, a in card["blinds"])
             + f", every {card['level_hands']} hands; cap {card['hand_cap']} hands",
             f"- **Schedule:** build {card['build_minutes']:g} min, {T} tournament(s) of {card['iterations']} "
             f"iterations, patch windows {card['patch_minutes']:g} min; time scale {ev.scale:g}"
             + ("; mock builders" if ev.mock else ""),
             f"- **Field:** {len(ev.teams)} builders; seed {card['seed']}", ""]
    lines += ["## Final weighted leaderboard", "",
              "| Rank | Team | Model | Archetype | Weighted score | " + " | ".join(f"T{k}" for k in range(1, T + 1)) + " |",
              "| -: | :- | :- | :- | -: |" + " -: |" * T]
    per_t = {k: {r["name"]: r for r in (summaries[k] or {"entries": []})["entries"]} for k in range(1, T + 1)}
    for rank, team in enumerate(sorted(weighted, key=lambda x: -weighted[x]), 1):
        t = teams[team]
        cells = [f"{per_t[k][team]['mean']:.1f}" if team in per_t[k] else "no bot" for k in range(1, T + 1)]
        lines.append(f"| {rank} | {team} | {t.model} | {t.archetype or 'free choice'} | {weighted[team]:.1f} | "
                     + " | ".join(cells) + " |")
    lines.append("")
    for k in range(1, T + 1):
        s = summaries[k]
        lines += [f"## T{k} (weight {k})", ""]
        if not s or not s["entries"]:
            lines += ["Not played (fewer than two valid bots).", ""]
            continue
        m = s["meta"]
        lines += [f"{m['tables']:,} tables, {m['hands']:,} hands, {m['elapsed_s']:.0f} s on {m['workers']} workers; "
                  f"{m['capped_tables']} tables reached the hand cap.", ""]
        lines += leaderboard_md(s) + [""]
        if m.get("events"):
            lines += ["Runner events: " + "; ".join(f"{e['kind']} {e.get('entry', '')}" for e in m["events"]), ""]
    lines += ["## By archetype and by model", "",
              "Weighted score, mean ± 95% interval across teams. Small groups say little.", ""]
    by_arch, by_model = defaultdict(list), defaultdict(list)
    for team, score in weighted.items():
        by_arch[teams[team].archetype or "free choice"].append(score)
        by_model[teams[team].model].append(score)
    lines += ["| Archetype | Score |", "| :- | -: |"] + [f"| {a} | {_group_stats(v)} |" for a, v in sorted(by_arch.items())]
    lines += ["", "| Model | Score |", "| :- | -: |"] + [f"| {a} | {_group_stats(v)} |" for a, v in sorted(by_model.items())]
    lines += ["", "## Substitutions", "", "| Team | " + " | ".join(f"T{k} timeout/error/illegal/hang" for k in range(1, T + 1)) + " |",
              "| :- |" + " :- |" * T]
    for team in sorted(teams):
        cells = []
        for k in range(1, T + 1):
            r = per_t[k].get(team)
            cells.append(f"{r['timeouts']}/{r['errors']}/{r['illegal']}/{r['hangs']}" if r else "—")
        lines.append(f"| {team} | " + " | ".join(cells) + " |")
    build = next((w for w in ev.state["windows"] if w["kind"] == "build"), None)
    lines += ["", "## Submission timeline", ""]
    if build:
        marks = [5, 10, 20, 40, 60]
        marks = [m for m in marks if m <= card["build_minutes"]] or [card["build_minutes"]]
        lines += ["Teams with an accepted bot by build minute (scaled by the time scale):", "",
                  "| Minute | Teams with an accepted bot |", "| -: | -: |"]
        for mnt in marks:
            t_cut = build["start"] + mnt * 60 * ev.scale
            n = sum(1 for t in ev.teams if any(r["observed"] <= t_cut for r in ev.submissions(t.team)))
            lines.append(f"| {mnt} | {n} of {len(ev.teams)} |")
        lines += [""]
    if not ev.mock:
        lines += ["## Builder runs", "",
                  "A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn "
                  "with time left. \"Stopped by\" is how the last window ended.", "",
                  "| Team | Runs | Clock-check resumes | Stopped by | Cost |", "| :- | -: | -: | :- | -: |"]
        for t in ev.teams:
            b = ev.state["builders"].get(t.team, {})
            lines.append(f"| {t.team} | {b.get('launches', 0)} | {sum((b.get('nudges') or {}).values())} "
                         f"| {b.get('stopped_by', 'unknown')} | ${b.get('cost_usd', 0.0):.2f} |")
        lines += [""]
    lines += ["## Builder failures", ""]
    fails = []
    for t in ev.teams:
        b = ev.state["builders"].get(t.team, {})
        missing = [k for k in range(1, T + 1) if not ev.state["frozen"].get(str(k), {}).get(t.team, {}).get("sid")]
        if b.get("errors") or missing or (b.get("exit") not in (0, None, -2)):
            fails.append(f"- {t.team}: exit {b.get('exit')}, errors {b.get('errors') or 'none'}"
                         + (f", no valid bot in T{', T'.join(map(str, missing))}" if missing else "")
                         + (f" (mock behavior: {b['behavior']})" if b.get("behavior") else ""))
    lines += fails or ["None."]
    if ev.state.get("paused"):
        lines += ["", f"The event was paused once: {ev.state['paused']}."]
    costs = {t.team: ev.state["builders"].get(t.team, {}).get("cost_usd", 0.0) for t in ev.teams}
    lines += ["", "## Cost", "", f"Total ${sum(costs.values()):.2f}; per builder: "
              + ", ".join(f"{k} ${v:.2f}" for k, v in sorted(costs.items())), ""]
    if ev.cfg["auth"]["mode"] == "subscription" and not ev.mock:
        lines += ["These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.", ""]
    meters = [u for u in (ev.state["builders"].get(t.team, {}).get("usage") for t in ev.teams) if u and u[0] is not None]
    if meters:
        lines += [f"Plan usage meter (five-hour window): {min(u[0] for u in meters):.0%} at the first reading, "
                  f"{max(u[1] for u in meters):.0%} at the last. It counts everything on the same login, "
                  "including your own sessions.", ""]
    os.makedirs(ev.p("report"), exist_ok=True)
    text = "\n".join(lines)
    with open(ev.p("report", "REPORT.md"), "w") as f:
        f.write(text)
    return text


def write_feedback(ev, team, k: int, summary: dict) -> str:
    """Write results/T<k>/ into the team's workspace; return the file list for PATCH_PROMPT."""
    mode = ev.cfg["schedule"].get("feedback", "own_stats_and_sample_hands")
    d = os.path.join(team.workspace, "results", f"T{k}")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "leaderboard.md"), "w") as f:
        f.write(f"# T{k} leaderboard\n\n" + "\n".join(leaderboard_md(summary)) + "\n")
    files = ["leaderboard.md"]
    row = next((r for r in summary["entries"] if r["name"] == team.team), None)
    if row and mode in ("own_stats", "own_stats_and_sample_hands"):
        with open(os.path.join(d, "own_stats.json"), "w") as f:
            json.dump({k2: v for k2, v in row.items() if k2 not in ("path", "hash")}, f, indent=1)
        files.append("own_stats.json")
    if row and mode == "own_stats_and_sample_hands":
        names = [e["name"] for e in summary["entries"]]
        idx = names.index(team.team) if team.team in names else None
        log_dir = ev.p("results", f"T{k}")
        if idx is not None and os.path.exists(os.path.join(log_dir, "hands.index.jsonl")):
            meta_entries = json.load(open(os.path.join(log_dir, "hands.meta.json")))["entries"]
            idx = meta_entries.index(team.team)
            sample = []
            for view in bot_view(log_dir, idx):
                sample.extend(view["hands"][:10])
                if len(sample) >= 40:
                    break
            with open(os.path.join(d, "sample_hands.json"), "w") as f:
                json.dump({"about": "your seat's hands; other seats anonymous, their cards only if shown; "
                                    "decisions are [hand, street, seat, action, amount, to_call, pot, "
                                    "eff_stack_bb*10, in_hand, alive, cpu_us, substitution]",
                           "hands": sample[:40]}, f)
            files.append("sample_hands.json")
    return ", ".join(files)
