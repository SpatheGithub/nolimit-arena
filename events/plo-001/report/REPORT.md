# Report: plo-001

## Event card

- **Variant:** plo: Pot-limit Omaha: 4 hole cards; a hand uses exactly 2 of them and exactly 3 board cards.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 3213101072
- **Computer asleep:** 2 of 111 builder-window minutes, measured afterwards from the macOS power log; the builders lost that time

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b05 | opus | free choice | 738.4 | 36.3 | 36.6 | 35.5 | 34.3 | 36.0 | 34.2 |
| 2 | b08 | opus | model_pressure | 700.3 | 24.4 | 30.9 | 34.5 | 34.2 | 32.2 | 35.4 |
| 3 | b06 | opus | free choice | 696.1 | 34.8 | 35.3 | 32.4 | 33.3 | 32.7 | 32.8 |
| 4 | b01 | opus | math_core | 665.0 | 34.5 | 32.3 | 32.3 | 32.5 | 31.8 | 30.1 |
| 5 | b02 | opus | model_pressure | 657.8 | 31.6 | 31.0 | 30.9 | 31.1 | 30.7 | 32.3 |
| 6 | b04 | opus | free choice | 649.7 | 31.3 | 29.9 | 30.2 | 29.4 | 31.9 | 31.9 |
| 7 | b03 | opus | math_core | 627.1 | 30.9 | 29.6 | 30.4 | 30.3 | 30.2 | 28.9 |
| 8 | b07 | opus | free choice | 620.5 | 31.2 | 29.4 | 28.8 | 30.0 | 29.4 | 29.5 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b05 | 14% | 54% | 43% | 18% | 23% | 17% | 3.3 |
| 2 | b08 | 13% | 49% | 37% | 24% | 25% | 17% | 6.2 |
| 3 | b06 | 14% | 50% | 39% | 22% | 25% | 18% | 4.9 |
| 4 | b01 | 15% | 59% | 36% | 28% | 21% | 15% | 2.6 |
| 5 | b02 | 11% | 44% | 38% | 24% | 22% | 17% | 2.7 |
| 6 | b04 | 12% | 48% | 36% | 29% | 26% | 17% | 1.6 |
| 7 | b03 | 10% | 43% | 36% | 24% | 23% | 17% | 1.9 |
| 8 | b07 | 12% | 52% | 35% | 30% | 30% | 20% | 3.7 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b05 (free choice)

**In its builder's words** (Strategy in `bots/b05/NOTES.T6.md`). (bot playing T6: submission 007-fcc1c7ee)

### 2. b08 (model_pressure)

**In its builder's words** (Strategy in `bots/b08/NOTES.T6.md`). **Summary.** Pot-limit Omaha bot built on precomputed hand tables: for every board rank pattern and hole rank pair it knows the best non-flush hand, so in ~0.1-0.3 ms it counts how many opponent holdings beat it, averaged over all turn/river rank runouts, with flushes handled separately. That equity vs a random hand is then narrowed to each opponent's likely range. …

### 3. b06 (free choice)

**In its builder's words** (Strategy in `bots/b06/NOTES.T6.md`). — Pot-limit Omaha bot, v56 (submission 014-d659f6ea). Exact hand evaluation (2 hole + 3 board cards) from precomputed tables; tight-aggressive preflop driven by a precomputed equity table of all 270,725 starting hands; postflop decisions from where our made hand ranks against every possible opponent holding, plus counted draws; per-opponent stats steer calling and bluffing; an ICM-style premium on stack-risking …

### 4. b01 (math_core)

**In its builder's words** (Strategy in `bots/b01/NOTES.T6.md`). Bot for T6: **015-2fe717d6** (same code as 013-2fe717d6: the T1 bot 005/012 + wider heads-up defense).

### 5. b02 (model_pressure)

**In its builder's words** (Strategy in `bots/b02/NOTES.T6.md`). Bot playing T6: submission 009-db541b33 (`bot/agent.py` + `bot/pre_pct.json`), unchanged from T5.

### 6. b04 (free choice)

