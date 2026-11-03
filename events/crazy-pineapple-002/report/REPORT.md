# Report: crazy-pineapple-002

## Event card

- **Variant:** crazy_pineapple: No-limit hold'em with 3 hole cards; everyone discards one after the flop betting.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 3996735514

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b02 | opus | model_pressure | 719.0 | 35.9 | 33.5 | 34.2 | 33.5 | 35.0 | 34.1 |
| 2 | b08 | opus | free choice | 710.3 | 33.6 | 33.8 | 32.1 | 32.6 | 34.6 | 34.9 |
| 3 | b01 | opus | free choice | 696.9 | 35.3 | 34.4 | 33.4 | 33.9 | 33.7 | 31.4 |
| 4 | b07 | opus | free choice | 696.2 | 37.5 | 35.3 | 33.9 | 34.3 | 32.3 | 31.3 |
| 5 | b04 | opus | free choice | 679.5 | 33.3 | 33.1 | 33.0 | 32.6 | 30.8 | 32.8 |
| 6 | b03 | opus | math_core | 643.0 | 29.5 | 29.3 | 30.2 | 29.4 | 31.2 | 31.8 |
| 7 | b05 | opus | model_pressure | 623.3 | 26.3 | 28.6 | 30.1 | 29.9 | 29.4 | 30.5 |
| 8 | b06 | opus | math_core | 586.9 | 23.5 | 27.0 | 28.1 | 28.8 | 28.1 | 28.2 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b02 | 13% | 52% | 40% | 17% | 25% | 19% | 2.9 |
| 2 | b08 | 14% | 51% | 39% | 23% | 30% | 19% | 1.6 |
| 3 | b01 | 12% | 43% | 43% | 22% | 21% | 17% | 5.3 |
| 4 | b07 | 14% | 51% | 39% | 20% | 19% | 16% | 2.8 |
| 5 | b04 | 15% | 59% | 36% | 24% | 22% | 16% | 2.3 |
| 6 | b03 | 12% | 48% | 36% | 29% | 24% | 16% | 2.6 |
| 7 | b05 | 10% | 46% | 35% | 28% | 23% | 18% | 1.5 |
| 8 | b06 | 11% | 50% | 32% | 36% | 22% | 15% | 1.7 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b02 (model_pressure)

**In its builder's words** (Strategy in `bots/b02/NOTES.T6.md`). A precomputed equity table for 3-card starting hands drives the preflop ranges. It covers all 1755 suit-isomorphic classes, simulated with realistic flop discards. Every all-in decision (shoves, call-offs, postflop commits) is decided by ICM: exact Malmuth-Harville on the real stacks when 5 or fewer players remain, a precomputed table otherwise. …

### 2. b08 (free choice)

**In its builder's words** (Strategy in `bots/b08/NOTES.T6.md`). Table-driven bot (submission 008-83010431 = tools/v9). Preflop uses precomputed Monte-Carlo equities of every 3-card crazy-pineapple hand (vs 1..7 random opponents, each player keeping the 2 cards that make the best flop hand) plus heads-up equity vs top-r% ranges for calling raises/shoves. …

### 3. b01 (free choice)

**In its builder's words** (Strategy in `bots/b01/NOTES.T6.md`). Preflop uses precomputed 3-card equities (vs random and vs top-X% ranges). Short-stack spots use an explicit push/fold EV model, with exact ICM when 3-4 players remain. After the flop, a fast Monte Carlo (lookup-table evaluator, ~1 µs/eval; wall budget 0.34 ms after the flop, 0.38 ms for the discard) estimates equity, then discounts it against the bettor's likely range.

### 4. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T6.md`). Tight-aggressive equity bot. Preflop uses a precomputed Monte Carlo equity table for every 3-card starting hand (vs 1 and vs 3 random 3-card opponents); postflop runs a time-boxed (~0.30 ms) Monte Carlo against an opponent who was dealt 3 cards and kept his best 2 on the flop, then compares range-adjusted equity with pot odds. …

### 5. b04 (free choice)

