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

## Known weaknesses
- Open-then-fold-to-3bet is the largest single loss bucket (~ -3.5bb each).
- Flop/turn equity is crude (wetness factor, outs), no true equity vs ranges.
- Little bluffing beyond HU flop c-bets; no check-raise bluffs.
- Opponent model only VPIP/PFR/aggression; no fold-to-cbet stat yet.

## Next steps
- Fold-to-cbet / fold-to-steal stats per seat, steal & bluff more vs folders.
- Short-stack push ranges (<=8bb) wider.
- Better flop equity (precomputed feature->equity tables).
