## Strategy

**Summary:** Equity-driven bot for shortdeck. Preflop uses a precomputed 81x81 class-vs-class equity matrix (36-card deck) to get equity vs an estimated opponent range (top-p%), with chip-EV push/fold and reshove-with-fold-equity when short. Postflop it runs a vectorized numpy Monte Carlo (192-320 samples, ~0.2 ms) against the opponents still in, weighting opponent hands by their preflop range and by how their current made hand fits their betting.

**Before the flop:** Open-raise top 13% (UTG) to 52% (SB), 80% heads-up, 48-62% three-handed; widen to 60-90% when the players behind fold a lot (steal model from their VPIP). 2.5bb (+1 per limper). Facing a raise: equity vs raiser's range (observed PFR scaled by raiser position, tightened 0.35x per extra raise); 3-bet with eq >= 0.60, call when eq beats pot odds +0.04 (-0.06 implied odds when deep) and eq >= 0.38 (the T1 rule); AA never folds preflop (safety net). <=14bb effective: shove/fold by chip EV with per-seat call probabilities; <=18bb facing an open: reshove/fold with fold equity.

**After the flop:** MC equity vs weighted ranges. A seat that bets/raises on the current street is assumed to hold the top 55%/45%/35% (flop/turn/river) of its range by current hand value (tighter for passive seats, multiple raises and pot-size bets; looser for maniacs); earlier-street aggression and calls downweight hands that don't improve on the board. Value bet 0.6-1.0 pot when eq > 0.58 (HU) / lower multiway (thinner vs stations); raise with eq > 0.78 HU; call when eq > pot odds + margin (+0.03 on the river; +0.03 on flop/turn when more than a pot remains behind, for reverse implied odds). Heads-up c-bets/semibluffs at fixed frequencies scaled by the villain's observed fold-to-bet rate.

**Short stacks and the points table:** push/fold zone <= 14bb; shoves and call-offs need chip EV > 0 after a loss penalty lambda x (fraction of our stack at risk), lambda ~50% of the ICM bubble factor minus one: 0.11 (8 left), 0.18 (6), 0.24 (5, bubble), 0.21 (4), 0.17 (3), 0 heads-up. HU/3-handed use wider shove/call assumptions.

**Opponents:** per-seat VPIP/PFR/exact preflop shove counts/postflop aggression/fold-to-bet (with priors), plus how often each seat actually called our preflop shoves (blended into the call probability with a prior weight of 4 observations). They set raiser and shover ranges, call probabilities for our shoves, steal widening, bluff frequency and value thresholds; postflop aggression ratio softens bet-means-strength weighting for maniacs.

**Last change:** v20 (011, played T4 at rank 4 with 21.37, kept for T5) is v14's preflop calling (the version that scored best in a real tournament, T1 24.07, rank 2) plus v18's per-seat shove-response tracking. The v17 tweaks are reverted: the cheap-call floor goes back to eq >= 0.38, and the never-fold safety net covers AA only (it had covered AA/KK/QQ, which let QQ/KK call off 100bb against tight 4-bet/5-bet ranges). Real-field trend T1/T2/T3: 24.07, 23.04, 21.64, with 7th+8th per 1000 at 174, 204, 248 and showdown win 55.8%, 54.0%, 53.7%. Local tests vs v18 were neutral: self-play 22.0 vs 21.6, mixed 26.4 vs 28.0 (700 tables each), and v20 had fewer 7th/8th places in self-play (0.11/0.11 vs ~0.13). Vs 008 (v14): self 21.6 vs 21.6, mixed 32.1 vs 31.7. Vs zoo (seed 3): 58.0 (v18 52.4, v14 52.8); 0 substitutions.

## Notes

- Card ids: r*4+s with r 0..8 = 6..A. Evaluator in bot/evalnp.py verified vs kit evaluator (0 mismatches / 20k).
- Precompute: tools/precompute.py -> bot/pre.npz (HU 81x81 from 16M deals, multiway vs k random).
- tools/sim.py = localsim with place distribution; tools/pf.py prints preflop charts; tools/post.py postflop scenarios.
- Results: v1 vs zoo 45.8/table (300 tables). v2 vs mixed (v1+zoo) 45.7 vs v1 40.6.
- In zoo fields the nit takes 2nd ~46% of the time: survival is worth a lot; steal more vs tight tables.
- Submissions: 001 v1, 002 v2, 003 v4, 004 v5, 005 v7, 006 v9, 007 v10, 008 v14 (played T1), 009 v17 (played T2), 010 v18 (played T3), 011 v20 (played T4, kept for T5).
- ICM: bubble factors (equal stacks) 8p 1.22, 6p 1.34, 5p 1.46, 4p 1.40, 3p 1.31, HU 1.0. Full-ICM lambda (v8) tested neutral/slightly negative vs v7; using ~50%.
- tools/analyze.py: hand-log breakdown of chips by our last decision (street, action).
- Timing: MC at 480 samples hit 2 timeouts under heavy load; now 320/240/192.

