# Team b01 notes

## Strategy

**Summary:** Equity bot built on exact precomputed tables for the 20-card royal deck (rank counts only; flush impossible, straight flush checked at runtime). Every decision compares equity versus each opponent's estimated range (top-X% of hands by strength on the current board, narrowed by their actions and their observed stats) with pot odds / fold equity.

**Before the flop:** 15 rank classes ranked by exact heads-up equity (AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50 ... TT .37 is the worst hand, it blocks straights). Opens top 25% early to 60% on the button/SB, size 2.5bb (2.2bb at 13-22bb). Facing a raise: equity vs raiser's range (from their observed PFR) decides 3-bet (eq>=.60) / call (eq >= pot odds + 4%) / fold. At <=15bb effective: shove/fold by an EV model with fold equity from opponents' estimated calling ranges; <=18bb vs a raise: 3-bet shove or fold.

**After the flop:** exact equity vs each opponent's range (flop: one card to come, enumerated; turn = final street, exact showdown vs range). Value-bets 60-80% pot when equity vs the opponent's *calling* range (range x observed call rate) is >= 50% (HU) or share >= 1.3 multiway; as preflop raiser heads-up it c-bets half pot 80% of the time on the flop, shoves when stack <= 1.4 pot. Raises with very strong equity. Calls when equity >= pot odds + 2% (5% if committing over half the stack). Small heads-up bluff frequency when the opponent's observed fold rate is high.

**Short stacks and the points table:** points 100/25/5 are top-heavy so play is close to chip-EV; push/fold below 15bb (EV model with fold equity, opponents assumed to call with ~top 15% adjusted by their VPIP). With 3-4 players left, big calls (>=30% of stack) use an exact ICM required-equity (Malmuth-Harville, 100/25/5) instead of plain pot odds.

**Opponents:** per seat VPIP, PFR, postflop aggression and fold-to-bet with priors; used for range widths and bluff decisions.

**Last change:** 002-130c3a9a: value bets vs calling range, ICM calls at <=4 players, HU c-bets, push/fold up to 15bb with tighter assumed calling ranges. Test (800 tables, seed 11, field 4x v1 + montecarlo/nit/pot_odds): 24.4 ± 2.7 vs v1 copies 21.4 avg. Without the aggression part the change was neutral (21.4 vs 22.0).

v1 (001-e5ef784d): 43.0 ± 12 pts/table vs house zoo (60 tables).

## Notes
- Evaluator (rank counts) verified identical ordering to engine ranker on 20k random hands.
- Tables are computed at import in ~0.16 s; act() p99 ~50 us.

## Next steps / ideas
- Aggression helped (+3 pts/table vs v1): try more (wider opens/steals, turn barrels) and test.
- Preflop multiway equity is a product of heads-up equities (card removal ignored; at 8-handed all 20 cards are dealt).
- Shove ranges: calibrate with a Nash-like computation per M and players behind.
- localsim: 800 tables takes ~3.5-4 min on the busy machine.
