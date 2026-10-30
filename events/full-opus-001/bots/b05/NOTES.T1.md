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
- Local snapshots in versions/v1..v6 (use as localsim opponents).
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
