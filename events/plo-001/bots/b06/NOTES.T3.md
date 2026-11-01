# Team b06 notes

## Approach (current = v39, submission 012-c8830165; = v31 + HU push/fold mode up to 30bb)
- `bot/evaluator.py`: exact PLO evaluator (2 hole + 3 board) via 5-card rank-key tables
  (dict for python, dense numpy array for vector lookups). Verified identical to engine.
  - `omaha_value` ~6-9 µs; `opp_pair_values` = best value of all 1326 2-card holdings on the
    board (numpy, ~40 µs); `next_card_values` = my value for every next card (~20 µs).
  - Decision time p50 25 µs, p99 ~200 µs, max ~450 µs on the busy machine.
- `bot/pf_eq.npz`: preflop equity of every 4-card hand vs 1,2,3,5,7 random hands
  (3000 random boards, rank-on-board method, averaged over suit isomorphism classes; built by
  `tools/pf_precompute.py` + `tools/pf_post.py`, ~2.5 min). Percentile key = eq vs 2 random
  hands since v24 (`tools/pf_post_v24.py`); was eq vs 3. v24 vs v16 copies: +2.3, +3.4.
- Preflop (normal mode): percentile thresholds by players behind (x1.25 since v14):
  open_th = 1.25*{0:.40,1:.36,2:.28,3:.22,4:.17,5:.14,else .12}; +.15 3-handed, HU .5;
  +.05 per tight (vpip<.25) player behind; pot-raise opens; 3-bet top 3.5% (+3% vs loose
  raisers); call_th ~.12-.25 adjusted by price, position, raiser PFR.
- Short-stack mode (eff or own stack <= 12bb): raise-max if pct < th (th ~.29-.40 by position,
  HU .72, 3-handed +.15, +.05 per tight player behind); facing raise: e1 - adj > need + .02 +
  ICM premium.
- Postflop: p_pair = fraction of opp 2-card holdings beating me now; b1 = 1-(1-p)^6.
  Draw outs = next cards making a strong (straight+, non-counterfeited) hand.
  Facing bets: bettor range = top X, X = .42 - .12*betfrac - .08*(raises-1), times
  sqrt(opp aggression) clamp [.6,1.8]; w_vs = (X-b1)/X; call if eq > pot odds + ICM premium.
  Raise for value if eq>.72 & w_vs>.6. Semi-bluff raise (v16): HU, flop/turn, p_hit>=.4,
  bettor fold rate>.4, 50% of the time.
- Betting when checked to: value if w_now >= .46 (.40 vs non-folders) (v14); bluffs scale with
  per-opponent fold-to-bet rate tracked in observe().
- ICM premium (v6): base*f, f = share of stack at risk (>=.15), base 0 HU/.05/.07/.08 (5+).

## Testing
- `tools/diag.py OPP1,OPP2,... N SEED [mybotdir]` -> points + place histogram per entry.
- Field: 3 copies of previous best + montecarlo, nit, maniac + an older version. Noise is
  about +-2 points at 600 tables, so only changes repeated positive were kept.
- No table reaches the 200-hand cap. The nit (folds everything) scores ~34 by finishing
  3rd/4th: survival matters (flat bottom of the payout ladder), hence the ICM premium.
- Rejected (neutral or worse): tighter postflop calls (X .36: -4), looser (X .48: -2.6),
  stronger ICM premium, loose HU/3-handed preflop calling (v4, v15), wider 3-bets (v17),
  lower value-raise threshold (v18), more frequent semi-bluffs (v19), short-stack mode at
  15bb (v20), wider re-shoves vs loose raisers (v9), HU turn barrels (v21: +1.5 then -0.9),
  more HU flop c-bets (v22: -0.5), tighter SB completes (v23: -0.3).
- Final cross-check, v16 vs all six earlier submissions + montecarlo (700 tables):
  v16 35.8 > 004 35.2 > 005 34.6 > 006 34.4 > 002 33.5 > 003 33.3 > 001 32.7.
- v14 vs v8 in a tight field (nits/checkfold/threshold): 59.7 vs 56.0; maniac field ~53 both.
- v24 vs house zoo (500 tables): 53.3 (nit 45.4, checkfold 42.7), 0 substitutions.
- CAUTION: last-minute 400-table run vs earlier submissions had v24 34.9 vs 007(v16) 38.1
  (noise +-3.4). Evidence v24 > v16 is mixed (+2.3, +3.4, then -3.2). First patch-window task:
  1000-table head-to-head v24 vs v16 (versions/v16); revert to v16 if v24 is not ahead.
  Final balanced run (500 tables, 4x v24 vs 3x v16 + montecarlo): v24 avg 34.7, v16 avg 33.2
  -> kept v24.

## T1 result (bot v24): rank 2/8, 34.81 pts (b05 36.26, b01 34.49, others 24-32)
- Places: 148,155,104,121,126,108,112,126 (8th 12.6%!). Showdown win 48% (local 55-58%),
  postflop aggression 5.2 (8962 bets/raises vs 1724 calls). Field VPIP 21-27% (b07 37%).
- sample_hands.json = first 10 hands of 4 tables only (little info).
- Built `versions/tag` = v24 with all bluffs off and vth .55 as an emulator of the tight field.
  In that field v24/v16 (bluffing) beat the non-bluffing copies by 5-9 pts, and v24 also
  busts 8th ~15% -> the high 8th rate is a property of tight fields, not a bug.
