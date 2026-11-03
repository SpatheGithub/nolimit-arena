## Strategy

**Summary:** Table-driven bot (submission 008-83010431 = tools/v9). Preflop uses precomputed Monte-Carlo equities of every 3-card crazy-pineapple hand (vs 1..7 random opponents, each player keeping the 2 cards that make the best flop hand) plus heads-up equity vs top-r% ranges for calling raises/shoves. Postflop uses a made-hand/draw strength estimate over the best 2-card keep, blended on turn/river with a time-boxed Monte Carlo hand strength, then compared with pot odds after a penalty for how strong the betting line is. All-in calls are checked with ICM in points. Cheap: p99 ~0.35 ms per act.

**Before the flop:** Hands ranked by percentile among all 22,100 3-card holdings (three of a kind in hand ranks last, small pairs are mediocre: one card is always dead). Deeper than 13bb effective: open-raise top 12% (7 players behind) up to ~42% (SB), with ranges x1.25 when 1-3 players are behind (CO/BTN/SB steals), sized 2.1-2.3bb (+1bb per limper, 3bb from SB), widened up to x1.35 when the players behind rarely raise. 3-bet/shove only premiums (top ~2.5%, shove if ≤30bb). Facing a raise: equity vs the raiser's estimated range (position-aware: push/open range for the number of players behind them, scaled by their observed raise frequency) times a realization factor (0.93 IP / 0.84 OOP) must beat pot odds; flat calls outside the big blind need +0.05 extra equity (+0.10 in the small blind). SB limps only top 30%; "cheap" implied-odds calls only with top 12% for ≤4% of stack. 13bb or less: push/fold with Nash-like ranges (SB 58% at 10bb ... UTG 15%, scaled by (10/eff_bb)^0.75).

**After the flop:** Flop: best of the 3 possible keeps by hold'em-style features (pair class, kicker, two pair, sets, straights, flushes) + draw outs. Turn/river: blended with Monte Carlo hand strength vs random hands (HS^3.4 per opponent). Value-bets 0.55-1.0 pot; c-bets 40% pot as the preflop raiser heads-up 55% of the time (30% vs two); semi-bluffs big draws; rare river bluffs. Facing bets: calls if adjusted equity minus a penalty beats pot odds; penalty grows with bet size, river, multiway, every extra villain bet/raise this hand (+0.09 each), raises over our bet (+0.16), and one-pair hands facing big turn/river bets (+0.10); smaller vs seats that bet often. Raises/shoves monsters. Discard: keeps the 2 cards with the best strength+draw score on the flop.

**Short stacks and the points table:** Push/fold at ≤13bb. Every call of an all-in or stack-committing bet (preflop or postflop, 3+ players alive) needs equity ≥ (EV_fold − EV_lose)/(EV_win − EV_lose) in points, using a Malmuth-Harville ICM (exact for places 1-4, uniform remainder; within ~1 point of kit/icm.py, ~45 µs). Heads-up: chip EV.

**Opponents:** Per seat during a table: preflop raise frequency (shapes their estimated raise/shove range and our steal width), postflop bet frequency (scales how much we respect their bets), and how often they call vs fold when facing a preflop all-in (shove ranges x0.7 when the players behind call shoves often, up to x1.25 when they fold; prior 20% calls = neutral).

**Last change:** No code change for T5 or T6: v9 (008-83010431) kept. T4 32.60 (rank 5) and T5 34.59 (rank 2) with the identical bot, so ±2 between tournaments is noise. Local paired test in a mixed field of all styles (tight, tight+re-steal, submissions 006-008; seed 808): v9 33.60 vs v8 32.03 vs v7 30.02. Rejected in the T5 window: re-steal shoves (no gain), wider 3-bet-shove call range (−2.6), all-in read strength 1.0/2.5 (32.7/30.7 vs 33.6). T6 window: v9 vs v8 over six paired seeds +0.4 on average (equivalent); wider shoves before blind level-ups rejected (−1.1, −0.8); 3-bet range wider (−3.3, −4.0) and tighter (−2.4, −0.9) both rejected; turn/river strength exponent 3.8 (−1.1, −2.8) and 3.0 (−1.7, −1.1) rejected. v9's change itself: per-seat all-in call/fold reads scale our shove ranges x0.7-1.25.

