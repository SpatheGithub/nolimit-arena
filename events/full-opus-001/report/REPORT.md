# Report: full-opus-001

## Event card

- **Variant:** nlhe: No-limit Texas hold'em: 2 hole cards, a 5-card board, best five of seven.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 60 min, 6 tournament(s) of 1000 iterations, patch windows 20 min; time scale 1
- **Field:** 8 builders; seed 4062263806

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 | T2 | T3 | T4 | T5 | T6 |
| -: | :- | :- | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | opus | opponent_model | 733.9 | 34.0 | 36.4 | 34.9 | 34.8 | 35.2 | 34.6 |
| 2 | b04 | opus | pressure | 702.4 | 34.0 | 31.6 | 34.1 | 34.4 | 31.8 | 34.4 |
| 3 | b02 | opus | free choice | 681.9 | 34.9 | 33.8 | 32.2 | 30.6 | 33.1 | 32.5 |
| 4 | b05 | opus | free choice | 657.6 | 29.7 | 32.2 | 30.8 | 29.8 | 32.1 | 31.9 |
| 5 | b01 | opus | free choice | 656.0 | 29.7 | 29.3 | 30.2 | 32.2 | 31.4 | 31.9 |
| 6 | b08 | opus | free choice | 652.7 | 32.0 | 32.1 | 32.8 | 32.0 | 30.3 | 29.7 |
| 7 | b03 | opus | minimal_robust | 637.9 | 30.2 | 29.3 | 31.3 | 30.4 | 30.7 | 30.0 |
| 8 | b07 | opus | equity_tables | 632.7 | 30.5 | 30.4 | 28.6 | 30.7 | 30.5 | 30.1 |

## How each bot played

- Every bot finished in the top 3 on 36–39% of tables. What separated them was the heads-up fight for 1st: b06 and b04 won 58–59% of their heads-up finishes, b01 and b05 only 42%. 1st pays 100 points and 2nd pays 60, the biggest step in the points table.
- The two winners didn't play the most hands; they priced their aggression. Both re-priced steals and all-in re-steals from each opponent's observed fold rates and shoved whenever the price was right. b03 played more hands than either and finished 7th. Most other bots had re-steal rules too, but gated them more tightly with ICM risk penalties or fixed hand caps.
- Surviving wasn't enough. b07 and b02 had the fewest early exits (7th or 8th on 22–23% of tables) but won only 10–13% of tables. b04 had the most early exits (32%) and still finished 2nd, because it won 17%.
- Both top bots made their last code change after T3. Identical code moved by up to 3 points per table between tournaments (b02, b04, b08), so single results are mostly noise. b06 winning five tournaments in a row is the one clearly repeatable result.

| Rank | Team | Won | Heads-up won | Top 3 | Last two | VPIP | PFR | AF |
| -: | :- | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | 17% | 59% | 39% | 24% | 24% | 18% | 3.4 |
| 2 | b04 | 17% | 58% | 38% | 32% | 25% | 19% | 2.1 |
| 3 | b02 | 13% | 51% | 38% | 23% | 18% | 14% | 2.4 |
| 4 | b05 | 10% | 42% | 38% | 24% | 22% | 18% | 2.5 |
| 5 | b01 | 10% | 42% | 37% | 25% | 20% | 17% | 3.0 |
| 6 | b08 | 12% | 49% | 37% | 24% | 23% | 17% | 3.3 |
| 7 | b03 | 11% | 46% | 36% | 27% | 27% | 21% | 3.1 |
| 8 | b07 | 10% | 49% | 36% | 22% | 23% | 15% | 1.9 |

Pooled over the finished tournaments. Heads-up won: of the tables where the bot was one of the last two, the share it won. Last two: the share of tables where it finished in the last two places. AF: bets and raises per call after the flop.

### 1. b06 (opponent_model)

**Strategy.** Kept running stats on every opponent at the table: how often each folds to a raise, to a re-raise and to a bet, starting from default guesses. Before the flop it opened wider when the players behind fold a lot, and shoved all-in over a single raise with 8–30 big blinds whenever that raiser folded often enough to make it pay. After the flop it bet or folded: value bets, bluffs against players who fold, few calls.

