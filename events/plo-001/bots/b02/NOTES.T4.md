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

## T1 (real field) result: 006 -> rank 4/8, 31.58 +- 1.85 (field mean 31.9)
- Places /1000: 102 140 148 139 121 128 98 124 (flat; few wins). 0 timeouts/errors/illegal.
- Leaderboard: b05 36.3, b06 34.8, b01 34.5, b02 31.6, b04 31.3, b07 31.3, b03 30.9, b08 24.4.
  Field is tight: VPIP 21-27% (b07 37%), PFR 14-21%. Our VPIP 22%, PFR 17%, WTSD 4.9% (very low).
- Sample hands: multiway pots often checked down on every street (passive field, little bluffing).
  Hand t3-10: we folded AAJTds on T98 flop to a jam getting 27% after 4-betting (model under-rates
  overpair+draw equity; real equity vs that range ~30%, so only a small leak).

## Patch window before T2 (final: 007 = 006 + stab-when-checked-to, see end of section)
- Stab when everyone checked to us (p 0.5/0.3/0.15 by opponents, HU river bluffs): competent field
  35.3 (s51) / 38.2 (s71) vs 37.3/38.0; passive field (threshold,nit,pot_odds + old versions) 46.7 vs
  006 copies 49.6/48.0 -> rejected.
- Pot-committed equity floor for HU flop/turn all-in calls at <=35% odds: 37.3 / 34.7 -> rejected.
- Adaptive steals (open_top += 0.4*(blind fold rate - 0.65) instead of 0.15*(..-0.7)): s51 36.8 -> rejected.
- BUILT tools/tp_proxy/: copy of 006 that never bluffs (no c-bet bluffs, no semibluffs) and only
  value-bets strength >= 0.75 (HU 0.68). Field "tp_proxy x4, 006, 003, nit" reproduces T1 (006 ~33,
  near field average) -> best proxy so far. Command:
  `python kit/localsim.py --tables 400 --seed 5 --opponents tools/tp_proxy,tools/tp_proxy,tools/tp_proxy,tools/tp_proxy,.submissions/006-08cc7480,.submissions/003-b0e7e729,nit` (~25 s)
- In that proxy the stab version beat the 006 copy at the same tables: seed 5 34.5 vs 33.4,
  seed 6 37.7 vs 33.4 -> SUBMITTED as 007-1ff2a233 (active for T2). Seed 7 after submit: 33.7 vs
  34.2 (neutral). 3-seed mean +1.6 vs 006 copy: weak but positive evidence.
  Zoo sanity (seed 123, 300 tables): 007 54.2 vs 006 54.9 -> no regression, 0 errors.
  Stab rule: to_call==0 and every live opponent already checked this street -> flop/turn bet 0.5 pot
  with p = 0.5 (1 opp) / 0.3 (2) / 0.15 (3+) + 0.5*(avg fold-rate - 0.7) if rel1>0.15 or outs>=4;
  river HU bet 0.6 pot with p = 0.3 + 0.5*(fold-rate - 0.7) when rel1 < 0.35 (no showdown value).
- If T2 shows 007 worse than 006's T1 result, revert to 006 (bot/ code: remove the stab block).
- Proxy fields (my old versions + house bots) don't match the real field; the real field is
  stronger than my old versions (006 tops proxies but is mid-table in T1).

## T2 result (007 = 006 + stab): rank 4/8, 31.02 +- 1.89 (T1 with 006: 31.58) -> same within noise
- Leaderboard T2: b05 36.6, b06 35.3, b01 32.3, b02 31.0, b08 30.9, b04 29.9, b03 29.6, b07 29.4.
- Places /1000: 108 135 130 120 127 135 134 111. Opponents often lead pot-size from the blinds.

## Patch window before T3
- Leak analysis in passive proxy (300 tables, logs): biggest losses = open then fold to 3-bet
  (-3.5bb x 209), call 3-bet then lose (rc: -5.7bb x 58 postflop SD, -2.9bb x 89 preflop all-in).
- Tighter EP opens (11/13/15/21%): proxy s5/6/7 34.0/37.0/38.0 vs 007 34.5/37.7/33.7 -> inconsistent, rejected.
- Tighter deep 3-bet calls (eff > 40bb: need pct >= 1 - 0.6*rng_w instead of 0.9*rng_w):
  proxy s5/6/7 35.4/38.2/34.2 vs 007 34.5/37.7/33.7 (+ on all 3; +3.0 vs 006 copy in same tables);
  old-versions field s51 34.9 (007 35.3). SUBMITTED 008-a0061fc2 (active for T3).
