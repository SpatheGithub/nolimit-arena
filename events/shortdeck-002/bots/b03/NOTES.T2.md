# Team b03 notes

## Strategy

**Summary:** Equity-driven bot. Preflop uses a precomputed 81x81 shortdeck class-vs-class equity matrix (bot/pre.json) to price shoves and calls against estimated opponent ranges; postflop runs a vectorized numpy Monte Carlo (70-150 samples from a precomputed permutation bank, halved if the decision is already slow; ~0.1-0.25 ms) against opponents' ranges weighted by their preflop and postflop actions. Risk is priced with ICM (exact at 3-4 players, a fitted concave utility at 5-8) because the 100/45/20/8 table makes busting expensive; opponent stats shift ranges, steals and bluffs.

**Before the flop:** Unopened pots: at <=13 BB effective it shoves when the EV of a jam (fold equity from every player who can still call, including limpers; equity vs their calling ranges) is positive; deeper it opens 2-2.3 BB (+1 per limper, 3 BB from SB) with the top 13% (UTG) to 55% (SB) of hands (85% heads-up on the button), scaled by how often the players behind fold to raises. Behind limpers it only iso-raises the top 15-20%. Facing a raise: the raiser's range = its observed PFR (prior 16%, x0.45 after re-raises, floors of 12-30% for short all-ins, wider short-handed); value 3-bets with >58% equity vs that range, re-shoves when the jam EV is positive, otherwise calls by pot odds (tighter outside the BB).

**After the flop:** Monte Carlo equity vs the opponents still in. Opponents who bet, raise or call postflop are modelled by current hand strength: each sampled opponent hand is ranked by its made-hand value on the current board, and only the top 0.6^(bets+raises) x 0.8^(calls) share keeps full weight (min 12%; extra 0.6x when they raised over a bet). Hands below that get a bluff weight (0.1 + 0.4 x observed aggression; 0.3 for pure callers), flush draws at least 0.7 before the river. Bets 60-75% pot with >=64% equity heads-up (lower thresholds multiway, +20% pot vs players who rarely fold), raises with >=78% (+ risk premium), calls when equity beats pot odds (+2%, -3% before the river) plus a premium proportional to the share of stack at risk. Bluffs are moderate: flop c-bet as preflop raiser ~55% heads-up (x fold-rate factor), some turn semi-bluffs/barrels, rare river bluffs with no showdown value.

**Short stacks and the points table:** Push/fold below 13 BB by EV with fold equity. With 5-8 players alive, outcomes go through a utility x^a (a = 0.87 at 8 players to 0.78 at 5, fitted to the ICM value of doubling up under 100/45/20/8), so all-ins need extra equity; with 3-4 alive, shoves and calls use exact ICM (copy of kit/icm.py); heads-up is chip-linear. Postflop calls get a 5% (8 players) to 12% (3 players) equity premium times the fraction of stack at risk.

**Opponents:** Per-seat counters, reset every table (fresh Agent): VPIP -> caller range, PFR -> raiser range, fold-to-raise -> steal width, calls vs all-ins -> assumed calling range for our shoves, postflop aggression -> bluff weight in a bettor's range, fold-to-bet -> bluff frequency and value-bet size.

**Last change:** v15c (007-aa4b7d56; v15 = 006-9130ba11 plus a guard that halves MC samples when a decision is already >0.15 ms in), after T1 (rank 8, 19.3 pts; 8th place 17.4% of tables = busting first too often). (1) Bettor ranges are narrowed by hand-strength percentile on the board instead of 'paired the board or not' (in shortdeck nearly every hand pairs, so the old filter overrated our equity vs bets and raises). (2) Preflop all-ins deeper than 30 BB are read as narrow (top 3-10%) instead of the 12% floor meant for short jams. (3) MC samples trimmed ~12% (T1 max CPU was 970 us). Test: 900 tables, v15 26.2 vs v10 copies 22.4.

