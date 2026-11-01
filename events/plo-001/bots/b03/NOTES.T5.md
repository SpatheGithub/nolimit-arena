# Team notes (b03, PLO)

## Strategy

Bot for T5: **013-959b0a3e**.

**Summary.** Math-first PLO bot. Each postflop decision runs a vectorised numpy Monte Carlo
(lookup-table PLO evaluator, exact against the engine) against up to 3 random opponent hands. The
samples are then narrowed to the bettor's likely range. Preflop uses a precomputed equity table for
all 16,432 suit-isomorphic starting hands. Tight-aggressive, with a survival premium early and wider
heads-up play.

**Before the flop.** Hands are ranked by a percentile of equity vs 1 plus equity vs 2 random hands,
which favours coordinated, suited hands. Unopened pots get a pot-sized raise if the hand is within
the position threshold × 1.3 (about 16% UTG to 39% BTN/SB), wider short-handed (HU button 70% deep,
85% at ≤12bb). Facing a raise: 3-bet the top 3.5% (7% vs loose raisers); call the top 12% (+5% in the
BB, + a pot-odds bonus); HU defend 55% and 3-bet 8%. Committed or ≤15bb: table equity minus a range
penalty (0.10 tight .. 0.03 loose raiser; 0.02 heads-up) against the required equity.

**After the flop.** MC equity against k ≤ 3 opponents (eq^(k/3) beyond 3). The bettor's range is the
top x of samples, ranked 60% by current-board strength and 40% by final strength. x is 0.45/0.36/0.28
by bet size, ×0.85 on the turn and ×0.7 on the river, ×0.6 vs a re-raise, ×1.5 vs aggressive
bettors, and ×1.4 heads-up (×1.2 3-handed). Pot-raise when range equity ≥ 0.68 (+ premium early);
call when it is ≥ required + 0.02; otherwise fold. Checked to: jam if SPR ≤ 1 and eq ≥ 0.45; bet
75–100% pot when equity vs the top 55% is ≥ 0.60; heads-up semi-bluffs and stabs.

**Short stacks and the points table.** At ≤12bb, open-raise pot with a wide range (28–45%, HU 85%).
Big calls with ≤4 players left use exact Malmuth–Harville ICM on the 100/60/40/25/15/10/5/0 points.
With ≥5 left, a survival premium (0.09 × fraction of stack risked, 0.08 with 4–5 left) is added to
the required equity and to the pot-raise threshold, which cut first-out finishes from 135 to ~100
per 1000.

**Opponents.** Per-seat VPIP, PFR, postflop aggression and fold rate (with priors) widen 3-bet/call
ranges vs loose raisers, widen the assumed betting range of aggressive bettors, and allow stabs vs
players who fold often.

**Last change** (013). Heads-up widening: committed-call range penalty 0.02 HU (≤0.05 3-handed) and
assumed betting range ×1.4 HU (×1.2 3-handed). Why: in T1–T4 we won only ~42% of heads-up finishes
(94–99 firsts vs 127–137 seconds). Test: own-versions field, HU win rate 56% vs 48–53% for 012
copies, points per top-3 table unchanged (67.8 vs 67.85); house bots, same seed, 60.13 vs 60.11
(per top-3 table 91.0 vs 89.4).

## T4 result (bot 012 = 010 code): rank 6/8, 30.30 (CI 28.5-32.1); weighted 302.66, rank 6
- Places 94/129/145/132/149/121/124/106; 0 timeouts. b05 34.3, b08 34.2, b06 33.3, b01 32.5.
- HU win rate across T1-T4 only ~42%; points per top-3 table 62.3 vs 66.7 for an average player
  (~1.6 pts/table lost in the endgame) -> 013 heads-up widening.
- Tip: changes that only act with <=k players left should be judged on points per top-k table
  (places k+1..8 are pure noise for them). work/diag.py prints the place counts.
- Rejected this window: PREM_MID 0.035 (smaller premium with 4-5 left): per top-5 table 46.0 vs 46.6;
  HU_VALUE (HU value bets vs top 75%, thr -0.02): HU win 45% vs 54-56%, 78.1 vs ~82 per top-2 table.
- Extra support for 013: per top-3 table, 013 copies 68.0 vs 65.2 avg for non-HU_WIDE versions (run 903)
  and 68.1 vs 66.1 (run 904). Stronger widening (HU x*1.7, pen 0; 3-handed x*1.3): 67.0 -> not better.
