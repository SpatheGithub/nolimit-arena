# Team notes (b08)

## Submissions
- 001 baseline; 002 +ICM on postflop big calls; 003 +opponent reads (shove freq, call-vs-allin, fold-to-bet)
  and EV-based bluffing; 004 +exact ICM (<=4 alive), ICM margin 2pts when >=5 alive, opens x0.85;
- 005-4412fcfa (active): + wider short-handed opens (HU 80%, 3-handed BTN 45%), postflop calling fix
  (DISC_MULT=1.5 on the bet-narrowing discount; the "cheap draw call" branch now needs discounted equity).

## T1 result (bot 005): rank 2/8, 33.73 pts (leader b03 34.78, within noise)
- Places 1st 11.3%, 2nd 13.1%, 3rd 16%, 4th 19.6%, 7th+8th 17.6%: survive well, convert poorly.
- 9 substitutions (4 timeouts, 5 hangs), cpu max 2.7ms -> MC budget cut 0.45 -> 0.35ms (006).
- Field VPIP 22-25%, PFR 17-20% (TAG bots); we were 19/12.

## Patch before T2
- 006-2f88672d: MC budget 0.35ms (p99 ~400us).
- 007: heads-up range floors: opp HU shove range >= 55%/45%/35% (<=10/15/20bb), opp HU call range
  >= 0.06+3/bb. HU SB shove 100% -> 62% at 10bb; BB calls 43/35/28% vs 6/10/15bb shoves (~Nash).
  Paired tests vs 006: seed 81 200t 43.1 vs 41.8; seed 83 600t 46.8 vs 44.8 (more 1sts).
  ACCEPTED as 007-396fa1f9 (active for T2). Third seed 89 600t: 43.2 vs 44.6 (-1.4) -> net ~+0.4,
  mostly noise; kept for the theory (old HU logic shoved 100% at 10bb and called HU shoves too tight).
- Health check of 007 vs house zoo (localsim seed 123, 300t): 60.35 pts, 1st of 8 (nit 44.9),
  0 substitutions, max 550us. bot/ == .submissions/007-396fa1f9.
- 007 vs 005 (T1 bot) paired seed 97, 500t vs 005 copies: 44.0 vs 45.0 (-1.0, noise +-3). All HU-change
  pairings so far: +1.3, +2.0, -1.4, -1.0 -> ~0. Kept 007 (also has the timeout fix).
- Rejected: DISC_MULT 2.0 on top of 007: seed 87 600t 43.1 vs 45.7 for 007 -> keep 1.5.
- Ideas next window: 3-4 handed aggression (we finish 3rd/4th a lot), small 3bet pots at 6-8 alive,
  BB defence; use paired seeds (same --seed, --me tools/vX vs --me bot), 600 tables, ~80s each.

## T2 result (bot 007): rank 4/8, 31.79 (b03 35.37 leads again). 0 substitutions.
- Same shape as T1: 1st 10.7%, 4th 19.2% spike. We were the tightest bot (VPIP 19 / PFR 11 vs field 22-24 / 17-19).
- KEY: a field of my own submissions (.submissions/002..007 + nit) reproduces the real result for 007
  (31.8 local vs 31.8 real) -> use it as the proxy for the real field; the house-bot field misled me
  toward tightness.
- 008-d224c379: ICM margin at >=5 alive 2 -> 0, opens x0.85 -> x1.0. Paired vs 007 in TAG field:
  seed 101 38.7 vs 31.8; seed 103 37.3 vs 33.0. Variants: opens x1.2 36.6 (seed 103, ~same);
  W_LIN 0.3 39.2 (103) / 40.2 vs vA 40.5 (107) -> no extra gain.
- v8 in TAG field: VPIP 24 / PFR 19 (matches real field). 002/003 (no margin) score like v8; 004-007 28-31.
- Seed 111 paired vs v8 (39.98), all rejected: DISC_MULT 1.0 38.0; final-table exact-ICM 30% chip blend 40.2
  (noise); opens x1.2 38.9; shove cutoff 15bb 37.2, 20bb 38.1, 22bb 38.6 -> keep 18bb.
- vF (final-table exact ICM blended 30% toward chip-linear, tools/vF): +0.25 (seed 111), +0.94 (seed 113)
  vs v8, then -2.4 (seed 117) -> net ~0; rejected, NOT submitted.
- vJ wider deep 3bet (rng_r*0.35 or eq>=0.60, tools/vJ): -1.1 (111), +2.7 (113), +1.9 (117), +0.0 (119)
  -> avg +0.9, likely small positive; not submitted before T3 (missed my +1 rule). Top candidate next window.
  v8 baselines: seed 111 39.98, 113 38.32, 117 36.94, 119 38.83 (450-500 tables).
