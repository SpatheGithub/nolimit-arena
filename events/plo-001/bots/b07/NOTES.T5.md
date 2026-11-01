# Team notes (b07, PLO)

## Strategy

Bot for T5: **v16, submission 012-0b31cbc6** (`bot/agent.py`, numpy + stdlib, ~50 µs median per decision).

**Summary.** Tight-aggressive pot-limit Omaha bot. Exact table-driven Omaha evaluator (verified identical
ordering to the engine), postflop hand strength from enumerating every opponent two-card holding on the
current board, opponent ranges narrowed by their betting, per-seat opponent stats, and an ICM risk premium
on chip-risking decisions.

**Before the flop.** Hand score = linear regression of equity vs a random hand on 58 hand features (pairs,
suits, connectivity, danglers), fit offline on 2M Monte Carlo matchups; percentile adds a small bonus for
rundowns and double-suited hands. Open pot-size or fold (no open limps): thresholds 0.58-0.76 percentile by
position at full tables, 0.3 heads-up, 0.45 three-handed, 0.5 four-handed. Facing one raise: call >= 0.84,
3-bet >= 0.955 (widened against loose raisers by their PFR). Facing a 3-bet or more: re-raise only with AA
(or under 25 bb); range penalty grows when we hold no ace (re-raise ranges are AA-heavy). Blind defence at
good prices with short-handed thresholds.

**After the flop.** f = fraction of live opponent two-card combos that beat our hand (+half ties).
P(a random 4-card hand beats us) = 1-(1-f)^6. Each opponent's range is narrowed by their raises this hand
(lead bet keeps top 55%, re-raise top 20%, earlier streets 70%/45%, wider for aggressive players);
P(beaten) = that probability / range fraction; product over opponents. Draws: nut-weighted flush outs and
exact-two-hole-card straight outs, two-card odds on the flop. Value bet at eq >= 0.6 (0.52 heads-up),
thinner against calling stations; raise facing a bet at eq >= 0.8 (0.7 heads-up) plus ICM premium; call at
pot odds + 0.02 + ICM premium. Semi-bluff strong draws and c-bet heads-up only with fold equity.

**Short stacks and the points table.** ICM risk premium on calls: {3 left: 0.06, 4: 0.085, 5+: 0.1} x share
of our stack at risk (full-stack flip breakeven is ~0.62 with 4-8 left, 0.57 three-handed, 0.5 heads-up,
computed with kit/icm.py). Preflop all-in calls compare range-adjusted, multiway-adjusted equity with pot
odds + premium. Wider opens under 12 bb and much wider under 6 bb; looser vs short-stack shoves.

**Opponents.** Per seat: VPIP, PFR, postflop aggression and fold-to-bet. Bluff (0.6 pot) only when the
product of remaining opponents' fold rates >= 0.45; thinner value and no c-bet bluffs vs stations
(fold rate < 0.3); maniacs' bets narrow their range less; loose raisers get wider calls and 3-bets.

**Last change.** v16 = v15 + the ICM premium also raises the thresholds for raising facing a bet (fewer
stack-offs with second-best hands; T1-T4 showed us busting 8th most often). localsim vs v15 copies at the
same tables: +2.0 (700 tables, seed 1601), +1.0 (seed 1701), single seat -2.2 (seed 2001): roughly level
locally, kept for the bust-reduction rationale. Doubling it (RAISE_PREM 2.0) tied (+1.25 / -1.13), not used.

## T4 result (v15 011-6f57c2aa): rank 7/8, 30.00. 8th 158 (down from 172), 1st 117. VPIP 28.5%, PFR 20%,
## aggression 3.3, 4 timeouts (max 1.6 ms). Patch -> v16 012-0b31cbc6 (see Strategy / Last change).
## Tie (not submitted): tools/var21 = v16 + full-ring opens +0.03: 33.9 vs v16 34.3 (700t seed 2101).
## Not better: tools/var22 = v16 + RISK_BASE {0.07,0.1,0.12}: 33.6 vs v16 34.5 (600t seed 2201).
## Tie: tools/var23 = v16 + HU flop c-bet 0.35 (was 0.5): 34.5 vs v16 34.2 (600t seed 2301). c-bet 0.65 was -1.0.
## Ideas for T6 window: if T5 still shows 8th most often, consider var21; else keep v16.

## T3 result (v14 010-1909fd94): rank 8/8, 28.82. 8th place 172 (T1 168, T2 168), 1st 106. PFR 21% vs field 13-17%,
## postflop aggression 3.9, WTSD 4.7%, 3 timeouts (max 2.3 ms).
## Confirmed leak in T3 sample (we were seat 2): K6 two pair bet flop, called a pot RAISE from a tight bot (set of JJ),
## shoved turn, lost 2000. Cause: old range model fi = f*m with m~2-3; when f (fraction of random pairs beating us)
## is small, f*m stays small -> medium made hands look strong vs raises.
## Patch before T4 -> v15 011-6f57c2aa: range-cutting model. Per opponent x = product over their postflop raises of
##   (BET_X 0.55 lead bet | RR_X 0.2 re-raise) this street, (BET_PREV 0.7 | RR_PREV 0.45) earlier streets,
##   each + 0.6*max(0, aggr-0.33), capped 0.9; preflop raiser x *= PRE_X 0.85.
##   P(opp beats us) = min(0.98, (1-(1-f)^6) / x) (x CHECK_M 0.8 if they checked); p_now = product of (1-P).
##   Tighter version (0.4/0.15/0.6/0.35/0.8) scored -3.3 vs v14 copies locally (they bluff a lot); mild version
##   localsim 600t seed 1201: v15 46.4 vs v14 copies 44.1. Confirm seed 1301: v15 avg 34.2 vs v14 avg 34.7 (tie).
##   Zoo 300t: 54.4. One local run showed 2 "hang" subs (wall > 50 ms) with CPU max 426 us -> machine load, not code.
## Next ideas: PFR 21% vs field 13-17% (opens wider than everyone); check T4 8th-place count after v15.
##   Tie (not submitted): tools/var18 full-ring opens +0.03: 35.1 vs v15 34.3 (500t seed 1401). Candidate if T4 bad.
##   tools/var_tight (0.4/0.15/0.6/0.35/0.8) vs v15 in value-betting house field (nit, montecarlo, threshold,
##   pot_odds), 500t seed 1501: v15 avg 45.5 vs tight 42.7 -> mild calibration confirmed.

