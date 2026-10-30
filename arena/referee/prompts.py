"""Rendering docs/BUILDER_BRIEF.md and docs/PATCH_PROMPT.md for one team."""

from __future__ import annotations

import os
import re

from ..tournament.wsstate import fmt_duration
from ..variants.library import ONE_LINERS
from .config import REPO, load_archetypes

DOCS = os.path.join(REPO, "docs")
_COMMENT = re.compile(r"<!--.*?-->\s*", re.S)


def render(template: str, values: dict) -> str:
    text = _COMMENT.sub("", template, count=1)
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    missing = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", text)))
    if missing:
        raise ValueError(f"unrendered placeholders: {', '.join(missing)}")
    return text


def _read(name: str) -> str:
    with open(os.path.join(DOCS, name)) as f:
        return f.read()


def points_text(points) -> str:
    return ", ".join(f"{k + 1}{'st' if k == 0 else 'nd' if k == 1 else 'rd' if k == 2 else 'th'} {p:g}"
                     for k, p in enumerate(points))


def tournament_plan(card: dict) -> str:
    t = card["tournaments"]
    if t == 1:
        return "One scored tournament starts when the build phase ends; there are no patch rounds."
    return (f"{t} scored tournaments follow the build phase, weighted 1 to {t}; between them you get "
            f"{card['patch_minutes']:g}-minute patch windows to improve your bot, with your results.")


def render_brief(card: dict, team: str, n_teams: int, deadline_human: str, archetype: str | None) -> str:
    block = ""
    if archetype:
        a = next(x for x in load_archetypes() if x["id"] == archetype)
        block = (f"## A starting idea\n\nHere is an idea to start from: **{a['name']}**: {a['description']}\n\n"
                 "It's a suggestion, not a limit. Your goal is still the highest score: combine it with anything "
                 "else that wins, and drop any part of it that your tests show costs points.\n")
    sb, bb, _ = card["blinds"][0]
    return render(_read("BUILDER_BRIEF.md"), {
        "TEAM_ID": team, "N_TEAMS": n_teams, "N_OTHERS": n_teams - 1, "BUILD_MINUTES": f"{card['build_minutes']:g}",
        "DEADLINE_HUMAN": deadline_human, "TOURNAMENT_PLAN": tournament_plan(card),
        "VARIANT_NAME": card["variant"]["name"], "VARIANT_ONE_LINER": ONE_LINERS.get(card["variant"]["name"], ""),
        "SEATS": card["seats"], "STARTING_STACK": f"{card['starting_stack']:,}", "SB": sb, "BB": bb,
        "LEVEL_HANDS": card["level_hands"], "HAND_CAP": card["hand_cap"], "POINTS_TABLE": points_text(card["points"]),
        "ITERATIONS": card["iterations"], "DECISION_LIMIT_MS": f"{card['decision_limit_ms']:g}",
        "INIT_LIMIT_S": f"{card['init_limit_s']:g}", "ALLOWED_PACKAGES": ", ".join(card["allowed_packages"]) or "nothing",
        "SIZE_LIMIT_MB": f"{card['bot_size_limit_mb']:g}", "COOLDOWN_SECONDS": f"{card['cooldown_seconds']:g}",
        "LOCALSIM_CAP": card["localsim_max_tables"], "ARCHETYPE_BLOCK": block,
    })


def render_nudge(left_s: float, deadline_human: str, last_sid: str | None) -> str:
    """The clock check the referee resumes a builder with when it ends its turn early."""
    status = (f"Your latest accepted submission is {last_sid}." if last_sid
              else "You have no accepted submission yet, so getting one accepted comes first.")
    return (f"Clock check: {fmt_duration(left_s)} left; this window closes at {deadline_human}. {status} "
            "Use the time: play your bot with kit/localsim.py against the house bots and your earlier versions in "
            ".submissions/, find where it loses points, "
            "improve that, run kit/check_bot.py, and resubmit only if the new version is better. "
            "Keep NOTES.md current.")


def render_patch(card: dict, k: int, patch_minutes: float, deadline_human: str, row: dict, rank: int, n_teams: int,
                 cum_score: float, cum_rank: int, feedback_files: str) -> str:
    t = card["tournaments"]
    places = row["places"]
    dist = ", ".join(f"{p + 1}{'st' if p == 0 else 'nd' if p == 1 else 'rd' if p == 2 else 'th'} {c:.0f}"
                     for p, c in enumerate(places) if c) + (f", survived to the cap {row['cap_survivals']}"
                                                           if row["cap_survivals"] else "")
    remaining = ", ".join(f"T{j} (weight {j})" for j in range(k + 1, t + 1))
    return render(_read("PATCH_PROMPT.md"), {
        "K": k, "K_NEXT": k + 1, "PATCH_MINUTES": f"{patch_minutes:g}", "DEADLINE_HUMAN": deadline_human,
        "RANK": rank, "N_TEAMS": n_teams, "AVG": f"{row['mean']:.2f}", "CI95": f"{row['lo']:.2f} to {row['hi']:.2f}",
        "PLACE_DISTRIBUTION": dist or "none", "TIMEOUTS": row["timeouts"], "ERRORS": row["errors"],
        "ILLEGAL": row["illegal"], "DECISIONS": row["decisions"], "CUM_SCORE": f"{cum_score:.2f}",
        "CUM_RANK": cum_rank, "REMAINING_PLAN": remaining, "FEEDBACK_FILES": feedback_files,
    })
