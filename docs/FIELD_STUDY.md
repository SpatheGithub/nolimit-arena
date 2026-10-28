# Field study: what wins, and where quickly built bots leak

This file states why our team runs the arena, and adds requirements to milestones 2, 4, 6 and 7. `SETUP_PROMPT.md` points here.

## Purpose

At the real event, most opponents will be bots that two-person teams built in 60 minutes with AI coding tools. They will look polished, but they share the shortcuts that fast, AI-assisted builds take. Our builders work under the same pressure, so each mini-event produces a population of bots that stands in for that field.

Every event should answer two questions:

1. **What wins?** Which approaches score best under the day's variant, points table and blind schedule, and how sure we can be.
2. **Where does the field leak points?** Which mistakes are common across bots, what they cost, and which exploits capture those points without making our own bot exploitable.

## What the format allows an exploit to use

- **Opponents are anonymous and state resets at every table.** An exploit is therefore either:
  - **population-level:** built into the bot's static strategy, from what the field does on average; or
  - **in-table:** learned within one table, with at most 200 hands and 7 opponents.
- **Teams can resubmit between tournaments.** Later tournaments weigh more (T6 is 6/21 of the final score), so adjusting to the observed field between tournaments pays.

## Hypotheses the arena tests

These are not findings yet. Each needs evidence from real events before it shapes our bot.

| # | Suspected leak in quickly built bots | How the arena measures it | Exploit if confirmed |
| :- | :- | :- | :- |
| 1 | Timeouts, exceptions and illegal amounts in rare spots: side pots, all-in for less, heads-up, discards, short-deck rankings | Substitutions by situation | Keep our bot robust, and apply pressure in the spots where others auto-fold |
| 2 | The same thresholds at every stack depth; no push/fold mode when short | VPIP, PFR and fold-to-shove by effective stack in big blinds | Steal and shove wider against overfolders; call tighter against overshovers |
| 3 | Chip-EV play that ignores the points table and ICM | Calls of all-ins near pay jumps compared with ICM-correct ranges | ICM pressure on medium stacks |
| 4 | Hold'em intuition carried into other variants | Showdown strength against bet behaviour, by hand category | Value-bet the categories the field underrates; bluff less into the ones it overrates |
| 5 | Folding too often to aggression | Fold-to-steal, fold-to-3-bet and fold-to-c-bet | Steal, 3-bet light and c-bet more |
| 6 | Calling stations | Went-to-showdown and call-down frequencies | Stop bluffing; value-bet thinner and bigger |
| 7 | Bet size that tracks hand strength | Bet size against showdown strength, per bot | In-table reads of sizing |
| 8 | Full-table ranges when short-handed or heads-up | VPIP and PFR by players remaining | Open wider late in a table |
| 9 | Ignoring the 200-hand cap and its ICM settlement | Changes in behaviour as the cap approaches | Adjust risk by hands left |
| 10 | Raise-to vs raise-by confusion, and fixed sizing patterns | Illegal-action counts and raise-size distributions | Mostly informative; feeds the in-table model |

## Added requirements

**Milestone 2: hand logs and a bot zoo.**
- **Hand logs** record per-decision features: street, effective stack in big blinds, players left, hands until the cap, size faced, action and amount. The report needs these to compute field tendencies.
- **House bots** form a zoo with two groups:
  - common quick-build patterns: a hand-strength threshold bot, a pot-odds caller, a Monte Carlo bot with a time budget, a min-raiser, a maniac shover, and an ICM-blind push/fold bot;
  - strong baselines: ICM-aware push/fold, and tight-aggressive play with stack-depth modes.

  The zoo serves as opponents in localsim and as a calibration set for the report's leak metrics.

**Milestone 4: archive and gauntlet.**
- **Archive.** Every frozen bot from every event is archived with its event card and snapshot hash.
- **Gauntlet.** `python -m arena.referee gauntlet <bot_dir> [--field <selector>] [--card-from <event>]` runs a candidate bot against archived bots. It needs no builders and spends nothing, and it is how we test exploits and our own builds.

**Milestone 6.** Variant docs list the hold'em intuitions each variant breaks. EVENT.md stays neutral; this list is for our analysis.

**Milestone 7: report and debrief.**
- **REPORT.md** gains two sections:
  - **Field profile:** aggregate tendencies of the builders' bots with intervals, and the biggest leaks per bot;
  - **Exploit board:** which zoo or builder bots gained most from which leaks.
- **The debrief** adds "Where the field leaks points" and "Exploits that worked" to `DEBRIEF.md`, and the lessons it appends to `LESSONS.md` cover leaks as well as winners.

## Field realism

- **Instructions.** The real field is built by people steering AI tools with short instructions. Keep about half of the builders on free choice: their bots are the closest stand-in.
- **Models.** Mix models (`builders.models`) so the population isn't one model's habits.
- **Other tools (later, if asked).** The real event's tools are not Claude-based. A pluggable builder command could add other AI coding CLIs to the population.
