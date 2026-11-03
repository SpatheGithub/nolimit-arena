# Team b06 notes

## Strategy

**Summary:** Math-first bot. Preflop decisions use a precomputed table of all 1755 canonical 3-card starting hands (equity vs 1..7 random hands, percentile rank, and equity vs top-X% ranges). Postflop it runs a time-budgeted Monte Carlo (~0.4 ms) of its equity vs random hands and compares to pot odds plus a margin that grows with bet size and shrinks vs aggressive bettors.

**Before the flop:** Opens top 10% (UTG) to 40% (SB) by players left to act (80% as heads-up SB, 45-50% three-handed; widened up to 75% when the players behind are observed very tight, VPIP<14%), 2.2-2.5bb plus 1bb per limper. Heads-up BB defends ~60% vs raises up to 3bb and 3-bets 12%. With <=13bb effective it plays push/fold (ranges widen with fewer players behind and shorter stack). 3-bets top ~3.5-9% depending on raiser looseness; calls by percentile with BB discount; facing all-ins/commits it calls when equity vs the shover's estimated range beats price + ICM margin.

**After the flop:** Deep-stack guard: with 4+ players alive and >25bb, it won't put over half its stack in with one pair (flop) or two pair or worse (turn/river) unless equity >= 0.9. MC equity (hero 3 cards on flop with best-2 hindsight, 2 after discard) vs n random opponents. Value bets 60-75% pot when equity share is high; c-bets heads-up 65% when equity >= 0.38; calls when equity >= pot odds + margin; raises/shoves with very strong equity. Discard: MC with common random numbers over the 3 possible keeps.

**Short stacks and the points table:** push/fold under 13bb (HU base 66%, SB 58%, BTN 40% ... UTG 16% at 10bb, scaled by (10/eff_bb)^0.7, wider vs very tight players behind). Calling all-ins demands extra equity matching exact ICM for this points table: +0.10 with 4+ players left, +0.07 with 3 (+0.03 when 40bb+ deep, x1.2 when the opponent covers us), scaled by the fraction of our stack at risk, halved under 8bb, zero under 4bb or heads-up. Pot odds count only chips we can actually win; multiway all-ins multiply equity vs each committed player.

**Opponents:** tracks per-seat VPIP, PFR and postflop aggression; widens calls vs loose raisers / aggressive bettors, tightens vs passive ones; opens/shoves wider when the players behind are observed to be very tight (VPIP<14% after 12+ hands).

**Last change:** v7 (007-d0ebbd31), after T1 rank 8/8 (23.6 pts, 8th place 27%, 7th 19%, showdown win 39%): deep-stack guard - with >25bb at hand start and 4+ players alive, putting over half our hand-start stack in postflop needs two pair+ on the flop / trips+ on turn-river unless MC equity >= 0.9; tighter postflop commitments (need +0.15 x commit fraction, raise gate 0.86 HU / 0.66 multi, 0.95 after our raise, +0.06 per earlier bettor street); exact-ICM call margins (0.10 with 4+ left, 0.07 with 3; x1.2 when covered); shove-range estimate x0.75; steal widening only vs VPIP<14%. Local: mixed field 47.7 vs v6 copies 40.1 (seed 55); tight field 37.0 vs v6 copies 30.2 (seed 101).

## Notes

- Precompute: tools/pre.py (eq vs k random, 1200 trials/class), tools/pre2.py (pct + eq vs top-X ranges, 250 trials).

## Test log
- v1 zoo 1000 tables: 46.7 (nit 51.3, checkfold 48.1). Busts mostly deep L0 multiway preflop all-in calls.
- v2 zoo 300 tables seed 5: 57.9. Mixed field (v1,v2,mc,pot_odds,nit,threshold,maniac) 1000: 50.1.
- v3 vs 3x v2 + mc/nit/pot_odds/maniac: 43.2 vs v2 avg 42.3. Aggro field: 61.6 vs 60.1. Tight field: 50.7 vs 48.3.
- v4 (steal widening) tight field 53.0 vs v3 copy 45.9; mixed neutral (42.3 vs 42.7).
- v5 (HU ranges, eff-stack shove prior, no flop overbet) vs 7x v4: 32.2 (neutral); mixed vs v4 copies 43.0 vs 41.9.
- Place distribution (mixed field): 1st 25%, 2nd 16%, 3rd 16%, 4th 18%. nit reaches HU 43% but wins rarely.

