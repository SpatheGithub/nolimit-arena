"""House bot zoo: clean play in every variant, act() CPU time, import and
init time, self-contained packages and the shared helper copies."""

from __future__ import annotations

import ast
import gc
import importlib
import importlib.util
import os
import sys
import time
import uuid
from collections import Counter, defaultdict

import pytest

from arena.engine.spec import NLHE
from arena.engine.xval import FLHE, PLO, ROYAL, SHORTDECK
from arena.house_bots import ZOO, sync
from arena.runner.local import play_local_table
from arena.runner.obs import table_config
from tests.test_hand_rules import PINEAPPLE

NAMES = list(ZOO)
POINTS = (100, 60, 40, 25, 15, 10, 5, 0)
ANTES = ((10, 20, 0), (15, 30, 0), (25, 50, 0), (50, 100, 0), (75, 150, 15), (100, 200, 20),
         (150, 300, 30), (200, 400, 40))
# name -> (spec, seats, blind schedule or None for the default, tables per bot)
RUNS = {
    "nlhe": (NLHE, 8, None, 30),
    "nlhe_antes": (NLHE, 8, ANTES, 5),
    "flhe": (FLHE, 8, None, 5),
    "plo": (PLO, 8, None, 5),
    "shortdeck": (SHORTDECK, 8, None, 5),
    "royal": (ROYAL, 7, None, 5),
    "pineapple": (PINEAPPLE, 8, None, 5),
}
UNTIMED = {"montecarlo"}


def load_agent(name: str) -> type:
    """Import a bot as a runner does: its directory as a package under a fresh name."""
    path = ZOO[name]["path"]
    mod = f"house_{name}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(mod, os.path.join(path, "__init__.py"),
                                                  submodule_search_locations=[path])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules[mod] = pkg
    spec.loader.exec_module(pkg)
    return importlib.import_module(f"{mod}.agent").Agent


def lineups(seats: int, per_bot: int):
    """Tables of consecutive zoo bots in rotation until every bot has ``per_bot`` seats."""
    seen = Counter()
    t = 0
    while min(seen[n] for n in NAMES) < per_bot:
        lineup = [NAMES[(t * seats + i) % len(NAMES)] for i in range(seats)]
        seen.update(lineup)
        t += 1
        yield lineup


class Recorder:
    """Plays tables with every agent wrapped to time act() and keep its instances."""

    def __init__(self, agents: dict[str, type]):
        self.agents = agents
        self.times: dict[str, list[int]] = defaultdict(list)
        self.instances: dict[str, list] = defaultdict(list)
        self.counts: dict[str, Counter] = defaultdict(Counter)
        self.tables: Counter = Counter()

    def wrap(self, name: str) -> type:
        cls, times, instances = self.agents[name], self.times[name], self.instances[name]

        class Timed:
            def __init__(self, config: dict):
                self.agent = cls(config)
                instances.append(self.agent)

            def act(self, obs: dict) -> dict:
                t0 = time.thread_time_ns()
                out = self.agent.act(obs)
                times.append(time.thread_time_ns() - t0)
                return out

            def observe(self, event: dict) -> None:
                fn = getattr(self.agent, "observe", None)
                if fn is not None:
                    fn(event)
        return Timed

    def play(self, spec, seats: int, blinds, per_bot: int, seed: int) -> None:
        extra = {"blinds": blinds} if blinds else {}
        for t, lineup in enumerate(lineups(seats, per_bot)):
            _, counts = play_local_table([self.wrap(n) for n in lineup], seed=seed + t, spec=spec, **extra)
            for n, c in zip(lineup, counts):
                self.counts[n].update(c)
                self.tables[n] += 1


@pytest.fixture(scope="module")
def agents() -> dict[str, type]:
    import numpy  # noqa: F401  (a tournament worker has it loaded before the bots)
    return {n: load_agent(n) for n in NAMES}


@pytest.fixture(scope="module")
def runs(agents) -> dict[str, Recorder]:
    gc.collect()
    out = {}
    for k, (name, (spec, seats, blinds, per_bot)) in enumerate(RUNS.items()):
        out[name] = rec = Recorder(agents)
        rec.play(spec, seats, blinds, per_bot, seed=1000 * (k + 1))
    return out


def test_registry():
    assert len(ZOO) == 11
    for name, info in ZOO.items():
        assert os.path.isabs(info["path"]) and os.path.basename(info["path"]) == name
        assert os.path.isfile(os.path.join(info["path"], "__init__.py"))
        assert os.path.isfile(os.path.join(info["path"], "agent.py"))
        assert info["group"] in ("quick-build", "baseline") and info["summary"]
    assert {n for n, i in ZOO.items() if i["group"] == "baseline"} == {"icm_pushfold", "tag"}


def test_bots_import_only_stdlib_numpy_and_themselves():
    allowed = set(sys.stdlib_module_names) | {"numpy"}
    for name, info in ZOO.items():
        for fn in sorted(os.listdir(info["path"])):
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(info["path"], fn)) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                assert set(roots) <= allowed, f"{name}/{fn} imports {roots}"


def test_common_copies_match_the_source():
    assert sorted(sync.users()) == sorted(i["path"] for i in ZOO.values())
    assert sync.stale() == []


@pytest.mark.parametrize("run", list(RUNS))
def test_every_bot_plays_cleanly(runs, run):
    rec = runs[run]
    per_bot = RUNS[run][3]
    for n in NAMES:
        c = rec.counts[n]
        assert rec.tables[n] >= per_bot and c["decisions"] > 0, (n, rec.tables[n])
        assert c["error"] == c["illegal"] == c["observe_error"] == 0, (n, dict(c))
        assert sum(a.failures for a in rec.instances[n]) == 0, n


def test_act_cpu_time(runs):
    rows = []
    slow = {}
    for n in NAMES:
        ts = sorted(t for rec in runs.values() for t in rec.times[n])
        p99, top = ts[int(0.99 * (len(ts) - 1))] / 1e6, ts[-1] / 1e6
        rows.append(f"{n:14s} {len(ts):6d} decisions  mean {sum(ts) / len(ts) / 1e6:.3f}  "
                    f"p99 {p99:.3f}  max {top:.3f} ms")
        assert len(ts) >= 1500, (n, len(ts))
        if n not in UNTIMED and p99 >= 1.0:
            slow[n] = p99
    print("\nact() thread CPU per bot\n" + "\n".join(rows))
    assert not slow, slow


def test_import_and_init_time():
    import numpy  # noqa: F401
    configs = [table_config(spec, seat=0, seed=s, points=POINTS, blinds=[(10, 20, 0)], level_hands=25,
                            hand_cap=200, seats=seats, starting_stack=2000, decision_limit_ms=1.0)
               for s, (spec, seats, _, _) in enumerate(RUNS.values())]
    rows = []
    for n in NAMES:
        t0 = time.perf_counter()
        cls = load_agent(n)
        imported = time.perf_counter() - t0
        init = 0.0
        for cfg in configs:
            t0 = time.perf_counter()
            cls(cfg)
            init = max(init, time.perf_counter() - t0)
        rows.append(f"{n:14s} import {imported * 1e3:6.1f} ms  init max {init * 1e3:5.2f} ms")
        assert imported < 2.0 and init < 0.05, (n, imported, init)
    print("\n" + "\n".join(rows))
