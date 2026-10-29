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
- `python -m arena.viz --demo | --dir LOGDIR | --event ID` (live table viewer in the browser; the Browser pane's "table-viz" launch config runs the demo)
- `python -m arena.referee new configs/event.yaml`
- `python -m arena.referee run <event-id> [--mock] [--time-scale X]`
- `python -m arena.referee status|report|debrief|cleanup <event-id>`

Workers default to the performance cores on Apple Silicon: the efficiency cores run bot code about half as fast, which would distort the 1 ms thread-CPU limit.
