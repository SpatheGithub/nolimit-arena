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

## T1 result (bot 008): rank 8/8, 29.72 pts/table (field 29.7..34.9, ranks 1-7 within noise of each other)
- Places 1st..8th: 103 138 100 145 107 121 140 146 -> too many 7th/8th (busting), too few 1sts.
- Our VPIP 21 / PFR 17, showdown win 47% (<50%: calling down too light). Winner b02 VPIP 19 / PFR 14 (tightest).
- sample_hands.json only has level-1 hands (first 10 hands of 4 tables) and doesn't mark our seat; it shows the
  field is solid TAG (2.5bb opens, 3-bets to ~7.5bb, c-bets ~0.5 pot, overpairs stack off).

## Patch before T2: 009-10eea6df (v12) = v11 +
- ICM_ALPHA 0.6 -> 0.85 (all-in decisions closer to true ICM; busting is costly with these payouts)
- deep-stack preflop call discount e-0.07 -> e-0.10 (looser BB defense/cold calls were bleeding)
- postflop call margin flop 0.03->0.045, turn/river 0.02->0.035 (showdown win 47%)
- Local test: equal to v11 (43.1 vs 43.2); the house field can't separate them. Submitted on T1 evidence + theory.
- v12 push/fold probe: 8p BTN 12.5bb shoves ~8% (88+, ATs+, AJo+); 5p BTN 10bb ~11%; BB calls BTN 10bb shove ~18%.
  Tight, but consistent with ICM for this payout table. If T2 shows few 1sts / blinding out, lower ICM_ALPHA.
- Tried SB completing instead of folding at <=18bb when folded to (v13): HU top 75% + multiway top 45%: 40.9 vs
  v12 copies' 43.3; HU-only version: 43.1 vs 43.3. Neither better, so neither submitted. bot/ = v12 (009).
  (HU SB in v12 shoves ~40%, folds ~60% at 12.5bb, which is a possible leak to revisit with better evidence.)
- Safety check, 1000 tables: v12 44.7 vs v11 copies 43.8/43.7/41.1 (avg 42.9). v12 is no worse; keep it.
- vs earlier submissions (500 tables): v12 45.4, 008 44.8, 005 42.0, 001 38.8, nit 35.8. v12 leads again.
- vs house zoo (300 tables): v12 58.4 (v11 was 55.8, v1 53.8), nit 46.6. 0 timeouts/errors; p99 ~0.5ms on a busy machine.
- Next window: read T2 places. If 7th/8th busts dropped but 1sts are still low, the endgame (3-handed/HU)
  is the place to work (HU limp/min-raise strategy, wider HU shoves).

## T4 result (bot 014/v17): rank 3/8, 32.23 (best so far). Places: 116 141 134 128 134 102 115 130
- HU conversion 116/257 = 45% (was 41%), 8th 130 (was 156). Weighted total 307.73, rank 5.
- Built tools/hu.py: 2-seat harness via arena run_tournament(seats=2, points 100/60, high blinds), with a
  __main__ guard (macOS spawn). Deterministic per seed; 3000 matches take ~5-20s. tools/mkvariant.py makes patched
  copies in $TMPDIR/variants (no rm on variable paths: that needs approval and gets denied).
- HU win% vs v15 (3000 matches, +-1.8%): v17 48.1 (12.5bb) / 48.4 (25bb); v17 without limp 50.9 / 51.3;
  v19 (=no limp) 50.9 / 51.5; v19 without HU_SHOVE_K 50.0 / 50.6; v19 with HU_OPEN 0.60 50.9 / 50.0.
  -> the HU limp hurt against push/fold opponents; the HU shove prior and 85% open help slightly.
- v19 = 015-91ecee74 (ACTIVE for T5): v17 with HU_LIMP_PCT = 0.
- More HU tests (not adopted, all within +-1.8%): HU q boost 0.14->0.08 (wider SB shoves): vs v15 51.9/50.0,
  head-to-head vs v19 49.7/51.4/48.6. BB assumes HU SB open >=0.75: vs v19 51.7, vs v15 51.2 (v19 51.5);
  >=0.45: vs v19 49.9, vs v15 50.5.
- 8-max regression (400 tables): v19 43.5, 014 43.5, 010 43.9, 009 42.0 (no change outside HU, as expected).
- tools/three.py = 3-seat harness (A vs 2 copies of B, points 100/60/40). At 8.3bb each over 2000 tables:
  v19 67.0 vs v15 66.5; ICM_ALPHA 0.6 variant 67.2 vs v19 66.4. Both within +-1.1, no change.
  At 16.7bb: a60 vs 2x v19 67.2 vs 66.4; v19 vs 2x a60 67.6 vs 66.2. Contradictory, so ICM_ALPHA stays 0.85.
