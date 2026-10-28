# No Limit practice arena

This repo is a local arena that simulates the No Limit pokerbot tournament and runs mini-events with many Claude Code builders.

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

- `pytest -q`
- `python -m arena.bench`
- `python -m arena.referee new configs/event.yaml`
- `python -m arena.referee run <event-id> [--mock] [--time-scale X]`
- `python -m arena.referee status|report|debrief|cleanup <event-id>`
