"""Playing one tournament table inside a worker process.

The table's result depends only on the task (seed, seating, frozen seats),
the settings and the bots' code; CPU-time substitutions are the one source of
nondeterminism, and each is recorded in the hand log.

Per-decision log record (FIELD_STUDY features):
    [hand, street, seat, action, amount, to_call, pot, eff_bb10, in_hand, alive,
     cpu_us, sub]
action is the one applied (f k c r d), amount its chips (raise-to for r),
eff_bb10 the effective stack in tenths of a big blind, in_hand the players
not folded, alive the players dealt in, and sub "" or the substitution: T
timeout, E error, I illegal, H hang, F frozen (seat disabled for the table).
"""

from __future__ import annotations

import bisect
import hashlib
import json
import random
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field

from ..engine.cards import CARD_STR
from ..engine.hand import IllegalAction
from ..engine.spec import VariantSpec
from ..engine.table import Table
from ..runner.guard import Capture
from ..runner.obs import BadAction, build_obs, hand_end_event, parse_action, table_config
from ..runner.seat import BotRunner
from .scoring import table_points

# Decision CPU-time histogram bucket upper edges, µs; the last bucket is open.
HIST_EDGES_US = (10, 25, 50, 100, 200, 300, 500, 750, 1000, 1500, 3000, 10000)
ACTION_CODE = {"fold": "f", "check": "k", "call": "c", "raise": "r", "discard": "d"}
STAT_KEYS = ("hands", "vpip", "pfr", "post_aggr", "post_calls", "showdowns", "showdown_wins",
             "decisions", "timeouts", "slow_core_passes", "errors", "illegal", "hangs", "frozen", "init_failures",
             "import_failures", "observe_errors", "cpu_ns_sum", "cpu_ns_max", "wall_ns_max")


def derive(*parts: object) -> int:
    """A stable 63-bit seed from ``parts`` (same in every process and run)."""
    return int.from_bytes(hashlib.blake2b(repr(parts).encode(), digest_size=8).digest(), "big") >> 1


@dataclass
class Settings:
    spec: VariantSpec
    points: tuple[float, ...] = (100, 60, 40, 25, 15, 10, 5, 0)
    blinds: tuple[tuple[int, int, int], ...] = tuple((10 * 2**k, 20 * 2**k, 0) for k in range(8))
    level_hands: int = 25
    hand_cap: int = 200
    seats: int = 8
    starting_stack: int = 2000
    decision_limit_ms: float = 1.0
    timing: str = "thread_cpu"
    hang_watchdog_ms: float = 50.0
    init_limit_s: float = 2.0
    import_limit_s: float = 30.0
    native_kill_s: float = 10.0
    bot_size_limit_mb: float = 100.0
    memory_mb: int | None = 2048        # per worker, where the OS enforces it (Linux)
    hand_logs: bool = True
    rules: str = ""


@dataclass
class TableTask:
    task_id: int
    iteration: int
    index: int
    seed: int
    entries: list[int]                   # entry index per seat
    fillers: list[bool]                  # filler copies score nothing
    frozen: tuple[int, ...] = ()         # seats forced to fold/check all table
    notes: list[str] = field(default_factory=list)


