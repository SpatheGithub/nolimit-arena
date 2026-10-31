# Team b04 notes

## Approach
- `bot/agent.py`: single-file bot. Data files (built by `tools/`):
  - `evtab.pkl`: hand-evaluator tables copied from kit fasteval (rank dict + suited table), same KEY scheme.
  - `pf.pkl`: preflop 169x169 equity matrix (numpy MC, 40M deals) -> `eqr[h][level]` = equity of class h vs top-p range,
    `pct[h]` = percentile of class (0 best), `rc[p]` = combo lists for top-p ranges (postflop range sampling).
  - `icm.pkl`: ICM value table VT[n][k] = points for holding k/200 of all chips with n alive (others equal), via kit/icm.py.
- Preflop: unopened -> push/fold when eff <= 14bb (ICM EV of shove vs fold, callers' ranges ~ 1.4/eff_bb + 0.05, adjusted by vpip);
  deeper -> open-raise by #players behind (12%..45%), adjusted by fold-to-raise stats of players behind.
  Facing raise: estimate raiser range from observed PFR; commit spots (<=18bb or all-in) use ICM EV of call/shove/fold;
  deep: 3-bet top (eq>=.62), set-mine pairs, call decent hands with small price.
- Postflop: MC equity (30-100 samples) vs opponents' preflop-action ranges; value bet eq>=.62 HU, c-bet/bluff by fold-to-bet stats;
  facing bets: equity discounted by bet size/street/raises (less vs aggressive opponents); big calls (>=30% stack) use ICM.
- Opponent stats per seat: VPIP, PFR, fold-to-raise, fold-to-bet postflop, aggression.

## Key findings
- ICM is huge here: doubling 2000->4000 at 8-handed = +19 pts, busting = -32. Survival matters (nit house bot scores ~48-50 just by folding).
- v1 (chip EV) 45.8 vs zoo; v2 (ICM) 59.2 vs zoo, 49 vs field of 3x v1 + nit/montecarlo/threshold/pot_odds.

## Submissions (snapshots in versions/vN)
- 001-305400a4: v1 chip-EV.
- 002-5c73d72f: v2 ICM-aware all-in decisions.
- 003-e802e4fe: v3 tighter flat calls (only deep: pairs >=35bb, others >=30bb).
- 004-b3e8cfcd: v5 = v4 (opponent all-in stats: shove freq -> wider shove range est., call-allin rate -> caller range)
  + postflop bettor range filter (sampled bettor hands must beat board category, bluff prob by street/aggression).
- 005-4f716bbb: v6 = + short-handed wider opens (HU 72%, 3-handed BTN 44%), MC time guard (0.42ms), resteal shove 18-32bb vs openers (r_range>=.2).
- v7: limpers counted as potential callers in push/fold shove EV (bug fix).
- 006-cbb21ccf (played T1, = versions/v8): v7 + river fixes: river value threshold +0.06, river all-in bets only with eq>=.82
  (else half-pot), river shove over a bet only with eqa>=.85 (else call), river raise needs eqa>=.80.
- 007-ab61c71c: v8b = v8 strategy + safer MC time guard (0.34ms, checked every 4 iters).
- 008-99c3c063 (played T2, = versions/v13): v8b + short-handed raiser ranges: PFR is measured mostly 8-handed and
  understates late ranges. n_alive==2: open-raise range >=55%, shove range >= min(.85, 3.5/rb+.22);
  n_alive==3 (raiser not BB): open >=35%, shove >= min(.7, 2.5/rb+.12). Tests: +3.1 self-play (450t), +1.6 mixed (450t),
  more 1st places in both; third check -0.3 self-play (seed 231) -> average ~+1.5, kept.
- 009-8c98960a (played T3, = versions/v18): v13 + (a) 3-bet shove at 18-30bb only if ICM EV(shove, raiser calls
  45% of range) > EV(fold), else flat if <=12% eff, else fold (premiums pct<=.025 always shove); (b) low-SPR (<1.2) postflop
  all-in bet needs eq>=.75 (was .62 vs unfiltered range), else 0.4-pot bet; (c) per-seat shove range learned from hands shown
  after preflop shoves (r_est = 2*avg pct, blended with prior weight 2; can narrow or widen).
  Local: vs v13 copies -0.9 / -1.4 (noise), vs zoo 56.8 (= v13 56.9). Submitted because real field shows early-bust pattern.
- 010-ec999c97 (ACTIVE for T4, = versions/v25 = bot/): v18 + stronger bettor range when facing a big bet (call >= 30% stack)
  or a raise: sampled bettor hand accepted if cat >= board cat + 2; one-pair-over-board with prob .45+.3*agg; else bp*0.6.
  Tests: seed-271 calibrated 38.1 vs v18 37.2 (+0.95); 4v4 head-to-head (600t, seed 291) v25 avg 32.2 vs v18 31.6 (+0.6);
  4v4 seed 301: v25 32.4 vs v18 31.3 (+1.1). Consistent small gain.
- versions/v10_candidate (NOT submitted): v8 + adaptive river vth by fold-to-bet (0.60-0.70) + lower default shove-caller
  range c = 1.15/eff_bb + 0.03 (was 1.4/eff_bb + 0.05). Mixed field +0.7 (noise), self-play -2.6 (noise) -> not shown better.

## Testing
- tools/sim.py <me> <comma-list opponents> <tables> <seed>: prints points + place distribution. ~50s / 400 tables.
- Typical field: versions/vX x3 + nit, montecarlo, maniac, pot_odds. Noise is +-3.5 pts at 400 tables, so small changes are unresolvable.
- Instrumentation (versions/instr pattern): appended observe() hook logging per-hand payoffs to $TMPDIR.
  Found: flat-calling preflop at mid stacks lost (fixed v3); postflop call-downs with weak pairs/ace-high vs value bettors (fixed v5 filter).

## Measurements
- v8 vs zoo (localsim seed 2, 400 tables): 56.0 (v5 56.6, v1 45.8). v8 vs v6 head-to-head: -0.7 / -1.0 / +1.5 over three runs => equal.
- Self-play call rate vs our preflop shoves (opponent decisions): <5bb 48%, 5-8bb 17%, 8-12bb 9%, 12-16bb 6%.
  The default caller-range assumption (1.4/eff_bb+0.05: 10bb->19%) is ~2x too loose for ICM-aware callers like us;
  per-seat observed call_allin rates override it after a few observations (prior weight 3).
- Machine gets very busy late: 400 tables can take >2 min; use <=250 tables per command.

## Known weaknesses / next
- Postflop sampling noisy (30-85 MC samples, 0.42ms guard); value-bet eq is vs unfiltered ranges.
- ICM uses an equal-other-stacks table (VT); real stacks (short stacks about to bust) not modelled.
- Default caller ranges for our shoves maybe too loose (see measurement) -> try v10_candidate when real results show we shove too rarely.
- Ideas: exact ICM for n<=4 preflop (cheap enough), river bluff-catching vs aggressive seats, board-texture c-bets.

## T1 result (v8 = 006): rank 6/8, 30.28 pts/table (CI 28.4-32.2); places nearly uniform [111,110,127,141,144,121,121,125].
- Field is tight: VPIP 19-25%, PFR 12-20%. Winner b03 34.8 (25/18); b08 33.7 is tightest (19/12). All ranks 1-7 overlap within noise.
- 3 "hangs" (wall >50ms; cpu max 760us) -> likely process scheduling/GC in shared process; tightened MC guard anyway (007).
- Patch-window tests (vs v8b-heavy fields, 250-650 tables): v10 (wider shoving) -3.6 and -2.6 => dropped;
  v11 (tighter shoving, c=1.65/bb+.06) +1.3 / -0.7 => no effect; v12 (opens x0.75 at levels 0-1) +0.3 in self-play => no effect.
  Conclusion: push/fold caller assumption and early open width are not where points are; look elsewhere (postflop, multiway, HU).
- v14 (HU caller range for our shoves c>=2.2/bb+.08 when n==2): -0.6 vs v13 self-play -> not submitted.
- v15 (HU open range .72 -> .85): -0.9 vs v13 self-play -> not submitted.
- v16 (4-handed raiser ranges: open >=.28, shove >= min(.6, 2/rb+.08)): +0.7 then -2.8 vs v13 self-play -> dropped.
- v13 (active 008) vs zoo seed 2: 56.9 (no regression; max 378us, 0 subs).
- HU/3-handed is where measurable gains showed up (v13). Next: our own HU shove/call assumptions (caller range c in
  _shove_decision is full-table based too), HU postflop aggression.
- Next ideas: exact ICM with real stacks for n<=4 (bubble-ish ladder spots); HU play quality (1st vs 2nd = 40 pts);
  postflop value-bet thresholds vs tight field (they fold more -> bluff more/value thinner?).

## T2 result (v13 = 008): rank 8/8, 28.96 (CI 27.1-30.9); places [105,115,110,123,136,140,129,142]; showdown win 48.7% (T1 50.4%).
- Field VPIP 19-24%, PFR 11-19%; b03 leads again (35.4). We're ~2-3 pts under average in both T1 and T2.
- Pattern: too few 1st/2nd (10.5-11%) and too many 5th-8th. Sample hands are only hands 1-10 of 4 tables (useless for late game).
- Hypotheses: (1) busting via 3-bet shoves / low-SPR stack-offs (addressed in v18); (2) default opponent shove range
  estimate too wide for tight bots -> calling off light (v18 learns it from showdowns); (3) late-game too tight (ICM) ->
  fewer 1sts; untested.
- T3 patch tests (field v18x3, v1, v13, nit, montecarlo; seed 271, 450t; v18-as-you calibration = 37.2):
  v19 softer ICM (0.8*ICM + 0.2*linear chips) 35.5 (-1.7); v20 harder ICM (1.2*ICM - 0.2*linear) 34.4 (-2.8) => plain ICM best.
  v18 in v1/v13 mixed field: +1.4 vs v13 copies. ICM bots beat chip-EV v1 copies by ~8 pts there.
  v21 half bluff/c-bet frequency 37.0 (-0.2); v22 thinner HU value (vth .58 flop/turn, .68 river) 35.2 (-2.0). None submitted.
- Calibrated v13-as-you on seed 271: 37.0 vs v18 37.2 => v18 not worse than v13 locally.
- v23 (big postflop calls: eqa - 0.04 in ICM branch): 36.4 (-0.8) -> not submitted.
- v24 (v18 + caller range c = 1.15/eff_bb + .03): 37.5 (+0.3) -> no effect, not submitted.
- Seed-calibration trick: run the incumbent as "you" on the same seed/field; compare candidates to that, not to copies' average.
- Next window: look at T3 places; if busts still high, consider tighter postflop stack-off (ICM branch threshold) or
  exact-stack ICM; if 1st-place share still low, look at HU/3-handed play.

## T3 result (v18 = 009): rank 6/8, 30.43; places [133,99,108,130,112,124,139,155]; showdown win 48.4%; weighted 179.5 (rank 7).
- b03 leads every tournament (35.4-35.7) with VPIP 25/PFR 18 like ours -> difference is in play quality, not frequencies.
- More 1sts than T2 (133) but most 8ths (155): early busts are the leak -> v25 (stronger ranges vs big bets/raises).
- T4 patch tests (calibrated seed 271 field; v25-as-you = 38.1): v26 push/fold zone 16bb 36.8 (-1.4); v27 zone 12bb 37.8 (-0.4);
  v28 SB limp only top 30% 37.4 (-0.7); v29 flop/turn call needs eqa >= need+.05 35.6 (-2.5). None submitted.
  v30 flop/turn call eqa >= need-.03: 34.4 (-3.75). Both call-threshold directions worse -> keep; note the seed-271
  calibration (38.1) is probably a lucky high (candidates average ~36.4), so single calibrated runs are +-3 noisy too.
- Best evaluation method found: 4v4 head-to-head (4 seats candidate, 4 seats incumbent, 600 tables, ~50s), pooled means.
- v31 (strong bettor filter also for turn/river bets >= .6 pot): 4v4 +1.3 then -1.6 vs v25 -> ~0, not submitted.
- v32 (short-handed postflop opp ranges >= .6 HU / .4 3-handed): 4v4 -0.1 vs v25 -> not submitted.
- Next window ideas: exact-stack ICM for n<=4 (cache per hand); look at T4 places (8th-place rate after v25).
