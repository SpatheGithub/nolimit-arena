# Team notes (b03, PLO)

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

## Flags in bot/agent.py (current values = 006)
OPEN_MULT 1.0, CALL_MULT 1.0, BLUFF 1.0, VALUE_THR 0.60, X 0.45/0.36/0.28, DEF_BONUS 1.0,
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
