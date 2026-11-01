# Team b01 notes (PLO, 8-max SNG, 1 ms/act)

## Submissions
- 001-ee47171e v1 heuristic preflop + exact postflop strength.
- 002-86a9c34b + precomputed preflop equity table (bot/pre_eq.json), opp modeling (aggr/PFR).
- 003-19ecb52d + fold-to-bet exploit bluffs, steal widening vs low-VPIP players behind.
- 004-5c0ff0db + EARLY tightness (bb<=40: open/call thresholds x0.55, postflop k +0.6). ~+2.5 pts.
- 005-76ffb41e + one-pair / board-paired-two-pair discount when facing bets, scaled by the
  bettor's observed aggression (full discount vs passive bettors, none vs af>=0.5). CURRENT BEST.
  (bot/ == .submissions/005 as of the end of the build phase)

## Approach
- Own table-driven evaluator (RT rank-key sums, FT flush masks); PLO best = max over 6 hole
  pairs x C(board,3). Verified 0 mismatches vs kit fasteval.
- Postflop: `beat_fraction` = exact fraction of unseen 2-card combos beating my made hand;
  ahead1=(1-bf)^6 ~ P(random 4-card hand not ahead). Draw outs from rank masks (straights) and
  flush outs (nut flag). Facing bets: ahead_vs = ahead1^(k*...) with k from bet size, #raises,
  bettor aggression (observed), early-stage bonus; weak-pair discount. Call if eq_vs >= need*1.05.
  Raise max with cat>=3 and ahead_vs>=0.7. Bets: value if ahead1^n>=0.8 (cat>=2), semi-bluff
  draws, c-bet HU 55%, exploit bluff 0.6 pot when product of opponents' fold-to-bet >= 0.5.
- Preflop: percentile from equity table (blend of eq vs 1 random and vs 3 random hands,
  640 MC trials/class, canonical suit-permutation key, variants/pre_eq*.py). Opens by #players
  behind x OPEN_MULT, 3-bet top ~3.5% (widened vs loose raisers); commit decisions
  (to_call >= 35% stack) use eq = 0.5 + 0.9*(eq1_me - avg eq1 of raiser's top-R range),
  R from observed PFR, + ICM premium 0.04.
- Opponent stats in observe(): hands, vpip, pfr, postflop aggr/passive, fold-to-bet.

## Key parameters (top of agent.py)
OPEN_MULT 1.35, CALL_MULT 1.3, K_BASE 1.6, CBET 0.55, VAL_TH 0.80, ICM_PREM 0.04,
EQ_SCALE 0.9, W1 0.5, EXPLOIT 1, EARLY_F 0.55, EARLY_K 0.6, EARLY_BB 40, SPR_COMMIT 0,
POST_PREM 0, WEAK_PAIR 0.4, WEAK_2P 0.7.

## Testing (variants/run.py = localsim with place distributions; variants/mk.py NAME K=V makes
## a variant dir; variants/dbg + variants/run_dbg.py logs big losing hands)
- Noise: identical bots differ by up to 4 pts at 450 tables. Only >3pt effects are visible.
- No table reached the 200-hand cap in sims; places come from busts.
- nit/checkfold score 30-40 just by surviving while active bots bust each other -> early
  tightness helped. My bots finish 5th-8th in ~45% of tables; 1st ~20%.
- Tried, no gain: CBET 0.3/0.8, ICM_PREM 0.08 (worse), postflop all-in risk premium (worse),
  SPR commit rule, looser (OPEN 1.7) or tighter (1.0) opens (both worse), EARLY_F 0.35/0.45,
  EARLY_BB 80, K_BASE 1.3/1.9, restricting exploit bluffs to flop/turn + size cap (worse),
  stronger weak-pair discount 0.25 (worse), unconditional weak-pair discount (worse vs bluffers).
- ICM math (kit/icm.py): stack-for-stack flip with equal stacks needs ~61-62% equity with 4-8
  left (57% with 3). Flat premiums tested worse in sims though; exact ICM costs 0.78ms at 8p.
- Big-loss log patterns: one pair called down vs sets (fixed in v5); exploit bluffs
  triple-barrelling into callers (restriction tested worse overall); 2nd-nut flush coolers.

## Final large runs (1000 tables)
- v5,v4,v5,v4,nit,pot_odds,montecarlo,threshold: v5 avg 44.1, v4 avg 44.2 (tie), nit 40.3.
- v5,v3,v2,v1,nit,montecarlo,pot_odds,v5: v5 avg 40.2, v3 39.8, v2 37.2, v1 36.8, nit 36.0.
  v5 places: 1st 21%, 2nd 13%, 3rd 9%, 4th 13%, 5th 16%, 6th 14%, 7th 8%, 8th 5%.
- VSHORT (open wider at <5bb) tested: no gain; not in v5.
- STATION exploit (HU thin value bet 0.6 pot with cat>=2 & ahead1>=0.65 and no c-bet vs
  opponents with fold-to-bet < 0.3 over >=4 samples): -0.9 vs v5 in a pot_odds-heavy field
  (noise); not in v5.
- Exploit bluff threshold fp>=0.42 (vs 0.5): 1000 tables, identical to v5 (38.76 vs 38.77).
- v5 vs zoo (400 tables): 54.4 pts/table (nit 47.0, checkfold 42.5); max act 278 us, 0 subs.
- Nit-heavy field (v5 x2, nit x3, checkfold, m_loose, m_tight; 450 tables): all my versions
  ~37-40; places are bimodal (1st/2nd or 7th/8th) because the active bots knock each other out
  while the nits wait. Patch idea: when most of the table is tight (low VPIP), stop widening
  calls vs loose raisers (PFR_W) and add ICM premium vs other active bots; keep stealing vs nits.
  -> Tested "no PFR widening when others' avg VPIP < 0.2" (variants/tt): 38.9 vs v5 40.9, no gain.
- EARLY_K 1.0 (vs 0.6), 2 seeds x 450 tables x 2 copies: 38.86 vs v5 38.77 -> tie, not adopted.
- Note: v3 (looser, no early-tightness) sometimes tops a run (41.4 on seed 41); differences
  between v3/v4/v5 are within ~2 pts. Field composition matters more than these tweaks.
- Aggressive field (v5 x2, maniac x2, minraiser, montecarlo, v3, v4; 400 tables): v5 avg 44.0,
  v3 45.3, v4 43.8, maniacs 13-14. v5 busts 7th/8th less, but v3 wins 1st more. If T1 shows
  the real field is loose/aggressive, consider raising EARLY_F back toward 1.0 (v3-like).
- Mirror check (v5 vs 7 copies, 250 tables): 0 timeouts/errors/illegal, max act 236 us.
- ICM_PREM 0.0 (vs 0.04), 400 tables x 2 copies: 37.7 vs v5 38.6 -> keep 0.04.
- Recheck seed 45 (350 tables): v5 avg 39.8, 002 40.0, 003 38.5, 001 35.6, nit 36.7.
- Zoo seed 46 (200 tables): v5 56.5 (1st), nit 45.2, checkfold 42.5; 0 substitutions.

## Known weaknesses / next steps
- Exploit bluffs can barrel off stacks vs calling stations: maybe stop river bluff if the
  target's fold-to-bet sample is from flop only, or cap by stack only when target VPIP high.
- No exact ICM in decisions; could use exact icm for <=5 players (0.06 ms).
- HU play is generic (1st vs 2nd = 40 pts).
- If T1 results show many busts: raise EARLY_F/ICM; if few 1sts: loosen OPEN_MULT.