## Log
- T1 (bot 005 = v10): rank 8/8, 19.34 pts/table; places 1st 109, 2nd 115, 3rd 124, 4th 98, 5th 105, 6th 135, 7th 140, 8th 174; VPIP 27%, PFR 15% (lowest PFR in the field; top teams 35/20 and 25/18); 0 substitutions, p99 300 us, max 970 us.
- 006-9130ba11: v15 (see Last change).
- 007-aa4b7d56: v15c = v15 + slow-decision guard (M halved if >0.15 ms used before the MC). Zoo check: 50.5 pts/table, 200 tables.
- Robustness (600 tables, field v10 x3 + maniac, minraiser, pot_odds, nit): v15c 31.5 vs v10 copies 32.1 (equal within noise), so the tighter calling isn't exploited by bluff-heavy bots; 0 timeouts, max 913 us.
- Record run (600 tables, v15c vs all accepted submissions 001-006 + nit): v15c 22.5 (1st), 005 22.5, 006 22.3, 001 22.1, nit 21.8, 002 21.2, 004 21.1, 003 19.6. All within noise; 0 timeouts, max 786 us.
- Rejected after T1: v16 (cold calls +8% equity outside BB, deep BB defense tighter, 3-bet at >55% instead of >58%): 21.6 vs v15 copies 24.4 (worse). In that run v15 copies 24.4 vs v10 copies 23.7.
- 001-e62efd56: v1, zoo 40 tables 46.8 +- 15.
- 002-dc566614: v3, ICM for 3-4 players, jam-call tracking, perm bank.
- 003-a81e28f9: v6, utility risk aversion at 5+ players, postflop call premium. 800 tables: v6 28.9 vs v5-equivalent copies 24.9 vs v4 copies 21.6.
- 004-58aa3e60: v8 = v6 + tight iso-raises behind limpers (neutral: 23.2 vs v6 copies 23.8).
- 005-f342d4c0: v10 = v8 + fewer flop c-bets: 25.8 vs v8 copies 22.8.
- Final check (400 tables, all accepted versions + nit/montecarlo/maniac): 005 26.5, 003 27.9, 001 26.5, 004 25.9, nit 25.3, 002 23.5 (all within +-3.6 noise). The accepted versions are about equal against each other; gains show against weaker or looser fields.
- Rejected: v14 tighter early-position opens (x0.85) and cold calls (+8% equity outside BB): 23.7 vs v10 copies 23.2 (neutral).
- Rejected: v13 more turn/river bluffs (+30%): 22.9 vs v10 copies 23.4 (neutral). Final zoo check of v10: 52.1 pts/table over 250 tables (1st), 0 substitutions.
- Rejected: v11 fewer turn/river bluffs: 21.0 vs v10 copies 24.3 (worse). v12 thinner value bets (0.60 heads-up): 23.5 vs v10 copies 23.4 (neutral).
- Rejected: v7 wider steals when P(all fold) high: 22.2 vs v6 copies 24.9. v9 stronger risk aversion (alpha 0.81 at 8 players, bigger premiums): 23.6 vs v8 copies 24.1.
- Observation: in local fields the tight 'nit' house bot scores ~24-27 (near top): loose bots bust each other and survival pays with 100/45/20/8. Less bluffing and more risk aversion have tested better than more aggression.
- Noise: +-2.3 points per bot at 900 tables; one run can't resolve differences under ~3 points.
- Timing: p99 ~300-500 us on the loaded machine; rare >1 ms spikes under load (1 timeout in ~100k decisions). Guards: ICM loop stops at 0.4 ms.
- Snapshots of versions live in snap/ (v3, v4, v5x, v6, v8, v8b, v10, v11) for A/B runs: `python kit/localsim.py --opponents snap/v10,...`.

## Next ideas
- Jam-calling calibration for 15-30 BB jams: track each seat's shove frequency separately from PFR (floor 12% may be too wide vs tight jammers).
- Still 6th-8th place too often in T1; check T2 places to see if v15 fixed early busts.
- Learn each seat's bluff frequency from showdowns (bet/raise then shown weak).
- Calibrate shove-calling floors (f_r) per stage using hands jammers show.
- Light 3-bets vs openers that fold to 3-bets often.
