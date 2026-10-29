# Build the No Limit practice arena

You're building a local practice arena for a pokerbot tournament. Read this whole prompt and the spec files it points to before writing any code, then do the environment check and report back.

## Mission

Build an arena in this repository that:

1. faithfully simulates the format of **No Limit**, the Sequoia × Citadel Securities × OpenAI pokerbot tournament;
2. runs **mini-events** in which N independent Claude Code builders (default 40) each get a hard build window (default 20 minutes) to write a bot from scratch, followed by scored tournaments and short patch rounds;
3. scores, explains and archives every event, so a human team can learn what wins before the real competition;
4. profiles the field of quickly built bots for leaks our bot can exploit, and lets us test exploits against every archived bot (`docs/FIELD_STUDY.md`).

Priorities, in order:

1. faithfulness to the format;
2. robustness;
3. measured results with error bars;
4. speed;
5. features.

## The spec (read first)

- `docs/OFFICIAL_FORMAT.md`: the official rules restated as a spec, plus every gap the rules leave open and the arena's choice for it. Where the official rules decide something, they win; tell me about any conflict.
- `docs/BUILDER_BRIEF.md`: the per-builder brief, a template you render.
- `docs/PATCH_PROMPT.md`: what builders are told between tournaments.
- `docs/ANALYST_PROMPT.md`: the post-event debrief.
- `docs/FIELD_STUDY.md`: why we run the arena (what wins, and where quickly built bots leak), with added requirements for milestones 2, 4, 6 and 7.
- `configs/event.example.yaml`: every tunable, with its default.
- `configs/archetypes.yaml`: strategy directions for builder diversity.
- `configs/builder_settings.example.json`: the Claude Code settings one builder runs under.
- `CLAUDE.md`: standing invariants.

## How to work

**Environment check first.** Before writing code, report:

- the OS, CPU core count, RAM and Python version;
- `claude --version`;
- whether Claude Code's Bash sandbox can run here (on Linux it needs bubblewrap and socat);
- which auth is available: `ANTHROPIC_API_KEY` or a subscription login.

Flag blockers now.

**Milestone by milestone.** The milestones are listed at the end of this prompt. After each one:

1. run the tests and commit;
2. report what you built, the test results, benchmark numbers and open questions;
3. wait for me.

**Dependencies.** Use Python 3.11+ in a venv at `.venv`.

- Runtime deps: numpy and pyyaml.
- Test-only deps: pytest and pokerkit.
- Builder bots get the standard library and numpy only.

Ask before adding anything else.

**Verify Claude Code details; don't recall them.** For every Claude Code CLI flag and settings key you use, check both of these against the installed version:

- `claude --help`;
- the current docs at code.claude.com/docs: headless, cli-reference, sandboxing, permissions and settings-reference.

Record what you verified, including minimum versions, in `docs/CLAUDE_CODE_NOTES.md`.

**Spending guardrail.** Never launch real `claude -p` builder processes except in milestone 5's smoke test (2 builders, 4-minute build). Every other pipeline test uses mock builders (`--mock`). I start real events myself.

## Repository layout

Adjust this if you have a reason, and say why.

```
arena/
  engine/       variants, dealing, betting, pots, showdown, hand evaluation
  variants/     variant specs, twist generator, EVENT.md renderer
  runner/       bot loading, timing, watchdog, runtime restrictions for bot code
  tournament/   table draws, sit-and-go loop, ICM, scoring, stats, hand logs
  kit/          starter-kit sources copied into each builder workspace
  referee/      event lifecycle CLI
  house_bots/   reference opponents
  report/       markdown reports
  bench.py
tests/
events/         referee-only data (gitignored)
```

Builder workspaces live **outside** this repo, under `paths.workspaces_root`, so builders never load this repo's CLAUDE.md.

## Components

### 1. Engine

**Variant spec.** One rules engine, driven by a variant spec. Implement no-limit hold'em first, but make the spec general enough to describe:

