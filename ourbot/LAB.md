# Lab results

Written by `python -m ourbot.lab report` at 2026-11-03 03:50 for bot code c76897b029af.
Δ is the paired difference from `base` (the house icm_pushfold) over the same tables, with a 95% interval. Points per table under each field's points table; win = 1st at the table.

## nlhe

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| no_shove20 | 3000 | 31.09 | +1.41 ± 1.12 | 10.2 | +1.2 |
| no_respect | 3000 | 30.06 | +0.38 ± 1.13 | 9.3 | +0.4 |
| only_resteal | 3000 | 29.95 | +0.27 ± 1.08 | 9.9 | +1.0 |
| all | 3000 | 29.93 | +0.25 ± 1.15 | 8.8 | -0.1 |
| no_noflat | 3000 | 29.91 | +0.23 ± 1.13 | 9.2 | +0.2 |
| base | 3000 | 29.68 | · | 9.0 | · |
| no_resteal | 3000 | 29.68 | -0.00 ± 1.08 | 8.6 | -0.4 |
| only_respect | 3000 | 29.48 | -0.20 ± 1.00 | 8.2 | -0.8 |
| only_shove20 | 3000 | 29.47 | -0.21 ± 1.05 | 8.7 | -0.3 |
| only_noflat | 3000 | 29.34 | -0.34 ± 0.99 | 8.8 | -0.2 |

## shortdeck

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| no_resteal | 150 | 24.64 | +6.21 ± 7.72 | 12.0 | +4.0 |
| no_respect | 100 | 26.97 | +4.68 ± 8.28 | 19.0 | +7.0 |
| all | 100 | 25.00 | +2.71 ± 8.34 | 13.0 | +1.0 |
| no_noflat | 100 | 23.44 | +1.15 ± 7.16 | 13.0 | +1.0 |
| only_resteal | 150 | 22.00 | +0.47 ± 7.63 | 12.0 | +1.0 |
| base | 100 | 22.29 | · | 12.0 | · |
| only_respect | 100 | 20.27 | -2.02 ± 8.42 | 11.0 | -1.0 |
| no_shove20 | 100 | 19.94 | -2.35 ± 8.08 | 11.0 | -1.0 |
| only_shove20 | 100 | 17.53 | -4.76 ± 7.22 | 6.0 | -6.0 |
| only_noflat | 100 | 17.23 | -5.06 ± 7.20 | 7.0 | -5.0 |

