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
| 1 | b06 | opus | math_core | 533.3 | 24.2 | 24.9 | 25.8 | 25.7 | 25.6 | 25.2 |
| 2 | b02 | opus | model_pressure | 500.3 | 21.4 | 24.5 | 24.3 | 24.3 | 24.9 | 22.6 |
| 3 | b08 | opus | free choice | 454.9 | 22.8 | 21.9 | 22.2 | 21.0 | 21.6 | 21.6 |
| 4 | b07 | opus | free choice | 453.5 | 24.1 | 23.0 | 21.6 | 21.4 | 20.8 | 21.5 |
| 5 | b04 | opus | free choice | 449.4 | 19.6 | 18.7 | 20.9 | 21.5 | 23.0 | 21.5 |
| 6 | b01 | opus | free choice | 421.7 | 21.6 | 20.6 | 18.8 | 20.0 | 19.7 | 20.6 |
| 7 | b05 | opus | math_core | 420.2 | 20.0 | 20.6 | 21.2 | 21.0 | 18.0 | 20.3 |
| 8 | b03 | opus | model_pressure | 399.7 | 19.3 | 18.8 | 18.2 | 18.1 | 19.4 | 19.8 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | 17% | 57% | 39% | 29% | 35% | 20% | 1.7 |
| 2 | b02 | 16% | 58% | 38% | 25% | 29% | 19% | 2.2 |
| 3 | b08 | 13% | 52% | 38% | 19% | 33% | 18% | 9.2 |
| 4 | b07 | 12% | 48% | 39% | 21% | 25% | 17% | 1.8 |
| 5 | b04 | 12% | 53% | 36% | 24% | 25% | 17% | 1.9 |
| 6 | b01 | 10% | 41% | 38% | 28% | 28% | 21% | 2.4 |
| 7 | b05 | 10% | 42% | 38% | 26% | 26% | 18% | 1.7 |
| 8 | b03 | 10% | 46% | 35% | 28% | 28% | 15% | 1.3 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b06 (math_core)

**In its builder's words** (Strategy in `bots/b06/NOTES.T6.md`). Math-first bot. Preflop decisions come from a precomputed 81x81 shortdeck class-vs-class equity matrix (equity vs "top q%" ranges), with ICM-priced (points, not chips) push/fold and all-in calls when short. Postflop it computes near-exact equity with a vectorized numpy evaluator (rank-count lookup + flush table) against an opponent range that is narrowed by their preflop action and postflop bets, then …

### 2. b02 (model_pressure)

**In its builder's words** (Strategy in `bots/b02/NOTES.T6.md`). Equity-driven bot for 36-card shortdeck. Preflop uses a precomputed 81x81 hand-class equity matrix (bot/data.npz) to price opens, shoves and calls against estimated ranges; postflop computes equity with a vectorised numpy lookup evaluator against every (river) or a 100-combo sample of (flop/turn) opponent hole-card combos, weighted by each opponent's preflop range and narrowed by their postflop aggression. …

### 3. b08 (free choice)

**In its builder's words** (Strategy in `bots/b08/NOTES.T6.md`). Table-driven shortdeck bot. Preflop uses a precomputed 81x81 class-vs-class equity matrix (shortdeck, Monte Carlo offline, bot/eqmat.json) to get equity vs "top p%" ranges; short stacks play push/fold by explicit chip-EV of shoving/re-shoving against modelled (and read-adjusted) calling ranges; postflop uses a fast made-hand/draw strength heuristic, bets for value often and calls tightly. …

### 4. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T6.md`). Equity-driven bot for shortdeck. Preflop uses a precomputed 81x81 class-vs-class equity matrix (36-card deck) to get equity vs an estimated opponent range (top-p%), with chip-EV push/fold and reshove-with-fold-equity when short. …

### 5. b04 (free choice)

**In its builder's words** (Strategy in `bots/b04/NOTES.T6.md`). Table-driven shortdeck bot. Preflop it uses a precomputed 81x81 class-vs-class equity matrix (36-card deck, flush > full house) to get equity against an opponent's estimated range, and makes push/fold and calling decisions by chip EV with a small ICM margin. …

