# Report: royal-001

## Event card

- **Variant:** royal: No-limit hold'em with only T-J-Q-K-A (20 cards) and a 4-card board (no river).
- **Points table (winner_take_most):** 1st 100, 2nd 25, 3rd 5, 4th 0, 5th 0, 6th 0, 7th 0, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 3766184575
- **Computer asleep:** 49 of 88 builder-window minutes, measured afterwards from the macOS power log; the builders lost that time

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b08 | opus | model_pressure | 124.9 | 20.4 | 21.5 | 20.5 | not played | not played | not played |
| 2 | b05 | opus | math_core | 115.1 | 18.5 | 19.0 | 19.5 | not played | not played | not played |
| 3 | b01 | opus | model_pressure | 104.5 | 16.9 | 18.3 | 17.0 | not played | not played | not played |
| 4 | b06 | opus | free choice | 104.5 | 18.5 | 17.5 | 17.0 | not played | not played | not played |
| 5 | b03 | opus | free choice | 99.3 | 14.6 | 16.4 | 17.3 | not played | not played | not played |
| 6 | b02 | opus | free choice | 82.2 | 13.4 | 13.5 | 14.0 | not played | not played | not played |
| 7 | b04 | opus | math_core | 76.3 | 13.1 | 12.6 | 12.7 | not played | not played | not played |
| 8 | b07 | opus | free choice | 73.0 | 14.6 | 11.1 | 12.1 | not played | not played | not played |

## How each bot played

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b08 | 18% | 61% | 38% | 32% | 43% | 25% | 2.4 |
| 2 | b05 | 15% | 51% | 44% | 22% | 38% | 16% | 2.3 |
| 3 | b06 | 15% | 59% | 36% | 26% | 34% | 20% | 2.5 |
| 4 | b01 | 13% | 50% | 40% | 24% | 34% | 20% | 2.9 |
| 5 | b03 | 12% | 47% | 39% | 23% | 30% | 21% | 3.3 |
| 6 | b02 | 9% | 35% | 42% | 14% | 33% | 18% | 1.5 |
| 7 | b04 | 10% | 50% | 29% | 33% | 32% | 17% | 1.3 |
| 8 | b07 | 9% | 45% | 32% | 27% | 28% | 19% | 1.9 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b08 (model_pressure)

**In its builder's words** (Strategy in `bots/b08/NOTES.T3.md`). Equity-driven bot for royal hold'em (20-card deck, 4-card board). All hand strength comes from tables precomputed for this deck (preflop equity vs 1..7 random hands, exact rank-only head-to-head equities for all 15x15 starting-hand types, flop/turn equity vs random); at decision time it computes equity against an estimated opponent range (top-X% of hands by strength, card-removal aware) and compares it with pot odds …

### 2. b05 (math_core)

**In its builder's words** (Strategy in `bots/b05/NOTES.T3.md`). Math-first bot for royal hold'em (20-card deck, 4-card board). All equities are precomputed exactly (rank-only, straight flushes ignored except a live check) into `bot/tables.json`: preflop HU matrix (15x15 rank classes), equity vs top-q ranges, flop/turn equity vs random and vs top 50/25/10% of holdings. …

### 3. b06 (free choice)

**In its builder's words** (Strategy in `bots/b06/NOTES.T3.md`). Equity-driven bot built on exact rank-only equity tables for the 20-card royal deck. Suits are ignored because flushes are impossible and straight flushes are 0.16%. Every decision compares equity against an estimated opponent range (narrowed by that opponent's observed raise rate and by betting on this board) with pot odds; short stacks use a chip-EV push/fold model. …

### 4. b01 (model_pressure)

**In its builder's words** (Strategy in `bots/b01/NOTES.T3.md`). Equity bot built on exact precomputed tables for the 20-card royal deck (rank counts only; flush impossible, straight flush checked at runtime). Every decision compares equity versus each opponent's estimated range (top-X% of hands by strength on the current board, narrowed by their actions and their observed stats) with pot odds / fold equity.

### 5. b03 (free choice)

