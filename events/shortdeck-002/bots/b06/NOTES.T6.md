# Team b06 notes

## Strategy

**Summary:** Math-first bot. Preflop decisions come from a precomputed 81x81 shortdeck class-vs-class equity matrix (equity vs "top q%" ranges), with ICM-priced (points, not chips) push/fold and all-in calls when short. Postflop it computes near-exact equity with a vectorized numpy evaluator (rank-count lookup + flush table) against an opponent range that is narrowed by their preflop action and postflop bets, then bets/calls/folds by equity vs pot odds.

**Before the flop:** Opens top ~12% (UTG) to ~45-50% (SB) by players left to act (heads-up SB 85%, 3-handed button 50%), widened when 4 or fewer remain and when the players behind are tight (low VPIP); 2.5bb open (2.2bb under 30bb). Facing a raise: estimates the raiser's range from their observed PFR (prior 18%), 3-bets when equity vs that range > 60%, calls with equity > pot odds + 6% when the call is < 12% of stack, otherwise folds. Committed spots (call >= 35% of stack) call/shove when equity beats the ICM break-even. Short all-in shovers (<= 15bb) are given a position-based range (SB/HU 60% ... UTG 15%) or their observed PFR if wider.

**After the flop:** Equity vs main opponent's weighted range (flop: 12 sampled runouts x all opponent combos; turn: 16 sampled rivers; river exact), raised to a power for multiway. Raises over our bet narrow the opponent's range strongly (more on turn/river than flop). Value bets 60-75% pot with equity > 0.6-0.72 (heads-up pot with <= 3 players left: > 0.55), c-bets flop ~60% as preflop raiser (x1.25 when <= 3 players left) and probes/bluffs the river at rates scaled by the opponents' observed fold-to-bet rate; raises with equity > 0.85; calls when equity > pot odds.

**Short stacks and the points table:** Re-shoves over a single open at <= 22bb when the ICM shove EV (raiser calls with part of his range) is positive. <= 14bb effective and unopened: shove/fold by an ICM (Malmuth-Harville, top-4 paid) EV model: each opponent still in calls with top ~1.4/stack_bb of hands (scaled by their VPIP, blinds wider); shove if points-EV beats folding. Facing all-ins / committing calls (pre and postflop): call only if equity > ICM break-even (F-L)/(W-L) computed from fold/win/lose stack outcomes vs the raiser.

**Opponents:** Tracks per-seat VPIP, PFR, postflop aggression vs passivity and fold-to-bet rate from hand histories; used for raiser/caller ranges, shove caller ranges (VPIP), narrowing strength (aggression) and bluff frequency (fold rate).

**Last change:** v12 (013-22677910, for T6): with 3 or fewer players left, heads-up pots are value-bet when checked to at equity > 0.55 (was 0.6). Tests vs v11 (012), 3v3 + 2 house bots: +2.63 (maniac+pot_odds, 900 t; all 3 c20 seats above all 3 v11 seats), +1.15 (montecarlo+nit, 700 t). v11 (012) won T5 with 25.57; T1-T5 all rank 1 (weighted 381.93). Rejected this window: c19 tighter deep early phase (opens x0.85, calls +0.02 when > 40bb and >= 6 players): -0.74.

## Notes / parameters
- bot/fasteq.py: RV table keyed by base-5 rank counts (5..7 cards), FV flush table by suit rank mask; verified 0 mismatches vs house Ranker on 20k random 7-card hands.
- bot/pf_matrix.json: 81x81 equity, 1500 MC boards per class pair (tools/pre_matrix.py).
- Timing: flop equity ~0.25ms, turn ~0.28ms, river ~0.03ms on busy machine.