- the deck: ranks, suits and size;
- hole cards, discards and when they happen;
- the board streets;
- the card-use rule: best five of any, exactly two hole plus three board, or at least one hole card;
- the hand-ranking order, which can differ from standard (in short deck a flush beats a full house and A-6-7-8-9 is a straight);
- the betting structure: no-limit, pot-limit or fixed-limit;
- antes by level.

**Tournament rules.** Implement these correctly:

- blinds and antes by level;
- heads-up blind and button order;
- a documented dead-button simplification;
- min-raise and full-raise rules: a short all-in doesn't reopen betting for players who have already acted;
- side pots, and split pots with a deterministic odd-chip rule;
- eliminations: when several bots bust in one hand, the one with the larger stack at the start of the hand places higher, and exact ties split those places' points.

Write the dealer rules you chose into `arena/kit/RULES.md`, which ships to builders.

**Hand evaluation.**

- Build a fast pure-Python evaluator for standard rank orders, with lookup tables built at import, plus a generic evaluator for twists.
- Cross-validate against pokerkit on at least 100k random deals and action sequences, covering showdown winners, pot and side-pot distribution, and betting legality, for every variant pokerkit supports. Keep this as a test.
- Property-test the generic evaluator.

**Performance.** Target at least 5,000 hands/s per core in NLHE with trivial bots, excluding bot time. Report what you actually get. Never trade correctness for speed.

### 2. Bot interface (`kit/agent_template.py`)

The real interface is only revealed on the day, so keep ours small and obvious: learning it should take two minutes.

**`Agent.__init__(self, config)`** runs once per table. `config` contains:

- the variant spec and its rules text;
- the points table and the blind schedule;
- the number of seats and the starting stack;
- the bot's own seat id;
- the decision limit;
- a per-table integer seed.

**`Agent.act(self, obs) -> dict`** returns `{"action": "fold"|"check"|"call"|"bet"|"raise", "amount": int}`. Amounts are raise-to totals for the street. All-in is a bet or raise to the maximum.

**`Agent.observe(self, event)`** is optional. It receives hand results and showdown cards.

**`obs`** is a plain dict of primitives, so it is cheap to build and to read. It contains:

- hand and street ids;
- hole cards and board as strings like `"As"` and `"Td"`;
- the pot and side pots;
- stacks and street contributions by seat;
- the button seat;
- the legal actions, `to_call`, `min_raise_to` and `max_raise_to`;
- this hand's action history;
- hands played at this table;
- the current blind level and hands until the next one;
- places already decided;
- the seats still alive.

Document every field with an example in the docstring. The template, copied to `bot/agent.py`, must itself be a valid always-check/fold bot.

### 3. Bot runner (the 1 ms rule, enforced safely)

**Loading.** Load each bot as a package under a unique module name; bots use relative imports only. Create a fresh `Agent` per table. Import happens once per worker, under a generous separate limit (`tournament.import_limit_s`). `__init__` gets `tournament.init_limit_s` of wall time per table.

**Timing** (`tournament.timing`).

- Default `thread_cpu`: measure each `act()` call with `time.thread_time_ns()`. On a busy shared machine this approximates wall time on a dedicated core.
- Log wall time too.
- Check the timer's resolution at startup. If it's coarser than 10 µs, fall back to `wall` and warn.

**Substitutions.** A call that goes over the limit, raises an exception or returns an illegal action becomes fold, or check when checking is free. Count every substitution per bot, by type.

**Hangs.**

- Run a wall-clock watchdog around each call (`tournament.hang_watchdog_ms`, via `signal.setitimer`).
- If a worker still gets stuck in native code, the parent kills it, replays the table with the offending bot set to always fold/check, and reports it.

A bad bot must never stall or crash a tournament.

**Bot code restrictions.**

- Block socket creation inside workers.
- Silence stdout and stderr, but keep the first few lines per bot for debugging.
- Set a memory rlimit per worker where the OS supports it.
- Enforce the size limit on the bot directory.
- Optionally run workers inside `@anthropic-ai/sandbox-runtime` if it's installed.

