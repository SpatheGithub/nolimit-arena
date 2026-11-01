## Strategy

**Summary:** Rule-based bot: preflop percentile table over all 22,100 three-card hands (Chen-score of best 2-card subset plus small credit for the other pairs), position/stack-aware open/3-bet/call thresholds, push/fold under 13 BB; postflop a hand-strength heuristic (made-hand class relative to the board, kicker, board texture, draw equity) mapped to an approximate win probability, discounted for multiway pots and compared to pot odds plus a bet-size margin. All decisions are lookups/arithmetic (~25 µs).

**Before the flop:** Opens to 2.5 BB (+1 BB per limper, 3 BB from SB) with top ~18% from early seats to top ~40% on the button/SB; 3-bets top 5% (shoves if 3-bet would commit >40% of stack), calls a single raise with top ~16% (wider in BB, tighter when the call is >25% of stack); vs 3-bet+ shoves top 2.5%, calls top 5-7%.

**After the flop:** Strength ≈ showdown win probability vs one random hand, raised to a power for extra opponents. Bets 70% pot with strong hands, 55% pot with good hands heads-up/3-way, semi-bluffs draws half the time, c-bets heads-up flops 55% as preflop raiser. Facing a bet: raises/shoves very strong hands, calls if strength ≥ pot odds + 0.06 + 0.12×(bet/pot), folds otherwise. Discard keeps the 2 cards with highest strength.

**Short stacks and the points table:** ≤13 BB effective: push/fold. Shove threshold widens with fewer players behind and shorter stack; calls shoves with top ~28% adjusted by pot odds. Slightly looser when ≤4 players remain.

**Opponents:** Tracks each seat's preflop raise frequency; vs seats raising >30-35% it calls/3-bets ~5-8 percentile points wider and needs less equity to call their postflop bets.

**Last change:** First version (001-eba40674). T3: rank 2/8, 35.36 pts/table.

## Notes

- T1, T2 missed (no submission in time).
- T3: 001-eba40674 rank 2, 35.36. b08 best at 38.0 (VPIP 20 / PFR 16, tighter than us).
