# Team b01 notes

## Strategy

**Summary:** Equity-driven bot. Preflop: position-aware opening ranges from a shortdeck hand-strength table, push/fold ranges widened by stack depth and short-handedness, and all-in calls decided by equity vs the shover's estimated range (81x81 precomputed class-vs-class matrix; shover range from their seat, depth and PFR) with an exact Malmuth-Harville ICM check when <=6 players remain. Postflop: a time-boxed (0.30 ms) Monte Carlo against opponents' ranges (preflop range from their VPIP/PFR; postflop bettors narrowed to hands that improved on the board) using a fast table evaluator; bets and calls by equity vs pot odds with a safety margin.

**Before the flop:** Unopened: <=12bb effective -> shove top 22% (UTG) up to ~50% (SB), x1.15/x1.35/x1.6 at <=9/6/4bb, then x1.15 overall (cap 92%), heads-up >=62-75%; 12-14bb -> shove-or-fold by a fold-equity EV model; deeper -> raise 2.2-2.5bb with top ~21% (8-handed early) to ~52-62% (BTN/SB) (table x1.25). Facing a raise: if <=18bb or the raise commits >1/3 of stack -> shove or fold by equity vs raiser's range (PFR-based; for shoves, a push-chart model by the shover's seat and depth, x1.0) plus ICM; deeper -> 3-bet top ~10% when equity >=60% vs their range, call top 35% if cheap and equity beats price by 10%. AA/KK/QQ never fold to re-raises (4-bet 2.5x deep, else jam); JJ/TT/AK call re-raises when equity beats price.

**After the flop:** MC equity vs ranges. Value-bet 65% pot (85% on river when very strong) with equity >=63% HU (lower multiway). C-bet flop 65% HU as preflop raiser, some turn barrels, no river bluffs. Facing a bet: call when equity minus (0.10 + 0.03*bet/pot) (less vs aggressive opponents) beats the price; raise/shove with >=78% HU.

**Short stacks and the points table:** Push/fold <=12-14bb with depth-aware ranges. All-in calls (pre and postflop) and the 12-14bb shove model use ICM $EV (points 100/45/20/8) once 6 or fewer remain.

**Heads-up:** SB opens ~85% (shoves 65% at 12-16bb, chart <=12bb); BB defends ~80% vs small raises (jams top 28% <=25bb); wider ranges assumed for the HU opponent; postflop calls/bets 5% lighter.

**Opponents:** Tracks VPIP, PFR and postflop aggression per seat (with priors). Ranges for MC and all-in calls come from these stats; aggressive bettors get called lighter.

