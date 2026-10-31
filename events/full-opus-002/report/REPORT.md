# Report: full-opus-002

## Event card

- **Variant:** nlhe: No-limit Texas hold'em: 2 hole cards, a 5-card board, best five of seven.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 4281125837

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | opus | math_core | 743.9 | 33.3 | 32.9 | 33.6 | 35.6 | 37.4 | 35.8 |
| 2 | b03 | opus | math_core | 713.0 | 34.8 | 35.4 | 35.7 | 35.3 | 33.8 | 31.8 |
| 3 | b08 | opus | free choice | 698.4 | 33.7 | 31.8 | 33.0 | 33.2 | 34.5 | 32.8 |
| 4 | b05 | opus | free choice | 681.1 | 32.9 | 32.1 | 34.0 | 31.6 | 32.4 | 32.3 |
| 5 | b02 | opus | free choice | 642.6 | 29.3 | 31.3 | 29.4 | 30.3 | 30.4 | 31.6 |
| 6 | b04 | opus | model_pressure | 636.2 | 30.3 | 29.0 | 30.4 | 28.7 | 29.9 | 32.1 |
| 7 | b01 | opus | free choice | 624.7 | 30.7 | 31.6 | 30.5 | 30.3 | 27.2 | 30.3 |
| 8 | b07 | opus | model_pressure | 615.2 | 30.0 | 31.0 | 28.4 | 30.0 | 29.5 | 28.4 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | 16% | 55% | 40% | 27% | 25% | 20% | 1.9 |
| 2 | b03 | 16% | 60% | 39% | 22% | 25% | 18% | 4.6 |
| 3 | b08 | 11% | 46% | 41% | 20% | 20% | 14% | 5.5 |
| 4 | b05 | 12% | 48% | 39% | 23% | 23% | 17% | 2.7 |
| 5 | b02 | 12% | 51% | 33% | 25% | 22% | 17% | 1.9 |
| 6 | b04 | 12% | 54% | 34% | 28% | 24% | 18% | 2.5 |
| 7 | b01 | 9% | 38% | 38% | 27% | 23% | 17% | 2.1 |
| 8 | b07 | 11% | 47% | 36% | 28% | 24% | 19% | 3.3 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 743.9 ± 21.0 | 96% | 100% | 1 | 1–1 | 96% | 4% | · | · | · | · | · | · |
| b03 | 713.0 ± 19.7 | 4% | 100% | 2 | 2–3 | 4% | 80% | 16% | 1% | · | · | · | · |
| b08 | 698.4 ± 18.5 | 0% | 100% | 3 | 2–4 | · | 16% | 73% | 11% | · | · | · | · |
| b05 | 681.1 ± 18.3 | 0% | 100% | 4 | 3–4 | · | 1% | 11% | 88% | · | · | · | · |
| b02 | 642.5 ± 18.1 | 0% | 64% | 5 | 5–7 | · | · | · | · | 64% | 29% | 6% | 0% |
| b04 | 636.2 ± 18.8 | 0% | 30% | 6 | 5–7 | · | · | · | · | 30% | 48% | 17% | 4% |
| b01 | 624.7 ± 17.2 | 0% | 5% | 7 | 6–8 | · | · | · | · | 5% | 18% | 54% | 22% |
| b07 | 615.2 ± 17.7 | 0% | 0% | 8 | 7–8 | · | · | · | · | · | 4% | 22% | 73% |

## Field profile

