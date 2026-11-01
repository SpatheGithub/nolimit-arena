# Team b08 notes

## Strategy

**Summary:** A tight-aggressive rules bot. Before the flop it ranks the 3-card hand with a precomputed table. After the flop it scores the made hand and draws, and when stacks are short it switches to push/fold. Every decision is a table lookup plus arithmetic (p99 about 100 µs), so it never times out. It scores by staying out of marginal pots, betting its strong hands and surviving to the higher places. It ranked 1st in T1, T2 and T3 (37–38 points per table).

**Before the flop:** Hand rank = percentile of the best 2-card subset (hold'em preflop table, `_common.json`), converted to a 3-card percentile with 1-(1-p)^3. It gets a small bonus when a second subset is also strong.
- Open-raise thresholds depend on the number of players left to act: about the top 14% early, 24% with 3 behind, 30% on the button and 40% from the SB. The open size is 2.5bb plus 1bb per limper, or 3bb from the SB.
- Facing a raise, it estimates the raiser's range from the bet size, the raiser's stack and that seat's observed raise frequency. It 3-bets the top ~3.5% (shoving when ≤30bb), calls when the hand is inside the pot-odds-scaled range, and folds otherwise. Facing a 4-bet it continues only with about the top 3%.

**After the flop:** It evaluates every 2-card subset with the kit's feature scorer (made-hand strength by category, kicker and board texture, plus draw outs) and keeps the best. Equity is taken as strength plus outs × 3.2% on the flop or 1.8% on the turn, minus 8% per extra opponent.
- **Betting:** it value-bets 60–75% pot with equity ≥0.6 (0.7 multiway), semi-bluffs with 8+ outs, c-bets the flop as the preflop raiser (55% on dry boards, 40% on wet ones) and stabs 25% in position heads-up.
- **Facing a bet:** it calls when equity minus a bet-size penalty beats the pot odds by 4%, raises with equity ≥0.8 and shoves when the SPR is low.
- **Discard:** it keeps the best 2 cards by the same strength + outs score.

**Short stacks and the points table:** At ≤13bb effective with an unopened pot it plays push/fold. The shove range is 0.55·(players behind)^-0.75·(10/bb)^0.8 as a fraction of hands, tightened by limpers and by ICM. When calling all-ins it compares its rank against the estimated shove range scaled by pot odds. The ICM tightening adds up to +9% required equity when 4 or fewer players remain, when it is a big stack (>1.5× average) or when the hand cap is near.

**Opponents:** It counts per-seat preflop raise frequency and VPIP through `observe()`. Frequent raisers get wider assumed ranges, so it calls shoves and raises lighter against them. Postflop it adds +6% equity against bettors whose preflop raise frequency is above 35%.

**Last change:** None since submission 001-4fdf5b82. That version won T1 (37.16), T2 (37.87) and T3 (38.02). No change was clearly better, so it is still active.

## Results
- T1: rank 1/3, 37.16. T2: rank 1/4, 37.87. T3: rank 1/8, 38.02 (b07 35.4, b05 34.8, b06 34.2).
- T3 places: 1st 133, 2nd 183, 3rd 168, 4th 140, 5th 150, 6th 94, 7th 65, 8th 67. No tables reach the hand cap (blinds get huge).

## Known weaknesses / next ideas
- Many 2nd–4th places compared with 1sts, so the endgame (3-handed and heads-up) may be too tight. Widen the short-handed open and shove ranges.
- The preflop rank uses hold'em 2-card percentiles, not true crazy-pineapple equities.
- There is no read on postflop aggression (only preflop raise frequency).