**In its builder's words** (Strategy in `bots/b03/NOTES.T3.md`). Table-driven equity bot for royal hold'em (20-card deck). Exact precomputed tables (preflop 190x190 pairwise equity, flop pairwise equity per 3-card board, exact turn hand values) let every decision compute equity against a Bayesian range for each opponent in ~50-100 µs. Decisions are chip-EV with small risk margins (payouts 100/25/5 are near winner-take-all, so chips ≈ points).

### 6. b02 (free choice)

**In its builder's words** (Strategy in `bots/b02/NOTES.T3.md`). Table-driven equity bot for royal hold'em (20-card deck, 4-card board). All equities come from exact rank-only enumeration precomputed into `bot/tables.json` (suits ignored: flushes are impossible, straight flushes are 0.16%; verified identical to the engine on 20k deals except SF). …

### 7. b04 (math_core)

**In its builder's words** (Strategy in `bots/b04/NOTES.T3.md`). Table-driven equity bot for royal hold'em (20-card deck, T-A, 4-card board). All equities are precomputed exactly (`precompute.py` -> `bot/tables.npz`): turn equity vs random / top-50% / top-25% hands for every (board, hole), flop equity averaged over turn cards, a 190x190 preflop heads-up matrix, preflop equity vs top-x% ranges and vs k random hands. …

### 8. b07 (free choice)

**In its builder's words** (Strategy in `bots/b07/NOTES.T3.md`). Equity-driven, fairly tight-aggressive bot for the royal (T-A, 20-card, 4-card board) variant. Hand values come from a precomputed rank-multiset table (suits only matter for straight flushes); preflop uses an exact class-vs-class equity matrix, postflop an exact enumeration of opponent rank classes (and turn card) weighted by each opponent's estimated range, narrowed when they bet. …

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b08 | 124.9 ± 8.3 | 94% | 100% | 1 | 1–2 | 94% | 6% | · | · | · | · | · | · |
| b05 | 115.1 ± 7.9 | 6% | 100% | 2 | 1–3 | 6% | 87% | 6% | 1% | · | · | · | · |
| b06 | 104.5 ± 8.0 | 0% | 100% | 4 | 3–5 | · | 4% | 42% | 39% | 16% | · | · | · |
| b01 | 104.5 ± 7.8 | 0% | 100% | 4 | 3–5 | · | 4% | 44% | 38% | 14% | · | · | · |
| b03 | 99.3 ± 7.4 | 0% | 100% | 5 | 3–5 | · | · | 8% | 22% | 70% | · | · | · |
| b02 | 82.2 ± 6.7 | 0% | 0% | 6 | 6–7 | · | · | · | · | · | 85% | 14% | 1% |
| b04 | 76.3 ± 6.9 | 0% | 0% | 7 | 6–8 | · | · | · | · | · | 13% | 62% | 25% |
| b07 | 73.0 ± 6.5 | 0% | 0% | 8 | 7–8 | · | · | · | · | · | 2% | 24% | 74% |

## Field profile