## Notes

- Tools: tools/pre3.py (3-card equity vs k random), tools/rng3.py (vs top-r ranges), tools/build_pre.py -> bot/pre3.json; tools/sim.py (place distribution harness), tools/biglos.py (hand logs of our big losses), tools/spot.py (crafted-spot sanity checks). Snapshots of versions in tools/v1..v6.
- localsim/sim is fast: 400 tables ≈ 45-60 s. Noise: ±3.3 per seat at 400 tables, ±2.4 at 700.

- Final check of 005 vs house zoo (localsim, 300 tables, seed 9): 64.3 pts/table (next best: nit 46.6); p99 0.3 ms, 0 substitutions.

- Final localsim vs earlier submissions (300 tables, seed 12): 004 copies 41.2/38.8, 005 (you) 38.0, 003 35.4/33.8, 002 26.6/25.0, 001 16.4. v5 vs v6 is within noise here (earlier runs had v6 +2-4); worth a 1000-table v5-vs-v6 check in the first patch window. Follow-up: 005 vs 7x 004 (300 tables, seed 14): 35.0 vs 31.9 baseline -> keep 005.

## T1 result (v6 / 005)
- Rank 4/8, 33.59 ± 2.0. Places 136/133/120/129/142/122/126/92 per 1000. Top: b07 37.5 (VPIP 20 PFR 17), b02 35.9, b01 35.3. All other teams VPIP 20-26%. 0 substitutions, p99 300 µs.

## T2 result (v7 / 006)
- Rank 3/8, 33.78 ± 2.0 (T1 was 33.59). Places 138/152/108/115/120/127/119/121 per 1000. Top: b07 35.3 (VPIP 20 PFR 17), b01 34.4 (19/15). Our VPIP 29% (still highest), PFR 18%. 0 substitutions.

## Patch window before T3: tight-field proxy
- tools/tag = v7 with strict calling (FLAT_SB .25, FLAT_OTH .12, BB −.07, no limps/cheap calls): VPIP 20 / PFR 16, like the T1/T2 leaders.
- v7 vs 7x tag (600 tables, seed 101): 33.19 (baseline 31.9) -> v7 beats the tight proxy.
- Candidates vs 7x tag, same seed: late opens x1.25: 33.69 (n.s.); shoves x1.2: 32.17; raise-or-fold outside blinds when deep (FLAT_OTH_DEEP .12): 30.52. Late opens re-tested on seed 202: 33.80 vs v7 31.65 -> adopted as v8; others not adopted.
- v7 preflop-call P&L vs tag field (120 tables): deep BB defense −0.32bb/call (fold = −1), short BB −0.19, deep non-blind flats 2-5bb −1.13 (n=121) but removing them tested worse.

- v8 vs v7, 7x tag, seed 303 (450 tables): 36.54 vs 32.40.
- v8 vs 2x 006, 2x 005, 2x 004, tag (localsim 400 tables, seed 44): v8 34.8 (1st), 006 33.8/29.8, tag 33.0, 005 31.8/28.8, 004 31.6/31.3.
- v8 vs house zoo (300 tables, seed 9): 64.0 (v7 59.7, v6 64.3 on the same seed), 0 substitutions.
- Late opens x1.45 (tools/v9) vs 7x tag: seed 303 34.84 (v8 36.54), seed 101 32.11 (v8 33.69) -> worse than x1.25; keep v8.
- v8 vs 4x 006 + 2x tag + 005 (localsim 400 tables, seed 33): 32.3 vs 006 copies avg 32.1 -> keep v8.

