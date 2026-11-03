# Team b03 notes

## Strategy

**Summary:** Equity-driven bot. Preflop uses a precomputed 81x81 shortdeck class-vs-class equity matrix (bot/pre.json) to price shoves and calls against estimated opponent ranges; postflop runs a vectorized numpy Monte Carlo (70-150 samples from a precomputed permutation bank, halved if the decision is already slow; ~0.1-0.25 ms) against opponents' ranges weighted by their preflop and postflop actions. Risk is priced with ICM (exact at 3-4 players, a fitted concave utility at 5-8) because the 100/45/20/8 table makes busting expensive; opponent stats shift ranges, steals and bluffs.

**Before the flop:** Unopened pots: at <=13 BB effective it shoves when the EV of a jam (fold equity from every player who can still call, including limpers; equity vs their calling ranges) is positive; deeper it opens 2-2.3 BB (+1 per limper, 3 BB from SB) with roughly the top 14% (UTG) to 60% (SB) of hands (open table x1.25 since v25; 85% heads-up on the button), scaled by how often the players behind fold to raises; at 13-30 BB it steals at least SB 65% / BTN 50% / CO 36%. Behind limpers it only iso-raises the top 15-20%. Facing a raise: the raiser's range = its observed PFR scaled by position (x0.6 UTG ... x1.68 BTN, x2.2 SB; re-raises x0.45); short all-ins get position-scaled floors of 12-30%; all-ins deeper than 30 BB are read as top 3-10%. Value 3-bets with >55% equity vs that range, re-shoves when the jam EV is positive (re-shove EV assumes the opener calls with 55-95% of its range and players who already called with 35%), otherwise calls by pot odds (deep: BB needs pot odds -7%, others -4%; +3% outside the BB). Completes the SB with the top 70%.

**After the flop:** Monte Carlo equity vs the opponents still in. Opponents who bet, raise or call postflop are modelled by current hand strength: each sampled opponent hand is ranked by its made-hand value on the current board, and only the top 0.6^(bets+raises) x 0.8^(calls) share keeps full weight (min 12%; extra 0.6x when they raised over a bet). Hands below that get a bluff weight (0.1 + 0.4 x observed aggression; 0.3 for pure callers), flush draws at least 0.7 before the river. Bets 60-75% pot with >=64% equity heads-up (lower thresholds multiway, +20% pot vs players who rarely fold), raises with >=78% (+ risk premium), calls when equity beats pot odds (+2%, -3% before the river) plus a premium proportional to the share of stack at risk. Made-hand guards (v26, only with 5+ players alive since v29): when a call or raise commits >=30% of the stack, one pair or worse folds (+25% equity needed), two pair needs +10%, trips +3%; one pair never raises for value, never shoves on a low SPR and value-bets at most 50% pot. With 3-4 players left one pair only needs +5% (+0.06 to raise), heads-up no guard, since ranges are wide and one pair is often best. Bluffs are moderate: flop c-bet as preflop raiser ~55% heads-up (x fold-rate factor), some turn semi-bluffs/barrels, rare river bluffs with no showdown value.

**Short stacks and the points table:** Push/fold below 13 BB by EV with fold equity. With 5-8 players alive, outcomes go through a utility x^a (a = 0.87 at 8 players to 0.78 at 5, fitted to the ICM value of doubling up under 100/45/20/8), so all-ins need extra equity; with 3-4 alive, shoves and calls use exact ICM (copy of kit/icm.py); heads-up is chip-linear. Postflop calls get a 5% (8 players) to 12% (3 players) equity premium times the fraction of stack at risk.

**Opponents:** Per-seat counters, reset every table (fresh Agent): VPIP -> caller range, PFR -> raiser range, fold-to-raise -> steal width, calls vs all-ins -> assumed calling range for our shoves, postflop aggression -> bluff weight in a bettor's range, fold-to-bet -> bluff frequency and value-bet size.