- On top of 008, rejected (proxy s5/6/7 vs 008 35.4/38.2/34.2):
  preflop eq slope 0.45 (was 0.32): 35.3/38.5/34.8 (neutral);
  deep opens 0.6 pot instead of pot: 34.8/36.4/35.8 (-0.3 avg);
  thin HU river value bet (strength >= 0.4, 0.5 pot): 35.7/38.2/34.4 (identical, rarely fires).
- Zoo sanity 008 (seed 123, 300 tables): 53.3, 1st, 0 errors (006 54.9, 007 54.2 same seed).
- Same-table check (field tp x4, 006, 007, nit): s8 008 35.8 / 007 37.4 / 006 30.2;
  s9 008 32.5 / 007 35.3 / 006 36.2; s10 008 37.1 / 007 34.5 / 006 37.5 -> over 6 seeds 008 vs
  007 ~ 0 (noise). 006/007/008 are statistically indistinguishable in every proxy. Kept 008.
- Caveat: T2 (with stab) 31.0 vs T1 (without) 31.6 -> no real-field evidence the stab helps; the
  proxy may over-fold. Don't push stab frequencies higher without real-field evidence.

## Known weaknesses
- Open-then-fold-to-3bet is the largest single loss bucket (~ -3.5bb each).
- Flop/turn equity is crude (wetness factor, outs), no true equity vs ranges.
- Little bluffing beyond HU flop c-bets; no check-raise bluffs.
- Opponent model only VPIP/PFR/aggression; no fold-to-cbet stat yet.

## T3 result (008): rank 5/8, 30.86 +- 1.89. 1 timeout (cpu max 1318 us, 1 of 108k decisions).
- T3 leaderboard: b05 35.5, b08 34.5, b06 32.4, b01 32.3, b02 30.9, b03 30.5, b04 30.2, b07 28.8.
- T1/T2/T3 (006/007/008): 31.6 / 31.0 / 30.9 -> all versions equal in the real field.

## Patch window before T4: table equity tried, rejected (kept 008)
- tools/flop_eq2.py -> tools/flop_eq2.json (300k samples): showdown equity by
  (street, rel1 bin, outs bin, nut flag) vs random hand / opp rel1>=0.7 / opp rel1>=0.9.
- tools/agent_tableeq.py = 008 + facing-bet flop/turn eq from that table (log-q interpolation,
  bluff mix, multiway eq *= er^(0.8(n-1))); needs bot/flop_eq2.json copied from tools/.
- Proxy vs 008: s5 36.5 (35.4), s6 35.6 (38.2), s7 33.4 (34.2); same-table s8 34.3 vs 35.4,
  s9 34.4 vs 33.7 -> avg ~ -0.6: no gain. Not submitted.

- Chips by stage (proxy logs, 007, 300 tables): + at bb 20-160 with 5+ players; small leaks at
  bb 320 with 3-4 players (-0.045 bb/hand, 1571 hands) and HU (-0.088 bb/hand, 592 hands);
  big wins HU at bb 640 (+0.25 bb/hand). Candidate next: HU/3-handed play at ~20-30bb effective.
- HU bb320 detail: BB folds to SB raise 83x (-1bb), SB open-fold to 3-bet 24x (-3bb).
  Wider HU BB defence (call_top 0.55 -> 0.65): same-table vs 008 copy s5 +1.5, s6 -4.1, s7 -0.1
  -> rejected. HU 3-bet continue floor 0.55: s5 +1.0, s6 -4.4, s7 -0.7 -> rejected.
- NOTE: same-table comparisons have a seat bias per seed (seed 6 the 008 copy's seat is ~+4 in
  every run). Compare "you" runs on the same seed (you=baseline vs you=candidate) instead.

## Plan for the next patch window (bigger lever than parameter tuning)
- Flop/turn equity: replace `win*(1-wet) + p_hit` with an offline table. Simulate random deals
  (tools/pre_mc.py evaluator, ~11 us/showdown), record features (street, rel1 bucket, outs bucket,
  nut_draw, board paired/monotone/connected) -> equity vs a random hand and vs a top-30% hand;
  ship as JSON, look up at runtime (no extra CPU).
- STARTED: tools/flop_eq.py -> tools/flop_eq.json (300k samples, 160 cells, key "nb_relbin_outsbin_nut",
  value [n, wins]; equity vs ONE random hand at showdown). Early data: flop rel1-bin0/no outs 0.25,
  13+ outs + nut draw 0.67 -> current model badly under-rates weak hands/draws vs random hands.
  To use: eq_rand from table, then range-adjust (e.g. vs bettor: shrink toward 0 by bet strength).
- Test only in the passive proxy field (tools/tp_proxy) with 3+ seeds and same-table comparison
  against .submissions/008 copies; adopt only if + on most seeds.

## Next steps
- Fold-to-cbet / fold-to-steal stats per seat, steal & bluff more vs folders.
- Short-stack push ranges (<=8bb) wider.
- Better flop equity (precomputed feature->equity tables).
