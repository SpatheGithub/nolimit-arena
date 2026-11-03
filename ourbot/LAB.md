# Lab results

Written by `python -m ourbot.lab report` at 2026-11-03 10:41; our bot's code is now 7911fd1208fd.
Δ is the paired difference from `base` (our bot with every switch off, which is the house icm_pushfold) over the same tables, with a 95% interval. Points are per table, under each field's points table; a win is 1st at the table.

## switches: nlhe (bot code c76897b029af)

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

## switches: shortdeck (bot code c76897b029af)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| no_noflat | 3000 | 21.85 | +0.56 ± 1.42 | 11.5 | +0.0 |
| no_respect | 3000 | 21.71 | +0.42 ± 1.44 | 12.2 | +0.7 |
| base | 3000 | 21.30 | · | 11.5 | · |
| no_shove20 | 3000 | 21.07 | -0.23 ± 1.43 | 11.2 | -0.3 |
| only_respect | 3000 | 21.07 | -0.23 ± 1.37 | 10.6 | -0.8 |
| no_resteal | 3000 | 20.99 | -0.31 ± 1.39 | 10.9 | -0.5 |
| only_resteal | 3000 | 20.94 | -0.35 ± 1.37 | 10.8 | -0.6 |
| only_shove20 | 3000 | 20.75 | -0.54 ± 1.40 | 10.8 | -0.7 |
| all | 3000 | 20.67 | -0.63 ± 1.45 | 10.7 | -0.8 |
| only_noflat | 3000 | 19.96 | -1.34 ± 1.36 | 10.0 | -1.5 |

## switches: royal (bot code c76897b029af)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| only_respect | 3000 | 11.71 | +0.04 ± 0.07 | 7.9 | +0.0 |
| base | 3000 | 11.67 | · | 7.8 | · |
| only_noflat | 3000 | 11.67 | +0.00 ± 0.00 | 7.8 | +0.0 |
| no_resteal | 3000 | 11.62 | -0.06 ± 0.87 | 8.0 | +0.1 |
| no_shove20 | 3000 | 11.62 | -0.06 ± 0.48 | 7.8 | -0.1 |
| only_shove20 | 3000 | 11.59 | -0.09 ± 0.87 | 7.9 | +0.1 |
| only_resteal | 3000 | 11.58 | -0.09 ± 0.48 | 7.7 | -0.1 |
| all | 3000 | 11.38 | -0.30 ± 0.94 | 7.7 | -0.1 |
| no_noflat | 3000 | 11.38 | -0.30 ± 0.94 | 7.7 | -0.1 |
| no_respect | 3000 | 11.35 | -0.32 ± 0.94 | 7.7 | -0.1 |

## bases: nlhe-x (bot code c76897b029af)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| winner_e2 | 3000 | 38.25 | +8.20 ± 1.61 | 21.2 | +12.0 |
| winner_e1 | 3000 | 34.55 | +4.50 ± 1.52 | 16.3 | +7.2 |
| best | 3000 | 31.04 | +1.00 ± 1.13 | 10.1 | +0.9 |
| base | 3000 | 30.05 | · | 9.2 | · |
| house_tag | 3000 | 29.42 | -0.62 ± 1.15 | 7.7 | -1.5 |

## icm: nlhe (bot code 0e22d33528b6)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| chipev | 2500 | 31.00 | +0.26 ± 1.34 | 10.9 | +1.4 |
| base | 2450 | 30.81 | · | 9.6 | · |

## v2: nlhe-x (bot code 674bd74249cd)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| chipsteal | 3000 | 37.62 | +7.52 ± 1.48 | 20.4 | +11.2 |
| chipsteal_chipev | 3000 | 37.00 | +6.91 ± 1.50 | 19.8 | +10.5 |
| chipsteal_flat | 3000 | 36.88 | +6.78 ± 1.46 | 18.7 | +9.4 |
| v1 | 3000 | 35.62 | +5.53 ± 1.37 | 15.2 | +5.9 |
| base | 3000 | 30.09 | · | 9.3 | · |

## v2: shortdeck (bot code 674bd74249cd)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| chipsteal | 3000 | 25.74 | +4.56 ± 1.57 | 16.6 | +5.9 |
| chipsteal_flat | 3000 | 24.68 | +3.51 ± 1.54 | 15.2 | +4.5 |
| v1 | 3000 | 24.03 | +2.86 ± 1.50 | 14.1 | +3.4 |
| chipsteal_chipev | 3000 | 23.92 | +2.75 ± 1.57 | 15.0 | +4.3 |
| base | 3000 | 21.17 | · | 10.7 | · |

## v2: royal (bot code 674bd74249cd)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| base | 3000 | 11.67 | · | 7.8 | · |
| v1 | 3000 | 11.51 | -0.17 ± 1.14 | 8.2 | +0.3 |
| chipsteal_flat | 3000 | 11.40 | -0.27 ± 1.13 | 8.2 | +0.3 |
| chipsteal_chipev | 3000 | 11.14 | -0.53 ± 1.16 | 7.8 | -0.0 |
| chipsteal | 3000 | 11.07 | -0.60 ± 1.18 | 7.8 | +0.0 |

## calib: royal (bot code 3b9709e3c856)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| base | 3000 | 11.07 | · | 7.8 | · |
| calib | 3000 | 10.29 | -0.78 ± 1.30 | 6.8 | -1.1 |

## calib: shortdeck (bot code 3b9709e3c856)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| base | 3000 | 25.65 | · | 16.8 | · |
| calib | 3000 | 24.34 | -1.31 ± 1.62 | 14.4 | -2.4 |

## robust: zoo (bot code 3b9709e3c856)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| shipped | 3000 | 49.58 | +0.35 ± 1.44 | 28.4 | +3.2 |
| base | 3000 | 49.23 | · | 25.2 | · |

## robust: mixed (bot code 3b9709e3c856)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| shipped | 3000 | 42.48 | +5.71 ± 1.51 | 23.1 | +9.2 |
| base | 3000 | 36.77 | · | 13.9 | · |

## variants: plo (bot code 3b9709e3c856)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| shipped | 3000 | 26.10 | +0.00 ± 0.01 | 0.2 | +0.0 |
| base | 3000 | 26.10 | · | 0.2 | · |

## variants: crazy (bot code 3b9709e3c856)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| base | 3000 | 35.33 | · | 19.1 | · |
| shipped | 3000 | 31.31 | -4.03 ± 1.38 | 16.7 | -2.4 |

## variants: crazy (bot code 7911fd1208fd)

| Config | Tables | Points | Δ vs base | Win % | Δ win % |
| :- | -: | -: | -: | -: | -: |
| shipped | 3000 | 36.67 | +1.36 ± 1.22 | 19.9 | +0.8 |
| base | 3000 | 35.30 | · | 19.1 | · |

