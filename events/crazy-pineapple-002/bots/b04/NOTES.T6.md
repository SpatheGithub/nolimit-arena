## Strategy

**Summary:** A tight-aggressive crazy-pineapple bot that uses lookup tables, not simulation. Preflop it reads precomputed equities for all 1,755 three-card hand classes (against random hands and against top-X% ranges). Postflop it scores the hand by made-hand category plus draw outs, and it compares estimated equity to pot odds. Survival is worth a lot under this points table (even a check/fold bot places well), so it calls all-ins tightly and gets its chips from blind steals, EV-based shoves and value bets.

**Before the flop:** Hands are ranked by percentile of 3-card equity against a random hand (`bot/pre3.json`). With more than 14bb, it opens to 2.2–2.5bb (+1bb per limper) with the top 14% (early) to 40–50% (button/SB). That is ×1.2 when 3-handed, 70% from the SB heads-up, ×1.4 when everyone behind is tight and ×0.8 when someone behind is loose. Heads-up it defends 55% of hands in the BB against raises ≤3bb and 3-bets 10%. It 3-bets the top ~4.5% (wider against frequent raisers) and calls the top 13% (22% from the BB against small raises). Against 3-bets it 4-bets/shoves the top 2% and calls the top 5%.

**After the flop:** It evaluates every 2-card keep from the hole cards with the kit's hold'em feature heuristic (category, kicker, board texture, outs) and takes the best. One-pair and two-pair hands are discounted by 0.12 when facing a bet (0.02 when betting), trips/straights/flushes get +0.05, and every extra opponent costs 0.07. Equity = strength + draw outs (×0.038 on the flop, ×0.021 on the turn). It value-bets 0.6–0.75 pot at strength ≥0.72 (≥0.62 heads-up, ≥0.56 against loose callers) and raises at ≥0.88 (≥0.84 heads-up against a single bet). It calls when equity ≥ pot odds + 0.08 + 0.08×(bet/pot) (+0.14 more against a raise; +0.10 more for calls of ≥30% of our stack during the first 100 hands). Bluffs (c-bets, river stabs) are scaled by BLUFF=0.5, cut further against loose callers and raised against nits. For the discard it keeps the pair with the best strength + outs.

**Short stacks and the points table:** At ≤14bb with no raise in front, it shoves when the chip EV of shoving is positive. That EV uses each player behind's estimated calling range (from the pot odds they get, their VPIP, and how often they have called shoves at this table) and the precomputed equity against that range, minus an ICM risk premium × the final pot. The premium is fitted to `kit/icm.py`: equal-stack all-ins need +0.07 equity with 3 left, +0.105 with 4, +0.12 with 5–8, and 0 heads-up. It is scaled down when we cover the opponent ((opp/me)^1.15) or are covered (0.44+0.56·me/opp). Facing a shove or a big raise, it calls only if equity against the shover's estimated range ≥ pot odds + premium (+0.05 in the first 50 hands), or re-shoves over a raise when that has positive EV. Postflop calls of ≥45% of our stack add the same premium.

**Opponents:** For each seat it tracks VPIP, PFR, postflop aggression, how often the seat calls preflop all-ins and how often it folds to our postflop bets. Frequent raisers widen our 3-bet and call ranges, aggressive bettors lower our calling bar, loose players and seats that rarely fold to our bets get fewer bluffs and thinner value bets, frequent folders get 1.5× bluffs, and tight callers widen our shove range.

