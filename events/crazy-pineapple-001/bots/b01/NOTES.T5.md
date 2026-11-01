# Team b01 notes

## Strategy

**Summary:** Preflop the bot ranks every 3-card hand with a Chen-score heuristic (best two-card pair plus a little credit for the other pairs) and plays by percentile ranges that depend on seat. Postflop it runs a Monte Carlo equity estimate with a time budget (about 0.3 ms) against random hands, using a fast table-driven evaluator stored in bot/evtab.bin. It then value-bets, calls on pot odds after a penalty for bet size, or folds.

**Before the flop:** Opens with the top 14% of hands when 7 players are behind it, widening to 40% when only the blinds are left. Opens to 2.5bb plus 1bb per limper, or 3bb in late position. Calls a raise with the top 11% if it's cheap; defends the big blind with the top 28% against raises of 3bb or less; 3-bets the top 3.5%; shoves the top 1.5% against a 4-bet.

**After the flop:** It estimates equity against the number of opponents still in. On the flop, while opponents still hold 3 cards, it raises equity to the power 1.15 to discount it. Bets 66% of the pot when equity is above 0.62 heads-up (lower multiway), and c-bets 55% of the time heads-up on the flop as the preflop raiser. Facing a bet, it subtracts 0.04 + 0.10×(bet/pot) from equity, then calls on pot odds or raises with very strong hands. For the discard it keeps the pair with the best average strength over all possible turn cards.

**Short stacks and the points table:** At 13bb or less it plays push/fold: the open-shove range widens as stacks shrink and in late position. It calls shoves when the estimated equity against the shover's range beats the price by a margin; the margin grows from 0.04 to 0.07 when 4 or fewer players are left, as an ICM caution.

**Opponents:** Tracks each seat's preflop raise frequency (with a prior of 20%) and uses it as the assumed range width when that seat raises or shoves.

**Last change:** First version (001-1594ea78). check_bot passed: p99 about 0.5 ms, no substitutions.

## Log
- 001-1594ea78: first accepted bot (missed T1 because nothing had been accepted before the build phase ended).

## Next steps
- Replace the heuristic preflop table with a precomputed equity table.
- Opponent-adaptive calling, plus more ICM work near the bubble.