## T3 result (v8 / 007)
- Rank 5/8, 32.08 ± 2.0 (field 28.1-34.2, all within noise). Places 131/130/107/112/134/149/120/117. VPIP 30 PFR 19; showdown win 55% (T1 58, T2 56).
- v9 vs house zoo (300 tables, seed 9): 62.8 (v8 64.0), 0 substitutions, p99 0.44 ms.
- Patch window before T4: v10 (tools/v10) = v9 + per-seat fold-to-open reads in steal_mult (FO_K 1.0): mixed field seed 55: 39.7 vs v9 copies 40.5 -> rejected.
- ICM shove factor vs tight proxy seed 202: 33.1 vs v8 33.8 (rejected). v8 vs v7 fourth seed 404: 32.7 vs 31.0 (+1.7; avg +2.1 over 4 seeds) -> kept late opens.

## T4 result (v9 / 008)
- Rank 5/8, 32.60 ± 2.1. Places 143/124/111/104/120/137/130/131 (most 1sts so far, but 7th/8th rising: 8th = 92, 121, 117, 131 in T1-T4). Leaders b07 34.3, b01 33.9, b02 33.5 (VPIP 19-26%).
- Real results by version: v6 33.59 (T1), v7 33.78 (T2), v8 32.08 (T3), v9 32.60 (T4) — differences within noise; the field also patches between tournaments.
- Local bust analysis (150 tables vs tag/v8/v9): 69% of our busts are preflop push/fold shoves at 7-12bb (mid 29%, early 21%, late 19%) — mostly standard flips/coolers, caused by the doubling blinds.

## Patch window before T5
- New proxy tools/tag2 = tag + re-steal shove (12-30bb vs wide openers, pct ≤ r_w*0.5). vs 7x tag2, seed 505, 450 tables: v7 31.46, v8 31.10, v9 33.74, v11 (v9 + same re-steal) 33.71, v12 (v9 + wider 3-bet-shove range estimate 0.11) 31.14. -> keep v9 (no re-steal, tight 3-bet shove calls).
- v11 vs 7x tag seed 303: 35.21 (v8 36.54, v7 32.40).
- Second tag2 seed 606: v9 29.41, v8 29.19 (equal). tag2 as hero vs 7x v9 (seed 707): 30.67 (< 31.9) -> v9 not dominated by the tight re-steal style. Decision: keep v9 (008) for T5.
- Paired mixed all-style field (tag, tag2 x2 each, 007, 006, 008; seed 808, 450 tables): v9 33.60 vs v8 32.03 vs v7 30.02 -> v9 best; no revert. AI_K bracket on this seed: 1.0 -> 32.69, 1.5 (v9) -> 33.60, 2.5 -> 30.69 -> keep AI_K 1.5.

## T5 result (v9 / 008, unchanged from T4)
- Rank 2/8, 34.59 ± 2.0 (T4 same bot 32.60). Places 141/148/114/128/144/115/108/102. Leaders b02 35.04, b01 33.69, b07 32.28. Weighted total 500.74, rank 4.

## Patch window before T6
- Paired v9 vs v8, mixed field seed 909: 30.28 vs 32.21 (−1.9). All paired v9−v8 results: +0.6 (tag s202), −0.8 (mixed s66), +2.6 (tag2 s505), +0.2 (tag2 s606), +1.6 (mixed s808), −1.9 (mixed s909): mean +0.4 -> equivalent; keep v9 (no change) for T6.
- v15 = v9 + wider shoves in the last 3 hands before a blind level-up (eff_bb / (1 + 0.25*(4 - hands_to_next_level))): tag2 s505 32.62 (v9 33.74), mixed s808 32.77 (v9 33.60) -> rejected.
- v16 = v9 with wider value 3-bets (pct ≤ .04 or eq ≥ .60 & pct ≤ .08): tag2 s505 30.42, mixed s808 29.61 (8th place 18-20%) -> rejected.
- v17 = v9 with tighter 3-bets (pct ≤ .015 or eq ≥ .65 & pct ≤ .04): 31.34, 32.69 -> rejected; v9's 3-bet threshold (pct ≤ .025 or eq ≥ .62 & pct ≤ .06) is a local optimum.
- v18 = v9 with turn/river MC exponent 3.8 (was 3.4): 32.63, 30.76 -> rejected. Exponent 3.0: 32.04, 32.47 -> rejected; 3.4 is a local optimum.