**Last change:** v12 (012-89cbdc1e, for T6) = v11 plus early preflop caution: in the first 50 hands, calling or re-shoving over a big preflop raise or all-in needs +0.05 more equity on top of the ICM premium. v11 (011-a925c517) had added +0.10 equity for postflop calls of ≥30% of our stack in the first 100 hands. Paired tests against v11, positive in 4 of 4: tight clone field seeds 61/71 36.38/33.02 vs 35.98/32.73; loose field (2× loose v8 variant at VPIP ~30%, plus v8/v7/v6/v10/v5) seed 91 35.80 vs 35.16; Monte Carlo bettor field seed 97 47.95 vs 46.98 (v8 45.24). Also seed 89: 35.36 vs 34.70, loose seed 93: 34.90 vs 34.63, and Monte Carlo seed 99: 47.72 vs 45.91, so 7 of 7 positive. Zoo (seed 101): 59.13 vs 58.17. In every local field type: v12 > v11 > v8. The next step (preflop +0.07 for 75 hands) was mixed against v12 (+0.7/−0.5/+0.2), so v12 is the plateau. Real results so far: T1 (v6) 33.30 rank 5; T2 (v7) 33.09 rank 5; T3 (v8) 32.98 rank 4; T4 (v10) 32.62 rank 4; T5 (v11) 30.75 rank 6. T5 drifted against the local evidence (see T5 analysis).

## Notes / log

- Precompute: `tools/pre3.py` (3-card equity vs k=1,2,4,7 random hands, 600 deals per class, flop-based discard) → `tools/post3.py` → `bot/pre3.json`; `tools/pre3r.py` (vs top-X% ranges, 300 deals per bucket) → `bot/pre3r.json`.
- Decision time is ~25µs p50 and ~150µs max locally.
- Zoo test (300 tables): v1 (no 3-card table) 47.8; v2 58.7; checkfold gets ~46 and nit ~48 there, which shows how much survival is worth.
- In the field of v2 copies + house bots: calling shoves wider (chip EV) is clearly worse. Tighter than v2 (×0.6) is neutral.
- No bluffing at all scored 46.2 vs 43 on one seed but did not repeat on another seed (44.4 vs ~45.7), so I compromised at BLUFF=0.5.

## Known weaknesses / next

- Postflop strength is a hold'em heuristic and isn't calibrated for pineapple ranges.
- ICM is a fitted premium (by players left and stack ratio), not a full calculation at decision time.
- Untested: the discard heuristic, bet sizing, and how opponent tracking does against unusual bots.

