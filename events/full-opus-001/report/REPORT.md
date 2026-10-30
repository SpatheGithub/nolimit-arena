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
