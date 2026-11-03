# Team b01 notes

## Strategy

**Summary:** Preflop uses precomputed 3-card equities (vs random and vs top-X% ranges). Short-stack spots use an explicit push/fold EV model, with exact ICM when 3-4 players remain. After the flop, a fast Monte Carlo (lookup-table evaluator, ~1 µs/eval; wall budget 0.38 ms after the flop, 0.42 ms for the discard) estimates equity, then discounts it against the bettor's likely range.

**Before the flop:** Opens by percentile with a position-based width (×0.9: about 14% UTG to 43% SB; widened short-handed: HU 78%, 3-handed 42-50%, 4-handed 30-36%; ×1.4, capped at 75%, when every player behind has VPIP<30% over ≥12 hands; in today's tight field this usually applies). Sizes 2.2-3 bb, +1 bb per limper. 3-bets when its equity vs the raiser's estimated range (from observed PFR) is ≥0.60. Flat-calls only if equity ≥ price·λ+0.08 and ≥0.46 (0.40 in the BB or heads-up), because loose flat calls were the biggest leak in diagnostics. At ≤14 bb effective it shoves or folds by EV (opponent call widths depend on stack depth and observed VPIP). Facing a normal raise at ≤14 bb it reshoves with ≥0.45 equity vs the raiser's range or folds; it flat-calls only in the BB at a good price.

**After the flop:** MC equity vs random hands (3-card hindsight opponents on the flop, 2-card after the discard). Facing a bet it raises equity to a power (1.25 + 0.35·raises + bet-size term + 1.8, +0.4 on the turn, +0.2 on the river, adjusted by the bettor's aggression factor: −0.8 if AF>2.5, −1.2 if AF>4) and compares that with the pot odds. The heavy discount was the largest single gain: house bots bet for value. Value-bets at ≥0.60 equity heads-up (≥0.66 multiway). C-bets about 55% heads-up as the preflop raiser, semi-bluffs draws, and bluffs the river rarely. Bluff frequency is scaled by the target's observed postflop fold rate (×0.35 vs stations, up to ×1.5 vs folders), and it value-bets thinner vs stations, pot-sized on the river with ≥0.8 equity. Discard keeps the pair with the best MC equity.

**Short stacks and the points table:** A loss-aversion factor λ (1.06 with 6+ players, 1.12 with 4-5, 1.18 with 3, 1.0 heads-up; reduced when short or when chip leader) raises the equity needed for all-in calls. Preflop all-in calls also need +0.10 equity over the λ-adjusted price, because loose all-in calls were a leak. Heads-up the margin is 0 and 3-handed 0.05. Heads-up, it assumes a shover holds a near-equilibrium range (×0.7 of 75/58/45/35/25% at ≤6/10/15/20/>20 bb) and a raiser at least 42%; 3-handed, shove ranges are widened ×1.3. With 3-4 players left, preflop all-in decisions use exact ICM (Malmuth-Harville, the same as kit/icm.py, over the open places' points): calling a shove compares win, lose and fold outcomes; open-shoving (when ≤2 opponents could call) weights fold equity and each caller's call width.

**Opponents:** Per-seat VPIP, PFR and postflop aggression from the hand histories. These set open-range and call-width estimates and the postflop discount.

**Last change:** v11 (011-d839e02f) for T3: the steal widening now triggers when every player behind has VPIP<30% (was <20%), with ×1.4 (was ×1.6). The field's VPIPs are 20-29%, so the old trigger almost never fired. Over 7 seeds of 8-seat localsim (2 copies vs v10 copies, T2-like fields): +3.0, −2.6, +4.1, +1.9, −0.7, +5.0, +1.5, mean +1.75 ± 1.0. v10 (010-01a4a4fb): heads-up and 3-handed shove-calling fix; T2 rank 2/8 (34.41), 1st places up from 108 to 119.

## Notes
- Evaluator: bot/evalr.py, additive keys + tables exported from kit fasteval (verified identical on 20k hands).
- Preflop data: bot/pre3.json from tools/pre.py (1755 suit-canonical 3-card classes; eq vs 1/2/3 random; eq vs top 5/10/15/25/40/60%).

## Test log (localsim, 300 tables, ±~3.8 stderr)
- v9 vs real v8/v6 submissions (seed 52): v9 42.2, v8 45.6/42.6, v6 44.3. Seed 53: v9 42.3/42.6 vs v8 43.3/43.1. Over four runs v9 vs v8 is a toss-up, with v8 slightly ahead in the last two. In a patch window, revert open to 0.8 or run larger A/Bs before trusting either.
- v9 vs the standard zoo (300 tables, seed 51): 56.2, 1st (nit 48.4, checkfold 44.5), 0 substitutions, p99 500 µs.
- Final v8 vs the standard zoo (400 tables): 61.3, 1st (nit 49.0, checkfold 45.8, montecarlo 25.3). v1 was 43.9 there.
- v1 (no extra discount) vs zoo: 43.9, nit 48.6, checkfold 48.7. Surviving is worth a lot here.
- Diagnostics (tools/diag.py, chips by the last aggressive action): turn/river calls lost heavily in v1 (fixed by g+1.8); then preflop flat calls lost (fixed by cfloor 0.46 and short-stack reshove-or-fold).
- Noise-level (no clear effect): open width 0.6-1.1, lam ±0.15, push 10 vs 14, three 0.55, cbet 0.5, vthr +0.05, cfloor 0.52, flop-only semi-bluff, gf (smaller flop discount) 0.8/1.4 (slightly worse), rv 1.3 (same), rv 0.8 (worse).
- Later noise-level tests (no change adopted): open size 2.2/3.0 bb, three 0.56/0.64, cbet 0.7, late-position open ×1.3/1.6, BB defense floor 0.02/0.10, river discount +0.5, vthr +0.03 (worse), 2-card flop opponent model, mg 1.2.
- Vs a c-bet-heavy TAG test bot (tools/cbettor): our versions 43-44, c-bettors 25-31.
- Robust: v3 tops an aggressive field (maniac×2, random, minraiser): 51.6 vs v2 48.9 vs v1 43.9; nit-heavy field: 43.6 vs nits ~28.

- Last build-phase tests (not adopted): all-in margin ac 0.14/0.18 (38.2/41.1 vs v8 47.8/42.5); heads-up range widening ×1.6 (41.3 vs v8 ~41.9; 42.3 vs v8 46.1/46.0); river discount +0.5 and the 2-card flop model (each won one seed and lost the other).
- tools/cap.py: in 30 test tables every table ended with one winner between hands 67 and 168. The 200-hand cap and ICM split essentially never apply, so every table ends heads-up and 1st vs 2nd (100 vs 60) is decided there.

- Final v8 diagnostics (40 tables vs v6/v7/cbettor/nit/montecarlo/maniac/pot_odds): every category profitable except blinds ("nothing", −38 per hand) and small-n turn calls (n=5, −6.9k). Biggest earners are preflop reshoves (+75k), river/turn value bets and flop bets. v8 vs v6/v7 copies (400 tables): 38.0 vs v6 39.4/37.2 and v7 38.4/37.3, within noise.

- Turn call margin mt +0.05 (mt5): 42.5/39.9 vs v8 43.9/42.7, worse. Turn-call losses in the diagnostics look like small-sample variance.
- Reshove threshold rs 0.42 (rs42): 43.6/39.8 vs v8 42.7/41.9, not better, so it stays at 0.45.
- c-bet ×1.4 (cb14): 42.8/42.2 vs v8 44.6/42.6, not better (cbet 0.7 was also slightly worse), so it stays at 1.0.

## Patch window before T2 (tests)
- T1: rank 3/8, 35.34 pts. Places 1st 108, 2nd 180, 3rd 176, 4th 129, 5th 130, 6th 107, 7th 91, 8th 79. 0 substitutions, p99 500 µs. Weakness: converting heads-up (wins only ~37% of heads-up finishes).
- New tools: tools/hu.py A B N SEED plays heads-up (8000 chips each, 160/320 rising) and reports A's win rate. tools/three.py A OPP1,OPP2 N SEED does the same 3-handed (5300 each) and reports A's average points. tools/pusher is a Nash-style push/fold test bot.
- Heads-up shove-calling fix (hux): ×1.0 vs cbettor 58.7%, ×0.7 60.7%, none 53.0%. vs pusher: ×0.7 52.0%, ×1.0 ~50%, none ~51%. vs v9 logic about 50%. ×0.7 adopted (v10).
- Rejected (noise or worse): heads-up shove-or-fold up to 20 bb (47.7%) / 25 bb (44.0%) vs pusher (current 49%); heads-up postflop discount −0.6/−1.0/−1.8 (vs pusher and cbettor, ±2%); 3-handed λ 1.06 and 3-handed open ×1.25 (3-handed avg pts 68.9/69.9 vs 68.6).
- v10 vs v9 in 8-seat fields: 46.4 vs 43.3/40.7; 44.5 vs 44.5/43.5.
- 3-handed (tools/three.py): v10 vs (v9, pusher) 67.1 vs v9's 64.6; v10 vs (v9, cbettor) 67.3 vs v9's 65.2. The fix helps 3-handed too.
- Heads-up multiplier sweep (seed 14): vs pusher ×0.5 52.3%, ×0.7 55.0%, ×0.9 55.0%; vs cbettor ×0.5 54.7%, ×0.9 59.7%. 0.7-0.9 is the sweet spot.
- 8-seat with v8/v9/v10 together (seed 66): v9 40.6, v10 39.9/38.5, v8 39.5, all within noise. Heads-up gains are diluted when most opponents are our own versions, which play each other heads-up at about 50%.
- Wider heads-up defense floor (−0.12 instead of −0.06; tools/hdf), seed 24: maniac 51.0% (v10 51.7%), cbettor 56.3% (57.3%), minraiser 59.7% (54.7%). Mixed, not adopted. Seed 25: 48.3/50.3/56.7 vs v10 48.7/50.0/55.3, a wash. Slightly positive only vs minraiser; retest with more seeds later.
- Heads-up v10 vs v9 over 4 seeds: 47.7, 52.7, 50.7, 49.7% (mean 50.2%). Even head-to-head, but v10 gains vs non-self styles (cbettor, pusher).
- 3-handed widening ×1.6 with no margin (t3w) vs v10's ×1.3 and half margin, 4 three-handed comparisons: +0.9, +0.9, −0.5, −1.3. Net about zero, not adopted.
- Adaptive heads-up shove-or-fold vs frequent 3-bettors (tools/ar: ≥35% 3-bets vs our opens over ≥6 spots, eff ≤20 bb): no effect (vs pusher 52.0% vs 52.3%, vs cbettor 55.3% both). The trigger rarely fires; not adopted.
- 4-handed open ×1.25 (o4a): 41.1/39.9 vs v10 40.2/38.9, noise, not adopted. The T1 sample hands are early-game only (hands 1-10), so no late-game insight.
- Heads-up vs house bots: nit 95%, montecarlo 77%, pot_odds 69%. v10 vs zoo (8-seat, 300 tables): 55.7, 1st.

## Patch window before T3 (tests)
- T2: rank 2/8, 34.41 pts (b07 35.34). Weighted total 104.15, rank 2. Places 1st 119 (T1 108), 2nd 156, 3rd 165, 4th 110, 5th 139, 6th 125, 7th 92, 8th 94. 0 substitutions, p99 500 µs. The heads-up fix raised heads-up conversion from ~37% to ~43%. More 5th-8th places than T1, but v10 didn't change ≥4-handed play, so that is field change or noise.
- Field from the leaderboards: VPIP 20-29%, PFR 15-20%, mostly tight-aggressive.
- Rejected (8-seat runs vs v10 copies, all noise or worse): steal trigger relaxed to VPIP<0.25/0.30 with ×1.4 (34.9/39.8 vs v10 34.4-38.9); combo (st30 + 4-handed ×1.25 + heads-up floor −0.12): 40.6 vs 39.8, 37.7 vs 39.0, 40.1 vs 41.3; flat-call floor 0.52/0.58: seed 74 worse (36.0/33.7 vs 38.1), seed 75 better (37.7/40.0 vs 35.3).
- 5-handed harness (tools/five.py: 3200 chips at 80/160, points 100/60/40/25/15, fair share 48): v10 54.1 vs λ(4-5 players) 1.04 variant 53.9. No change.
- 5-handed push/fold: push 17 bb 50.3 vs v10 49.2 (seed 31). rs 0.42 over seeds 31-33: +2.9, −1.3, −0.7 (mean +0.3). Noise, not adopted.
- st30 (steal ×1.4 when all behind have VPIP<0.30) vs v10 over 5 seeds (70, 76-79): +3.0, −2.6, +4.1, +1.9, −0.7, mean +1.15 ± 1.2. Seeds 80/81 added +5.0/+1.5 (7-seed mean +1.75 ± 1.0), so it was adopted as v11. Zoo regression check (seed 64): v11 57.3 vs v10 55.7. After submitting: seed 82 v11 41.5 vs v10 34.5/33.4 (+7.6); seed 83 (loose field, trigger rarely fires) 44.4 vs 48.8/45.5 (−2.7). 9-seed mean about +1.9.
- Thinner heads-up value bets (thr −0.05, tools/huv), seed 26: cbettor 54.0% (v10 51.3%), maniac 44.7% (45.3%), minraiser 50.3% (50.7%), v9 47.7% (47.0%). Noise, not adopted. Heads-up results vary ±3-5% between seeds at 300 matches.
- The diagnostic's "pf_call_vs" loss (−97 per hand) is mostly BB defenses, where folding also loses the BB, so the category is not a true leak.

## Known weaknesses / next
- CANDIDATE for the T4 window: steal multiplier ×1.6 instead of ×1.4 with the VPIP<30% trigger (tools/st16). Seeds 84/85 vs v11: +3.8, +1.5. Needs more seeds before submitting. Seeds 86/87: +1.3, −1.3 (4-seed mean +1.3 ± 1.1). The submit attempt was stopped by the user, so v11 (×1.4) stays active and bot/ was restored to v11. Seed 88: st16 38.0/35.5 vs v11 37.9/36.2 (−0.3). 5-seed mean about +1.0, still marginal.
- TOP ITEM for the next window: heads-up vs aggressive bots is only even. v10 vs maniac 49.3% (v9 44.3%), vs minraiser 52.0%, though both are weak in full games. A smaller heads-up discount (hug 1.0) gave maniac 51.7%, minraiser 51.3%: noise, not adopted. Range multipliers ×0.7/0.9/1.0 vs maniac (seed 21): 49.7/48.0/48.7%, no effect. Probably inherent: with fast blinds, shove-often play is near-optimal at short stacks. Ideas: call wider vs high-PFR shovers heads-up, use opponent-specific shove widths from observed all-in frequency, and check-call more vs high-AF bettors heads-up.
- Heads-up play is generic: push/fold call widths are the 8-handed defaults scaled by VPIP. A proper HU push/fold chart is the top idea for a patch window, but the quick ×1.6 widening tested neutral to worse, and ×0.7 narrowing tested neutral (43.3/42.1 vs v8 43.3/42.7).
- Rarely calls flop bets (folds or raises), so heavy c-bettors could exploit it. Watch the opponent stats in results.
- MC is vs random hands with a power discount, not real range sampling.
- Exact ICM only for 3-4-handed preflop all-ins; elsewhere a heuristic λ. No special heads-up postflop strategy.
- Tools: tools/mk.py NAME key=val creates a variant copy of bot/ in tools/NAME; tools/diag.py MODULE N FIELD prints chip flow by decision type.