- ICM finding (from kit/icm.py, equal stacks, all-in for everything): required equity is 0.5 heads-up, 0.571 with 3 left, 0.605 with 4, 0.617 with 5, ~0.61–0.62 with 6–8. Covering the opponent 2× halves the premium. This is why wide chip-EV calls lose points.
- Place distribution of v3 in the v2 field (400 tables): 1st 21.5%, 2nd 11.5%, 3rd 16.5%, 4th 18.5%, 5th 15%, 6th 10%, 7th 5.5%, 8th 1.75%. It rarely busts early and wins heads-up often.
- Many knobs were neutral within ±2.7 (600 tables): tighter opens ×0.75, shove EV threshold −0.5/+0.6 bb, postflop discounts, tighter calls ×0.6.
- Calibration (tools/calib.py), feature strength vs MC equity against one random pineapple hand. River: pair .27/.31, two pair .51/.56, trips .58/.66, straight .74/.87, flush .77/.87. Flop: high card .09/.23 (with 8+ outs .11/.45), pair .36/.49, two pair .64/.69, trips .68/.81.
- Discard heuristic vs a 500-runout MC choice: it differs 17% of the time, with an average equity loss of 0.5% (partly MC noise), so I kept it.
- Final check (1000 tables, seed 23, against 3× v5, v4, nit, pot_odds, montecarlo): v6 40.2, v5 copies 40.3–41.1, v4 39.8, nit 34.9. All of these versions are level against each other; the gains are against weaker and less disciplined bots.
- Rejected after testing on v6 (same seed 13 as v6's 47.9): draw multiplier 1.1 (45.7), BLUFF 0 (45.2), BLUFF 0.8 (43.9), ICM premium ×0.7 (46.2), ×1.3 (46.5). Results weren't monotonic, so the bluff level is mostly noise; kept 0.5.

- Wild field (2 maniac, random, 2 minraiser, nit, v2): seed 31 had v6 51.7 vs v2 56.0. v2-style discounts, ICM ×0.4 and v2's push chart did not change it (50.7–51.4). Seed 37 had v6 54.35 vs v2 54.36, so the gap was noise.

- Push/fold threshold 18bb instead of 14bb: 45.0 on seed 13 (v6 47.9). Rejected.

- v6 place distribution (500 tables, seed 41, field 2× v2 + v4 + nit/pot_odds/montecarlo/maniac; mean 48.1): 1st 27.8%, 2nd 11.8%, 3rd 16.2%, 4th 14.0%, 5th 13.6%, 6th 9.9%, 7th 4.3%, 8th 2.5%. It wins about 70% of heads-up matches; the leak is going out in 3rd–5th.

- Short-stack re-steal with the opener's range ×1.6 when ≤5 players are left: 45.3 on seed 13 (v6 47.9). Rejected.

- Paired fresh-seed test (seed 43, field v2/v4/v5 + nit/pot_odds/montecarlo/maniac): v6 43.8, v6 with BLUFF 0 43.5, so no-bluff isn't better. In direct fields v5 copies are level with or slightly ahead of v6 (seed 17 +0.7, seed 23 +0.4, seed 43 +3.2 for one v5 copy), while v6 as hero beat v5 as hero on seed 13 by +1.2. Overall within noise; kept v6.

- Baselines for patch-window comparisons (same seeds): zoo 1000 tables seed 101, v6 57.43 ±2.35 (checkfold 47.2, nit 46.7). Field 2×v2 + v4 + nit/pot_odds/montecarlo/maniac seed 13, v6 47.9; field v2/v4/v5 + nit/pot_odds/montecarlo/maniac seed 43, v6 43.8.

- All versions at one table (400 tables, seed 202): v6 38.6, v5 38.1, v2 36.3, v4 35.7, v3 35.5, nit 34.0, v1 28.0, maniac 8.8. v6 came first, but it is within noise of v5.

## T1 analysis (patch window 1)
- Leaderboard: b07 37.5 (VPIP 20, PFR 17), b02 35.9, b01 35.3, b08 33.6 (VPIP 34), b04 (us) 33.3 (22/16), b03 29.5, b05 26.3, b06 23.6. The field is tight (VPIP 20–26%) and several teams run ~500µs decisions (likely Monte Carlo).
- The sample hands are only the first 10 hands of 4 tables, so they are of little use.
- Proxy field for testing: `--opponents .submissions/006-f3a23673,.submissions/006-f3a23673,.submissions/005-1d04a6f5,.submissions/005-1d04a6f5,.submissions/004-19478750,.submissions/003-019a1794,.submissions/002-d329e6e7`. Baselines: seed 51 (600 tables) v6 34.91, seed 53 (700 tables) v6 32.90.
- The shove calling-range estimate y = 0.20 − 1.0·(e_req − 0.40) is at a local optimum: 0.14 gives −2 and 0.26 gives −0.7.

- v6 sits at a local optimum against near-clones. A real gain probably needs exploits aimed at specific opponents (per-seat fold-to-steal and fold-to-c-bet tracking) or better postflop equity, not global knob changes.

- v7 zoo regression check (1000 tables, seed 101): 58.35 ±2.34 vs v6 57.43, so no regression against weak bots.

## T2 analysis (patch window 2)
- T2 (v7): 33.09, rank 5. Top: b07 35.3, b01 34.4, b08 33.8, b02 33.5, so the top five are within noise. Our showdown win rate went from 51.3% to 52.0% and postflop calls fell 29% (1780 vs 2505), but the score didn't change.
- New proxy field including v7: `.submissions/007-4569294a ×2, 006 ×2, 005, 004, 002`, seed 61: v7 34.65. Monte Carlo caller field: `007 ×2, 006, montecarlo ×2, pot_odds, nit`, seed 67: v7 44.98, v8 46.06.

- v8 vs v7 follow-up: second Monte Carlo caller seed (73) v8 44.36 vs v7 47.10 (−2.7). Across four paired tests (+0.0, −0.2, +1.1, −2.7) the mean is −0.4, about ±1.0, so inconclusive; kept v8 active. v8 zoo check (seed 101): 58.05 vs v7 58.35. Clone-field pair seed 79 (500 tables, run non-destructively with `python tools/sim2.py <hero dir> <field> N seed`): v8 33.25 vs v7 33.35 (−0.1). Five paired tests average −0.4, so v8 and v7 are equal within noise and v8 stays active.

## T3 analysis (patch window 3)
- T3 (v8): 32.98, rank 4. Top: b02 34.2, b07 33.9, b01 33.4, us 33.0, b08 32.1, so the top five are within noise again. Places: 14.8/11.2/11.1/13.1/12.9/11.7/12.9/12.3%. Showdown win 51.6%.
- The sample hands are level-1 only again.
- Less-noisy preflop tables (tools/cand_bot/pre3*.json, tools/pre3_raw_hi.json) lost ~1.2 in paired tests; the thresholds would need retuning before using them.
- Note: files copied from .submissions are read-only (chmod u+w before writing).

- v9 zoo check (1000 tables, seed 101): 57.21 ±2.32 (v8 58.05, v7 58.35, v6 57.43), within noise.

- v10 zoo check (600 tables, seed 101): 58.12 ±3.08, no regression, 0 substitutions.

## T4 analysis (patch window 4)
- T4 (v10): 32.62, rank 4. Top: b07 34.3, b01 33.9, b02 33.5, us 32.6, b08 32.6. Places: 15.3/10.2/9.9/12.1/14.7/13.9/12.3/11.6%. Every tournament so far has landed at 32.6–33.3.
- The early-survival series (v8→v9→v10→v11) was positive at every step in the clone field and plateaus at 100 hands/+0.10.

- v11 vs v10, extra seed 89 (600 tables): 34.70 vs 34.54 (+0.2). v11 now leads v10 on 4 of 4 seeds.
- v11 checks: zoo (600 tables, seed 101) 58.17 (v10 58.12); Monte Carlo caller field (seed 67) 46.50 (v8 46.06, v7 44.98). No regressions, 0 substitutions.

## T5 analysis (patch window 5)
- T5 (v11): 30.75, rank 6. Places: 13.5/8.8/12.7/12.5/11.1/13.8/14.4/13.2%, so 7th+8th = 27.6%, up from 23.9%. Top: b02 35.0, b08 34.6 (VPIP 30, up from 32.6), b01 33.7, b07 32.3.
- The field has improved since T1: b03/b05/b06 gained 2–5 points and all top teams dropped. Our score relative to the other top-4 average: v6 −2.3, v7 −1.2, v8 −0.4, v10 −1.0, v11 −3.2 (each about ±1.2).
- Local checks disagree with that drift. Loose field (tools/loose_bot = v8 with OPEN_K 1.45, call range 0.22, BLUFF 0.9, PF_DISC 0.06), seed 91: v11 35.16, v8 33.27, v6 33.09. Monte Carlo field seed 97: v12 47.95, v11 46.98, v8 45.24. I went with the local paired evidence.

## Next steps (patch windows)
- Read the tournament results: if we bust early often, tighten deep-stack calls; if we finish 3rd–4th a lot, push harder 3–4 handed.
- Use a full icm_equity call when ≤4 players are left (it's cheap at that size) instead of the fitted premium.
- Replace the hold'em `features()` postflop heuristic with a small pineapple-specific table (category × board texture → equity against a betting range).
- Track per-opponent fold-to-c-bet and fold-to-steal to drive bluff and steal frequencies.