## T1 result (field = other teams)
- Rank 1/8, 24.20 (b07 24.07, b08 22.81, b01 21.64, b02 21.41, b05 19.96, b04 19.57, b03 19.34) - top 2 within noise.
- Places: 1st 168, 2nd 103, 3rd 100, 4th 96, 5th 101, 6th 133, 7th 171, 8th 128. Heads-up conversion 168/271 = 62%. Early busts (6th-8th) 43% vs 37.5% baseline - loose style (VPIP 35%, field 22-33%) = high variance, fine for top-heavy points, but early stack-offs are the main thing to look at.
- Showdown win 51.7%, WTSD 9.9%, aggression 1.75.
- sample_hands.json: seat ids anonymous and our cards are not in 'shown', so our seat can't be identified directly; all 40 sample hands are from the first 10 hands of 4 tables (10/20 blinds).

## Patch window before T2: diagnostics
- tools/cands/diag = v8 + logging of hands losing >= 40% of stack in hands 1-75 (writes $TMPDIR/diag.jsonl; local only, never submit). 250 tables x 3 copies: 510 big losses. By (last street we put chips in, who raised last, depth): preflop shoves when <= 30bb 195; preflop calls short 65; river call-downs deep 53; deep preflop calls 49 (mostly KK vs AA coolers / KK vs deep open-shove = fine); turn calls deep 40.
- Postflop examples worth fixing later: AA calls turn raise on KK-paired board vs AK; KK calls flop check-raise shove vs straight; AA calls river bet multiway on paired board vs full house. I.e. calls vs raises with overpair/two pair.
- Candidate c9 (raise-over-my-bet narrowing weight 1.6 -> 2.3, +0.4 when bet >= 0.75 pot): A/B 700 t vs 3x v8 + montecarlo: c9 22.9 avg vs v8 24.7 -> NOT better, reverted. Next try: target only the specific spots (paired boards / multiway river) rather than global narrowing.

- NULL TEST (accidental: c10 copy failed because .submissions files are read-only -> c10 == 007): 4x007 vs 3x007 (700 t): group means 20.7 vs 22.6, single seats 18.0..24.2. => A/B gaps of ~2 pts at 700 tables are pure noise; need >= 3000 tables (several runs, different seeds) or a much larger effect before trusting a change. When copying a submission to edit it, chmod/cp the files fresh (cp -r keeps read-only mode).
- Candidate c10 (tools/cands/c10: raise-over-my-bet narrowing 2.4 on turn/river only, flop stays 1.6): 4x c10 vs 4x 007 (900 t, seed 601): 21.9 vs 21.4 (+0.5, noise). Second run (seed 701, 900 t): 21.6 vs 21.7 (-0.1). Combined 1800 t: +0.2 -> no measurable effect in self-play; only worth shipping if T-results show we lose to turn/river raises. Third run vs house field (2x c10, 2x 007, montecarlo/nit/pot_odds/maniac, 700 t): c10 31.2 vs 007 28.7 (+2.5, +-2.8). FIRST CANDIDATE FOR T3 WINDOW: run >= 2000 more tables in house/mixed fields; ship if it stays >= +1.
- Decision for T2: keep 007 unchanged.

## T5 result
- Rank 1/8, 25.57 (b02 24.86, b04 23.05, b08 21.64, b07 20.82, b01 19.71, b03 19.37, b05 17.99). Places 169/135/92/94/105/103/128/174. HU conversion 55.6%. Weighted total 381.93, rank 1. cpu max 756 us, 0 subs. 8th-place finishes trending up (128,132,155,150,174) - early deep busts; tighter-early candidate c19 tested -0.74 locally so not changed.

## Patch window before T6
- c19 (deep early tighten): 24.6 vs 25.3 -> dropped. v11 vs zoo sanity (400 t): 51.4. c20 (HU thin value 0.55 when <= 3 players): +2.63, +1.15 -> shipped as 013. Self-play safety check 4x013 vs 4x012 (600 t): 21.9 vs 21.3 (tie, no regression). v12 vs zoo (400 t): 52.9 pts/table (v11 51.4, v7 48.4, v1 46.6), 0 subs, max 650 us.

