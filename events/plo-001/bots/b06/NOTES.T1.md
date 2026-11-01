# Team b06 notes

## Approach (current = v24, submission 008-4e097e9f; = v16 + preflop key eq-vs-2)
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

## Submissions
- 001 v1 baseline; 002 v3; 003 v5; 004 v6 (ICM); 005 v8 (short-stack steals);
  006 v14 (wider opens, thinner value); 007 v16 (semi-bluff raises);
  008 v24 (preflop percentile by eq vs 2 random hands). Versions in `versions/`.

## Known weaknesses
- Crude vulnerability factor; no check-raising; bettor range is one X parameter.
- Preflop deep play is percentile-only (no stack-depth / implied-odds logic).
- Opponent stats need ~20+ hands to move off priors.

## Next steps (patch windows)
- Key = eq vs 1 random hand tested (v25, 500 tables): 38.1 vs v24 copies 37.9 -> neutral,
  v24 (eq vs 2) kept. Could still re-tune open thresholds for the eq-vs-2 key.
- Use tournament results: if we bust 5th-7th a lot, raise ICM premium mid-game; if opponents
  are aggressive, widen X scaling. Consider HU-specific postflop aggression.
