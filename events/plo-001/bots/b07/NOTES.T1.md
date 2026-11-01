# Team notes (b07, PLO)

FINAL active submission at end of build: **007-ea8beae4 (v10)** = v9 with RISK_BASE {3:0.06, 4:0.085, 5+:0.1}
(mid ICM premium): +3.3 vs v9 copies over 1000 tables (seed 111); confirmation seed 123: v10 41.76 vs
v9 avg 40.99 vs v8 39.92 (no regression). bot/ == v10.
v10 localsim zoo (300 tables, seed 5): 54.2 ± 4.8, 1st of 8 (nit 45.5, checkfold 42.5); max act 229 µs, 0 substitutions.
Note: survival-only bots (nit/checkfold) score well in house fields -> survival is valuable; ICM premium direction helped.
Patch candidate (NOT submitted): tools/var_risk = v10 with RISK_BASE {3:0.07,4:0.1,5:0.12}: 41.50 vs v10 39.77
(harness, 500 tables, seed 131, field v10x3+montecarlo+pot_odds+nit+maniac). Earlier vs v8: +2.5/-2.3/zoo -2.9 -> unproven.
Seed 141 (300 tables, threshold instead of pot_odds): var_risk 41.55 vs v10 44.22 -> net ~0; keep v10's RISK_BASE.
Previous: 006-2ebd8c31 (v9) = v8 + station targeting: if every opponent's
fold-to-bet rate < STATION_F 0.3, value-bet thresholds drop by STATION_THIN 0.06 and no flop c-bet bluff.
v9 vs v8 copies, 1000 tables each: +1.97 (seed 88), +0.12 (seed 99). Working copy bot/ == v9.
Fallback if v9 misbehaves: copy .submissions/005-1bf78c13/agent.py back into bot/.

## Approach
- `bot/agent.py`, numpy + stdlib. Exact Omaha evaluator: table V2[pair-rank-idx*2197 + triple-rank-idx]
  (canonical sorted rank indices) + SUITED[5-bit mask] for flushes. Verified 0 order mismatches vs engine.
- Postflop made-hand strength: enumerate every opponent 2-card combo from the live deck (numpy), take its
  best value on this board -> f = fraction of pairs beating us (+half ties). P(best vs one opp) = (1-f*m)^6,
  m = range multiplier from that opp's betting this hand: m = 1 + (0.1 + 1.6(1-aggr)^1.2)*min(k,3),
  k = 2 per raise this street, 1 per raise earlier street; m = 0.8 if they checked this street. Product over opps.
- Draws (flop/turn): bitmask flush outs (nut-weighted) + Omaha straight outs (exactly-2-hole rule), nut-checked.
  Flop uses two-card hit odds; eq = p_now*(1-vulnerability) + (1-p_now)*p_hit*0.92.
- Preflop: linear regression of equity-vs-random-hand on 58 hand features, fit on 2M MC matchups
  (tools/premc.py, tools/fit.py, weights W1 in agent). pct = percentile of (eq + small playability bonus).
  Open pot with pct >= 0.58-0.76 by position (HU 0.3, 3-handed 0.45, 4-handed 0.5); 3-bet >= 0.955;
  4-bet >= 0.985; all-in calls compare (eqr - range penalty)^(1+0.75(k-1)) with pot odds + ICM risk.
  Blind defence vs single raise at po<=0.4: DEF_HU 0.35, DEF_3 0.5, DEF_4 0.58.
- Opp stats per seat (observe): VPIP, PFR, postflop aggression, fold-to-bet.
  widen = min(0.3, (pfr-0.15)*0.5) loosens calls vs loose raisers.
- Bluffs: if P(all opps fold) (product of fold-to-bet rates, prior 0.5) >= 0.45 and <=2 opps: bet 0.6 pot with
  prob min(0.75,(F-0.3)*2.5). Plus 50% HU flop c-bet as preflop raiser, semi-bluff with >=8 outs.
- ICM risk premium on calls: RISK_BASE {3:0.05, 4:0.07, 5+:0.08} * min(1, call/stack) * (cover factor).
  (ICM breakeven for full-stack flip: 0.62 at 8 left, 0.605 at 4, 0.57 at 3, 0.5 HU.)

## Results (local harness $TMPDIR/harn.py: play_local_table with our seat random; and kit/localsim.py)
- v1 001: zoo 52.3. v2 002 (regression preflop): zoo 60.3. v4 003 (+bluff vs folders), v6 004 (+maniac-aware m),
  v8 005 (+ICM premium, checked-range, flop draw fix).
- 1000-table mixed field (seed 77): v8 copies avg 39.4, v6 38.2, v4 36.3, montecarlo 18.9, pot_odds 8.3.
- Tried and rejected (net negative/noise): stronger ICM premium {0.07,0.1,0.12}; thinner value (0.55/0.48);
  river bets weighted k=3; tighter early opens (UTG 0.8).
- Noise: 300-table runs have se ~1.9; single-run differences < 4-5 pts are not meaningful.

## Known weaknesses
- Range model is (1-f*m)^6 independence approximation; can still pay off non-nut straights on 4-flush rivers.
- Preflop equity is vs random hands (big pairs slightly overrated vs rundowns in multiway pots).
- No position use postflop; no showdown-based reads; no hand-cap (hand 200) special logic.

## Next steps (patch windows)
- Look at real tournament results: if we bust early a lot -> raise RISK_BASE; if we rarely win -> more aggression.
- Nut-awareness on river vs big bets (flush/straight boards), position-aware bluffing,
  targeted thin value vs stations (fold rate < 0.3).
