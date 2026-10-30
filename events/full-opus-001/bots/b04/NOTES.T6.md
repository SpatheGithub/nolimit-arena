# Team notes (b04)

## Approach
Aggressive-pressure NLHE SNG bot (bot/agent.py) with helpers copied from house-bot `_common.py`
(Spot parser, Ranker, postflop `features()` strength, preflop class/percentile tables).

- Preflop:
  - Unopened: open-raise ranges by # players behind (OPEN table, BTN 48%, SB 62%), 2.3bb (3bb SB);
    deep (>40bb) early/mid positions tightened by DEEP_OPEN=0.7; widened/tightened by observed
    fold-to-raise rate of players behind.
  - <=13bb: open-shove. Candidate range = PUSH table (Nash-like) x PUSH_CAP, final decision by
    ICM EV with fold equity. Each player behind calls with top cr (prior 12%, from observed fold rate;
    x1.8 for BB, x1.2 SB, x1.6 if the call is cheap for them, x2.5 if they're nearly all-in anyway).
  - Facing a raise: raiser range = observed open rate x position factor (3-bet: observed re-raise rate).
    Re-steal shove (<=32bb) if ICM EV with fold equity > RESTEAL (0). All-in calls by ICM EV
    using precomputed equity vs top-R% ranges (bot/eqr.json, 4000 samples per cell, tools/eqrange.py).
    Cheap flat calls (BB pct<=35%, others <=12%) when the shove isn't +EV.
  - Deep: 3-bet value (pct<=3.5%), light 3-bets vs wide openers 35%, BB defend pct<=45% vs small opens.
- Postflop: features() strength s, outs. Value bet s>=0.6 (size x1.2 vs stations, x0.85 vs folders),
  c-bet HU 75%/50%/20% flop/turn/river, stabs 25% IP HU; bluff freq scaled by opponents' observed
  fold-to-bet rate. Semi-bluff draws. Facing bets: eq = s - bet-size penalty + bettor aggression adj;
  draws use 2-card equity on flop (x0.85) / implied odds on turn; call if eq >= pot odds; big commits
  (>=50% stack) need positive ICM EV.
- ICM: bot/icm.json = ICM points by (players left, my chip fraction), others equal (kit/icm.py);
  exact Malmuth-Harville (icm_me) with real stacks when <=4 players have chips and <=5 alive.
  Value = ICM_W*ICM + (1-ICM_W)*chip-linear points, ICM_W = 0.8.
- Opponent model (per table only): open rate, fold-to-raise, re-raise rate, postflop aggression,
  postflop fold-to-bet, all with priors.

## Key parameters
OPEN/PUSH tables, PUSH_CAP=1.6, RESTEAL=0.0 (ICM pts), STAB=0.25, RIVER_BLUFF=0.2, DEEP_OPEN=0.7, ICM_W=0.8.

## Test results (localsim)
- Each house field x7: nit 80, maniac 47, montecarlo 57, pot_odds 45, random 68, minraiser 48,
  threshold 57, checkfold 100 (all 1st).
- ICM vs chip-EV all-in decisions: +3.6 pts (600 tables, mixed field). Blend 0.6 vs 1.0: +1 (noise).
- Field of all my submissions: latest ~35 vs v1 ~28.
- In fields with several aggressive clones, the house nit scores ~37-43 (survival is worth a lot with
  100/60/40/25/15/10/5/0); ICM was the fix that helped most.

## Submissions
- 001 baseline; 002 opp model + ICM all-in; 003 RESTEAL=0 + flat calls + postflop fold stats + precise eqr;
  004 exact ICM (<=5p) + blind call-range fix; 005 draw-equity fix, ICM_W 0.8, exact ICM <=4p;
  006 value sizing vs stations/folders + showdown-based range widths; 007 multiway all-in eq^(1+0.4*callers).
- 009-a15c20b6 = 007 + unopened shove-or-fold up to 20bb (008 was the 16bb step). Played T1.
- ACTIVE for T2: 010-0eb467a0 = 009 with shove-or-fold up to 25bb (zoo 300 tables: 55.0, 1st).
- Late A/Bs (600 tables, all within noise): SB deep-open x0.75 = no change; re-steal call_r lower
  (more re-steals) -1.8; call_r higher (fewer re-steals) -3 -> kept 007 values. Multiway exponent 0.7 was -2.

## Loss diagnostics (end of build, tools/vDiag logs hands losing >35% of stack to tools/diag.log)
- 300 mixed tables, share of big-loss chips: preflop re-shove 13-30bb 23%, preflop calls 13-30bb 16%,
  open/re-shove <=13bb 11%, calls <=13bb 9%, river calls (deep+mid) ~12%, everything else small.
- Re-shoves 13-30bb used hands with median pct 0.42 (90th pct 0.83) vs callers' shown median 0.05.
  Tried RESTEAL_PC=0.35 floor + RESTEAL_CAP=0.30: A/B -1.9 (noise) -> NOT submitted (the log only shows
  called re-steals, not the ones that won the pot uncontested). Worth re-testing with real tournament data.
- Postflop big losses looked like coolers (sets, two pair, full houses), not systematic.

## Extended window (16:14-16:25)
- Big A/B design: 3 copies of variant + 3-4 copies of baseline + nit, 1000 tables (~60-90s).
- Re-steal fix (RESTEAL_PC 0.35 + RESTEAL_CAP 0.30): -2.9 vs 007 -> rejected; wide re-steals ARE profitable.
- Open shove-or-fold threshold (unopened pot) 13bb -> 16bb: +1.7 (all 3 copies above all 007 copies) -> 008.
- 16bb -> 20bb: +2.6 vs 008 (again all 3 above all 4); zoo 300 tables 56.0 (1st) -> submitted as 009.
- 20bb -> 25bb (tools/vS25, 500 tables, not submitted: window closed): 34.1 avg vs 009 31.2 avg (+2.9,
  but only 500 tables and one 25bb copy fell below one 009 copy). FIRST THING TO DO IN THE PATCH WINDOW: confirm with
  1000 tables + zoo check, then submit (one-line change at agent.py `if eff_bb <= 20:` in the unopened branch).
  Second seed (400 tables): vS25 32.6 avg vs 009 32.5 avg -> no difference. Combined evidence is weak;
  20bb (009) may already be near the optimum. Only switch to 25bb if a 1000-table run is clearly positive.
- Then try widening the re-steal zone (eff_bb <= 32 now); aggression keeps paying in clone fields.

## T1 result (bot 009): rank 2/8, 33.99 (b02 34.90 with VPIP 19/PFR 14 won; all within noise)
- Places 1st 184, 2nd 99, 3rd 94, 4th 98, 5th 110, 6th 109, 7th 140, 8th 166: bimodal (many 1sts AND early busts).
  0 subs, cpu p99 100us, max 871us. No table reached the 200-hand cap. Field VPIP 19-28%, PFR 14-22%.
- Bust diagnostics (tools/vBust, 500 tables in clone field): early busts (>=7 alive) = preflop re-shoves/open
  shoves at <=16bb (~40%), postflop stack-offs deep (~30%: turn/river raises, 3-street call-downs), coolers.
  With 100/60/40/../0 payouts, early busts are cheap relative to 1st places; aggression stays.

## Patch before T2
- Tried barrel penalty (eq -0.06 per earlier street the bettor bet, -0.03 on river, turn/river raise only s>=0.85):
  -0.3 vs 009 (1000 tables) -> not submitted (clones bluff-barrel; real field may differ, idea kept in tools/vBar).
- Unopened shove-or-fold threshold 20bb -> 25bb: 6 runs / 4900 tables, +0.95 avg (~2.6 SE) -> submitted 010-0eb467a0.
- 25bb -> 30bb: +0.25 (1 run, 1000 tables) = flat; diminishing returns, keep 25 (tools/vS30 if needed).
- Re-steal zone 32bb -> 40bb (tools/vRS40): -0.07 (1 run) = flat; keep 32.
- ICM_W 0.8 -> 0.7 (tools/vW7): -0.8 (1 run); ICM_W 0.9 (tools/vW9): -0.1 (1 run). Keep 0.8.
- Barrel penalty rebased on 010 (tools/vBar10) vs value-betting field (threshold, pot_odds, nit + 010 x3):
  +1.3 (700 tables, 1 run). Clone field said -0.3. Depends on whether real opponents bluff-barrel:
  TOP CANDIDATE for the T3 window - run 3-4 more seeds in mixed fields; submit if consistently >= 0.
  Seed 421 (500 tables, threshold/pot_odds/maniac + 010 x3): +1.06 again (both vBar10 copies above all 010).
  Seed 431 clone field (vBar10 x3, 010 x3, 007; 400 tables): -0.8. Pattern: helps vs value-bettors, hurts
  vs bluffy clones. Decide in T3 window using T2 own_stats (opponent aggression) - consider making the
  penalty conditional on the bettor's observed aggr_rate (apply only when aggr_rate < ~0.35).
- Ideas next: re-steal zone (<=32bb) and its fold-equity model, barrel penalty vs real field, GC/alloc
  trimming (referee cpu max 871us, close to the 1ms limit, though 0 timeouts in T1).

## T2 result (bot 010, 25bb shove-or-fold): rank 5/8, 31.59 (b06 36.36 won)
- Places 1st 155 (T1 184), 8th 193 (T1 166): fewer wins, more early busts vs T1's 009 (20bb).
  Confounded with field changes, but consistent with real opponents calling shoves more than my clones do.
- VPIP 23 / PFR 17 (T1 25/19): 20-25bb hands that fail the shove EV check are folded instead of opened.

## Patch before T3
- 011-a15c20b6: reverted to 009 code (20bb) immediately.
- 012-46d64584 (ACTIVE for T3): 009 + per-seat learning of responses to preflop all-ins
  (hand-start stacks recorded at my first preflop decision; at hand_end, every seat acting after the first
  all-in raise counts as call/raise or fold). shove_call(seat, prior) = (calls + 4*prior)/(faced + 4) replaces
  the assumed call range for open shoves (cr) and re-steals (call_r). Clone field +0.5 (1000 tables), zoo 58 (100),
  no errors in debug run. Loose-caller field test did not finish (machine busy, command timed out).
- Caution: localsim runs with pot_odds/maniac/threshold mixes can take minutes when the machine is busy.
- Loose-caller field A/B 012 vs 011 (2 x 300 tables): -2.8, +0.3 -> overall neutral with the clone +0.5.
- Bias found: calls of tiny short-stack shoves were counted as "calls a shove", inflating call rates and
  making my real shoves too timid. Fix: count a response only if the shove >= 30% of responder's start stack.
  Submitted as 013-588da5cc = ACTIVE for T3; quick 300-table check was noise-level, no errors.
- If T3 is worse than T1's 33.99 again, fall back to 009 code (.submissions/011-a15c20b6 is identical).
- Post-submit info run (clone field, 400 tables): 013 avg 31.5 vs 011 avg 34.0 (-2.4, ~1.5 SE) - the
  filtered adaptive version may be worse. T4 window: run 2-3 x 1000-table A/B of 013 vs 011 FIRST; unless 013
  is >= 011, resubmit 011's code (copy .submissions/011-a15c20b6/agent.py to bot/).
  Second info run (seed 511, 400 tables): 013 32.8 vs 011 32.0 (+0.8). Net over 800 tables: about -0.8 = noise.
  Third (seed 521, 400 tables): 013 30.9 vs 011 34.4 (-3.5). Net over 1200 tables: about -1.7 (~1.8 SE).
  => T4 window: DEFAULT ACTION = resubmit 011's code (009, T1 rank 2) unless new evidence favors 013.
  bot/ ALREADY HOLDS 011's code (staged 17:04, check_bot OK); T3 plays 013-588da5cc.
  Fourth run (seed 531, 300 tables): 013 31.6 vs 011 32.9 (-1.3). Net over 1500 tables: about -1.6.

## T3 result (bot 013): rank 2/8, 34.07 (b06 34.94). Weighted total 199.37, rank 2.
- Places 1st 165, 2nd 133, 3rd 103, 4th 95, 5th 98, 6th 94, 7th 137, 8th 175. cpu_max 1197us but 0 timeouts.
- Real field: 009 (T1) 33.99 ~= 013 (T3) 34.07, although clone-field A/B said 013 was 1.6 worse ->
  clone-field proxy does NOT predict real-field results well (it also favored 010, which did worse in T2).
  New rule: only adopt changes that are >= 0 in several proxy types (clone field AND house-bot fields).

## Patch before T4
- 014-2245fff3 (ACTIVE for T4): 013 + barrel penalty only vs passive bettors:
  pw = clamp((0.45 - aggr_rate(bettor)) / 0.15, 0, 1); on turn/river eq -= pw * (0.06 * earlier streets
  the bettor bet + 0.03 on river). A/B vs 013: clone +0.54 (1000), value-bettors +2.3 (700), mixed with
  maniac -0.08 (600). No errors in debug run; check_bot OK. Extra check vs 013 (clone, 800 tables): +1.31.
- Rejected afterwards (window extended to 21:27:38):
  - turn/river raise with s in [0.76,0.85) only vs aggressive bettors (tools/vCB2): -0.65 vs value-bettors.
  - thin river value bet (s>=0.48, 0.5 pot) vs stations with post_fold<0.35 (tools/vTV): -1.75 vs stations.
- 014 sanity: zoo 300 tables 56.5 (1st); vs 011 (T1 code) in value-bettor field +3.35 (500 tables).
- 015-12cabef9 = ACTIVE for T4: 014 with stronger passive-bettor penalty (0.08 per earlier barrel, 0.04 river;
  was 0.06/0.03). A/B vs 014: value-bettor fields +1.38, +2.29 (500 each), clone -0.21 (800). Debug run clean,
  check_bot OK. If T4 disappoints, 014 (.submissions/014-2245fff3) is the fallback.
  Later mixed fields (threshold/maniac/nit or pot_odds + 014 x2): -1.36, +1.42 (600 each).
  Net 015 vs 014 over 5 runs / 3000 tables: about +0.57 -> kept 015. Zoo (seed 611, 300 tables): 57.3, 1st
  (014 on the same seed: 56.5).
- Rejected: extra eq -0.08*pw when facing a raise from a passive player (tools/vRP): -0.77 vs value-bettors.
- Extra clone-field check 015 vs 014 (seed 701, 600 tables): +0.63. Net over 6 runs / 3600 tables: ~+0.58.
- Candidate for next window (tools/vPW5): passive threshold 0.45 -> 0.50 in pw = clamp((0.50-ar)/0.15).
  Value field (seed 711, 450 tables): +1.31 vs 015 (one 015 copy scored above both). Clone field (seed 721,
  450 tables): -0.75. Net ~+0.3 = noise; only pursue with more runs.
- Next ideas: per-seat postflop "bets only with strong hands" detection via showdowns (shown hand strength
  when they bet turn/river) to set the penalty directly instead of via aggr_rate.

## T4 result (bot 015): rank 2/8, 34.45 (b06 34.77). Weighted total 337.15, rank 2 (b06 ~350.6, 3rd ~322.8).
- Places 1st 173, 2nd 121, 3rd 108, 4th 89, 5th 99, 6th 114, 7th 143, 8th 153. cpu_max 530us, 0 subs.
- Real-field history: 009 33.99 (T1), 010 31.59 (T2), 013 34.07 (T3), 015 34.45 (T4).
- T4 samples (my seat found via 2.3bb opens = raise to 46): biggest loss KJ on 9-9-3-J calling BB's turn+river
  leads vs AJ (kicker). BB leads from passive players look value-heavy.

## Patch before T5
- 016-e0df6e0a (ACTIVE for T5): 015 + "donk lead" penalty: facing a single bet (sp.raises == 1) from a passive
  player (pw > 0) when I was the last aggressor, eq -= pw * 0.05. A/B vs 015: value field +2.97 (500),
  clone -1.08 (800) and +0.82 (800), mixed w/ maniac +0.57 (600) -> ~+0.6 over 2700 tables. Debug clean.
- Fallback: 015 (.submissions/015-12cabef9), the best real-field result so far.
- Post-submit checks of 016 vs 015: zoo 57.8 (fine) but mixed fields -1.71 (500), -1.91 (600).
  Net over 6 runs / 3800 tables: ~-0.1 -> REVERTED to 015 code: 017-12cabef9 = ACTIVE for T5 (same code as 015).
- Lesson: single-run gains of +2-3 in one field type routinely vanish; need >= 4 runs across field types.
- vPW5 (passive threshold 0.50) vs 015: value +1.31 (450), clone -0.75 (450), mixed +0.91 (600), clone -0.38 (600)
  -> net ~+0.27 over 2100 tables: below the +0.6 bar, not submitted.
- T6 plan: keep 015 code (017) unless T5 reveals a real problem; any change needs >= 4 runs, net >= +0.6.
- Info: 015 vs 011 (T1 code) mixed field (seed 821, 500 tables): -1.07; earlier value field +3.35 (014 vs 011).
  Proxies disagree; real field favored 015 (T4 34.45 vs T1 33.99), so 015 stays the default.

## T5 result (bot 017 = 015 code): rank 4/8, 31.78 (b06 35.19, b02 33.06). Weighted 496.05, rank 2.
- Places 1st 161, 2nd 107, 3rd 101, 4th 81, 5th 88, 6th 115, 7th 145, 8th 202. cpu_max 937us, 0 subs.
- Same code scored 34.45 in T4 and 31.78 in T5 -> real-field noise is about +-2.5 per tournament.
- Real results by version: 009 33.99, 010 31.59, 013 34.07, 015 34.45 / 31.78. All within noise of ~33.
- Estimated weighted totals after T5: b06 ~526.5, b04 496.05, b02 ~487.1, b08 ~474.4, b05 ~466.0.

## Decision for T6 (weight 6)
- Keep 017-12cabef9 (015 code). No version is distinguishable in the real field, proxies have not predicted
  real results reliably, and the last tournament has the largest weight, so an untested change has risk
  without demonstrated gain. T5 sample hands showed no bugs (sensible folds, normal coolers).

- Unverified hypothesis (not submitted): deep open-shoves (raiser >= 30bb) are probably premium-only for tight
  bots, but rng_est uses open_rate x posf x 0.9 (~0.18). A cap like min(rng_est, max(0.10, 0.6*open_rate))
  would avoid calling off with TT/AQ vs QQ+/AK, but would over-fold vs maniacs; needs real-field shove data.

## Known weaknesses
- Postflop strength is a category heuristic, no real equity / range reading.
- Fold-equity model for shoves is crude (prior call range 12%), re-steal call_r guess.
- ICM table for >4 players assumes opponents have equal stacks; ICM ignores blind pressure (blend helps).
- Occasional localsim "hang"/max-time spikes are machine load (p50 25us, p99 ~100-200us).

## Next steps / ideas for patch windows
- Use showdown cards to calibrate opponent ranges; per-seat call-vs-shove frequency.
- Tune open-shove threshold (13bb) vs raise-fold at 13-20bb.
- Ramp ICM_W to 1.0 near the hand cap.
- Tools: tools/scen.py (preflop spots), tools/post.py (postflop spots), tools/scan.py (push range sizes),
  tools/bench.py (timing). A/B: copy bot to tools/vX and run localsim with mixed --opponents.