**Last change:** 014-f0f719ed kept for T3 (no candidate beat it in the T3 patch window: wider BB defence -0.5, c-bet 40% -0.9, PREM_FIX off -1.7, ICM only at <=4 players -2.1, push x1.0 -1.1 even vs wide callers). 014 (patch before T2): HU shoves wider (SB 12-16bb top 65% instead of 55%; BB jams top 28% vs small raises <=25bb instead of 22%): +1.3 and +1.3 vs 013 copies (700 and 600 tables). Builds on 013-be182c77. T1 places (1st 89 / 2nd 193) showed heads-up was being lost (~32% of HU finals won). 012: HU SB opens 2.2bb with ~85% above 16bb and shoves top 55% at 12-16bb; HU BB defends ~80% vs small raises (jams top 22% <=25bb); HU range estimates widened (raiser >=60%, re-raiser >=30%, postflop >=60%); AA/KK/QQ never fold to re-raises (KK folded to a 4-bet in T1 samples due to a 25%-of-stack cap), JJ-TT/AK call re-raises without the cap. Local: +2.2 and +1.0 vs 011 copies (two 800-table runs). 013: HU postflop calls 5% lighter and value-bets 5% thinner: +1.9 and +0.7 vs 012 copies (two 800-table runs). Loose house field (500 tables): 013 37.1 > 012 34.2 > 011 32.3.

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
- T1 result (011): rank 4/8, 21.64 pts/table; places 89/193/157/115/103/93/129/121. Leak: HU conversion. Leader b06 24.2.
- 012-20b36b73: HU_FIX + PREM_FIX. +2.2 vs 011 copies (800 tables, seed 101).
- 3-handed version of the fix (TH_FIX: wider blind defence/range estimates at 3 players): 25.7 vs 012 copies 25.9 -> no gain, flag off.
- 013-be182c77: HU_POST (+1.9, +0.7 vs 012).
- Next ideas: check T2 places for HU conversion again; 3-handed play; early-bust rate (7th/8th = 25% in T1).
- Loose-field robustness (seed 127, 500 tables): 013 37.1, 012 34.2, 011 32.3.
- Candidate wider HU shoves (SB 12-16bb 0.55->0.65, BB jam vs small raise 0.22->0.28): +1.3 vs 013 (700 tables, seed 131) -> promising but not submitted late; retest next window.
- Retest seed 137 (600 tables): candHU +1.3 vs 013 again -> submitted as 014-f0f719ed. Active for T2.
- Loose-field check seed 139 (450 tables): 011 39.3, 013 34.6, 014 33.8 (reverses seed 127 order: 013 37.1 > 012 34.2 > 011 32.3) -> loose-field differences are noise at this size; HU changes not proven vs maniac-heavy fields. Re-check T2 places (1st vs 2nd) next window; if HU conversion did not improve, consider reverting toward 011.
- Self-play-like field seed 149 (400 tables): 014 copies 28.7/27.1/24.7 (avg 26.8) vs 011 copies 24.8, 22.6 and a third ranked below 22.6 (avg under 23.7) -> 014 ahead of 011 in range-aware fields.
- T2 result (014): rank 5/8, 20.60 pts/table; places 107/140/133/117/116/111/143/133. HU conversion improved 32% -> 43% (1st 89 -> 107), but final-3 reached less often (439 -> 380); only multi-player change was PREM_FIX (tested locally: helps +1.7), so likely opponents' patches/noise.
- T3 window tests (800 tables each, vs 014 copies): BBDEF (BB calls top 55% when equity >= price+0.03): 25.0 vs 25.5 -> no. CBET_F 0.4 in sticky field (montecarlo/pot_odds/threshold): 30.6 vs 31.5 -> no. PREM_FIX off: 22.9 vs 24.6 -> keep PREM_FIX. Debug run (200 tables, tracebacks on): no hidden exceptions.
- Kept 014-f0f719ed for T3.
- Next ideas: track per-opponent all-in calling frequency to adapt push width; mid-game (4-6 players) all-in call ranges vs tighter real shovers; 3-handed play.
- Wide-caller field (4x 014 with FACE_MULT 1.3, seed 173, 600 tables): 014 (push x1.15) avg 22.8 > push x1.0 avg 21.7 > wide callers avg 21.0 -> keep push 1.15 and FACE 1.0.
- Tight-shover field (4x 014 with PUSH_MULT 0.8, seed 179, 600 tables): FACE_MULT 0.85 avg 22.8 vs 014 (1.0) avg 22.0 (+0.9, noise); tight shovers themselves avg ~20.9. Keep FACE 1.0 (it won +1.8/+2.9 vs wide shovers).
- ICM only at <=4 alive (instead of <=6): 23.5 vs 014 25.6 (600 tables, seed 181) -> keep ICM at <=6.
- PUSH_MAX 14 re-test (seed 191, 600 tables, mixed field with maniac/montecarlo): candidate avg 25.3 vs 014 copies 26.0/25.7/22.3 (avg 24.7) -> +0.6, noise; not adopted.
- Informational (seed 197, 400 tables): HU postflop loosening +0.08 (vs +0.05 in 014): candidate avg 25.9 vs 014 avg 23.8 (+2.1, small sample) -> retest next window before adopting.