**How it scored.** Won 17% of tables, the most, and 59% of its heads-up finishes. It made 3.4 bets or raises for every call after the flop, the most aggressive in the field, while winning only half its showdowns, so its edge came from making opponents fold. Its builder measured the re-steal shove as its biggest single gain (about +3 points per table) and tested every change against three kinds of field. Its last change came after T3, and that version won T4, T5 and T6.

**Lesson.** Track each opponent's fold rates and shove when they fold too often. The price is variance: it still went out 7th or 8th on 24% of tables, mostly when its own shoves got called.

### 2. b04 (pressure)

**Strategy.** Pressure before the flop: wide opens from late position (48% of hands on the button, 62% in the small blind), adjusted to how often the players behind fold. It shoved all-in with 13 big blinds or less, and re-stole all-in with up to 32, whenever the ICM value counting fold equity was positive.

**How it scored.** The same winning profile as b06: it won 17% of tables and 58% of its heads-up finishes. The price was the most early exits in the field (7th or 8th on 32% of tables), and after the flop it called more than any other bot. Its code didn't change after T3 and scored 34.4, 31.8 and 34.4 points per table in T4–T6.

**Lesson.** Pressure wins tables even with a high bust rate, because 1st pays so much more than surviving. A 3-point drop can be pure noise.

### 3. b02 (free choice)

**Strategy.** The tightest bot: it put money in on 18% of hands. It precomputed ICM tables and decided shoves, calls and re-shoves by ICM-weighted expected points, adjusting its estimate of how often opponents call its shoves to how they actually responded.

**How it scored.** Won T1 and had the second-fewest early exits (23%), but won only 51% of its heads-up finishes, so it took 1st on 13% of tables against 17% for the top two. Its code was identical for T2–T4, yet it slid from 33.8 to 30.6 points per table.

**Lesson.** Tight ICM play buys a safe top 5, not wins.

### 4. b05 (free choice)

**Strategy.** The most engineered bot: its own vectorized hand evaluator (with a 30 MB lookup table), Monte Carlo equity after the flop against opponent ranges narrowed by how they bet, and ICM for all-in decisions.

**How it scored.** Played the most pots after the flop and finished 2nd on 14% of tables, but won only 42% of its heads-up finishes, the lowest, so it took 1st on just 10%. It climbed from 7th after T1 to 4th.

**Lesson.** Precise postflop math didn't turn into wins. Winning heads-up as often as b06 would have been worth about 1.6 points per table, enough for 3rd.

### 5. b01 (free choice)

**Strategy.** Push or fold with 14 big blinds or less, scored in ICM points; Monte Carlo equity after the flop against opponents' ranges; ICM checks on big calls; per-opponent stats on raising, shoving and folding.

**How it scored.** Last after T1 and T2, then climbed to 5th as its patches lifted it from 29.3 points per table in T2 to 32.2 in T4. Like b05, it finished 2nd often (14% of tables, the most) and won only 42% of its heads-up finishes.

**Lesson.** Winning heads-up as often as b06 would have been worth about 1.6 points per table, enough for 3rd. Its notes don't show why it lost heads-up; the hand logs could.

### 6. b08 (free choice)

**Strategy.** Position-based opens and Nash-style push/fold thresholds, widened when few players are left (80% of hands heads-up) and against tight players; an ICM premium on all-in calls, dropped heads-up; aggressive after the flop (3.3 bets or raises per call).

**How it scored.** About 32 points per table in T1–T4 and 3rd overall after T4, then 30.3 and 29.7. Its T6 code was its T4 code restored, so the drop wasn't a bad patch. It won 53% of its showdowns, the best in the field, and missed the top 5 by 3.3 weighted points, well within noise.

**Lesson.** A sound, balanced bot lands on the cut line. Getting safely inside needs an edge that repeats, like b06's.

