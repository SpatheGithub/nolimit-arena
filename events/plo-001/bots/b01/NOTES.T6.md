# Team b01 notes (PLO, 8-max SNG, 1 ms/act)

## Strategy

Bot for T6: **015-2fe717d6** (same code as 013-2fe717d6: the T1 bot 005/012 + wider heads-up
defense).

**Summary.** Math-first tight-aggressive PLO bot. An exact table-driven evaluator (2 hole +
3 board) measures how many possible opponent hands beat ours; a precomputed equity table ranks
starting hands; simple per-opponent stats adjust calls, bluffs and steals. Every decision is
lookups plus arithmetic (median ~50 us, max well under 1 ms).

**Before the flop.** Hand percentile comes from a 16k-class equity table (Monte Carlo, 640
trials per class; blend of equity vs 1 and vs 3 random hands). Open-raise pot when the hand is
inside a threshold that depends on how many players act behind (13% UTG to 38% SB, x1.35
overall, wider short-handed and heads-up). Thresholds x0.55 while the big blind is <= 40
(levels 1-2) to avoid deep-stack early busts. 3-bet top ~3.5% (wider vs frequent raisers); call
raises with top ~16-30% depending on position/price, widened vs loose raisers. Heads-up, facing
a raise we call with at least the top 65% and 3-bet at least the top 12%.

**After the flop.** Strength = exact fraction of unseen 2-card combos that beat our made hand,
turned into P(random opponent hand not ahead) = (1-f)^6, plus straight/flush draw outs.
Facing a bet we raise to pot with trips+ that are very likely ahead, call when estimated
equity vs the bettor's (stronger-than-random) range beats the pot odds, otherwise fold. One
pair and board-paired two pair are discounted vs passive bettors. Betting: value-bet pot or
3/4 pot when well ahead of the field, semi-bluff big draws, c-bet heads-up 55% as the
preflop raiser, and bluff opponents whose observed fold-to-bet rate is high.

**Short stacks and the points table.** When calling would commit about a third of our stack or
more, we switch to an all-in equity model: our equity vs the raiser's estimated range (from
their observed raise frequency) must beat the price plus a small survival premium (4%, +2%
with <= 4 players). Exact-ICM calling and bigger premiums were tested and lost points (fewer
wins), so the bot accepts variance: the points table pays 100 for 1st vs 60 for 2nd.

**Opponents.** observe() tracks per seat: hands, VPIP, PFR, postflop bets vs checks/calls,
and fold-to-bet. Uses: tighter calls vs passive bettors, looser vs aggressive ones; wider
3-bets/calls vs frequent raisers; wider steals when the players behind rarely play; bluffs
when the opponents' product of fold-to-bet >= 0.5.

**Last change.** For T6 nothing changed in play: an early stack-off guard (levels 1-2: fold
to bets committing 40%+ of the stack unless ahead_vs >= 0.75 or draw equity >= 0.35) was
submitted as 014, then withdrawn. Against 013 over 5 local runs x 2 copies it scored +1.4,
+3.3, -3.0, +0.5, -1.9 points/table (mean +0.04; TAG-field mean -0.55), so it was not
demonstrably better and 013 was resubmitted. T5 (013): 31.77, rank 5, about level with the
field. Earlier changes: (1) Reverted to the T1 bot. Real tournaments, points relative to the six other
established teams: T1 (this bot) +1.81, T2 (tighter preflop) +0.38, T3 (tighter + 75% c-bet)
+0.89, T4 (this bot + 95% c-bet) +1.07. Tighter versions won fewer tables (1sts 180/156/133);
the 95% c-bet did not beat 55%. (2) Wider heads-up defense (call >= top 65%, 3-bet >= top 12%
when facing a raise heads-up), because heads-up conversion fell to 54% in T4 (63% in T1).
Local test, 4 runs x 2 copies: heads-up win rate 55.6% (535/962) vs 50.1% (507/1011) for the
T1 bot, +5.5% +- 2.2%; points per table -1.8 / +0.1 / +0.3 / +0.4 (noise). A no-barrel rule was also
tested and rejected (-1.65).

## T5 result (bot 013): rank 5/8, 31.77 (b05 35.98, b06 32.73, b08 32.23, b04 31.89)
- Places 154/100/91/127/110/122/136/160; HU conversion 60.6% (T4 53.6%, T1 62.9%).
  Relative to comparable teams -0.06 (history +1.81, +0.38, +0.89, +1.07, -0.06): all my
  versions are within noise of each other in the real field.
- Patch before T6: early stack-off guard (014) tested 5 runs, mean +0.04 -> withdrawn;
  013 code resubmitted as 015-2fe717d6 (ACTIVE for T6).

## T4 result (bot 011): rank 4/8, 32.46 (b05 34.28, b08 34.22, b06 33.29, b02 31.09)
- Places 150/130/91/111/91/118/140/169 (many first-busts). VPIP 21.8% PFR 16.2%. Relative to
  comparable teams +1.07 (T1 v5 +1.81, T2 +0.38, T3 +0.89).
