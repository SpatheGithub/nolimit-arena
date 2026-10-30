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
