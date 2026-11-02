## Strategy

**Summary:** Equity-driven bot for shortdeck. Preflop uses a precomputed 81x81 class-vs-class equity matrix (36-card deck) to get equity vs an estimated opponent range (top-p%), with chip-EV push/fold and reshove-with-fold-equity when short. Postflop it runs a vectorized numpy Monte Carlo (192-320 samples, ~0.2 ms) against the opponents still in, weighting opponent hands by their preflop range and by how their current made hand fits their betting.

**Before the flop:** Open-raise top 13% (UTG) to 52% (SB), 80% heads-up, 48-62% three-handed; widen to 60-90% when the players behind fold a lot (steal model from their VPIP). 2.5bb (+1 per limper). Facing a raise: equity vs raiser's range (observed PFR scaled by raiser position, tightened 0.35x per extra raise); 3-bet with eq >= 0.60, call when eq beats pot odds (+implied odds deep). <=14bb effective: shove/fold by chip EV with per-seat call probabilities; <=18bb facing an open: reshove/fold with fold equity.

**After the flop:** MC equity vs weighted ranges. A seat that bets/raises on the current street is assumed to hold the top 55%/45%/35% (flop/turn/river) of its range by current hand value (tighter for passive seats, multiple raises and pot-size bets; looser for maniacs); earlier-street aggression and calls downweight hands that don't improve on the board. Value bet 0.6-1.0 pot when eq > 0.58 (HU) / lower multiway (thinner vs stations); raise with eq > 0.78 HU; call when eq > pot odds + margin (+0.03 on the river; +0.03 on flop/turn when more than a pot remains behind, for reverse implied odds). Heads-up c-bets/semibluffs at fixed frequencies scaled by the villain's observed fold-to-bet rate.

**Short stacks and the points table:** push/fold zone <= 14bb; shoves and call-offs need chip EV > 0 after a loss penalty lambda x (fraction of our stack at risk), lambda ~50% of the ICM bubble factor minus one: 0.11 (8 left), 0.18 (6), 0.24 (5, bubble), 0.21 (4), 0.17 (3), 0 heads-up. HU/3-handed use wider shove/call assumptions.

**Opponents:** per-seat VPIP/PFR/exact preflop shove counts/postflop aggression/fold-to-bet (with priors). They set raiser and shover ranges, call probabilities for our shoves, steal widening, bluff frequency and value thresholds; postflop aggression ratio softens bet-means-strength weighting for maniacs.

**Last change:** v14 (008): flop/turn calls need +0.03 extra equity when deep stacks remain behind (the v10 hand analysis showed most losses were chips put in early and then folded later: river folds -8.4bb, turn folds -5.8bb on average). Tests vs v10: self-play 22.6 vs 21.5 avg of the v10 copies (700 tables), mixed field 29.1 vs 27.1 (700 tables); both point the same way but each is within noise. v10 (007) before it: tighter ranges for pot-size and all-in bets, ~50% ICM loss penalty.

## Notes

- Card ids: r*4+s with r 0..8 = 6..A. Evaluator in bot/evalnp.py verified vs kit evaluator (0 mismatches / 20k).
- Precompute: tools/precompute.py -> bot/pre.npz (HU 81x81 from 16M deals, multiway vs k random).
- tools/sim.py = localsim with place distribution; tools/pf.py prints preflop charts; tools/post.py postflop scenarios.
- Results: v1 vs zoo 45.8/table (300 tables). v2 vs mixed (v1+zoo) 45.7 vs v1 40.6.
- In zoo fields the nit takes 2nd ~46% of the time: survival is worth a lot; steal more vs tight tables.
- Submissions: 001 v1, 002 v2, 003 v4, 004 v5, 005 v7, 006 v9, 007 v10, 008 v14 (final of build phase).
- ICM: bubble factors (equal stacks) 8p 1.22, 6p 1.34, 5p 1.46, 4p 1.40, 3p 1.31, HU 1.0. Full-ICM lambda (v8) tested neutral/slightly negative vs v7; using ~50%.
- tools/analyze.py: hand-log breakdown of chips by our last decision (street, action).
- Timing: MC at 480 samples hit 2 timeouts under heavy load; now 320/240/192.

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
- Use showdown cards (observe 'shown') to calibrate each opponent's bet ranges.
- ICM-exact call-offs at <=4 players with cached icm (cost concerns at 1 ms).
- Re-run tools/analyze.py after each change; the (street, action) breakdown found the river-call leak.
