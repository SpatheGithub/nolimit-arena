# Report: m5-smoke

## Event card

- **Variant:** nlhe: No-limit Texas hold'em: 2 hole cards, a 5-card board, best five of seven.
- **Points table (standard):** 1st 100, 2nd 60, 3rd 40, 4th 25, 5th 15, 6th 10, 7th 5, 8th 0
- **Blinds (doubling):** 10/20, 20/40, 40/80, 80/160, 160/320, 320/640, 640/1280, 1280/2560, every 25 hands; cap 200 hands
- **Schedule:** build 4 min, 1 tournament(s) of 400 iterations, patch windows 0 min; time scale 1
- **Field:** 2 builders; seed 5

## Final weighted leaderboard

| Rank | Team | Model | Archetype | Weighted score | T1 |
| -: | :- | :- | :- | -: | -: |
| 1 | b02 | sonnet | free choice | 37.5 | 37.5 |
| 2 | b01 | sonnet | free choice | 27.6 | 27.6 |

## T1 (weight 1)

400 tables, 61,859 hands, 8 s on 4 workers; 29 tables reached the hand cap.

| Rank | Team | Points/table (95% CI) | Tables | VPIP | PFR | Subs | p99 µs |
| -: | :- | :- | -: | -: | -: | -: | -: |
| 1 | b02 | 37.52 ± 3.67 | 400 | 41% | 6% | 1 | 25 |
| 2 | b01 | 27.59 ± 2.28 | 400 | 10% | 3% | 0 | 25 |

≈ marks a rank whose 95% interval overlaps the next one's: the order between them is within noise.

## By archetype and by model

Weighted score, mean ± 95% interval across teams. Small groups say little.

| Archetype | Score |
| :- | -: |
| free choice | 32.6 ± 9.7 (n=2) |

| Model | Score |
| :- | -: |
| sonnet | 32.6 ± 9.7 (n=2) |

## Substitutions

| Team | T1 timeout/error/illegal/hang |
| :- | :- |
| b01 | 0/0/0/0 |
| b02 | 0/0/0/1 |

## Submission timeline

Teams with an accepted bot by build minute (scaled by the time scale):

| Minute | Teams with an accepted bot |
| -: | -: |
| 4 | 2 of 2 |

## Builder runs

A run is one `claude -p` process. A clock-check resume restarts a builder that ended its turn with time left. "Stopped by" is how the last window ended.

| Team | Runs | Clock-check resumes | Stopped by | Cost |
| :- | -: | -: | :- | -: |
| b01 | 0 | 0 | unknown | $0.09 |
| b02 | 0 | 0 | unknown | $0.08 |

## Builder failures

None.

## Cost

Total $0.17; per builder: b01 $0.09, b02 $0.08

These are Claude Code's API-price estimates; on a Claude plan login nothing is billed per token.

Plan usage meter (five-hour window): 56% at the first reading, 57% at the last. It counts everything on the same login, including your own sessions.