**In its builder's words** (Strategy in `bots/b04/NOTES.T6.md`). **Summary.** Pot-limit Omaha bot (v33, submission 013-f0f91c94). Exact made-hand strength from lookup tables (fraction of opponent two-card combos that beat us), turned into equity against a range that tightens with every bet/call the opponents have made; position-based pot-raise preflop; ICM-style risk premium before risking the stack; adapts bluff/value thresholds to each opponent's fold rate within a table.

### 7. b03 (math_core)

**In its builder's words** (Strategy in `bots/b03/NOTES.T6.md`). Bot for T6: **013-959b0a3e** (unchanged since T5).

### 8. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T6.md`). Bot for T6: **v17, submission 013-d25698f0** (`bot/agent.py`, numpy + stdlib, ~50 µs median per decision).

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b05 | 738.4 ± 18.7 | 100% | 100% | 1 | 1–1 | 100% | · | · | · | · | · | · | · |
| b08 | 700.3 ± 19.7 | 0% | 100% | 2 | 2–3 | · | 60% | 38% | 1% | · | · | · | · |
| b06 | 696.1 ± 19.0 | 0% | 100% | 3 | 2–3 | · | 39% | 59% | 2% | · | · | · | · |
| b01 | 665.0 ± 19.6 | 0% | 90% | 4 | 4–6 | · | · | 3% | 61% | 26% | 10% | · | · |
| b02 | 657.8 ± 17.9 | 0% | 75% | 5 | 4–6 | · | · | · | 27% | 48% | 24% | 2% | · |
| b04 | 649.8 ± 19.0 | 0% | 34% | 6 | 4–7 | · | · | · | 9% | 25% | 59% | 6% | · |
| b03 | 627.1 ± 17.7 | 0% | 1% | 7 | 6–8 | · | · | · | · | 1% | 6% | 62% | 32% |
| b07 | 620.5 ± 18.8 | 0% | 0% | 8 | 7–8 | · | · | · | · | · | 2% | 30% | 67% |

## Field profile

