# Team b08 notes

## Strategy

**Summary:** Table-driven shortdeck bot. Preflop uses a precomputed 81x81 class-vs-class equity matrix (shortdeck, Monte Carlo offline, bot/eqmat.json) to get equity vs "top p%" ranges; short stacks play push/fold by explicit chip-EV of shoving/re-shoving against modelled (and read-adjusted) calling ranges; postflop uses a fast made-hand/draw strength heuristic, bets for value often and calls tightly. Everything is lookups, ~25 µs per decision. Tuned by paired 1000-table sweeps against earlier versions, nit and montecarlo.

**Before the flop:** Deep (>15 BB effective): open-raise top ~13% with 7 to act behind widening to ~45% from the SB (OPEN_W x 1.0), 2.2-2.5 BB (+1 BB per limper), 3 BB from SB; in the last 3 seats also steal any top-75% hand when the players behind fold often enough by observed VPIP. SB completes top 50%. BB raises its option with top 12%. 3-bet only top ~5% (AA-TT); call opens when equity vs the opener's range (observed PFR, prior 15%) + 6% implied odds beats price + 8% (top 25% hands; BB defends at price + 5%); fold to 3-bets without QQ+. ≤15 BB: open-shove if EV(shove) vs modelled calls beats the margin, else fold/check; facing an open, re-shove using fold equity (opener continues with half its range). Heads-up SB opens top 60%; 3-handed opens x1.4.

**After the flop:** Strength 0-1 from made-hand category relative to board (top pair/kicker, overpair, two pair, sets, straight/flush quality, flushy/paired-board penalties, shortdeck scaling) minus 0.07 per extra opponent, plus draw equity from outs. Bet 75% pot with ≥0.85, 60% with ≥0.68, 45% heads-up with ≥0.38 (70%); semi-bluff 8+ outs, c-bet 40% pot heads-up, occasional IP stab; bluff frequencies x2.2 (capped at always) scaled x0.4-x2 by the opponent's observed fold-to-bet rate. Facing bets: raise ≥0.9 (or ≥0.8 vs a single bet), call when strength (minus 0.15 x (bet/pot - 0.5), 0.04 per raise, 0.04 per earlier-street bet by the bettor; ±0.08 by the bettor's VPIP and aggression) + draw equity ≥ pot odds + 0.28 (+0.06 if the call is half our stack); shove instead of calling when little would be left.

**Short stacks and the points table:** Push/fold with explicit EV. With ≤5 players left, calling a heads-up all-in uses exact ICM of the win/lose/fold outcomes (+1% margin). Calling all-ins needs equity vs the shover's estimated range (stack-depth table x position factor 1.8 SB / 1.4 BTN / 1.15 CO, widened 50/50 by observed PFR but never narrowed below the table) ≥ pot odds + margin: 0.09 base (x0.5 heads-up, x0.6 three-handed), +0.02 at 5 left (bubble before the 4 paid places), -0.02 when we have <8 BB, +0.02 per player still behind. Payouts 100/45/20/8 are top-heavy so this stays close to chip-EV, with extra caution only where a bust costs places.

**Opponents:** Per-seat VPIP, PFR, calls-vs-all-in counts, postflop aggression and fold-to-bet counts from hand histories (Bayesian priors, nothing kept between tables). Used to widen/narrow raiser/shover ranges, opponents' calling ranges for our shoves, steal decisions, postflop call thresholds (tight/passive bettors = fold more) and bluff frequency.