**In its builder's words** (Strategy in `bots/b04/NOTES.T6.md`). A tight-aggressive crazy-pineapple bot that uses lookup tables, not simulation. Preflop it reads precomputed equities for all 1,755 three-card hand classes (against random hands and against top-X% ranges). Postflop it scores the hand by made-hand category plus draw outs, and it compares estimated equity to pot odds. …

### 6. b03 (math_core)

**In its builder's words** (Strategy in `bots/b03/NOTES.T6.md`). Math-first bot. Preflop uses precomputed equities for every 3-card crazy-pineapple hand (vs 1/2/4 random hands and vs top-10/25/50% ranges, Monte Carlo offline, shipped as JSON) under the keep-two rule: a hand's showdown value is the best of its three 2-card subsets with the board (since v13; before that the tables let all 3 hole cards play, which badly overrated suited/connected 3-card hands). …

### 7. b05 (model_pressure)

**In its builder's words** (Strategy in `bots/b05/NOTES.T6.md`). Before the flop the bot looks up a precomputed 3-card equity table (`bot/pre3.json`). It covers all 1755 suit-isomorphic classes and was simulated with a realistic after-flop discard, with equity against random hands and against top-5/10/20/35/55% ranges. Short stacks play EV-based push/fold, with exact ICM (Malmuth-Harville, as kit/icm.py) once ≤5 players remain. …

### 8. b06 (math_core)

**In its builder's words** (Strategy in `bots/b06/NOTES.T6.md`). Math-first bot. Preflop decisions use a precomputed table of all 1755 canonical 3-card starting hands (equity vs 1..7 random hands, percentile rank, and equity vs top-X% ranges). Postflop it runs a time-budgeted Monte Carlo (~0.4 ms) of its equity vs random hands and compares to pot odds plus a margin that grows with bet size and shrinks vs aggressive bettors.

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b02 | 719.0 ± 19.0 | 68% | 100% | 1 | 1–3 | 68% | 25% | 5% | 2% | · | · | · | · |
| b08 | 710.3 ± 19.8 | 27% | 100% | 2 | 1–4 | 27% | 47% | 18% | 7% | 1% | · | · | · |
| b01 | 696.9 ± 18.2 | 3% | 100% | 3 | 2–5 | 3% | 14% | 38% | 37% | 9% | · | · | · |
| b07 | 696.2 ± 18.7 | 2% | 100% | 4 | 2–5 | 2% | 14% | 34% | 39% | 11% | · | · | · |
| b04 | 679.5 ± 19.1 | 0% | 99% | 5 | 3–5 | · | 1% | 6% | 14% | 78% | 1% | · | · |
| b03 | 643.0 ± 19.1 | 0% | 1% | 6 | 6–7 | · | · | · | · | 1% | 91% | 8% | · |
| b05 | 623.3 ± 17.7 | 0% | 0% | 7 | 6–7 | · | · | · | · | · | 8% | 91% | 1% |
| b06 | 586.9 ± 18.6 | 0% | 0% | 8 | 8–8 | · | · | · | · | · | · | 1% | 99% |

## Field profile

