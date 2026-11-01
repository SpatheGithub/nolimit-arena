# Team b07 notes

## Strategy

**Summary:** Table-driven shortdeck bot. Preflop uses a precomputed 81x81 class-vs-class equity matrix (shortdeck, 3M deals) to get equity vs each opponent's estimated range, plus a chip-EV push/fold model when short. Postflop it runs a vectorized numpy Monte Carlo (360 samples, lookup-table evaluator, ~0.2 ms) against up to 3 opponents whose hands are weighted by their preflop range and, if they bet, strongly by their current made-hand strength. Betting lines are its profit source; calling is kept tight because bot bets are value-heavy.

**Before the flop:** Open-raise by position (players left to act): top ~16% UTG up to ~55% SB (75% heads-up), +8% when the players behind are tight (low VPIP), -4% when loose; 2.3-2.5bb (+1bb per limper). Facing a raise: equity vs raiser range (observed PFR; tighter for 3-bets and big sizes). All-in raisers: range from their observed shove frequency, or a stack-depth push range for <=16bb shovers. Multiway: equity vs each voluntary opponent (callers of a shove get ~top 10%) multiplied, then ^0.8. 3-bet/shove with eq>=0.60 or top 3.5%; flat small raises only with top 33% (40% when closing action) and eq >= pot odds + 5-8%; call big/all-in raises with eq >= pot odds + 2% + ICM margin. At <=13bb effective: shove-or-fold by chip EV, opponents' calling range modeled from shove size and their VPIP.

**After the flop:** Value bet 65-80% pot when equity >= 0.62 HU (higher multiway, +4% on river), larger and thinner vs opponents who rarely fold. C-bet 50% pot HU as preflop raiser with eq>=0.25, frequency scaled by the opponent's observed fold-to-bet rate; occasional turn barrels/probes. Facing bets: raise with eq>=0.78 HU; call when eq >= pot odds + margin, margin 8% (flop) / 10% (turn) / 12% (river), +3% vs passive bettors, -3% vs hyper-aggressive ones, scaled down for small bets (full margin only at >=60% pot); range narrowing vs a bettor also scales with bet size and grows with multiple barrels; ICM margin added for big/all-in calls.

**Short stacks and the points table:** Push/fold <=13bb by chip EV with a small margin; an ICM-ish margin (2-5% extra equity) for calls that risk tournament life when 5-6 players remain (bubble of the 4-paid structure), reduced for short stacks. Payouts are top-heavy (100/45/20/8) so chip accumulation dominates.

**Opponents:** Per-seat VPIP, PFR, preflop shove frequency, postflop aggression factor and fold-to-bet rate (counted from hand histories in observe()). Used for raiser/caller/shover ranges, shove-calling ranges, bluff frequency and value sizing, and how much a postflop bet narrows the range.

**Last change:** v5 (005-9c589626): call margins and bettor-range narrowing now scale with bet size (v4 folded the last 2.7bb into a 48bb pot, and folded to 15%-pot river bets); slightly tighter big-bet calls and multi-barrel narrowing. A/B 1000 tables, 3 seats each vs v4: 25.5 vs 24.1 (and +1.1 in an earlier run of the margin part).

## Log
- tables: tools/build_tables.py -> bot/tables.npz (RT 5^9 rank table, FT flush table, E 81x81 equity, EQM vs k random, PCT).
- v1 001: vs zoo 45.9 pts/table.
- v2 002: fold-rate-scaled bluffs: +0.8 (noise).
- v3 003: shove-frequency ranges for all-in raisers + multiway product equity. Leak found via instrumented copy (tools/dbg + tools/analyze.py): deep calls of preflop all-ins were -28 bb/hand (calling 100bb multiway shoves with trash due to x0.85 multiway factor). After fix: -3.7 bb/hand; points 36.3 vs v2 30.7.
- v4 004: river/turn calling-down lines were -15 bb/hand (call-call-fold) -> tightened.
- v5 005: bet-size-scaled call margins. Note: flop-call lines lose -2.0 bb/hand but folding the flop instead loses ~-2.9, so "calling-down leak" numbers must be compared against fold, not zero.
- Instrumentation: tools/dbg/ is a copy of the bot (core.py) that logs each hand's actions+payoff to tools/dbg_log.jsonl; run it as an opponent in localsim.

## T1 result (v5 005-9c589626)
- Rank 4/8, 21.16 pts/table (top: b02 24.95, b08 23.87, b06 23.50). VPIP 28% PFR 20%, aggression 2.56, WTSD 7.6%, showdown win 56%.
- Places: 1st 104, 2nd 148, 3rd 143, 4th 155, 5th 134, 6th 117, 7th 115, 8th 84. 1st is BELOW the 125 average while 2nd-4th are above: we survive but don't convert to wins. Biggest lever: short-handed/heads-up endgame aggression (wider opens/shoves at <=4 players, HU open ~80%+, wider calls of shoves HU).
- 1 hang (wall 94 ms) and cpu max 1.57 ms once in 114k decisions; probably a GC/first-call pause. Could pre-warm numpy in __init__.
- T2 patch window: no change made (the window ran out before a tested fix); v5 stays.
- READY TO TEST (in tools/dbg/core.py, NOT in bot/): endgame aggression = open threshold +0.08 more at <=3 alive, HU open >=85%, push/fold shove margin 0 at <=3 alive. Run the A/B recipe below first thing in the next window; submit only if the dbg seats beat v5.

## Known weaknesses / next
- Tested, not adopted: widen 3-bets to eq>=0.57 vs single raiser or top 4.5% (3-bets earn +5.8 bb/hand deep, flat calls only +0.13). A/B 600 tables, 3 seats each: candidate 25.03 vs v5 24.98 = no gain. Next try instead: light 3-bets only vs high-PFR openers, or 3-bet in place of marginal flats in position.
- A/B recipe: put the candidate in tools/dbg/core.py (bot/ stays = accepted), run `kit/localsim.py --opponents tools/dbg,.submissions/<cur>,tools/dbg,.submissions/<cur>,nit,montecarlo,tools/dbg --tables 600-1000`; compare the 3 dbg seats against you + 2 old seats.
- When the machine is loaded, run localsim without a `timeout` wrapper and with fewer tables; it may not even respect its 240 s budget.
- Calling down still negative (call-call-fold -14 bb/hand); maybe need made-hand based caps.
- No explicit ICM computation (margins only).
- Preflop open sizes fixed; no limp strategy.
