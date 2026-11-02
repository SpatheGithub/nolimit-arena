# Report: royal-001

## Event card

- **Variant:** royal: No-limit hold'em with only T-J-Q-K-A (20 cards) and a 4-card board (no river).
- **Points table (winner_take_most):** 1st 100, 2nd 25, 3rd 5, 4th 0, 5th 0, 6th 0, 7th 0, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 3766184575
- **Computer asleep:** 71 min of the builder windows; the referee added it back to them
- **Computer asleep:** 49 of 148 builder-window minutes, measured afterwards from the macOS power log; the builders lost that time

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b05 | opus | math_core | 432.2 | 18.5 | 19.0 | 19.5 | 21.0 | 20.8 | 21.5 |
| 2 | b08 | opus | model_pressure | 413.4 | 20.4 | 21.5 | 20.5 | 17.8 | 20.1 | 19.5 |
| 3 | b06 | opus | free choice | 364.4 | 18.5 | 17.5 | 17.0 | 17.7 | 18.7 | 15.9 |
| 4 | b03 | opus | free choice | 359.8 | 14.6 | 16.4 | 17.3 | 18.6 | 16.2 | 17.5 |
| 5 | b01 | opus | model_pressure | 359.2 | 16.9 | 18.3 | 17.0 | 17.2 | 16.9 | 16.9 |
| 6 | b02 | opus | free choice | 281.3 | 13.4 | 13.5 | 14.0 | 14.5 | 12.8 | 12.8 |
| 7 | b07 | opus | free choice | 263.9 | 14.6 | 11.1 | 12.1 | 12.9 | 12.7 | 12.6 |
| 8 | b04 | opus | math_core | 255.8 | 13.1 | 12.6 | 12.7 | 10.4 | 11.7 | 13.2 |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b05 | 16% | 53% | 44% | 21% | 38% | 16% | 2.2 |
| 2 | b08 | 17% | 60% | 38% | 31% | 40% | 24% | 2.5 |
| 3 | b06 | 14% | 56% | 36% | 26% | 35% | 20% | 2.6 |
| 4 | b03 | 13% | 50% | 39% | 25% | 32% | 22% | 3.2 |
| 5 | b01 | 13% | 50% | 39% | 25% | 35% | 20% | 2.5 |
| 6 | b02 | 9% | 36% | 40% | 16% | 36% | 18% | 1.4 |
| 7 | b07 | 9% | 44% | 33% | 24% | 26% | 18% | 1.9 |
| 8 | b04 | 9% | 47% | 30% | 32% | 33% | 17% | 1.3 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b05 (math_core)

**In its builder's words** (Strategy in `bots/b05/NOTES.T6.md`). Math-first bot for royal hold'em (20-card deck, 4-card board). All equities are precomputed exactly (rank-only, straight flushes ignored except a live check) into `bot/tables.json`: preflop HU matrix (15x15 rank classes), equity vs top-q ranges, flop/turn equity vs random and vs top 50/25/10% of holdings. …

### 2. b08 (model_pressure)

**In its builder's words** (Strategy in `bots/b08/NOTES.T6.md`). Equity-driven bot for royal hold'em (20-card deck, 4-card board). All hand strength comes from tables precomputed for this deck (preflop equity vs 1..7 random hands, exact rank-only head-to-head equities for all 15x15 starting-hand types, flop/turn equity vs random); at decision time it computes equity against an estimated opponent range (top-X% of hands by strength, card-removal aware) and compares it with pot odds …

### 3. b06 (free choice)

**In its builder's words** (Strategy in `bots/b06/NOTES.T6.md`). Equity-driven bot built on exact rank-only equity tables for the 20-card royal deck. Suits are ignored because flushes are impossible and straight flushes are 0.16%. Every decision compares equity against an estimated opponent range (narrowed by that opponent's observed raise rate and by betting on this board) with pot odds; short stacks use a chip-EV push/fold model. …

### 4. b03 (free choice)

