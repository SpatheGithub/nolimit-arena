# Team b03 notes

## Strategy

**Summary:** Preflop decisions use a precomputed 81x81 shortdeck class-vs-class equity matrix (Monte Carlo, 1500 deals/pair) turned into "equity vs top-x% range" tables, so every call/shove is an EV computation against an estimated range, valued with a 50/50 blend of ICM points (precomputed table, exact referee payouts 100/45/20/8) and chip EV. Postflop uses a fast made-hand/draw heuristic adjusted for board dangers (4-straight boards, paired boards, 3-4 flush cards), multiway pots, bet size, street and opponent aggression. Per-seat stats (VPIP, PFR, fold-to-raise, short-stack shove rate, postflop aggression and fold-to-bet) shift ranges and steals during a table.

**Before the flop:** Unopened: open-raise to 2.4bb (+1bb/limper, 2.8bb from SB) with the top 13% (early) to 38% (button) / 55% (SB) of hands, widened when the players behind fold a lot; plus explicit steals with any top-80% hand when the product of the behind players' observed fold-to-raise rates beats the raise's break-even. At <=13bb effective (or 13-18bb with non-premium hands) it is shove-or-fold by EV: sum over players behind of P(call) x value(win/lose) + P(all fold) x value(steal). Facing a raise: raiser range from their PFR (or, for big raises/shoves, from stack depth, position and observed short-stack shove rate); 3-bet/shove the top ~3.5%, re-shove <=22bb by fold-equity EV, call when equity x realization (0.82 OOP, 0.92 IP) beats pot odds; committing calls use the ICM/chip check.

**After the flop:** Strength from category/kicker/texture plus draw outs, minus penalties for dangerous boards (4-straight boards, paired boards for straights, 3-4 flush cards incl. one pair on 3-flush boards, trips with a weak kicker), raised to a power for multiway pots. Bets 0.6-0.85 pot with strong hands (only converts to all-in when very strong), 0.5 pot with medium hands heads-up/IP (not after an opponent has raised postflop this hand), c-bets heads-up flops as preflop raiser (frequency from opponent fold-to-bet), semi-bluffs draws, rare river bluffs. Facing a bet: equity discounted by bet size, street (turn x1.15, river x1.35), opponent aggression and +0.05 per earlier street the same bettor already bet (barrels); raises very strong hands, calls when equity beats pot odds; big calls (>=50% of stack) go through the ICM/chip check.

**Short stacks and the points table:** Push/fold below ~13bb (EV vs modelled calling ranges). All-in decisions valued with blended ICM (V_n(chip share) table for 2-8 players) and chip EV at ICM's marginal rate, so it avoids marginal flips with many players left but stays aggressive enough to win (1st = 100 pts).

**Opponents:** Tracks VPIP, PFR, fold-to-raise, big-raise rate when short (<=25bb), postflop aggression and fold-to-bet per seat, with Bayesian priors. Used for raiser range width, shove-range width, steals, c-bet and bluff frequency, and the bet-strength discount.

**Last change:** v6 (005-2412bff5, for T3): call-down discipline from big-loss logs: extra bet discount per previous barrel, pair-on-flush-board and weak-kicker-trips penalties, no medium value bets after an opponent's postflop raise (history scan rewritten to one pass). Test: paired 600 tables vs [004 x2, c6, v2, v1, c3, c4]: 22.24 vs 20.96 for 004; earlier smaller samples +2.0 and +2.3 (one -8 on a mismatched table count).

## T2 result and patch window
- T2 (bot 004): rank 7/8, 20.39 (CI 18.4-22.3); places 108/127/138/139/134/125/119/110. b02 leads both rounds (26.3, VPIP 30% PFR 20%). Weighted total 60.69, rank 8.
- Paired 600-table tests vs [004 x2, c6, v2, v1, c3, c4] (quick.py, same seeds): c5/004 20.96, c7 (LAM 0.25) 20.24, c8 (wider preflop calls: realization 0.86/0.95, BB 0.9, pct<=0.55) 20.85, c6 22.24 -> submitted c6 (as 005, linear history scan; check_bot p99 50 us).