How the bots played, from the hand logs of T1–T6 (4,569,992 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b06 | 25% | 20% | 38% | 66% | 12% | 78% | 22% |
| b03 | 25% | 18% | 45% | 65% | 7% | 74% | 25% |
| b08 | 20% | 14% | 33% | 77% | 4% | 76% | 13% |
| b05 | 23% | 17% | 39% | 71% | 7% | 76% | 13% |
| b02 | 22% | 17% | 41% | 80% | 5% | 70% | 17% |
| b04 | 24% | 18% | 45% | 77% | 4% | 81% | 18% |
| b01 | 23% | 17% | 43% | 75% | 5% | 86% | 12% |
| b07 | 24% | 19% | 54% | 79% | 3% | 68% | 19% |
| **Field** | 23% (20%–25%) | 18% (14%–20%) | 42% (33%–54%) | 74% (65%–80%) | 6% (3%–12%) | 76% (68%–86%) | 17% (12%–25%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b06 | 81% | 69% | 33% | 47% | 51% | 69% | 52% |
| b03 | 86% | 80% | 14% | 42% | 48% | 67% | 57% |
| b08 | 85% | 60% | 38% | 39% | 48% | 80% | 72% |
| b05 | 62% | 86% | 31% | 37% | 51% | 86% | 59% |
| b02 | 75% | 65% | 46% | 47% | 51% | 62% | 53% |
| b04 | 68% | 55% | 33% | 42% | 47% | 88% | 54% |
| b01 | 71% | 63% | 43% | 42% | 48% | 69% | 64% |
| b07 | 87% | 86% | 55% | 41% | 49% | 93% | 66% |
| **Field** | 77% (62%–87%) | 72% (55%–86%) | 37% (14%–55%) | 42% (37%–47%) | 49% (47%–51%) | 76% (62%–93%) | 60% (52%–72%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 32% | 29% | 32% | 20% | 20% | 28% | 37% | 58% |
| b03 | 34% | 30% | 27% | 20% | 19% | 27% | 44% | 50% |
| b08 | 22% | 18% | 22% | 19% | 17% | 19% | 29% | 52% |
| b05 | 32% | 26% | 26% | 19% | 19% | 24% | 36% | 59% |
| b02 | 23% | 24% | 24% | 20% | 19% | 22% | 33% | 49% |
| b04 | 37% | 23% | 27% | 22% | 21% | 25% | 38% | 61% |
| b01 | 33% | 24% | 24% | 21% | 20% | 25% | 28% | 50% |
| b07 | 31% | 25% | 27% | 21% | 20% | 26% | 36% | 60% |
| **Field** | 29% (22%–37%) | 25% (18%–30%) | 26% (22%–32%) | 20% (19%–22%) | 19% (17%–21%) | 25% (19%–28%) | 35% (28%–44%) | 55% (49%–61%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b06 | 23% | 19% | 23% | 25% |
| b03 | 23% | 23% | 27% | 37% |
| b08 | 13% | 12% | 14% | 19% |
| b05 | 13% | 12% | 14% | 22% |
| b02 | 14% | 17% | 20% | 20% |
| b04 | 17% | 16% | 19% | 30% |
| b01 | 16% | 11% | 7% | 13% |
| b07 | 27% | 16% | 16% | 24% |
| **Field** | 17% (13%–27%) | 15% (11%–23%) | 17% (7%–27%) | 24% (13%–37%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b06 | 2.5 bb | 57% | 40% pot | 44% |
| b03 | 2.5 bb | 56% | 70% pot | 35% |
| b08 | 2.5 bb | 55% | 50% pot | 53% |
| b05 | 2.5 bb | 38% | 50% pot | 48% |
| b02 | 2.5 bb | 68% | 50% pot | 46% |
| b04 | 2.5 bb | 76% | 70% pot | 43% |
| b01 | 2.5 bb | 63% | 50% pot | 42% |
| b07 | 2.5 bb | 63% | 50% pot | 72% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b06**: facing a 3-bet: -0.3 ± 0.5 bb/100 (folds 78% against 76%) — within noise.
- **b03**: facing a c-bet: -0.7 ± 0.4 bb/100 (calls 17% against 27%); facing a river bet: -0.3 ± 0.4 bb/100 (folds 83% against 57%) — within noise.
- **b08**: facing a river bet: -1.6 ± 0.5 bb/100 (raises 2% against 3%); facing a 3-bet: -1.1 ± 0.5 bb/100 (calls 16% against 20%).
- **b05**: facing a c-bet: -0.7 ± 0.4 bb/100 (folds 86% against 69%); facing a steal: -0.2 ± 0.4 bb/100 (folds 71% against 74%) — within noise.
- **b02**: facing a steal: -1.4 ± 0.4 bb/100 (folds 80% against 73%); facing an open: -0.9 ± 0.8 bb/100 (folds 89% against 86%).
- **b04**: facing a river bet: -1.9 ± 0.6 bb/100 (folds 64% against 59%); facing an open: -1.0 ± 0.9 bb/100 (calls 12% against 9%).
- **b01**: facing an open: -1.0 ± 0.9 bb/100 (raises 4% against 5%); facing a 3-bet: -0.8 ± 0.6 bb/100 (folds 86% against 74%).
- **b07**: facing a steal: -2.2 ± 0.4 bb/100 (folds 79% against 73%); facing an open: -1.1 ± 0.8 bb/100 (folds 90% against 85%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 74% (65%–80%) | b03 +6.7 (all fold 61%), b07 +6.2 (all fold 56%) | b07 -2.2, b02 -1.4 |
| 3-bet | 76% (68%–86%) | b06 +8.6 (all fold 76%), b03 +7.3 (all fold 75%) | b08 -1.1, b01 -0.8 |
| Preflop shove | 82% (75%–87%) | b06 +8.0 (all fold 75%), b03 +7.5 (all fold 74%) | b04 -0.8, b01 -0.6 |
| Heads-up raise | 60% (52%–72%) | b02 +0.4 (all fold 60%), b03 +0.4 (all fold 60%) | b01 -0.3, b07 -0.2 |
| C-bet | 72% (55%–86%) | b07 +6.3 (all fold 68%), b03 +5.9 (all fold 69%) | b07 -1.1, b05 -0.7 |
| River bet | 60% (43%–83%) | b05 +4.8 (all fold 64%), b06 +3.8 (all fold 62%) | b04 -1.9, b08 -1.6 |

## T1 (weight 1)

1,000 tables, 130,878 hands, 125 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b03 | 34.78 ± 2.12 | 1000 | 25% | 18% | 3 | 500 |
| 2 ≈ | b08 | 33.73 ± 1.84 | 1000 | 19% | 12% | 9 | 500 |
| 3 ≈ | b06 | 33.32 ± 1.93 | 1000 | 22% | 17% | 2 | 100 |
| 4 ≈ | b05 | 32.91 ± 2.01 | 1000 | 23% | 18% | 0 | 100 |
| 5 ≈ | b01 | 30.70 ± 1.90 | 1000 | 23% | 17% | 8 | 500 |
| 6 ≈ | b04 | 30.28 ± 1.89 | 1000 | 24% | 18% | 3 | 500 |
| 7 ≈ | b07 | 30.01 ± 1.94 | 1000 | 24% | 20% | 5 | 200 |
| 8 | b02 | 29.27 ± 2.07 | 1000 | 24% | 19% | 2 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 129,570 hands, 43 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b03 | 35.37 ± 2.18 | 1000 | 24% | 18% | 0 | 200 |
| 2 ≈ | b06 | 32.88 ± 2.03 | 1000 | 23% | 17% | 0 | 50 |
| 3 ≈ | b05 | 32.13 ± 1.94 | 1000 | 23% | 17% | 0 | 50 |
| 4 ≈ | b08 | 31.79 ± 1.83 | 1000 | 19% | 11% | 0 | 500 |
| 5 ≈ | b01 | 31.61 ± 1.90 | 1000 | 23% | 17% | 0 | 500 |
| 6 ≈ | b02 | 31.28 ± 1.97 | 1000 | 22% | 17% | 0 | 100 |
| 7 ≈ | b07 | 30.97 ± 1.96 | 1000 | 24% | 19% | 0 | 100 |
| 8 | b04 | 28.96 ± 1.89 | 1000 | 24% | 18% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 130,533 hands, 43 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b03 | 35.70 ± 2.13 | 1000 | 25% | 18% | 0 | 200 |
| 2 ≈ | b05 | 33.95 ± 1.97 | 1000 | 23% | 17% | 0 | 50 |
| 3 ≈ | b06 | 33.60 ± 2.00 | 1000 | 23% | 17% | 0 | 50 |
| 4 ≈ | b08 | 33.04 ± 1.96 | 1000 | 22% | 15% | 0 | 500 |
| 5 ≈ | b01 | 30.50 ± 1.95 | 1000 | 23% | 17% | 0 | 500 |
| 6 ≈ | b04 | 30.43 ± 2.01 | 1000 | 24% | 17% | 0 | 300 |
| 7 ≈ | b02 | 29.39 ± 1.83 | 1000 | 21% | 16% | 0 | 50 |
| 8 | b07 | 28.38 ± 1.82 | 1000 | 25% | 21% | 0 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 126,873 hands, 41 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 35.63 ± 2.28 | 1000 | 28% | 23% | 0 | 50 |
| 2 ≈ | b03 | 35.28 ± 2.09 | 1000 | 24% | 18% | 0 | 200 |
| 3 ≈ | b08 | 33.22 ± 1.85 | 1000 | 20% | 15% | 0 | 500 |
| 4 ≈ | b05 | 31.59 ± 1.90 | 1000 | 22% | 17% | 0 | 50 |
| 5 ≈ | b01 | 30.29 ± 1.82 | 1000 | 22% | 17% | 0 | 500 |
| 6 ≈ | b02 | 30.29 ± 1.85 | 1000 | 21% | 17% | 0 | 100 |
| 7 ≈ | b07 | 30.00 ± 1.94 | 1000 | 24% | 19% | 0 | 100 |
| 8 | b04 | 28.70 ± 1.91 | 1000 | 23% | 17% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 125,848 hands, 41 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 37.37 ± 2.30 | 1000 | 28% | 22% | 0 | 50 |
| 2 ≈ | b08 | 34.48 ± 1.86 | 1000 | 20% | 15% | 0 | 481 |
| 3 ≈ | b03 | 33.75 ± 2.05 | 1000 | 24% | 18% | 0 | 200 |
| 4 ≈ | b05 | 32.37 ± 1.97 | 1000 | 23% | 17% | 0 | 50 |
| 5 ≈ | b02 | 30.41 ± 1.84 | 1000 | 21% | 17% | 0 | 100 |
| 6 ≈ | b04 | 29.86 ± 1.99 | 1000 | 27% | 21% | 0 | 300 |
| 7 ≈ | b07 | 29.55 ± 1.88 | 1000 | 23% | 18% | 0 | 100 |
| 8 | b01 | 27.21 ± 1.71 | 1000 | 24% | 19% | 0 | 447 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 126,848 hands, 42 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 35.78 ± 2.29 | 1000 | 28% | 22% | 0 | 50 |
| 2 ≈ | b08 | 32.78 ± 1.90 | 1000 | 20% | 16% | 0 | 499 |
| 3 ≈ | b05 | 32.30 ± 1.93 | 1000 | 23% | 17% | 0 | 50 |
| 4 ≈ | b04 | 32.10 ± 2.01 | 1000 | 25% | 19% | 0 | 300 |
| 5 ≈ | b03 | 31.75 ± 1.98 | 1000 | 26% | 20% | 0 | 300 |
| 6 ≈ | b02 | 31.55 ± 1.92 | 1000 | 22% | 17% | 0 | 100 |
| 7 ≈ | b01 | 30.34 ± 1.79 | 1000 | 22% | 17% | 0 | 500 |
| 8 | b07 | 28.39 ± 1.84 | 1000 | 23% | 18% | 0 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 661.7 ± 33.3 (n=4) |
| math_core | 728.5 ± 30.3 (n=2) |
| model_pressure | 625.7 ± 20.6 (n=2) |

| Model | Score |
| :- | -: |
| opus | 669.4 ± 32.3 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 5/0/0/3 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b02 | 1/0/0/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b03 | 0/0/0/3 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b04 | 0/0/0/3 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b05 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b06 | 0/0/0/2 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b07 | 1/0/0/4 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b08 | 4/0/0/5 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |

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
| b01 | 46 | 37 | finished | $28.00 |
| b02 | 43 | 34 | finished | $22.42 |
| b03 | 40 | 31 | finished | $20.36 |
| b04 | 32 | 23 | finished | $22.62 |
| b05 | 40 | 31 | finished | $19.73 |
| b06 | 32 | 23 | finished | $17.98 |
| b07 | 42 | 33 | finished | $22.32 |
| b08 | 33 | 24 | finished | $16.08 |

## Builder failures

None.

## Cost

Total $169.51; per builder: b01 $28.00, b02 $22.42, b03 $20.36, b04 $22.62, b05 $19.73, b06 $17.98, b07 $22.32, b08 $16.08

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 18% at the first reading, 61% at the last. It counts everything on the same login, including your own sessions.