### 4. Tournament

**Iteration loop.** Follow `docs/OFFICIAL_FORMAT.md` exactly:

- each iteration seats every bot once, at random tables of eight;
- when the field isn't a multiple of eight, fill seats with random copies of submitted bots, which earn nothing;
- play each table until one bot is left or the hand cap is reached;
- award points by place;
- at the cap, settle the survivors with ICM (Malmuth–Harville over the remaining places), using the same code as `kit/icm.py`.

**Per-bot results.**

- average points per table, with a standard error and a 95% interval;
- finishing-place distribution;
- VPIP, PFR and aggression;
- showdown rate;
- the share of its tables that hit the hand cap;
- substitution counts.

**Parallelism and determinism.** Run across `tournament.workers` processes. Results must be deterministic given the bot snapshot hashes, the config and the seed, and must not depend on the worker count.

**Hand logs.** Keep compact, compressed hand logs per tournament. They must be filterable to one bot's tables with the other seats anonymized, so builders can receive their own hands.

**Benchmark.** Target 40 house bots × 400 iterations in 5 minutes or less on 16 cores. Report the actual time and how it scales with the number of workers.

### 5. Variants, points, blinds

**Variant library.** `nlhe`, `shortdeck`, `plo` (pot-limit Omaha), `pineapple`, `crazy_pineapple` and `royal` (20-card deck), each with engine tests.

**Twist generator.** Generates novel but playable variants by combining spec options. Examples:

- a 4-card board;
- 3 hole cards with exactly one to be used;
- a 40-card deck;
- flush above full house;
- antes from level 3.

A twist ships only if all three hold:

1. it passes the engine self-tests;
2. it plays 10k hands with house bots without errors;
3. its rendered ranking order matches the measured category frequencies, or EVENT.md flags where it doesn't.

**`EVENT.md` renderer.** Writes the complete rules for the drawn variant in plain English:

- the deck and the deal;
- the streets and the betting structure;
- which cards may be used;
- the ranking order, with one example hand per category and the frequencies measured on this deck;
- the points table and the blind schedule;
- stacks and the hand cap;
- the tournament plan.

A builder should never need the engine source to understand the rules.

**Points library** (eight places):

| Name | Points by place |
| :- | :- |
| `flat` | 7, 6, 5, 4, 3, 2, 1, 0 |
| `standard` | 100, 60, 40, 25, 15, 10, 5, 0 |
| `top_heavy` | 100, 45, 20, 8, 0, 0, 0, 0 |
| `winner_take_most` | 100, 25, 5, 0, 0, 0, 0, 0 |
| `castle` | 9, 4, 2, 0, 0, 0, 0, 0 |

**Blind schedules.** All start at 10/20 and rise every 25 hands:

- `doubling`;
- `sng_standard`: 10/20, 15/30, 25/50, 50/100, 75/150, 100/200, 150/300, 200/400, with an ante of bb/10 from level 5;
- `slow`: 10/20, 15/30, 20/40, 30/60, 40/80, 50/100, 60/120, 80/160.

### 6. Starter kit (copied into every workspace)

**Contents.**

- `EVENT.md`
- `kit/RULES.md`
- `kit/agent_template.py`, also copied to `bot/agent.py`
- `kit/localsim.py`
- `kit/check_bot.py`
- `kit/submit.py`
- `kit/clock.py`
- `kit/icm.py`
- `kit/house_bots/`
- `kit/arena/`, a read-only copy of the engine, runner and tournament code the referee runs (the kit scripts import it)
- a stub `NOTES.md`

**localsim and check_bot.** 40 teams share the machine, so:

- run them on one core under `nice`;
- cap them by `kit.localsim_max_tables` and `kit.localsim_max_seconds`;
- keep their output to a few lines, because builders read terminal output.

**submit.py.** First it runs the same validation the referee will:

- import under a random module name;
- interface checks;
- a smoke match;
- a size check;
- a timing profile.

Then it:

