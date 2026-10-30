# Report: calibrate-opus

## Event card

- **Variant:** nlhe: No-limit Texas hold'em: 2 hole cards, a 5-card board, best five of seven.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 15 min, 1 tournament(s) of 400 iterations, patch windows 0 min; time scale 1
- **Field:** 2 builders; seed 11

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 |
| -: | :- | :- | :- | -: | -: |
| 1 | b01 | opus | free choice | 30.2 | 30.2 |
| 2 | b02 | opus | free choice | 30.1 | 30.1 |

## T1 (weight 1)

400 tables, 54,054 hands, 8 s on 4 workers; 0 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 ≈ | b01 | 30.19 ± 3.03 | 400 | 20% | 16% | 0 | 200 |
| 2 | b02 | 30.15 ± 2.92 | 400 | 23% | 19% | 0 | 200 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 30.2 ± 0.0 (n=2) |

| Model | Score |
| :- | -: |
| opus | 30.2 ± 0.0 (n=2) |

## Substitutions

| Team | T1 timeout/error/illegal/hang |
| :- | :- |
| b01 | 0/0/0/0 |
| b02 | 0/0/0/0 |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 5 | 2 of 2 |
| 10 | 2 of 2 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 5 | 4 | finished | $1.32 |
| b02 | 5 | 4 | finished | $1.01 |

## Builder failures

None.

## Cost

Total $2.32; per builder: b01 $1.32, b02 $1.01

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 0% at the first reading, 5% at the last. It counts everything on the same login, including your own sessions.
