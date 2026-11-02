# Report: shortdeck-002

## Event card

- **Variant:** shortdeck: No-limit hold'em with a 36-card deck (6 to A): a flush beats a full house and A-6-7-8-9 is a straight.
- **Points table (top_heavy):** 1st 100, 2nd 45, 3rd 20, 4th 8, 5th 0, 6th 0, 7th 0, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 2685883945

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b07 | opus | free choice | 24.9 | 24.9 | not played | not played | not played | not played | not played |
| 2 | b06 | opus | math_core | 24.4 | 24.4 | not played | not played | not played | not played | not played |
| 3 | b02 | opus | model_pressure | 23.4 | 23.4 | not played | not played | not played | not played | not played |
| 4 | b08 | opus | free choice | 22.9 | 22.9 | not played | not played | not played | not played | not played |
| 5 | b05 | opus | math_core | 22.0 | 22.0 | not played | not played | not played | not played | not played |
| 6 | b01 | opus | free choice | 19.3 | 19.3 | not played | not played | not played | not played | not played |
| 7 | b04 | opus | free choice | 18.4 | 18.4 | not played | not played | not played | not played | not played |
| 8 | b03 | opus | model_pressure | 17.6 | 17.6 | not played | not played | not played | not played | not played |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b07 | 15% | 55% | 42% | 17% | 25% | 18% | 1.9 |
| 2 | b06 | 16% | 54% | 39% | 28% | 35% | 20% | 1.7 |
| 3 | b02 | 15% | 56% | 39% | 23% | 29% | 19% | 2.2 |
| 4 | b08 | 14% | 52% | 39% | 18% | 33% | 19% | 8.1 |
| 5 | b05 | 13% | 51% | 37% | 29% | 27% | 18% | 2.1 |
| 6 | b01 | 7% | 28% | 39% | 26% | 28% | 21% | 2.4 |
| 7 | b04 | 10% | 52% | 33% | 26% | 22% | 14% | 1.8 |
| 8 | b03 | 10% | 50% | 32% | 33% | 27% | 15% | 1.3 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T1.md`). Equity-driven bot for shortdeck. Preflop uses a precomputed 81x81 class-vs-class equity matrix (36-card deck) to get equity vs an estimated opponent range (top-p%), with chip-EV push/fold and reshove-with-fold-equity when short. …

### 2. b06 (math_core)

**In its builder's words** (Strategy in `bots/b06/NOTES.T1.md`). Math-first bot. Preflop decisions come from a precomputed 81x81 shortdeck class-vs-class equity matrix (equity vs "top q%" ranges), with ICM-priced (points, not chips) push/fold and all-in calls when short. Postflop it computes near-exact equity with a vectorized numpy evaluator (rank-count lookup + flush table) against an opponent range that is narrowed by their preflop action and postflop bets, then …

### 3. b02 (model_pressure)

**In its builder's words** (Strategy in `bots/b02/NOTES.T1.md`). Equity-driven bot for 36-card shortdeck. Preflop uses a precomputed 81x81 hand-class equity matrix (bot/data.npz) to price opens, shoves and calls against estimated ranges; postflop computes equity with a vectorised numpy lookup evaluator against every (river) or a 100-combo sample of (flop/turn) opponent hole-card combos, weighted by each opponent's preflop range and narrowed by their postflop aggression. …

### 4. b08 (free choice)

**In its builder's words** (Strategy in `bots/b08/NOTES.T1.md`). Table-driven shortdeck bot. Preflop uses a precomputed 81x81 class-vs-class equity matrix (shortdeck, Monte Carlo offline, bot/eqmat.json) to get equity vs "top p%" ranges; short stacks play push/fold by explicit chip-EV of shoving/re-shoving against modelled (and read-adjusted) calling ranges; postflop uses a fast made-hand/draw strength heuristic, bets for value often and calls tightly. …

### 5. b05 (math_core)

**In its builder's words** (Strategy in `bots/b05/NOTES.T1.md`). Math-first bot. A precomputed exact 7-card hand-value table for the 36-card deck (8.3M entries, colex index, verified against the kit evaluator) powers a vectorised numpy Monte Carlo at decision time (opponent hands sampled directly from their estimated ranges, ~128/96/72 trials for 1/2/3 opponents, ~150 us). …

### 6. b01 (free choice)

**In its builder's words** (Strategy in `bots/b01/NOTES.T1.md`). Equity-driven bot. Preflop: position-aware opening ranges from a shortdeck hand-strength table, push/fold ranges widened by stack depth and short-handedness, and all-in calls decided by equity vs the shover's estimated range (81x81 precomputed class-vs-class matrix; shover range from their seat, depth and PFR) with an exact Malmuth-Harville ICM check when <=6 players remain. …

### 7. b04 (free choice)

**In its builder's words** (Strategy in `bots/b04/NOTES.T1.md`). Table-driven shortdeck bot. Preflop it uses a precomputed 81x81 class-vs-class equity matrix (36-card deck, flush > full house) to get equity against an opponent's estimated range, and makes push/fold and calling decisions by chip EV with a small ICM margin. …

### 8. b03 (model_pressure)

**In its builder's words** (Strategy in `bots/b03/NOTES.T1.md`). Equity-driven bot. Preflop uses a precomputed 81x81 shortdeck class-vs-class equity matrix (bot/pre.json) to price shoves and calls against estimated opponent ranges; postflop runs a vectorized numpy Monte Carlo (80-170 samples from a precomputed permutation bank, ~0.1-0.25 ms) against opponents' ranges weighted by their preflop and postflop actions. …

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b07 | 24.9 ± 2.1 | 53% | 100% | 1 | 1–4 | 53% | 30% | 12% | 5% | 1% | · | · | · |
| b06 | 24.4 ± 2.2 | 33% | 100% | 2 | 1–4 | 33% | 35% | 20% | 10% | 3% | · | · | · |
| b02 | 23.4 ± 2.1 | 9% | 100% | 3 | 1–5 | 9% | 19% | 31% | 28% | 13% | · | · | · |
| b08 | 22.9 ± 2.1 | 4% | 99% | 4 | 2–5 | 4% | 12% | 27% | 35% | 21% | 1% | · | · |
| b05 | 22.0 ± 2.2 | 1% | 95% | 5 | 3–5 | 1% | 4% | 11% | 23% | 57% | 4% | · | · |
| b01 | 19.3 ± 1.7 | 0% | 4% | 6 | 6–8 | · | · | · | · | 4% | 65% | 25% | 6% |
| b04 | 18.4 ± 1.9 | 0% | 1% | 7 | 6–8 | · | · | · | · | 1% | 20% | 51% | 28% |
| b03 | 17.6 ± 2.0 | 0% | 0% | 8 | 6–8 | · | · | · | · | · | 10% | 24% | 66% |

## Field profile

How the bots played, from the hand logs of T1–T1 (655,946 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b07 | 25% | 18% | 49% | 67% | 2% | 45% | 26% |
| b06 | 35% | 20% | 41% | 37% | 12% | 56% | 23% |
| b02 | 29% | 19% | 50% | 53% | 2% | 48% | 36% |
| b08 | 33% | 19% | 57% | 49% | 2% | 78% | 18% |
| b05 | 27% | 18% | 41% | 69% | 5% | 41% | 31% |
| b01 | 28% | 21% | 50% | 78% | 2% | 68% | 18% |
| b04 | 22% | 14% | 33% | 63% | 4% | 59% | 25% |
| b03 | 27% | 15% | 33% | 52% | 4% | 53% | 16% |
| **Field** | 28% (22%–35%) | 18% (14%–21%) | 45% (33%–57%) | 59% (37%–78%) | 4% (2%–12%) | 57% (41%–78%) | 24% (16%–36%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b07 | 60% | 28% | 15% | 41% | 54% | 84% | 49% |
| b06 | 71% | 51% | 22% | 40% | 50% | 65% | 39% |
| b02 | 69% | 40% | 33% | 38% | 51% | 70% | 60% |
| b08 | 84% | 90% | 24% | 29% | 51% | 83% | 46% |
| b05 | 63% | 63% | 35% | 43% | 52% | 67% | 65% |
| b01 | 63% | 55% | 33% | 43% | 53% | 66% | 85% |
| b04 | 68% | 33% | 44% | 44% | 47% | 47% | 34% |
| b03 | 68% | 33% | 39% | 42% | 45% | 84% | 25% |
| **Field** | 68% (60%–84%) | 53% (28%–90%) | 31% (15%–44%) | 40% (29%–44%) | 50% (45%–54%) | 71% (47%–84%) | 54% (25%–85%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b07 | 33% | 26% | 31% | 22% | 19% | 25% | 38% | 60% |
| b06 | 50% | 50% | 39% | 31% | 29% | 38% | 50% | 55% |
| b02 | 65% | 39% | 33% | 25% | 22% | 32% | 47% | 53% |
| b08 | 51% | 34% | 38% | 30% | 27% | 33% | 49% | 60% |
| b05 | 40% | 28% | 29% | 25% | 23% | 27% | 35% | 47% |
| b01 | 41% | 25% | 31% | 26% | 25% | 29% | 32% | 39% |
| b04 | 24% | 15% | 27% | 22% | 19% | 21% | 28% | 54% |
| b03 | 28% | 26% | 31% | 25% | 23% | 28% | 33% | 68% |
| **Field** | 36% (24%–65%) | 29% (15%–50%) | 33% (27%–39%) | 26% (22%–31%) | 23% (19%–29%) | 29% (21%–38%) | 39% (28%–50%) | 54% (39%–68%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b07 | 22% | 23% | 29% | 32% |
| b06 | 20% | 18% | 24% | 31% |
| b02 | 76%† | 50% | 27% | 25% |
| b08 | 46% | 21% | 13% | 12% |
| b05 | 64% | 29% | 23% | 28% |
| b01 | 20% | 17% | 18% | 18% |
| b04 | 47% | 26% | 16% | 16% |
| b03 | 16% | 13% | 18% | 17% |
| **Field** | 32% (16%–76%) | 24% (13%–50%) | 21% (13%–29%) | 23% (12%–32%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b07 | 2.5 bb | 62% | 60% pot | 50% |
| b06 | 2.5 bb | 56% | 60% pot | 42% |
| b02 | 2.5 bb | 69% | 50% pot | 43% |
| b08 | 2.5 bb | 40% | 60% pot | 32% |
| b05 | 2.5 bb | 66% | 70% pot | 63% |
| b01 | 2.5 bb | 58% | 60% pot | 32% |
| b04 | 2.5 bb | 82% | 60% pot | 41% |
| b03 | 2.5 bb | 63% | 60% pot | 40% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b07**: no spot below the field.
- **b06**: facing a shove: -1.2 ± 1.3 bb/100 (folds 76% against 74%) — within noise; facing a 3-bet: -0.4 ± 1.5 bb/100 (raises 8% against 3%) — within noise.
- **b02**: facing an open: -0.8 ± 2.6 bb/100 (folds 86% against 81%) — within noise.
- **b08**: facing a shove: -1.8 ± 1.2 bb/100 (folds 81% against 73%); facing a steal: -0.9 ± 1.7 bb/100 (calls 48% against 33%) — within noise.
- **b05**: facing a c-bet: -1.6 ± 2.1 bb/100 (calls 35% against 47%) — within noise; facing a 3-bet: -1.4 ± 1.9 bb/100 (calls 55% against 38%) — within noise.
- **b01**: heads-up vs a raise: -1.0 ± 0.5 bb/100 (folds 85% against 47%); facing a shove: -0.1 ± 1.6 bb/100 (calls 18% against 25%) — within noise.
- **b04**: facing a river bet: -11.3 ± 2.6 bb/100 (calls 44% against 29%); facing an open: -5.7 ± 3.0 bb/100 (calls 8% against 16%).
- **b03**: facing a river bet: -10.2 ± 3.2 bb/100 (folds 55% against 65%); facing an open: -6.4 ± 3.4 bb/100 (calls 19% against 15%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 59% (37%–78%) | b02 +9.1 (all fold 33%), b08 +8.5 (all fold 42%) | b04 -2.1, b03 -2.0 |
| 3-bet | 57% (41%–78%) | b05 +9.1 (all fold 58%), b06 +7.9 (all fold 56%) | b03 -2.3, b05 -1.4 |
| Preflop shove | 74% (63%–81%) | b05 +5.1 (all fold 65%), b08 +4.5 (all fold 64%) | b08 -1.8, b06 -1.2 |
| Heads-up raise | 54% (25%–85%) | b07 +1.2 (all fold 58%), b05 +1.1 (all fold 59%) | b01 -1.0, b08 -0.8 |
| C-bet | 53% (28%–90%) | b01 +15.3 (all fold 49%), b02 +14.4 (all fold 54%) | b03 -5.5, b04 -5.3 |
| River bet | 64% (52%–82%) | b06 +18.6 (all fold 61%), b05 +16.0 (all fold 63%) | b04 -11.3, b03 -10.2 |

## T1 (weight 1)

1,000 tables, 118,147 hands, 28 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b07 | 24.89 ± 2.17 | 1000 | 25% | 18% | 0 | 300 |
| 2 ≈ | b06 | 24.43 ± 2.22 | 1000 | 35% | 20% | 0 | 500 |
| 3 ≈ | b02 | 23.41 ± 2.18 | 1000 | 29% | 19% | 0 | 300 |
| 4 ≈ | b08 | 22.94 ± 2.09 | 1000 | 33% | 19% | 0 | 50 |
| 5 ≈ | b05 | 21.99 ± 2.09 | 1000 | 27% | 18% | 0 | 300 |
| 6 ≈ | b01 | 19.34 ± 1.76 | 1000 | 28% | 21% | 0 | 429 |
| 7 ≈ | b04 | 18.40 ± 1.90 | 1000 | 22% | 14% | 0 | 500 |
| 8 | b03 | 17.61 ± 1.90 | 1000 | 27% | 15% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

Not played (fewer than two valid bots).

## T3 (weight 3)

Not played (fewer than two valid bots).

## T4 (weight 4)

Not played (fewer than two valid bots).

## T5 (weight 5)

Not played (fewer than two valid bots).

## T6 (weight 6)

Not played (fewer than two valid bots).

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 21.4 ± 3.0 (n=4) |
| math_core | 23.2 ± 2.4 (n=2) |
| model_pressure | 20.5 ± 5.7 (n=2) |

| Model | Score |
| :- | -: |
| opus | 21.6 ± 1.9 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/0 | — | — | — | — | — |
| b02 | 0/0/0/0 | — | — | — | — | — |
| b03 | 0/0/0/0 | — | — | — | — | — |
| b04 | 0/0/0/0 | — | — | — | — | — |
| b05 | 0/0/0/0 | — | — | — | — | — |
| b06 | 0/0/0/0 | — | — | — | — | — |
| b07 | 0/0/0/0 | — | — | — | — | — |
| b08 | 0/0/0/0 | — | — | — | — | — |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 5 | 3 of 8 |
| 10 | 8 of 8 |
| 20 | 8 of 8 |
| 40 | 8 of 8 |
| 60 | 8 of 8 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 5 | 4 | finished | $5.60 |
| b02 | 7 | 6 | finished | $6.67 |
| b03 | 8 | 7 | finished | $5.55 |
| b04 | 7 | 6 | finished | $6.32 |
| b05 | 8 | 7 | finished | $5.60 |
| b06 | 7 | 6 | finished | $5.15 |
| b07 | 7 | 6 | finished | $7.85 |
| b08 | 9 | 8 | finished | $5.71 |

## Builder failures

- b01: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b02: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b03: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b04: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b05: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b06: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b07: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6
- b08: exit 0, errors none, no valid bot in T2, T3, T4, T5, T6

## Cost

Total $48.45; per builder: b01 $5.60, b02 $6.67, b03 $5.55, b04 $6.32, b05 $5.60, b06 $5.15, b07 $7.85, b08 $5.71

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 32% at the first reading, 87% at the last. It counts everything on the same login, including your own sessions.
