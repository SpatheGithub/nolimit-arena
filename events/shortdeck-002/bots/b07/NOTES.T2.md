## Strategy

**Summary:** Equity-driven bot for shortdeck. Preflop uses a precomputed 81x81 class-vs-class equity matrix (36-card deck) to get equity vs an estimated opponent range (top-p%), with chip-EV push/fold and reshove-with-fold-equity when short. Postflop it runs a vectorized numpy Monte Carlo (192-320 samples, ~0.2 ms) against the opponents still in, weighting opponent hands by their preflop range and by how their current made hand fits their betting.

**Before the flop:** Open-raise top 13% (UTG) to 52% (SB), 80% heads-up, 48-62% three-handed; widen to 60-90% when the players behind fold a lot (steal model from their VPIP). 2.5bb (+1 per limper). Facing a raise: equity vs raiser's range (observed PFR scaled by raiser position, tightened 0.35x per extra raise); 3-bet with eq >= 0.60, call when eq beats pot odds +0.04 (-0.06 implied odds when deep) and eq >= min(0.38, pot odds + 0.12), so cheap calls with a big price are no longer folded; AA/KK/QQ never fold preflop (safety net). <=14bb effective: shove/fold by chip EV with per-seat call probabilities; <=18bb facing an open: reshove/fold with fold equity.

**After the flop:** MC equity vs weighted ranges. A seat that bets/raises on the current street is assumed to hold the top 55%/45%/35% (flop/turn/river) of its range by current hand value (tighter for passive seats, multiple raises and pot-size bets; looser for maniacs); earlier-street aggression and calls downweight hands that don't improve on the board. Value bet 0.6-1.0 pot when eq > 0.58 (HU) / lower multiway (thinner vs stations); raise with eq > 0.78 HU; call when eq > pot odds + margin (+0.03 on the river; +0.03 on flop/turn when more than a pot remains behind, for reverse implied odds). Heads-up c-bets/semibluffs at fixed frequencies scaled by the villain's observed fold-to-bet rate.

**Short stacks and the points table:** push/fold zone <= 14bb; shoves and call-offs need chip EV > 0 after a loss penalty lambda x (fraction of our stack at risk), lambda ~50% of the ICM bubble factor minus one: 0.11 (8 left), 0.18 (6), 0.24 (5, bubble), 0.21 (4), 0.17 (3), 0 heads-up. HU/3-handed use wider shove/call assumptions.

**Opponents:** per-seat VPIP/PFR/exact preflop shove counts/postflop aggression/fold-to-bet (with priors). They set raiser and shover ranges, call probabilities for our shoves, steal widening, bluff frequency and value thresholds; postflop aggression ratio softens bet-means-strength weighting for maniacs.

**Last change:** v17 (009, for T2): the preflop call floor of eq >= 0.38 became eq >= min(0.38, pot odds + 0.12). Debug runs showed TT folded getting 10:1. Added a safety net so AA/KK/QQ never fold preflop. Tests vs 008: self-play 23.1 vs 21.4 avg of the 008 copies, mixed field 28.1 vs 27.5 and 28.3 vs 26.8 (800 tables each). Both are small gains within noise; VPIP rose only from 25% to 27%. Before that, v14 (008, played T1, rank 2): +0.03 equity needed on flop/turn calls when deep.

## Notes

- Card ids: r*4+s with r 0..8 = 6..A. Evaluator in bot/evalnp.py verified vs kit evaluator (0 mismatches / 20k).
- Precompute: tools/precompute.py -> bot/pre.npz (HU 81x81 from 16M deals, multiway vs k random).
- tools/sim.py = localsim with place distribution; tools/pf.py prints preflop charts; tools/post.py postflop scenarios.
- Results: v1 vs zoo 45.8/table (300 tables). v2 vs mixed (v1+zoo) 45.7 vs v1 40.6.
- In zoo fields the nit takes 2nd ~46% of the time: survival is worth a lot; steal more vs tight tables.
- Submissions: 001 v1, 002 v2, 003 v4, 004 v5, 005 v7, 006 v9, 007 v10, 008 v14 (played T1), 009 v17 (for T2).
- ICM: bubble factors (equal stacks) 8p 1.22, 6p 1.34, 5p 1.46, 4p 1.40, 3p 1.31, HU 1.0. Full-ICM lambda (v8) tested neutral/slightly negative vs v7; using ~50%.
- tools/analyze.py: hand-log breakdown of chips by our last decision (street, action).
- Timing: MC at 480 samples hit 2 timeouts under heavy load; now 320/240/192.

