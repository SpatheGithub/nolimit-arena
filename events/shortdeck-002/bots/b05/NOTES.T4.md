# Team b05 notes

## Strategy

**Summary:** Math-first bot. A precomputed exact 7-card hand-value table for the 36-card deck (8.3M entries, colex index, verified against the kit evaluator) powers a vectorised numpy Monte Carlo at decision time (opponent hands sampled directly from their estimated ranges, ~128/96/72 trials for 1/2/3 opponents, ~150 us). Preflop uses precomputed class equities (81 classes vs 1..7 random hands, 81x81 heads-up matrix, equity-vs-top-p% table) to price shoves, calls and opens in chips, with an ICM margin calibrated on exact ICM breakevens for the 100/45/20/8 table.

**Before the flop:** Unopened pots: at <= 16 BB effective (or own stack <= 12 BB) it computes the chip EV of an open shove against each player left to act (and limpers), using a calling range that blends a fixed tight model with a "rational caller" (calls with hands that have enough equity vs my likely shoving range), adjusted by each opponent's VPIP and observed shove-calling frequency, with the ICM margin applied inside each called branch. Deeper, opens to 2.5 BB (3 BB from SB) with the top 16-55% depending on players left to act; iso-raises top 13% over limpers. Facing raises: estimates the raiser's range (shove range from stack depth, open range from observed PFR, both widened for late position/steals), calls or shoves all-ins when equity vs that range beats pot odds (computed on the effective pot: bets above our stack are not winnable) + ICM margin, 3-bets/shoves premiums, resteal-shoves <= 22 BB, otherwise calls with pot odds + implied odds.

**After the flop:** Equity vs each opponent's preflop range (raiser/caller/limper/blind). Value-bets 66-75% pot at equity >= 0.68 multiway / 0.58 heads-up, c-bets 40% pot ~55% of the time as heads-up preflop aggressor on the flop. Facing bets: subtracts a strength discount growing with bet size (x1.6 scale, more on the river, +0.08 for every extra raise on the street, +0.07 for every earlier postflop street the bettor also bet/raised, +0.04 for river overbets; the whole discount is scaled per bettor by their observed postflop aggression - x0.6 for frequent bettors/raisers up to x1.2 for passive ones) and the ICM margin when the call is >= 30% of stack or leaves SPR < 1; then raises if the discounted equity is >= 0.80 (>= 0.70 heads-up), calls if it beats pot odds (effective pot), else folds.

**Short stacks and the points table:** Push/fold below ~16 BB. ICM margin table from exact ICM (full-stack flip breakeven equity): 8 players 0.549, 7 ~0.56, 6 0.572, 5 0.593, 4 0.584, 3 0.568, 2 0.50; scaled by fraction of stack at risk and reduced when we are short.

**Opponents:** Per seat: hands seen, VPIP, PFR, preflop shoves, shoves faced and called, and postflop bets/raises vs checks/calls. These set raiser ranges, shove ranges, shove-calling probabilities and (postflop) how much a bet from that seat is discounted: aggression frequency afq (shrunk to 0.4 over 20 actions) scales the discount by 1 - 1.5*(afq - 0.4), clamped to [0.6, 1.2].

**Last change:** v11 (011-fe328cc0), after T3 (rank 5, 21.18; places 112/132/147/137/115/107/120/130 - early busts now normal, wins still low; b06 with VPIP 35/PFR 20 has won all three): the postflop bet discount is now opponent-adaptive (smaller vs seats that bet/raise often postflop, larger vs passive seats), so we stop over-folding to aggressive players while keeping the caution vs value-heavy bettors. Tests: vs aggressive house field (2 v11, 2 v10, maniac, minraiser, pot_odds, montecarlo; 600 tables) 35.6 vs 32.6 points, wins 258 vs 232, 8th 18 vs 40; clone field 4v4 (1000 tables) 21.62 vs 21.63 (neutral), 8th 474 vs 525. Previous: v10 effective-pot fix (+0.9), v9 barrel discount, v8 raise-war fix.

