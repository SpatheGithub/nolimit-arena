# Team b05 notes

## Submissions
- 001-009c9341 v1: equity bot, no ICM.
- 002-d38072a9 v2: + ICM-based all-in decisions.
- 003-855203bb v3: + position-aware shove/open range estimates for opponents.
- 004-e18d82d7 v4: + fix (own raise was counted as an opponent in committed spots), limpers
  as potential callers in shove model, opp-adaptive open widening / bluff freq, faster eval.
- 005-dd9a8aa3 v5: + bet-based range narrowing postflop (biggest single gain).
- 006-af91acf8 v6 (ACTIVE): v5 + open range x1.25 when <=3 players behind (late-position
  steals). A/B vs v5 copies over 4 runs of 1000 tables: +1.5, -0.1 (with push85), +2.8 (tight
  field: 2 nits + threshold), +0.7 (mixed) -> ~+1.2 avg, never clearly negative.
- 007-37dbc30a v7 (ACTIVE for T2): v6 + opponent raise over OUR bet on the same street adds
  +1.0 to gamma (strong narrowing, RAISE_X), river bets +0.3 (RIVER_X), postflop ICM call check
  for calls >= 15% of stack (was 30%, ICM_FRAC). Local: neutral vs v6 copies (39.6 vs 39.5),
  zoo seed 71: 65.3 (v5 60.8).
- 008-1c93c812 v8 (ACTIVE for T2): v7 + tight3 deep 3-bet ranges: value 3-bet only QQ+/AK
  (pct<=0.012 or AKo=155/AKs=167), facing 3-bet+ jam only AA/KK (pct<=0.007), call QQ/JJ/AK
  if to_call <= 20% of stack. Tests vs v7: -0.8 (mixed w/ maniac), +1.1 (nit-heavy),
  +1.75 (TAG field v5/v6/v7, seed 251; all 3 tight3 copies top 3) -> adopted for tight T1-like field.
- Local snapshots in versions/v1..v7 + versions/tight3 (= v8).
- v8 vs zoo seed 71: 61.3 (v7 65.3, v5 60.8): tighter 3-bets cost a bit vs loose/maniac bots
  (they 3-bet light). If T2 field looks loose/aggressive, consider reverting the 3-bet part.

## T2 result (v8): rank 3/8, 32.15 pts (field 29.3-36.4); weighted total 94.04, rank 5
- Places: 116,137,127,149,115,122,116.5,117.5 (balanced now; 8th down from 135 to 117.5).
- Showdown win 49.1% (T1 47.5%), WTSD 5.4%. Leader b06 (VPIP 24/PFR 19), b02 (19/14).
- Sample hands T1+T2: preflop raiser c-bet 22 of 27 flops it acted on; 14/22 c-bets took
  the pot immediately (64% fold-to-cbet in this field).
- Patch tests before T3 (seed 301, 1000 tables, all variants in one field, all noise-level):
  cbB (flop c-bet by pf raiser read as gamma 0.5 instead of ~0.85-1.0 -> fold less to c-bets)
  32.8 vs v8 31.7; cbA (c-bet 85% HU + 45% 3-way) 31.5; cbAB 31.6. Confirmation run timed
  out (machine overloaded). Short re-run (400 tables, seed 311): cbB 34.5 vs v8 32.2 (+2.3)
  -> ADOPTED as v9 = 009-b8326b46 (ACTIVE for T3): CB_G = 0.5 (flop c-bet from preflop raiser,
  first bet of the flop, not over our bet -> gamma 0.5). CB1 = 0.55 (unchanged), CB2 = 0
  (no 3-way c-bets). Snapshot versions/v9.
- v9 vs zoo seed 71: 61.4 (v8 61.3) -> no regression. Referee timeouts so far: 0 (T1, T2).
- v9 vs earlier submissions (500 tables, seed 331): v9 34.7, 008 34.7/34.6, 006 33.7,
  007 32.4/30.4, 005 32.0 -> v8/v9 lineage on top; v9 ~= v8 here.
- cb75 (v9 + CB1 0.75) tested: 31.8 vs v9 33.9 (600 tables, seed 321) -> rejected.
  More c-betting does not help locally; keep CB1 0.55.
- Next ideas: tight3 part of v8 cost ~4 pts vs loose zoo bots (re-check vs field type);
  M-depth (13-30bb) open-then-fold leak; check T3 sample hands for big losses.

## T1 result (v6): rank 7/8, 29.73 pts (field 29.7-34.9, all within ~2 CI)
- Places 1st..8th: 79,129,164,157,147,92,97,135 -> too few wins, too many first-busts.
- Field is tight: VPIP 19-28%, PFR 14-22%; winner b02 is the tightest (19/14).
- Our WTSD 5.3%, showdown win 47.5% (low -> paying off). Sample hand: hand 8, called a river
  check-raise (195 -> 747) with 55 on TT board, lost 862. -> motivated v7.
