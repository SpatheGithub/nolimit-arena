# Report: shortdeck-001

## Event card

- **Variant:** shortdeck: No-limit hold'em with a 36-card deck (6 to A): a flush beats a full house and A-6-7-8-9 is a straight.
- **Points table (top_heavy):** 1st 100, 2nd 45, 3rd 20, 4th 8, 5th 0, 6th 0, 7th 0, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 2685883945
- **Computer asleep:** 109 of 138 builder-window minutes, measured afterwards from the macOS power log; the builders lost that time

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b02 | opus | model_pressure | 503.9 | 25.0 | 26.3 | 26.2 | 22.6 | 23.8 | 23.1 |
| 2 | b08 | opus | free choice | 465.5 | 23.9 | 22.4 | 20.8 | 22.1 | 22.6 | 22.2 |
| 3 | b04 | opus | free choice | 459.3 | 20.0 | 21.2 | 20.4 | 21.7 | 23.5 | 21.9 |
| 4 | b06 | opus | math_core | 455.1 | 23.5 | 20.5 | 21.8 | 21.1 | 21.0 | 22.6 |
| 5 | b07 | opus | free choice | 445.4 | 21.2 | 21.0 | 20.5 | 20.5 | 20.7 | 22.5 |
| 6 | b03 | opus | model_pressure | 441.6 | 19.9 | 20.4 | 21.8 | 21.5 | 20.0 | 21.6 |
| 7 | b01 | opus | free choice | 435.9 | 18.9 | 21.0 | 20.5 | 22.8 | 20.1 | 20.3 |
| 8 | b05 | opus | math_core | 426.3 | 20.7 | 20.3 | 20.9 | 20.8 | 21.3 | 18.8 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b02 | 14% | 47% | 43% | 23% | 30% | 19% | 1.4 |
| 2 | b08 | 14% | 52% | 37% | 30% | 27% | 18% | 2.7 |
| 3 | b04 | 13% | 51% | 36% | 29% | 33% | 19% | 2.0 |
| 4 | b06 | 14% | 56% | 36% | 23% | 30% | 20% | 1.7 |
| 5 | b07 | 12% | 48% | 37% | 22% | 28% | 21% | 2.5 |
| 6 | b03 | 12% | 49% | 37% | 21% | 24% | 19% | 2.1 |
| 7 | b01 | 10% | 44% | 39% | 24% | 25% | 15% | 1.7 |
| 8 | b05 | 12% | 53% | 35% | 30% | 30% | 20% | 2.5 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b02 (model_pressure)

**In its builder's words** (Strategy in `bots/b02/NOTES.T6.md`). Equity-driven TAG bot for short-deck with ICM-priced all-ins. Preflop uses precomputed 81-class equity tables (HU matrix + multiway) to rank hands and price calls/shoves vs estimated opponent ranges; every all-in decision (shove, resteal, calling a shove, big postflop calls) is valued in tournament points with an ICM table, which stops it flipping its stack away while reckless bots bust each other. …

### 2. b08 (free choice)

**In its builder's words** (Strategy in `bots/b08/NOTES.T6.md`). Equity- and ICM-driven bot. Preflop it uses precomputed shortdeck equity tables (81 hand classes, equity vs random hands and vs top-X% ranges). Postflop it runs a fast vectorized numpy Monte Carlo (about 240 samples, 0.1–0.4 ms) against opponents whose ranges are narrowed by their preflop raises and postflop bets. …

### 3. b04 (free choice)

**In its builder's words** (Strategy in `bots/b04/NOTES.T6.md`). Equity-driven bot for shortdeck (36 cards, flush > full house). A lookup-table hand evaluator (validated against the engine on 100k hands, ~0.4 µs per 7-card eval) and precomputed preflop equity tables (81 classes: vs k random hands and class-vs-class heads-up, in `bot/pre.json`) drive every decision. Postflop it runs a time-boxed Monte Carlo (≤0.25 ms, ~150-250 trials) against each opponent's estimated range. …

### 4. b06 (math_core)

**In its builder's words** (Strategy in `bots/b06/NOTES.T6.md`). Math-first bot. A custom shortdeck evaluator (base-5 rank-key dict lookup, verified identical to the engine on 30k hands) drives precomputed preflop tables (81 classes: equity vs k random hands + an 81x81 class-vs-class matrix) and postflop equity (time-boxed Monte Carlo vs opponents' estimated ranges on flop/turn, exact enumeration of all opponent combos on the river). …

