# Team b01 notes

## Approach
- `bot/agent.py` (+ `bot/_common.py` copied from house bots: Ranker 7-card evaluator, Spot parser, preflop pct table).
- `bot/eq169.npy`: 169x169 preflop all-in equity matrix (MC, 600 trials/pair, tools/precompute_eq.py).
  At import -> RQ[h][k] = equity of class h vs top-k% range (ordered by house pct table).
- Preflop:
  - eff stack <= 14bb (<=18bb with <=2 behind) unopened: push/fold, EV computed in ICM points
    (symmetric-ICM approx `U(x, n, T)`: others treated as equal stacks; within ~1pt of exact ICM).
    Opp call prob = per-seat observed call-vs-big-bet freq (prior 0.30), widened for cheap odds.
  - Deeper: open top-X% by players behind (OPEN_PCT), 2.5bb (2.2bb if <22bb), iso vs limpers.
  - Facing raise: raiser range = observed PFR freq (prior 18%); shove range prior SHOVE_K/stack_bb.
    Commit-sized calls decided by ICM gain (icm_call). Resteal shove EV (ICM) when eff<=24bb.
    3-bet value top ~2.5-6%, light 3-bet vs wide openers, call by equity-0.07 vs pot odds, set-mine pairs.
- Postflop: Monte Carlo equity (budget 0.22ms, <=130 trials) vs opp ranges: preflop range bucket
  (raiser/caller/limper) + weights by opp's current made-hand level if they bet this street
  (bigger bets/raises => stronger weighting). Value bet e>=0.62 HU; c-bet/semi-bluff frequency scales with
  observed fold-to-bet freq; call if e >= need+margin; big calls (>=25% stack) need ICM-adjusted equity.
- Opp stats per seat within a table: PFR, shove freq, call-vs-big-bet, postflop fold-to-bet.

## Key parameters
SHOVE_K=2.6 (x position factor 1+0.3*max(0,4-players_behind_shover)), SHOVE_MARGIN=CALL_MARGIN=0.02 points,
ICM_ALPHA=0.6 (utility = 0.6*symmetric-ICM + 0.4*chip-linear), CALL_PRIOR=0.16 (+0.06 BB, +0.14 HU, +0.05 3-handed),
MC budget 0.3ms wall (<=200 trials, ~5-8us/trial), OPEN_PCT table, steal widening by observed fold-to-open.

## Submissions
001 v1 heuristic postflop | 002 v3 MC postflop+resteal+fold-adaptive bluffs | 003 v5 ICM blend
004 v7 HU/position shove priors + caller-range weights | 005 v8 steal adaptation | 006 v9 faster MC, budget 0.3ms
007 v10 postflop-aggression adaptation (flatten bettor weights vs frequent bettors), MC budget 0.25ms
008-a6c93ffd v11 FINAL for T1: MC budget 0.4ms only when facing a call >= 40% of stack (noise in stack-off spots)

## Late experiments
- ICM_ALPHA 0.3 vs 0.6: identical (36.6 vs 36.6 over 900 tables) -> kept 0.6.
- Ran with act() exceptions re-raised: 0 errors over 300 tables (no hidden fallback folds).
- Timing on busy machine: p50 25us, p99 ~300-490us, max seen 1072us once (before budget cut); referee idle machine faster.

## Window ending 16:25 (still 008-a6c93ffd)
- v11 vs v1/v8/v10 + house (500 tables): v8 45.5, v11 42.4, v10 42.4, v1 39.3. All within +-3 noise, no regression.
- Tried SB limp-complete range 0.65 -> 0.40: 41.1 vs v11 copies' 42.2 average (700 tables). Not better,
  so not submitted and bot/ was restored to v11 (identical to 008).
- Tried thinner value bets (vthr HU 0.62->0.58, multiway 0.50/0.42->0.48/0.40): 40.8 vs v11 copies' 43.0
  average (550 tables). Not better, so not submitted; restored v11.
- Tried thicker value bets (vthr HU 0.66, multiway 0.52/0.44): 41.0 vs v11 copies' 42.2 (450 tables).
  Not better either, so 0.62 looks like a reasonable middle. Restored v11.
- Lesson: 500-700 table runs can't resolve changes smaller than ~3 pts. Patch windows should go to
  bigger structural ideas (exact postflop strength tables, better opponent models), not small threshold tweaks.

## Testing results (localsim, noisy +-2.5)
All my versions within noise of each other vs house bots + own copies (~40-45 pts/table); a LAG variant
(ICM_ALPHA=0, wider opens) also within noise. Beats maniac-heavy fields (~51). Probe tool: tools/probe.py prints
shove/call grids for synthetic spots (useful for sanity-checking ranges).

## Key insight
Points 100/60/40/25/15/10/5/0: early-game full-stack all-in needs ~62% equity in ICM terms
(2000 chips/8 players = 31.9 pts; double-up => 51.1). Survival matters; nit/checkfold score well vs house zoo.

## Known weaknesses
- Opp range model crude; postflop multiway weak; no turn/river bluff-catching logic beyond weights.
- Timing p99 ~0.3-0.5ms on busy machine (MC). Watch for timeouts.

## Next steps (patch windows)
- Use tournament results: if we bust early often -> tighten deep-stack calls; if we blind out -> raise ICM_ALPHA down / widen shoves.
- MC equity is noisy (~25-50 trials). Could precompute flop/turn hand-strength tables or use numpy vectorized eval.
- c-bet logic depends on pf_aggr_me (set when we raised preflop in this hand).
- Deep-stack cold-call rule (e-0.07 > pot odds) may be loose OOP; consider position-aware discount.
- River value threshold 0.62 vs full range might be thin vs tight callers.