## T2 result (v12 008-1c19083d): rank 8/8, 29.36 pts. Places 1st 113 (T1 140), ..., 8th 168 (same as T1).
## VPIP 28%, PFR 20%, aggr 4.1. Field top: b05 36.6 (24/17), b06 35.3 (25/17). Tightening cost wins, busts unchanged.
## Local bust logs (field of own versions): early busts = preflop re-raise wars with KK/QQ hands vs AA-heavy
## 3-bet/4-bet ranges (e.g. KKJ9 4-bet at hand 26, 85bb deep). Equity-vs-random preflop score overrates KKxx there.
## Patch before T3:
##   v13 009-24de01f9: vs raises>=2, re-raise only with AA (or eff < RERAISE_BB 25bb); all-in-call range penalty
##     +NOACE_PEN 0.08 when we hold no ace, -0.04 with AA. localsim 800t: v13 36.3 vs v12 copies 34.8.
##   v14: v13 + revert FOLD_PRIOR 0.5 and RISK_BASE {3:0.06,4:0.085,5:0.1} (T1 values, more wins).
##     localsim 800t seed 701: v14 avg 34.8 vs v13 avg 33.9 (tie); chosen on T1-vs-T2 evidence.
##   ACTIVE for T3: v14 010-1909fd94. Check: localsim 800t seed 801 v14 copies avg 35.6 vs v10 copies 32.6
##     (every v14 seat > every v10 seat). Zoo 300t: 52.5.
##   Rejected: tools/var15 bigger playability bonus (0.032/0.013/0.016): 34.0 vs v14 35.1.
##   Rejected: tools/var16 HU flop c-bet 0.65 (was 0.5): 33.7 vs v14 34.7.
##   Tie: tools/var17 NOACE_PEN 0.12: 34.9 vs v14 34.6 (600t) -> kept 0.08.
## Next ideas after T3: compare T3 places vs T2 (8th-place count should drop with v13 AA-aware fix);
##   better preflop model vs raised ranges (equity vs top-20% hands), timeouts are ~1/100k (ignore).

## T1 result (v10 007-ea8beae4): rank 6/8, 31.25 pts. Places 1st 140, 2nd 102, 3rd 132, 4th 97, 5th 102,
## 6th 119, 7th 140, 8th 168 (bust first most often!). VPIP 37% vs field 21-27% (PFR 21% vs ~17%),
## aggression 5.3 (12019 bets/raises vs 2281 calls postflop), WTSD 5.6%, 2 timeouts (max 1.6 ms, rare).
## Top teams b05/b06/b01 (34-36 pts) are tight: VPIP 22-25%, PFR 16-17%.
## Sample: KK+K-high flush draw semi-bluffed all-in into a 3-bettor's AA.
## Patch before T2 -> v12 008-1c19083d:
##   LIMP=False (no open limps), SB_COMPLETE 0.6 (was 0.45), DEF_FULL 0.08 (BB defence full ring call_thr-0.08,
##   was -0.15), semi-bluff needs P(all fold) >= SEMI_F 0.3 and (spr >= 1.5 or outs >= 12),
##   FOLD_PRIOR 0.42 (was 0.5: bluff only after observed folds), CALL1 0.84 (was 0.8) vs single raise,
##   RISK_BASE {3:0.07, 4:0.1, 5+:0.12} (stronger ICM premium).
##   Local: harness 500t seed 201 v12 43.2 vs v10 41.0; localsim 1000t v12 44.6 vs v10 copies 44.1 (tie);
##   local VPIP 34%. Local house fields don't punish looseness; change is motivated by real T1 stats.
##   v12 zoo (300t seed 5): 50.6 (v10 54.2), within noise.
## Tested, NOT submitted: tools/var_ep = v12 with tighter EP opens {3:0.68, 4:0.75, 5+:0.8}:
##   localsim 800t seed 301 same tables: var_ep avg 35.2 vs v12 avg 34.4 -> noise; kept v12.
## Tested, NOT submitted: tools/var_sh = v12 with tighter short-handed OPEN (0.35/0.5/0.55) and DEF
##   (0.42/0.55/0.62): localsim 800t seed 401: var_sh avg 34.8 vs v12 avg 34.7 -> tie; kept v12.
## Safety check: localsim 700t seed 501, v12 copies avg 35.2 vs v10 copies avg 33.9 (+1.3) -> v12 stays active.
## Next ideas: check T2 places/VPIP; if still busting 8th most, raise RISK_BASE further or tighten
##   short-handed DEF_*/OPEN_*; if 1st-place rate drops a lot, revert toward v10 (007).

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