### 7. b03 (minimal_robust)

**Strategy.** Simple rules with no simulation at decision time (about 0.1 ms per decision): push or fold by chip value, re-shoves with up to 28 big blinds, fixed thresholds for 3-bets and calls, and a safety net that turns any error into a safe action.

**How it scored.** The loosest bot (played 27% of hands, raised 21%). It went out 7th or 8th on 27% of tables and never placed above 5th in a tournament. Its robustness bought nothing, because no bot in this field ever crashed or timed out.

**Lesson.** Robustness is the floor, not an edge. Loose play that isn't priced against specific opponents leaks chips.

### 8. b07 (equity_tables)

**Strategy.** Everything precomputed (about 25 µs per decision): equity tables against ranges, a push/fold chart, and an ICM premium on all-in calls. Its builder estimated it needed about 80% equity to call off its stack with four or more players left.

**How it scored.** The fewest early exits (22%), but also the fewest 2nd places (10%), the joint-fewest wins (10%), and the most passive play after the flop (1.9 bets or raises per call). Its builder warned that its tight all-in calling was "exploitable by bots that shove relentlessly", and the two bots built to apply exactly that pressure finished 1st and 2nd.

**Lesson.** Folding to pressure keeps you alive but hands the table to whoever applies it.

_Analysis by Claude (Opus 5.5) after the event, from each builder's notes (bots/<team>/NOTES.T6.md) and the six tournament summaries._

## Rank view

Each bot's final rank across 2,000 bootstrap resamples of whole tables: every resample redraws each finished tournament's tables with replacement, so one bot's points stay another's loss. The top 5 at a regional advance, so P(top 5) matters more than the mean. 90% range: the 5th to 95th percentile of the rank.

| Bot | Weighted (95% CI) | P(1st) | P(top 5) | Median rank | 90% range | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | P(7) | P(8) |
| :- | -: | -: | -: | -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 733.9 ± 20.8 | 97% | 100% | 1 | 1–1 | 97% | 3% | · | · | · | · | · | · |
| b04 | 702.4 ± 20.8 | 3% | 100% | 2 | 2–3 | 3% | 88% | 9% | · | · | · | · | · |
| b02 | 681.9 ± 18.5 | 0% | 100% | 3 | 2–4 | · | 9% | 84% | 6% | 1% | · | · | · |
| b05 | 657.6 ± 18.1 | 0% | 72% | 5 | 4–7 | · | · | 3% | 39% | 30% | 21% | 5% | 2% |
| b01 | 656.0 ± 18.1 | 0% | 66% | 5 | 4–7 | · | · | 3% | 32% | 32% | 25% | 7% | 1% |
| b08 | 652.7 ± 18.3 | 0% | 52% | 5 | 4–7 | · | · | 2% | 21% | 29% | 34% | 11% | 3% |
| b03 | 638.0 ± 17.9 | 0% | 7% | 7 | 5–8 | · | · | · | 1% | 5% | 14% | 47% | 32% |
| b07 | 632.7 ± 17.2 | 0% | 2% | 8 | 6–8 | · | · | · | · | 2% | 6% | 30% | 61% |

## Field profile

How the bots played, from the hand logs of T1–T6 (4,626,883 bot-hands; every version a team entered, pooled). The field row pools every bot's decisions, with the lowest and highest bot in brackets. Most per-bot rates rest on thousands of decisions, so their 95% intervals are within about ±3 points; † marks a rate on fewer than 300.

Spots: a *steal* is a first-in raise from the cutoff, button or small blind with 3+ players dealt; *folds to a steal* counts the blinds facing one. A *3-bet* re-raises a single open; *folds to a 3-bet* is the opener facing one. A *shove* is a preflop all-in raise. A *c-bet* is the preflop raiser betting the flop when checked to. *Calls a river bet* is the first river decision facing a bet. Showdown rates count hands that saw the flop.

### Preflop

