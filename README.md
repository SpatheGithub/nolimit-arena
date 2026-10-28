# No Limit practice arena: kit for Claude Code

This kit has Claude Code build a local arena that mirrors the format of **No Limit**, the Sequoia × Citadel Securities × OpenAI pokerbot tournament. The arena then runs mini-events in which **40 independent Claude Code builders get 20 minutes each** to write a bot, followed by scored tournaments.

Claude Code will rewrite this README into a full operator's manual at milestone 7. Until then, this is the quick start.

## What's in the kit

| File | Purpose |
| :- | :- |
| `SETUP_PROMPT.md` | The prompt you give Claude Code to build the arena (one time) |
| `CLAUDE.md` | Standing project rules. Claude Code loads this automatically. |
| `docs/OFFICIAL_FORMAT.md` | The official format restated as a spec, plus the gaps and the arena's choices |
| `docs/BUILDER_BRIEF.md` | What each of the 40 builders is told (template) |
| `docs/PATCH_PROMPT.md` | What builders are told between tournaments (template) |
| `docs/ANALYST_PROMPT.md` | Post-event debrief that feeds `LESSONS.md` |
| `configs/event.example.yaml` | Defaults: 40 builders, 20-minute build, 6 tournaments, and so on |
| `configs/archetypes.yaml` | Strategy directions that keep the field diverse |
| `configs/builder_settings.example.json` | The Claude Code sandbox and permission settings each builder runs under |

## Before you start

**Machine.** macOS or Linux (on Windows, use WSL2). Forty Claude Code processes plus their test runs is a lot for a laptop.
- A rough starting point is 16+ cores and 32 GB+ RAM.
- Run your first real event with about 8 builders and watch CPU and memory before scaling up.

**Claude Code.** Install a recent version (`claude update`). Some flags in the plan need newer versions. Claude Code checks this itself and records it in `docs/CLAUDE_CODE_NOTES.md`.

**Bash sandbox.**
- macOS: nothing to install.
- Linux: install `bubblewrap` and `socat`. On Ubuntu 24.04+, also follow the AppArmor step in the sandboxing docs (code.claude.com/docs/en/sandboxing).

**Authentication.** An API key is recommended for this.
- **API key** (`auth.mode: api_key`), from the Claude Console:
  - lets builders run with `--bare`, so they start clean, without your personal CLAUDE.md, skills, hooks or MCP servers;
  - gives predictable, per-token billing.
- **Subscription** (`auth.mode: subscription`):
  - works without `--bare`;
  - `claude -p` usage currently draws on your plan's usage limits;
  - forty parallel builders will eat through those limits fast.

  Anthropic changed and then paused a policy on this during 2026, so check https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan.

**Python.** Python 3.11+. Claude Code sets up the venv.

**tmux** (or screen). An event runs for more than an hour.

## Step 1: build the arena (one time)

```bash
unzip nolimit-arena-kit.zip && cd nolimit-arena
git init && git add -A && git commit -m "kit"
claude
```

Then tell Claude Code:

> Read SETUP_PROMPT.md and the files it lists. Do the environment check, then milestone 1. Stop and report when it's done.

Continue one milestone at a time and review each report. Milestone 5 runs the only real-builder test, with 2 builders for 4 minutes. It reports the cost per builder and an estimate for a full event, then waits for your go-ahead.

## Step 2: dry run with mock builders (free)

```bash
python -m arena.referee new configs/event.yaml
python -m arena.referee run <event-id> --mock --time-scale 0.05
```

## Step 3: a real event

```bash
cp configs/event.example.yaml configs/event.yaml    # then edit: builders, models, schedule
tmux new -s event
python -m arena.referee new configs/event.yaml
python -m arena.referee run <event-id>
```

- **Monitor:** from another pane, run `python -m arena.referee status <event-id>`.
- **Location:** run the referee in your own terminal, not inside a Claude Code session. It's a long-running process that starts and stops 40 Claude Code processes.

## Step 4: results and lessons

```bash
python -m arena.referee report <event-id>
python -m arena.referee debrief <event-id>    # one Claude call; writes DEBRIEF.md and appends LESSONS.md
python -m arena.referee cleanup <event-id>
```

**Testing your own bots.** Use `python -m arena.referee enter <event-id> <bot_dir> --team <name>` to drop a bot your team built by hand into an event's tournaments. Use `new --card-from <event-id>` to rerun the exact same variant, points table and blinds.

## Cost and capacity

**Builder time.** With the defaults (20-minute build, then 5 patch windows of 7 minutes), each builder works about 55 minutes, which comes to about **2,200 builder-minutes** per event. Setting `schedule.tournaments: 1` (no patch rounds) cuts that to 800.

**Real cost.** Milestone 5's smoke test measures the cost per builder. Multiply it out before running 40.

**If you hit rate-limit retries in the logs:**
- launch fewer builders;
- raise `launch_stagger_seconds`;
- mix in cheaper models.

## Using this for the real competition

- **The real tools and rules.** At the event, the rules name the AI tools allowed for building (Astra and Codex), and the site describes building from scratch. Use this arena for strategy and architecture discovery. Rehearse the actual 60-minute build with those tools, for example by replaying an event card with `--card-from` and entering your own bot.
- **The interface.** Our Agent interface is a guess at theirs, so keep your approach easy to port.
- **What you can bring.** Ask the organizers (pokerbot@sequoiacap.com) what, if anything, you may bring in.