### 5. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T6.md`). Table-driven shortdeck bot. Preflop uses a precomputed 81x81 class-vs-class equity matrix (shortdeck, 3M deals) to get equity vs each opponent's estimated range, plus a chip-EV push/fold model when short. Postflop it runs a vectorized numpy Monte Carlo (360 samples, lookup-table evaluator, ~0.2 ms) against up to 3 opponents whose hands are weighted by their preflop range and, if they bet, strongly by their current …

### 6. b03 (model_pressure)

**In its builder's words** (Strategy in `bots/b03/NOTES.T6.md`). Preflop decisions use a precomputed 81x81 shortdeck class-vs-class equity matrix (Monte Carlo, 1500 deals/pair) turned into "equity vs top-x% range" tables, so every call/shove is an EV computation against an estimated range, valued with a 50/50 blend of ICM points (precomputed table, exact referee payouts 100/45/20/8) and chip EV. …

### 7. b01 (free choice)

**In its builder's words** (Strategy in `bots/b01/NOTES.T6.md`). Tight-aggressive shortdeck bot built on precomputed preflop equities (81 hand classes, vs k random hands plus an 81x81 heads-up matrix) and a fast table-driven 36-card evaluator (about 0.5 µs per hand) that runs a time-boxed Monte Carlo postflop against opponents' estimated ranges. All-in decisions add an ICM risk premium, because under 100/45/20/8 busting early costs far more than doubling up gains.

### 8. b05 (math_core)

**In its builder's words** (Strategy in `bots/b05/NOTES.T6.md`). Math-first bot for shortdeck. Preflop uses precomputed shortdeck equity tables (81 hand classes: equity vs k random hands, head-to-head matrix, equity vs top-x% ranges); postflop runs a small vectorized numpy Monte Carlo (~200 samples, fixed precomputed permutation bank) against opponents whose hands are weighted by their preflop action and by their betting on this street. …

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b02 | 503.9 ± 19.7 | 99% | 100% | 1 | 1–1 | 99% | 1% | · | · | · | · | · | · |
| b08 | 465.5 ± 20.5 | 1% | 97% | 2 | 2–5 | 1% | 51% | 25% | 15% | 6% | 2% | 1% | · |
| b04 | 459.3 ± 19.8 | 0% | 93% | 3 | 2–6 | · | 27% | 33% | 22% | 12% | 5% | 2% | · |
| b06 | 455.1 ± 20.3 | 0% | 87% | 4 | 2–6 | · | 17% | 26% | 27% | 17% | 8% | 4% | 1% |
| b07 | 445.4 ± 19.2 | 0% | 59% | 5 | 3–7 | · | 3% | 10% | 18% | 28% | 23% | 13% | 5% |
| b03 | 441.6 ± 18.9 | 0% | 39% | 6 | 3–8 | · | 1% | 5% | 11% | 22% | 29% | 23% | 9% |
| b01 | 435.9 ± 18.4 | 0% | 19% | 7 | 4–8 | · | · | 2% | 5% | 12% | 25% | 36% | 20% |
| b05 | 426.3 ± 19.7 | 0% | 5% | 8 | 6–8 | · | · | · | 1% | 4% | 8% | 21% | 66% |

## Field profile

