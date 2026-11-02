# Team b06 notes

## Strategy

**Summary:** Math-first bot. Preflop decisions come from a precomputed 81x81 shortdeck class-vs-class equity matrix (equity vs "top q%" ranges), with ICM-priced (points, not chips) push/fold and all-in calls when short. Postflop it computes near-exact equity with a vectorized numpy evaluator (rank-count lookup + flush table) against an opponent range that is narrowed by their preflop action and postflop bets, then bets/calls/folds by equity vs pot odds.

**Before the flop:** Opens top ~12% (UTG) to ~45-50% (SB) by players left to act, widened when 4 or fewer remain and when the players behind are tight (low VPIP); 2.5bb open (2.2bb under 30bb). Facing a raise: estimates the raiser's range from their observed PFR (prior 18%), 3-bets when equity vs that range > 60%, calls with equity > pot odds + 6% when the call is < 12% of stack, otherwise folds. Committed spots (call >= 35% of stack) call/shove when equity beats the ICM break-even. Short all-in shovers (<= 15bb) are given a position-based range (SB/HU 60% ... UTG 15%) or their observed PFR if wider.

**After the flop:** Equity vs main opponent's weighted range (flop: 12 sampled runouts x all opponent combos; turn: 16 sampled rivers; river exact), raised to a power for multiway. Value bets 60-75% pot with equity > 0.6-0.72, c-bets flop ~60% as preflop raiser and probes/bluffs the river at rates scaled by the opponents' observed fold-to-bet rate; raises with equity > 0.85; calls when equity > pot odds.

**Short stacks and the points table:** Re-shoves over a single open at <= 22bb when the ICM shove EV (raiser calls with part of his range) is positive. <= 14bb effective and unopened: shove/fold by an ICM (Malmuth-Harville, top-4 paid) EV model: each opponent still in calls with top ~1.4/stack_bb of hands (scaled by their VPIP, blinds wider); shove if points-EV beats folding. Facing all-ins / committing calls (pre and postflop): call only if equity > ICM break-even (F-L)/(W-L) computed from fold/win/lose stack outcomes vs the raiser.

**Opponents:** Tracks per-seat VPIP, PFR, postflop aggression vs passivity and fold-to-bet rate from hand histories; used for raiser/caller ranges, shove caller ranges (VPIP), narrowing strength (aggression) and bluff frequency (fold rate).

**Last change:** v8 (007-07c52c90): open-raise range widened/tightened by the average VPIP of the players left to act (factor 1+(0.28-vpip)*1.5, clipped 0.85..1.3) to steal more from nit-like bots. Test vs 2x v7 + 2 nit + checkfold/montecarlo/threshold (700 t): 35.7 vs v7 34.4 (within noise); neutral in self-play by construction. Also v7 sanity vs zoo (400 t): 48.4 pts/table. Previous: v7 fold-to-bet stat scales bluffing; v6 position prior for short shove ranges.

## Notes / parameters
- bot/fasteq.py: RV table keyed by base-5 rank counts (5..7 cards), FV flush table by suit rank mask; verified 0 mismatches vs house Ranker on 20k random 7-card hands.
- bot/pf_matrix.json: 81x81 equity, 1500 MC boards per class pair (tools/pre_matrix.py).
- Timing: flop equity ~0.25ms, turn ~0.28ms, river ~0.03ms on busy machine.

## Test results
- v1 vs zoo (150 tables): 46.6 pts/table (avg 21.6).
- v3 vs 3x v1 + 4 house (400 t): 35.4 vs v1 29.2/29.2/28.0.
- v4 vs 3x v3 + 2x v1 + mc + nit (1000 t): 27.2 vs v3 25.2 / v1 25.3.
- v5 vs 2x v4 + 4 house (800 t): 33.0 vs 30.1; self-play 4v4: 21.2 vs 22.0.
- v6/v7/v8: ties vs predecessor in self-play; v7 vs zoo 48.4; v8 vs nits field 35.7 vs 34.4.
- Final self-play 4 v8 vs 4 v7 (700 t): 21.8 vs 21.4 (tie). v8 vs 3 maniac + 2 minraiser + 2 v7 (400 t): v8 35.9, v7 37.3/36.4, maniacs 12.5-14.0 each — maniacs still collect ~13 pts each; a patch could call down lighter vs high-aggression seats (narrowing exponent is only cut x0.6 when aggr/passive > 1.5).
- Lineage test, v8 vs one copy each of v1..v8 (600 t, +-2.7): v7(006) 24.2, v6(005) 23.0, v8(007 copy) 23.0, v8(you) 22.3, v1 21.5, v5(004) 21.0, v4(003) 20.3, v3(002) 17.8. Later versions on top; v7 vs v8 is within noise (if a patch round shows v8's VPIP steal-widening hurting, v7 = 006 is the fallback).
- Tried at the end: stronger cut (x0.5 when aggr/passive > 1.5, x0.3 when > 2.5) vs 3 maniac + 2 minraiser + 2 v8 (900 t): 36.5 vs v8 36.1 avg (tie) -> not submitted, reverted. Maniacs' points barely moved, so the leak is probably preflop (vs their raises/shoves), not postflop narrowing.

## Known weaknesses / next
- Next ideas: per-position open-rate stats for opponents (first-in raise frequency) to model steal/shove ranges; caller model in shove EV (1.4/stack_bb, x1.25 blinds) is a guess - make it use observed call-vs-shove frequency; postflop has no slowplay / check-raise / bluff-raise; multiway equity is a crude power of HU equity.
- Push/fold sanity (tools/ranges.py): BTN 10bb shove ~28% classes 6-handed, ~62% 8-handed; HU ~all; BB call vs BTN 10bb shove ~15% classes (ICM premium), HU ~43%.
- History: VPIP-based open widening and position-based raiser-range priors first tested worse (noise) and were dropped; both came back in narrower form (v6: position prior only for short all-in shoves <= 15bb; v8: VPIP widening clipped 0.85..1.3) and tested as ties vs predecessors. A position prior for normal (non-all-in) opens is still NOT used.
- Self-play tests have +-2.5 noise at 700 tables; use A/B with 4 copies each side.
- Local runs on the loaded machine show rare timeouts/hangs (max ~1.2ms CPU); thread-CPU profile: flop max ~450us, turn ~360us.
