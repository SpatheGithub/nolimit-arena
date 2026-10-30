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

## T4 result (v10): rank 8/8, 29.78 pts; weighted total 305.57, rank 6
- Places: 95,125,140,149,121,107,114,149. Aggression factor fell each version:
  T1 2.59, T2 2.44, T3 2.27, T4 2.08 (v9/v10 call more vs c-bets/steals).
- Real-field score by version (SE ~1 each): v6 29.73, v8 32.15, v9 30.80, v10 29.78.
  Locally v8 ~= v9 ~= v10 (self-play can't separate them). Story consistent with data:
  tightening vs aggression (v7/v8) helped; loosening vs aggression (v9 CB_G, v10 BB defense)
  hurt in the real field (opponents' c-bets/steals are value-heavier than modeled).
- DECISION for T5: reverted to exact v8 code -> submission 011-1c93c812 (same hash as 008).
- Tested & rejected this window: ICM/linear-chip blend LAMBDA 0.3 (31.8) / 0.6 (31.2) vs
  v10 32.3 (versions/lam0.3, lam0.6; LAMBDA code not in active bot); estt (shove-range
  estimate x0.8 on v8): 32.8 vs v8 33.4; mtight (open range x0.75 instead of x0.9 at
  eff < 25bb): 32.4 vs v8 33.7; g8hi (v8 + GAM0 0.8, GAM1 1.0): 33.6 vs v8 32.8 (+0.8;
  earlier g_hi on v5 +0.4) -> consistently slightly positive but noise-level; candidate for T6
  (versions/g8hi). Third run (seed 561): g8hi 32.8 vs v8 31.5 (+1.3).
- FINAL for T5: v11 = v8 + GAM0 0.8 / GAM1 1.0 (stronger bet narrowing) -> submission
  012-a91fa626 (3 consistent local gains +0.7/+0.8/+1.3; fits "respect aggression" story).
  Snapshot versions/v11. Fallback: 011-1c93c812 (= exact v8).
  v11 vs zoo seed 71: 64.5 (v8 61.3, v10 64.4) -> no regression vs loose bots.
  v11 vs submissions (800 tables, seed 571): v11 34.2 avg (3 copies top 3), v8 32.9, v9 33.1,
  v10 31.8 -> 4th consistent gain for v11 over v8.
- v8 vs v10 locally: field with maniac+minraiser: v10 38.9 vs v8 36.2 (+2.75, minraiser
  min-raises every hand -> wider BB defense pays); field with only maniac: v10ncb (v10 with
  CB_G 1.0) 34.25, v8 34.26, v10 33.6 -> equal. Real field is TAG (PFR 14-21%) -> kept v8.
- If T5 (v8) again lands ~32 while T3/T4 were ~30, keep v8 for T6. If T5 is also ~30, the
  version differences were noise -> consider v10ncb/v10 (better vs loose bots: zoo +3).

## T3 result (v9): rank 6/8, 30.80 pts; weighted total 186.45, rank 5
- Places: 99,142,139,125,127,122,115,131. Across T1-T3 1st place = 79/116/99 (< 125 avg)
  while 2nd/3rd are above average -> we reach the end but don't convert heads-up.
- Diagnosis: at 16-30bb (not committed), BB defended only top 22% vs ANY min-raise, incl.
  HU SB steals (needs ~25% equity at 3:1 -> should defend ~55-70%); HU SB opened only ~52%.
- v10 = 010-5a924b1f (ACTIVE for T4): BB vs SB open (rnb<=1, no callers) callp 0.55
  (BVB_CALL), vs BTN open (rnb==2) 0.35 (BTN_CALL); heads-up SB open range 0.75 (HU_OPEN).
  Tests vs v9: +2.4 (seed 401), -0.3 (seed 411) -> +1.0 avg; adopted on theory (local field
  of tight self-copies underweights it). Snapshot versions/v10.
  v10 vs zoo seed 71: 64.4 (v9 61.4) -> wider defense also pays vs loose raisers.
- Rejected after v10 (neutral): hu2 (BVB 0.65, BTN 0.40, HU open 0.85, HU BB raise limps top
  30%): 35.4 vs v10 35.7; rsh (re-shove range over OUR open est*0.35 instead of 0.5): 31.7 vs 31.4.
- v10 diag by players left (versions/diag10, suffix 2 = heads-up, 3 = 3-4 players):
  M2 pf_allin_open_sd -1313 avg (n=95) vs M2 pf_allin_open +640 (n=153): heads-up 13-30bb
  all-ins that get called lose a lot; M2 post_sd -1009 (n=36). S3/M3 fine. Next: inspect
  heads-up 13-30bb play (SB open 2.2bb then call re-shove? BB 3-bet range QQ+/AK only).
- hupush (heads-up open-shove threshold 18bb instead of 13): 34.7 vs v10 35.9 -> rejected.
- hu3b (heads-up value 3-bet top 12% instead of QQ+/AK): 33.9 vs v10 34.1 -> rejected.
- v10 vs v9 across 7 shared local runs: +2.4,-0.3,+1.5,-2.6,+0.4,-0.15,-0.7 -> ~+0.1 (equal in
  self-play), +3.0 vs zoo. Kept v10 (theory: HU blind defense vs aggressive real opponents).

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