- Next-window ideas: postflop aggression/c-bet sizing vs TAG field; deep 3bet ranges; check what b03 does
  differently (VPIP 24 / PFR 18 like us now). Always test paired in the TAG field, >=2 seeds.
- v8 vs house zoo (seed 131, 300t): 62.1, 1st; 0 subs, max 458us. ACTIVE for T3: 008-d224c379.
- TAG-field command: F=.submissions/005..,004..,003..,006..,002..,007..,nit;
  python tools/sim.py --me tools/vX --tables 500 --opp $F --seed S  (~50s; run baseline on same seed).

## T3 result (bot 008): rank 4/8, 33.04 (b03 35.70 leads all three). VPIP 22 / PFR 15, showdown win
  46% (T1 49.5, T2 48). Places flatter: 1st 12.3%, 2nd 14.7%, 7th+8th 25.6%.
- Tougher proxy field F2 = 008,008,003,002,005,007,nit (v8 scores ~31-37 there, close to real 33).
- 009-8bef9511 = vJK: tighter preflop flats (deep: call only if eq >= po+0.08 and to_call <= 8% stack;
  set-mine <= 5%; no pct-based flat) + wider 3bets (pct <= rng_r*0.35 or eq >= 0.60).
  Paired vs v8 in F2: seed 201 35.3 vs 31.1, 203 37.5 vs 33.2, 205 37.2 vs 37.4 -> avg +2.8.
  vK alone (flats only) avg +1.9; vJ alone +3.0/-0.0.
- Rejected vs v9 (baselines F2: 201 35.31, 203 37.51, 205 37.22):
  call-only ICM margin +1 at >=5 alive: -2.1/-3.9/-0.7; margin -1: -1.6/-0.4/-2.0 -> margin 0 is right;
  BB defends at po+0.04 (others po+0.08): +0.1/-2.7/+0.8.
  opens x1.1: +0.1/-3.4/-1.7 -> keep x1.0.
  fold-to-bet prior 0.50 (more bluffs): -1.5/-1.5/+0.3 -> keep 0.42.
- 009 vs house zoo (seed 141, 300t): 57.6, 1st; 0 subs, max 432us.
- ACTIVE for T4: 009-8bef9511.

## T4 result (bot 009): rank 3/8, 33.22 (b06 35.63 at VPIP 28 / PFR 23, b03 35.28). Cum rank 3.
- 1st only 10.8% again; leaders are more aggressive.
- 010-22945861 = vS: late-position opens BTN (nb=2) 0.36 -> 0.45, CO (nb=3) 0.27 -> 0.33.
  Paired vs v9 in F2: 201 +1.5, 203 -1.0, 205 +2.0, 207 +2.8, 209 +2.1 (avg +1.5, more 1sts).
  vS scores (baselines for v10): 201 36.81, 203 36.55, 205 39.18, 207 37.93, 209 39.04.
- Rejected: vR (callers x0.75 when we cover, >=3 alive): +1.7/-4.4/-0.0.
- Rejected vs v10 (seeds 201/207/209): SB open 0.50: -1.4/-2.4/-3.8; BTN 0.52 + CO 0.36: -1.9/-1.1/-1.0;
  3bet rng_r*0.45 or eq>=0.58: -2.4/-2.3/-1.2. -> v10 preflop widths look locally optimal.
  value-bet size 0.9/1.0 pot (was 0.75/0.8): -1.2/-2.6/-2.9 -> keep.
  MP opens nb4 0.24 / nb5 0.19: -0.1/-1.5/-0.5 -> keep 0.21/0.17.
  fewer bluffs (ftb prior 0.38, no c-bet x1.15): -1.8/-3.6/-2.1; more bluffs (0.50) was also worse -> keep.

## T5 result (bot 010): rank 2/8, 34.48 (best yet; b06 37.37 at 28/22). Cum rank 3 (501.67).
- HU conversion still < 50% (1st 114 vs 2nd 150).
- Rejected vZ (HU: assume opener range >= 60%/40% for non-allin opens): -2.4/-2.9/-4.0/-2.6/-0.0 (seeds 201-209).
- Rejected vs v10: opens 2.2bb at all depths -1.6/-1.6/-2.1; postflop value-raise at eqe >= 0.62 -4.3/-1.8/-4.0.
- Winner's-curse check on FRESH seeds 211/213/215: v10 vs v9 -2.3/-0.6/-0.6 -> v10's +1.5 on 201-209 was
  partly selection luck; over 8 seeds v10 ~ v9 (+0.5). Real: 009 T4 33.22 (r3), 010 T5 34.48 (r2).
  Lesson: confirm a selected candidate on fresh seeds before trusting its baselines.