## Tournament results
- T1 (bot 008/v14): rank 2 of 8, 24.07 points/table (CI 21.96-26.18); places 1st-8th per 1000: 138/146/128/142/140/132/100/74; 0 substitutions in 118969 decisions; p99 300 us. Field is close (19.3-24.2); others play looser (VPIP 27-35% vs our 25%).
- results/T1/sample_hands.json: decisions use real seat ids and seat 0 is NOT us; find our seat from the hole cards and actions (e.g. hand 1: we were the BB with AA and 3-bet to 135 = 2.7x).
- Patch 1 (before T2): a debug run printing our preflop folds of top-10% hands found TT folded getting 10:1 (the absolute eq>=0.38 floor) and AKo folded vs a 5x open because every player still to act counted as a caller (x0.88 each). v16 (both fixes) was neutral (self 21.65 vs 21.62, mixed 26.9 vs 27.3) and raised VPIP 25->31%: not submitted.
- v17 = only the floor fix + AA-QQ never fold (old multiway discount kept): self 23.1 vs 21.4, mixed 28.1 vs 27.5 -> submitted as 009. Third check (mixed, seed 221, 800 tables): v17 28.3 vs 008 copies 26.8 avg -> +1.7/+0.7/+1.5 across three tests, kept.
- v17 vs zoo 52.55 (seed 3; v14 was 52.8). One run under patch-window load showed 1 timeout + 2 hangs; re-runs had 0 (load spikes, the change only adds a table lookup).
- v17 analysis in a looser field (008/007/006 + maniac/minraiser/montecarlo/pot_odds, 120 tables): calls now profit on every street (flop +5.0, turn +21, river +5.6 bb). By blind level: +1.1 bb/hand at bb 20, +1.0 at bb 40, about 0 at bb 80-320, -0.56 at bb 640. NEXT WEAKNESS: the push/fold endgame (bb >= 160) gains nothing; check shove/call ranges at 3-5 players and heads-up.

## Known weaknesses
- Self-play tests have +-2.3 points noise at 800 tables; most tuning since v7 is within noise.
- Equity vs ranges preflop ignores card removal; ranges are top-p% by equity vs random (pairs rank lower than in hold'em).
- Postflop range model uses category-relative-to-board and value percentile, no draw awareness for bettors.
- No exact ICM at decision time (lambda heuristic); hand cap never reached in sims (tables end ~hand 130).
- v11 (3-bet wider vs loose openers at eq>=0.56, river bluff 0.18) tested neutral/negative: not submitted.
- v12 (raise-over-bet counts double for range narrowing) mixed 24.3 vs v10 27.9, self-play +0.8: not submitted.
- v13 (wider CO/BTN opens 0.30/0.42) self-play 20.9 vs v10 21.7, mixed 27.9 vs 27.1: neutral, not submitted.
- v15 (deep flop/turn call margin +0.05 instead of +0.03) self-play 22.4 vs v14 21.5, mixed 24.9 vs 28.1: worse, not submitted; +0.03 stays.
- All-versions field (600 tables): v9 25.9, v10 23.7/23.2, v7 21.0, v2 20.8, v4 20.0, v5 19.4, v1 18.8 -> steady progression; v10 was the base for v14.
- v14 vs house zoo (300 tables, seed 3): 52.8, v10 52.5, v1 45.8; 0 substitutions, p99 500 us under load.
- v14 in a field of submissions 005/006/007 (500 tables): 19.8 vs 007 copies 20.7 avg, 006 23.9, 005 21.6 -> all within noise (+-2.8). Combined evidence v14 vs v10: +1.1, +2.1, -0.9, +0.3 -> kept v14.
- Under heavy machine load all versions show occasional >1 ms maxima (thread CPU); idle p99 ~300 us.

## Next steps
- Endgame push/fold (bb >= 160): compare the shove_ev call-probability tables with what opponents actually do (track calls vs our shoves).
- Use showdown cards (observe 'shown') to calibrate each opponent's bet ranges.
- ICM-exact call-offs at <=4 players with cached icm (cost concerns at 1 ms).
- Re-run tools/analyze.py after each change; the (street, action) breakdown found the river-call leak.
