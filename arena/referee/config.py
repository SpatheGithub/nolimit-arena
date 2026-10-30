"""Event configuration (configs/event.yaml) and the secrets drawn from it.

``draw_event`` turns a config into an event card (variant, points table,
blind schedule, seed, limits) and a team list (model and archetype per
builder). Missing keys take the defaults in configs/event.example.yaml.
"""

from __future__ import annotations

import copy
import os
import random
import secrets
from dataclasses import dataclass

import yaml

from ..tournament.card import make_card
from ..variants.library import BLINDS, POINTS, VARIANTS

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULTS_PATH = os.path.join(REPO, "configs", "event.example.yaml")
ARCHETYPES_PATH = os.path.join(REPO, "configs", "archetypes.yaml")


@dataclass
class Team:
    team: str
    model: str
    archetype: str | None   # archetype id, or None for free choice
    workspace: str


REPLACED = {"models"}  # mappings that are values, not sections: a config's model mix replaces the default one


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        merge = isinstance(v, dict) and isinstance(out.get(k), dict) and k not in REPLACED
        out[k] = _merge(out[k], v) if merge else v
    return out


def load_config(path: str | None) -> dict:
    with open(DEFAULTS_PATH) as f:
        base = yaml.safe_load(f)
    if path is None:
        return base
    with open(path) as f:
        return _merge(base, yaml.safe_load(f) or {})


def load_archetypes() -> list[dict]:
    with open(ARCHETYPES_PATH) as f:
        return yaml.safe_load(f)


def _pick(rng: random.Random, value, library: dict, what: str):
    if value == "random":
        name = rng.choice(sorted(library))
        return name, library[name]
    if isinstance(value, str):
        if value not in library:
            raise ValueError(f"unknown {what} {value!r}; choose from {sorted(library)} or 'random'")
        return value, library[value]
    return "custom", value


def draw_event(cfg: dict, seed: int | None = None) -> tuple[dict, list[Team], list[str]]:
    """Returns (card, teams, notes)."""
    notes = []
    ev = cfg["event"]
    seed = seed if seed is not None else (ev.get("seed") if ev.get("seed") is not None else secrets.randbits(32))
    rng = random.Random(seed)
    pool = [v for v in cfg.get("variant_pool", sorted(VARIANTS)) if v in VARIANTS]
    skipped = [v for v in cfg.get("variant_pool", []) if v not in VARIANTS]
    if skipped:
        notes.append(f"variant pool entries not available yet: {', '.join(skipped)}")
    vname = cfg["variant"]
    if vname == "random":
        vname = rng.choice(pool)
    if vname not in VARIANTS:
        raise ValueError(f"unknown variant {vname!r}; choose from {sorted(VARIANTS)}")
    spec = VARIANTS[vname]
    t = cfg["table"]
    spec.validate(t["seats"])
    points_name, points = _pick(rng, t["points"], POINTS, "points table")
    blinds_name, blinds = _pick(rng, t["blinds"]["schedule"], BLINDS, "blind schedule")
    tour, sch, kit = cfg["tournament"], cfg["schedule"], cfg["kit"]
    card = make_card(
        event=ev["name"], spec=spec, points=points, blinds=blinds, level_hands=t["blinds"]["level_every_hands"],
        hand_cap=t["hand_cap"], seats=t["seats"], starting_stack=t["starting_stack"],
        decision_limit_ms=tour["decision_limit_ms"], iterations=tour["iterations"],
        tournaments=sch["tournaments"], timing=tour["timing"], hang_watchdog_ms=tour["hang_watchdog_ms"],
        init_limit_s=tour["init_limit_s"], import_limit_s=tour["import_limit_s"],
        bot_size_limit_mb=tour["bot_size_limit_mb"], allowed_packages=tour["allowed_packages"],
        cooldown_seconds=sch["submit_cooldown_seconds"], localsim_max_tables=kit["localsim_max_tables"],
        localsim_max_seconds=kit["localsim_max_seconds"], build_minutes=sch["build_minutes"],
        patch_minutes=sch["patch_minutes"],
    )
    card.update(seed=seed, points_name=points_name, blinds_name=blinds_name)
    teams = assign_teams(cfg, rng)
    return card, teams, notes


def assign_teams(cfg: dict, rng: random.Random) -> list[Team]:
    b = cfg["builders"]
    n = b["count"]
    models = []
    for alias, count in b["models"].items():
        models += [alias] * count
    if len(models) != n:
        raise ValueError(f"builders.models counts sum to {len(models)}, not builders.count {n}")
    rng.shuffle(models)
    archetypes: list[str | None] = [None] * n
    mode = b.get("archetypes", "none")
    if isinstance(mode, list):  # exactly these ids, to random builders; the rest choose freely
        unknown = sorted(set(mode) - {a["id"] for a in load_archetypes()})
        if unknown or len(mode) > n:
            raise ValueError(f"builders.archetypes: unknown ids {unknown}" if unknown
                             else f"builders.archetypes lists {len(mode)} ids for {n} builders")
        for slot, a in zip(rng.sample(range(n), len(mode)), mode):
            archetypes[slot] = a
    elif mode in ("assign_half", "assign_all"):
        ids = [a["id"] for a in load_archetypes()]
        k = n if mode == "assign_all" else n // 2
        chosen = rng.sample(range(n), k)
        order = ids * (k // len(ids) + 1)
        rng.shuffle(order)
        for i, slot in enumerate(chosen):
            archetypes[slot] = order[i]
    root = os.path.join(os.path.expanduser(cfg["paths"]["workspaces_root"]), cfg["event"]["name"])
    return [Team(f"b{i + 1:02d}", models[i], archetypes[i], os.path.join(root, f"b{i + 1:02d}")) for i in range(n)]