- Final T6 sanity: active bot (== 008) vs house zoo, 200 tables seed 31: 68.2, 0 substitutions, max 0.35 ms.

## Version history
- v1 001: hold'em-proxy preflop. v2/v3 002: 3-card table + range table (+8 vs v1).
- v4 003: ICM calls + river/turn MC + equity realization: 56.7 vs 47.0 (v3) on house field. Biggest single gain.
- v5 004: postflop call penalties vs multi-street aggression (logs showed big losses calling down one pair/weak two pair): 43.4 vs v4 32-33.
- v6 005: position-aware villain ranges (+2-4 vs v5).
- v7 006: fewer flat calls (VPIP 34→29%). T2: rank 3, 33.78.
- v8 007: late-position opens x1.25 (steals vs tight blinds). T3: rank 5, 32.08.
- v9 008: all-in call/fold reads scale shove ranges.

## Tried and rejected (within noise or worse)
- HU SB open 72% at 2.2bb: −2.6. ICM tightening of shove ranges: −5 (aggression pays in these fields). Shove ranges x1.2: neutral.
- Bigger value bets/fewer bluffs vs stations: −3.4. Flop multiway exponent 1.35: neutral. C-bet 75%: +1.3 (n.s.).
- Re-steal shove 12-28bb vs wide openers: +2.5 vs v6 copies but −2.5 on mixed field. Tighter flat calls (0.88/0.76): neutral. Push/fold up to 16bb: neutral. C-bet 45%/15%: −2 on mixed seed 99 (but that seat scored ~43 for every variant there, so seat luck; inconclusive).
- 700 tables vs 7x v6 (baseline 31.9): thinner value bets (0.56): 32.0; stronger call penalties (0.12/0.20/0.14): 31.3 — v6 parameters look locally optimal.
- Final-window check: v6 big postflop losses are mostly one pair on paired boards (QQ on 522, JJ on QQx) calling turn/river raises. Treating board-pair two-pair as one pair for PAIR_PEN: 30.7 vs 31.9 baseline (700 tables) -> not adopted. Raise-only variant (paired board + villain raised/bet twice): 31.5 -> not adopted either.
- Lesson: 400-table comparisons within one run carry seat luck of ±2-3; use 700+ tables vs 7 copies of the baseline (baseline = 31.9).

## Patch window before T2 (tested on top of v7, not adopted)
- Shove ranges x1.2: tight field +2.0 (n.s.), vs 7x v7 29.0 (baseline 31.9) -> rejected.
- Open size 2.5bb/2.2bb: vs 7x v7 31.2 -> neutral, rejected.
- v7 vs house zoo (300 tables, seed 9): 59.7 (v6 was 64.3 on the same seed; within noise ±4), 0 substitutions.
- v7 vs 4x 005 + 3x 004 (localsim 400 tables, seed 21): 33.7 vs field mean ~31.6 -> keep 006.
- Local preflop-call P&L (100 tables, self+nit field): BB defense −0.79bb/call (better than −1 fold); SB flat calls −2.6bb (vs −0.5 fold); other flats −0.24bb. Basis for v7. Tools: tools/biglos.py (logs) + tools/vpip.py.

- v7 preflop-call P&L (80 tables vs v7/v6/v5/nit field): deep BB defense vs ≤2bb raises −1.17bb/call (n=286; ≈ folding's −1.0), short BB defense −0.10 (good), SB deep flats −4.2 (n=26, still some). Tested: SB raise-or-fold when ≥25bb + deep BB defense −0.03 equity: vs 7x v7 700 tables 31.0 (baseline 31.9) -> not adopted.

## Known weaknesses / next
- Flop strength still hold'em-calibrated `features`; discard heuristic not equity-based.
- Opponent model crude (no fold-to-shove or showdown-strength stats).
- Hand cap / hands_left not used (tables never reached the cap locally).