**In its builder's words** (Strategy in `bots/b03/NOTES.T6.md`). Table-driven equity bot for royal hold'em (20-card deck). Exact precomputed tables (preflop 190x190 pairwise equity, flop pairwise equity per 3-card board, exact turn hand values) let every decision compute equity against a Bayesian range for each opponent in ~50-100 µs. Decisions are chip-EV with small risk margins (payouts 100/25/5 are near winner-take-all, so chips ≈ points). …

### 5. b01 (model_pressure)

**In its builder's words** (Strategy in `bots/b01/NOTES.T6.md`). Equity bot built on exact precomputed tables for the 20-card royal deck (rank counts only; flush impossible, straight flush checked at runtime). Every decision compares equity versus each opponent's estimated range (top-X% of hands by strength on the current board, narrowed by their actions and their observed stats) with pot odds / fold equity.

### 6. b02 (free choice)

**In its builder's words** (Strategy in `bots/b02/NOTES.T6.md`). Table-driven equity bot for royal hold'em (20-card deck, 4-card board). All equities come from exact rank-only enumeration precomputed into `bot/tables.json` (suits ignored: flushes are impossible, straight flushes are 0.16%; verified identical to the engine on 20k deals except SF). …

### 7. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T6.md`). Equity-driven, fairly tight-aggressive bot for the royal (T-A, 20-card, 4-card board) variant. Hand values come from a precomputed rank-multiset table (suits only matter for straight flushes); preflop uses an exact class-vs-class equity matrix, postflop an exact enumeration of opponent rank classes (and turn card) weighted by each opponent's estimated range, narrowed when they bet. …

### 8. b04 (math_core)

**In its builder's words** (Strategy in `bots/b04/NOTES.T6.md`). Table-driven equity bot for royal hold'em (20-card deck, T-A, 4-card board). All equities are precomputed exactly (`precompute.py` -> `bot/tables.npz`): turn equity vs random / top-50% / top-25% hands for every (board, hole), flop equity averaged over turn cards, a 190x190 preflop heads-up matrix, preflop equity vs top-x% ranges and vs k random hands. …

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b05 | 432.2 ± 21.3 | 87% | 100% | 1 | 1–2 | 87% | 13% | · | · | · | · | · | · |
| b08 | 413.4 ± 21.4 | 13% | 100% | 2 | 1–2 | 13% | 87% | · | · | · | · | · | · |
| b06 | 364.4 ± 20.5 | 0% | 100% | 4 | 3–5 | · | · | 46% | 31% | 23% | · | · | · |
| b03 | 359.8 ± 19.6 | 0% | 100% | 4 | 3–5 | · | · | 28% | 33% | 38% | · | · | · |
| b01 | 359.2 ± 19.7 | 0% | 100% | 4 | 3–5 | · | · | 25% | 36% | 39% | · | · | · |
| b02 | 281.3 ± 17.3 | 0% | 0% | 6 | 6–7 | · | · | · | · | · | 89% | 9% | 1% |
| b07 | 263.9 ± 16.0 | 0% | 0% | 7 | 6–8 | · | · | · | · | · | 9% | 66% | 25% |
| b04 | 255.8 ± 16.8 | 0% | 0% | 8 | 7–8 | · | · | · | · | · | 2% | 25% | 74% |

## Field profile