- Re-test on unbiased fresh seeds (v10 baselines 211 36.75, 213 34.02, 215 34.78):
  vX (MP opens nb4 0.24 / nb5 0.19): +1.2/+2.9/+1.6; vU (BTN 0.52 / CO 0.36): +1.5/+2.0/+2.5.
  Their earlier negatives were vs inflated baselines; bias-adjusted both ~+1.
- FINAL for T6: 011-75ecd4ab = 010 + vX (smaller change of the two). check_bot OK, 0 subs.
  Confirmation on fresh seeds 217/219: 011 vs 010 +0.8/-0.6 -> 5 fresh seeds avg +1.2 (4/5 positive). Kept.
  011 vs house zoo (seed 161, 300t): 62.7, 1st; 0 subs, max 467us.
- v10 vs house zoo (seed 151, 300t): 62.3, 1st; 0 subs, max 435us.
- ACTIVE for T5: 010-22945861.
- Next ideas: postflop c-bet/bluff priors (ftb prior 0.42, pf_aggr x1.15); shove-range reads.

## Approach
- Precomputed (tools/pre_*.py): evaluator lookup tables (evtab.pkl, copied from kit fasteval),
  169x169 preflop HU equity matrix (pf_eq.npy, MC 1500/pair), equity vs k random hands (pf_mw.npy),
  ICM table icm_tab.npy: f(n players, my chip share) with others equal, exact kit icm.
- Preflop: hand percentile ranking; EQR[class, top-x%] equity vs ranges (matrix product at import).
  - Unopened, eff <= 18bb: shove iff ICM EV(shove) - ICM(fold) > margin (2 pts when >=5 alive, else 0).
    Callers' ranges: 0.06 + 2/shove_bb (BB), x0.65 others, scaled by vpip, blended with observed
    call-vs-allin frequency. <=4 alive: exact ICM on the real stack vector (icm_exact, ~9us).
  - Deeper: open ranges by # players behind (x0.85), 2.5bb; 3bet strong vs raiser range; set-mine.
  - Facing all-in: ICM call check (call_ok) with equity vs estimated shove range (observed first-in
    shove frequency when <=20bb, prior by depth 45/32/22/12%).
- Postflop: Monte Carlo equity (budget 0.45ms, sd ~0.03) vs opponents' preflop ranges.
  Facing bets: equity minus discount (size/street/opp aggression, x1.5); big calls (>=35% stack) and
  all-ins use the ICM call check. Value bet >=0.55 eq; bluffs/c-bets when fold-equity EV beats checking
  (per-opponent fold-to-bet read).

## Findings
- Tables almost never reach the 200-hand cap; place = elimination order. Survival is worth a lot
  (house nit takes 2nd/3rd ~60% by folding). ICM at 8 equal stacks needs ~73% equity to call off.
- Leak analysis (tools/vdbg = instrumented copy logging tag/payoff per hand to $DBG_OUT):
  all all-in categories are chip-positive; postflop bets/raises strongly positive; postflop CALLS were
  the big leak (~-1250bb/250 tables) -> fixed in 005 (now ~-700bb). Small 3bets at 6-8 alive slightly negative.
- Parameter tests vs copies are noisy (+-2.5 pts at 700 tables); use paired seeds (--me tools/vX same --seed).
  Blending ICM toward chip-EV (W_LIN) tested worse; extra ICM margin slightly better.

## Tools
- tools/sim.py --me <dir> --opp a,b,... --tables N --seed S : prints place distribution per bot.
- tools/probe2.py : shove-range widths in synthetic spots. tools/v1..v5 snapshots.

## Known weaknesses / next steps
- Postflop calls still negative: try DISC_MULT 2.0 (tools/vD2 ready; its paired test vs v5 on seed 73
  was killed by timeouts on the loaded machine, so it is untested), or model multi-barrel range narrowing.
- Paired evidence for 005: seed 71, 450 tables: 005 46.1 vs 004 44.9 as "me"; seed 61, 250 tables: ~equal.
- Late in the window the shared machine was overloaded (sims and even `sleep` timed out): run single
  sims with timeout <= 200s and fewer tables.
- 3bet pots deep (6-8 alive) lose small; BB defence check-folds a lot.
- ICM table assumes equal other stacks for >=5 alive.
