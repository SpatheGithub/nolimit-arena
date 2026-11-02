# Team b08 notes

## Strategy

**Summary:** Table-driven shortdeck bot. Preflop uses a precomputed 81x81 class-vs-class equity matrix (shortdeck, Monte Carlo offline, bot/eqmat.json) to get equity vs "top p%" ranges; short stacks play push/fold by explicit chip-EV of shoving/re-shoving against modelled (and read-adjusted) calling ranges; postflop uses a fast made-hand/draw strength heuristic, bets for value often and calls tightly. Everything is lookups, ~25 µs per decision. Tuned by paired 1000-table sweeps against earlier versions, nit and montecarlo.

**Before the flop:** Deep (>15 BB effective): open-raise top ~11% with 7 to act behind widening to ~38% from the SB (OPEN_W x 0.85), 2.2-2.5 BB (+1 BB per limper), 3 BB from SB; in the last 3 seats also steal any top-75% hand when the players behind fold often enough by observed VPIP. SB completes top 50%. BB raises its option with top 12%. 3-bet only top ~5% (AA-TT); call opens when equity vs the opener's range (observed PFR, prior 15%) + 6% implied odds beats price + 8% (top 25% hands; BB defends at price + 5%); fold to 3-bets without QQ+. ≤15 BB: open-shove if EV(shove) vs modelled calls beats the margin, else fold/check; facing an open, re-shove using fold equity (opener continues with half its range). Heads-up SB opens top 60%; 3-handed opens x1.4.

**After the flop:** Strength 0-1 from made-hand category relative to board (top pair/kicker, overpair, two pair, sets, straight/flush quality, flushy/paired-board penalties, shortdeck scaling) minus 0.07 per extra opponent, plus draw equity from outs. Bet 75% pot with ≥0.85, 60% with ≥0.68, 45% heads-up with ≥0.50 (70%); semi-bluff 8+ outs, c-bet 40% pot heads-up, occasional IP stab; bluff frequencies x1.5 scaled by the opponent's observed fold-to-bet rate. Facing bets: raise ≥0.9 (or ≥0.8 vs a single bet), call when strength (minus 0.15 x (bet/pot - 0.5), 0.04 per raise, 0.04 per earlier-street bet by the bettor; ±0.08 by the bettor's VPIP and aggression) + draw equity ≥ pot odds + 0.28 (+0.06 if the call is half our stack); shove instead of calling when little would be left.

**Short stacks and the points table:** Push/fold with explicit EV. Calling all-ins needs equity vs the shover's estimated range (stack-depth table blended 50/50 with observed PFR) ≥ pot odds + margin: 0.09 base (x0.5 heads-up, x0.6 three-handed), +0.02 with ≥5 alive, +0.02 more at 5 left (bubble before the 4 paid places), -0.02 when we have <8 BB, +0.02 per player still behind. Payouts 100/45/20/8 are top-heavy so this stays close to chip-EV, with extra caution only where a bust costs places.

**Opponents:** Per-seat VPIP, PFR, calls-vs-all-in counts, postflop aggression and fold-to-bet counts from hand histories (Bayesian priors, nothing kept between tables). Used to widen/narrow raiser/shover ranges, opponents' calling ranges for our shoves, steal decisions, postflop call thresholds (tight/passive bettors = fold more) and bluff frequency.

**Last change:** v7 (007-aa4f6015): re-shove ("resteal") over a single non-committed open when ≤15 BB or the raise is ≥40% of our stack, using fold equity: opener continues with top (0.5 x their estimated open range); shove if EV(fold equity + equity vs calling range) beats the margin. Sweep 10 (1000 tables): resteal variants 27.0/26.1/25.4 vs v6 copies 23.9/23.1/23.0.

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

## Key parameters (bot/agent.py top)
P_PUSH_BB 15, P_OPEN 0.85, P_DEEPCALL 0.08, P_AI_MARGIN 0.09, P_POSTCALL 0.28, P_BLUFF 1.5, P_BBDEF 0.05, P_SBLIMP 0.5, P_THIN 0.50, P_READ 1, P_STEAL 0.6, P_HUM 0.5, P_HUOPEN 0.6, P_BETPEN 0.15, P_RIVPEN 0, P_BARREL 0.04, P_FTB 1, P_LIGHT3 0 (off), P_RESTEAL 0.5, P_VSIZE 1.0, P_3BCOMMIT 0 (off), P_CALLQ 1.0.

## Known weaknesses / next steps
- Postflop strength is a category heuristic (house-bot features()), not real equity vs a range; the large call margin (0.28) compensates. Calibrating strengths by offline simulation per feature bucket is the obvious next step.
- No check-raises, few turn/river bluffs; folds a lot to multi-street aggression (exploitable by a bluff-heavy bot; reads only partly correct for it).
- Tuning field is our own versions + nit + montecarlo; real opponents may differ. Watch tournament results: if we bust early a lot, raise P_AI_MARGIN; if we blind out, raise P_PUSH_BB / P_OPEN.
- "hang" substitutions seen locally are wall-clock stalls under machine load (CPU max <0.6 ms, p99 ~50-100 µs).