- Patch before T5: reverted to v5 exactly -> 012-76ffb41e.
- HU widening test (variants/hu: n_alive<=2 -> call_th >= 0.65, 3-bet >= 0.12): HU win rate
  mixed field 60.8% vs v5 53.0%; TAG field 50.0% vs 51.0%; pooled +3.9% +- 3.2%. Points neutral.
  Aggressive house field: 55.2% vs 48.2% (+0.3 pts). Pooled 3 fields: +5.0% +- 2.5% ->
  ADOPTED as 013-2fe717d6 (active for T5). Revert = resubmit 012 (only diff: 3 lines).
- Stronger HU widening (call >= 0.75, 3-bet >= 0.15, variants/hu2) vs 013: HU win rate 53.7% vs
  61.1%, pts 36.7 vs 38.6 -> 013's 0.65/0.12 is better. Not adopted.
- 2nd TAG run (seed 106): 013-style HU win 55.0% vs v5 47.9%, pts 32.7 vs 32.3. Pooled 4 runs:
  55.6% (535/962) vs 50.1% (507/1011), +5.5% +- 2.2% (~2.5 sigma); points within noise.
- 3-handed widening on top of 013 (n_alive==3: call >= 0.45, 3-bet >= 0.08, variants/h3):
  P(top2 | top3) 75.1% vs 80.1%, pts 38.0 vs 38.3 -> rejected.
- Milder HU widening (0.55/0.10, variants/hum) vs 013: HU win 56.1% vs 55.9%, pts 38.6 vs 40.5
  -> 013's 0.65/0.12 sits between two worse settings (0.55 and 0.75). Keep.

## T1 result (bot 005): rank 3/8, 34.49 pts/table (b05 36.26, b06 34.81; b08 last 24.43)
- Places 1st 180, 2nd 106, 3rd 102, 4th 102, 5th 110, 6th 110, 7th 150, 8th 140 -> too many
  early busts (29% 7th/8th). Showdown win 48.6% (sims vs house: 55-59%). 0 subs, p99 200us.
- Field VPIP 21-37%, PFR 14-21%: TAG-like. sample_hands.json = first 10 hands of 4 tables only.
- Best proxy field: my own versions (v1..v6 + 002/001), sdw ~0.50 like T1.

## T2 result (bot 008): rank 3/8, 32.34 (b05 36.60, b06 35.26, b02 31.02, b08 30.87 (+6.4 vs T1))
- Places 1st 156, 2nd 99, 3rd 78, 4th 143, 5th 139, 6th 139, 7th 127, 8th 119. VPIP 19% PFR 13%
  (T1: 22/16; top teams 24-25/17). Fewer early busts but fewer wins, and 30% bust-4th once in
  the final 4 (T1: 21%). Most teams lost 1.3-1.9 pts to b08's improvement, so v8 vs v5 in the
  real field is roughly a wash (-0.5 +- 2).
## T3 result (bot 009): rank 4/8, 32.27 (b05 35.54, b08 34.47, b06 32.40, b02 30.86)
- Places 133/115/117/133/146/131/113/112 (nearly uniform). VPIP 18.4% PFR 13.2% = tightest in
  field (top teams 23-26% / 17%). 1sts fell 180 (T1, v5) -> 156 (T2, v8) -> 133 (T3, v9).
- Relative to the 6 comparable teams (excluding b08): v5 +1.81, v8 +0.38, v9 +0.89.
  Real field rewards the looser v5 style; local proxies (my own versions) favored tighter.
  Trusting the real field for style questions.
- 1 "hang": wall 103 ms with cpu 0.72 ms -> machine scheduling, not our code. cpu_max 717us.
## Patch before T4 -> 011-2de5bef5 (ACTIVE) = v5 (005) with CBET 0.95
- Real-field sample hands T1-T3: HU flop c-bets by the preflop raiser were folded 11/19 (58%),
  called 8, raised 0 -> half-pot c-bets with any hand are +EV vs this field. Local: CBET 0.95
  vs 0.75 on v10 +0.75 (noise). 010-5adc1c89 was the same with CBET 0.75.
- Aggressive house field (maniac, minraiser, pot_odds, montecarlo): v11 43.6 vs v9 48.1 on seed
  93, but v11 47.5 on seed 94 (same field) -> noise +-4. Adaptive c-bet (0.35 vs opp with
  fold-to-bet < 0.3, variants/v12): 43.9 vs v11 47.5 -> rejected.
- TAG proxy seed 95: v9 33.9, v11 32.4, v10 32.0 (local proxy still prefers the tight v9 by
  ~1.5; real field preferred v5-style). Decide T5 patch from T4 result: if T4 (v11) scores
  better than T2/T3 relative to the field, keep; else go back to 009.
- v11 vs zoo (seed 47, 200 t): 55.8 (1st). 2 "hangs" locally with cpu max 487us -> wall-clock
  stalls from the shared busy machine, same as T3's single hang; not a code issue.
- Mixed seed 96 (330 t): v11 39.1, v5 39.4, v9 36.9 -> c-bet 0.95 ~neutral vs v5 locally.
## (superseded) 010-5adc1c89 = v5 (005) with CBET 0.75
- Reverted EARLY_BB 80 -> 40 and removed the adaptive open tightening (both were tightening
  preflop). Kept CBET 0.75 (postflop). Local mixed test: v9 35.7, v10b (no adaptive) 34.7,
  v10 33.8 (local proxy keeps favoring tight; ignored in favor of real-field evidence).