1. enforces the cooldown and the window deadline;
2. snapshots `bot/` immutably, with a content hash, into `.submissions/<id>/` inside the workspace (the only place sandboxed commands can write);
3. appends to `.submissions/log.jsonl`;
4. prints `ACCEPTED` or `REJECTED` with reasons, and when the next submission is allowed.

**clock.py.** Prints the time left in the current window and what happens at its end. The workspace copy of the clock state is informational; the referee's copy is authoritative.

### 7. Referee (`python -m arena.referee ...`)

**Subcommands.**

- **`new <config> [--card-from <event>]`.** Draws the secrets (seed, variant, points, blinds), creates the event directory and the N workspaces, and renders the briefs. Nothing is revealed yet. `--card-from` reuses another event's card, so builders or humans can replay identical conditions.
- **`run <event> [--mock] [--time-scale X]`.** Runs the whole event: reveal, build window, freeze, tournaments, patch rounds, report. It must be crash-safe: persist a state machine in `events/<id>/state.json`, and `run` resumes where it stopped.
- **`status <event>`.** A live table of builder states, last accepted submission, errors and cost so far.
- **`enter <event> <bot_dir> --team <name>`.** Enters an external bot, such as one my human team built, into an event's tournaments.
- **`report <event>`** and **`debrief <event>`.**
- **`cleanup <event>`.** Archives the workspaces into `events/<id>/workspaces.tar.gz` and deletes them from `workspaces_root`.

**Launching builders.**

- Assign models and archetypes per the config.
- Stagger launches by `builders.launch_stagger_seconds`.
- Run each builder as its own process, with its workspace as the working directory.
- Put the arena venv first on `PATH`, so that `python` has numpy.
- Capture the stream to `events/<id>/logs/<team>.jsonl`.

Baseline invocation (verify every flag first):

```
claude -p "The build phase has started. Read EVENT.md, then build and submit your bot." \
  --model <alias> \
  --append-system-prompt-file <workspace>/.brief/BRIEF.md \
  --settings events/<id>/settings/<team>.json \
  --permission-mode acceptEdits \
  --permission-prompts none \
  --output-format stream-json --verbose
```

- **`auth.mode: api_key`.** Add `--bare`. It needs `ANTHROPIC_API_KEY`, and it keeps the operator's personal hooks, skills, MCP servers and CLAUDE.md out of every builder.
- **`auth.mode: subscription`.** Omit `--bare`.
- **Budget.** Add `--max-budget-usd` when `builders.max_budget_usd_per_builder` is set.
- **Missing flags.** If the installed version lacks a flag, degrade gracefully and note it.

**Ending a window.** At the deadline, send SIGINT, then SIGTERM after 10 seconds, then SIGKILL after 30. Record the exit status, plus `session_id` and `total_cost_usd` from the result event when present.

**Freeze.**

1. Per team, take the latest accepted submission stamped at or before the freeze time that respects the cooldown.
2. Re-validate it and copy it, hashed, into `events/<id>/bots/<team>/T<k>/`.

Teams with no valid submission don't play, as in the real rules. Before each tournament, re-time every frozen bot on the idle machine and include the results in the report.

**Patch rounds** (`schedule.patch_minutes` > 0). After each tournament except the last:

1. Write `results/T<k>/` into each workspace, as allowed by `schedule.feedback`.
2. Render `docs/PATCH_PROMPT.md`.
3. Resume each builder with `claude -p "<rendered prompt>" --resume <session_id>`, from its workspace, with the same settings and flags.
4. Apply the same window and freeze procedure.

**Failure handling.**

- Parse each stream for auth, rate-limit, overload and usage-limit errors.
- If more than 20% of builders fail to start, or hit auth or usage-limit errors in the first 2 minutes, pause the event and tell me rather than burning the window.
- Record every builder failure in the report.

**Mock mode.** `--mock` replaces Claude with scripted builders. A mock builder:

- copies a house bot into `bot/`;
- sometimes breaks it;
- submits on a schedule;
- occasionally misses the deadline.