## Patch window before T5
- 011: timing tier 3. c16 (3-handed SB 70%, 4-handed SB 65% / BTN 45% opens) vs 011 (1000 t): 24.7 vs 25.1 -> dropped. c17 (short-handed c-bet x1.25, floor 0.25): +1.47, +1.01 -> shipped as 012. Self-play safety check 4x012 vs 4x011 (700 t): 21.8 vs 21.5 (tie, no regression).
- c18 (tools/cands/c18 = v11 + HU probe/turn-bet frequency x1.3 when <= 3 players): vs 012 (3v3 + montecarlo + nit, 800 t): 25.3 vs 24.4 (+0.87); second run (maniac + pot_odds, 600 t): 24.9 vs 26.6 (-1.67) -> dropped.

## T4 result
- Rank 1/8, 25.72 (b02 24.29, b04 21.46, b07 21.37, b05 20.99, b08 20.98, b01 20.04, b03 18.15). Places 176/121/92/104/98/120/139/150. HU conversion 59.3% (T1 62.0, T2 53.8, T3 53.0). Weighted total 254.09, rank 1. cpu max 973 us, 0 subs.
- Referee timing by street (sample hands): preflop ~20 us; flop median 310-440 us (max ~650); turn ~245; river ~180-200 -> referee is ~2-3x slower than local thread-time profile, so the 120 us 'fast' threshold probably often selects the 6/8 tier there.

## Patch window before T4
- 009 (v9.1): speed-only, exact (0 mismatches / 3000 calls). 010 (v10): HU SB open 85%, 3-handed BTN 50%. c14 tests vs 009: +0.93, +1.08 (mixed fields); self-play 4v4 (800 t): 21.4 vs 21.8 (tie). Shipped 010.
- c15 (HU BB: defend at need+0.0 instead of +0.035, 3-bet at e > 0.56 instead of 0.6) vs v10 (3v3 + montecarlo + maniac, 800 t): 25.7 vs 25.4 (+0.35, noise); second run (nit + pot_odds, 700 t): 24.8 vs 26.0 (-1.15) -> dropped. HU BB defense looks fine as is.
- Late check v10 vs 008 (2v3 + montecarlo + nit, 500 t): 24.3 vs 25.4 (-1.1, noise +-2.5). Kept v10 (earlier 2x1000 t vs decision-identical 009: +0.93, +1.08). Watch T4 HU conversion (1st/(1st+2nd)); if it does not improve vs T2/T3 (~53%), consider reverting the HU open change.
- Next ideas: HU postflop; 3-bet range of opponents from an actual 3-bet stat; tail CPU (flop) could drop further by cutting the narrowing step (argsort) when villain did not bet.

## T3 result
- Rank 1/8, 25.76 (b02 24.30, b08 22.19, b07 21.64, b05 21.18, b04 20.85, b01 18.84, b03 18.23). Places 166/147/95/81/115/112/129/155. Weighted total 151.23, rank 1. 0 subs but 1 slow_core_pass, cpu max 1165 us, mean 117 us (T1 84, T2 92).

## T2 result
- Rank 1/8, 24.87 (b02 24.53, b07 23.04, b08 21.90, b01 20.60, b05 20.58, b03 18.79, b04 18.69). Places 162/139/85/89/123/129/141/132. 0 subs. Weighted total 73.94, rank 1.
- Patch before T3: shipped c10 as v9 (008-643cbae6) after +1.6..+2.5 in three non-self fields (2700 t).
- Shove-model caller assumption (qc = 1.4/shove_bb) bracketed vs v9 in mixed field (3v3 + montecarlo + nit): c11 1.7 (tighter shoves) 24.3 vs 25.2 (1000 t); c12 1.2 (looser shoves) 24.6 vs 25.5 (800 t). Both worse -> 1.4 kept; looks near-optimal locally.
- Safety re-check v9 vs 007 (3v3 + maniac + nit, 800 t, seed 1301): 23.7 vs 24.1 (-0.4, noise). Running total for v9 vs 007 in non-self fields: +2.5, +1.65, +1.6, -0.4 (avg ~+1.2). Keep v9 for T3.
- c13 (earlier-street bet weight in narrowing 0.4 -> 0.6): vs v9 (3v3 + montecarlo + maniac, 700 t): 24.3 vs 26.8 -> worse, dropped. Narrowing vs plain bets seems about right; only raises needed more.

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