**Last change:** v11 (011-5b6ea3eb, patch before T4; kept for T5 - T4 gave 20.98, rank 6, within noise of T1-T3; no T5-window variant beat it locally): with ≤5 players left, calling a heads-up all-in now uses real ICM (Malmuth-Harville, same as kit/icm.py, points 100/45/20/8) on the three outcomes win/lose/fold, needed equity = (ICM_fold - ICM_lose)/(ICM_win - ICM_lose) + 0.01, instead of the fixed margin heuristic (e.g. 4 equal stacks: 0.51 vs chip-EV 0.42; with a short stack at the table 0.53; 3-handed 0.49). T3 (v10) was 22.19, rank 3; results flat at ~22 over T1-T3 while b06 rose to 25.8, so a structural fix for the late stage (4th-6th places ~43%) was chosen. Local tests vs v10: +3.4 (800 tables: v11 27.1 vs v10 25.2/23.4/22.6), -1.6 (900 tables: 24.6 vs 27.1/25.3), +1.3 (v11 copies 28.5/26.0 vs v10 26.9/24.9) , -0.7 (1000-table balanced 3 v 3) -> about +0.6 on average, i.e. equal locally, but theory-backed; zoo 43.0. CPU max ~165 µs. ICM for our own open-shoves was also tried and rejected (22.8 vs v11 copies 27.2).

## Log
- v1: zoo 150 tables 38.1 (nit 35.0, montecarlo 30.2, checkfold 26.8).
- v2 test (700 tables, seed 3): nit 27.5, tight 24.7, v1 23.2, noread 22.0, v1.5(read af) 21.2, aggr 20.5 -> tighter is better.
- v2 test (700 tables, seed 4): you 25.9, push18 25.9, nosteal 25.4, tight(old) 23.1, nit 21.8/20.6, v1 21.1, montecarlo 9.2.
- Tools: tools/precompute.py (equity matrix -> bot/eqmat.json), tools/mkvar.py NAME P_X=val (variant copies in vars/).
- sweep1 (1000t): postcall12 23.7, aim06 22.6, bluff15 21.7, base 21.5, bluff05 20.3, thin65 20.0, push11 19.2, nit 24.0.
- sweep2 (1000t): post16 23.7, aim08 22.2, bbdef03 22.0, sblimp60 21.7, open06 21.6, nit 21.3, base 20.8, push20 19.6.
- sweep3 (1000t): post22 24.1, thin50 22.8, aim10 22.7, bluff16 22.1, v2 21.9/19.8, v3 21.4, nit 18.3.
- sweep4 (1000t): post28 23.9, open09 22.2, hum1 22.2, aim12 21.6, v3 21.6, thin45 21.3, cand 20.8, v2 19.4.
- sweep5 (1000t): deep08 24.2, betpen15 22.9, moresteal 22.6, v4 21.8, post34 21.2, v3 20.8/18.9, riv06 20.7 -> postflop margin optimum ~0.28; river penalty hurts.
- sweep6 (1000t): barrel04 24.7, open1 22.3, v5cand 22.2, v4 21.6/21.1/19.2, deep04 21.5, push17 20.4.
- zoo (500t) v5cand: 45.6, nit 30.6, checkfold 25.3, maniac 19.0, montecarlo 17.7.
- sweep7 (1000t, montecarlo seat): bluff16 25.8, v4 25.1/23.3, sblimp30 24.0, bbdef10 23.5, v5 23.4, barrel08 23.1.
- sweep8 (1000t): noftb 23.5, v6cand 23.1, v5 23.0/21.8, bluff2 22.8, sblimp30 22.5, v4 20.6, nit 15.6. Parameter tuning now at noise floor (±2.2).
- sweep9 (1000t): v6 24.3, light3(0.25) 23.9, open1 23.0, v5 23.0/20.5, light3b 22.9, thin45 21.6, nit 13.9 -> keep v6.
- sweep10 (1000t): resteal60 27.0, resteal30 26.1, resteal45 25.4, v6 23.9/23.1/23.0, nit 17.9, montecarlo 6.6 -> v7 uses 0.5.
- sweep11 (1000t): v7 26.2, aim06 25.5, resteal80 25.3, v6 24.5/24.2, vsize1.3 23.2, nit 17.5, montecarlo 6.5 -> keep v7.
- sweep12 (1000t): 3bet-commit<=30BB 25.7, v7 copies 25.6/24.9/24.1/23.8, commit<=45BB 25.4 -> noise, not adopted.
- aggressive field (500t: maniac x2, minraiser, pot_odds, montecarlo, v7 x2): v7 36.4/35.3/34.4, maniacs 16.3/15.7.
- sweep13 (1000t): v7 copies 25.7/25.3/25.0, BB defend 0.02 24.8, HU no-margin+75% opens 24.1, 3bet-commit 24.0 -> keep v7.
- zoo (500t) v7 final: 44.5 (nit 30.6, checkfold 25.4, montecarlo 19.0, maniac 18.9).
- sweep14 (1000t): v7 copies 25.8/24.3/22.9, post32 25.8, post24 25.7, aim12 24.8 -> noise, keep v7 (final build-phase submission).
- sweep15 (1000t): opponents' shove-call range x0.65/0.8/1.2 = 25.3/23.7/24.5 vs v7-equivalent 26.6 and v7 copies 24.9/24.4 -> keep x1.0.
- sweep16 (800t): v7 copies 26.3/25.9 (identical-code copy in "you" seat 23.5 = noise ~±2.5), bluff1.8 25.6, resteal0.6 25.5, steal0.4 24.6 -> no change; 007-aa4f6015 stays.
- all versions at one table (500t): v7 28.5, v6 24.2, v5 24.0, v7-equivalent bot/ 22.8, v4 21.1, v3 21.1, v1 17.3, v2 14.0 -> progression holds; v7 is the build-phase final.
- tight field (400t: nit x3, threshold, montecarlo, v7 x2): v7 38.0/35.7/35.0, nits 17.7/17.2/15.9 -> steals/resteals exploit nits well.
- bot/ now = v7 plus neutral-default params P_VSIZE 1.0, P_3BCOMMIT 0, P_CALLQ 1.0 (behaviour identical to 007-aa4f6015).