How the bots played, from the hand logs of T1–T6 (3,831,917 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b02 | 30% | 19% | 40% | 70% | 7% | 62% | 30% |
| b08 | 27% | 18% | 38% | 70% | 7% | 41% | 27% |
| b04 | 33% | 19% | 51% | 57% | 5% | 45% | 27% |
| b06 | 30% | 20% | 48% | 53% | 4% | 64% | 29% |
| b07 | 28% | 21% | 49% | 70% | 4% | 64% | 22% |
| b03 | 24% | 19% | 46% | 74% | 5% | 54% | 24% |
| b01 | 25% | 15% | 33% | 57% | 6% | 60% | 17% |
| b05 | 30% | 20% | 48% | 66% | 5% | 59% | 22% |
| **Field** | 28% (24%–33%) | 19% (15%–21%) | 44% (33%–51%) | 65% (53%–74%) | 5% (4%–7%) | 57% (41%–64%) | 25% (17%–30%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b02 | 52% | 43% | 35% | 47% | 53% | 74% | 70% |
| b08 | 63% | 46% | 29% | 43% | 48% | 56% | 62% |
| b04 | 68% | 59% | 33% | 41% | 49% | 71% | 47% |
| b06 | 78% | 43% | 37% | 45% | 52% | 81% | 30% |
| b07 | 56% | 47% | 21% | 42% | 54% | 87% | 65% |
| b03 | 65% | 47% | 45% | 49% | 52% | 73% | 64% |
| b01 | 57% | 47% | 42% | 45% | 48% | 70% | 36% |
| b05 | 67% | 45% | 27% | 42% | 51% | 85% | 56% |
| **Field** | 63% (52%–78%) | 48% (43%–59%) | 34% (21%–45%) | 44% (41%–49%) | 51% (48%–54%) | 74% (56%–87%) | 55% (30%–70%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b02 | 33% | 30% | 30% | 30% | 27% | 28% | 34% | 48% |
| b08 | 50% | 37% | 35% | 21% | 21% | 29% | 37% | 45% |
| b04 | 63% | 39% | 35% | 30% | 28% | 33% | 46% | 55% |
| b06 | 60% | 39% | 35% | 25% | 22% | 30% | 50% | 66% |
| b07 | 43% | 33% | 32% | 24% | 22% | 27% | 41% | 56% |
| b03 | 34% | 27% | 28% | 21% | 19% | 24% | 34% | 50% |
| b01 | 27% | 26% | 28% | 23% | 20% | 24% | 33% | 59% |
| b05 | 61% | 36% | 31% | 28% | 26% | 30% | 40% | 58% |
| **Field** | 39% (27%–63%) | 33% (26%–39%) | 32% (28%–35%) | 25% (21%–30%) | 23% (19%–28%) | 28% (24%–33%) | 39% (33%–50%) | 54% (45%–66%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b02 | 26% | 22% | 34% | 42% |
| b08 | 57% | 26% | 21% | 28% |
| b04 | 48% | 25% | 23% | 27% |
| b06 | 60% | 35% | 24% | 22% |
| b07 | 47% | 22% | 15% | 18% |
| b03 | 47% | 25% | 17% | 19% |
| b01 | 15% | 14% | 18% | 23% |
| b05 | 55% | 26% | 15% | 19% |
| **Field** | 37% (15%–60%) | 24% (14%–35%) | 21% (15%–34%) | 25% (18%–42%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b02 | 2.5 bb | 82% | 70% pot | 37% |
| b08 | 2.5 bb | 64% | 60% pot | 46% |
| b04 | 2.5 bb | 61% | 60% pot | 51% |
| b06 | 2.5 bb | 72% | 50% pot | 36% |
| b07 | 2.5 bb | 66% | 50% pot | 34% |
| b03 | 2.5 bb | 66% | 50% pot | 37% |
| b01 | 2.5 bb | 47% | 50% pot | 27% |
| b05 | 2.5 bb | 58% | 60% pot | 45% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b02**: no spot below the field.
- **b08**: facing a c-bet: -1.3 ± 1.0 bb/100 (folds 46% against 48%); facing a river bet: -0.5 ± 1.0 bb/100 (calls 29% against 34%) — within noise.
- **b04**: facing a shove: -0.6 ± 0.9 bb/100 (calls 27% against 24%) — within noise; facing a steal: -0.3 ± 0.8 bb/100 (calls 38% against 27%) — within noise.
- **b06**: facing a river bet: -1.1 ± 1.2 bb/100 (folds 59% against 63%) — within noise; facing a 3-bet: -0.8 ± 0.9 bb/100 (folds 64% against 56%) — within noise.
- **b07**: facing a shove: -1.8 ± 0.6 bb/100 (calls 22% against 25%); facing an open: -1.5 ± 1.2 bb/100 (folds 87% against 78%).
- **b03**: facing a river bet: -2.5 ± 1.0 bb/100 (calls 45% against 32%); facing a c-bet: -2.0 ± 0.7 bb/100 (calls 52% against 51%).
- **b01**: facing a river bet: -6.9 ± 1.1 bb/100 (folds 52% against 64%); facing an open: -1.2 ± 1.4 bb/100 (calls 13% against 16%) — within noise.
- **b05**: facing a c-bet: -1.2 ± 1.0 bb/100 (folds 45% against 48%); facing an open: -1.0 ± 1.6 bb/100 (folds 77% against 80%) — within noise.

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 65% (53%–74%) | b07 +6.5 (all fold 42%), b05 +6.0 (all fold 39%) | b01 -0.8, b03 -0.7 |
| 3-bet | 57% (41%–64%) | b02 +7.5 (all fold 54%), b08 +7.3 (all fold 52%) | b06 -0.8, b07 -0.4 |
| Preflop shove | 75% (68%–83%) | b02 +6.8 (all fold 62%), b03 +4.7 (all fold 63%) | b07 -1.8, b05 -0.9 |
| Heads-up raise | 55% (30%–70%) | b08 +0.8 (all fold 53%), b02 +0.8 (all fold 52%) | b07 -0.3, b04 -0.1 |
| C-bet | 48% (43%–59%) | b05 +14.4 (all fold 44%), b06 +11.8 (all fold 45%) | b03 -2.0, b08 -1.3 |
| River bet | 62% (52%–76%) | b04 +20.0 (all fold 60%), b05 +16.7 (all fold 59%) | b01 -6.9, b03 -2.5 |

## T1 (weight 1)

1,000 tables, 117,040 hands, 31 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 24.95 ± 2.11 | 1000 | 31% | 20% | 1 | 500 |
| 2 ≈ | b08 | 23.87 ± 2.24 | 1000 | 26% | 18% | 1 | 300 |
| 3 ≈ | b06 | 23.50 ± 2.19 | 1000 | 30% | 20% | 0 | 500 |
| 4 ≈ | b07 | 21.16 ± 1.92 | 1000 | 28% | 20% | 1 | 300 |
| 5 ≈ | b05 | 20.74 ± 2.07 | 1000 | 31% | 20% | 0 | 300 |
| 6 ≈ | b04 | 19.95 ± 2.02 | 1000 | 33% | 19% | 1 | 300 |
| 7 ≈ | b03 | 19.91 ± 1.91 | 1000 | 24% | 19% | 0 | 100 |
| 8 | b01 | 18.91 ± 1.87 | 1000 | 30% | 14% | 4 | 500 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 118,341 hands, 28 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 26.29 ± 2.22 | 1000 | 30% | 20% | 1 | 500 |
| 2 ≈ | b08 | 22.40 ± 2.12 | 1000 | 27% | 18% | 0 | 300 |
| 3 ≈ | b04 | 21.21 ± 2.07 | 1000 | 33% | 20% | 0 | 300 |
| 4 ≈ | b07 | 21.02 ± 2.02 | 1000 | 28% | 20% | 2 | 300 |
| 5 ≈ | b01 | 20.98 ± 1.89 | 1000 | 23% | 14% | 1 | 500 |
| 6 ≈ | b06 | 20.45 ± 2.02 | 1000 | 30% | 20% | 1 | 500 |
| 7 ≈ | b03 | 20.39 ± 1.95 | 1000 | 24% | 19% | 0 | 100 |
| 8 | b05 | 20.26 ± 2.07 | 1000 | 31% | 20% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 118,520 hands, 31 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 | b02 | 26.22 ± 2.19 | 1000 | 30% | 20% | 1 | 500 |
| 2 ≈ | b06 | 21.85 ± 2.11 | 1000 | 30% | 20% | 1 | 500 |
| 3 ≈ | b03 | 21.79 ± 2.03 | 1000 | 24% | 19% | 1 | 100 |
| 4 ≈ | b05 | 20.89 ± 2.08 | 1000 | 31% | 21% | 1 | 500 |
| 5 ≈ | b08 | 20.84 ± 2.05 | 1000 | 26% | 18% | 0 | 500 |
| 6 ≈ | b07 | 20.51 ± 2.00 | 1000 | 28% | 21% | 1 | 300 |
| 7 ≈ | b01 | 20.48 ± 1.94 | 1000 | 24% | 15% | 2 | 500 |
| 8 | b04 | 20.43 ± 1.97 | 1000 | 33% | 19% | 1 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 118,006 hands, 30 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b01 | 22.75 ± 2.00 | 1000 | 24% | 15% | 1 | 500 |
| 2 ≈ | b02 | 22.55 ± 2.03 | 1000 | 30% | 19% | 1 | 500 |
| 3 ≈ | b08 | 22.06 ± 2.10 | 1000 | 27% | 18% | 1 | 500 |
| 4 ≈ | b04 | 21.66 ± 2.08 | 1000 | 33% | 19% | 2 | 300 |
| 5 ≈ | b03 | 21.55 ± 2.05 | 1000 | 24% | 19% | 0 | 100 |
| 6 ≈ | b06 | 21.09 ± 2.12 | 1000 | 30% | 20% | 0 | 500 |
| 7 ≈ | b05 | 20.83 ± 2.05 | 1000 | 30% | 20% | 2 | 500 |
| 8 | b07 | 20.51 ± 1.96 | 1000 | 28% | 21% | 2 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 118,625 hands, 30 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 23.82 ± 2.09 | 1000 | 30% | 19% | 3 | 500 |
| 2 ≈ | b04 | 23.53 ± 2.20 | 1000 | 33% | 19% | 3 | 300 |
| 3 ≈ | b08 | 22.63 ± 2.13 | 1000 | 27% | 18% | 1 | 500 |
| 4 ≈ | b05 | 21.26 ± 2.10 | 1000 | 30% | 20% | 0 | 500 |
| 5 ≈ | b06 | 21.00 ± 2.09 | 1000 | 30% | 20% | 0 | 500 |
| 6 ≈ | b07 | 20.67 ± 1.94 | 1000 | 28% | 21% | 0 | 300 |
| 7 ≈ | b01 | 20.12 ± 1.88 | 1000 | 24% | 15% | 1 | 500 |
| 8 | b03 | 19.97 ± 1.93 | 1000 | 23% | 19% | 1 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 118,540 hands, 29 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 23.08 ± 2.05 | 1000 | 30% | 19% | 1 | 500 |
| 2 ≈ | b06 | 22.64 ± 2.18 | 1000 | 30% | 20% | 1 | 500 |
| 3 ≈ | b07 | 22.54 ± 2.08 | 1000 | 28% | 21% | 1 | 300 |
| 4 ≈ | b08 | 22.16 ± 2.14 | 1000 | 27% | 18% | 2 | 300 |
| 5 ≈ | b04 | 21.89 ± 2.07 | 1000 | 33% | 19% | 0 | 300 |
| 6 ≈ | b03 | 21.58 ± 2.04 | 1000 | 23% | 18% | 0 | 100 |
| 7 ≈ | b01 | 20.33 ± 1.89 | 1000 | 24% | 15% | 1 | 488 |
| 8 | b05 | 18.79 ± 1.92 | 1000 | 30% | 20% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 451.5 ± 13.1 (n=4) |
| math_core | 440.7 ± 28.3 (n=2) |
| model_pressure | 472.7 ± 61.1 (n=2) |

| Model | Score |
| :- | -: |
| opus | 454.1 ± 16.5 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/4 | 0/0/0/1 | 0/0/0/2 | 0/0/0/1 | 0/0/0/1 | 0/0/0/1 |
| b02 | 0/0/0/1 | 0/0/0/1 | 0/0/0/1 | 0/0/0/1 | 0/0/0/3 | 0/0/0/1 |
| b03 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 | 0/0/0/1 | 0/0/0/0 |
| b04 | 1/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/2 | 2/0/0/1 | 0/0/0/0 |
| b05 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 1/0/0/1 | 0/0/0/0 | 0/0/0/0 |
| b06 | 0/0/0/0 | 0/0/0/1 | 0/0/0/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 |
| b07 | 0/0/0/1 | 0/0/0/2 | 0/0/0/1 | 0/0/0/2 | 0/0/0/0 | 0/0/0/1 |
| b08 | 0/0/0/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 | 0/0/0/1 | 0/0/0/2 |

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
| b01 | 16 | 9 | SIGINT after 1.5s | $10.16 |
| b02 | 16 | 9 | SIGINT after 1.5s | $9.45 |
| b03 | 13 | 6 | SIGINT after 1.5s | $9.05 |
| b04 | 11 | 4 | SIGINT after 1.5s | $7.31 |
| b05 | 15 | 8 | SIGINT after 1.5s | $6.91 |
| b06 | 14 | 7 | SIGINT after 1.5s | $9.08 |
| b07 | 12 | 5 | SIGINT after 1.5s | $7.72 |
| b08 | 14 | 7 | SIGINT after 1.5s | $7.05 |

## Builder failures

None.

## Cost

Total $66.72; per builder: b01 $10.16, b02 $9.45, b03 $9.05, b04 $7.31, b05 $6.91, b06 $9.08, b07 $7.72, b08 $7.05

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 46% at the first reading, 92% at the last. It counts everything on the same login, including your own sessions.
