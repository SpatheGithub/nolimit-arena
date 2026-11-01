# Team b06 notes

## Strategy

**Summary:** A fast rules bot that runs in about 25 µs per decision. Before the flop it ranks hands by percentile among all 22,100 three-card starting hands. After the flop it estimates equity from the made hand plus outs. Bet and call sizes come from pot odds, a discount for multiway pots and per-seat raise frequencies. Short stacks play push/fold.

**Before the flop:** The 3-card score is the best Chen pair + 0.3×second pair + 0.1×third, turned into a percentile. With more than 14 BB it opens the top ~14% (7 players behind) up to ~50% (button/SB), sized 2.2–2.5 BB plus 1 BB per limper. It 3-bets the top ~3.5% (wider against loose raisers) and calls the top ~13% (wider for cheap prices, in position or against loose raisers). Against a 3-bet it continues with the top 2–5%.

**After the flop:** On the flop it keeps the best 2 of its 3 cards. Equity comes from hand class: sets, straights, flushes and two pair are strong; over/top/middle pair are graded by kicker and pair rank; board-only hands count as weak. Flush and straight outs add equity. It value-bets 2/3–3/4 pot when multiway-adjusted equity is at least 0.62. It c-bets 1/2 pot heads-up 55% of the time, semi-bluffs big draws and sometimes bluffs the river in position. Against a bet, it discounts equity by bet size and raise count (less against loose players), then calls if that beats the pot odds and raises at 0.75+. For the discard it keeps the pair with the best made value plus draw bonus.

**Short stacks and the points table:** At 14 BB or less it plays push/fold. The shove width grows with fewer players behind and shorter stacks (~16% from early position up to 55–90% from the SB/BB at 10 BB). It calls all-ins from pot odds, widened against loose shovers and when very short. There is no explicit ICM yet.

**Opponents:** It counts each seat's preflop raise frequency during the table (`loose()`, prior 0.25 until 6 hands). That widens 3-bet, call and reshove ranges against loose raisers and lowers the postflop discount against them.

**Last change:** First version (001-2d1d289a). T2 31.6 pts (avg 31.9); T3 34.15, 4th of 8.

## Log
- T2: 31.62 (3/4). T3: 34.15 (4/8). b08 leads at ~38 with VPIP 20 / PFR 16, tighter than us (25/19).
- Ideas: tighter early-position opens, ICM for all-in calls, better river bluff-catching.