How the bots played, from the hand logs of T1–T6 (3,956,972 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b05 | 38% | 16% | 52% | 46% | 2% | 33% | 38% |
| b08 | 40% | 24% | 63% | 45% | 7% | 41% | 28% |
| b06 | 35% | 20% | 60% | 44% | 6% | 45% | 31% |
| b03 | 32% | 23% | 62% | 45% | 5% | 41% | 26% |
| b01 | 35% | 19% | 58% | 37% | 6% | 33% | 29% |
| b02 | 36% | 18% | 59% | 34% | 4% | 63% | 24% |
| b07 | 27% | 18% | 53% | 67% | 4% | 55% | 38% |
| b04 | 33% | 17% | 50% | 56% | 7% | 43% | 42% |
| **Field** | 34% (27%–40%) | 19% (16%–24%) | 57% (50%–63%) | 46% (34%–67%) | 5% (2%–7%) | 44% (33%–63%) | 32% (24%–42%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b05 | 50% | 51% | 26% | 52% | 55% | 64% | 22% |
| b08 | 63% | 53% | 25% | 49% | 51% | 85% | 26% |
| b06 | 53% | 55% | 25% | 48% | 53% | 77% | 24% |
| b03 | 45% | 48% | 23% | 45% | 50% | 80% | 23% |
| b01 | 64% | 61% | 24% | 48% | 56% | 67% | 21% |
| b02 | 32% | 50% | 16% | 48% | 54% | 80% | 14% |
| b07 | 45% | 39% | 31% | 54% | 53% | 81% | 50% |
| b04 | 37% | 60% | 37% | 57% | 58% | 73% | 44% |
| **Field** | 49% (32%–64%) | 53% (39%–61%) | 25% (16%–37%) | 50% (45%–57%) | 54% (50%–58%) | 75% (64%–85%) | 27% (14%–50%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b05 | 51% | 43% | 42% | 34% | 32% | 37% | 52% | 70% |
| b08 | 59% | 52% | 45% | 36% | 34% | 43% | 58% | 73% |
| b06 | 72% | 51% | 40% | 30% | 28% | 40% | 55% | 70% |
| b03 | 52% | 39% | 37% | 28% | 26% | 35% | 51% | 70% |
| b01 | 59% | 45% | 39% | 30% | 28% | 38% | 55% | 73% |
| b02 | 43% | 39% | 41% | 33% | 30% | 38% | 55% | 74% |
| b07 | 46% | 33% | 31% | 23% | 21% | 28% | 41% | 70% |
| b04 | 63% | 37% | 33% | 31% | 29% | 34% | 45% | 59% |
| **Field** | 53% (43%–72%) | 42% (33%–52%) | 39% (31%–45%) | 31% (23%–36%) | 29% (21%–34%) | 37% (28%–43%) | 52% (41%–58%) | 70% (59%–74%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b05 | 78% | 47% | 29% | 30% |
| b08 | 79% | 40% | 19% | 23% |
| b06 | 79% | 43% | 25% | 23% |
| b03 | 52% | 34% | 19% | 21% |
| b01 | 56% | 34% | 24% | 23% |
| b02 | 48% | 28% | 16% | 19% |
| b07 | 82% | 48% | 26% | 29% |
| b04 | 81% | 51% | 33% | 34% |
| **Field** | 67% (48%–82%) | 40% (28%–51%) | 24% (16%–33%) | 25% (19%–34%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b05 | 2.5 bb | 65% | 70% pot | 42% |
| b08 | 2.5 bb | 66% | 70% pot | 70% |
| b06 | 2.5 bb | 76% | 60% pot | 48% |
| b03 | 2.5 bb | 63% | 60% pot | 58% |
| b01 | 2.5 bb | 64% | 50% pot | 53% |
| b02 | 2.5 bb | 82% | 60% pot | 52% |
| b07 | 2.5 bb | 91% | 70% pot | 49% |
| b04 | 2.5 bb | 75% | 50% pot | 47% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b05**: no spot below the field.
- **b08**: facing a c-bet: -1.8 ± 0.7 bb/100 (folds 53% against 53%); facing a river bet: -0.9 ± 1.0 bb/100 (calls 25% against 26%) — within noise.
- **b06**: facing a shove: -0.2 ± 0.5 bb/100 (folds 68% against 65%) — within noise; facing a 3-bet: -0.2 ± 0.7 bb/100 (calls 50% against 51%) — within noise.
- **b03**: facing a river bet: -3.5 ± 0.9 bb/100 (calls 23% against 26%); facing an open: -1.8 ± 0.9 bb/100 (folds 85% against 73%).
- **b01**: facing an open: -2.0 ± 1.0 bb/100 (calls 18% against 22%); facing a shove: -0.6 ± 0.6 bb/100 (folds 71% against 64%).
- **b02**: facing a steal: -1.4 ± 0.5 bb/100 (calls 58% against 43%); heads-up vs a raise: -0.3 ± 0.2 bb/100 (folds 14% against 29%).
- **b07**: facing an open: -3.8 ± 0.9 bb/100 (folds 86% against 73%); facing a river bet: -3.0 ± 0.8 bb/100 (folds 62% against 71%).
- **b04**: facing an open: -6.7 ± 1.3 bb/100 (folds 69% against 75%); facing a shove: -2.1 ± 0.9 bb/100 (calls 42% against 31%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 46% (34%–67%) | b03 +3.2 (all fold 15%), b08 +3.1 (all fold 13%) | b04 -1.8, b02 -1.4 |
| 3-bet | 44% (33%–63%) | b08 +8.7 (all fold 36%), b07 +7.8 (all fold 33%) | b04 -1.7, b08 -0.3 |
| Preflop shove | 65% (53%–74%) | b08 +6.3 (all fold 33%), b07 +5.1 (all fold 37%) | b04 -2.1, b01 -0.6 |
| Heads-up raise | 27% (14%–50%) | b08 +1.1 (all fold 17%), b01 +0.8 (all fold 35%) | b07 -0.4, b04 -0.4 |
| C-bet | 53% (39%–61%) | b03 +15.9 (all fold 53%), b08 +15.9 (all fold 48%) | b08 -1.8, b03 -0.3 |
| River bet | 70% (58%–83%) | b08 +30.5 (all fold 62%), b03 +28.7 (all fold 66%) | b03 -3.5, b07 -3.0 |

## T1 (weight 1)

1,000 tables, 116,312 hands, 15 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 20.45 ± 2.34 | 1000 | 45% | 26% | 1 | 100 |
| 2 ≈ | b05 | 18.52 ± 2.12 | 1000 | 37% | 16% | 0 | 50 |
| 3 ≈ | b06 | 18.52 ± 2.22 | 1000 | 35% | 21% | 0 | 50 |
| 4 ≈ | b01 | 16.85 ± 2.03 | 1000 | 32% | 19% | 2 | 50 |
| 5 ≈ | b03 | 14.62 ± 1.87 | 1000 | 26% | 18% | 0 | 100 |
| 6 ≈ | b07 | 14.55 ± 1.93 | 1000 | 24% | 18% | 0 | 100 |
| 7 ≈ | b02 | 13.40 ± 1.70 | 1000 | 22% | 17% | 0 | 50 |
| 8 | b04 | 13.09 ± 1.86 | 1000 | 32% | 16% | 0 | 25 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 113,820 hands, 16 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 21.52 ± 2.34 | 1000 | 44% | 24% | 0 | 100 |
| 2 ≈ | b05 | 19.02 ± 2.13 | 1000 | 38% | 16% | 0 | 50 |
| 3 ≈ | b01 | 18.34 ± 2.10 | 1000 | 35% | 19% | 0 | 50 |
| 4 ≈ | b06 | 17.55 ± 2.15 | 1000 | 34% | 19% | 0 | 50 |
| 5 ≈ | b03 | 16.45 ± 2.00 | 1000 | 29% | 21% | 0 | 100 |
| 6 ≈ | b02 | 13.48 ± 1.74 | 1000 | 39% | 18% | 0 | 25 |
| 7 ≈ | b04 | 12.55 ± 1.85 | 1000 | 32% | 16% | 0 | 25 |
| 8 | b07 | 11.10 ± 1.73 | 1000 | 37% | 22% | 0 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 114,093 hands, 25 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 20.48 ± 2.25 | 1000 | 40% | 25% | 0 | 200 |
| 2 ≈ | b05 | 19.50 ± 2.20 | 1000 | 38% | 16% | 0 | 100 |
| 3 ≈ | b03 | 17.27 ± 2.10 | 1000 | 35% | 24% | 0 | 200 |
| 4 ≈ | b01 | 17.00 ± 2.10 | 1000 | 35% | 20% | 0 | 100 |
| 5 ≈ | b06 | 16.98 ± 2.09 | 1000 | 34% | 20% | 0 | 100 |
| 6 ≈ | b02 | 13.96 ± 1.81 | 1000 | 40% | 18% | 0 | 100 |
| 7 ≈ | b04 | 12.71 ± 1.83 | 1000 | 32% | 17% | 0 | 50 |
| 8 | b07 | 12.10 ± 1.70 | 1000 | 24% | 17% | 0 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 112,125 hands, 23 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 21.00 ± 2.29 | 1000 | 37% | 16% | 0 | 100 |
| 2 ≈ | b03 | 18.64 ± 2.15 | 1000 | 35% | 24% | 0 | 200 |
| 3 ≈ | b08 | 17.77 ± 2.14 | 1000 | 40% | 25% | 0 | 100 |
| 4 ≈ | b06 | 17.67 ± 2.10 | 1000 | 36% | 21% | 0 | 100 |
| 5 ≈ | b01 | 17.16 ± 2.10 | 1000 | 35% | 19% | 0 | 50 |
| 6 ≈ | b02 | 14.49 ± 1.85 | 1000 | 40% | 18% | 0 | 50 |
| 7 ≈ | b07 | 12.91 ± 1.79 | 1000 | 25% | 17% | 0 | 100 |
| 8 | b04 | 10.37 ± 1.64 | 1000 | 37% | 22% | 0 | 25 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 113,436 hands, 23 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 20.80 ± 2.26 | 1000 | 37% | 16% | 0 | 100 |
| 2 ≈ | b08 | 20.09 ± 2.29 | 1000 | 40% | 24% | 0 | 100 |
| 3 ≈ | b06 | 18.73 ± 2.21 | 1000 | 36% | 21% | 0 | 100 |
| 4 ≈ | b01 | 16.91 ± 2.06 | 1000 | 35% | 19% | 0 | 50 |
| 5 ≈ | b03 | 16.20 ± 2.05 | 1000 | 35% | 24% | 0 | 200 |
| 6 ≈ | b02 | 12.85 ± 1.68 | 1000 | 39% | 18% | 0 | 50 |
| 7 ≈ | b07 | 12.67 ± 1.76 | 1000 | 25% | 17% | 0 | 100 |
| 8 | b04 | 11.74 ± 1.71 | 1000 | 32% | 16% | 0 | 50 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 113,955 hands, 23 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b05 | 21.53 ± 2.26 | 1000 | 38% | 16% | 0 | 50 |
| 2 ≈ | b08 | 19.48 ± 2.24 | 1000 | 30% | 18% | 0 | 100 |
| 3 ≈ | b03 | 17.49 ± 2.10 | 1000 | 35% | 25% | 1 | 200 |
| 4 ≈ | b01 | 16.91 ± 2.04 | 1000 | 35% | 20% | 0 | 50 |
| 5 ≈ | b06 | 15.92 ± 2.03 | 1000 | 36% | 21% | 0 | 100 |
| 6 ≈ | b04 | 13.21 ± 1.85 | 1000 | 32% | 16% | 0 | 25 |
| 7 ≈ | b02 | 12.80 ± 1.76 | 1000 | 39% | 18% | 0 | 50 |
| 8 | b07 | 12.64 ± 1.78 | 1000 | 25% | 18% | 0 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 317.3 ± 51.2 (n=4) |
| math_core | 344.0 ± 172.9 (n=2) |
| model_pressure | 386.3 ± 53.1 (n=2) |

| Model | Score |
| :- | -: |
| opus | 341.2 ± 46.5 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/2 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b02 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b03 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/1 |
| b04 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b05 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b06 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b07 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| b08 | 0/0/0/1 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 5 | 0 of 8 |
| 10 | 1 of 8 |
| 20 | 7 of 8 |
| 40 | 8 of 8 |
| 60 | 8 of 8 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 31 | 24 | finished | $10.20 |
| b02 | 37 | 30 | finished | $12.32 |
| b03 | 39 | 32 | finished | $13.40 |
| b04 | 46 | 39 | finished | $14.50 |
| b05 | 35 | 28 | finished | $13.04 |
| b06 | 41 | 34 | finished | $12.95 |
| b07 | 53 | 46 | finished | $12.51 |
| b08 | 50 | 43 | finished | $16.68 |

## Builder failures

None.

## Cost

Total $105.60; per builder: b01 $10.20, b02 $12.32, b03 $13.40, b04 $14.50, b05 $13.04, b06 $12.95, b07 $12.51, b08 $16.68

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 44% at the first reading, 31% at the last. It counts everything on the same login, including your own sessions.
