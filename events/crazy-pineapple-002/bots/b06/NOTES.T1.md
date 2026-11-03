# Team b06 notes

## Strategy

**Summary:** Math-first bot. Preflop decisions use a precomputed table of all 1755 canonical 3-card starting hands (equity vs 1..7 random hands, percentile rank, and equity vs top-X% ranges). Postflop it runs a time-budgeted Monte Carlo (~0.4 ms) of its equity vs random hands and compares to pot odds plus a margin that grows with bet size and shrinks vs aggressive bettors.

**Before the flop:** Opens top 10% (UTG) to 40% (SB) by players left to act (80% as heads-up SB, 45-50% three-handed; widened up to 75% when the players behind are observed tight), 2.2-2.5bb plus 1bb per limper. Heads-up BB defends ~60% vs raises up to 3bb and 3-bets 12%. With <=13bb effective it plays push/fold (ranges widen with fewer players behind and shorter stack). 3-bets top ~3.5-9% depending on raiser looseness; calls by percentile with BB discount; facing all-ins/commits it calls when equity vs the shover's estimated range beats price + ICM margin.

**After the flop:** MC equity (hero 3 cards on flop with best-2 hindsight, 2 after discard) vs n random opponents. Value bets 60-75% pot when equity share is high; c-bets heads-up 65% when equity >= 0.38; calls when equity >= pot odds + margin; raises/shoves with very strong equity. Discard: MC with common random numbers over the 3 possible keeps.

**Short stacks and the points table:** push/fold under 13bb (HU base 66%, SB 58%, BTN 40% ... UTG 16% at 10bb, scaled by (10/eff_bb)^0.7, wider vs tight players behind). Calling all-ins demands extra equity: ICM margin 2% + 1.4% per player beyond two (+4% when 40bb+ deep), scaled by the fraction of our stack at risk, halved under 8bb, zero under 4bb or heads-up. Pot odds count only chips we can actually win; multiway all-ins multiply equity vs each committed player.

**Opponents:** tracks per-seat VPIP, PFR and postflop aggression; widens calls vs loose raisers / aggressive bettors, tightens vs passive ones; opens/shoves wider when the players behind are observed to be tight.

**Last change:** v6 (006-eda54b57): range-equity table re-run with 700 more trials per class and merged (950 total; 250-trial table had ~6% max noise); Monte Carlo equity results cached per (hole, board) and accumulated across decisions on the same street (flop MC gets only ~20-40 samples per call). Mixed field vs v5 copies: 42.4 vs 41.9 (neutral to slightly positive). Earlier v5: steal widening vs tight players (+7 in tight field), HU/3-handed ranges, effective-stack shove prior, no flop overbet shoves.

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

## Known weaknesses / next steps
- Postflop equity is vs random hands; facing bets uses heuristic margins (bet size, multi-street aggression, bettor aggression stat) rather than real range conditioning.
- Flop MC is noisy (3-card best-of-3 evals are slow); a specialized incremental evaluator would allow 2x samples.
- Push ranges are heuristic, not Nash for this variant; no explicit ICM computation at decision time (too slow for 8 players).
- Ideas: range-conditioned MC (reject weak opponent holdings when they bet big), bigger value sizing vs calling stations, track opponents' shove frequency separately from PFR.