## T1 (real field) and patch log
- T1: rank 3/8, 22.81 (b06 24.20, b07 24.07, b01 21.64, b02 21.41, b05 19.96, b04 19.57, b03 19.34). Places 138/112/129/174/146/134/88/79. VPIP 33%, PFR 19%, postflop aggression 7.8 (12873 bets/raises vs 1655 calls), WTSD 6.8%, showdown win 53%. 0 substitutions, p99 100 µs.
- Field VPIP 22-35%, PFR 15-21%: TAG-ish bots, none maniac.
- patch1 (1000t): widen_only 26.0, v8 25.8, m5only 25.5, v7 25.3/24.0/22.7 -> submitted v8 (008-1e7f27cd).
- patch2 (1000t): posw 26.3/24.4, v8 25.1, v7 25.6/24.3/23.0 -> submitted v9 (009-87b50001). Zoo 500t: v9 44.8.
- versions-only table (800t): v9 22.1/21.8/21.0, v8 23.3/20.9, v7 22.4/20.0, v6 21.4 -> all within noise; the T2 changes only matter vs wider real-field shoves.
- patch3 (1000t, info only): v9 copies 25.6/25.3/24.9, v7 23.8, all-in margin 0.06 variant 24.6/23.4 -> locally the 0.09 margin is still better; lower it only if T2 places again pile up in 4th-6th.
- patch4 (700t, info only): bluff x1.0 variant 27.2/25.1 vs v9 25.0/23.5/23.3, v7 24.6. Contradicts sweeps 5-7 (x1.6 > x1.2 > x0.5); T1 postflop aggression 7.8 suggests we may over-bluff vs the real field. Re-test bluff x1.0-1.2 with more tables next window before changing.
- T2: rank 4/8, 21.90 (b06 24.87, b02 24.53, b07 23.04, b01 20.60, b05 20.58, b03 18.79, b04 18.69). Places 125/120/142/145/151/144/90.5/82.5. Postflop aggression 8.3 (13039 vs 1568 calls), WTSD 7.1%, showdown win 51%.
- T2 sample hands: opponents barrel medium hands (JJ under a K, TPTK 2-3 streets, two pair raises) -> our 0.28 call margin may over-fold vs the real field.
- patch T3-1 (1000t versions-only): v9 23.0/22.1/21.1, bluff1.0 22.4/21.4, bluff1.2 21.6, v8 22.3, v7 19.3 -> bluff change was noise, keep 1.5.
- patch T3-2 (1000t, field: aggressive variant x3 [thin 0.38, bluff 2.2, call margin 0.15, open 1.0], nit): aggfield 23.3/22.5/22.3, call-margin 0.24 22.7, v9 21.8/20.4, 0.20 21.2.
- patch T3-3 (1000t mixed: aggfield x2, v9 x2, v7, nit, montecarlo): v9 25.7/24.6, aggfield 25.5/24.2, call-margin 0.24 23.9, v7 23.1 -> 0.24 vs 0.28 is a wash across fields; kept v9 for T3.
- patch T3-4 (1000t: thin42, open10, aggfield x2, v9 x3, nit): aggfield 23.6/22.6, thin42 22.4, open10 22.1, v9 21.9/21.8/21.3.
- patch T3-5 (700t: aggfield x3, v9 x3, montecarlo, pot_odds): aggfield 29.8/26.2/25.1 vs v9 28.4/25.8/25.7 -> pooled aggfield - v9 ~ +0.8 over 4 fields; not significant, kept v9.
- patch T3-6 (900t: aggfield x2, v9 x3, v8, v7, nit): aggfield 23.3/22.7 vs v9 22.9/22.6/21.4. Pooled over 5 fields: aggfield - v9 = +1.6, -0.3, +1.5, +0.4, +0.7 (mean +0.8); edge smallest in fields with calling-station bots (montecarlo/pot_odds), which are probably most like the real field -> v9 kept for T3. Candidate for T4: aggfield's thin value (0.38-0.42) + bluff 2.2 with v9's 0.28 call margin (untested).
- patch T3-7 (700t: aggv9 [thin 0.38, bluff 2.2, open 1.0, call margin 0.28] x2, aggfield, v9 x3, montecarlo, pot_odds): aggv9 28.0/26.2, aggfield 28.0, v9 26.9/26.2/26.2 -> aggv9 +0.7 vs v9, same small edge; worth a bigger test in the T4 window.
- patch T3-8 (700t: aggv9 x2, v9 x3, v8, v7, nit): aggv9 24.5/23.7 vs v9 23.4/22.6/22.2 -> submitted aggv9 as v10 (010-e426f39d).
- zoo (500t) v10: 41.3 (v9 44.8, v7 44.5 on other seeds; ±3.9) -> extra bluffing costs a little vs calling-station house bots; watch T3 vs T2.
- v10 vs v9 (450t, with montecarlo + pot_odds): v10 27.95/27.81/26.24 vs v9 28.56/27.21/25.81 -> even.
- T3 (v10): rank 3/8, 22.19 (b06 25.76, b02 24.30, b07 21.64, b05 21.18, b04 20.85, b01 18.84, b03 18.23). Places 135/114/123/138/146/142/107/95; aggression 9.9; showdown win 49.9%; CPU max 883 µs (p99 100) - watch the 1 ms limit.
- patch T4-1 (800t): v11 (ICM calls) 27.1, v10 25.2/23.4/22.6, v9 24.8/23.5, nit 19.8 -> submitted v11.
- patch T4-2 (900t: v10 x2, v9 x2, v7, nit, pot_odds): v11 24.6 vs v10 27.1/25.3, v9 26.5/25.3 (noise; v11 avg over tests ~ +1 vs v10).
- patch T4-3 (900t): ICM open-shoves at ≤4 players (P_ICMS=1) 22.8 vs v11 copies 28.5/26.0, v10 26.9/24.9 -> rejected, code kept but off.
- patch T4-4 (1000t balanced: v11 x3 vs v10 x3, nit, montecarlo): v11 25.6/24.1/24.1 (avg 24.6) vs v10 27.6/24.7/23.6 (avg 25.3). Pooled v11-v10 over 4 tests: +3.4, -1.6, +1.3, -0.7 = +0.6 -> equal locally; kept v11 for its correct late-stage ICM.
- patch T4-5 (700t, info): ICM threshold also for our re-shoves over a raise (P_ICMR=1) 24.7/24.0 vs v11 25.6/25.3/24.6, v10 25.0 -> no gain, left off.
- all-versions (600t): v8 24.2, v10 23.7, v11 23.4/22.7, v9 22.5, v7 21.2, v5 19.7, v3 15.7 -> v8-v11 cluster within noise; clear gain over v3-v5.
- T4 (v11): rank 6/8, 20.98 (b06 25.72, b02 24.29, b04 21.46, b07 21.37, b05 20.99, b01 20.04, b03 18.15). Places 119/113/142/145/156/152/100/73. Showdown win by tournament 53.4 / 51.1 / 49.9 / 49.0% (falls even between v7 and v9 with identical postflop params -> field getting tougher, not only our params). Real-field means: v7 22.81, v9 21.90, v10 22.19, v11 20.98 (all within ±2).
- patch T5-1 (900t): v12 = v11 with v9 aggression (thin 0.50, bluff 1.5, open 0.85) 26.4 vs v11 28.9/27.0/26.8, v9 27.6/24.7 -> not better locally; kept v11.
- patch T5-2 (900t): all-in margin -0.04 with 6+ players (P_M6) 25.7/25.3 vs v11 27.9/24.8/23.2 -> equal; off.
- patch T5-3 (900t): value-bet size x0.8 25.8/23.5, multiway penalty 0.10 23.0/22.7 vs v11 24.4/23.4/23.2 -> noise; off (P_VSIZE 1.0, P_MWPEN 0.07). Re-test (800t): vs08 26.5/26.2 vs v11 26.8/26.2/24.5 -> +0.5, noise; not adopted.
- patch T5-4 (800t): resteal 0.35 26.1/23.5, resteal 0.40 23.3/18.9 vs v11 (0.50) 22.0/21.5/21.2 -> no consistent gradient (0.35 up, 0.40 flat; build-phase sweep had 0.3-0.6 all equal); not adopted. Re-test (800t): resteal 0.35 26.9/22.8 vs v11 26.5/25.0/23.9 -> -0.2, the +3.3 was noise.
- zoo (500t) v11: 43.0 (nit 28.2, checkfold 26.1, montecarlo 25.4).
- Next ideas: direct per-seat shove-rate read (count preflop all-ins when short) instead of PFR proxy; watch T2 places: if 4th-6th still dominate, lower P_AI_MARGIN to ~0.06.

