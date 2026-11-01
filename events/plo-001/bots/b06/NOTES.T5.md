# Team b06 notes

## Strategy

**Summary** — Pot-limit Omaha bot, v45 (submission 013-a6a42b0d). Exact hand evaluation
(2 hole + 3 board cards) from precomputed tables; tight-aggressive preflop driven by a
precomputed equity table of all 270,725 starting hands; postflop decisions from where our
made hand ranks against every possible opponent holding, plus counted draws; per-opponent
stats steer calling and bluffing; an ICM-style premium on stack-risking calls; push/fold play
when short or heads-up. ~25 µs median, ~200 µs p99 per decision; 0 substitutions in T1-T4.

**Before the flop** — Hands ranked by percentile of equity vs 2 random hands. Pot-size opens
with thresholds by players left to act (1.25 x {0:.40, 1:.36, 2:.28, 3:.22, 4:.17, 5:.14,
else .12}; +.08 with <=4 alive; +.05 per tight (VPIP<25%) player behind; x.8 with limpers).
Big blind checks its option except the top 7%. Facing one raise: 3-bet top 6% (+3% vs loose
raisers), call top ~12-25% by price, position and the raiser's PFR. Facing a 3-bet: 4-bet top
~1-3%, call top 4-8%.

**After the flop** — Our hand is ranked against all 1,326 two-card holdings on the board
(numpy), giving the chance a random 4-card hand beats us; draws come from enumerating the
next card (straights or better that the board doesn't counterfeit). Facing a bet we assume
the bettor holds the top X of hands (X = .42 - .12*bet/pot - .08*extra raises, scaled by the
square root of their aggression) and call when equity beats pot odds plus the ICM premium;
raise pot with equity > .72. Semi-bluff raise big draws heads-up vs players who fold (50%).
Checked to: value bet if win chance vs random hands >= .46 (.40 vs callers); c-bets and bluffs
scale with the opponents' fold-to-bet rate.

**Short stacks and the points table** — At <=12 big blinds (or heads-up at <=30 bb) the bot
plays push/fold: raise the maximum with percentile below ~.29-.47 by position (3-handed +.15,
heads-up .85), and call raises when equity vs the raiser's range beats the pot odds. ICM
premium = base x share of stack at risk (base 0 heads-up, .05 3-handed, .07 4-handed, .08 with
5-6 alive, .16 with 7-8 alive), because the 100/60/40/25/15/10/5/0 table punishes busting.
No table reached the 200-hand cap in testing, so the cap ICM split is not modelled.

**Opponents** — Per-seat counts from observe(): VPIP, PFR, postflop aggression (bets+raises
vs calls) and fold-to-bet rate, with priors. Used to call wider vs loose raisers, tighten vs
nits (PFR<9%), steal more vs tight players behind, size bluff frequency and value-bet
thickness by fold rate, and widen the assumed bettor range vs aggressive bettors.

**Last change** — v45: 3-bet threshold top 3.5% -> 6%. In a test field built to mimic the
real (tight) opponents, paired seeds vs v39 gave +0.65, +2.5 and +1.9 points per table.
Before it, v39 added heads-up push/fold up to 30 bb (heads-up wins 223 vs 187 of 342).
Kept unchanged for T5: four further tweaks (wider 3-handed opens, wider short-stack pushes,
smaller bluffs, tighter river play) all tested neutral or worse, and in a tougher field of v45
copies v45 vs v39 came out even (-2.95, +0.85, +0.98 over three seeds).

## Approach (current = v45, submission 013-a6a42b0d; = v39 + 3-bet top 6% (was 3.5%))
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

## T3 result (bot v39): rank 3/8, 32.40 (b05 35.54, b08 34.47 jumped from 24/31). Places
  135,116,123,124,148,113,113,128. HU conversion improved (54% vs 49%) but fewer HU finishes
  (251 vs 302) -> v39 is HU-only, so the drop is noise/field (b08 improved).
- Tests in tag field (paired seeds 8080/9090/5656; v39 = 38.62/36.45/36.76):
  v41 (3-handed short-stack mode <=20bb): 39.02 / 35.92 -> neutral, rejected.
  v44 (equity-based call vs 3-bet after opening, eff<=30bb): 36.35 on 8080 -> worse, rejected
      (tag 3-bets are value-heavy).
  v45 (3-bet threshold .035 -> .06): 39.27 / 38.92 / 38.62 -> +0.65/+2.5/+1.9. SUBMITTED 013.
  v46 (3-bet .08): 40.39 / 39.40 / 37.51 vs v45 -> +1.1/+0.5/-1.1, neutral -> kept .06.
- v45 zoo check (seed 99): 53.5 (top). One local hang + one 1053 µs call under heavy machine
  load; check_bot right after: max 208-309 µs. Tournaments T1-T3: 0 timeouts, max ~390 µs.
- Lesson: in the tag field, more preflop aggression (HU mode, wider 3-bets) helps; more
  calling (v44 3-bet defense, v4/v15 loose calls) hurts. Next idea: wider 4-bet/re-steal
  short-handed; 3-handed open th.
- UNVALIDATED: v47 = v45 + normal-mode open_th +.08 more when 3-handed (versions/v47).
  450-table runs: 38.98 (seed 8080), 41.30 (seed 9090) — no paired v45 baseline at 450 tables
  yet (earlier v45 numbers were 500/650 tables, not comparable). Run v45 vs v47 paired first.

## T4 result (bot v45): rank 3/8, 33.29 (b05 34.28, b08 34.22, b01 32.46 ...). Places
  131,124,140,134,129,131,111,100. 8th fell to 100; top-2 finishes 255 (T1/T2 ~300).
  Weighted total 335.68, rank 2.
- Paired tests in tag field (v45 = 39.27 @8080/500, 38.92 @9090/650, 38.62 @5656/400):
  v47 (3-handed opens +.08): 39.11 / 39.58 -> neutral. v48 (short-stack th base .35->.42):
  38.69 / 39.18 -> neutral. v49 (smaller bluff sizes .4/.45): 38.42 @8080 -> worse.
  v50 (river: X*.85, vth+.06): 39.54 / 39.04 / 38.33 -> neutral. None submitted.
- Stronger field (3x v45 + 3 tag + v31), v45 vs v39 paired: seed 7373 33.59 vs 36.54,
  seed 7474 35.36 vs 34.51, seed 7575 34.41 vs 33.43 -> v45 -2.95/+0.85/+0.98 (even);
  kept v45 (tag field favoured it 3/3). Strong-field baseline for v45: 33.59/35.36/34.41.
- Strong-field screen seed 7373 (v45 33.59): v50 34.14, v47 33.72 -> both ~neutral.
  v50 over 4 tests: +0.27, +0.12, -0.29, +0.55 (avg +0.16). T6 candidates only if more seeds agree.
  v50 strong seeds 7474/7575: 35.13 / 34.76 vs v45 35.36 / 34.41 -> 6-test avg +0.13: neutral, dropped.
- v51 (made-hand vulnerability flop .22->.15, turn .12->.08): tag 8080 38.87 (-0.40),
  strong 7373 33.82 (+0.23) -> neutral, dropped.
- v52 (vulnerability .30/.16): tag 8080 39.43 (+0.16), strong 7373 33.58 (-0.01) -> flat;
  the vul parameter is insensitive around .22/.12.
- v53 (BB raises limpers with top 12% instead of 7%): tag 8080 39.14 (-0.13), strong 7373
  33.56 (-0.03) -> flat, dropped.
- Kept v45 (013-a6a42b0d) for T5. Small tweaks now test neutral: bot is near a local
  optimum for this test method; bigger structural changes would be needed for more.

## Submissions
- 001 v1 baseline; 002 v3; 003 v5; 004 v6 (ICM); 005 v8 (short-stack steals);
  006 v14 (wider opens, thinner value); 007 v16 (semi-bluff raises);
  008 v24 (preflop percentile by eq vs 2 random hands); 009 v29, 010 v31 (patches before T2); 011 v38, 012 v39 (before T3); 013 v45 (before T4). Versions in `versions/`.

## Known weaknesses
- Crude vulnerability factor; no check-raising; bettor range is one X parameter.
- Preflop deep play is percentile-only (no stack-depth / implied-odds logic).
- Opponent stats need ~20+ hands to move off priors.

## Next steps (patch windows)
- Key = eq vs 1 random hand tested (v25, 500 tables): 38.1 vs v24 copies 37.9 -> neutral,
  v24 (eq vs 2) kept. Could still re-tune open thresholds for the eq-vs-2 key.
- Use tournament results: if we bust 5th-7th a lot, raise ICM premium mid-game; if opponents
  are aggressive, widen X scaling. Consider HU-specific postflop aggression.
