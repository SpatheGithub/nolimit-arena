## Strategy

**Summary:** Table-driven bot (submission 005-6838bd18 = tools/v6). Preflop uses precomputed Monte-Carlo equities of every 3-card crazy-pineapple hand (vs 1..7 random opponents, each player keeping the 2 cards that make the best flop hand) plus heads-up equity vs top-r% ranges for calling raises/shoves. Postflop uses a made-hand/draw strength estimate over the best 2-card keep, blended on turn/river with a time-boxed Monte Carlo hand strength, then compared with pot odds after a penalty for how strong the betting line is. All-in calls are checked with ICM in points. Cheap: p99 ~0.35 ms per act.

**Before the flop:** Hands ranked by percentile among all 22,100 3-card holdings (three of a kind in hand ranks last, small pairs are mediocre: one card is always dead). Deeper than 13bb effective: open-raise top 12% (7 players behind) up to ~42% (SB), sized 2.1-2.3bb (+1bb per limper, 3bb from SB), widened up to x1.35 when the players behind rarely raise. 3-bet/shove only premiums (top ~2.5%, shove if ≤30bb). Facing a raise: equity vs the raiser's estimated range (position-aware: push/open range for the number of players behind them, scaled by their observed raise frequency) times a realization factor (0.93 IP / 0.84 OOP) must beat pot odds. 13bb or less: push/fold with Nash-like ranges (SB 58% at 10bb ... UTG 15%, scaled by (10/eff_bb)^0.75).

**After the flop:** Flop: best of the 3 possible keeps by hold'em-style features (pair class, kicker, two pair, sets, straights, flushes) + draw outs. Turn/river: blended with Monte Carlo hand strength vs random hands (HS^3.4 per opponent). Value-bets 0.55-1.0 pot; c-bets 40% pot as the preflop raiser heads-up 55% of the time (30% vs two); semi-bluffs big draws; rare river bluffs. Facing bets: calls if adjusted equity minus a penalty beats pot odds; penalty grows with bet size, river, multiway, every extra villain bet/raise this hand (+0.09 each), raises over our bet (+0.16), and one-pair hands facing big turn/river bets (+0.10); smaller vs seats that bet often. Raises/shoves monsters. Discard: keeps the 2 cards with the best strength+draw score on the flop.

**Short stacks and the points table:** Push/fold at ≤13bb. Every call of an all-in or stack-committing bet (preflop or postflop, 3+ players alive) needs equity ≥ (EV_fold − EV_lose)/(EV_win − EV_lose) in points, using a Malmuth-Harville ICM (exact for places 1-4, uniform remainder; within ~1 point of kit/icm.py, ~45 µs). Heads-up: chip EV.

**Opponents:** Per seat during a table: preflop raise frequency (shapes their estimated raise/shove range and our steal width) and postflop bet frequency (scales how much we respect their bets).

**Last change:** v6 (005-6838bd18): villain raise/shove range now depends on their position (players behind them) and stack depth instead of a fixed width. Own-version field, 400 tables: v6 43.3 vs v5 copies 40.3; confirmation seed: v6 ~43 vs v5 ~39; nit/station/maniac field: v6 57.2 vs v5 51.1.

## Notes

- Tools: tools/pre3.py (3-card equity vs k random), tools/rng3.py (vs top-r ranges), tools/build_pre.py -> bot/pre3.json; tools/sim.py (place distribution harness), tools/biglos.py (hand logs of our big losses), tools/spot.py (crafted-spot sanity checks). Snapshots of versions in tools/v1..v6.
- localsim/sim is fast: 400 tables ≈ 45-60 s. Noise: ±3.3 per seat at 400 tables, ±2.4 at 700.

- Final check of 005 vs house zoo (localsim, 300 tables, seed 9): 64.3 pts/table (next best: nit 46.6); p99 0.3 ms, 0 substitutions.

- Final localsim vs earlier submissions (300 tables, seed 12): 004 copies 41.2/38.8, 005 (you) 38.0, 003 35.4/33.8, 002 26.6/25.0, 001 16.4. v5 vs v6 is within noise here (earlier runs had v6 +2-4); worth a 1000-table v5-vs-v6 check in the first patch window. Follow-up: 005 vs 7x 004 (300 tables, seed 14): 35.0 vs 31.9 baseline -> keep 005.

## Version history
- v1 001: hold'em-proxy preflop. v2/v3 002: 3-card table + range table (+8 vs v1).
- v4 003: ICM calls + river/turn MC + equity realization: 56.7 vs 47.0 (v3) on house field. Biggest single gain.
- v5 004: postflop call penalties vs multi-street aggression (logs showed big losses calling down one pair/weak two pair): 43.4 vs v4 32-33.
- v6 005: position-aware villain ranges (+2-4 vs v5).

## Tried and rejected (within noise or worse)
- HU SB open 72% at 2.2bb: −2.6. ICM tightening of shove ranges: −5 (aggression pays in these fields). Shove ranges x1.2: neutral.
- Bigger value bets/fewer bluffs vs stations: −3.4. Flop multiway exponent 1.35: neutral. C-bet 75%: +1.3 (n.s.).
- Re-steal shove 12-28bb vs wide openers: +2.5 vs v6 copies but −2.5 on mixed field. Tighter flat calls (0.88/0.76): neutral. Push/fold up to 16bb: neutral. C-bet 45%/15%: −2 on mixed seed 99 (but that seat scored ~43 for every variant there, so seat luck; inconclusive).
- 700 tables vs 7x v6 (baseline 31.9): thinner value bets (0.56): 32.0; stronger call penalties (0.12/0.20/0.14): 31.3 — v6 parameters look locally optimal.
- Final-window check: v6 big postflop losses are mostly one pair on paired boards (QQ on 522, JJ on QQx) calling turn/river raises. Treating board-pair two-pair as one pair for PAIR_PEN: 30.7 vs 31.9 baseline (700 tables) -> not adopted. Raise-only variant (paired board + villain raised/bet twice): 31.5 -> not adopted either.
- Lesson: 400-table comparisons within one run carry seat luck of ±2-3; use 700+ tables vs 7 copies of the baseline (baseline = 31.9).

## Known weaknesses / next
- Flop strength still hold'em-calibrated `features`; discard heuristic not equity-based.
- Opponent model crude (no fold-to-shove or showdown-strength stats).
- Hand cap / hands_left not used (tables never reached the cap locally).