## Tools
- tools/analyze.py N field seed: runs localsim with logs, chip flow by level/street. tools/busts.py, tools/places.py read the logs.
- v7 trial: ICM margin set to exact-ICM values (0.10 for 4+ left, 0.07 for 3) -> 40.2 vs v6 copies 42.3: reverted (fast blinds + wide shovers make static ICM too tight).
- Exact ICM (kit/icm.py) required equity for an equal-stack flip: 8 left 0.624, 5 left 0.617, 4 left 0.605, 3 left 0.571; covering 2:1 at 8 left 0.567, covered 0.649.

- v7b trial: thinner/bigger value bets (share>=1.3 / HU eq>=0.63, 65-85% pot): +0.7 vs v6 copies (seed 55) but -2.4 in zoo-style field (seed 66): not submitted.
- Chip flow by last action (v6, mixed field, seed 77, 350 tables): river calls -14bb avg (-7000bb total) but that includes earlier-street investment; adding +0.08 river call margin cut call losses ~1000bb, added ~700bb of fold losses, score unchanged (45.19 vs 45.16): reverted.
- Wider late-position opens (OPEN 1/2/3 = 0.48/0.34/0.25): 43.1 vs 45.2 same seed: reverted.
- Version ladder (bot=v6 vs 001..006 + nit, 500 tables seed 88): nit 40.9, v4 34.6, v3 32.9, v6(you) 32.3, v6 copy 30.5, v5 30.1, v2 27.9, v1 26.0. v3-v6 within noise of each other; v1/v2 clearly worse. Nit wins a field of my own aggressive bots (they bust each other while it coasts) -> if T1 shows many early/mid busts, try tightening opens/calls vs. aggressive fields.
- Exact-ICM call margins in the version-ladder field (seed 88): 32.5 vs v6 32.3 -> no gain there either (and -2.1 in mixed field); v6 kept.
- v6 zoo baseline (localsim, seed 5, 300 tables): 57.9 (nit 49.9, checkfold 45.8); 0 timeouts, p99 547us on the busy machine.

## T1 result (v6): rank 8/8, 23.55 pts. Places 1st..8th: 102 82 73 82 93 113 186 269. VPIP 25% PFR 18%, showdown win 39%. Top teams VPIP ~20%. Diagnosis: stacking off / all-in calls too light vs real (tighter, value-heavy) bots.
- v7 tests: tightening alone (no guard) tight field 32.5 vs v6 31.6; + deep-stack guard: mixed 47.7 vs 40.1, tight 37.0 vs 30.2. Stronger guard (>40% stack, 3+ players, eq<0.92): 47.3 mixed (no better) - not used.
- v7 checks: zoo seed 5: 59.4 (v6 57.9). Field (2x v6, 2x v7, 2x nit, mc) seed 202: v7 copies avg 39.2 vs v6 avg 31.2. Chip flow: turn/river folds after investing cost -10..-14bb each (guard + tight calls), river bets +11bb avg.
- Guard from 15bb instead of 25bb: 46.9 vs 47.7 (seed 55): not used.
- Tighter flop c-bets (eq>=0.45, multiway 25%): 45.6 vs 47.7 (seed 55): not used.
- Tighter non-BB preflop calls (call range x0.75 when >3 players): 44.9 vs 47.7 (seed 55): not used.
- v7 fresh-seed check (seed 303, 3x v6 + mc/nit/pot_odds/threshold, 500 tables): v7 48.7 vs v6 copies avg 40.3.

## Known weaknesses / next steps
- Postflop equity is vs random hands; facing bets uses heuristic margins (bet size, multi-street aggression, bettor aggression stat) rather than real range conditioning.
- Flop MC is noisy (3-card best-of-3 evals are slow); a specialized incremental evaluator would allow 2x samples.
- Push ranges are heuristic, not Nash for this variant; no explicit ICM computation at decision time (too slow for 8 players).
- Ideas: range-conditioned MC (reject weak opponent holdings when they bet big), bigger value sizing vs calling stations, track opponents' shove frequency separately from PFR.
