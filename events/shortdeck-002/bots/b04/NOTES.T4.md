# Team b04 notes

## Strategy

**Summary:** Table-driven shortdeck bot. Preflop it uses a precomputed 81x81 class-vs-class equity matrix (36-card deck, flush > full house) to get equity against an opponent's estimated range, and makes push/fold and calling decisions by chip EV with a small ICM margin. Postflop it runs a time-boxed Monte Carlo (about 0.45 ms) against each opponent's preflop range, sampled by rejection from the class percentile table, then bets or calls against thresholds that adjust for bet size and the bettor's observed aggression.

**Before the flop:** Hands are ranked by equity against a random hand (percentile `PCT`). When unopened and deeper than 15bb, it opens to 2.5bb (+1bb per limper) with the top 14% from early seats, widening to 40% on the button and 54% in the small blind (v13: 1.2x the v10 thresholds); these widen against tight players behind and tighten against loose ones. At 15bb or less it shoves when the chip EV of shoving beats folding; callers' ranges are estimated from each seat's VPIP and the pot odds they would get. Facing a raise, it estimates the raiser's range from their observed PFR (shove rate for all-ins; a 3-bet range is 0.55x the PFR range) and compares equity against that range with pot odds. When committed (18bb or less, a big raise, or the raiser all-in), it goes all-in or folds; that includes a resteal shove using fold-equity EV, which also applies at 18–28bb. When deep, it 3-bets with equity of 0.57 or more against the range (v15; was 0.60) and calls when equity beats pot odds by 6%.

**After the flop:** Monte Carlo equity against opponents' preflop ranges: raisers get their PFR range, callers their VPIP range, and checkers any hand. It value-bets 60% of the pot at an equity threshold of 0.58 heads-up, raised by 0.08 per extra opponent. With higher equity it bets 80% of the pot, or shoves when the stack-to-pot ratio is low. It c-bets about 55% of the time heads-up as the preflop raiser, and bluffs the river in position about 15% of the time with air. Facing a bet, it subtracts a range penalty: (0.05 + 0.13 × bet/pot, capped at 2x pot) × (1.3 − 0.8 × the bettor's aggression), plus 0.08 for a re-raise, 0.04 on the river, 0.04 for each earlier street the bettor bet, and 0.07 when calling commits half the stack or more (v16/v17). It raises with adjusted equity of 0.72 or more and otherwise calls when equity beats pot odds.

**Short stacks and the points table:** Push/fold applies at 15bb or less. Shove EV assumes rational callers: a caller calls when their equity against a perceived shove range (25% of hands with 5+ players left, 35% with 3–4, 50% heads-up) beats their pot odds; this comes from a precomputed table, scaled by the caller's VPIP. Facing an all-in, the shover's range uses a position and stack prior (blinds 60%, button 42%, cutoff 32%, then 26% and 18%, wider when the shover is shorter), scaled by their observed looseness. ICM margins come from `kit/icm.py` with the 100/45/20/8 table: an even stack-for-stack all-in needs about 0.55 equity with 8 players left, 0.57 with 6, 0.59 with 5, 0.58 with 4, 0.57 with 3 and 0.50 heads-up. The bot adds that excess (0.05 / 0.06 / 0.07 / 0.085 / 0.08 / 0.065 / 0) times the share of its own stack at risk (minimum 25%) times ICM_SCALE = 1.3, times a depth factor min(1, max(0.25, stack in bb / 30)) (v19: static ICM overstates the value of folding when blinds are big; full margin at 30bb or more, 0.5x at 15bb, 0.33x at 10bb), to all-in calls, resteals, shoves and big postflop calls. Covering a short stack therefore costs only a small margin.

**Opponents:** Per-seat decayed counts (factor 0.985 per hand) of VPIP, PFR, preflop shoves, postflop raises versus passive actions, and folds versus continues when facing a postflop bet. These set raiser and caller ranges, shove-caller ranges, the penalty for facing a bet, and the bluff and c-bet frequency (scaled by fold-to-bet; no river bluffs against calling stations, plus slightly thinner value bets against them).

