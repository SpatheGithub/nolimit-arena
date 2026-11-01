# Report: crazy-pineapple-001

## Event card

- **Variant:** crazy_pineapple: No-limit hold'em with 3 hole cards; everyone discards one after the flop betting.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 3996735514
- **Computer asleep:** 130 of 136 builder-window minutes, measured afterwards from the macOS power log; the builders lost that time

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b08 | opus | free choice | 792.7 | 37.2 | 37.9 | 38.0 | 38.6 | 36.8 | 37.9 |
| 2 | b05 | opus | model_pressure | 716.7 | 33.4 | 32.2 | 34.8 | 34.8 | 34.6 | 33.7 |
| 3 | b06 | opus | math_core | 656.5 | no bot | 31.6 | 34.1 | 30.9 | 33.2 | 33.5 |
| 4 | b07 | opus | free choice | 618.9 | no bot | no bot | 35.4 | 36.3 | 34.1 | 32.8 |
| 5 | b04 | opus | free choice | 574.8 | 25.1 | 24.1 | 28.6 | 28.0 | 26.8 | 28.3 |
| 6 | b02 | opus | model_pressure | 561.9 | no bot | no bot | 24.7 | 32.3 | 32.6 | 32.6 |
| 7 | b03 | opus | math_core | 517.5 | no bot | no bot | 30.8 | 25.9 | 28.9 | 29.4 |
| 8 | b01 | opus | free choice | 498.2 | no bot | no bot | 28.6 | 28.1 | 28.1 | 26.6 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b08 | 14% | 44% | 47% | 16% | 20% | 16% | 1.5 |
| 2 | b05 | 14% | 53% | 40% | 23% | 25% | 19% | 1.6 |
| 3 | b06 | 12% | 49% | 39% | 23% | 25% | 19% | 1.4 |
| 4 | b07 | 14% | 50% | 42% | 23% | 25% | 19% | 1.1 |
| 5 | b04 | 11% | 54% | 30% | 36% | 24% | 20% | 1.5 |
| 6 | b02 | 13% | 54% | 35% | 28% | 24% | 20% | 1.3 |
| 7 | b03 | 10% | 46% | 34% | 27% | 20% | 15% | 1.4 |
| 8 | b01 | 10% | 51% | 32% | 27% | 22% | 16% | 1.8 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b08 (free choice)

**In its builder's words** (Strategy in `bots/b08/NOTES.T6.md`). A tight-aggressive rules bot. Before the flop it ranks the 3-card hand with a precomputed table. After the flop it scores the made hand and draws, and when stacks are short it switches to push/fold. Every decision is a table lookup plus arithmetic (p99 about 100 µs), so it never times out. It scores by staying out of marginal pots, betting its strong hands and surviving to the higher places. …

### 3. b06 (math_core)

**In its builder's words** (Strategy in `bots/b06/NOTES.T6.md`). A fast rules bot that runs in about 25 µs per decision. Before the flop it ranks hands by percentile among all 22,100 three-card starting hands. After the flop it estimates equity from the made hand plus outs. Bet and call sizes come from pot odds, a discount for multiway pots and per-seat raise frequencies. Short stacks play push/fold.

### 4. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T6.md`). Rule-based bot: preflop percentile table over all 22,100 three-card hands (Chen-score of best 2-card subset plus small credit for the other pairs), position/stack-aware open/3-bet/call thresholds, push/fold under 13 BB; postflop a hand-strength heuristic (made-hand class relative to the board, kicker, board texture, draw equity) mapped to an approximate win probability, discounted for multiway pots and compared to po. …

### 6. b02 (model_pressure)

**In its builder's words** (Strategy in `bots/b02/NOTES.T6.md`). Rule-based tight-aggressive bot. Preflop uses a 3-card strength score built from hold'em equity tables (best 2-card subset + bonus for the other subsets); postflop uses a fast made-hand/draw heuristic that estimates equity, discounted for multiway pots and bet size, compared against pot odds. Short stacks switch to push/fold.

### 7. b03 (math_core)

**In its builder's words** (Strategy in `bots/b03/NOTES.T6.md`). A tight-aggressive bot built on precomputed math. Before the flop it looks up each 3-card hand in a table of equities (1755 suit classes, Monte Carlo, oracle discard) and plays by its percentile. After the flop it runs a small timed Monte Carlo against random hands, discounts that for bet size, and compares it with the pot odds. …

### 8. b01 (free choice)

