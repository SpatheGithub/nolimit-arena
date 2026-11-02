# Team b01 notes

## Strategy

**Summary:** Equity-driven bot. Preflop: position-aware opening ranges from a shortdeck hand-strength table, push/fold ranges widened by stack depth and short-handedness, and all-in calls decided by equity vs the shover's estimated range (81x81 precomputed class-vs-class matrix; shover range from their seat, depth and PFR) with an exact Malmuth-Harville ICM check when <=6 players remain. Postflop: a time-boxed (0.30 ms) Monte Carlo against opponents' ranges (preflop range from their VPIP/PFR; postflop bettors narrowed to hands that improved on the board) using a fast table evaluator; bets and calls by equity vs pot odds with a safety margin.

**Before the flop:** Unopened: <=12bb effective -> shove top 22% (UTG) up to ~50% (SB), x1.15/x1.35/x1.6 at <=9/6/4bb, then x1.15 overall (cap 92%), heads-up >=62-75%; 12-14bb -> shove-or-fold by a fold-equity EV model; deeper -> raise 2.2-2.5bb with top ~21% (8-handed early) to ~52-62% (BTN/SB) (table x1.25). Facing a raise: if <=18bb or the raise commits >1/3 of stack -> shove or fold by equity vs raiser's range (PFR-based; for shoves, a push-chart model by the shover's seat and depth, x1.0) plus ICM; deeper -> 3-bet top ~10% when equity >=60% vs their range, call top 35% if cheap and equity beats price by 10%.

**After the flop:** MC equity vs ranges. Value-bet 65% pot (85% on river when very strong) with equity >=63% HU (lower multiway). C-bet flop 65% HU as preflop raiser, some turn barrels, no river bluffs. Facing a bet: call when equity minus (0.10 + 0.03*bet/pot) (less vs aggressive opponents) beats the price; raise/shove with >=78% HU.

**Short stacks and the points table:** Push/fold <=12-14bb with depth-aware ranges. All-in calls (pre and postflop) and the 12-14bb shove model use ICM $EV (points 100/45/20/8) once 6 or fewer remain.

**Opponents:** Tracks VPIP, PFR and postflop aggression per seat (with priors). Ranges for MC and all-in calls come from these stats; aggressive bettors get called lighter.

**Last change:** 011-6e5ce776: postflop calling margin ADJ_PLUS 0.06 -> 0.08 (+1.9 vs 010 in loose field, +1.4 in self-play earlier). 010-6570c359: call shoves vs the full seat/depth push-chart range (FACE_MULT 0.9 -> 1.0): +2.9 vs 009 in loose house field (450 tables) and +1.8 in self-play field (900 tables). 009-649ddccf: push ranges x1.15 wider (avg 24.2 vs 21.5 for 008 over 900 tables, both copies ahead). Before that, 008-db6e5fdc: shover-range model by seat/depth (FACE3, +3 pts vs 005 over 900 tables), opening ranges x1.25 (+2.7), tighter postflop calling margin (+0.06) and value threshold 0.63 (each +1..1.5 in self-play fields), MC budget cut to 0.30 ms for timing safety. Robustness vs loose house field: 40.7 pts/table (600 tables).

## Log
- v0 001-01a6d503: simple threshold bot (safety submission).
- v1 002-2c3a81ca: evaluator + matrix + MC + ICM. Zoo: 40.5 ±8.7.
- 003-90d3ec6b: v0 preflop + MC postflop with bettor narrowing (hybrid tests showed v1 preflop leaky, MC postflop better than v0 postflop).
- 004-f6f34dae: v1 preflop but v0 push ranges (component swap tests: v1 shove-EV model was the leak).
- 005-f7b23c4b: depth/HU-aware push ranges. +2.5..5 pts vs 003/004 in 800-table runs.
- Tested, no measurable effect (+-2.5): c-bet 35% vs 65%, value threshold 0.55 vs 0.6, value size 0.8 vs 0.65, wider shove-range estimates when facing shoves (FACE2), push/fold up to 14bb.
- Note: localsim reports occasional "hang" (50ms wall) under machine load; CPU max ~600us.
- 006-9c1da522: FACE3 shover-range model. 27.9 vs 005 copies 24.9 (900 tables).
- 007-5afd748c: open x1.25, ADJ_PLUS 0.04. 008-db6e5fdc: ADJ_PLUS 0.06, VTHR 0.63, MC 0.30ms.
- Tested, no gain: 3-bet shove top 16% vs loose openers <=30bb (RESHOVE). Tighter calls (ADJ 0.08, VTHR 0.66) slightly better in self-play but field is my own value-heavy variants -> only partly adopted.
- Ideas next: fold-to-cbet tracking, river bluffs vs. high fold rates, ICM with >6 players, better multiway handling.
- 009-649ddccf: PUSH_MULT 1.15 (+2.7 vs 008). FACE_MULT 1.0 (call shoves wider) mixed (+1.8), not adopted.
- Candidate PUSH_MAX 14: +2.0 vs 009 in self-play field (800 tables) but -4.4 vs 009 in loose house field (400 tables) -> net ~0, NOT submitted; 009 stays active. PUSH_MULT 1.3: +1.2 (noise), not adopted.
- Patch-round ideas: test PUSH_MAX 14 / PUSH_MULT 1.3 against real-field results; track opponents' shove-calling ranges to size push ranges; fold-to-cbet stats.
- 010-6570c359: FACE_MULT 1.0 (call shoves wider).
- 011-6e5ce776: ADJ_PLUS 0.08. FINAL build-phase submission (active for T1).
- PUSH_MULT 1.3 on top of 011: +1.1 loose field (vs 010 base), +1.2 self-play (vs 009 base), but -3.3 vs 011 copies in a 400-table self-play run (23.6 vs 26.9) -> rejected; keep 1.15.
- VTHR 0.66 on top of 011 (350 tables, mixed field): candZ avg 27.8 vs 011 copies avg 28.8 -> no gain, keep 0.63.
- Baseline 011 vs house zoo (250 tables, seed 89): 45.9 +-5.8 pts/table, 1st of 8 (nit 2nd at 29.4). v1 scored 40.5 on the same test earlier.