- Timing (variants/timing.py, 4000 random postflop spots incl. flush boards): median ~106us,
  p99 ~210us on this busy machine; slowest spots repeat at 130-175us, so the rare 500-700us
  maxima are GC/scheduling spikes, not code paths. No change.

## Patch before T3 -> 009-801a9db8 (ACTIVE for T3) = 008 with CBET 0.55 -> 0.75
- c-bet 0.75 (HU flop, as preflop aggressor): TAG field +2.4 (v8 base) and +1.2 (v6 base);
  mixed field -0.7 (noise). T1/T2 fields are TAG-like and T2 suggested we were too passive.
  If T3 regresses, revert to 008 (only diff: CBET line).
  Confirmation TAG seed 85: v9 33.9 vs v8 32.8 (+1.1). Tally TAG: +2.4, +1.2, +1.1; mixed -0.7;
  house+maniac field (280 t): v9 43.4 vs v8 42.6 (+0.8).
- Local re-tests: mixed field v8 40.9 vs v5 39.4; TAG field v8 34.9 vs v5 32.0 -> keep v8.
- Not adopted: SH_OPEN 1.6/SH_3B 0.09/SH_CALL 0.10 short-handed loosening (neutral, more 1sts
  but more 4ths); EARLY_BB back to 40 on v8 (-1.7); exact ICM need-equity for preflop commits
  at <=5 players (ICM_EXACT, code in variants/icx): -3.4 (fewer wins) -> ICM caution keeps losing
  locally. Parameters SH_* exist in variants only (bot/ == 008).
- Wider steals at bb>=320 (open th x1.25, variants/late): mixed +0.9, TAG -1.3 -> net ~0, not
  adopted.
- Short-handed (n_alive<=4) params: looser sh1 (1.6/0.09/0.10) TAG -3.6; tighter sht
  (1.1/0.045/0.0) TAG -3.0 -> v8's 1.3/0.06/0.05 is a local optimum. Leave it.
- ICM_PREM 0.0 on v8: TAG 31.4 vs v8 35.4 (-4.0); exact ICM (tighter) -3.4 mixed -> 0.04 is
  a local optimum too. v8 now looks locally optimal on every knob tried; next windows should
  look for structural gains (e.g., postflop multiway, bet sizing) rather than these params.
- VAL_TH 0.72 (thinner value bets) TAG: 32.7 vs v8 31.9 (+0.9, noise); mixed: 37.8 vs v8
  40.8 (-3.0) -> rejected.

## Patch before T2
- 006-c3f26654: EARLY_BB 40 -> 80 (early tightness through level 3). TAG field: +2.6 over v5
  (3 copies over 2 seeds, ~2.6 sigma); house field: identical to v5. ACTIVE for T2.
- Tested, not adopted: NO_BARREL (no exploit bluff after opp called postflop) neutral;
  ICM_PREM 0.08 neutral; POST_PREM 0.04 worse; EARLY_BB 160 tie; EARLY_F 0.45 / EARLY_K 0.9 /
  CALL_MULT 1.1 / CBET 0.75 / K_BASE 1.9 within noise; OPEN_MULT 1.15: +2.4 TAG field but -3.3
  vs house bots (not robust) -> kept 1.35. Candidate for later if field stays TAG-like.
- 007-c5a030d6 (ACTIVE): v6 + ADAPTIVE open tightening: once every opponent has >=12 hands
  observed and their avg VPIP is in [0.15, 0.35] (TAG table), open threshold x 1.15/1.35.
  TAG field: 35.3 vs v6 31.2 (+4.1); house field: 44.3 vs v6 42.5 (+1.8). Robust in both.
  BUT maniac-heavy field: v7 43.2 vs v6 46.3 (-3.1): after maniacs bust, the remaining avg
  VPIP falls into the band and v7 tightened short-handed.
- 008-3c0eb52f (h_ad5, ACTIVE): same rule only when n_alive >= 5. Aggressive field: 44.5 vs v6 45.7 (-1.2,
  noise); TAG field: 34.7 vs v7 30.5 vs v6 31.6. Submitted as the active bot for the next T.
- Factor 1.0/1.35 instead of 1.15/1.35: +0.7 vs v7 (noise), not adopted.
- v8 house field (300 tables, 2 copies each): v8 40.8 vs v6 42.5 (-1.7, noise; 007's version
  was +1.8 there). Next patch: if v8's result disappoints, compare 006 vs 008 again with
  more tables; the adaptive rule's value depends on the field being TAG-like.
- TAG field seed 68 (280 tables): v8 31.3 vs v6 32.4 (-1.1, noise +-4). Adaptive-rule tally vs
  v6 in TAG fields over 4 runs: +4.1, +5.5, +3.1, -1.1 (avg ~+2.9); house +1.8/-1.7;
  aggressive -3.1 (v7) / -1.2 (v8). Net: keep 008 unless the next T's results say otherwise.

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