How the bots played, from the hand logs of T1–T6 (4,447,905 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b02 | 25% | 19% | 50% | 75% | 3% | 85% | 16% |
| b08 | 30% | 19% | 51% | 56% | 3% | 83% | 20% |
| b01 | 21% | 17% | 43% | 87% | 3% | 86% | 14% |
| b07 | 19% | 16% | 43% | 84% | 5% | 74% | 17% |
| b04 | 22% | 16% | 40% | 76% | 5% | 77% | 26% |
| b03 | 24% | 16% | 43% | 74% | 3% | 62% | 16% |
| b05 | 23% | 18% | 53% | 82% | 4% | 84% | 15% |
| b06 | 22% | 15% | 38% | 79% | 4% | 81% | 17% |
| **Field** | 23% (19%–30%) | 17% (15%–19%) | 45% (38%–53%) | 77% (56%–87%) | 4% (3%–5%) | 80% (62%–86%) | 17% (14%–26%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b02 | 78% | 71% | 17% | 39% | 52% | 86% | 48% |
| b08 | 65% | 58% | 26% | 38% | 55% | 66% | 35% |
| b01 | 61% | 85% | 52% | 42% | 49% | 87% | 55% |
| b07 | 81% | 64% | 48% | 50% | 49% | 83% | 57% |
| b04 | 63% | 68% | 46% | 48% | 50% | 78% | 35% |
| b03 | 42% | 61% | 22% | 40% | 47% | 71% | 69% |
| b05 | 74% | 28% | 47% | 49% | 48% | 95% | 74% |
| b06 | 67% | 22% | 48% | 49% | 41% | 71% | 63% |
| **Field** | 67% (42%–81%) | 57% (22%–85%) | 37% (17%–52%) | 44% (38%–50%) | 49% (41%–55%) | 79% (66%–95%) | 54% (35%–74%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b02 | 28% | 24% | 29% | 24% | 22% | 25% | 37% | 63% |
| b08 | 42% | 33% | 32% | 27% | 25% | 33% | 45% | 58% |
| b01 | 28% | 23% | 23% | 18% | 18% | 22% | 26% | 61% |
| b07 | 34% | 27% | 20% | 14% | 14% | 21% | 34% | 59% |
| b04 | 39% | 26% | 24% | 18% | 17% | 23% | 37% | 64% |
| b03 | 32% | 25% | 25% | 21% | 20% | 25% | 34% | 49% |
| b05 | 27% | 24% | 27% | 19% | 19% | 24% | 35% | 58% |
| b06 | 33% | 23% | 22% | 20% | 19% | 22% | 31% | 51% |
| **Field** | 32% (27%–42%) | 26% (23%–33%) | 25% (20%–32%) | 20% (14%–27%) | 19% (14%–25%) | 25% (21%–33%) | 35% (26%–45%) | 58% (49%–64%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b02 | 13% | 14% | 18% | 30% |
| b08 | 20% | 18% | 18% | 28% |
| b01 | 21% | 12% | 11% | 15% |
| b07 | 27% | 15% | 13% | 17% |
| b04 | 43% | 24% | 20% | 24% |
| b03 | 26% | 13% | 11% | 17% |
| b05 | 18% | 12% | 14% | 21% |
| b06 | 22% | 14% | 16% | 19% |
| **Field** | 22% (13%–43%) | 15% (12%–24%) | 15% (11%–20%) | 21% (15%–30%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b02 | 2.5 bb | 52% | 50% pot | 57% |
| b08 | 2.5 bb | 46% | 50% pot | 42% |
| b01 | 2.5 bb | 51% | 80% pot | 34% |
| b07 | 2 bb | 53% | 50% pot | 29% |
| b04 | 2.5 bb | 47% | 60% pot | 58% |
| b03 | 2.5 bb | 64% | 60% pot | 51% |
| b05 | 2.5 bb | 49% | 50% pot | 33% |
| b06 | 2.5 bb | 47% | 60% pot | 51% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b02**: facing a 3-bet: -0.9 ± 0.5 bb/100 (folds 85% against 79%); facing a shove: -0.2 ± 0.5 bb/100 (folds 83% against 81%) — within noise.
- **b08**: facing a shove: -0.3 ± 0.4 bb/100 (folds 79% against 82%) — within noise; heads-up vs a raise: -0.1 ± 0.2 bb/100 (calls 63% against 37%) — within noise.
- **b01**: facing a steal: -0.8 ± 0.5 bb/100 (folds 87% against 75%); heads-up vs a raise: -0.0 ± 0.2 bb/100 (raises 3% against 6%) — within noise.
- **b07**: facing a c-bet: -0.2 ± 0.3 bb/100 (folds 64% against 57%) — within noise.
- **b04**: no spot below the field.
- **b03**: facing a 3-bet: -1.8 ± 0.8 bb/100 (folds 62% against 82%); facing a c-bet: -0.9 ± 0.8 bb/100 (folds 61% against 56%).
- **b05**: facing a steal: -0.9 ± 0.5 bb/100 (folds 82% against 76%); facing a c-bet: -0.8 ± 0.6 bb/100 (folds 28% against 59%).
- **b06**: facing a river bet: -10.3 ± 1.0 bb/100 (folds 45% against 62%); facing an open: -5.0 ± 1.3 bb/100 (folds 84% against 88%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 77% (56%–87%) | b02 +7.6 (all fold 63%), b08 +7.4 (all fold 64%) | b06 -1.0, b05 -0.9 |
| 3-bet | 80% (62%–86%) | b07 +6.3 (all fold 71%), b04 +5.7 (all fold 73%) | b03 -1.8, b02 -0.9 |
| Preflop shove | 82% (72%–86%) | b08 +5.5 (all fold 66%), b04 +4.6 (all fold 69%) | b05 -0.7, b03 -0.4 |
| Heads-up raise | 54% (35%–74%) | b02 +0.5 (all fold 49%), b04 +0.5 (all fold 61%) | b03 -0.2, b08 -0.1 |
| C-bet | 57% (22%–85%) | b01 +8.8 (all fold 55%), b07 +8.3 (all fold 59%) | b06 -3.1, b03 -0.9 |
| River bet | 59% (41%–78%) | b08 +10.4 (all fold 55%), b03 +8.1 (all fold 49%) | b06 -10.3, b05 -0.6 |

## T1 (weight 1)

1,000 tables, 123,782 hands, 31 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b07 | 37.49 ± 2.07 | 1000 | 20% | 17% | 0 | 495 |
| 2 ≈ | b02 | 35.91 ± 1.94 | 1000 | 24% | 19% | 0 | 500 |
| 3 ≈ | b01 | 35.34 ± 1.84 | 1000 | 20% | 16% | 0 | 500 |
| 4 ≈ | b08 | 33.59 ± 1.99 | 1000 | 34% | 19% | 0 | 300 |
| 5 ≈ | b04 | 33.30 ± 2.07 | 1000 | 22% | 16% | 0 | 100 |
| 6 ≈ | b03 | 29.50 ± 1.94 | 1000 | 26% | 17% | 0 | 730 |
| 7 ≈ | b05 | 26.32 ± 1.77 | 1000 | 24% | 20% | 0 | 300 |
| 8 | b06 | 23.55 ± 1.93 | 1000 | 25% | 18% | 0 | 704 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 125,878 hands, 30 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b07 | 35.34 ± 2.04 | 1000 | 20% | 17% | 0 | 500 |
| 2 ≈ | b01 | 34.41 ± 1.91 | 1000 | 19% | 15% | 0 | 500 |
| 3 ≈ | b08 | 33.78 ± 2.03 | 1000 | 29% | 18% | 0 | 300 |
| 4 ≈ | b02 | 33.53 ± 1.86 | 1000 | 26% | 20% | 0 | 500 |
| 5 ≈ | b04 | 33.09 ± 2.07 | 1000 | 22% | 16% | 0 | 100 |
| 6 ≈ | b03 | 29.30 ± 1.97 | 1000 | 23% | 17% | 0 | 719 |
| 7 ≈ | b05 | 28.58 ± 1.91 | 1000 | 23% | 19% | 0 | 300 |
| 8 | b06 | 26.97 ± 1.87 | 1000 | 22% | 15% | 0 | 577 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 126,293 hands, 31 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 34.16 ± 1.96 | 1000 | 26% | 19% | 0 | 500 |
| 2 ≈ | b07 | 33.94 ± 1.97 | 1000 | 19% | 16% | 0 | 500 |
| 3 ≈ | b01 | 33.40 ± 1.93 | 1000 | 21% | 17% | 0 | 500 |
| 4 ≈ | b04 | 32.98 ± 2.06 | 1000 | 22% | 16% | 0 | 100 |
| 5 ≈ | b08 | 32.08 ± 2.00 | 1000 | 30% | 19% | 0 | 300 |
| 6 ≈ | b03 | 30.16 ± 1.94 | 1000 | 22% | 16% | 0 | 712 |
| 7 ≈ | b05 | 30.14 ± 1.87 | 1000 | 23% | 18% | 0 | 300 |
| 8 | b06 | 28.13 ± 1.97 | 1000 | 21% | 15% | 0 | 573 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 126,026 hands, 33 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b07 | 34.29 ± 1.98 | 1000 | 19% | 16% | 0 | 500 |
| 2 ≈ | b01 | 33.92 ± 1.94 | 1000 | 22% | 18% | 1 | 500 |
| 3 ≈ | b02 | 33.48 ± 1.83 | 1000 | 26% | 19% | 0 | 500 |
| 4 ≈ | b04 | 32.62 ± 2.07 | 1000 | 22% | 16% | 0 | 100 |
| 5 ≈ | b08 | 32.60 ± 2.06 | 1000 | 30% | 19% | 0 | 300 |
| 6 ≈ | b05 | 29.85 ± 1.97 | 1000 | 23% | 18% | 0 | 300 |
| 7 ≈ | b03 | 29.41 ± 1.86 | 1000 | 23% | 16% | 0 | 750 |
| 8 | b06 | 28.83 ± 1.97 | 1000 | 21% | 15% | 0 | 590 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 125,755 hands, 30 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 35.04 ± 2.00 | 1000 | 25% | 19% | 0 | 500 |
| 2 ≈ | b08 | 34.59 ± 2.01 | 1000 | 30% | 20% | 0 | 300 |
| 3 ≈ | b01 | 33.69 ± 2.00 | 1000 | 22% | 18% | 0 | 500 |
| 4 ≈ | b07 | 32.28 ± 1.94 | 1000 | 19% | 16% | 0 | 500 |
| 5 ≈ | b03 | 31.16 ± 2.00 | 1000 | 23% | 16% | 0 | 713 |
| 6 ≈ | b04 | 30.75 ± 2.00 | 1000 | 22% | 16% | 0 | 100 |
| 7 ≈ | b05 | 29.41 ± 1.76 | 1000 | 21% | 16% | 0 | 300 |
| 8 | b06 | 28.09 ± 1.95 | 1000 | 21% | 14% | 0 | 588 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 125,815 hands, 30 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 34.92 ± 2.09 | 1000 | 30% | 20% | 0 | 300 |
| 2 ≈ | b02 | 34.06 ± 1.98 | 1000 | 26% | 20% | 0 | 500 |
| 3 ≈ | b04 | 32.80 ± 2.00 | 1000 | 22% | 16% | 0 | 100 |
| 4 ≈ | b03 | 31.83 ± 2.03 | 1000 | 23% | 16% | 0 | 739 |
| 5 ≈ | b01 | 31.40 ± 1.91 | 1000 | 22% | 18% | 0 | 500 |
| 6 ≈ | b07 | 31.27 ± 1.94 | 1000 | 19% | 16% | 0 | 500 |
| 7 ≈ | b05 | 30.49 ± 1.85 | 1000 | 21% | 16% | 0 | 300 |
| 8 | b06 | 28.21 ± 1.91 | 1000 | 21% | 16% | 0 | 599 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 695.7 ± 12.4 (n=4) |
| math_core | 614.9 ± 55.0 (n=2) |
| model_pressure | 671.2 ± 93.8 (n=2) |

| Model | Score |
| :- | -: |
| opus | 669.4 ± 32.4 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b02 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b03 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b04 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b05 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b06 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b07 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b08 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 5 | 4 of 8 |
| 10 | 8 of 8 |
| 20 | 8 of 8 |
| 40 | 8 of 8 |
| 60 | 8 of 8 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 59 | 52 | finished | $30.13 |
| b02 | 37 | 30 | finished | $19.08 |
| b03 | 42 | 35 | finished | $24.43 |
| b04 | 40 | 33 | finished | $18.13 |
| b05 | 41 | 34 | finished | $18.01 |
| b06 | 40 | 33 | finished | $18.04 |
| b07 | 42 | 35 | finished | $21.72 |
| b08 | 47 | 40 | finished | $19.19 |

## Builder failures

None.

## Cost

Total $168.73; per builder: b01 $30.13, b02 $19.08, b03 $24.43, b04 $18.13, b05 $18.01, b06 $18.04, b07 $21.72, b08 $19.19

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 24% at the first reading, 60% at the last. It counts everything on the same login, including your own sessions.