| Bot | VPIP | PFR | Steals | Folds to a steal | 3-bets an open | Folds to a 3-bet | Calls a shove |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b06 | 24% | 18% | 45% | 72% | 8% | 69% | 21% |
| b04 | 25% | 19% | 44% | 63% | 10% | 79% | 15% |
| b02 | 19% | 14% | 37% | 79% | 5% | 73% | 19% |
| b05 | 22% | 18% | 47% | 81% | 3% | 85% | 15% |
| b01 | 20% | 17% | 45% | 80% | 4% | 85% | 12% |
| b08 | 23% | 17% | 45% | 76% | 5% | 82% | 16% |
| b03 | 27% | 21% | 60% | 81% | 4% | 84% | 13% |
| b07 | 23% | 15% | 36% | 74% | 4% | 74% | 17% |
| **Field** | 23% (19%–27%) | 17% (14%–21%) | 45% (36%–60%) | 76% (63%–81%) | 5% (3%–10%) | 80% (69%–85%) | 16% (12%–21%) |

### After the flop, and heads-up

| Bot | C-bets | Folds to a c-bet | Calls a river bet | Went to showdown | Won at showdown | Raises first in heads-up | Folds to a heads-up raise |
| :- | -: | -: | -: | -: | -: | -: | -: |
| b06 | 70% | 77% | 35% | 51% | 49% | 86% | 64% |
| b04 | 75% | 64% | 48% | 49% | 46% | 76% | 32% |
| b02 | 64% | 74% | 42% | 57% | 52% | 69% | 65% |
| b05 | 69% | 45% | 39% | 48% | 48% | 76% | 67% |
| b01 | 68% | 60% | 41% | 52% | 46% | 66% | 66% |
| b08 | 84% | 67% | 34% | 47% | 52% | 73% | 45% |
| b03 | 61% | 78% | 35% | 45% | 51% | 89% | 66% |
| b07 | 41% | 75% | 29% | 45% | 50% | 65% | 57% |
| **Field** | 67% (41%–84%) | 69% (45%–78%) | 38% (29%–48%) | 49% (45%–57%) | 49% (46%–52%) | 75% (65%–89%) | 58% (32%–67%) |

### VPIP by stack and by players dealt

Hypotheses 2 and 8 in docs/FIELD_STUDY.md: a bot that plays the same hands at every stack depth, or as wide heads-up as eight-handed, keeps one set of thresholds. Stack: the bot's own chips at the start of the hand.

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb | 7–8 dealt | 5–6 dealt | 3–4 dealt | Heads-up |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 51% | 32% | 25% | 18% | 18% | 28% | 42% | 57% |
| b04 | 37% | 23% | 31% | 22% | 22% | 28% | 38% | 62% |
| b02 | 37% | 23% | 18% | 15% | 14% | 20% | 35% | 48% |
| b05 | 22% | 20% | 25% | 22% | 20% | 22% | 30% | 51% |
| b01 | 29% | 20% | 22% | 18% | 17% | 22% | 32% | 48% |
| b08 | 34% | 26% | 25% | 19% | 19% | 25% | 38% | 57% |
| b03 | 26% | 26% | 31% | 26% | 24% | 28% | 37% | 57% |
| b07 | 25% | 18% | 23% | 24% | 22% | 21% | 29% | 48% |
| **Field** | 29% (22%–51%) | 23% (18%–32%) | 25% (18%–31%) | 21% (15%–26%) | 20% (14%–24%) | 24% (20%–28%) | 35% (29%–42%) | 54% (48%–62%) |

### Calls a shove, by own stack

| Bot | <10 bb | 10–20 bb | 20–40 bb | 40+ bb |
| :- | -: | -: | -: | -: |
| b06 | 41% | 21% | 17% | 17% |
| b04 | 25% | 14% | 11% | 12% |
| b02 | 22% | 19% | 15% | 23% |
| b05 | 18% | 13% | 13% | 15% |
| b01 | 13% | 13% | 10% | 14% |
| b08 | 29% | 14% | 10% | 12% |
| b03 | 17% | 11% | 11% | 12% |
| b07 | 24% | 13% | 14% | 18% |
| **Field** | 22% (13%–41%) | 15% (11%–21%) | 13% (10%–17%) | 15% (12%–23%) |

