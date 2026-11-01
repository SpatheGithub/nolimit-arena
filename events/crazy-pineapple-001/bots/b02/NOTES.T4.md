# Team b02 notes

## Strategy

**Summary:** Rule-based tight-aggressive bot. Preflop uses a 3-card strength score built from hold'em equity tables (best 2-card subset + bonus for the other subsets); postflop uses a fast made-hand/draw heuristic that estimates equity, discounted for multiway pots and bet size, compared against pot odds. Short stacks switch to push/fold.

**Before the flop:** Strength s1 = best pair's hold'em equity vs 1 random hand + 0.25/0.1 bonus for the other two pairs (top 10% ≈ 0.69, top 20% ≈ 0.65, top 30% ≈ 0.63). Opens ~12% early (s1 ≥ 0.68), ~18% middle (0.657), ~28% late/SB (0.633), raise to 2.5bb + 1bb per limper (2.2bb under 25bb). 3-bets s1 ≥ 0.775 (0.75 vs loose raisers), calls a raise with s1 ≥ 0.69 + small size term; jams 3-bet hands if the raise is ≥35% of stack.

**After the flop:** On the flop (3 hole cards) values the best 2-card keep; discards the card that leaves the highest heuristic strength. Strength by category and hole-card involvement (sets/two pair using both hole cards high, board-paired hands low, one pair 0.28–0.7 by top/over/middle), plus flush/straight-draw equity. Multiway: eq = s^(0.75+0.6·(n-1)). Bets 75–85% pot with eq ≥ 0.72, 55% pot with eq ≥ 0.55 heads-up/3-way (70%), c-bets 45% pot 55% of the time as preflop raiser, small river bluff frequency heads-up. Facing bets: discounts eq by bet size and raises, calls if eq ≥ price + 0.07, raises with eq ≥ 0.85.

**Short stacks and the points table:** At ≤13bb effective: open-jam s1 ≥ 0.60–0.67 by players behind, looser as the stack shrinks and with ≤3 players left; calls jams when s1 − 0.17 (+ looseness of the jammer) ≥ price + 0.03, or s1 ≥ 0.75. No explicit ICM yet.

**Opponents:** Tracks per-seat hands, VPIP, PFR, postflop raises vs calls. Loose raisers (PFR > 30%) get looser 3-bets/calls; frequent postflop aggressors get less bet-size discount when calling.

**Last change:** v2 (002-f5e0de70): tightened all preflop thresholds after calibrating s1 percentiles; v1 played 47% VPIP and finished 8th in T3 (24.7 pts). Local zoo test: VPIP 22%, 50.4 pts vs 46.9 for v1 (80 tables, noisy).

## Log
- T3 (v1, 001-88c8a1b5): 8/8, 24.73 pts/table, VPIP 47% — far too loose.
- Others in T3 ran 20–25% VPIP, 14–19% PFR; winner b08 20%/16%.

## Next steps
- Calibrate postflop thresholds for crazy pineapple (two pair is common at showdown).
- ICM-aware calling near the end; heads-up push/fold ranges.