## Tournament results
- T1 (bot 008/v14): rank 2 of 8, 24.07 points/table (CI 21.96-26.18); places 1st-8th per 1000: 138/146/128/142/140/132/100/74; 0 substitutions in 118969 decisions; p99 300 us. Field is close (19.3-24.2); others play looser (VPIP 27-35% vs our 25%).
- T4 (bot 011/v20): rank 4 of 8, 21.37 (CI 19.39-23.34); places per 1000: 114/131/150/134/141/126/109/95 (7th+8th back down to 204 but only 114 wins); VPIP 24.5%, showdown win 54.9%. b06 25.72 (35/20), b02 24.29 (29/20). Score trend 24.07, 23.04, 21.64, 21.37 while the field improves.
- T4 sample review (seats from tools/replayseat.py): AQo folded facing a single UTG open from UTG+1. Chart check: vs a UTG open with 6 players still to act, v20 folds QQ, JJ, AKo and AQs, because every player still to act cost x0.88 equity (up to 3). v21 (callers x0.88, players to act x0.97 for all hands): self -0.5, mixed -2.1, VPIP +4: not submitted. v22 (the smaller discount only for top-8% hands: QQ/JJ/AK/AQs now call a UTG open): self +0.3, mixed -1.5, looser-opener field -2.5 -> not submitted; calling opens with more premiums does not pay locally. Kept 011 (v20) for T5.
- v23 (ICM loss penalty halved, ~25% of BF-1): self +3.5 (wins 17% vs 12%), mixed -1.7, versions field -1.9 (8th 17%) -> net ~0, not submitted. Note: every candidate this window scored below the 011 copies in the 011x4 + nit/maniac/montecarlo mixed field (v21 -2.1, v22 -1.5, v23 -1.7).
- T3 (bot 010/v18): rank 4 of 8, 21.64 (CI 19.62-23.67); places per 1000: 120/140/114/133/123/122/144/104. Trend across T1/T2/T3: 24.07, 23.04, 21.64; 7th+8th per 1000: 174, 204, 248; showdown win 55.8%, 54.0%, 53.7%; WTSD 7.3%, 7.9%, 8.0%. b06 leads every time (24.2, 24.9, 25.8; VPIP 35% PFR 20%) and b02 has risen (21.4, 24.5, 24.3). Suspect: v17's AA/KK/QQ never-fold net (QQ/KK call off 100bb vs tight 4-bet/5-bet ranges) and its looser cheap multiway calls.
- v18 vs 009 over six tests: mixed +2.7, +1.9, +0.7; versions field -1.4; self 0.0; zoo -0.2 -> mean +0.6, kept 010 for T3.
- v19 (same blend for the reshove fold-equity cf) vs v18: mixed +0.6 and -2.2 -> not submitted.
- T2 (bot 009/v17): rank 3 of 8, 23.04 (CI 20.91-25.16); places per 1000: 141/118/121/151/132/133/113/91 (more 7th/8th than T1: 204 vs 174); 0 substitutions in 117587 decisions. b06 first again (24.87, VPIP 35% PFR 20%), b02 24.53; all of the top 6 within noise.
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
- tools/replayseat.py <sample_hands.json> finds our seat per sample table by replaying our agent's preflop decisions (T3: table0 seat1 11/11, table2 seat0 10/10, table3 seat7 10/10, table1 ambiguous 0/1). Our T3 sample hands looked sound (QQ full house stacked AA +2030; K7o SB raise/c-bet/check-down -120; QTs BB defend, fold turn -99). Next window: run it on the new sample_hands.json first. T1/T2 seats found too (T1 t0 = seat 5, the BB that 3-bet AA). Big swings reviewed: KK lost to a rivered ace after betting flop/turn; AQ value-bet turn/river into AK on a paired board; A7 two pair called flop+turn on a 3-diamond board then folded the river to a pot bet (-312): the call-call-fold pattern is still the main chip loss.
- Done in v18: per-seat tracking of calls vs our shoves. Next: per-seat tracking of their shove frequency by position/stack to widen our calling ranges vs wide shovers.
- Use showdown cards (observe 'shown') to calibrate each opponent's bet ranges.
- ICM-exact call-offs at <=4 players with cached icm (cost concerns at 1 ms).
- Re-run tools/analyze.py after each change; the (street, action) breakdown found the river-call leak.