**In its builder's words** (Strategy in `bots/b01/NOTES.T6.md`). Preflop the bot ranks every 3-card hand with a Chen-score heuristic (best two-card pair plus a little credit for the other pairs) and plays by percentile ranges that depend on seat. Postflop it runs a Monte Carlo equity estimate with a time budget (about 0.3 ms) against random hands, using a fast table-driven evaluator stored in bot/evtab.bin. …

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b08 | 792.7 ± 18.1 | 100% | 100% | 1 | 1–1 | 100% | · | · | · | · | · | · | · |
| b05 | 716.7 ± 19.7 | 0% | 100% | 2 | 2–2 | · | 100% | · | · | · | · | · | · |
| b06 | 656.5 ± 18.2 | 0% | 100% | 3 | 3–3 | · | · | 100% | · | · | · | · | · |
| b07 | 618.9 ± 18.7 | 0% | 100% | 4 | 4–4 | · | · | · | 100% | · | · | · | · |
| b04 | 574.8 ± 19.0 | 0% | 80% | 5 | 5–6 | · | · | · | · | 80% | 20% | · | · |
| b02 | 561.9 ± 18.0 | 0% | 20% | 6 | 5–6 | · | · | · | · | 20% | 80% | · | · |
| b03 | 517.5 ± 17.3 | 0% | 0% | 7 | 7–8 | · | · | · | · | · | · | 93% | 7% |
| b01 | 498.2 ± 17.0 | 0% | 0% | 8 | 7–8 | · | · | · | · | · | · | 7% | 93% |

## Field profile