- Deep HU 50bb vs v15 (2000 matches, +-2.2%): v19 49.4%, open60 50.4%. At 25bb v19 51.5 vs open60 50.0. Keep 0.85.
- v19 HU at 12.5bb vs nit: wins 94.5%; vs threshold: 52.7%. No anomalies.
- Next ideas: tune 3-handed push/fold with tools/three.py at other depths; try HU-specific
  opponent stats (shove frequency in HU hands only) for faster adaptation.

## T3 result (bot 010/v15): rank 7/8, 30.18. Places 1st..8th: 98 144 122 126 138 113 103 156
- HU conversion is the clearest leak: 1st/(1st+2nd) = T1 103/241, T2 83/208, T3 98/242 -> 284/691 = 41%
  (about 4.7 SE below 50%). We reach HU often and lose it. Showdown win 46.8%. Sample hands are level-1 only.
- Pre-v16 HU push/fold: SB shoved ~40% and folded ~60% at 12.5bb; BB called SB shoves ~30% (equilibrium ~37-40%,
  and field bots probably shove wider). Deeper HU: SB opened only 60%; BB treated SB opens as ~36% range.
- v16 = 011 (see below): HU only:
  HU_LIMP_PCT 0.8 (SB completes instead of folding when not shoving), HU_SHOVE_K 6.5 (opp HU shove range ~6.5/bb,
  cap 0.9 -> BB calls ~40% vs 12.5bb shove), HU_OPEN_PCT 0.85 (SB opens 85% deeper), BB assumes HU SB open >=60%.
- Local tests (8-max, HU diluted, vs own copies): +0.25 (push/fold part only), -1.8 (full) -> within noise.
  Submitted on tournament evidence + equilibrium theory. v16 = 011-a6505b96.
- v17 = 012 (see the submit log): targets early busts (8th = 156). Deep (>=30bb), facing a 3-bet or 4-bet, the old
  code shoved the top 2.5% (QQ+, AK) for 100bb, bypassing ICM. Now only pr < DEEP_STACKOFF_PCT=0.012 (AA-QQ)
  shoves; AK/JJ-99 call if the call is <=25% of stack. Local: 44.1 vs v16 copies 43.7 (neutral).
  v17 = 012-fd41af8a.
- v18 = 013-e445a9e9 (ACTIVE): postflop all-in raise (spr<2.2, e>=rthr) now needs e >= EARLY_AI_RAISE=0.86 while
  5+ players are alive; otherwise call if e >= need+margin. Callers of all-ins are stronger than bettors, and early
  busts (8th) are costly. Local: 45.0 vs v17 copies 43.5 (+1.5, noise).
- But the regression run vs submissions had v18 43.6 vs 012 (v17) 46.2, 010 45.0, 009 43.7. Net v18 vs v17 is
  about -0.6 over two runs, so not better. Reverted bot/ to v17 (identical to 012) and resubmitted it
  as 014-fd41af8a (same code hash as 012). EARLY_AI_RAISE idea is parked.
- ACTIVE for T4: 014-fd41af8a = v17 (v15 + HU fixes + deep 3bet/4bet stack-off guard).
- Regression vs submissions (500 tables): v17 45.8, 009 43.3, 008 42.5, 010 41.4.
- Ran v17 with act() exceptions re-raised (200 tables incl. HU endings): 0 errors, so the new HU/deep paths are clean.
- Ideas not done: ICM gate on postflop all-in raises (spr<2.2 & e>=0.78) since callers are stronger than bettors;
  value-bet threshold vs checked ranges; more accurate HU testing needs a custom 2-seat harness
  (localsim is always 8-max).

## T2 result (bot 009/v12): rank 8/8, 29.27 (winner b06 36.4 with VPIP 24 / PFR 19)
- Places 1st..8th: 83 125 154 138 140 125 103 132. Busts fell vs T1 (7th+8th 286 -> 235) but 1sts fell 103 -> 83.
  We survive into 3rd-5th and rarely win. Showdown win still 47%. Sample hands are level-1 only again (no help).
- Tried ICM_ALPHA 0.4 (more chip-EV push/fold): 40.7 vs v12 copies 43.8 locally, so not submitted.
- Found leak: the opener's range was estimated from overall raise frequency (prior 18%) regardless of position,
  so we over-folded the blinds to BTN/SB steals and under-restole. Fix: OPEN_POS_F multiplier by players
  behind the opener {SB/1:2.0, BTN/2:1.6, CO/3:1.25, 4:0.95, else 0.8}. BB vs BTN 2.5bb open now 3-bets ~6%,
  calls ~40%. Local: 45.5 vs v12 copies 41.7 (350 tables).
- Submitted as v15 = 010-49ac4159 (v12 + OPEN_POS_F; ICM_ALPHA stays 0.85).
- Confirm run (350 tables) vs submissions: v15 45.2, 009 44.4/42.6, 008 43.3. Consistent lead.
- vs house zoo (300 tables): v15 60.6 (v12 58.4, v11 55.8). No sign of exploitation by raise-happy bots; 0 errors. If T3 still shows few 1sts, look at HU play (SB folds ~60% at <=18bb).

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
