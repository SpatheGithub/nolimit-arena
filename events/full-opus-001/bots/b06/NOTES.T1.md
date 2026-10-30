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
- Look at T1 results: if we bust early a lot, raise ICM_K; if the field is passive, try CALL_BASE .26.
- EV-based open-raise sizing at 13-25bb (open-shove vs raise/fold).
- Per-position or first-in raise frequency for better steal-range estimates.
