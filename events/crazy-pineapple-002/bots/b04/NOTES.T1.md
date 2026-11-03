## Strategy

**Summary:** A tight-aggressive crazy-pineapple bot that uses lookup tables, not simulation. Preflop it reads precomputed equities for all 1,755 three-card hand classes (against random hands and against top-X% ranges). Postflop it scores the hand by made-hand category plus draw outs, and it compares estimated equity to pot odds. Survival is worth a lot under this points table (even a check/fold bot places well), so it calls all-ins tightly and gets its chips from blind steals, EV-based shoves and value bets.

**Before the flop:** Hands are ranked by percentile of 3-card equity against a random hand (`bot/pre3.json`). With more than 14bb, it opens to 2.2–2.5bb (+1bb per limper) with the top 14% (early) to 40–50% (button/SB). That is ×1.2 when 3-handed, 70% from the SB heads-up, ×1.4 when everyone behind is tight and ×0.8 when someone behind is loose. Heads-up it defends 55% of hands in the BB against raises ≤3bb and 3-bets 10%. It 3-bets the top ~4.5% (wider against frequent raisers) and calls the top 13% (22% from the BB against small raises). Against 3-bets it 4-bets/shoves the top 2% and calls the top 5%.

**After the flop:** It evaluates every 2-card keep from the hole cards with the kit's hold'em feature heuristic (category, kicker, board texture, outs) and takes the best. One-pair and two-pair hands are discounted by 0.08 when facing a bet (0.02 when betting), trips/straights/flushes get +0.05, and every extra opponent costs 0.07. Equity = strength + draw outs (×0.038 on the flop, ×0.021 on the turn). It value-bets 0.6–0.75 pot at strength ≥0.72 (≥0.62 heads-up, ≥0.56 against loose callers) and raises at ≥0.88 (≥0.80 heads-up against a single bet). It calls when equity ≥ pot odds + 0.05 + 0.08×(bet/pot). Bluffs (c-bets, river stabs) are scaled by BLUFF=0.5, cut further against loose callers and raised against nits. For the discard it keeps the pair with the best strength + outs.

**Short stacks and the points table:** At ≤14bb with no raise in front, it shoves when the chip EV of shoving is positive. That EV uses each player behind's estimated calling range (from the pot odds they get, their VPIP, and how often they have called shoves at this table) and the precomputed equity against that range, minus an ICM risk premium × the final pot. The premium is fitted to `kit/icm.py`: equal-stack all-ins need +0.07 equity with 3 left, +0.105 with 4, +0.12 with 5–8, and 0 heads-up. It is scaled down when we cover the opponent ((opp/me)^1.15) or are covered (0.44+0.56·me/opp). Facing a shove or a big raise, it calls only if equity against the shover's estimated range ≥ pot odds + premium, or re-shoves over a raise when that has positive EV. Postflop calls of ≥45% of our stack add the same premium.

**Opponents:** For each seat it tracks VPIP, PFR, postflop aggression and how often the seat calls preflop all-ins. Frequent raisers widen our 3-bet and call ranges, aggressive bettors lower our calling bar, loose players get fewer bluffs and thinner value bets, and tight callers widen our shove range.

**Last change:** v6 (006-f3a23673): postflop calibration against Monte Carlo (tools/calib.py; equity against one random 3-card opponent who keeps the best flop pair). Trips, straights and flushes were underrated by 0.08–0.13, so they get +0.05. One pair and two pair keep the 0.08 discount only when facing a bet; when betting the discount is 0.02, so two pair and top pair/top kicker value-bet heads-up again. Seed 13 field: 47.9–48.2 (v5 got 46.7 on the same seed; v4 copy 44.5–46.1). Against v5 copies on seed 17 it was level (39.6–40.5 vs 39.2–40.8). Before that, v5 (005-1d04a6f5) added heads-up/3-handed preflop ranges, steal widening against tight players, and the ICM premium on big postflop calls.

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

## Next steps (patch windows)
- Read the tournament results: if we bust early often, tighten deep-stack calls; if we finish 3rd–4th a lot, push harder 3–4 handed.
- Use a full icm_equity call when ≤4 players are left (it's cheap at that size) instead of the fitted premium.
- Replace the hold'em `features()` postflop heuristic with a small pineapple-specific table (category × board texture → equity against a betting range).
- Track per-opponent fold-to-c-bet and fold-to-steal to drive bluff and steal frequencies.