With `--time-scale` (for example 0.05), this runs the whole pipeline in minutes, for free.

### 8. Builder isolation (requirements, then proof)

**Requirements.** A builder must not be able to:

- read other workspaces or the referee's data;
- write outside its own workspace;
- reach the network;
- start subagents or workflows;
- use web tools;
- see `ANTHROPIC_API_KEY` from shell commands.

**Mechanism.** Generate one settings file per team, following `configs/builder_settings.example.json`. It has two layers.

The Bash sandbox:

- enabled, with `failIfUnavailable` and no unsandboxed retries;
- `denyRead` on the workspaces root and the events directory, with `allowRead` for the team's own workspace;
- an empty network allowlist with `strictAllowlist`;
- the credential env var denied.

Permission deny rules:

- `Read(...)` on every sibling workspace and on the events directory. The Read tool runs outside the sandbox, so `denyRead` doesn't cover it.
- `WebFetch`, `WebSearch`, `Agent` and `Workflow`.

Evaluate whether `permissions.blockReadsOutsideWorkingDirectories` would replace the per-path rules more simply.

**Proof.** In the smoke test:

1. Plant canary files in a sibling workspace and in the events directory.
2. Using a scripted `claude -p` run under a builder's settings, show that the builder can't read the canaries, can't reach the internet, and can't write outside its workspace.
3. Report the results.

If the sandbox can't run on this machine, stop and tell me; don't fall back silently.

### 9. Reports and lessons

**`events/<id>/report/REPORT.md`** contains:

- the event card;
- the final weighted leaderboard;
- per-tournament leaderboards with 95% intervals, marking rank gaps that are within noise;
- breakdowns by archetype and by model, with sample sizes and uncertainty;
- substitution counts: timeouts, errors and illegal actions;
- a submission timeline: who had an accepted bot at minutes 5, 10 and 20;
- builder failures;
- cost per builder and in total.

**`debrief`** runs `docs/ANALYST_PROMPT.md` as one `claude -p` call, only when I ask.

**`LESSONS.md`** at the repo root accumulates across events. Only the analyst appends to it.

## Milestones (stop and report after each)

1. **Engine and evaluator, hold'em first.**
   - The pokerkit cross-validation passes.
   - Benchmark numbers are reported.
2. **Runner, tournament, ICM, scoring and house bots.**
   - Determinism test: identical results with 1 and with N workers.
   - Fault-injection tests with bots that hang, crash, return illegal actions or exceed the limit.
   - The 40×400 benchmark.
   - The bot zoo and per-decision hand-log features from `docs/FIELD_STUDY.md`.
3. **Starter kit.** clock, submit, check_bot, localsim and the template, tested inside a temp workspace under the builder sandbox settings.
4. **Referee with mock builders.** A 40-builder mock event with 3 tournaments and patch rounds, at `--time-scale 0.05`, that:
   - completes;
   - survives a forced crash and resumes;
   - produces the report.

   Also the bot archive and the `gauntlet` command from `docs/FIELD_STUDY.md`.
5. **Real smoke test.** 2 real builders, a 4-minute build and 1 tournament, plus the isolation proof.
   - Report per-builder cost and wall-clock behavior.
   - Estimate the cost of a 40-builder, 6-tournament event at the default settings.
   - **Then stop and wait for my go-ahead.**
6. **Variants and libraries.** Variant library, twist generator, points and blind libraries and the EVENT.md renderer, each with tests.
7. **Debrief and handover.**
   - The debrief command and `LESSONS.md`.
   - The field profile and exploit board in REPORT.md, and the leak sections of the debrief (`docs/FIELD_STUDY.md`).
   - Rewrite `README.md` as the operator's manual: setup, auth choices, hardware guidance, running an event and troubleshooting.

## Definition of done

- `pytest -q` passes.
- A 40-builder, 6-tournament mock event completes end to end and writes its report.
- The real smoke test has run and the isolation proof passed.
- Someone who has never seen this repo can run a real event from README.md alone.
