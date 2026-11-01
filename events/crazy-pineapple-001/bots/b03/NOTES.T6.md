# Team b03 notes

## Strategy

**Summary:** A tight-aggressive bot built on precomputed math. Before the flop it looks up each 3-card hand in a table of equities (1755 suit classes, Monte Carlo, oracle discard) and plays by its percentile. After the flop it runs a small timed Monte Carlo against random hands, discounts that for bet size, and compares it with the pot odds. When short it plays push/fold, and it calls all-ins only when its equity beats the price plus an ICM margin.

**Before the flop:** Opens to 2.5bb (+1bb per limper) with the top 12% of hands from early seats, widening to 30% on the button and 42% from the small blind. Opponents are counted by how many still act behind. It 3-bets the top 3.5% (shoves at 25bb or less), calls single raises with the top ~10% (+8% in the big blind), and plays only the top 2.5–6% against 3-bets. When the big blind gets a free option it raises the top 10%.

**After the flop:** Equity comes from about 10–40 timed Monte Carlo samples (stopping at 0.36 ms wall). On the flop it simulates 3-card opponent hands with the best 2-of-3 keep, and it extrapolates from 2 simulated opponents to more. With no bet in front of it, it value-bets 70% pot when equity × players ≥ 1.45. It c-bets half pot heads-up on the flop 55% of the time as the preflop raiser, and stabs 40% of the time with equity ≥ 0.55. Facing a bet, it calls if equity − 0.07 − 0.10·(bet/pot) − 0.06 per extra raise (−0.03 more on the river) ≥ pot odds, and it raises very strong hands. To discard, it keeps the 2 cards with the best average hand over 24 sampled runouts.

**Short stacks and the points table:** At 13bb effective or less it plays push/fold. The shove range is 0.94/(players behind + 0.8) · (10/bb)^0.6, ×1.15 with 3 or fewer players left. Against a big raise or shove, it estimates the raiser's range from their stack depth and the number of players left. It converts its equity against that range with a linear model (0.5 + its equity − the range's average equity) and calls only if that beats the pot odds + 0.04 (4+ players left) or + 0.02 (3 left). Heads-up it uses no margin.

**Opponents:** No per-seat reads yet. Opponent ranges are inferred only from bet sizes and the action in the current hand.

**Last change:** (v3, submission 002-699ddeb8) Replaced the fixed percentile cut for calling all-ins with equity against an estimated range. Before, heads-up it called shoves with only ~18% of hands. It now also shoves wider short-handed, cuts the MC budget from 0.45 to 0.36 ms (T3 max CPU was 792 µs), and calls tighter postflop. In local tests against v1 copies + house bots it scored 41.7 vs v1's 38.7 (150 tables) and 40.9 vs 39–46 (120 tables). Both are within noise, but it was never clearly worse, and the changes target T3–T5 problems: 7th/8th finishes ≥ 1st finishes, and a 45% showdown win rate.

## Results so far
- T1, T2: no accepted bot (the session got cut off before I submitted).
- T3 (v1, 001-30b642d6): 30.77, rank 5. T4 (v1): 25.95, rank 8. T5 (v1): 28.94, rank 6.
- The winner b08 plays VPIP 20 / PFR 16. Locally the house "nit" (top 8%, folds to raises) beats our copies, so tight play pays in this field.

## Known weaknesses / next steps
- MC equity against random hands overrates our hands against betting ranges. A range-weighted postflop model would help.
- No opponent modelling (VPIP/aggression per seat, which would let us widen steals against folders).
- The preflop table weights all classes equally in AVG_TOP, which is slightly off. Oracle discard inflates 3-suited/connected hands.
- Push/fold ranges are formula-based, not Nash-computed for this variant.