def play_table(task: TableTask, st: Settings, runner: BotRunner,
               agent_class: Callable[[int], type | None]) -> dict:
    n = st.seats
    runner.refresh_baseline()
    rng = random.Random(task.seed)
    table = Table(st.spec, n_seats=n, starting_stack=st.starting_stack, blinds=st.blinds,
                  level_hands=st.level_hands, hand_cap=st.hand_cap, rng=rng)
    stats = [dict.fromkeys(STAT_KEYS, 0) for _ in range(n)]
    hist = [[0] * (len(HIST_EDGES_US) + 1) for _ in range(n)]
    caps = [Capture(keep=5) for _ in range(n)]
    agents: list[object | None] = [None] * n
    frozen = set(task.frozen)
    limit_ns = int(st.decision_limit_ms * 1e6)
    hang_s = st.hang_watchdog_ms / 1000
    for seat in range(n):
        if seat in frozen:
            continue
        cls = agent_class(task.entries[seat])
        if cls is None:
            stats[seat]["import_failures"] += 1
            frozen.add(seat)
            continue
        cfg = table_config(st.spec, seat=seat, seed=derive(task.seed, "seat", seat), points=st.points,
                           blinds=st.blinds, level_hands=st.level_hands, hand_cap=st.hand_cap,
                           seats=n, starting_stack=st.starting_stack,
                           decision_limit_ms=st.decision_limit_ms, rules=st.rules)
        agent, failure, _, _ = runner.call(cls, cfg, st.init_limit_s, caps[seat], seat,
                                           hard_limit_s=st.init_limit_s + 10)
        if failure:
            stats[seat]["init_failures"] += 1
            frozen.add(seat)
        else:
            agents[seat] = agent
    log_hands = [] if st.hand_logs else None

    while not table.over():
        hand = table.start_hand()
        seats = table.seats
        sb, bb, ante = table.level()
        start_stacks = list(hand.start_stacks)
        vpip, pfr = set(), set()
        decisions = []
        while hand.to_act is not None:
            p = hand.to_act
            seat = seats[p]
            s = stats[seat]
            s["decisions"] += 1
            legal = hand.legal()
            to_call, pot = legal.call, sum(hand.total)
            me = hand.bet[p] + hand.stack[p]
            others = max((hand.bet[j] + hand.stack[j] for j in range(hand.n)
                          if j != p and not hand.folded[j]), default=0)
            eff10 = min(me, others) * 10 // max(bb, 1)
            in_hand = hand.folded.count(False)
            mark = len(hand.history)
            sub, cpu = "", 0
            agent = agents[seat]
            if agent is None:
                sub = "F"
                s["frozen"] += 1
            else:
                obs = build_obs(table, hand, legal)
                ret, failure, cpu, wall = runner.call(agent.act, obs, hang_s, caps[seat], seat)
                s["cpu_ns_sum"] += cpu
                if cpu > s["cpu_ns_max"]:
                    s["cpu_ns_max"] = cpu
                if wall > s["wall_ns_max"]:
                    s["wall_ns_max"] = wall
                hist[seat][bisect.bisect_left(HIST_EDGES_US, cpu / 1000)] += 1
                if failure == "hang":
                    sub = "H"
                    s["hangs"] += 1
                elif failure:
                    sub = "E"
                    s["errors"] += 1
                elif cpu > limit_ns and runner.core_adjusted(cpu) > limit_ns:
                    sub = "T"
                    s["timeouts"] += 1
                else:
                    if cpu > limit_ns:
                        s["slow_core_passes"] += 1
                    try:
                        name, amount, cards = parse_action(ret)
                        hand.act(name, amount, cards)
                    except (BadAction, IllegalAction):
                        sub = "I"
                        s["illegal"] += 1
            if sub:
                hand.act_default()
            street, _, act, amount = hand.history[mark]
            if street == 0 and act in ("call", "raise"):
                vpip.add(seat)
                if act == "raise":
                    pfr.add(seat)
            elif street > 0:
                if act == "raise":
                    s["post_aggr"] += 1
                elif act == "call":
                    s["post_calls"] += 1
            if log_hands is not None:
                decisions.append([table.hands_played + 1, street, seat, ACTION_CODE.get(act, act[:1]), amount,
                                  to_call, pot, eff10, in_hand, len(seats), cpu // 1000, sub])
        res = hand.result
        for seat in seats:
            stats[seat]["hands"] += 1
        for seat in vpip:
            stats[seat]["vpip"] += 1
        for seat in pfr:
            stats[seat]["pfr"] += 1
        if res.showdown:
            winners = {seats[i] for pot_ in res.pots for i in pot_.winners}
            for i in res.shown:
                stats[seats[i]]["showdowns"] += 1
                if seats[i] in winners:
                    stats[seats[i]]["showdown_wins"] += 1
        dealt = list(seats)
        if log_hands is not None:
            log_hands.append([
                table.hands_played + 1, seats[hand.button], [sb, bb, ante], dealt, start_stacks,
                ["".join(CARD_STR[c] for c in hand.hole[i]) for i in range(hand.n)],
                "".join(CARD_STR[c] for c in hand.board), decisions, res.payoffs,
                [seats[i] for i in res.shown],
            ])
        out = table.finish_hand()
        event = None
        for seat in dealt:
            agent = agents[seat]
            if agent is None:
                continue
            observe = getattr(agent, "observe", None)
            if observe is None:
                continue
            if event is None:
                event = hand_end_event(table, hand, out)
            _, failure, _, _ = runner.call(observe, event, hang_s, caps[seat], seat)
            if failure:
                stats[seat]["observe_errors"] += 1

    survivors = table.survivors()
    points = table_points(table.places, survivors, table.stacks, st.points)
    log = None
    if log_hands is not None:
        log = zlib.compress(json.dumps(log_hands, separators=(",", ":")).encode(), 6)
    return {
        "task_id": task.task_id, "iteration": task.iteration, "index": task.index,
        "entries": task.entries, "fillers": task.fillers, "frozen": sorted(frozen),
        "hands": table.hands_played, "capped": len(survivors) > 1,
        "places": {s: list(span) for s, span in table.places.items()}, "survivors": survivors,
        "stacks": list(table.stacks), "points": points, "stats": stats, "hist": hist,
        "output": {s: c.lines + ([f"... {c.dropped} more lines"] if c.dropped else [])
                   for s, c in enumerate(caps) if c.lines},
        "log": log,
    }