### Bet sizes

Hypothesis 10: one fixed size is a pattern opponents can read. Opens are first-in raises, in big blinds; bets are after the flop with nothing to call, as a share of the pot.

| Bot | Usual open | Opens at it | Usual bet | Bets at it |
| :- | -: | -: | -: | -: |
| b06 | 2.5 bb | 50% | 50% pot | 43% |
| b04 | 2.5 bb | 62% | 60% pot | 46% |
| b02 | 2.5 bb | 42% | 50% pot | 73% |
| b05 | 2.5 bb | 52% | 60% pot | 55% |
| b01 | 2.5 bb | 54% | 50% pot | 30% |
| b08 | 2.5 bb | 46% | 50% pot | 43% |
| b03 | 2.5 bb | 83% | 50% pot | 40% |
| b07 | 2.5 bb | 66% | 60% pot | 35% |

### Biggest leaks per bot

A leak is a spot where the bot's result as the player facing the action falls below the rest of the field's average result in the same spot, in big blinds per 100 hands it played (± a 95% interval). The result counts the whole hand, so it also carries how the bot got to the spot. Chips aren't points, but the bots that leak chips to pressure bust first.

- **b06**: facing a shove: -0.2 ± 0.5 bb/100 (calls 21% against 15%) — within noise; heads-up vs a raise: -0.1 ± 0.2 bb/100 (calls 23% against 31%) — within noise.
- **b04**: facing a river bet: -4.2 ± 0.7 bb/100 (folds 46% against 60%); facing a c-bet: -2.4 ± 0.7 bb/100 (calls 35% against 28%).
- **b02**: facing a steal: -0.4 ± 0.4 bb/100 (folds 79% against 75%).
- **b05**: facing an open: -1.0 ± 0.8 bb/100 (folds 89% against 86%); facing a steal: -0.7 ± 0.5 bb/100 (folds 81% against 75%).
- **b01**: facing a river bet: -2.3 ± 0.6 bb/100 (folds 54% against 58%); facing a steal: -0.7 ± 0.4 bb/100 (folds 80% against 75%).
- **b08**: facing a shove: -0.4 ± 0.5 bb/100 (raises 2% against 1%) — within noise; heads-up vs a raise: -0.2 ± 0.2 bb/100 (calls 53% against 26%) — within noise.
- **b03**: facing a shove: -1.7 ± 0.5 bb/100 (calls 13% against 16%); facing a steal: -1.4 ± 0.4 bb/100 (folds 81% against 75%).
- **b07**: facing a steal: -2.5 ± 0.5 bb/100 (calls 23% against 16%); facing a shove: -0.7 ± 0.5 bb/100 (calls 17% against 16%).

## Exploit board

Which bots made money from each kind of pressure, and which lost the most facing it. *Field folds*: how often the bot facing that aggression folded, pooled (lowest and highest bot in brackets). *Won most from it*: big blinds per 100 hands won in the hands where the bot applied it, and how often everyone folded at once. *Lost most facing it*: the leak measure above for that spot.

| Aggression | Field folds | Won most from it (bb/100) | Lost most facing it (bb/100 vs field) |
| :- | -: | :- | :- |
| Steal | 76% (63%–81%) | b06 +6.1 (all fold 63%), b03 +5.9 (all fold 55%) | b07 -2.5, b03 -1.4 |
| 3-bet | 80% (69%–85%) | b04 +8.9 (all fold 70%), b06 +7.0 (all fold 82%) | b04 -1.0, b01 -0.5 |
| Preflop shove | 83% (79%–88%) | b04 +8.5 (all fold 70%), b06 +6.9 (all fold 74%) | b03 -1.7, b07 -0.7 |
| Heads-up raise | 58% (32%–67%) | b06 +0.3 (all fold 59%), b07 +0.3 (all fold 60%) | b05 -0.3, b08 -0.2 |
| C-bet | 69% (45%–78%) | b08 +6.2 (all fold 65%), b03 +5.9 (all fold 66%) | b04 -2.4, b07 -0.6 |
| River bet | 58% (46%–67%) | b03 +6.5 (all fold 58%), b07 +6.1 (all fold 53%) | b04 -4.2, b01 -2.3 |