### 6. b01 (free choice)

**In its builder's words** (Strategy in `bots/b01/NOTES.T6.md`). Equity-driven bot. Preflop: position-aware opening ranges from a shortdeck hand-strength table, push/fold ranges widened by stack depth and short-handedness, and all-in calls decided by equity vs the shover's estimated range (81x81 precomputed class-vs-class matrix; shover range from their seat, depth and PFR) with an exact Malmuth-Harville ICM check when <=6 players remain. …

### 7. b05 (math_core)

**In its builder's words** (Strategy in `bots/b05/NOTES.T6.md`). Math-first bot (this is v10's code, resubmitted as 013-56b410f4 for T6). A precomputed exact 7-card hand-value table for the 36-card deck (8.3M entries, colex index, verified against the kit evaluator) powers a vectorised numpy Monte Carlo at decision time (opponent hands sampled directly from their estimated ranges, ~128/96/72 trials for 1/2/3 opponents, ~150 us). …

### 8. b03 (model_pressure)

**In its builder's words** (Strategy in `bots/b03/NOTES.T6.md`). Equity-driven bot. Preflop uses a precomputed 81x81 shortdeck class-vs-class equity matrix (bot/pre.json) to price shoves and calls against estimated opponent ranges; postflop runs a vectorized numpy Monte Carlo (70-150 samples from a precomputed permutation bank, halved if the decision is already slow; ~0.1-0.25 ms) against opponents' ranges weighted by their preflop and postflop actions. …

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 533.3 ± 21.6 | 97% | 100% | 1 | 1–1 | 97% | 3% | · | · | · | · | · | · |
| b02 | 500.3 ± 21.1 | 3% | 100% | 2 | 2–2 | 3% | 97% | · | · | · | · | · | · |
| b08 | 454.9 ± 19.4 | 0% | 99% | 4 | 3–5 | · | · | 44% | 31% | 24% | 1% | · | · |
| b07 | 453.5 ± 19.1 | 0% | 98% | 4 | 3–5 | · | · | 35% | 36% | 26% | 2% | · | · |
| b04 | 449.4 ± 19.6 | 0% | 96% | 4 | 3–5 | · | · | 21% | 31% | 44% | 4% | · | · |
| b01 | 421.7 ± 18.7 | 0% | 4% | 6 | 6–7 | · | · | · | 0% | 4% | 48% | 42% | 5% |
| b05 | 420.2 ± 18.0 | 0% | 2% | 7 | 6–8 | · | · | · | · | 2% | 44% | 48% | 6% |
| b03 | 399.7 ± 17.7 | 0% | 0% | 8 | 7–8 | · | · | · | · | · | 2% | 10% | 89% |

## Field profile

