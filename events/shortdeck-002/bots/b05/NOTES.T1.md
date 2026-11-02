# Team b05 notes

## Strategy

**Summary:** Math-first bot. A precomputed exact 7-card hand-value table for the 36-card deck (8.3M entries, colex index, verified against the kit evaluator) powers a vectorised numpy Monte Carlo at decision time (opponent hands sampled directly from their estimated ranges, ~128/96/72 trials for 1/2/3 opponents, ~150 us). Preflop uses precomputed class equities (81 classes vs 1..7 random hands, 81x81 heads-up matrix, equity-vs-top-p% table) to price shoves, calls and opens in chips, with an ICM margin calibrated on exact ICM breakevens for the 100/45/20/8 table.

**Before the flop:** Unopened pots: at <= 16 BB effective (or own stack <= 12 BB) it computes the chip EV of an open shove against each player left to act (and limpers), using a calling range that blends a fixed tight model with a "rational caller" (calls with hands that have enough equity vs my likely shoving range), adjusted by each opponent's VPIP and observed shove-calling frequency, with the ICM margin applied inside each called branch. Deeper, opens to 2.5 BB (3 BB from SB) with the top 16-55% depending on players left to act; iso-raises top 13% over limpers. Facing raises: estimates the raiser's range (shove range from stack depth, open range from observed PFR, both widened for late position/steals), calls or shoves all-ins when equity vs that range beats pot odds + ICM margin, 3-bets/shoves premiums, resteal-shoves <= 22 BB, otherwise calls with pot odds + implied odds.

**After the flop:** Equity vs each opponent's preflop range (raiser/caller/limper/blind). Value-bets 66-75% pot at equity >= 0.68 multiway / 0.58 heads-up, c-bets 40% pot ~55% of the time as heads-up preflop aggressor on the flop. Facing bets: subtracts a strength discount growing with bet size (x1.6 scale, more on the river) and calls if equity beats pot odds; ICM margin added for calls >= 30% of stack; raises with >= 0.85 (>= 0.75 heads-up).

**Short stacks and the points table:** Push/fold below ~16 BB. ICM margin table from exact ICM (full-stack flip breakeven equity): 8 players 0.549, 7 ~0.56, 6 0.572, 5 0.593, 4 0.584, 3 0.568, 2 0.50; scaled by fraction of stack at risk and reduced when we are short.

**Opponents:** Per seat: hands seen, VPIP, PFR, preflop shoves, shoves faced and called. These set raiser ranges, shove ranges and shove-calling probabilities (shrunk toward priors).

**Last change:** v7 (007-0c111de1): postflop bet-strength discount raised from x1.3 to x1.6 (folds more to postflop bets: discount = (0.06 + 0.08 * bet/pot) * 1.6, +0.03 on the river). 4-vs-4 over 900 tables: 22.4 vs 20.9 group average; an earlier field test also had DISC 1.5 on top. v6 (006): in-position flop c-bets (22.1 vs 21.1). v5: position-aware opponent ranges. v4: exact-ICM margins (+1.8 vs v3). Field test: v6 30.8 vs v5 29.6; vs house zoo 45.0 (v1: 40.0).

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

## Known weaknesses / next steps (patch windows)
- Local tests are noisy (+-2.3 per bot per 1000 tables; use 4-vs-4 group splits via tools/mkvar.py variants to halve noise).
- Rare timeouts/hangs locally under heavy machine load (a few per 40k decisions, max ~2 ms); MC trials are 128/96/72 for 1/2/3 opponents - drop to ~100/80/60 if the referee reports timeouts.
- Postflop is simple: no river bluffs, no modelling of postflop bets beyond a size-based equity discount, no check-raises.
- Opponent model only uses preflop stats; could add fold-to-cbet and postflop aggression.
- Push/fold assumptions (calling-range blend) are untuned against the real field: check T1 results for whether we bust too often (call/shove too wide) or blind out.
- Tools: tools/pre7.py (7-card table), tools/prepre.py (preflop tables), tools/verify.py (evaluator check), tools/scen.py / scen2.py (scenario spot checks), tools/prof.py (equity timing), tools/mkvar.py NAME KEY=VAL (variant copies in variants/).
