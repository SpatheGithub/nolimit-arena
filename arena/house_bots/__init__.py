"""The house bot zoo: reference opponents for localsim and calibration bots
for the report's leak metrics (docs/FIELD_STUDY.md).

ZOO maps each bot's name to its package directory, its group ("quick-build"
patterns that mimic quickly built bots, or strong "baseline"s), a one-line
summary and whether builders' kits carry it. Every bot is a self-contained
package (agent.py with class Agent) that imports only the standard library,
numpy and itself, never arena.*, so it can be copied into builders'
workspaces. Helpers shared by several bots live in _common.py and
_common.json here; the strategy only the strong bots use is in _strategy.py
and _strategy.json. Each package carries identical copies of the ones it
uses: ``python -m arena.house_bots.sync``.

Builders' kits (KIT_BOTS) get the quick-build patterns except chip_pushfold,
whose push/fold charts are as much of a head start as the baselines' play.
Builders then write their bots from scratch, as teams at the real event do,
instead of tuning the arena's own baselines.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _entry(name: str, group: str, summary: str, kit: bool = True) -> tuple[str, dict]:
    return name, {"path": os.path.join(HERE, name), "group": group, "summary": summary, "kit": kit}


ZOO: dict[str, dict] = dict([
    _entry("checkfold", "quick-build", "Checks when free, folds otherwise: the template bot."),
    _entry("random", "quick-build", "Uniformly random legal actions with uniformly random raise sizes."),
    _entry("threshold", "quick-build",
           "Static Chen-score and made-hand-category thresholds; min-raises strong, calls medium."),
    _entry("pot_odds", "quick-build", "Calling station: calls when crude equity beats pot odds, never bluffs."),
    _entry("montecarlo", "quick-build",
           "Monte Carlo equity vs random hands on a ~0.7 ms wall-clock budget; raises when equity is high."),
    _entry("minraiser", "quick-build", "Min-raises any decent hand on every street, calls small bets."),
    _entry("maniac", "quick-build", "Shoves or raises big with any pair, ace or two broadways; bluffs often."),
    _entry("nit", "quick-build", "Top ~8% of hands only; folds to any raise without QQ+ or AK."),
    _entry("chip_pushfold", "quick-build",
           "Chip-EV Nash-like push/fold under 15 BB, ignoring ICM; limps or folds deeper.", kit=False),
    _entry("icm_pushfold", "baseline",
           "ICM push/fold under 15 BB from the points table, stacks and hands left; solid TAG deeper.",
           kit=False),
    _entry("tag", "baseline",
           "Tight-aggressive with stack-depth modes: positional opens, 3-bets, c-bets, push/fold when short.",
           kit=False),
])

KIT_BOTS = tuple(name for name, info in ZOO.items() if info["kit"])