How the bots played, from the hand logs of T1–T6 (3,960,647 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b06 | 35% | 20% | 41% | 37% | 11% | 60% | 23% |
| b02 | 29% | 19% | 49% | 52% | 5% | 49% | 34% |
| b08 | 33% | 19% | 57% | 48% | 2% | 78% | 21% |
| b07 | 25% | 17% | 49% | 67% | 2% | 50% | 24% |
| b04 | 25% | 17% | 40% | 62% | 5% | 58% | 25% |
| b01 | 28% | 21% | 50% | 79% | 3% | 70% | 19% |
| b05 | 26% | 18% | 41% | 71% | 5% | 50% | 22% |
| b03 | 28% | 15% | 36% | 50% | 4% | 54% | 16% |
| **Field** | 28% (25%–35%) | 18% (15%–21%) | 46% (36%–57%) | 59% (37%–79%) | 5% (2%–11%) | 59% (49%–78%) | 23% (16%–34%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b06 | 71% | 52% | 23% | 39% | 50% | 72% | 36% |
| b02 | 68% | 42% | 31% | 39% | 50% | 69% | 53% |
| b08 | 81% | 90% | 23% | 29% | 48% | 81% | 34% |
| b07 | 61% | 27% | 15% | 42% | 52% | 84% | 50% |
| b04 | 65% | 38% | 40% | 41% | 49% | 54% | 40% |
| b01 | 63% | 54% | 33% | 42% | 53% | 76% | 59% |
| b05 | 63% | 63% | 44% | 42% | 52% | 69% | 69% |
| b03 | 67% | 32% | 32% | 41% | 47% | 85% | 23% |
| **Field** | 67% (61%–81%) | 52% (27%–90%) | 30% (15%–44%) | 39% (29%–42%) | 50% (47%–53%) | 74% (54%–85%) | 47% (23%–69%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 50% | 51% | 39% | 30% | 29% | 38% | 50% | 60% |
| b02 | 61% | 39% | 34% | 24% | 22% | 32% | 46% | 56% |
| b08 | 55% | 34% | 38% | 30% | 27% | 34% | 50% | 64% |
| b07 | 34% | 26% | 30% | 22% | 19% | 26% | 39% | 61% |
| b04 | 29% | 20% | 30% | 24% | 21% | 25% | 33% | 55% |
| b01 | 41% | 25% | 31% | 26% | 24% | 28% | 32% | 54% |
| b05 | 34% | 26% | 28% | 25% | 23% | 26% | 33% | 48% |
| b03 | 26% | 26% | 33% | 26% | 24% | 29% | 34% | 70% |
| **Field** | 37% (26%–61%) | 29% (20%–51%) | 33% (28%–39%) | 26% (22%–30%) | 24% (19%–29%) | 30% (25%–38%) | 39% (32%–50%) | 58% (48%–70%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b06 | 19% | 19% | 23% | 28% |
| b02 | 73% | 45% | 27% | 23% |
| b08 | 49% | 25% | 16% | 15% |
| b07 | 21% | 22% | 27% | 28% |
| b04 | 50% | 31% | 16% | 16% |
| b01 | 26% | 18% | 17% | 18% |
| b05 | 29% | 18% | 19% | 26% |
| b03 | 18% | 13% | 18% | 18% |
| **Field** | 30% (18%–73%) | 23% (13%–45%) | 21% (16%–27%) | 21% (15%–28%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b06 | 2.5 bb | 55% | 60% pot | 42% |
| b02 | 2.5 bb | 69% | 50% pot | 43% |
| b08 | 2.5 bb | 43% | 40% pot | 33% |
| b07 | 2.5 bb | 62% | 60% pot | 50% |
| b04 | 2.5 bb | 80% | 60% pot | 38% |
| b01 | 2.5 bb | 58% | 60% pot | 33% |
| b05 | 2.5 bb | 66% | 70% pot | 64% |
| b03 | 2.5 bb | 64% | 60% pot | 37% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b06**: facing a 3-bet: -0.4 ± 0.6 bb/100 (calls 35% against 38%) — within noise; facing a shove: -0.1 ± 0.5 bb/100 (folds 77% against 75%) — within noise.
- **b02**: heads-up vs a raise: -0.0 ± 0.2 bb/100 (folds 53% against 46%) — within noise.
- **b08**: facing a steal: -1.2 ± 0.7 bb/100 (calls 49% against 32%); facing a shove: -0.7 ± 0.6 bb/100 (folds 78% against 75%).
- **b07**: facing an open: -1.0 ± 0.9 bb/100 (folds 89% against 80%); facing a river bet: -0.7 ± 0.8 bb/100 (folds 82% against 64%) — within noise.
- **b04**: facing a river bet: -5.5 ± 1.0 bb/100 (calls 40% against 29%); facing a c-bet: -2.1 ± 0.8 bb/100 (calls 61% against 45%).
- **b01**: facing a steal: -2.2 ± 0.6 bb/100 (folds 79% against 56%); facing a shove: -1.0 ± 0.7 bb/100 (raises 7% against 1%).
- **b05**: facing a c-bet: -1.8 ± 0.8 bb/100 (folds 63% against 51%); facing a shove: -1.2 ± 0.7 bb/100 (folds 78% against 75%).
- **b03**: facing a river bet: -5.5 ± 1.2 bb/100 (folds 64% against 66%); facing an open: -3.5 ± 1.2 bb/100 (calls 19% against 15%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 59% (37%–79%) | b02 +7.6 (all fold 33%), b08 +6.9 (all fold 41%) | b01 -2.2, b08 -1.2 |
| 3-bet | 59% (49%–78%) | b06 +8.1 (all fold 60%), b05 +7.1 (all fold 58%) | b03 -1.4, b05 -0.9 |
| Preflop shove | 75% (66%–79%) | b02 +5.4 (all fold 63%), b05 +4.8 (all fold 62%) | b05 -1.2, b01 -1.0 |
| Heads-up raise | 47% (23%–69%) | b02 +0.7 (all fold 41%), b08 +0.5 (all fold 54%) | b08 -0.4, b05 -0.4 |
| C-bet | 52% (27%–90%) | b01 +14.6 (all fold 48%), b04 +13.2 (all fold 54%) | b03 -2.5, b04 -2.1 |
| River bet | 66% (53%–82%) | b06 +17.5 (all fold 63%), b08 +14.8 (all fold 60%) | b04 -5.5, b03 -5.5 |

## T1 (weight 1)

1,000 tables, 118,809 hands, 29 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 24.20 ± 2.28 | 1000 | 35% | 20% | 0 | 500 |
| 2 ≈ | b07 | 24.07 ± 2.11 | 1000 | 25% | 18% | 0 | 300 |
| 3 ≈ | b08 | 22.81 ± 2.10 | 1000 | 33% | 19% | 0 | 100 |
| 4 ≈ | b01 | 21.64 ± 1.84 | 1000 | 28% | 21% | 0 | 500 |
| 5 ≈ | b02 | 21.41 ± 2.12 | 1000 | 29% | 18% | 0 | 500 |
| 6 ≈ | b05 | 19.96 ± 1.98 | 1000 | 27% | 18% | 2 | 300 |
| 7 ≈ | b04 | 19.57 ± 1.95 | 1000 | 22% | 15% | 0 | 500 |
| 8 | b03 | 19.34 ± 1.97 | 1000 | 27% | 15% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 116,412 hands, 32 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 24.87 ± 2.26 | 1000 | 35% | 20% | 0 | 500 |
| 2 ≈ | b02 | 24.53 ± 2.20 | 1000 | 29% | 18% | 0 | 500 |
| 3 ≈ | b07 | 23.04 ± 2.13 | 1000 | 26% | 17% | 0 | 500 |
| 4 ≈ | b08 | 21.90 ± 2.04 | 1000 | 33% | 18% | 0 | 100 |
| 5 ≈ | b01 | 20.60 ± 1.95 | 1000 | 28% | 22% | 0 | 407 |
| 6 ≈ | b05 | 20.58 ± 1.98 | 1000 | 26% | 17% | 0 | 500 |
| 7 ≈ | b03 | 18.79 ± 1.91 | 1000 | 27% | 15% | 0 | 500 |
| 8 | b04 | 18.69 ± 1.87 | 1000 | 24% | 17% | 0 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 118,329 hands, 41 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 25.76 ± 2.27 | 1000 | 35% | 20% | 0 | 500 |
| 2 ≈ | b02 | 24.30 ± 2.24 | 1000 | 28% | 19% | 0 | 500 |
| 3 ≈ | b08 | 22.19 ± 2.10 | 1000 | 33% | 19% | 0 | 100 |
| 4 ≈ | b07 | 21.64 ± 2.03 | 1000 | 26% | 18% | 0 | 500 |
| 5 ≈ | b05 | 21.18 ± 1.97 | 1000 | 26% | 18% | 0 | 500 |
| 6 ≈ | b04 | 20.85 ± 1.97 | 1000 | 25% | 17% | 0 | 500 |
| 7 ≈ | b01 | 18.84 ± 1.85 | 1000 | 28% | 21% | 0 | 500 |
| 8 | b03 | 18.23 ± 1.91 | 1000 | 27% | 15% | 0 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 116,465 hands, 36 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 25.72 ± 2.31 | 1000 | 35% | 20% | 0 | 500 |
| 2 ≈ | b02 | 24.29 ± 2.24 | 1000 | 29% | 20% | 0 | 500 |
| 3 ≈ | b04 | 21.46 ± 2.09 | 1000 | 26% | 19% | 0 | 500 |
| 4 ≈ | b07 | 21.37 ± 1.98 | 1000 | 24% | 17% | 0 | 500 |
| 5 ≈ | b05 | 20.99 ± 1.87 | 1000 | 26% | 18% | 0 | 500 |
| 6 ≈ | b08 | 20.98 ± 2.00 | 1000 | 33% | 18% | 0 | 100 |
| 7 ≈ | b01 | 20.04 ± 1.90 | 1000 | 28% | 21% | 0 | 500 |
| 8 | b03 | 18.15 ± 1.93 | 1000 | 28% | 15% | 0 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 117,237 hands, 36 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 25.57 ± 2.28 | 1000 | 35% | 20% | 0 | 500 |
| 2 ≈ | b02 | 24.86 ± 2.28 | 1000 | 29% | 19% | 1 | 500 |
| 3 ≈ | b04 | 23.05 ± 2.16 | 1000 | 26% | 18% | 0 | 500 |
| 4 ≈ | b08 | 21.64 ± 2.03 | 1000 | 33% | 19% | 0 | 100 |
| 5 ≈ | b07 | 20.82 ± 2.01 | 1000 | 24% | 16% | 0 | 500 |
| 6 ≈ | b01 | 19.71 ± 1.92 | 1000 | 27% | 21% | 0 | 486 |
| 7 ≈ | b03 | 19.37 ± 1.87 | 1000 | 29% | 17% | 2 | 500 |
| 8 | b05 | 17.99 ± 1.75 | 1000 | 26% | 18% | 0 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 116,210 hands, 29 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 25.23 ± 2.29 | 1000 | 35% | 20% | 0 | 300 |
| 2 ≈ | b02 | 22.57 ± 2.16 | 1000 | 28% | 19% | 0 | 300 |
| 3 ≈ | b08 | 21.61 ± 2.07 | 1000 | 33% | 18% | 0 | 50 |
| 4 ≈ | b07 | 21.47 ± 1.96 | 1000 | 24% | 17% | 0 | 300 |
| 5 ≈ | b04 | 21.47 ± 2.10 | 1000 | 26% | 18% | 0 | 500 |
| 6 ≈ | b01 | 20.61 ± 2.01 | 1000 | 27% | 21% | 0 | 500 |
| 7 ≈ | b05 | 20.27 ± 1.87 | 1000 | 26% | 17% | 0 | 300 |
| 8 | b03 | 19.78 ± 1.90 | 1000 | 29% | 17% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 444.9 ± 15.3 (n=4) |
| math_core | 476.7 ± 110.9 (n=2) |
| model_pressure | 450.0 ± 98.5 (n=2) |

| Model | Score |
| :- | -: |
| opus | 454.1 ± 30.5 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b02 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 |
| b03 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 1/0/0/1 | 0/0/0/0 |
| b04 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b05 | 2/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b06 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b07 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b08 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |

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
| b01 | 32 | 25 | finished | $20.43 |
| b02 | 38 | 31 | finished | $21.67 |
| b03 | 32 | 25 | finished | $19.31 |
| b04 | 35 | 28 | finished | $21.30 |
| b05 | 34 | 27 | finished | $19.44 |
| b06 | 37 | 30 | finished | $17.09 |
| b07 | 40 | 33 | finished | $26.44 |
| b08 | 46 | 39 | finished | $19.38 |

## Builder failures

None.

## Cost

Total $165.07; per builder: b01 $20.43, b02 $21.67, b03 $19.31, b04 $21.30, b05 $19.44, b06 $17.09, b07 $26.44, b08 $19.38

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 32% at the first reading, 24% at the last. It counts everything on the same login, including your own sessions.