- House zoo same-seed checks 013 vs 012: seed 41 60.13 vs 60.11; seed 43 55.30 vs 55.22 -> no regression.
- Run 905 (maniac, minraiser, montecarlo + 2x013-ish, 2x012, 009): per top-3 table 013 65.8 vs 012 68.8.
  013 vs 012 over runs 903/904/905: +2.8, -0.5, -3.0 -> neutral on average (SE ~2 per top-3 table).
  For T6: check the real T5 HU win rate (1st/(1st+2nd)); if still ~42%, HU_WIDE didn't help -> revisit.
- Run 906 (4x013 incl. bot/, 3x012, 009; 450 tables): per top-3 013 65.9 vs 012 67.4; HU win 52% vs 49%.
  4-run average 013 - 012 per top-3 table: about -0.5 (noise). Kept 013 because the real-field HU
  weakness (42%) argues for it; if T5 HU win rate does not improve, resubmit 012 code for T6.

## T1 result (bot 006): rank 7/8, 30.89 pts/table (CI 29.1-32.7)
- Field is all TAG-ish: VPIP 22-27%, PFR 16-21%. Top: b05 36.3, b06 34.8, b01 34.5; b08 24.4 last.
- Ours: VPIP 21%, PFR 14% (tightest raiser in field); 1st place only 9.6% (avg 12.5%);
  places 96/137/144/139/139/118/115/112. 4 timeouts (max 1723 us), p99 500 us (others 100-200).
- results/T1/sample_hands.json: first 10 hands of 4 tables; our seat is not labelled (high-cpu seat).