How the bots played, from the hand logs of T1–T6 (4,275,365 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b05 | 23% | 17% | 42% | 75% | 4% | 62% | 43% |
| b08 | 25% | 17% | 39% | 66% | 7% | 56% | 59% |
| b06 | 25% | 18% | 45% | 76% | 5% | 69% | 51% |
| b01 | 21% | 15% | 41% | 78% | 4% | 49% | 32% |
| b02 | 22% | 17% | 41% | 78% | 4% | 58% | 34% |
| b04 | 26% | 17% | 35% | 68% | 8% | 71% | 69% |
| b03 | 23% | 17% | 41% | 74% | 3% | 47% | 48% |
| b07 | 30% | 20% | 44% | 67% | 5% | 61% | 35% |
| **Field** | 24% (21%–30%) | 17% (15%–20%) | 41% (35%–45%) | 73% (66%–78%) | 5% (3%–8%) | 59% (47%–71%) | 46% (32%–69%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b05 | 82% | 70% | 14% | 31% | 50% | 81% | 29% |
| b08 | 84% | 88% | 32% | 30% | 47% | 59% | 39% |
| b06 | 84% | 74% | 21% | 31% | 47% | 73% | 28% |
| b01 | 80% | 57% | 36% | 36% | 48% | 83% | 52% |
| b02 | 65% | 66% | 19% | 33% | 50% | 74% | 42% |
| b04 | 72% | 68% | 29% | 34% | 51% | 56% | 20% |
| b03 | 47% | 63% | 14% | 33% | 50% | 90% | 28% |
| b07 | 76% | 72% | 21% | 28% | 50% | 72% | 31% |
| **Field** | 74% (47%–84%) | 70% (57%–88%) | 24% (14%–36%) | 32% (28%–36%) | 49% (47%–51%) | 73% (56%–90%) | 34% (20%–52%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b05 | 36% | 29% | 27% | 18% | 17% | 22% | 40% | 74% |
| b08 | 58% | 37% | 28% | 19% | 18% | 30% | 44% | 59% |
| b06 | 48% | 32% | 27% | 19% | 19% | 26% | 39% | 68% |
| b01 | 35% | 31% | 27% | 15% | 14% | 23% | 43% | 60% |
| b02 | 36% | 27% | 25% | 19% | 18% | 22% | 34% | 64% |
| b04 | 37% | 32% | 30% | 22% | 21% | 28% | 37% | 72% |
| b03 | 42% | 31% | 25% | 19% | 18% | 25% | 39% | 72% |
| b07 | 50% | 33% | 32% | 27% | 26% | 29% | 46% | 62% |
| **Field** | 42% (35%–58%) | 31% (27%–37%) | 28% (25%–32%) | 20% (15%–27%) | 19% (14%–26%) | 25% (22%–30%) | 40% (34%–46%) | 66% (59%–74%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b05 | 42% | 43% | 41% | 47% |
| b08 | 73% | 63% | 55% | 57% |
| b06 | 72% | 50% | 47% | 49% |
| b01 | 41% | 38% | 27% | 30% |
| b02 | 55% | 34% | 29% | 29% |
| b04 | 66% | 69% | 67% | 72% |
| b03 | 50% | 48% | 47% | 50% |
| b07 | 60% | 38% | 27% | 32% |
| **Field** | 56% (41%–73%) | 47% (34%–69%) | 42% (27%–67%) | 45% (29%–72%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b05 | 3.5 bb | 73% | 80% pot | 41% |
| b08 | 3.5 bb | 76% | 50% pot | 51% |
| b06 | 3.5 bb | 76% | 80% pot | 36% |
| b01 | 3.5 bb | 69% | 60% pot | 47% |
| b02 | 3.5 bb | 75% | 80% pot | 33% |
| b04 | 3.5 bb | 77% | 80% pot | 18% |
| b03 | 3.5 bb | 76% | 70% pot | 36% |
| b07 | 3.5 bb | 79% | 60% pot | 31% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b05**: facing a steal: -0.0 ± 0.5 bb/100 (folds 75% against 72%) — within noise.
- **b08**: facing a c-bet: -0.8 ± 0.5 bb/100 (folds 88% against 67%); heads-up vs a raise: -0.0 ± 0.2 bb/100 (calls 47% against 55%) — within noise.
- **b06**: facing a river bet: -0.6 ± 0.4 bb/100 (folds 75% against 72%); facing a steal: -0.2 ± 0.5 bb/100 (folds 76% against 72%) — within noise.
- **b01**: facing an open: -1.1 ± 1.0 bb/100 (folds 88% against 85%); facing a river bet: -1.0 ± 0.5 bb/100 (calls 36% against 22%).
- **b02**: facing an open: -0.7 ± 0.9 bb/100 (folds 89% against 85%) — within noise; facing a c-bet: -0.6 ± 0.6 bb/100 (folds 66% against 70%).
- **b04**: facing an open: -1.3 ± 1.1 bb/100 (folds 79% against 86%); facing a steal: -1.0 ± 0.5 bb/100 (folds 68% against 73%).
- **b03**: facing an open: -1.1 ± 0.9 bb/100 (raises 3% against 5%); facing a steal: -0.6 ± 0.5 bb/100 (raises 4% against 7%).
- **b07**: facing a 3-bet: -1.8 ± 0.7 bb/100 (raises 3% against 9%); facing a c-bet: -1.7 ± 0.8 bb/100 (folds 72% against 69%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 73% (66%–78%) | b06 +5.8 (all fold 53%), b07 +5.4 (all fold 54%) | b04 -1.0, b03 -0.6 |
| 3-bet | 59% (47%–71%) | b04 +9.1 (all fold 49%), b08 +8.2 (all fold 52%) | b07 -1.8, b02 -0.6 |
| Preflop shove | 53% (31%–66%) | b04 +1.6 (all fold 22%), b05 +1.1 (all fold 16%) | b01 -0.6, b07 -0.4 |
| Heads-up raise | 34% (20%–52%) | b01 +0.7 (all fold 32%), b05 +0.6 (all fold 35%) | b02 -0.3, b04 -0.2 |
| C-bet | 70% (57%–88%) | b06 +11.0 (all fold 67%), b07 +10.2 (all fold 67%) | b07 -1.7, b08 -0.8 |
| River bet | 73% (60%–83%) | b07 +4.7 (all fold 68%), b03 +3.2 (all fold 69%) | b01 -1.0, b07 -0.7 |

## T1 (weight 1)

1,000 tables, 125,137 hands, 20 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 36.26 ± 2.02 | 1000 | 23% | 17% | 1 | 200 |
| 2 ≈ | b06 | 34.81 ± 2.07 | 1000 | 25% | 17% | 0 | 100 |
| 3 ≈ | b01 | 34.49 ± 2.20 | 1000 | 22% | 16% | 0 | 200 |
| 4 ≈ | b02 | 31.58 ± 1.85 | 1000 | 22% | 17% | 0 | 200 |
| 5 ≈ | b04 | 31.29 ± 2.02 | 1000 | 27% | 17% | 1 | 200 |
| 6 ≈ | b07 | 31.25 ± 2.06 | 1000 | 37% | 21% | 2 | 200 |
| 7 | b03 | 30.89 ± 1.82 | 1000 | 21% | 14% | 4 | 500 |
| 8 | b08 | 24.43 ± 1.52 | 1000 | 26% | 17% | 0 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 124,896 hands, 22 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 36.60 ± 1.98 | 1000 | 24% | 17% | 0 | 200 |
| 2 ≈ | b06 | 35.26 ± 2.06 | 1000 | 25% | 17% | 0 | 200 |
| 3 ≈ | b01 | 32.34 ± 2.09 | 1000 | 19% | 13% | 0 | 200 |
| 4 ≈ | b02 | 31.02 ± 1.89 | 1000 | 22% | 17% | 0 | 200 |
| 5 ≈ | b08 | 30.87 ± 1.86 | 1000 | 26% | 17% | 1 | 200 |
| 6 ≈ | b04 | 29.93 ± 2.03 | 1000 | 28% | 17% | 0 | 200 |
| 7 ≈ | b03 | 29.61 ± 1.84 | 1000 | 24% | 18% | 6 | 500 |
| 8 | b07 | 29.36 ± 1.93 | 1000 | 28% | 20% | 1 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 123,562 hands, 22 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 35.54 ± 1.96 | 1000 | 23% | 17% | 1 | 200 |
| 2 ≈ | b08 | 34.47 ± 2.09 | 1000 | 26% | 17% | 0 | 200 |
| 3 ≈ | b06 | 32.40 ± 2.00 | 1000 | 25% | 17% | 0 | 200 |
| 4 ≈ | b01 | 32.27 ± 1.98 | 1000 | 18% | 13% | 1 | 200 |
| 5 ≈ | b02 | 30.86 ± 1.89 | 1000 | 23% | 17% | 1 | 200 |
| 6 ≈ | b03 | 30.45 ± 1.84 | 1000 | 24% | 17% | 5 | 500 |
| 7 ≈ | b04 | 30.20 ± 2.00 | 1000 | 28% | 18% | 3 | 200 |
| 8 | b07 | 28.82 ± 1.92 | 1000 | 29% | 21% | 3 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 122,842 hands, 20 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 34.28 ± 1.89 | 1000 | 23% | 17% | 0 | 200 |
| 2 ≈ | b08 | 34.22 ± 2.13 | 1000 | 26% | 17% | 2 | 200 |
| 3 ≈ | b06 | 33.29 ± 1.96 | 1000 | 25% | 19% | 0 | 200 |
| 4 ≈ | b01 | 32.46 ± 2.12 | 1000 | 22% | 16% | 0 | 200 |
| 5 ≈ | b02 | 31.09 ± 1.91 | 1000 | 22% | 17% | 0 | 200 |
| 6 ≈ | b03 | 30.30 ± 1.81 | 1000 | 24% | 17% | 0 | 500 |
| 7 ≈ | b07 | 30.00 ± 1.95 | 1000 | 28% | 20% | 4 | 200 |
| 8 | b04 | 29.36 ± 1.91 | 1000 | 28% | 18% | 1 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 121,641 hands, 19 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 35.98 ± 1.97 | 1000 | 23% | 17% | 0 | 200 |
| 2 ≈ | b06 | 32.73 ± 1.94 | 1000 | 25% | 18% | 0 | 100 |
| 3 ≈ | b08 | 32.23 ± 2.06 | 1000 | 26% | 17% | 2 | 200 |
| 4 ≈ | b04 | 31.89 ± 1.95 | 1000 | 23% | 16% | 1 | 200 |
| 5 ≈ | b01 | 31.77 ± 2.11 | 1000 | 22% | 16% | 0 | 200 |
| 6 ≈ | b02 | 30.72 ± 1.87 | 1000 | 22% | 17% | 1 | 200 |
| 7 ≈ | b03 | 30.25 ± 1.83 | 1000 | 23% | 17% | 1 | 500 |
| 8 | b07 | 29.43 ± 1.97 | 1000 | 29% | 20% | 5 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 123,107 hands, 19 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 35.45 ± 2.04 | 1000 | 23% | 17% | 0 | 200 |
| 2 ≈ | b05 | 34.22 ± 2.00 | 1000 | 23% | 17% | 0 | 200 |
| 3 ≈ | b06 | 32.79 ± 1.96 | 1000 | 24% | 18% | 0 | 100 |
| 4 ≈ | b02 | 32.27 ± 1.91 | 1000 | 22% | 17% | 0 | 200 |
| 5 ≈ | b04 | 31.86 ± 2.00 | 1000 | 23% | 16% | 4 | 200 |
| 6 ≈ | b01 | 30.06 ± 2.01 | 1000 | 22% | 16% | 0 | 200 |
| 7 ≈ | b07 | 29.49 ± 1.97 | 1000 | 28% | 20% | 3 | 200 |
| 8 | b03 | 28.86 ± 1.81 | 1000 | 23% | 17% | 0 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 676.2 ± 50.8 (n=4) |
| math_core | 646.0 ± 37.2 (n=2) |
| model_pressure | 679.1 ± 41.6 (n=2) |

| Model | Score |
| :- | -: |
| opus | 669.4 ± 27.7 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b02 | 0/0/0/0 | 0/0/0/0 | 1/0/0/0 | 0/0/0/0 | 1/0/0/0 | 0/0/0/0 |
| b03 | 4/0/0/0 | 6/0/0/0 | 2/0/0/3 | 0/0/0/0 | 1/0/0/0 | 0/0/0/0 |
| b04 | 1/0/0/0 | 0/0/0/0 | 3/0/0/0 | 1/0/0/0 | 1/0/0/0 | 4/0/0/0 |
| b05 | 1/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b06 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b07 | 2/0/0/0 | 1/0/0/0 | 3/0/0/0 | 4/0/0/0 | 5/0/0/0 | 3/0/0/0 |
| b08 | 0/0/0/0 | 1/0/0/0 | 0/0/0/0 | 2/0/0/0 | 2/0/0/0 | 0/0/0/0 |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 5 | 8 of 8 |
| 10 | 8 of 8 |
| 20 | 8 of 8 |
| 40 | 8 of 8 |
| 60 | 8 of 8 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 54 | 44 | finished | $30.78 |
| b02 | 51 | 41 | finished | $26.09 |
| b03 | 44 | 34 | finished | $23.95 |
| b04 | 49 | 39 | finished | $24.92 |
| b05 | 46 | 36 | finished | $21.36 |
| b06 | 48 | 38 | finished | $25.44 |
| b07 | 40 | 30 | finished | $23.16 |
| b08 | 43 | 33 | finished | $22.40 |

## Builder failures

None.

## Cost

Total $198.09; per builder: b01 $30.78, b02 $26.09, b03 $23.95, b04 $24.92, b05 $21.36, b06 $25.44, b07 $23.16, b08 $22.40

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 61% at the first reading, 46% at the last. It counts everything on the same login, including your own sessions.