How the bots played, from the hand logs of T1–T3 (1,993,716 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b08 | 43% | 25% | 67% | 39% | 7% | 38% | 29% |
| b05 | 38% | 16% | 53% | 45% | 2% | 33% | 37% |
| b06 | 34% | 20% | 60% | 43% | 6% | 42% | 31% |
| b01 | 34% | 19% | 58% | 38% | 6% | 34% | 28% |
| b03 | 30% | 21% | 61% | 51% | 4% | 41% | 25% |
| b02 | 33% | 18% | 59% | 42% | 4% | 64% | 24% |
| b04 | 32% | 17% | 49% | 57% | 7% | 43% | 42% |
| b07 | 28% | 19% | 53% | 64% | 4% | 52% | 35% |
| **Field** | 34% (28%–43%) | 19% (16%–25%) | 58% (49%–67%) | 47% (38%–64%) | 5% (2%–7%) | 43% (33%–64%) | 31% (24%–42%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b08 | 62% | 54% | 25% | 49% | 51% | 87% | 22% |
| b05 | 50% | 51% | 25% | 52% | 55% | 65% | 28% |
| b06 | 46% | 55% | 25% | 49% | 54% | 77% | 25% |
| b01 | 65% | 65% | 23% | 48% | 57% | 68% | 23% |
| b03 | 43% | 48% | 22% | 45% | 49% | 79% | 24% |
| b02 | 32% | 50% | 17% | 49% | 55% | 82% | 22% |
| b04 | 39% | 51% | 39% | 60% | 57% | 75% | 45% |
| b07 | 45% | 42% | 31% | 54% | 53% | 82% | 60% |
| **Field** | 48% (32%–65%) | 53% (42%–65%) | 26% (17%–39%) | 50% (45%–60%) | 54% (49%–57%) | 76% (65%–87%) | 30% (22%–60%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b08 | 58% | 54% | 48% | 40% | 37% | 47% | 61% | 76% |
| b05 | 51% | 43% | 42% | 34% | 32% | 37% | 53% | 69% |
| b06 | 72% | 51% | 39% | 29% | 27% | 40% | 56% | 70% |
| b01 | 58% | 45% | 39% | 29% | 27% | 38% | 55% | 73% |
| b03 | 45% | 36% | 35% | 26% | 24% | 32% | 48% | 70% |
| b02 | 43% | 38% | 38% | 30% | 27% | 35% | 53% | 73% |
| b04 | 63% | 37% | 33% | 30% | 29% | 33% | 43% | 61% |
| b07 | 46% | 34% | 32% | 25% | 23% | 30% | 42% | 67% |
| **Field** | 52% (43%–72%) | 41% (34%–54%) | 38% (32%–48%) | 30% (25%–40%) | 28% (23%–37%) | 37% (30%–47%) | 52% (42%–61%) | 70% (61%–76%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b08 | 76% | 42% | 19% | 24% |
| b05 | 77% | 45% | 28% | 29% |
| b06 | 77% | 41% | 25% | 22% |
| b01 | 54% | 33% | 24% | 23% |
| b03 | 44% | 32% | 19% | 20% |
| b02 | 47% | 29% | 15% | 18% |
| b04 | 82% | 50% | 33% | 33% |
| b07 | 79% | 46% | 22% | 25% |
| **Field** | 64% (44%–82%) | 39% (29%–50%) | 23% (15%–33%) | 25% (18%–33%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b08 | 2.5 bb | 66% | 70% pot | 69% |
| b05 | 2.5 bb | 64% | 70% pot | 42% |
| b06 | 2.5 bb | 76% | 60% pot | 54% |
| b01 | 2.5 bb | 63% | 50% pot | 53% |
| b03 | 2.5 bb | 61% | 60% pot | 56% |
| b02 | 2.5 bb | 84% | 60% pot | 53% |
| b04 | 2.5 bb | 73% | 50% pot | 47% |
| b07 | 2.5 bb | 91% | 70% pot | 48% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b08**: facing a c-bet: -1.8 ± 1.1 bb/100 (folds 54% against 52%); facing a river bet: -0.8 ± 1.5 bb/100 (calls 25% against 26%) — within noise.
- **b05**: no spot below the field.
- **b06**: facing a 3-bet: -0.3 ± 0.9 bb/100 (folds 42% against 43%) — within noise; facing a shove: -0.2 ± 0.7 bb/100 (folds 68% against 65%) — within noise.
- **b01**: facing an open: -0.7 ± 1.4 bb/100 (calls 17% against 21%) — within noise; facing a shove: -0.2 ± 0.9 bb/100 (folds 71% against 65%) — within noise.
- **b03**: facing an open: -4.0 ± 1.1 bb/100 (folds 88% against 73%); facing a river bet: -2.8 ± 1.2 bb/100 (calls 22% against 26%).
- **b02**: facing a steal: -1.0 ± 0.7 bb/100 (calls 50% against 43%); heads-up vs a raise: -0.2 ± 0.3 bb/100 (folds 22% against 31%) — within noise.
- **b04**: facing an open: -7.2 ± 1.8 bb/100 (folds 69% against 76%); facing a shove: -1.8 ± 1.1 bb/100 (calls 42% against 30%).
- **b07**: facing an open: -4.1 ± 1.3 bb/100 (folds 84% against 74%); facing a river bet: -3.9 ± 1.2 bb/100 (folds 62% against 71%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 47% (38%–64%) | b08 +3.6 (all fold 13%), b01 +3.1 (all fold 23%) | b04 -1.5, b07 -1.2 |
| 3-bet | 43% (33%–64%) | b08 +8.8 (all fold 36%), b07 +7.4 (all fold 30%) | b04 -1.5, b07 -0.5 |
| Preflop shove | 66% (53%–74%) | b08 +6.4 (all fold 32%), b07 +5.3 (all fold 36%) | b04 -1.8, b03 -0.3 |
| Heads-up raise | 30% (22%–60%) | b08 +1.1 (all fold 18%), b06 +0.9 (all fold 45%) | b07 -0.2, b04 -0.2 |
| C-bet | 53% (42%–65%) | b08 +16.4 (all fold 47%), b03 +13.7 (all fold 54%) | b08 -1.8, b07 -0.5 |
| River bet | 70% (57%–82%) | b08 +33.6 (all fold 63%), b03 +25.6 (all fold 66%) | b07 -3.9, b03 -2.8 |

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

1,000 tables, 114,093 hands, 15 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b08 | 20.48 ± 2.25 | 1000 | 40% | 25% | 0 | 100 |
| 2 ≈ | b05 | 19.50 ± 2.20 | 1000 | 38% | 16% | 0 | 50 |
| 3 ≈ | b03 | 17.27 ± 2.10 | 1000 | 35% | 24% | 0 | 100 |
| 4 ≈ | b01 | 17.00 ± 2.10 | 1000 | 35% | 20% | 0 | 50 |
| 5 ≈ | b06 | 16.98 ± 2.09 | 1000 | 34% | 20% | 0 | 50 |
| 6 ≈ | b02 | 13.96 ± 1.81 | 1000 | 40% | 18% | 0 | 50 |
| 7 ≈ | b04 | 12.71 ± 1.83 | 1000 | 32% | 17% | 0 | 25 |
| 8 | b07 | 12.10 ± 1.70 | 1000 | 24% | 17% | 0 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

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
| free choice | 89.8 ± 14.4 (n=4) |
| math_core | 95.7 ± 37.9 (n=2) |
| model_pressure | 114.7 ± 20.0 (n=2) |

| Model | Score |
| :- | -: |
| opus | 97.5 ± 12.9 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/2 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b02 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b03 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b04 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b05 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b06 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b07 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | — | — | — |
| b08 | 0/0/0/1 | 0/0/0/0 | 0/0/0/0 | — | — | — |

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
| b01 | 13 | 9 | finished | $4.55 |
| b02 | 14 | 10 | finished | $5.29 |
| b03 | 16 | 12 | finished | $5.90 |
| b04 | 20 | 16 | finished | $5.17 |
| b05 | 14 | 10 | finished | $5.79 |
| b06 | 19 | 15 | finished | $5.47 |
| b07 | 20 | 16 | finished | $5.30 |
| b08 | 19 | 15 | finished | $6.35 |

## Builder failures

- b01: exit 0, errors none, no valid bot in T4, T5, T6
- b02: exit 0, errors none, no valid bot in T4, T5, T6
- b03: exit 0, errors none, no valid bot in T4, T5, T6
- b04: exit 0, errors none, no valid bot in T4, T5, T6
- b05: exit 0, errors none, no valid bot in T4, T5, T6
- b06: exit 0, errors none, no valid bot in T4, T5, T6
- b07: exit 0, errors none, no valid bot in T4, T5, T6
- b08: exit 0, errors none, no valid bot in T4, T5, T6

## Cost

Total $43.83; per builder: b01 $4.55, b02 $5.29, b03 $5.90, b04 $5.17, b05 $5.79, b06 $5.47, b07 $5.30, b08 $6.35

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 44% at the first reading, 70% at the last. It counts everything on the same login, including your own sessions.