## Key parameters (bot/agent.py top)
P_PUSH_BB 15, P_OPEN 1.0 (v10), P_DEEPCALL 0.08, P_AI_MARGIN 0.09, P_POSTCALL 0.28, P_BLUFF 2.2 (v10), P_BBDEF 0.05, P_SBLIMP 0.5, P_THIN 0.38 (v10), P_READ 1, P_STEAL 0.6, P_HUM 0.5, P_HUOPEN 0.6, P_BETPEN 0.15, P_RIVPEN 0, P_BARREL 0.04, P_FTB 1, P_LIGHT3 0 (off), P_RESTEAL 0.5, P_VSIZE 1.0, P_3BCOMMIT 0 (off), P_CALLQ 1.0.

## Known weaknesses / next steps
- Postflop strength is a category heuristic (house-bot features()), not real equity vs a range; the large call margin (0.28) compensates. Calibrating strengths by offline simulation per feature bucket is the obvious next step.
- No check-raises, few turn/river bluffs; folds a lot to multi-street aggression (exploitable by a bluff-heavy bot; reads only partly correct for it).
- Tuning field is our own versions + nit + montecarlo; real opponents may differ. Watch tournament results: if we bust early a lot, raise P_AI_MARGIN; if we blind out, raise P_PUSH_BB / P_OPEN.
- "hang" substitutions seen locally are wall-clock stalls under machine load (CPU max <0.6 ms, p99 ~50-100 µs).
