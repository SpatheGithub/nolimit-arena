# No Limit format reference

- **Source:** the official rules at https://pokerbot.sequoiacap.com/rules.html, read on October 28, 2026.
- **What this file is:** a restatement, in our own words, of the parts that matter for simulation. It ends with what the rules leave open and the choice this arena makes for each gap.
- **Keeping it current:** if the official page changes, update this file first, then the code.

## Build phase (real event)

- **Variant:** the poker variant is kept secret until the build phase starts. The regionals and the finals use different variants.
- **Teams and time:** teams of one or two people have 60 minutes to write a Python bot that implements an Agent interface the organizers provide.
- **Starter kit:** an agent template, a local simulator, an ICM calculator, the payout (points) structure and the blind schedule.
- **Tools:** for building, the rules name the AI tools teams may use (Astra and Codex) and allow public documentation. This applies to the human team, not to the simulation.
- **Submissions:** one submission is accepted every five minutes. The most recent accepted one is the team's active bot.

## Runtime constraints (real event)

- **Isolation:** bots run in isolated sandboxes without network access and cannot call outside services.
- **Time limit:** every decision must come back within one millisecond.
- **Size limit:** 100 MB.
- **Failures:** a bot that errors or runs out of time folds, or checks when checking is legal.
- **Resets and anonymity:** bot state is reset at the start of each table, and opponents are anonymized.

## Scoring (real event)

- **Six tournaments:** there are six scored tournaments, T1–T6.
  - T1 starts when the build phase ends.
  - Each later tournament starts 20 minutes after the previous one.
- **Submitting between tournaments:** teams can keep submitting after the build phase.
  - A team's active bot is frozen when each tournament starts.
  - Submissions accepted afterwards count from the next tournament.
- **One tournament:** 10,000 simulated eight-bot sit-and-gos. Bots are assigned to tables at random in each iteration.
- **Table rules:**
  - a table runs until one bot holds every chip or 200 hands have been played;
  - stacks start at 2,000;
  - blinds start at 10/20 and go up every 25 hands, following the schedule in the starter kit.
- **Points:**
  - Points depend on finishing place. The points table is announced at the start of the build phase and can depend on the variant.
  - A bot that busts gets the points for the place it finished in.
  - At the 200-hand cap, the surviving bots split the remaining places' points by ICM.
- **Filler seats:** when the field isn't a multiple of eight, empty seats are filled with random copies of submitted bots, and those copies earn nothing.
- **Score:**
  - A team's tournament score is its average points per table.
  - Final score = 1·T1 + 2·T2 + 3·T3 + 4·T4 + 5·T5 + 6·T6.
  - Ties go to a separate tiebreak challenge.

## Open questions and arena choices (all configurable)

| The rules don't specify | Arena choice |
| :- | :- |
| The Agent interface and observation format | Our own small interface (`kit/agent_template.py`), designed so adapting to the real one on the day is quick |
| The variant | Drawn from a pool of community-card variants, plus generated "twists" |
| The points table | Drawn from a library, from flat to winner-take-most |
| The blind increments | Start 10/20, rise every 25 hands; the schedule is drawn from a library |
| How the 1 ms is measured | Per-call thread CPU time, which stays fair on a shared machine; wall time is logged too |
| Several eliminations in one hand | The larger stack at the start of the hand places higher; exact ties split those places' points |
| Button and blinds after busts | A documented dead-button simplification (`kit/RULES.md`) |
| Packages available to bots | Standard library + numpy |
| Feedback between tournaments | Leaderboard, own stats, a sample of own hands (configurable) |
| Number of iterations | 400 per tournament by default, to fit local CPU; error bars always reported |

## Scaled schedule for a 20-minute mini-event

Times are compressed by a factor of three. The six tournaments, weighted 1–6, are kept.

| | Real event | Mini-event |
| :- | :- | :- |
| Build | 60 min | 20 min |
| Submission cooldown | 5 min | 2 min |
| Time between tournaments | 20 min | 7-minute patch window |