**Last change:** v29 (015-52d425e3) = v27 + made-hand guards switched off/softened with <=4 players alive. Reason: T5 (v27) fixed reaching the top 4 (50.1%, was 43-44%) but only 19% of top-4 finishes became wins (T1-T4: 22-24%) and heads-up wins fell to 42%; the one-pair guards from v26 also applied heads-up and 3-4 handed, where one pair is often the best hand. Local A/B (2 x 1000 tables): v29 25.8 vs v27 copies 24.4, then 24.3 vs 24.6 (pooled +0.5, neutral-positive). Rejected alternative v28 (also replaced exact ICM at 3-4 players with mild utility and cut call premiums): 24.5 vs v27 copies 25.2, and fewer local wins.

## Log
- T5 (bot 013 = v27): rank 7/8, 19.37 pts/table (best so far); places 1st 95, 2nd 130, 3rd 151, 4th 125, 5th 106, 6th 122, 7th 135, 8th 136; P(top 4) 50.1% (fixed); P(1st | top 4) 19% (T1-T4: 22-24%); VPIP 29%, PFR 17%; 1 timeout + 1 hang (max CPU 1314 us, wall 58 ms) in 125k decisions.
- 014-d9b6a156: v28 (late-game: ALPHA 0.9/0.92 instead of exact ICM at 3-4 players, PREM 0.04, guards relaxed late). Local 24.5 vs v27 copies 25.2; bust tool 150 tables: v28 24.8 vs v27 29.3 pts/table. Replaced by v29.
- 015-52d425e3: v29 = v27 + late-game guard relaxation only (keeps ICM). Zoo check: 52.6 pts/table (1st), 200 tables, 0 substitutions. Local 25.8 vs v27 copies 24.4 (seed 301), 24.3 vs 24.6 (seed 311); bust tool 26.4 pts/table on the same seeds.
- T4 (bot 010 = v21t): rank 8/8, 18.15 pts/table; places 1st 104, 2nd 102, 3rd 116, 4th 105, 5th 123, 6th 139, 7th 138, 8th 173 (busting first 17%); P(top 4) 42.7%; VPIP 28%, PFR 14.7% (field 17-21%); max CPU 1177 us, 0 timeouts.
- Local A/B tests are biased: our own versions defend the BB ~100%, so wider steals can't show gains locally; the real field (all PFR 17-21%) ranks us last with the lowest PFR.
- 011-4afbbe53: v25 = v21t + opens x1.25, late-position steals at 13-30 BB (SB 65%, BTN 50%, CO 36%), value 3-bet at >55% equity. Local: 24.1 vs v21t copies 24.4 (neutral); PFR 15% -> 19%, VPIP 29% (like b02, 2nd in the field).
- After the T5 freeze, A/B (600 tables): v27 24.1 vs v26 copies 24.7 (neutral, within +-2.8). Locally no gain; the fix targets real opponents calling re-shoves more than our versions do.
- 013-1be2c765: v27 re-shove fix (cold callers q 0.08 -> 0.35, opener q 0.45 -> 0.55 base). Lesson: run localsim with timeout >= 250 s, or its output is lost.
- 012-7738faad: v26 made-hand guards (24.8 vs v25 copies 23.8). Bust profile v26: turn/river busts 23 (v25: 35), 8th places 7 (v25: 11), preflop busts 57 (v25: 43).
- Bust dump (tools/bust.py, v25, 100 local tables): 23 busts in levels 1-2 (deep!), 35/79 busts on turn/river. Almost all deep busts = one pair / weak two pair stacked off on coordinated or paired boards (AA on 6-7-9-T, KK on 6-7-8-T calling a river jam, AK top pair vs set, two pair vs straights/full houses).
- T3 (bot 008 = v19): rank 8/8, 18.23 pts/table; places 1st 101, 2nd 102, 3rd 134, 4th 107, 5th 131, 6th 155, 7th 124, 8th 146; P(top 4) 44.4% again; VPIP 27%, PFR 15% (field lowest); max CPU 1112 us (no timeout counted).
- Local bust profile (tools/bust.py, 80 tables): 65% of our busts are preflop all-ins, mostly in levels 3-5 (hands 51-125).
- 009-27f5f021: v21 looser preflop calls (26.3 vs v19 copies 24.7).
- 010-64bebeaf: v21t = v21 + timing headroom (M 132/96/64, guard at 0.12 ms). Zoo: 55.4 pts/table (1st), 200 tables.
- Rejected after T3: v24 = v21t + opens x1.15 and calls ~1% looser: 23.6 vs v21t copies 24.2 (neutral).
- Rejected after T3: v23 = v21 + shove-or-fold vs small opens at <=15 BB (no flat calls unless >50% equity): 23.4 vs v21 copies 24.8.
- T2 (bot 007 = v15c): rank 7/8, 18.79 pts/table; places 1st 99, 2nd 129, 3rd 114, 4th 101, 5th 136, 6th 142, 7th 133, 8th 146; VPIP 27%, PFR 15% (field PFR 17-22%); 0 substitutions, p99 500 us, max 813 us.
- T1+T2 diagnosis: P(top 4) = 44% in both (50% expected). Conditional on top 4 we're at par: P(top3|top4) 77-78% (75% exp.), P(top2|top3) 64-67% (67% exp.). So nearly the whole deficit (~2.5 pts) is busting 5th-8th in the early/mid stage. Sample hands (first 10 hands only) show our early decisions are fine and net positive; our seat can be found by the 46-chip (2.3 BB) level-1 opens.
- T1 (bot 005 = v10): rank 8/8, 19.34 pts/table; places 1st 109, 2nd 115, 3rd 124, 4th 98, 5th 105, 6th 135, 7th 140, 8th 174; VPIP 27%, PFR 15% (lowest PFR in the field; top teams 35/20 and 25/18); 0 substitutions, p99 300 us, max 970 us.
- 006-9130ba11: v15 (see Last change).
- 007-aa4b7d56: v15c = v15 + slow-decision guard (M halved if >0.15 ms used before the MC). Zoo check: 50.5 pts/table, 200 tables.
- Robustness (600 tables, field v10 x3 + maniac, minraiser, pot_odds, nit): v15c 31.5 vs v10 copies 32.1 (equal within noise), so the tighter calling isn't exploited by bluff-heavy bots; 0 timeouts, max 913 us.
- Record run (600 tables, v15c vs all accepted submissions 001-006 + nit): v15c 22.5 (1st), 005 22.5, 006 22.3, 001 22.1, nit 21.8, 002 21.2, 004 21.1, 003 19.6. All within noise; 0 timeouts, max 786 us.
- 008-8f8c9e4b: v19 position-scaled raiser ranges (1000 tables: 25.1 vs v15c copies 25.0). Zoo check: 48.0 pts/table (1st), 250 tables, 0 substitutions.
- After T2: v20 (assumed calling rates vs our shoves 16/24/40% -> 20/30/45%): 24.5 vs v19 copies 24.4 (neutral, not adopted).
- After T2: v18 (late-position opens widened to SB 60% / BTN 45% / CO 33% at 13-30 BB only): 24.7 vs v15c copies 24.4 (neutral, not adopted).
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
- After T4: if P(top 4) still ~44%, revisit mid-stage push/fold: alpha risk aversion may be too tight for fast blinds (ICM ignores blind pressure); try alpha 0.93+ at 5-8 players.
- After T3: check whether P(top 4) rose above 44%; if not, look at mid-stage push/fold assumptions (base_q calling ranges 16/24/40%) and blind defense at 10-20 BB.
- Jam-calling calibration for 15-30 BB jams: track each seat's shove frequency separately from PFR (floor 12% may be too wide vs tight jammers).
- Still 6th-8th place too often in T1; check T2 places to see if v15 fixed early busts.
- Learn each seat's bluff frequency from showdowns (bet/raise then shown weak).
- Calibrate shove-calling floors (f_r) per stage using hands jammers show.
- Light 3-bets vs openers that fold to 3-bets often.