## Patch window before T2
- Test field that mimics T1 better: localsim --opponents 7 of my own earlier submissions (TAG-like).
- OPEN_MULT 1.3 (wider opens): +1.1, +0.7 vs 006 copies -> 007-823786e0 (VPIP 25%, PFR 18-19%).
- BLUFF 1.6: +0.3 (noise) -> not used.
- Init warm-up (_warm: touch all lookup tables + run each equity path once in __init__, ~2-3 ms):
  same field/seed: max decision 2630 us / 2 timeouts -> 678 us / 0 timeouts. Decisions identical
  (warm-up doesn't use self.rng). -> 008-69d85973 (ACTIVE).
- BUT next run (same kind of field, seed 401) still had 6 timeouts, max 3693 us -> spikes are mostly
  machine-load driven (shared box during patch windows), warm-up is not a full fix. Real T1 rate was
  4 / 111k decisions (negligible points). If it grows: cut SAMPLES for kk=2/3 (heaviest paths).
- THREE_MULT 1.8 (3-bet top 6.3% instead of 3.5% vs single raise): -1.9, last place -> rejected.
- 008 vs house zoo: 58.28 +- 4.5 (300 tables), 0 timeouts, max 800 us -> no regression.
- CALL_MULT 1.2 (wider preflop flats): -0.8 vs 008 copies (800 tables) -> rejected.
- In the own-versions field all of 003..008 land within ~+-1.5 of each other over several runs;
  single-run leaders (e.g. 004 at 35.1 once) are noise. Real-field results are the better guide.

## T2 result (bot 008): rank 7/8, 29.61 (CI 27.8-31.5); weighted total 90.11, rank 6
- b05 36.6, b06 35.3 again on top with VPIP 24-25 / PFR 17 (same as ours now) -> gap is postflop/endgame.
- Our places 96/127/141/113/135/126/127/135: too many 6th-8th (39%) = early stack-offs. 6 timeouts.
- Own-versions field: 006 copies averaged ~0.6 above 007/008 copies over 5 runs (OPEN_MULT 1.3 doubtful).

## Patch window before T3
- STREET_X {flop 1.0, turn 0.85, river 0.7} (bettor range narrower on later streets): +0.1, +0.45.
- + PREM_EARLY 0.06 (required-equity premium base for big calls with >=6 alive, 0.05 with 4-5;
  pot-raise threshold 0.68 + premium when >=5 alive): +2.1, +1.4 vs 008 copies -> 009-6a80fad2 (ACTIVE).
- Timeouts still 1-2 per 900 local tables (machine load); not fixed.
- PREM_EARLY 0.09 (vs 0.06): +0.7, +0.5 vs 009 copies (small, both positive); house zoo 59.98
  -> 010-f9da6f2e (ACTIVE for T3).
- Info only: OPEN_MULT 1.0 on top of 010: 31.2 vs 010 copies 33.5/31.1 (-1.1) -> keep 1.3.
  Timeouts persist: 2 per 900 tables, max 3787 us (busy machine). Next idea: cut SAMPLES for kk=2/3.

## T3 result (bot 010): rank 6/8, 30.45 (CI 28.6-32.3); weighted total 181.44, rank 7
- Places 99/134/139/108/140/145/139/96: 8th dropped (135 -> 96, survival premium works) but 5th-7th
  rose; 1st still ~10%. b05 35.5, b08 34.5 (b08 improved every round), b06 32.4, b01 32.3.
- Real results by version: 006 30.89 (T1), 008 29.61 (T2), 010 30.45 (T3) -> all equal within noise;
  local "improvements" of +1..+2 have not shown up in the real field.

## Patch window before T4 (kept 010, no new submission)
- SHORT_BB 18 / COMMIT_BB 20 (wide short-stack mode up to 18bb, commit calls up to 20bb):
  +0.4, +0.8, then last place (29.9) in a 3x006 + 3x010 field -> rejected.
- 3x006 vs 3x010 direct: 006 avg 31.9, 010 avg 31.4 (noise) -> no revert.
- Machine is slower now: 600 tables take 85-150 s; keep runs <= 600 tables with timeout 170.
- SAMPLES {1:110, 2:72, 3:52} (was 130/90/66; ~20% less CPU per postflop decision): +0.95 vs 010
  copies, 0 timeouts (max 1012 us) in 600 tables -> 011-b276901c. Only change vs 010.
- BUT house zoo, same seed 37: 011 52.8 vs 010 59.3 (-6.5) -> noisier equity hurts (multiway pots).
  Reverted: resubmitted 010's exact code as 012-f9da6f2e (ACTIVE for T4). Keep SAMPLES 130/90/66.
- Lesson: check every candidate on BOTH the own-versions field and the house zoo (same seed as the
  active version) before submitting.

## Submissions
- 001-9e95458e: first working bot (MC equity, final-value range model).
- 002-39ae3674: + current-board range ranking (stops folding flop sets), ICM req_eq (<=4 alive),
  BB pot-odds defense bonus, low-SPR jam, wider short-handed opens.
- 003-56281829: + short-stack heads-up opens (HU button 85% when eff<=12bb, 70% deep; 3-handed +10%).
- 004-900da3d9: + heads-up/3-handed preflop defense (HU: call 55%/3-bet 8% vs single raise,
  call 25%/4-bet 4% vs 3-bet; 3-handed call +8%).
- 005-7ba16bca: + preflop percentile from e1+e2 blend (pf.json "q2" grid, weighted by class
  counts) instead of e1 only -> favours coordinated/suited hands for multiway pots.
- 006-2e1ccaae (ACTIVE, final of build phase): 005 with tighter bettor ranges
  X_SMALL/X_MID/X_BIG = 0.45/0.36/0.28 (was 0.5/0.4/0.32). +2.9 and +3.2 vs 005 copies on two seeds.

## Approach
- `bot/ev.py`: vectorised numpy PLO evaluator. 5-card hand = hole pair + board triple;
  value = LUT2[pair-rank-multiset*455 + triple-rank-multiset] (41k entries), flushes via FLV[13-bit mask]
  when pair suited and triple monotone in the same suit. Verified exact vs the engine ranker
  (work/test_ev.py). MC equity vs k<=3 random hands using a precomputed permutation bank of unseen-card
  indices. Also returns opponents' current-board values (flop/turn) for range ranking.
  ~0.15-0.35 ms per decision on the loaded machine; check_bot p99 ~500-740 us (busy box).
- `bot/pf.json`: preflop equity for all 16,432 suit-isomorphic 4-card classes (e1 vs 1 random, e2 vs 2)
  + percentile grid (work/pf_table.py, work/mk_pf.py).
- Preflop: unopened -> pot-raise if percentile <= threshold by players behind (12% UTG .. 30% BTN/SB),
  wider short-handed; eff <= 12bb: 28-45% (HU 85%). Facing a raise: 3-bet top 3.5% (7% vs loose
  raisers), call top 12% (+5% BB, + pot-odds bonus); HU much wider. Committed / eff <= 15bb:
  table equity minus range penalty (0.03 loose .. 0.10 tight raiser) vs ICM-required equity.
- Postflop: opponent range = top-x of MC samples ranked by 0.6*current-board rank + 0.4*final rank
  (river: final value). x = 0.5/0.4/0.32 by bet size, *0.6 vs re-raise, *1.5 vs aggressive bettors.
  Raise pot if eq_vs_range >= 0.68; call if >= required + 0.02; else fold. Checked to: jam if SPR<=1
  and eq>=0.45; bet 75-100% pot if eq vs top-55% >= 0.60 (0.62 river); semi-bluff/stab heads-up.
- ICM: exact Malmuth-Harville (bot/icm.py) for big calls when <= 4 alive; else pot odds + premium.
- Opponent stats per seat via observe(): VPIP, PFR, postflop raise/call/fold/check (with priors).

## Flags in bot/agent.py (current values = 013)
HU_WIDE True, STREET_X {1:1.0, 2:0.85, 3:0.7}, PREM_EARLY 0.09, SAMPLES {1:130, 2:90, 3:66},
OPEN_MULT 1.3, CALL_MULT 1.0, BLUFF 1.0, VALUE_THR 0.60, X 0.45/0.36/0.28, DEF_BONUS 1.0,
LOW_SPR_JAM True, STEAL False, RESAMPLE False, HU_FIX True, HU_DEF True, HU_CBET False, BLEND True.

## Testing
- work/diag.py <opps,comma> <tables> <seed>: per-entry points + place distribution (uses kit arena;
  dev only). Field used: 2x previous submission + older submission + montecarlo, pot_odds, nit, maniac.
  600 tables ~4 min; noise ~+-2.5 per entry (two identical copies differ by up to 4 points).
- Results (you vs copies of the previous version, same field):
  tighter ranges (x 0.45/0.36/0.27, no jam, no def bonus): -2 .. +0 (rejected)
  steal-widening vs low-VPIP + respect nit bets: -4.5 (rejected; noisy)
  aggressive (opens x1.2, bluff x1.5, value thr 0.57): -1.4 (rejected)
  resample MC in close big spots: -1.8 vs control (rejected; noisy)
  HU_FIX: +2.1, +0.9 (kept -> 003); HU_DEF: +0.7, +0.4, more 1st places (kept -> 004)
  HU_CBET (HU flop c-bet 60% as PF raiser): +2.2, -1.75 (rejected)
  BLEND (e1+e2 preflop percentile): +2.1, +0.7, more 1sts (kept -> 005)
  HU_E1 (e1-only percentile when 2 alive, on top of 005): +0.2 (not submitted)
  W2=1.5 (e1+1.5*e2 percentile): 0.0 (not submitted)
  X 0.45/0.36/0.28 on top of 005: +2.9, +3.2, more 1sts (kept -> 006)
  X 0.40/0.32/0.25 on top of 006: -0.8 (one seed, 450 tables; the two 006 copies differed by 6 pts) -> keep 006
- bot/ is identical to 006-2e1ccaae (= 005 agent.py with the X line changed).
- Note: on the 002 base, tighter X (0.45/0.36/0.27 + no jam + no def bonus) was ~-2; on the 005 base
  tighter X alone is +3. Interactions matter; always test against copies of the active submission.
- 005 vs house zoo (004 config): ~56.6 pts/table.
- Final checks of 006 (localsim): vs house zoo 58.97 +- 4.4 (300 tables, 0 timeouts/errors);
  field of 001..005 + nit + montecarlo (400 tables): 005 37.5, 006 36.1, 002 36.1, 003 34.4,
  004 34.1, 001 33.5 (all within +-3.4 noise). Kept 006 (two dedicated runs +2.9/+3.2 vs 005).
- diag 400 tables (006 vs 005, 004, 002 + montecarlo, pot_odds, nit, maniac): 006 45.5 (most 1sts: 93),
  005 43.9, 004 43.6, 002 41.3. Possible leak to check first in patch windows: 006 busted 7th in 34/400
  tables vs 15 for 005 (early stack-offs?) -> look at early-level big pots / LOW_SPR_JAM / BB defense.
  Re-check on a new seed (350 tables): 006 7th 20 vs 005 21 -> NOT confirmed (noise). Scores 006 43.8,
  005 43.4, 004 40.6, 002 44.6 (all within noise). Versions 002-006 are close; the real field decides.
- vs 7 maniacs: 65 pts/table; vs pot_odds/montecarlo field: 67.

## Known weaknesses
- MC noise (SE ~4-5%); range model heuristic; no blocker/nut-draw reasoning.
- Multiway (>3 opps) equity uses eq^(k/3).
- Postflop play is mostly position-agnostic.

## Next steps (patch windows)
- FIRST: timing. localsim vs maniac/minraiser/005 (300 tables) showed 1 timeout (max 1132 us, p99 500 us)
  on the loaded build machine. If real results show timeouts, cut SAMPLES (e.g. {1:110, 2:76, 3:56})
  or skip the current-board range pass when time.thread_time() - self.t0 is already high.
- Look at real results: if busting early -> tighten X / stack-off; if few 1sts -> more endgame aggression.
- Try weighting e2 more (e.g. e1 + 1.5*e2) or a separate heads-up percentile (e1 only) when HU.
- work/pf_backup.json = pf.json before the q2 grid was added.
- HU postflop c-bet frequency; steal more vs observed nits (needs more testing).
- work/v_* dirs were left by an interrupted command; unused.
