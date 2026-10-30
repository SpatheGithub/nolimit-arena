# No Limit practice arena

This repo is a local arena that simulates the No Limit pokerbot tournament and runs mini-events with many Claude Code builders.

**Purpose:** find what wins, and where quickly built, AI-assisted bots leak points that our bot can exploit (`docs/FIELD_STUDY.md`).

- **Build plan:** `SETUP_PROMPT.md`
- **Spec:** `docs/`
- **Defaults:** `configs/`

## Invariants

- **Format fidelity.** `docs/OFFICIAL_FORMAT.md` is the spec.
  - Where the official rules decide something, follow them.
  - Where they're silent, use the documented arena choice and keep it configurable.
- **Bad bots can't break a tournament.** A failing bot never stalls or crashes one. Its decision becomes fold (or check when free) and is counted.
- **Reproducibility.** Every tournament can be reproduced from the bot snapshot hashes, the config and the seed.
- **Workspace location.** Builder workspaces live outside this repo (`paths.workspaces_root`), so builders never load this file.
- **Spending guardrail.** Never launch real `claude -p` builders, except for the milestone-5 smoke test or when the user runs the referee. Use `--mock` for pipeline tests.
- **Claude Code facts are verified, not remembered.** Check flags and settings keys against `claude --help` and code.claude.com/docs for the installed version, and record findings in `docs/CLAUDE_CODE_NOTES.md`.

## Conventions

- **Dependencies.**
  - Python 3.11+, with a venv at `.venv`.
  - Runtime: numpy and pyyaml.
  - Tests: pytest and pokerkit.
  - Bots: standard library + numpy.
- **Kit output.** Kit tools print short output, because builders read it in their terminal.
- **Milestones.** Commit after each milestone, with a summary of tests and benchmarks.

## Commands

Keep this list current as commands are added.

- `uv venv --python 3.12 .venv && uv pip install -e '.[test]'` (native arm64 Python; Homebrew and Anaconda on this Mac are Intel builds under Rosetta)
- `pytest -q` (`-m "not slow"` skips the 100k-hand pokerkit cross-validation and the exhaustive evaluator census)
- `python -m arena.engine.xval 100000` (engine vs pokerkit; prints counts of the documented rule differences)
- `python -m arena.bench [--workers 1,4,9]` and `python -m arena.bench --tournament [--workers 2,4,9]`
- `python -m arena.tournament --zoo 40 --iterations 400 [--bot NAME=DIR] [--log DIR] [--json FILE]` (one tournament with the real runner)
- `python -m arena.viz --demo | --dir LOGDIR | --event ID|latest` (live viewer: an event's builders during windows, its tables while a tournament plays, and its standings and winners after each one; the Browser pane's "event-viz" launch config follows the latest event, "table-viz" runs the demo)
- `python -m arena.referee new configs/event.yaml [--name ID]` (also builds the builders' own Python in `~/nolimit-workspaces/.python` and `.venv` on first use; `configs/full-opus.yaml` is the full-strength field)
- `python -m arena.referee isolation <event-id>` (scripted Haiku run with real builder settings; spends a fraction of a cent)
- `python -m arena.referee run <event-id> [--mock] [--time-scale X] [--no-viz]` (serves the live viewer on 127.0.0.1:8766; waits out plan usage limits and resumes)
- `python -m arena.referee status|report|cleanup <event-id>` (the report's rank view, field profile and exploit board come from the hand logs; profiles are cached in `results/T<k>/profile.json`)
- `python -m arena.referee debrief <event-id> [--mock]` (one paid `claude -p` analyst run, only when the user asks; writes `report/DEBRIEF.md` and `LESSONS.md`; `--mock` is free)
- `python -m arena.tournament.hands events/<id>/results/T<k> [--team NAME] [--hands 20]` (prints a tournament's compressed hand logs as text)
- `python -m arena.referee gauntlet <bot_dir> [--field latest|all|event:<id>[,<id>...]]` (scores a bot against archived builder bots; no builders, no spend)
- `python -m arena.house_bots.sync [--check]` (refreshes each house bot's copies of `_common` and `_strategy`; builders' kits get only `KIT_BOTS`)

Workers default to the performance cores on Apple Silicon: the efficiency cores run bot code about half as fast, which would distort the 1 ms thread-CPU limit.