## Log
- Built bot/data/h7.npy (7-card values, uint16 ranks of 752 distinct values; verified vs kit evaluator, 0 mismatches on 20k pairs), pre.npy, hu.npy, cls.npy via tools/pre7.py and tools/prepre.py.
- v1 vs zoo (150 tables): 39.95 pts/table; checkfold scores 29.6 (survival is valuable!).
- v2 (002-377f2c3b): limper fix + rational-caller model. vs v1 copies: within noise.
- Variant test (1000 tables, field of variants): DISC 1.5 25.5, VB_HU .56 25.0, ICM 2.5 25.0, CALLM .05 24.2 vs identical baselines 23.6/20.6 -> adopted a blend of all four (v3).
- Timing: local p50 25us, p99 ~500us, max up to ~1.9ms with a few "hang" substitutions under heavy machine load (10 per ~50k decisions). Reduced MC trials to 100/80/64 for 1/2/3 opponents.
- Noise is about +-2.2 pts per bot at 1000 tables, so small parameter changes can't be resolved locally.
- v4 (004-feeaeb77): range-sampled MC (noise +-0.04 vs +-0.15 before - old weighted MC had tiny effective sample), exact-ICM margins. vs 4 copies v3: 27.6 vs 25.8.
- v5 (005-5e3afe7a): position-aware opponent ranges, batched eval. vs 3 copies v4 + v3: 26.8 vs 26.1/24.9.
- Variants with no measurable effect (1000 tables, +-2.3): PUSH_BB 20, OPEN 1.25, CBET 0.75 (lowest), tight early (OPEN .75 + CALLCAP .18, 4v4: 21.5 vs 21.7).
- v6 (006-9fe491d4): in-position c-bets (CBIP=1), 4v4 22.1 vs 21.1.
- After v6: CAPB (+0.05 equity when checked to heads-up) 4v4 21.4 vs 21.9 -> left at 0 (code present, no-op). QS 0.8 (assume fewer callers) 4v4 21.3 vs 21.9 -> rejected.
- v6 vs 3 copies of v5 + house: 30.8 vs 29.6 avg. vs aggressive field (maniacs, random, minraiser...): 38.7 (and a v6 copy 39.4).
- ICM 0.7 (less risk-averse) 4v4 21.5 vs 21.75 -> kept exact-ICM calibration (ICM 1.0).
- DISC 1.6 4v4 (900 tables): 22.4 vs 20.9 -> adopted as v7 (007-0c111de1).
- v7 vs 3 copies of v6 + house (500 tables): 30.2 vs 29.6 avg, no timeouts.
- DISC 2.0 vs v7 (DISC 1.6) 4v4 (700 tables): 21.1 vs 22.2 -> rejected; 1.6 looks near the sweet spot.
- VB_HU 0.54 / VB_MW 0.64 (thinner value) vs v7 4v4 (650 tables): 21.4 vs 21.85 -> rejected.
- bot/ on disk == v7 (DISC 1.6, CBIP 1, no-op CAPB hook). Final accepted build-phase submission: 007-0c111de1.

- T1: rank 6/8, 19.96 pts (CI 18.0-21.9); places 113/115/127/118/124/122/113/168 -> busting first is the leak. 2 timeouts in 109.6k decisions (max 1.2 ms).
- tools/places.py TABLES SEED dir1,dir2,... prints per-bot finishing-place counts (8 entries).
- v8 (008-8cce11f0): RW=0.08 raise-war fix. RW 0.14 vs 0.08: +0.8 in one test, -1.0 in another -> kept 0.08.
- Diagnostic (variants/diag logs hands losing >= 50% of stack before hand 75 to $TMPDIR/b05diag.jsonl): of 149, pre_call 45, post-river call 42, pre_raise 29, turn call 12, river raise 9. Preflop all-ins looked reasonable (QQ vs AA, 20bb resteals); river/turn calls vs barrels were the leak.
- v9 (009-b88cd4e0): BARREL=0.07 (see Last change). Checks: mixed field (3 v9, 2 v8, 2 v7, nit, 700 tables) v9 21.6 / v8 22.6 / v7 22.6 (noise; v7 busts first most, 14.8% vs 12.7%); head-to-head 4 v9 vs 4 v8 (900 tables) 21.9 vs 21.3, 8th 438 vs 460, 1st 448 vs 452 -> keep v9 for T2.

