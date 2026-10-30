# Team b06 notes

## Approach
- `bot/common.py` = copy of the house-bot helper lib (Ranker, Spot parser, `features()` postflop strength heuristic, preflop class/percentile tables).
- `bot/eqrange.json` = precomputed (tools/precompute.py, 500 MC samples/cell) all-in equity of each of 169 preflop classes vs a random hand from the top-p% range, p in 16 buckets.
- In-table opponent model per seat (reset every table, `self.st`): HANDS, VPIP, PFR, folds-to-preflop-raise, postflop bet/raise vs call/check counts, folds-to-postflop-bet, aggressive showdowns that were weak (bluff indicator). Estimates are shrunk to priors (VPIP .28, PFR .16, fold-to-raise .6, agg .35, fold-to-bet .45, bluffiness .25).
- Preflop unopened: open-raise threshold by #players behind (OPEN_TH x0.85), scaled by avg fold-to-raise of players behind; open any pct<=0.9 if P(all behind fold) >= 0.72. <=13bb: push table (PUSH_TH) OR model-based shove EV (fold rates behind, equity vs their calling range) > 0.05*risk.
- Preflop facing raise: raiser range = observed PFR (x2 if <=10bb, x1.5 if <=20bb, x0.4 for 3-bets), equity from eqrange. Value re-raise eq>=0.60. **Re-steal shove** (8-30bb, single open, no callers) when EV from opener's fold rate (-0.1) & players behind > 0.05*risk. Big win (+3). Committed spots = all-in pot-odds decision + ICM-ish margin 0.02+0.012*(n_alive-2) (x0.4 if we cover). Otherwise call by pot odds with realization (0.92 IP / 0.80 OOP) + implied odds for pairs/suited connectors deep; BB defense only pct<=0.5.
- Postflop: `features()` strength s. Value bet s>=0.62 HU / 0.70 multiway (-0.05 vs stations), c-bet frequency from opponents' fold-to-bet, IP bluff vs folders, semi-bluff draws. Facing bet: s + adj vs 0.22 + 0.95*pot_odds, where adj = (agg-.35)*.45 + (bluffiness-.25)*.4 + (vpip-.28)*.4 - 0.03*earlier streets the bettor bet, clamped [-0.18, 0.2]. Raise s>=0.86.

## Submissions
- 001-6589382b: v1 baseline.
- 002-3f5f4a81: v2 = ICM-ish margin, tighter opens (x0.85), BB defend pct<=0.5. +1.5 vs v1.
- 003-6a5b68ac: v3 = tightness (vpip) + barrel terms in facing-bet adj. +2.9 tight field, +1.2 self-play.
- 004-578c049b: v5 = model-based unopened shove EV + auto-steal vs folders. +1.4 mixed, +1.5 tight.
- 005-ab226160: v6 = re-steal shove EV. +2.9 self-play, +3.3 mixed, +0.8 tight. FINAL of build phase.
  Regression (800 tables, 2 copies each): v6 34.1, v5 32.0, v3 31.8, v1 29.6.
