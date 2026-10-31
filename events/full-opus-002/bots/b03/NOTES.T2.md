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