- Patch-window tests (not adopted, neutral): PUSH_BB 16 on v7 (33.2 vs 33.2);
  tight3 = jam over 3-bet only AA/KK, call QQ/JJ/AK if <=20% stack, value 3-bet only QQ+/AK
  (versions/tight3): -0.8 in mixed field, +1.1 in nit-heavy field -> net ~0.
  NOTE: percentile ranking puts 88-TT above AKs/AKo, so 3-bet range (pct<=0.035) is pair-heavy
  and v7 jams JJ+ over 3-bets deep. Candidate for later if T2 shows early busts again.
- steal15 (late-position open x1.5 instead of x1.25): 32.2 vs v7 32.6 -> not adopted.
  Same run: v7 copies 32.6 avg > v5 31.2 > v6 29.3 (supports v7 over v6).
- Also neutral: push70 (push call-range model x0.7, chart cap 2.0): 33.2 vs v5 33.1.
- Baseline (800 tables, seed 181) v6 vs [005, 004, 003, nit, mc, maniac, pot_odds]:
  v6 47.2, 005 46.1, 003 42.3, 004 39.1, nit 36.0, others <16. No timeouts.

## Approach
- `bot/ev.py`: numpy-vectorized 7-card evaluator. Non-flush value via rank-key-sum lookup
  (`nf.npy`, 7.8M int32, SK keys, verified collision-free); flush via 13-bit mask table
  (`fl.npy`), flush suit per sample from a suit-count signature table (FSUIT52).
  Values = house Ranker encoding (category<<20 | kickers).
- Postflop equity: Monte Carlo with fixed pre-generated index samples (NS=140) vs up to 3
  opponents (extrapolated e^(n/3) beyond), exact enumeration on river heads-up (990 combos).
  Opponent hands weighted by (a) preflop range (percentile cutoff + floor) from their
  preflop action and observed PFR/VPIP, and (b) **bet narrowing**: if an opponent bet/raised
  this street, weight *= (final-strength rank + 0.05)^gamma, gamma = 0.5 + 0.7*min(bet/pot,1.5)
  (+0.6 per extra raise, +0.3 per earlier-street bet). Call if eq >= pot odds + 0.02.
- Preflop: percentile table (equity vs random) + 169x169 class-vs-class equity (`cvc.npy`)
  -> range_equity(c, top-p) via precomputed cumulative table (O(1)).
- ICM: `icm.npy` = expected points (n players, my chip fraction, others equal), from
  kit/icm.py. Used for: committed preflop spots (call/shove EV vs fold), small all-in calls,
  open-shove EV (per-player call-range model ci = (0.10+0.9/rbb [+0.08 BB, +0.03 SB]) *
  (0.7+vpip)), postflop calls >= 30% of stack. At 8 players a full-stack flip needs ~63%.
- Deep (>13bb eff): open 2.2-2.5bb by position (OPEN by players behind), 3-bet top 3.5%,
  call top 9-22%, set-mine pairs when cheap. <=13bb: push/fold (chart cap * ICM check).
- Opponent stats per table (hands, VPIP, PFR) from observe(); no cross-table memory.

## Results (localsim, noisy: identical bots differ by ~2-3 pts at 1000 tables)
- vs zoo: v1 48.9, v4 57.2, v5 60.8 (nit ~47) (600 tables, seed 71).
- v5 vs [v4 x3, v3, nit, mc, maniac]: 46.0 vs v4 copies ~36.7 (same seed v4-ish got 39.1).
- Tested neutral (not adopted): stronger gamma, call-narrowing, wider late steals (x1.25),
  looser push model (ci*0.85), PUSH_BB 16, re-shove up to 22bb, c-bet 40%, value thr
  0.55 (slightly worse) / 0.65 (neutral), wider BB defense (0.30) — all within +-1.5 pts.
- Diag tally (versions/diag5 instrumentation -> $TMPDIR/diag_*.txt): after v5, all postflop
  categories positive; remaining big negatives are blinds lost folding (normal) and
  called open-shoves at 13-30bb (net ~0 with steals).
- localsim on this loaded machine shows rare >1ms spikes (~1 timeout per 1000 tables).

## v6 leak diagnostic (250 tables, versions/diag6, avg chips/hand; D>=30bb, M 13-30, S<13)
- Positive: steals (pf_raise_raise D +99, M +232), open-shoves (S +404, M +386),
  all postflop showdown categories, called all-ins.
- Weakest: M pf_raise_fold -357 (n=229) and M pf_raise_call -259 (n=66): opening 2.2bb at
  13-30bb then folding to / flatting a 3-bet. Try open-shove or tighter opens at 13-20bb next.
- D post_nosd -40 (n=1907): failed c-bets/bluffs; cut flop c-bet frequency multiway/OOP.

## Known weaknesses
- Timing: postflop ~100us median, p99 ~300us, rare ~0.9ms spikes on the loaded machine.
- Opponent shove-calling ranges are modeled, not fitted. No multi-caller shove modeling.
- No check-raising / slowplay; c-bet bluff 55% * looseness factor, flop only.

## Next steps
- Use T1 results: if we bust early often -> tighten; if we blind out -> widen pushes.
- Consider tools/mkvar.py to make variants; tools/build*.py rebuild tables.