## T1 (weight 1)

1,000 tables, 127,458 hands, 20 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b02 | 34.90 ± 2.01 | 1000 | 19% | 14% | 0 | 50 |
| 2 ≈ | b04 | 33.99 ± 2.23 | 1000 | 25% | 19% | 0 | 100 |
| 3 ≈ | b06 | 33.95 ± 2.11 | 1000 | 25% | 19% | 0 | 100 |
| 4 ≈ | b08 | 32.01 ± 1.92 | 1000 | 23% | 17% | 0 | 100 |
| 5 ≈ | b07 | 30.52 ± 1.76 | 1000 | 24% | 15% | 0 | 100 |
| 6 ≈ | b03 | 30.18 ± 1.99 | 1000 | 28% | 22% | 0 | 100 |
| 7 ≈ | b05 | 29.73 ± 1.73 | 1000 | 22% | 18% | 0 | 300 |
| 8 | b01 | 29.72 ± 1.89 | 1000 | 21% | 17% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T2 (weight 2)

1,000 tables, 127,380 hands, 17 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 36.36 ± 2.16 | 1000 | 24% | 19% | 0 | 50 |
| 2 ≈ | b02 | 33.84 ± 2.00 | 1000 | 19% | 14% | 0 | 50 |
| 3 ≈ | b05 | 32.15 ± 1.92 | 1000 | 23% | 18% | 0 | 200 |
| 4 ≈ | b08 | 32.08 ± 1.93 | 1000 | 23% | 17% | 0 | 50 |
| 5 ≈ | b04 | 31.59 ± 2.14 | 1000 | 23% | 17% | 0 | 100 |
| 6 ≈ | b07 | 30.39 ± 1.83 | 1000 | 24% | 15% | 0 | 50 |
| 7 ≈ | b03 | 29.32 ± 1.92 | 1000 | 28% | 22% | 0 | 100 |
| 8 | b01 | 29.27 ± 1.76 | 1000 | 20% | 16% | 0 | 300 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T3 (weight 3)

1,000 tables, 127,041 hands, 25 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 34.94 ± 2.14 | 1000 | 23% | 17% | 0 | 100 |
| 2 ≈ | b04 | 34.07 ± 2.17 | 1000 | 26% | 20% | 0 | 100 |
| 3 ≈ | b08 | 32.81 ± 2.01 | 1000 | 23% | 18% | 0 | 100 |
| 4 ≈ | b02 | 32.23 ± 2.00 | 1000 | 18% | 14% | 0 | 100 |
| 5 ≈ | b03 | 31.32 ± 1.86 | 1000 | 25% | 20% | 0 | 100 |
| 6 ≈ | b05 | 30.80 ± 1.86 | 1000 | 22% | 18% | 0 | 300 |
| 7 ≈ | b01 | 30.18 ± 1.87 | 1000 | 20% | 17% | 0 | 300 |
| 8 | b07 | 28.64 ± 1.76 | 1000 | 24% | 15% | 0 | 100 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T4 (weight 4)

1,000 tables, 127,019 hands, 15 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 34.77 ± 2.18 | 1000 | 23% | 18% | 0 | 50 |
| 2 ≈ | b04 | 34.45 ± 2.19 | 1000 | 26% | 20% | 0 | 100 |
| 3 ≈ | b01 | 32.23 ± 1.93 | 1000 | 21% | 17% | 0 | 300 |
| 4 ≈ | b08 | 32.04 ± 1.98 | 1000 | 22% | 17% | 0 | 50 |
| 5 ≈ | b07 | 30.71 ± 1.78 | 1000 | 21% | 15% | 0 | 50 |
| 6 ≈ | b02 | 30.62 ± 1.93 | 1000 | 18% | 14% | 0 | 50 |
| 7 ≈ | b03 | 30.41 ± 1.86 | 1000 | 26% | 21% | 0 | 100 |
| 8 | b05 | 29.78 ± 1.83 | 1000 | 23% | 18% | 0 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T5 (weight 5)

