# Team b03 notes

## Approach
- `bot/ev.pkl`: 7-card evaluator tables copied from kit fasteval (rank dict + suited list); `ev()` in agent.py.
- `bot/pre.pkl`: preflop 1326x1326 equity matrix (4000 random boards, numpy, tools/gen_pre.py + tools/proc_pre.py):
  - `pct[cls]` percentile of class (ordering by equity vs random hand),
  - `eqr[cls][x]` HU equity of class vs top-x% range (x=0..100), with card removal,
  - `cf[x][t]` fraction of hands with equity >= t vs a top-x% shove range (models opponents' all-in calls).
- `bot/icm.pkl`: ICM equity table, n alive 2..8 x my chip share (others equal) — tools/gen_icm.py.
  `icm_val(stack, total, n)`; busting = PTS[n-1]. Used for every all-in / big call / push decision.
- Preflop: position-based open ranges (2.3-2.5bb); ICM push/fold when eff <= 15bb (push EV in points with
  per-opponent call ranges from pot odds needed + 0.06 ICM premium (+0.03 if I cover them), wider for BB in
  blind-vs-blind/HU, VPIP-adjusted); raiser range by raiser's position (OPEN_BY_BEHIND) and PFR stats;
  shover range by stack depth & position; value 3-bets top third of raiser range; jams checked with
  resteal_ev (ICM) or eq vs continuing range >= ICM required; resteal shoves <= 25bb.
- Postflop: hand strength vs weighted range (260 sampled opp combos, weights from preflop action).
  Facing a bet: HS vs the strongest X of that range, X by street (0.6/0.48/0.4), bet size, raises,
  bettor's earlier aggression and bettor's aggression factor. Draw outs add equity. Multiway exponent.
  Value bet >= 0.62 HU / 0.72 multi; c-bet freq scaled by opponents' observed fold-to-bet rate;
  river/turn bluffs only vs folders. Call if equity >= max(pot odds, ICM required).
- Opponent model per seat: hands, VPIP, PFR, postflop agg/passive counts, fold-to-bet.

## Testing (localsim, noisy: +-3 pts at 400 tables)
- v1 zoo 44.9 -> ICM v2 54.3 -> narrowing v3 -> positional ranges v4 58.2 -> v6 61.9 (seed 2, 300 tables).
- ICM blend test: full ICM (lambda 1) beat 0.5 and 0 (37.3 / 35.7 / 32.1).
- PF_BB 11/15/20, OPEN_MULT 0.8/1.25, CBET, XSCALE: all within noise in self-play fields.
- tools/diag.py: per-level and per-final-action chip attribution; tools/diag2.py logs big losing hands.

## Submissions
- 001 v1 baseline; 002 ICM; 003 range narrowing; 004 positional ranges + pot-odds call ranges;
  005 HU/BvB call-range fix; 006 re-raise jam ICM checks + postflop narrowing by prior aggression;
  007 per-opponent all-in call/shove tracking (geometric mean with PFR looseness), HS samples 260->220;
  008 XSCALE 0.9 (slightly tighter calls vs bets). 008 is active for T2.

## T1 result (played with 007)
- Rank 1/8, 34.78 pts (CI 32.7-36.9); places 1st 167 ... 8th 115; 0 timeouts/errors; 3 "hangs"
  (wall > 50 ms with CPU <= 1.4 ms, i.e. machine scheduling, not our code). cpu p99 500 us bucket.
- Field: VPIP 19-24%, PFR 12-20% for all teams (tight-aggressive LLM bots). b08 (19/12) was 2nd.
- Only big sample pot: we light-3bet 33, check-called flop+turn on QQJ, folded river (loose-passive leak)
  -> XSCALE 0.9.
- Patch tests (1000 tables each, paired fields): v8 vs v7 +1.6 (noise ~2); CBET 0.85 / XSCALE 0.8 vs v8
  within noise -> kept v8. No light-3bet-bluff (NB) and VALUE_HU 0.58 also within 0.2 of v8.
- Final v8 zoo check: 56.6 +- 3.7 (rank 1), 0 subs, max 278 us.
- v8 diag vs 005/006/007 + nit + montecarlo (300 tables): 37.7 pts, 8th only 4%; chips + at levels 0-3,
  slightly - at levels 4-5 (push/fold variance). Losses are folds and called shoves; no glaring leak.
- Min-raise opens (2.0bb) when eff < 25bb (variants/MR): 35.92 vs v8 35.95 over 1000 tables -> no effect.
- Opponent call-model ICM premium 0.03 instead of 0.06 (variants/PR3): 36.05 vs v8 35.96 (800 tables) -> no effect.
- Self-play parameter tuning is exhausted at this noise level; next gains need new logic (exact ICM with
  real stacks for <=4 players, better paired-board/underpair handling, turn barrels, check-raises).
- Benchmark: hand_strength ~100 us, draw_outs ~9 us per postflop street (cached per street).

## T2 result (played with 008)
- Rank 1/8, 35.37 pts (CI 33.2-37.6); places 1st 181, 2nd 109, 3rd 105, 4th 109, 5th 128, 6th 124,
  7th 129, 8th 115. 0 subs, 0 hangs, cpu p99 200 us, max 346 us. Weighted total 105.52 (rank 1).
- Bust analysis (tools/diag3.py, 400 tables vs 004-007 + nit): busts mostly at levels 3-4 (hands 76-125)
  in preflop all-ins (220/339 my shoves called, 75/339 my calls); early busts (levels 0-2) rare.
- Tested shover-range x0.8 (variants/SRT): 32.0 vs v8 32.8 -> rejected. Kept 008 for T3.
- Tested capped range when HU opponent checked (variants/CAP: HS vs range minus top 12%): 32.5 vs 32.0,
  then 32.3 vs 32.5 on another seed -> no measurable effect, not submitted. Cap 0.25 (CAP25): 32.0 vs
  v8 32.6 -> rejected. Self-play tuning is at the noise floor; 008 is robust (rank 1 in T1 and T2).
- ICM_LAMBDA 0.85 (L85) 31.7 and multiway exponent 1.0 (MW) 32.2 vs v8 32.2 -> no change.
- HS samples k=300 (K300) 32.67 vs v8 32.0 (1000 tables), repeat 33.46 vs 31.42 -> +1.35 over two
  seeds, same sign both times. Submitted as 009-c8c535e8 (only change vs 008: k 220 -> 300).
  check_bot p99 ~300 us / max 322 us locally. If T3 shows timing trouble, revert to 008 (k=220).
  Third run (seed 1414): 009 32.24 vs 008 32.87 -> 3-run average diff about +0.7 (weak, within noise).

## T3 result (played with 009)
- Rank 1/8, 35.70 pts (CI 33.6-37.8); places 1st 173, 2nd 111, 3rd 125, 4th 126, 5th 110, 6th 136,
  7th 117, 8th 102. 0 subs, cpu p99 200 us, max 628 us (k=300 OK). Weighted total 212.64 (rank 1).
- Real-field sample (T1-T3, 120 hands): short-shove (<12bb) faced 14x, called 4x (29%); too few to act on.
- Patch tests vs 009: call-range prior x1.2 (CR12) 31.7 vs 32.6 -> rejected; flop semi-bluff raise with
  8+ outs HU vs folders (variants/SB) 32.52 vs 32.56 -> no effect. Kept 009 for T4.
- Real-field sample: facing a flop bet players FOLD 79% (42 obs), turn 64% (14), river 50% (4).
  Our fold-rate prior is 0.45 (adapts per opponent with weight 4). Prior 0.6 (FR60) 31.6 and prior 0.6 +
  HU flop stab when checked to (FR60S) 32.1 vs v9 33.7 in self-play -> not submitted (self-play bots
  fold less than the real field). Possible future bet: prior ~0.55, or stabs only after observing folds.
- Self-play fold-to-bet (tools/foldstat.py, v9 x8): flop 65%, turn 72%, river 80%. FR60 repeat run:
  32.2 vs 31.9 -> 2-run avg about -0.9 -> rejected.
- STAB (HU flop, non-aggressor, opponent checked, opponent observed fb>=3 and fold_rate>=0.6, 60%:
  bet 0.45 pot): 32.79 vs 31.77, then 32.85 vs 32.21 (avg +0.8, same sign twice). Only acts vs observed
  over-folders (real field folds 79% to flop bets). Submitted as 010-2805dc6e for T4. Fallback: 009.
  Third run (seed 2121): 010 31.52 vs 009 32.82 -> 3-run avg about +0.1 (neutral in self-play). Kept 010
  because the real field over-folds more than self-play (79% vs 65%) and break-even fold is only 31%.
  If T4 drops clearly below T1-T3 (~35), revert to 009.

## Key parameters
- ICM: breakeven for a stack-for-stack flip at 8 even stacks is ~62% equity. Calling all-ins is tight.
- PF_BB=15, VALUE_HU=0.62, CBET_HU=0.65, XSCALE=1.0, OPEN_MULT=1.0.

## Known weaknesses
- ICM table assumes other stacks equal (ignores short stacks about to bust).
- Postflop heuristic: low flush on 4-flush boards overvalued; no check-raise bluffs; no turn barrels.
- Self-play tests are too noisy to tune parameters finely.

## Next steps
- Track opponents' actual all-in call/shove frequencies and use them in call_range / shover range.
- Exact ICM with real stacks for <=4 players (cheap enough).