- Diagnostic re-run on v9 (250 tables, $TMPDIR/b05diag2.jsonl): 146 big early losses: river call 38, pre call 37, pre raise 24, turn call 15, river raise/bet 15, turn raise/bet 12. Next to inspect: our own turn/river bets/raises that end all-in vs better hands (value-bet sizing into raises with SPR < 1), and preflop calls of all-ins.

- T2: rank 6/8, 20.58 (CI 18.6-22.6); places 113/123/135/130.5/104.5/117/135.5/141.5; 0 subs. Top bots are looser (b06 VPIP 35/PFR 20 won T1 and T2; we are 26/17).
- MSC (shrink ICM margin when avg stack < 12 BB of blinds) 4v4: 21.4 vs 21.8, wins 481 vs 519 -> rejected.
- v10 (010-56b410f4): EP=1 effective-pot fix (see Last change).
- Looser preflop on v10 (OPEN 1.3, CALLCAP 0.42): 4v4 21.95 vs 21.3 (wins 528 vs 472, 8th 529 vs 469), but mixed field (3 loose, 3 v10, 2 v9, 500 tables) loose 21.4 / v10 22.4 / v9 20.9 -> not adopted; v10 stays for T3. bot/ == v10.

- Diagnostic on v10 (300 tables, $TMPDIR/b05diag3.jsonl, all hands where we lose >= 50% of stack): 375 total; before hand 75: 158 = shove/raise 46, river call 42, pre call 21 (was 37 on v9 -> EP fix works), river bet/raise 17, turn call 15. Next candidate: river-specific caution (bigger river discount vs bets after the bettor barrelled, or bluff-catch only with eq well above pot odds) - test 4v4 with tools/places.py before adopting; DISC 2.0 overall was too much.

- BARREL 0.10 vs v10 (0.07) 4v4 1000 tables: 21.4 vs 21.9 -> keep 0.07.

- T3: rank 5/8, 21.18 (CI 19.2-23.1); places 112/132/147/137/115/107/120/130; 0 subs. Weighted 124.64 (rank 5).
- SH (short-handed widening: HU SB open 85%, BB defend cap 0.8, HU 3-bet 12%; 3-handed wider) 4v4: 20.8 vs 22.4, wins 481 vs 519 -> rejected (code present, SH=0).
- v11 (011-fe328cc0): AGA=1.5 adaptive discount (see Last change). AGA 2.5 vs 1.5 in aggressive field: 34.5 vs 34.1 (noise) -> keep 1.5. Mixed field (3 v11, 3 v10, v9, nit; 600 tables): v11 21.9 / v10 23.3 / v9 23.0 - within noise (diff SE ~2.3) but negative; kept v11 because it only loosens vs seats that actually bet often (neutral in clone 4v4, +3.0 vs aggressive bots). Replicate head-to-head 4 v11 vs 4 v10 (900 tables): 21.75 vs 21.51, 8th 424 vs 474 -> neutral-to-positive; v11 plays T4. If T4 is clearly worse than T3, revert to v10 (set AGA=0).

## Known weaknesses / next steps (patch windows)
- Local tests are noisy (+-2.3 per bot per 1000 tables; use 4-vs-4 group splits via tools/mkvar.py variants to halve noise).
- Rare timeouts/hangs locally under heavy machine load (a few per 40k decisions, max ~2 ms); MC trials are 128/96/72 for 1/2/3 opponents - drop to ~100/80/60 if the referee reports timeouts.
- Postflop is simple: no river bluffs, no modelling of postflop bets beyond a size-based equity discount, no check-raises.
- Opponent model only uses preflop stats; could add fold-to-cbet and postflop aggression.
- Push/fold assumptions (calling-range blend) are untuned against the real field: check T1 results for whether we bust too often (call/shove too wide) or blind out.
- Tools: tools/pre7.py (7-card table), tools/prepre.py (preflop tables), tools/verify.py (evaluator check), tools/scen.py / scen2.py (scenario spot checks), tools/prof.py (equity timing), tools/mkvar.py NAME KEY=VAL (variant copies in variants/).