**Last change:** v19 (submission 014-d88c8409, for T4). The ICM margin is scaled by stack depth: min(1, max(0.25, bb/30)). T3 was rank 6 of 8 (20.85). Early busts were fixed (8th place 130 times; it was 159 in T2), but we reached the final four 54.5% of the time and then underconverted: from there we finished 1st 21% and 4th 30%, which suggests over-tight late play while blinds eat the stacks. v18 (bb/20) against v17 head-to-head: +0.6 on two seeds (21.95 vs 21.31, 21.93 vs 21.32). v19 (bb/30) against v18: 22.24 vs 21.02 (seed 5656) and 22.07 vs 21.18 (seed 7878), +1.0 over 1000 tables. Underneath is v17 (tighter postflop calls against big bets, barrels and stack-off calls), which had beaten v15 23.9 vs 19.3.

## Test log
- Head-to-head, 4x v19 (014) vs 4x v17 (012, the T3 bot), 450 tables, seed 2468: v19 averaged 22.6 vs v17's 20.6 (+2.0). This confirms the depth-scaled ICM gain.
- T3 (real field, v17): rank 6/8, 20.85 ± 1.97. Places: 1st 114, 2nd 112, 3rd 155, 4th 164, 5th 122, 6th 113, 7th 90, 8th 130. Showdown wins 52.3% (T2: 49.5%). Early busts fixed; the final four were underconverted.
- v18 (depth-scaled ICM margin) against v17: 21.95 vs 21.31 and 21.93 vs 21.32 (500 tables each). Shipped as 013-acd463e1.
- v19 (depth bb/30, minimum 0.25) against v18: 22.24 vs 21.02 and 22.07 vs 21.18 (500 tables each). Shipped as 014-d88c8409.
- v20 (depth bb/45, minimum 0.2) against v19 (450 tables, seed 9090): 21.43 vs 21.82, so not shipped. The depth-scaling optimum is around bb/30.
- v19 baselines: 7 maniacs (seed 9, 1000 tables) 39.4 ± 1.9; 7 nits (seed 5, 300 tables) 64.0 ± 5.4 (v15 59.6). No regression.
- Head-to-head, 4x v17 (012) vs 4x v15 (010), 450 tables, seed 9191: v17 averaged 23.9 vs v15's 19.3, and every v17 seat ranked above every v15 seat. This is the strongest confirmation of the postflop-calling fix.
- v17 (barrel 0.04, stack-commit 0.07): montecarlo field 53.8 / 55.4 (v16 52.3 / 53.8, v15 49.6 / 48.7); maniacs 39.4; pot_odds field (v16) 77.2. Shipped as 012-8474ad6b.
- T2 (real field): rank 8/8, 18.69 ± 1.87. Places: 1st 97, 2nd 109, 3rd 142, 4th 156, 5th 118, 6th 112, 7th 107, 8th 159. VPIP 24%, PFR 17%, WTSD 7.9%, showdown wins 49.5%. In the samples (first 10 hands of 4 tables), the bot lost small pots calling down with ace-high plus a gutshot (AQ -229, A9o -275 after calling two barrels).
- v16 (stronger postflop calling penalty): montecarlo field 52.3 vs v15 49.6 (160 tables, seed 99); head-to-head against v15 21.8 vs 21.4; maniacs 39.2. Shipped as 011-5742474f.
- v16 confirmation against the montecarlo field, seed 100 (160 tables): v16 53.8 vs v15 48.7. Over two seeds it is +3.9 (53.1 vs 49.1).
- v15 baselines: 7 maniacs, seed 9, 1000 tables: 40.0 ± 1.9 (v10 39.5); 7 nits, seed 5, 300 tables: 59.6 ± 5.5 (v10 61.3). No regression against house styles.
- v15 (3-bet threshold 0.57) against v13: 22.2 vs 21.0 and 21.7 vs 21.5, so it was shipped as 010-2bbdfc37.
- T1 (real field): rank 7/8, 19.57 ± 1.95. All 8 teams were within noise (19.3–24.2). Places: 1st 109, 8th 139 (expected 125 each). VPIP 22% was the lowest in the field and PFR 15%. In the samples, the bot folded ATs/KQs/99/AJo on the button to a single 2.5bb open and folded TT to a 3-bet after opening.
- v12 (looser cold-calls: call when equity ≥ pot odds in position, or pot odds + 0.03 in the blinds, with pct ≤ 0.6; behind penalty 0.015; 3-bet range 0.6x; 3-bet threshold 0.58): head-to-head against v10 (500 tables) it averaged 20.2 vs 23.1, with every v10 seat ranked above. Cold-calling more loses, so it was not shipped (tools/v12).
- v13 (opens 1.2x wider, 3-bet range 0.55x): head-to-head against v10 averaged 21.9 vs 21.4 and 22.5 vs 20.8, so it was shipped as 009-b8682570.
- v14 (opens 1.4x instead of 1.2x) head-to-head against v13: 22.1 vs 21.2 (seed 31337) and 21.3 vs 21.9 (seed 4040), so even (21.7 vs 21.6). Not shipped; tools/v14 has it. The open-width optimum is around 1.2–1.4x.
- Open leak: TT still folds to a 3-bet to 9bb after an UTG open (3-bet range 0.55x is not enough). Untested fix: a 0.65x range, or always continuing with pct ≤ 0.05.
- v10 baselines for patch rounds: 7 maniacs, seed 9, 1000 tables: 39.5 ± 1.9 (v7 36.7, v9 39.3); 7 nits, seed 5, 300 tables: 61.3 ± 5.5 (v9 58.3, v7 57.7).
- Second head-to-head, 4x v10 vs 4x v9 (450 tables, new seed): v10 averaged 22.2 against v9's 21.0, the same direction as the first run, so v10 (008-fa564900) stays.
- Final build-phase run, one seat each for v10, v9, v7, v5, v2, nit, maniac and montecarlo (300 tables, ±4 per seat): v9 29.7, v5 27.5, v2 25.9, v10 25.4, nit 25.1, v7 23.8. One seat per version cannot separate them; the 4-vs-4 head-to-heads above are the stronger evidence, so v10 was kept.
- Head-to-head 4x v7 vs 4x v9 (600 tables): v9 23.1 vs v7 20.1 average; every v9 seat ranked above every v7 seat.
- Head-to-head 4x v9 vs 4x v10 (ICM_SCALE 1.3, 550 tables): v10 22.7 vs v9 20.6 average; every v10 seat ranked above. 
- ICM_SCALE 1.6 vs 1.3 head-to-head (500 tables): 1.6 averaged 21.1 vs 1.3's 22.2, so 1.3 is kept. 1.6 scored 40.7 against maniacs.
- v8 (postflop value and raise thresholds scaled by (2/(n+1))^0.6 for multiway): zoo +1 but mixed field 25.6 vs v7 copies 30.1 (about 2 sigma worse), so not shipped (tools/v8).
- v9 ICM: maniacs 39.3/40.0 vs 36.7/37.6; nits 58.3; mixed field -1.6 (noise).
- v7 multiway fix: maniac field 31.3 -> 36.7/37.6 (1000 tables, +-2): the clearest gain so far.
- v6 (multi-street barrel penalty, +0.03 per earlier street the bettor bet): measured neutral (29.7 vs 30.8), not shipped; kept in tools/v6.
- v3 (rational shove callers) vs mixed field with 3x v2: 28.7 vs 30.1 avg (noise).
- 500-table v2x4 vs v3x3 + v4cand: v2 21.2, v3 22.3, v4cand 21.3 -> all equal within noise.
- v1 vs house zoo (150 tables): 35.3 (1st), nit 32.9.
- v1+gc fix vs zoo (300 tables): 38.5 (1st), nit 31.5.
- v2 vs 7x v1 (450 tables): 22.9 ± 3.1.

## Known weaknesses / next
- For patch rounds: test changes as 4-vs-4 head-to-heads with 500 or more tables (one-seat mixed runs are too noisy). Candidate snapshots are in tools/v6, v8, v10 and v11.
- MC only gets about 40–80 samples, so equity is noisy (SE about 0.06).
- No showdown-based reads yet; ranges are based on frequencies only.
- The ICM margin is a lookup by player count, not computed per decision (kit/icm.py is too slow for 8 players in 1 ms).
- Ideas not yet tested: a multi-street barrel penalty (neutral so far), milder multiway value thresholds, showdown-based reads, and exact ICM for 5 or fewer players at decision time.
