# Team b04 notes

## Strategy

**Summary:** Table-driven shortdeck bot. Preflop it uses a precomputed 81x81 class-vs-class equity matrix (36-card deck, flush > full house) to get equity against an opponent's estimated range, and makes push/fold and calling decisions by chip EV with a small ICM margin. Postflop it runs a time-boxed Monte Carlo (about 0.45 ms) against each opponent's preflop range, sampled by rejection from the class percentile table, then bets or calls against thresholds that adjust for bet size and the bettor's observed aggression.

**Before the flop:** Hands are ranked by equity against a random hand (percentile `PCT`). When unopened and deeper than 15bb, it opens to 2.5bb (+1bb per limper) with the top 12% from early seats, widening to 33% on the button and 45% in the small blind; these widen against tight players behind and tighten against loose ones. At 15bb or less it shoves when the chip EV of shoving beats folding; callers' ranges are estimated from each seat's VPIP and the pot odds they would get. Facing a raise, it estimates the raiser's range from their observed PFR (shove rate for all-ins) and compares equity against that range with pot odds. When committed (18bb or less, a big raise, or the raiser all-in), it goes all-in or folds; that includes a resteal shove using fold-equity EV, which also applies at 18–28bb. When deep, it 3-bets with equity of 0.60 or more against the range and calls when equity beats pot odds by 6%.

**After the flop:** Monte Carlo equity against opponents' preflop ranges: raisers get their PFR range, callers their VPIP range, and checkers any hand. It value-bets 60% of the pot at an equity threshold of 0.58 heads-up, raised by 0.08 per extra opponent. With higher equity it bets 80% of the pot, or shoves when the stack-to-pot ratio is low. It c-bets about 55% of the time heads-up as the preflop raiser, and bluffs the river in position about 15% of the time with air. Facing a bet, it subtracts a range penalty that grows with bet size, re-raises and the river, and shrinks against aggressive seats. It raises with adjusted equity of 0.72 or more and otherwise calls when equity beats pot odds.

**Short stacks and the points table:** Push/fold applies at 15bb or less. Shove EV assumes rational callers: a caller calls when their equity against a perceived shove range (25% of hands with 5+ players left, 35% with 3–4, 50% heads-up) beats their pot odds; this comes from a precomputed table, scaled by the caller's VPIP. Facing an all-in, the shover's range uses a position and stack prior (blinds 60%, button 42%, cutoff 32%, then 26% and 18%, wider when the shover is shorter), scaled by their observed looseness. ICM margins come from `kit/icm.py` with the 100/45/20/8 table: an even stack-for-stack all-in needs about 0.55 equity with 8 players left, 0.57 with 6, 0.59 with 5, 0.58 with 4, 0.57 with 3 and 0.50 heads-up. The bot adds that excess (0.05 / 0.06 / 0.07 / 0.085 / 0.08 / 0.065 / 0) times the share of its own stack at risk (minimum 25%) times ICM_SCALE = 1.3, to all-in calls, resteals, shoves and big postflop calls. Covering a short stack therefore costs only a small margin.

**Opponents:** Per-seat decayed counts (factor 0.985 per hand) of VPIP, PFR, preflop shoves, postflop raises versus passive actions, and folds versus continues when facing a postflop bet. These set raiser and caller ranges, shove-caller ranges, the penalty for facing a bet, and the bluff and c-bet frequency (scaled by fold-to-bet; no river bluffs against calling stations, plus slightly thinner value bets against them).

**Last change:** v10 (submission 008-fa564900). ICM margins are scaled by ICM_SCALE = 1.3. Over 550 tables, 4 v10 seats against 4 v9 seats averaged 22.7 against 20.6, with every v10 seat ranked above every v9 seat. v9 had introduced the exact-ICM margins (instead of a flat 0.02–0.04): over 600 tables, 4 v9 seats against 4 v7 seats averaged 23.1 against 20.1, again with every seat ranked above. Against maniacs v9 scored 39.3 and 40.0 (v7: 36.7 and 37.6). v7 fixed preflop multiway equity (maniac field 31 to 37); v5 added resteals and VPIP-adaptive steals.

## Test log
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
