"""Building a builder's workspace from the event card.

    <workspace>/
      EVENT.md              today's rules
      NOTES.md              the team's notes (collected by the referee)
      bot/                  the team's bot, starting as the template
      kit/                  RULES.md, agent_template.py, icm.py, localsim.py, check_bot.py,
                            submit.py, clock.py, event.json, house_bots/ (the quick-build
                            practice opponents only, see arena.house_bots.KIT_BOTS),
                            arena/ (the engine, runner and tournament code the referee runs)
      .brief/BRIEF.md       the builder's system-prompt brief (rendered by the referee)
      .clock.json           window deadlines (informational; the referee's copy rules)
      .submissions/         accepted snapshots and log.jsonl (written by kit/submit.py)

Workspaces live outside the arena repo, so builders never load its CLAUDE.md.
"""

from __future__ import annotations

import json
import os
import shutil

from ..house_bots import KIT_BOTS, ZOO
from ..tournament.card import save_card

ARENA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT_SRC = os.path.join(ARENA, "kit")
KIT_FILES = ("RULES.md", "agent_template.py", "icm.py", "localsim.py", "check_bot.py", "submit.py", "clock.py")
ARENA_PARTS = ("engine", "runner", "tournament", "variants")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "tests")

NOTES_STUB = """# Team notes

## Approach

## Key parameters

## Known weaknesses

## Next steps
"""


def copy_arena_subset(dst: str) -> None:
    """The arena package the kit scripts import, as kit/arena."""
    os.makedirs(dst, exist_ok=True)
    shutil.copy2(os.path.join(ARENA, "__init__.py"), dst)
    for part in ARENA_PARTS:
        shutil.copytree(os.path.join(ARENA, part), os.path.join(dst, part), ignore=IGNORE, dirs_exist_ok=True)
    os.makedirs(os.path.join(dst, "kit"), exist_ok=True)
    shutil.copy2(os.path.join(KIT_SRC, "icm.py"), os.path.join(dst, "kit", "icm.py"))


def copy_house_bots(dst: str) -> None:
    """The practice opponents: the zoo's kit bots, never the strong ones."""
    os.makedirs(dst, exist_ok=True)
    for name in KIT_BOTS:
        shutil.copytree(ZOO[name]["path"], os.path.join(dst, name), ignore=IGNORE, dirs_exist_ok=True)


def write_clock(ws: str, windows: list[dict]) -> None:
    """``windows``: [{"name", "start", "end", "then"}], times as epoch seconds."""
    tmp = os.path.join(ws, ".clock.json.tmp")
    with open(tmp, "w") as f:
        json.dump({"windows": windows}, f, indent=1)
    os.replace(tmp, os.path.join(ws, ".clock.json"))


def build_workspace(ws: str, card: dict | None, event_md: str, brief_md: str | None = None,
                    windows: list[dict] | None = None) -> None:
    """Create the workspace. With ``card=None`` (before the reveal) kit/event.json
    is left out; the referee writes it with EVENT.md when the build starts."""
    if os.path.exists(os.path.join(ws, "bot")):
        raise FileExistsError(f"{ws} already has a bot/")
    kit = os.path.join(ws, "kit")
    os.makedirs(kit, exist_ok=True)
    for name in KIT_FILES:
        shutil.copy2(os.path.join(KIT_SRC, name), kit)
    copy_arena_subset(os.path.join(kit, "arena"))
    copy_house_bots(os.path.join(kit, "house_bots"))
    if card is not None:
        save_card(card, os.path.join(kit, "event.json"))
    os.makedirs(os.path.join(ws, "bot"))
    shutil.copy2(os.path.join(KIT_SRC, "agent_template.py"), os.path.join(ws, "bot", "agent.py"))
    open(os.path.join(ws, "bot", "__init__.py"), "w").close()
    with open(os.path.join(ws, "EVENT.md"), "w") as f:
        f.write(event_md)
    with open(os.path.join(ws, "NOTES.md"), "w") as f:
        f.write(NOTES_STUB)
    if brief_md is not None:
        os.makedirs(os.path.join(ws, ".brief"), exist_ok=True)
        with open(os.path.join(ws, ".brief", "BRIEF.md"), "w") as f:
            f.write(brief_md)
    os.makedirs(os.path.join(ws, ".submissions"), exist_ok=True)
    write_clock(ws, windows or [])