- T1 result (v6): rank 3/8, 33.95 pts (field 29.7-34.9, all TAG bots with VPIP 19-28%; leader b02 is the tightest at 19/14). Places 161/120/97/120/129/109/150/114: 7th+8th = 26%.
- 006-a56d8adb: v7 = v6 + STACKOFF guard: postflop, if to_call >= 35% of our stack and n_alive >= 5, need hs+draw >= 0.66 (hs includes bettor-aggression adj, so maniacs still get called). TAG-version field +3.8/+1.4/+2.4/+1.1/+0.7, self +1.25, mixed -0.3.
- 007-944c5788: v8 = v7 + OPEN_SCALE 0.75 (tighter opens). vs v7: TAG field +1.5/+1.1, self +0.6, mixed +2.3. ACTIVE for T2.
- Final T2-window localsim (400 tables, v8 vs 006/005x2/004/003/001 copies): v8 1st at 34.5. Single copies spread ±3, so the 005 vs 006 order there is noise.
- Place histogram, TAG field (600 tables), 1st to 8th. v8: 16.0/12.3/12.7/14.2/10.4/12.9/11.7/9.8 (35.5 pts). v6: 12.5/11.8/13.1/11.7/13.6/10.3/13.7/13.3 (31.5 pts). v8 cuts 7th+8th from 27% to 21.5% and wins more often.
- T2 result (v8): rank 1/8, 36.36 pts (b02 33.84 2nd). Places 178/139/86/115/141/115/128/98: 7th+8th = 22.6% (T1 26.4%). Weighted total rank 1.
- 008-4edd94fd: v9 = v8 + OPEN_SCALE 0.65. vs v8: TAG +1.1/+1.1, self -0.3/+0.2, mixed +2.6. ACTIVE for T3.
- Machine got heavily loaded late in the T3 window: a 600-table sim took >5 min and the shell killed it. In later windows use 200-300 tables per run, and give a bash call at most about 4 min of work.
- OPEN_SCALE .55 vs .65: TAG +1.9 (200 tables)/+0.0, self +0.8, mixed -3.9, so not adopted. Tightening has topped out around .65.
- On top of v9: HU/3-handed p_r floors TAG +1.0, self -1.5 (no). DECAY .99 TAG -1.4 (no).
- STACKOFF .62 vs .66 on v9: +1.3 (one TAG run, 400 tables). The same run had v9 31.6 vs single-copy v8 34.3, so this field is very noisy. Re-test STACKOFF .62 with 2+ runs before using it. Self-play: +0.4. So far +1.3/+0.4. Mixed field: -1.7. Overall neutral, keep .66.
- Untested next: preflop stack-off guard for 4-bet pots when n_alive >= 5. v8 vs v9 order flips between single-copy runs. The head-to-head with 2 copies each (400 tables) gave v9 35.1, v8 34.2, so v9 stays.
- T3 result (v9): rank 1/8, 34.94 (b04 34.07). Places 171/116/103/110/141/125/129/105. Weighted total 211.5, rank 1.
- Bust analysis (tools/dbg3, TAG field): at 5-8 players alive most busts are our own preflop shoves getting called (e.g. 5 alive: 29 shoves vs 12 calls), including re-steals with junk (92o, J2s).
- 009-907a27be: v10 = v9 + direct per-seat fold-to-3bet stat (F3_OPP/F3_FOLD: an earlier preflop raiser facing a later raise), prior 0.75 (weight 4), used for re-steal pricing instead of fold_to_raise-0.1. vs v9: TAG +2.5/+1.7/+0.9, self -0.4, mixed -0.8. With prior 0.6: TAG -3.1 (re-steals pay vs these fields). ACTIVE for T4.
  Confirmation runs vs v9: self +1.7, mixed +1.3, TAG +3.1. Overall 6/8 positive, avg about +1.2.
- Rejected on top of v10: SQUEEZE_MAX 2 (TAG -1.9, self -0.5), RESTEAL_BB 35 (+1.0/-0.85), F3_PRIOR .85 (TAG +2.5, self -1.2), PUSH_EV_MARGIN .10 (TAG -1.0, self -1.3), STACKOFF_N 6 (TAG -2.5, self +1.6), PUSH_TH[1] .75 HU (TAG -0.05, self -1.1), ICM_K .006 (TAG -2.6, self -0.7). ICM_K .012 sits at a local optimum (.02 and .022 were also neutral or worse). BARREL_K .05: TAG -0.5/+0.1/+0.1, self +1.6, mixed +2.0. Neutral in the TAG field (the closest proxy for the real field), small gains elsewhere. Low priority.
- TIGHT_K .6 vs .4: TAG +2.35, self -1.5. Inconsistent, low priority.
- Localsim v10 vs all earlier submissions (400 tables): v10 38.3, v8 36.0, v9 35.2, the rest 27.7-30.4. 0 errors.
- TAG-version field = 2 new + 2 old + v6/v5/v3/v1 copies from .submissions; best proxy for the real field.
- Rejected in T2 window: STACKOFF .72 (neutral), STACKOFF_N 4, STACKOFF_FRAC .25, ICM_K .02 (all neutral). OPEN_SCALE .65 vs .75: TAG +1.1, self -0.3, mixed +2.6, so not clear. Retry with more tables in a later window. RERAISE_EQ .64 vs .60: TAG -0.9 (keep .60). CALL_BASE .24 vs .22: TAG +1.05, self -0.2, so neutral overall. Low priority.
- Current bot/ has extra knobs (SQUEEZE_MAX, CALL_BASE, VTH_BASE, ADJ_CAP, ADJ_MULT, FLOOR_HU/3, LIMP_EV) whose defaults reproduce v6 exactly.

