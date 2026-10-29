"""The event card: everything about today's event a workspace or referee needs.

Workspaces get it as kit/event.json; the referee keeps the authoritative copy.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from ..engine.spec import VariantSpec
from .play import Settings


def make_card(*, event: str, spec: VariantSpec, points: Sequence[float], blinds: Sequence[Sequence[int]],
              team: str = "", level_hands: int = 25, hand_cap: int = 200, seats: int = 8,
              starting_stack: int = 2000, decision_limit_ms: float = 1.0, iterations: int = 400,
              tournaments: int = 6, timing: str = "thread_cpu", hang_watchdog_ms: float = 50,
              init_limit_s: float = 2, import_limit_s: float = 30, bot_size_limit_mb: float = 100,
              allowed_packages: Sequence[str] = ("numpy",), cooldown_seconds: float = 120,
              localsim_max_tables: int = 200, localsim_max_seconds: float = 60,
              build_minutes: float = 20, patch_minutes: float = 7) -> dict:
    return {
        "event": event, "team": team, "variant": spec.to_dict(), "points": list(points),
        "blinds": [list(b) + [0] * (3 - len(b)) for b in blinds], "level_hands": level_hands,
        "hand_cap": hand_cap, "seats": seats, "starting_stack": starting_stack,
        "decision_limit_ms": decision_limit_ms, "iterations": iterations, "tournaments": tournaments,
        "timing": timing, "hang_watchdog_ms": hang_watchdog_ms, "init_limit_s": init_limit_s,
        "import_limit_s": import_limit_s, "bot_size_limit_mb": bot_size_limit_mb,
        "allowed_packages": list(allowed_packages), "cooldown_seconds": cooldown_seconds,
        "localsim_max_tables": localsim_max_tables, "localsim_max_seconds": localsim_max_seconds,
        "build_minutes": build_minutes, "patch_minutes": patch_minutes,
    }


def card_spec(card: dict) -> VariantSpec:
    return VariantSpec.from_dict(card["variant"])


def settings_from_card(card: dict, **overrides) -> Settings:
    base = dict(
        spec=card_spec(card), points=tuple(card["points"]),
        blinds=tuple(tuple(b) for b in card["blinds"]), level_hands=card["level_hands"],
        hand_cap=card["hand_cap"], seats=card["seats"], starting_stack=card["starting_stack"],
        decision_limit_ms=card["decision_limit_ms"], timing=card["timing"],
        hang_watchdog_ms=card["hang_watchdog_ms"], init_limit_s=card["init_limit_s"],
        import_limit_s=card["import_limit_s"], bot_size_limit_mb=card["bot_size_limit_mb"],
    )
    base.update(overrides)
    return Settings(**base)


def load_card(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def save_card(card: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(card, f, indent=1)
