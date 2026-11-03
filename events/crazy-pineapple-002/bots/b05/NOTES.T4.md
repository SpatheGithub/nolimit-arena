# Team b05 notes

## Strategy

**Summary:** Before the flop the bot looks up a precomputed 3-card equity table (`bot/pre3.json`). It covers all 1755 suit-isomorphic classes and was simulated with a realistic after-flop discard, with equity against random hands and against top-5/10/20/35/55% ranges. Short stacks play EV-based push/fold, with exact ICM (Malmuth-Harville, as kit/icm.py) once ≤5 players remain. After the flop it blends a time-boxed Monte Carlo equity (about 0.2 ms) with a heuristic hand-strength score. Per-seat stats (VPIP, PFR, fold-to-raise, fold-to-bet, postflop aggression) widen or narrow its ranges.

**Before the flop:** Deep (>16bb effective): open-raises top 0.40/n_behind^0.6 of hands (≈12% UTG to 40% SB) to 2.2-2.5bb (+1bb per limper), widened against blinds that fold too much. Heads-up and 3-handed (sh_k 0.15, only when ≤3 players), open, call and 3-bet thresholds are multiplied by 1+0.15·(8−players): ×1.9 heads-up (about 76% opens from the button) and ×1.75 3-handed. Auto-steal: it opens any hand when the product of the observed fold-to-raise rates of everyone behind (0.5 prior until a seat has faced 4 raises) makes P(all fold)·pot > 1.1·(1−P)·risk. The SB limps up to 60% when deep, and the BB raises its top 12% when checked to. Facing a raise it 3-bets about the top 3.5% (more against wide openers, by the opener's PFR) and calls about the top 10%. It switches to an all-in decision when the raise commits ≥35% of its stack, or when ≤14bb. Then it calls when equity against the raiser's estimated range (width depends on their stack depth and PFR, up to any-two for maniacs) beats the pot odds, or the ICM-required equity with ≤5 players left.

**After the flop:** Equity is a 65/35 blend of Monte Carlo (against random 3-card holdings, hindsight best-5) and heuristic strength (best 2-of-3 sub-hand; pairs ×0.86, two pair ×0.93). It value-bets at ≥0.70 equity (0.6-0.75 pot, +0.2 against calling stations) and thin-bets at ≥0.56 heads-up. It c-bets about 55% heads-up as preflop raiser, semi-bluffs big draws, and makes rare river bluffs, all scaled by the opponents' fold-to-bet. Facing a bet, equity is cut by (0.14+0.05·street)×bet/pot, scaled by the bettor's aggression factor. It calls on pot odds plus draw equity with a 0.05 margin. When a call would commit more than 20% of a deep stack (>25bb effective), it needs another 0.16. It raises or jams at ≥0.82.

**Short stacks and the points table:** At ≤16bb effective it open-shoves when EV(shove) > 0. Callers are modelled as top 2.0/(bb+2), scaled up (never down) for loose players. With only one player behind (SB vs BB, heads-up) the caller is assumed at least 3.6/(bb+2), about 30% at 10bb. When it faces a shove, the shover's range is the larger of a depth/PFR model (0.08+2/(bb+4), ×0.85) and a position model, 0.5/(players behind the shover)^0.7 × (12/bb)^0.5. That makes it about 55% heads-up at 10bb, about 34% from the button 3-handed, and unchanged for early positions. With 3-5 players left the shove decision uses exact ICM (shove vs fold in points), and all-in calls use the ICM break-even equity. With 6+ players it uses chip EV with a small margin.

**Opponents:** Per-seat VPIP, PFR, fold-to-raise preflop, fold-to-bet postflop, and aggression factor, all with priors. They set the raiser's range width, the callers' widths in push/fold, steal widening and the any-hand auto-steal, bluff/c-bet frequency, value sizing, and the call-down threshold.

**Last change:** v11 (011-9c4cf2f8), after T3 (rank 7/8, 30.1 points; trend 26.3 → 28.6 → 30.1). T3 places showed the late game is the leak: we reached the last three 390 times but won only 96, and won only 41% of heads-up finishes. Two fixes. (1) v10: a position-aware shove range (heads-up 10bb shove ≈ top 55% instead of 19%, so we no longer fold too much to wide shoves) and wider assumed callers with one player behind. (2) v11: heads-up/3-handed range widening (sh_k 0.15, only at ≤3 players) for the deeper non-all-in game. Local tests (650 tables each): sh_k at all table sizes was neutral overall (44.7 vs 44.7) but lifted heads-up wins from 51-53% to 60-63%. Limiting it to ≤3 players scored 45.7 vs v10 42.9 (+2.75), with heads-up wins 58-61% vs 54-56%.

## T1 result (v5 played)
- T1: rank 7/8, 26.32 points/table. Places [80, 107, 130, 109, 114, 149, 154, 157]: most often 8th. VPIP 24, PFR 20, AF 1.6, WTSD 6%, showdown win 43%.
- Leaders: b07 37.5 (VPIP/PFR 20/17), b02 35.9 (24/19), b01 35.3 (20/16). The field is tight-aggressive, so their bets mean strong hands and our random-hand MC overrates our hands.
- v6 006-67075464: tighter postflop (see Last change).
- v7 007-6f521981: push/fold caller model widened (vp_floor 1.0, caller_k 2.0), shove calls w_mult 0.85.
- Tried for T2, not submitted: oop_thin 0.06 (no thin leads out of position as non-aggressor). Local 43.7 vs v7 44.8/43.3, neutral. Left at 0, so bot/ plays exactly like v7.
- v7 zoo (600 tables, seed 15): 56.9 (v5 56.6 on the same seed), nit 48.5, checkfold 44.8. No substitutions; max 0.67 ms.
- Tried for T2, not submitted: sb_limp 0.35. Local 52.7 vs v7 50.6/49.9 (seed 35), but sb_limp 0.30 earlier was −0.8, so pooled ≈ +0.8, within noise. Replicate (seed 36): 42.2 vs v7 45.7/45.5/44.8, i.e. −3.2. Rejected: keep sb_limp 0.60.
- Next ideas: SB limp 60% when deep may be exploitable by aggressive BBs. Range-weighted postflop MC (sample stronger hands for bettors) instead of linear penalties. Per-seat shove-frequency tracking.

## T2 result (v7 played)
- T2: rank 7/8, 28.58 points/table. Places [109, 101, 124, 123, 88, 148, 157, 150]. VPIP 23, PFR 19, AF 1.4, WTSD 5.4%, showdown win 49% (T1: 43%).
- Leaders: b07 35.3 (VPIP/PFR 20/17), b01 34.4 (19/15), b08 33.8 (29/18).
- v8 008-908e4ba8: deep_guard 0.12 at guard_frac 0.25. Local race (seed 40, 750 tables): var_g 41.8, v7 40.3/40.1, open_k 0.34 39.8, both together 39.3, all within noise.
- v8 places check (600 tables, seed 41): v8 51.7 / v7 50.7 / v5 48.8. 6th-8th finishes: 69 / 82 / 97, so the tighter versions bust early less.
- Tried for T3, not submitted:
  - open_k 0.34 on v8: +3.9 (seed 42), +0.1 (seed 43); on the v7 base −0.5. Pooled ≈ +1.2, not convincing.
  - open_k 0.34 on v9 (seed 46, two copies each): 45.9/44.5 vs 45.5/42.8, i.e. +1.1. Over 4 runs ≈ +1.1. Fifth run (seed 48, two copies each): 44.2/42.4 vs v9 46.6/46.5, i.e. −3.2. Over 5 runs ≈ +0.2: rejected, open_k stays 0.40.
  - deep_guard 0.16 at 20%: +2.1 (seed 42), +0.7 (seed 44). Adopted as v9 009-580ea0a1. Maniac-heavy safety check (650 tables, seed 45): v9 55.3 vs v8 52.4, so no cost against overbettors.
  - Both are candidates if T3 still shows early busts.
- T2 sample, me = seat 3 (CPU ≈ 250 µs): we folded AK top pair to a half-pot c-bet in a 3-way pot. Reconstructed it is a borderline call: MC 0.45, heuristic 0.36, 0.32 after penalty vs 0.30 needed.
  - Root cause: the MC gives opponents hindsight best-5-of-8, which undervalues made hands against draws, especially multiway.
  - Fix idea: myopic flop discard for opponents in the MC, then re-tune thresholds.

## T3 result (v9 played)
- T3: rank 7/8, 30.14 points/table (6th place 30.16). Places [96, 139, 155, 115, 85, 115, 139, 156]: reached heads-up 235 times, won 41%. VPIP 23, PFR 18, showdown win 49%.
- Leaders: b02 34.2 (26/19), b07 33.9 (19/16), b01 33.4 (21/17).
- The sample hands (me = seat 3/5/7/6 by CPU signature) look sound. Losses are mostly call-call-fold lines against opponents who lead (donk) and barrel with strong hands.
- v10 010-7097cfbc: position-aware shove ranges and wider callers with one player behind (see Last change).
- v11 011-9c4cf2f8: sh_k 0.15 with sh_max 3. Local: var_sh (all sizes) 45.7/43.8 vs v10 44.8/44.5; var_sh3 48.7/42.6 vs v10 43.4/42.5. Confirmation (seed 53): v11 44.8/44.3 vs v10 47.5/41.4, i.e. +0.1 overall; heads-up wins 58-59% vs 55% (higher in all 3 runs). Kept.
- v11 zoo (600 tables, seed 15): 55.6 (v7 56.9, v5 56.6), nit 47.8, checkfold 45.0. Local max time 1.19 ms on the busy machine; the tournaments measured 0.71-0.77 ms max with 0 timeouts over about 340k decisions.
- Tried for T4, not submitted: sh_k 0.25 (≤3 players). Seed 54: 44.8/44.5 vs v11 44.4/43.0, i.e. +0.9, within noise; heads-up wins 61-63% vs 48-62%. Kept sh_k 0.15.
- Next ideas: 3-handed play (T3 had 155 3rd places). Fixing the hindsight bias of the postflop MC for multiway made hands. Re-check heads-up win rate in the T4 places (it was 41% in T3).

## Log / test results (localsim, 1000 tables unless noted, ±2 = 95% CI per bot)
- v1 001-bdf6aa79: first accepted. Zoo (60 tables): 57.5.
- v2 002-a0d65428: + Monte Carlo postflop blend, bigger table, more postflop aggression (val 0.66 / thin 0.50 / cbet 0.7 / face_pen 0.06). Field test: var_post 40.9 vs base 37.5 vs v1 37.6.
- Tried and rejected (no gain, or worse): push/fold from 20bb with caller_k 1.2 (−2 to −3); multiway all-in fix (counting only callers): ≈0 to −1; tighter preflop; looser preflop; even more postflop aggression; tighter all-in calls (w_mult 0.7); caller_k 2.0; SB limp 30%; c-bet 45%; short-handed range widening (sh_k 0.08/0.15).
- v3 003-895e0ca7: ICM shove on.
- After v3, tried and rejected:
  - Extra ICM conservatism: icm_sm 0.5 / icm_ce 0.03 tied; 1.0 / 0.06 was −2.3, fewer 1sts.
  - MC discard selection with common random numbers (mc_disc=1): 43.2 vs 44.9 without, no gain, and more CPU.
  - Value bets +0.25 pot: tie.
  - Open size 3bb: −3.
  - All of these stay off in bot/ (params default to v3 behaviour).
- v4 004-7136cebb: auto-steal (param auto_steal=1).
- After v4, tried: blending fold-to-raise into the push/fold caller model (pf_fr=1). 49.6 vs 49.2 in the zoo-like field, no gain; left off.
- v5 005-183196aa: face_pen 0.06 → 0.09 (see Last change). raise_thr 0.70 was a tie (40.3).
  - Maniac-heavy field checks of v5 vs v4 (700 tables each): 51.0 vs 53.7 (seed 26), then 54.7 vs 49.8 (seed 27).
  - Over all 4 comparison runs v5 averages ≈ +1.6 over v4, so it was kept.
- Final benchmark (800 tables, seed 28; field v5 + v1-v4 + nit, maniac, montecarlo): v5 41.8, v3 38.6, v1 38.6, v2 38.4, v4 36.6, nit 35.7. v5 is the version to patch from.
- v5 zoo (600 tables, seed 15, same seed as the v3 zoo run): v5 56.6 vs v3 53.6, nit 48.7, checkfold 46.5. No substitutions; max 0.9 ms on the busy machine.
- Where points leak (places.py, 400 tables, seed 29; field v5, v4, v3, nit, checkfold, maniac, montecarlo, pot_odds):
  - v5 places [110, 45, 32, 42, 55, 65, 40, 11] = 44.3. v4 scored 44.6, v3 41.1.
  - nit finished 2nd 163 times and checkfold 3rd 177 times.
  - Our bots win often but bust 5th-7th in about 40% of tables. The losses come from mid-game 5-7-player confrontations, in which the other strong bots also play.
  - Next patch idea: more caution with 6-7 players when the table has passive survivors (ICM for 6+ players via the top-5 stacks). Alternatively, range-weighted postflop MC.
- Last check (400 tables, seed 30, field v1-v4 + nit, checkfold, maniac): v4 39.1, v2 37.7, v5 36.4, v1 35.4, v3 34.8, all inside ±3.6 noise.
  - v5 vs v4 over 7 comparisons: +3.6, +0.7, −2.7, +4.9, +5.2, −0.3, −2.6, mean ≈ +1.3.
  - v5 ≈ v4, very slightly ahead. Small parameter changes are below what 1000-table localsim can resolve; patch only with bigger structural changes.
- After v4, tried: wider BB defence against single raises with good odds (bb_def 0.25/0.35). 37.8/39.2 vs v4 copies 37.5/40.3, no gain; left off (bb_def=0).
- Zoo (600 tables): v3 53.6, nit 49.7, checkfold 46.6. Places: 237 1st / 30 2nd / 54 3rd / 125 4th of 600. The finishes are bimodal: either it wins or it busts around 4th-5th, while checkfold piles up 2nd/3rd just by surviving.
- Place histograms (tools/places.py, 500 tables): our bots win 1st ~25-30% of tables; nit mostly 2nd/3rd.

## Known weaknesses / next ideas
- The parameter space looks flat against my test field (copies of my versions + house bots). Real opponents are other teams' bots, so the exploit stats matter more there.
- Postflop equity is against random holdings and only roughly penalised for bets. Range-weighted MC (reject weak opponent samples when they bet) would be better.
- No ICM for 6+ players (too slow in Python). Approximating with the top-5 stacks would be possible.
- Timing: localsim on the busy machine shows p99 300-500 µs and rare max ~1 ms spikes. MC_BUDGET=0.22 ms of wall time.
- Tools: tools/precomp.py (table), tools/places.py (finish histograms), tools/var_* (param variants via params.json).