## Testing tools
- tools/sim.py N SEED name=dir ... : 8-entry tournament, prints per-group mean + place histogram (needs 8 entries; house names allowed).
- tools/mk.py SRC DST CONST=val : variant copy with module constants overridden.
- tools/dbg2 : instrumented copy that logs the actions of every hand where we bust to tools/bust.log.
- tools/shover : always-all-in test bot.
- Fields: self-play 4v4 (new vs old), mixed (2+2 + nit maniac montecarlo pot_odds), tight (2+2 + nit nit pot_odds threshold). Noise is about ±2 points at 500 tables, so only trust gains that repeat across fields.
- Tried and rejected (neutral or noise): ICM_K .022, OPEN_SCALE .7, PUSH_SCALE 1.25, PUSH_BB 16/17, RERAISE_EQ .56, stat DECAY .97, squeeze shove (SQUEEZE_MAX 2), CALL_BASE .26 (+2.5 self but -2.5 mixed), .30, .18, VTH .56, ADJ_CAP/MULT combo, HU/3-handed p_r floors, RESTEAL_BB 22/40, RESTEAL_MARGIN 0/.1, LIMP_EV, SHOVE3_K .7 (wider range for short re-shoves), DECAY .99, CBET_FRAC .35, PUSH_EV_MARGIN 0 (+0.8 self, -1.8 mixed).
- LIMP_EV re-tested: self -0.2, mixed +1.2 / -0.8, tight +1.0, so about +0.3 overall (noise). Worth another look if T1 shows a limp-heavy field.
- Final localsim vs earlier submissions (300 tables): current bot/v6 copies about 33.3, 003 about 31.2, 001 about 29.6.

## Where v6 loses points (300 tables vs full house zoo: v6 58.2, nit 50.9)
- Places for v6, 1st to 8th: 42.0 / 8.3 / 12.3 / 14.3 / 13.7 / 5.7 / 2.3 / 1.3 %. The nit's: 5 / 53 / 29 / 6 / ... %.
- The leak is the 4th-5th cluster (28%), busting from all-in confrontations in mid-game. When we survive, we usually win: we take 1st far more often than 2nd. A patch that cuts mid-game busts without cutting 1st-place rate is worth the most.

- Head-to-head in a zoo-like field (v6, v1, nit, maniac, montecarlo, pot_odds, checkfold, random; 400 tables): v6 49.6, nit 46.2, v1 42.1. Single-bot zoo runs swing ±5 between seeds, so always compare versions at the same tables.

## Known weaknesses
- Busts 5th-7th in ~25-30% of tables (all-in coinflips taken on chip-EV); the house nit reaches top 3 more often, though it almost never wins.
- No real ICM; postflop strength is a heuristic, not equity vs range.
- Opponent stats are cumulative (no recency), and the PFR used for a short-handed raiser lags.

## Next steps (patch windows)
- Check the T2 place histogram: did 7th+8th drop from 26%? If so, consider more stack-off caution (e.g. also preflop 4-bet pots when n_alive >= 5).
- Look at T1 results: if we bust early a lot, raise ICM_K; if the field is passive, try CALL_BASE .26.
- EV-based open-raise sizing at 13-25bb (open-shove vs raise/fold).
- Per-position or first-in raise frequency for better steal-range estimates.
