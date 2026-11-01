# Team b08 notes (PLO, 8-max SNG, 1 ms/act)

## Submissions
- 001 template (safety). 002 first real bot. 003 bet-size-aware ranges + pair-score fix (zoo 50 -> 57).
- 004 pot-odds fix for tiny bets/all-ins + caller-range narrowing. 005 push_add=0.08 (wider short-stack pushes).
- 006 icm=0.03: ICM-style risk premium (+0.03 needed equity, x0.7 at 3-handed, x0.3 when we cover, 0 heads-up)
  on calls that risk a big part of the stack (runs: +2.3, +0.35, +1.1 vs v5).
- 007 low-SPR commit: spr_commit 1.3->1.8, commit_eq 0.42->0.35 (two runs: +1.3, +1.55 vs v6).

## Approach
- `bot/evalcore.py`: engine-identical 5-card evaluator (house `_common.py` Ranker, standard order).
- `bot/ranktab.npz` (`tools/precompute.py`, ~2 s): for every board rank-multiset of size 3/4/5 and every hole
  rank pair (91), best NON-flush value with exactly 2 hole + 3 board. Counting opponent 2-card combos that beat
  us is a numpy compare; flop/turn enumerate all rank runouts (91 / 13 river rows).
- `analyze()` -> equity vs one random 4-card hand: p = share of 2-card combos beating us, win ≈ (1-p)^6,
  averaged over runouts; flushes exact on the current board, probabilistic for the future (flush-draw nutness,
  opponent flush factor). ~100-170 us.
- Range model: eq_vs_range = eq ** (1/t); t = continuing fraction: blind 0.8, caller 0.55, raiser 0.45,
  x(0.75+0.3*aggr) per earlier-street raise, x0.85 per earlier-street call, current bet scaled by aggression
  and SOFTENED by bet size (small bets / short all-ins keep wide ranges). Multiway = product.
- Preflop: heuristic 4-card score -> percentile (6000 random hands sampled at import).
  `bot/preeq.npy` (`tools/preeq.py`, 2.5M MC matchups, 60 s): 20x20 all-in equity by hero/villain percentile
  bucket; used for push/fold call decisions (eq vs top-w range, x0.72 per extra player).
- Deep (>14 BB eff): position open ranges with pot raises, 3-bet top ~3.5%, percentile call thresholds.
  <=14 BB: push/fold (pot-raise max), opens widen with fewer players behind, push_add=0.08.
- Postflop: value raise eq_r>=0.72, call if eq_r >= pot odds (+0.02 unless odds<0.2, then 0.85*odds),
  bet if eq_r>=0.62, low-SPR commit, semi-bluff draws, c-bet/bluff by observed fold-vs-bet.

## Findings (localsim, 1000 tables, noise between identical copies ~±2)
- Tables NEVER reach the 200-hand cap (cap_survivals 0): ICM-at-cap irrelevant; places come from busts.
  Points sum is 255/table (avg 31.9).
- Wider pushes (+0.08) won ~+2 in three separate runs. pf_bb=18 worse (~-3). pf_bb=10, looser opens,
  more bluffs, tighter calls: no clear effect.
- Equity-matrix-priced preflop defense (calling more in BB/short-handed) was WORSE (~-2.7): keep tight.
- Biggest losses now are short-stack preflop coolers and +EV calls vs maniacs.

## Tools
- `tools/mkvar.py name key=val` copies bot to tools/vars/name with P overrides (for localsim --opponents).
- `tools/sim.py opps tables seed` place distributions; `tools/logsim.py opps tables seed N [maxbb]` prints our
  N biggest losing hands (optionally only postflop hands with bb <= maxbb).

## Known weaknesses / next
- ICM premium is a flat approximation; exact ICM (kit/icm.py, fast for <=5 players) for all-in calls/pushes
  is the principled next step.
- Preflop percentile is heuristic (rundowns slightly undervalued vs pairs); could rank by preeq-style MC.
- 4-card opponent approximated by 6 independent 2-card combos.
- Heads-up play uses generic thresholds; 1st vs 2nd is worth 40 points, worth a dedicated HU look
  (logsim filtered to 2 alive).
- Final regression check: v7 vs v6 copies 36.0 vs 35.6 (neutral/slightly positive).
- Place profile (600 tables, field v7x3/v6/v5/nit/montecarlo/maniac): ours ~15% 1st, 15% 2nd, 11% 3rd,
  12% 4th, 16% 5th, 15% 6th, 11% 7th, 3% 8th. ~42% of tables we bust 5th-7th; the nit never wins but
  scores 34 by landing 3rd/4th. Next test: larger risk premium / tighter calls when 5-7 players remain
  (mid levels, 10-25 BB), aiming to turn 5th-7th busts into 3rd-4th without losing 1sts.
- Tried icm_mid=0.04 (extra premium on at-risk calls with >=5 alive): +0.4 vs v7 (noise) -> not submitted;
  param left at 0.0 in bot/ (identical behaviour to 007). Bigger levers probably: steal/3-bet vs nits,
  postflop sizing vs calling stations, exact ICM.
- Nit-heavy field (3 nit, checkfold, threshold + 3 v7 copies, 600 tables): v7 copies ~51 each, nits ~26.
  We already exploit passive/tight bots well; gains must come from playing vs other strong bots (mirror).
- Cumulative check, v7 x4 (incl. working copy) vs v3 x3 + nit, 700 tables: v7 avg 32.6 vs v3 avg 31.7
  (+0.9, within noise). The v4-v7 tweaks are small; bigger structural changes are needed for real gains.
- Last accepted submission: 007-ace0e8bc.