## T1 result and patch window
- T1: rank 7/8, 19.91 pts/table (CI 18.0-21.8); places 1st 104, 2nd 117, 3rd 148, 4th 161, 5th 134, 6th 127, 7th 122, 8th 88. 0 substitutions. Field is tight: 18.9-25.0. Our VPIP 24% is the lowest (others 26-33%), PFR 19% (others 14-20%), WTSD 7.8%.
- Diagnosis: we survive (many 3rd-5th) but win only 10.4% (fair 12.5%). Likely too tight/ICM-averse in the late stage for a top-heavy payout.
- Tried c7 = c5 with LAM 0.25 (less ICM weight): quick.py vs [004 x3, v2 x2, c6, nit] 22.3 (150 tables) vs c5 23.4 (65 tables, same seeds) -> no evidence, not submitted.
- Second sample vs [004, v2, c6, nit, montecarlo, v1, maniac]: c7 16 tables 37.7 (hit a ~40 s slow table), c5 103 tables 26.2 -> still no usable comparison.
- sample_hands.json only has the first 10 hands of 4 tables (early stage), and our own seat id isn't marked in it.
- Next window: test late-stage aggression (wider push/call when <=4 left, LAM 0.25), wider BB defence and more VPIP, with larger paired runs. quick.py sometimes hits a ~20-25 s table under load; give it budget and timeout slack.

## Results log
- v1 vs zoo (200 tables): 41.7 pts/table (1st). vpip 28% pfr 26%.
- v2 vs [v1x3, mc, nit, maniac, pot_odds] 600 tables: v2 30.2, v1s 29.9/28.6/28.5, nit 26.7.
- v3 candidate (blend observed fold-to-raise into call ranges) vs [v2x3,...] 700 tables: 28.2 vs v2s 31.8/28.8/28.2 -> not adopted.

- c1 (stronger value bets) 32.2, c2 (pure ICM) 30.8, c3 (ICM/chip blend) 30.5 vs v2 32.0 on seed 11 mixed field: all within noise; c3 submitted as 003 on theory.
- Mirror field (7 x v2, 1000 tables): v2 20.9, c1 21.3, c3 21.9.
- Nit-heavy field [v2,nit,v2,nit,mc,nit,v2] seed 31: c3 28.8, c4 (steals) 29.8, c5 (postflop leak fixes) 34.2.
- Observation: house nit takes 2nd ~40% of tables because aggressive bots bust each other; ICM matters.

- c6 (extra discount per previous barrel by the bettor, pair-on-flush-board penalty, trips weak-kicker penalty, no medium bets after an opponent's postflop raise): quick in-process test 28.7 (150 tables) vs c5 36.9 (121 tables), different table sets, noise +-7 -> NOT submitted. bot/ restored to c5 = 004-f52b239b.

- Final checks: accepted 004 vs zoo (200 tables, seed 7): 44.7 (1st), max 108 us, 0 substitutions. Extra quick.py samples c6 vs c5: mixed 33.6 (100) vs 31.7 (62); nit-heavy 33.3 (96) vs 31.0 (98). Combined with the first sample (28.7 vs 36.9) still inconclusive; c6 is the first thing to test properly in a patch window (fix its O(n^2) scan first).

## Known weaknesses (from big-loss logs, tools/bigloss.py)
- Calls down 2-3 barrels with overpairs/top pair (AA/KK on paired or 4-straight boards). c6 tried a per-barrel discount; untested properly. Note c6's opp_raised_post scan is O(n^2) in history length; rewrite as a single pass before reusing.
- Trips with a weak kicker (A9 on A-A board) valued like strong trips (house features() uses max hole rank as kicker).
- Postflop strength is a heuristic, not equity; no turn barrels as a bluff.
- Preflop: no limping/over-limping; BB vs limpers only raises top 10%.

## Testing notes
- Machine got very loaded late in the build (100 tables went from ~11s to 55s; subprocess runs timed out). tools/quick.py is an in-process paired evaluator (play_local_table, seeds 5000+t, rotating my seat) that is much faster; use it with a time budget arg.
- tools/sim.py = localsim with any bot dir as "ME" plus place histograms; tools/bigloss.py prints our decisions in hands losing >=40% of stack.
- Fields used: mixed [v2,v2,v1,nit,montecarlo,maniac,pot_odds] seed 11; nit-heavy [v2,nit,v2,nit,montecarlo,nit,v2] seed 31; mirror 7 x v2.

## Notes / next
- Tools: tools/precompute.py builds bot/eqmat.json; tools/icmtab.py builds bot/icmtab.json.
- versions/ holds snapshots for A/B tests (v1, v2, c1..c6; c5 = accepted 004).
- Next: validate c6-style call-down discipline with quick.py on 500+ paired tables; try LAM (ICM blend) 0.3 vs 0.7; widen BB defence vs steals; add turn barrels vs high fold-to-bet seats.
