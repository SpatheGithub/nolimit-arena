# Team notes (b02, PLO)

## Approach
- `bot/agent.py`, single file + `bot/pre_pct.json` (preflop table). Tools in `tools/`.
- Evaluator: at import, table NF[455 rank-triples][13x13 hole rank pairs] of non-flush 5-card values,
  plus FL[13-bit mask] flush values. Per decision: max over board triples -> 13x13 best-value grid
  for any opponent 2-card holding; counts unseen combos that beat/tie us (`fb`, `ft`), with exact flush
  correction. `rel1 = (1-fb-ft/2)^6` ~ P(we beat a random 4-card hand right now). ~25-200 us/decision.
- Draws: flush outs (nut flag), straight outs by rank (nut straight full credit, non-nut half).
- Preflop: MC equity vs 1 random hand for all 16,432 suit-canonical hands (300 deals each,
  `tools/pre_mc.py` in 4 chunks, `tools/build_pct.py`), blended 80/20 with a heuristic score, converted
  to a combo-weighted percentile. Open thresholds by players behind; tight 3-bets deep, wider short.
  Heads-up: open top 72%, SB limps most of the rest, BB defends 55%+, 3-bet top 7-20%.
- Raiser range width from observed PFR (single raise) / 0.55*PFR (3-bet+). 3-bet calls need pct>=0.72
  (0.6 when <=25bb). Committed (>=30% of stack in, odds<=0.42): always call.
- Postflop facing bets: villain range = top q of hands (q: 0.40 small bet / 0.28 big / 0.08 raise /
  0.04 re-raise, x(0.5+1.4*aggr), x0.8 per earlier street villain bet, x0.85 river) plus bluff share
  (from aggression); our win = percentile within that range; add draw equity; call if eq >= need;
  raise pot if eq >= 0.72.
- Value betting when checked to: vs caller range q_c = 0.85*0.8^(called streets); bet 0.75 pot if
  strength >= 0.6, 0.6 pot HU if >= 0.48, nuts (fb<0.4%) pot. Semi-bluff big draws. HU flop c-bet
  bluffs ~35% (more vs folders). Low SPR (stack <= 0.8 pot, flop/turn only): jam any piece/draw.
- ICM: with 3-4 alive and an all-in call, exact Malmuth-Harville required equity (copied referee code);
  otherwise a small risk margin.

## Results (localsim, noisy: +-2.3 at 1000 tables)
- v1 (001): zoo ~47. v3 (002, MC preflop table): 55.8 vs v1 48.6 same field.
- Mixed field (v3, v1, maniac, nit, montecarlo, pot_odds, minraiser), 1000 tables: v6..v10 all ~48.5-49.6
  vs v3 ~47-49.6 -> equal within noise.
- "Competent" field (2x v6, 2x v3, v1, nit, montecarlo), 800 tables: v8 34.3 (too tight value bets,
  reverted), v9 37.2, v10 37.3 (top of field).
- vs maniac/random field: ~62.6. Zoo (default localsim): v12 53.1 (v1 was ~47).
- Seed 71 confirmation, competent field, 800 tables: v12 38.0 (top); v6 36.4/35.7; v3 35.4/35.3; v1 31.1.
- Final sanity (006, zoo, seed 123, 300 tables): 54.9 +- 4.4, 1st of 8; 0 timeouts/errors/illegal.

## Submissions
- 001 v1, 002 v3, 003 v6 (PFR ranges), 004 v9 (postflop range recalibration, river SPR fix),
  005 v10 (+ exact ICM all-in calls with <=4 alive),
  006 v12 = v10 + gc.freeze() after import and PRE_TABLE stored as plain floats (GC-pause safety).
  006-08cc7480 is ACTIVE; bot/ == .submissions/006-08cc7480 at the end of the build phase.

## Tried and rejected (competent field, seed 51, 800 tables; v10 baseline 37.3)
- Wider short-stack opens (+30% at <=5bb, +15% at <=8bb): 35.7.
- HU flop c-bet bluff base 0.55 instead of 0.35: 35.0.
- +8% late-position open range at bb >= 80: 37.1 (no gain).
- Tighter early-position opens (UTG..UTG+2 11/13/15%): seed 51 38.5, seed 71 34.2 (baseline 37.3/38.0) -> worse.
- Wider BB defence vs single raise (BB bonus 0.20 instead of 0.12): seed 51 35.3 -> worse.
- HU flop c-bet bluff base 0.20 (instead of 0.35): seed 51 37.0 -> no gain. 0.35 looks near a local optimum.
- Tighter value betting (caller range 0.6*0.72^streets): 34.3 (v8); milder 0.85*0.8^streets kept.

## Testing recipe
- `python kit/localsim.py --tables 800 --seed 51 --opponents .submissions/003-b0e7e729,.submissions/002-cb286c9a,.submissions/001-d1ef031e,.submissions/003-b0e7e729,.submissions/002-cb286c9a,nit,montecarlo`
  (~85 s). Noise is +-2.3 points, so only trust differences of 3+ points or repeated seeds.
- Hand-log leak analysis: run run_tournament with hand_logs=True and log_dir, then
  arena.tournament.handlog.bot_view(dir, 0); group our net chips by preflop action / street / showdown.
- Timing: analyze() p99 < 100 us, max ~200 us in-process; localsim max spikes of 600-900 us are machine noise.

## Known weaknesses
- Open-then-fold-to-3bet is the largest single loss bucket (~ -3.5bb each).
- Flop/turn equity is crude (wetness factor, outs), no true equity vs ranges.
- Little bluffing beyond HU flop c-bets; no check-raise bluffs.
- Opponent model only VPIP/PFR/aggression; no fold-to-cbet stat yet.

## Next steps
- Fold-to-cbet / fold-to-steal stats per seat, steal & bluff more vs folders.
- Short-stack push ranges (<=8bb) wider.
- Better flop equity (precomputed feature->equity tables).