- Tested in tag field (paired seed 1111, v24 = 35.13): v26 (X scale by sqrt(af)*vpip/.35,
  vth .50/.44) 34.87; v27 (ICM base .12 when 7-8 alive) 35.82; v28 (more bluffs: c-bet
  .35+.5fr, generic bluff fr>.42 & rng<fr-.2) 35.43. v29 = v27+v28: seed 2222 40.48 vs v24 39.2.
- Patch before T2: submitted v29 (009-c0125b27), then v31 (010-6f738c54) = v29 with ICM base
  .16 when 7-8 alive. Paired results: v29 vs v24 seed 3333 37.61 vs 36.44; v31 vs v29:
  seed 3333 38.24 vs 37.61, seed 2222 42.19 vs 40.48. v30 (HU BB defense call_th>=.35): 40.22
  vs 40.48 -> rejected. Gains small but consistently positive.
- v32 (premium .20 when 7-8 alive): seed 2222 39.57 vs v31 42.19 -> rejected; .16 kept.
- v31 vs house zoo (300 tables): 54.7, 0 substitutions.
- v31 vs v29 seed 4444 (450 tables): 41.32 vs 38.60 -> v31 ahead on 3 seeds (+0.6,+1.7,+2.7).
- v31 vs submissions 007/008/009 + 2 tag + nit + montecarlo (300 tables, seed 5555): v31 37.6
  first (007 36.8, 008 34.8, 009 31.4; noise +-4).
- Loose field (2 maniac, 2 tag, 008, minraiser, montecarlo; 300 tables, seed 6666): v31 43.8 vs
  008(v24) 47.4 (noise +-3.7). Possible cost of the early ICM premium vs maniacs -> next patch:
  skip the extra 7-8-alive premium when the bettor is loose (vpip > .5), re-test in both fields.
  Second loose-field seed 7777: v31 47.4 vs 008 46.1 -> overall no clear loss vs loose fields.
- Ideas for next patches: premium scaled by stack depth / hands_played; per-opponent
  showdown-based bluff estimates (observe() sees shown cards) to replace the af scaling.

## T2 result (bot v31): rank 2/8, 35.26 (b05 36.60 first; others 29-32). Places
  149,153,114,124,120,122,100,118. Showdown win 48%, aggression 5.7.
- The tag-emulator field reproduces this (v31 there: sd win 48.3%, aggr 5.1) -> 48% is a
  style artifact, not a leak. The emulator field is a good proxy for the real field.
- Weakness found: HU conversion ~50% (1st 149 vs 2nd 153). Paired seeds isolate HU changes
  (places 3-8 identical). v37 (HU push th .72->.85, HU call adj<=.02): +4/+2 firsts.
  v38 = v37 + short-stack mode when HU and eff<=20bb: firsts 96 vs 83 (seed 8080, 500 tables),
  114 vs 104 (seed 9090, 650) -> HU win 61% vs 55%, ~+0.8 pts/table. Submitted 011-d087043e.
- v39 = v38 with HU short-stack mode up to 30bb: firsts 100 (8080) / 123 (9090) vs v38 96/114,
  v31 83/104 (of 162/180 HU finishes). v40 (HU mode at any depth): 102 on 8080 -> marginal, not used.
- Rejected: opens x1.4 (v33, -0.8), semi-bluff raise freq .8 (v35, -0.15).
- Zoo check (house bots, seed 99, 400 tables): v31 52.4 vs v39 50.3. Not truly paired
  (montecarlo house bot is wall-clock dependent -> places 3-8 differ), within noise +-4.
  If T3 shows fewer 1sts than 2nds again or HU problems, revisit HU th (.85) / 30bb cutoff.
- Mixed run (350 tables, seed 4321): 011(v38) 40.2, v39 37.0, 010(v31) 35.7, 008(v24) 33.4,
  tags 27-28, nit 27.8 -> the HU-mode versions lead; v38 vs v39 order within noise (+-3.9).
- Third paired seed 5656 (400 tables): v38 36.86 (78 firsts) vs v39 36.76 (77) -> v39 kept
  (paired firsts over 3 seeds: +4, +9, -1 vs v38).
- v40 (HU mode at any depth) seed 9090: 122 firsts vs v39 123 -> no gain; 30bb cutoff is fine.
- BUG CAUGHT: v38 first draft used undefined local `n_alive` in _preflop -> NameError swallowed
  by act()'s try/except -> folds (scored 26.7). ALWAYS use self.n_alive there, and run a copy
  with `except ZeroDivisionError` (versions/dbg38 style) to expose hidden exceptions:
  v38 had 0 errors in 400 tables.

## Submissions
- 001 v1 baseline; 002 v3; 003 v5; 004 v6 (ICM); 005 v8 (short-stack steals);
  006 v14 (wider opens, thinner value); 007 v16 (semi-bluff raises);
  008 v24 (preflop percentile by eq vs 2 random hands); 009 v29, 010 v31 (patches before T2); 011 v38, 012 v39 (before T3). Versions in `versions/`.

## Known weaknesses
- Crude vulnerability factor; no check-raising; bettor range is one X parameter.
- Preflop deep play is percentile-only (no stack-depth / implied-odds logic).
- Opponent stats need ~20+ hands to move off priors.

## Next steps (patch windows)
- Key = eq vs 1 random hand tested (v25, 500 tables): 38.1 vs v24 copies 37.9 -> neutral,
  v24 (eq vs 2) kept. Could still re-tune open thresholds for the eq-vs-2 key.
- Use tournament results: if we bust 5th-7th a lot, raise ICM premium mid-game; if opponents
  are aggressive, widen X scaling. Consider HU-specific postflop aggression.