How the bots played, from the hand logs of T1–T6 (2,800,338 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b08 | 20% | 16% | 30% | 84% | 5% | 77% | 21% |
| b05 | 25% | 19% | 37% | 75% | 5% | 53% | 29% |
| b06 | 25% | 19% | 41% | 79% | 4% | 78% | 16% |
| b07 | 25% | 19% | 39% | 80% | 5% | 68% | 22% |
| b04 | 24% | 20% | 37% | 79% | 8% | 50% | 29% |
| b02 | 24% | 20% | 39% | 81% | 7% | 61% | 37% |
| b03 | 20% | 15% | 33% | 83% | 3% | 69% | 21% |
| b01 | 22% | 16% | 35% | 79% | 4% | 73% | 20% |
| **Field** | 23% (20%–25%) | 18% (15%–20%) | 36% (30%–41%) | 80% (75%–84%) | 5% (3%–8%) | 65% (50%–78%) | 24% (16%–37%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b08 | 73% | 24% | 56% | 64% | 54% | 42% | 79% |
| b05 | 73% | 45% | 63% | 58% | 55% | 44% | 68% |
| b06 | 73% | 46% | 74% | 60% | 51% | 62% | 82% |
| b07 | 69% | 48% | 75% | 63% | 53% | 53% | 78% |
| b04 | 62% | 39% | 73% | 65% | 45% | 52% | 75% |
| b02 | 68% | 45% | 81% | 65% | 49% | 42% | 71% |
| b03 | 70% | 17% | 75% | 69% | 45% | 47% | 75% |
| b01 | 79% | 7% | 73% | 68% | 44% | 51% | 74% |
| **Field** | 71% (62%–79%) | 37% (7%–48%) | 71% (56%–81%) | 63% (58%–69%) | 50% (44%–55%) | 49% (42%–62%) | 76% (68%–82%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b08 | 35% | 23% | 21% | 17% | 15% | 18% | 24% | 29% |
| b05 | 39% | 29% | 27% | 23% | 20% | 24% | 30% | 33% |
| b06 | 37% | 27% | 27% | 23% | 20% | 23% | 32% | 36% |
| b07 | 42% | 31% | 27% | 23% | 20% | 23% | 31% | 34% |
| b04 | 37% | 27% | 26% | 23% | 21% | 23% | 30% | 32% |
| b02 | 67% | 29% | 22% | 23% | 21% | 24% | 29% | 28% |
| b03 | 37% | 25% | 21% | 18% | 16% | 19% | 26% | 30% |
| b01 | 45% | 25% | 23% | 20% | 17% | 21% | 27% | 34% |
| **Field** | 39% (35%–67%) | 27% (23%–31%) | 24% (21%–27%) | 21% (17%–23%) | 19% (15%–21%) | 22% (18%–24%) | 28% (24%–32%) | 32% (28%–36%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b08 | 28% | 17% | 15% | 25% |
| b05 | 58% | 29% | 22% | 27% |
| b06 | 19% | 12% | 14% | 20% |
| b07 | 26% | 18% | 20% | 24% |
| b04 | 30% | 23% | 23% | 36% |
| b02 | 84% | 41% | 29% | 32% |
| b03 | 43% | 21% | 14% | 16% |
| b01 | 44% | 20% | 15% | 17% |
| **Field** | 35% (19%–84%) | 22% (12%–41%) | 19% (14%–29%) | 26% (16%–36%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b08 | 2.5 bb | 58% | 80% pot | 35% |
| b05 | 2.5 bb | 76% | 50% pot | 45% |
| b06 | 2.5 bb | 60% | 70% pot | 63% |
| b07 | 2.5 bb | 60% | 70% pot | 38% |
| b04 | 2.5 bb | 86% | 70% pot | 56% |
| b02 | 2.5 bb | 71% | 50% pot | 33% |
| b03 | 2.5 bb | 85% | 70% pot | 62% |
| b01 | 2.5 bb | 63% | 70% pot | 67% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b08**: no spot below the field.
- **b05**: facing a 3-bet: -0.3 ± 1.6 bb/100 (calls 39% against 21%) — within noise.
- **b06**: facing a river bet: -0.5 ± 1.8 bb/100 (calls 74% against 70%) — within noise; facing a steal: -0.2 ± 1.3 bb/100 (calls 17% against 14%) — within noise.
- **b07**: heads-up vs a raise: -0.3 ± 0.3 bb/100 (folds 78% against 75%) — within noise.
- **b04**: facing a shove: -10.9 ± 2.1 bb/100 (folds 66% against 75%); facing a 3-bet: -7.6 ± 2.0 bb/100 (folds 50% against 67%).
- **b02**: facing a steal: -0.8 ± 1.3 bb/100 (calls 11% against 15%) — within noise; facing a c-bet: -0.7 ± 1.7 bb/100 (folds 45% against 36%) — within noise.
- **b03**: facing a river bet: -7.8 ± 2.2 bb/100 (folds 16% against 25%); facing a c-bet: -5.6 ± 1.9 bb/100 (folds 17% against 39%).
- **b01**: facing a river bet: -11.7 ± 2.2 bb/100 (folds 18% against 24%); facing a c-bet: -4.4 ± 2.0 bb/100 (folds 7% against 40%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 80% (75%–84%) | b07 +10.0 (all fold 67%), b05 +8.9 (all fold 67%) | b01 -4.0, b03 -2.3 |
| 3-bet | 65% (50%–78%) | b01 +9.3 (all fold 56%), b07 +8.2 (all fold 57%) | b04 -7.6, b05 -0.3 |
| Preflop shove | 73% (59%–84%) | b07 +7.6 (all fold 58%), b03 +7.4 (all fold 57%) | b04 -10.9, b02 -0.2 |
| Heads-up raise | 76% (68%–82%) | b07 +1.8 (all fold 76%), b08 +1.4 (all fold 77%) | b07 -0.3, b03 -0.1 |
| C-bet | 37% (7%–48%) | b02 +12.3 (all fold 33%), b07 +12.0 (all fold 32%) | b03 -5.6, b01 -4.4 |
| River bet | 24% (15%–40%) | b07 +20.2 (all fold 20%), b05 +18.9 (all fold 21%) | b01 -11.7, b03 -7.8 |

## T1 (weight 1)

1,000 tables, 125,517 hands, 14 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 37.16 ± 1.97 | 1000 | 19% | 16% | 0 | 100 |
| 2 | b05 | 33.42 ± 2.01 | 1000 | 25% | 19% | 0 | 50 |
| 3 | b04 | 25.09 ± 1.85 | 1000 | 24% | 20% | 0 | 402 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 125,830 hands, 15 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 | b08 | 37.87 ± 1.92 | 1000 | 19% | 16% | 0 | 100 |
| 2 ≈ | b05 | 32.18 ± 1.96 | 1000 | 25% | 19% | 0 | 100 |
| 3 | b06 | 31.62 ± 1.92 | 1000 | 24% | 19% | 0 | 50 |
| 4 | b04 | 24.12 ± 1.87 | 1000 | 24% | 19% | 3 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 118,457 hands, 16 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 38.02 ± 1.91 | 1000 | 20% | 16% | 0 | 100 |
| 2 ≈ | b07 | 35.36 ± 2.02 | 1000 | 25% | 19% | 0 | 200 |
| 3 ≈ | b05 | 34.76 ± 1.98 | 1000 | 25% | 18% | 0 | 100 |
| 4 ≈ | b06 | 34.15 ± 1.97 | 1000 | 25% | 19% | 0 | 50 |
| 5 ≈ | b03 | 30.77 ± 1.83 | 1000 | 20% | 14% | 0 | 500 |
| 6 ≈ | b04 | 28.62 ± 2.00 | 1000 | 25% | 19% | 1 | 442 |
| 7 | b01 | 28.60 ± 1.83 | 1000 | 22% | 16% | 0 | 500 |
| 8 | b02 | 24.73 ± 2.04 | 1000 | 47% | 36% | 0 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 124,189 hands, 17 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 38.62 ± 2.00 | 1000 | 20% | 16% | 0 | 100 |
| 2 ≈ | b07 | 36.29 ± 2.07 | 1000 | 25% | 19% | 0 | 200 |
| 3 ≈ | b05 | 34.78 ± 2.06 | 1000 | 25% | 19% | 0 | 100 |
| 4 ≈ | b02 | 32.28 ± 1.92 | 1000 | 19% | 16% | 0 | 100 |
| 5 ≈ | b06 | 30.95 ± 1.90 | 1000 | 25% | 19% | 0 | 50 |
| 6 ≈ | b01 | 28.14 ± 1.87 | 1000 | 22% | 16% | 0 | 448 |
| 7 ≈ | b04 | 27.99 ± 1.98 | 1000 | 24% | 20% | 1 | 500 |
| 8 | b03 | 25.95 ± 1.77 | 1000 | 20% | 15% | 0 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 124,318 hands, 16 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 36.77 ± 1.95 | 1000 | 20% | 16% | 0 | 100 |
| 2 ≈ | b05 | 34.62 ± 2.04 | 1000 | 25% | 19% | 0 | 100 |
| 3 ≈ | b07 | 34.11 ± 2.01 | 1000 | 25% | 19% | 0 | 200 |
| 4 ≈ | b06 | 33.17 ± 1.98 | 1000 | 25% | 20% | 0 | 50 |
| 5 ≈ | b02 | 32.56 ± 1.98 | 1000 | 19% | 16% | 1 | 100 |
| 6 ≈ | b03 | 28.94 ± 1.87 | 1000 | 20% | 15% | 1 | 500 |
| 7 ≈ | b01 | 28.05 ± 1.84 | 1000 | 22% | 16% | 2 | 500 |
| 8 | b04 | 26.79 ± 1.96 | 1000 | 25% | 20% | 0 | 478 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 123,639 hands, 16 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 | b08 | 37.91 ± 1.96 | 1000 | 20% | 16% | 0 | 100 |
| 2 ≈ | b05 | 33.73 ± 2.09 | 1000 | 24% | 19% | 1 | 100 |
| 3 ≈ | b06 | 33.53 ± 1.96 | 1000 | 25% | 19% | 0 | 50 |
| 4 ≈ | b07 | 32.84 ± 2.02 | 1000 | 25% | 19% | 1 | 200 |
| 5 ≈ | b02 | 32.64 ± 1.93 | 1000 | 19% | 16% | 0 | 100 |
| 6 ≈ | b03 | 29.45 ± 1.87 | 1000 | 20% | 15% | 0 | 500 |
| 7 ≈ | b04 | 28.29 ± 2.00 | 1000 | 23% | 20% | 1 | 300 |
| 8 | b01 | 26.60 ± 1.80 | 1000 | 22% | 16% | 1 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 621.2 ± 122.3 (n=4) |
| math_core | 587.0 ± 136.3 (n=2) |
| model_pressure | 639.3 ± 151.6 (n=2) |

| Model | Score |
| :- | -: |
| opus | 617.2 ± 69.9 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | — | — | 0/0/0/0 | 0/0/0/0 | 0/0/0/2 | 0/0/0/1 |
| b02 | — | — | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 |
| b03 | — | — | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 |
| b04 | 0/0/0/0 | 0/0/0/3 | 0/0/0/1 | 0/0/0/1 | 0/0/0/0 | 0/0/0/1 |
| b05 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 |
| b06 | — | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b07 | — | — | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 |
| b08 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 5 | 0 of 8 |
| 10 | 0 of 8 |
| 20 | 0 of 8 |
| 40 | 4 of 8 |
| 60 | 4 of 8 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 7 | 0 | SIGINT after 1.0s | $1.41 |
| b02 | 7 | 0 | SIGINT after 1.0s | $1.83 |
| b03 | 7 | 0 | finished | $1.57 |
| b04 | 7 | 0 | SIGINT after 1.0s | $1.22 |
| b05 | 6 | 0 | SIGINT after 1.0s | $1.93 |
| b06 | 6 | 0 | SIGINT after 1.0s | $1.90 |
| b07 | 6 | 0 | SIGINT after 1.0s | $1.16 |
| b08 | 5 | 0 | SIGINT after 1.0s | $2.13 |

## Builder failures

- b01: exit 0, errors none, no valid bot in T1, T2
- b02: exit 0, errors none, no valid bot in T1, T2
- b03: exit 0, errors none, no valid bot in T1, T2
- b06: exit 0, errors none, no valid bot in T1
- b07: exit 0, errors none, no valid bot in T1, T2

## Cost

Total $13.14; per builder: b01 $1.41, b02 $1.83, b03 $1.57, b04 $1.22, b05 $1.93, b06 $1.90, b07 $1.16, b08 $2.13

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 93% at the first reading, 43% at the last. It counts everything on the same login, including your own sessions.
