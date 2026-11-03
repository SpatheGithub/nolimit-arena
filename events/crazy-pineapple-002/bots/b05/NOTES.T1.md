# Team b05 notes

## Strategy

**Summary:** Before the flop the bot looks up a precomputed 3-card equity table (`bot/pre3.json`). It covers all 1755 suit-isomorphic classes and was simulated with a realistic after-flop discard, with equity against random hands and against top-5/10/20/35/55% ranges. Short stacks play EV-based push/fold, with exact ICM (Malmuth-Harville, as kit/icm.py) once ≤5 players remain. After the flop it blends a time-boxed Monte Carlo equity (about 0.2 ms) with a heuristic hand-strength score. Per-seat stats (VPIP, PFR, fold-to-raise, fold-to-bet, postflop aggression) widen or narrow its ranges.

**Before the flop:** Deep (>16bb effective): open-raises top 0.40/n_behind^0.6 of hands (≈12% UTG to 40% SB) to 2.2-2.5bb (+1bb per limper), widened against blinds that fold too much. Auto-steal: it opens any hand when the product of the observed fold-to-raise rates of everyone behind (0.5 prior until a seat has faced 4 raises) makes P(all fold)·pot > 1.1·(1−P)·risk. The SB limps up to 60% when deep, and the BB raises its top 12% when checked to. Facing a raise it 3-bets about the top 3.5% (more against wide openers, by the opener's PFR) and calls about the top 10%. It switches to an all-in decision when the raise commits ≥35% of its stack, or when ≤14bb. Then it calls when equity against the raiser's estimated range (width depends on their stack depth and PFR, up to any-two for maniacs) beats the pot odds, or the ICM-required equity with ≤5 players left.

**After the flop:** Equity is a 65/35 blend of Monte Carlo (against random 3-card holdings, hindsight best-5) and heuristic strength (best 2-of-3 sub-hand; pairs ×0.86, two pair ×0.93). It value-bets at ≥0.66 equity (0.6-0.75 pot, +0.2 against calling stations) and thin-bets at ≥0.50 heads-up. It c-bets about 70% heads-up as preflop raiser, semi-bluffs big draws, and makes rare river bluffs, all scaled by the opponents' fold-to-bet. Facing a bet, equity is cut by (0.09+0.03·street)×bet/pot, scaled by the bettor's aggression factor. It calls on pot odds plus draw equity, and raises or jams at ≥0.75.

**Short stacks and the points table:** At ≤16bb effective it open-shoves when EV(shove) > 0. Callers are modelled as top 1.5/(bb+2) scaled by their VPIP. With 3-5 players left the shove decision uses exact ICM (shove vs fold in points), and all-in calls use the ICM break-even equity. With 6+ players it uses chip EV with a small margin.

**Opponents:** Per-seat VPIP, PFR, fold-to-raise preflop, fold-to-bet postflop, and aggression factor, all with priors. They set the raiser's range width, the callers' widths in push/fold, steal widening and the any-hand auto-steal, bluff/c-bet frequency, value sizing, and the call-down threshold.

**Last change:** v5 (005-183196aa) makes postflop call-downs tighter: the bet-facing penalty face_pen goes from 0.06 to 0.09. It was ahead in two 800-table runs against v4 copies (42.6 vs 40.5/37.4, then 39.9/39.2 vs 40.2/37.4). Pooled that is ≈+1.7 points (~1.9 SE). Looser (0.04) was worse, and 0.12 slightly below 0.09. v4 (004-7136cebb) had added the any-hand auto-steal against over-folders: +2.4 in a zoo-like field, no harm against my own versions.

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