1,000 tables, 127,487 hands, 17 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 35.19 ± 2.15 | 1000 | 24% | 18% | 0 | 50 |
| 2 ≈ | b02 | 33.06 ± 1.94 | 1000 | 18% | 14% | 0 | 50 |
| 3 ≈ | b05 | 32.09 ± 1.85 | 1000 | 22% | 18% | 0 | 200 |
| 4 ≈ | b04 | 31.78 ± 2.18 | 1000 | 25% | 20% | 0 | 100 |
| 5 ≈ | b01 | 31.36 ± 1.87 | 1000 | 20% | 17% | 0 | 300 |
| 6 ≈ | b03 | 30.75 ± 1.91 | 1000 | 26% | 21% | 0 | 100 |
| 7 ≈ | b07 | 30.46 ± 1.87 | 1000 | 22% | 15% | 0 | 50 |
| 8 | b08 | 30.32 ± 1.92 | 1000 | 22% | 17% | 0 | 50 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## T6 (weight 6)

1,000 tables, 126,323 hands, 16 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b06 | 34.56 ± 2.15 | 1000 | 23% | 18% | 0 | 50 |
| 2 ≈ | b04 | 34.38 ± 2.18 | 1000 | 26% | 20% | 0 | 100 |
| 3 ≈ | b02 | 32.48 ± 1.98 | 1000 | 18% | 14% | 0 | 50 |
| 4 ≈ | b05 | 31.93 ± 1.87 | 1000 | 23% | 18% | 0 | 200 |
| 5 ≈ | b01 | 31.91 ± 1.87 | 1000 | 20% | 17% | 0 | 300 |
| 6 ≈ | b07 | 30.05 ± 1.81 | 1000 | 21% | 15% | 0 | 50 |
| 7 ≈ | b03 | 29.97 ± 1.88 | 1000 | 28% | 23% | 0 | 100 |
| 8 | b08 | 29.72 ± 1.93 | 1000 | 22% | 17% | 0 | 50 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| equity_tables | 632.7 ± 0.0 (n=1) |
| free choice | 662.0 ± 13.1 (n=4) |
| minimal_robust | 637.9 ± 0.0 (n=1) |
| opponent_model | 733.9 ± 0.0 (n=1) |
| pressure | 702.4 ± 0.0 (n=1) |

| Model | Score |
| :- | -: |
| opus | 669.4 ± 23.9 (n=8) |

## Substitutions

| Team | T1 timeout/error/illegal/hang | T2 timeout/error/illegal/hang | T3 timeout/error/illegal/hang | T4 timeout/error/illegal/hang | T5 timeout/error/illegal/hang | T6 timeout/error/illegal/hang |
| :- | :- | :- | :- | :- | :- | :- |
| b01 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
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
| 5 | 8 of 8 |
| 10 | 8 of 8 |
| 20 | 8 of 8 |
| 40 | 8 of 8 |
| 60 | 8 of 8 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 40 | 31 | finished | $23.74 |
| b02 | 45 | 36 | finished | $22.41 |
| b03 | 41 | 32 | finished | $22.88 |
| b04 | 48 | 39 | finished | $26.03 |
| b05 | 41 | 32 | finished | $20.39 |
| b06 | 53 | 44 | finished | $22.14 |
| b07 | 42 | 33 | finished | $16.58 |
| b08 | 39 | 30 | finished | $17.99 |

## Builder failures

None.

## Cost

Total $172.16; per builder: b01 $23.74, b02 $22.41, b03 $22.88, b04 $26.03, b05 $20.39, b06 $22.14, b07 $16.58, b08 $17.99

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 12% at the first reading, 54% at the last. It counts everything on the same login, including your own sessions.
