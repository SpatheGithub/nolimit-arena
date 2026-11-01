# Team b01 notes

## Strategy

**Summary:** Equity bot built on exact precomputed tables for the 20-card royal deck (rank counts only; flush impossible, straight flush checked at runtime). Every decision compares equity versus each opponent's estimated range (top-X% of hands by strength on the current board, narrowed by their actions and their observed stats) with pot odds / fold equity.

**Before the flop:** 15 rank classes ranked by exact heads-up equity (AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50 ... TT .37 is the worst hand, it blocks straights). Opens top 25% early to 60% on the button/SB, size 2.5bb (2.2bb at 13-22bb). Facing a raise: equity vs the last raiser's range (from their observed PFR; other callers/raisers count softly as eq^0.6; players still to act enter as an 8%-per-player chance of a top-8% hand) decides 3-bet (eq>=.60) / call (eq >= pot odds + 4%) / fold. At <=15bb effective: shove/fold by an EV model with fold equity from opponents' estimated calling ranges; <=18bb vs a raise: 3-bet shove or fold.

**After the flop:** exact equity vs each opponent's range (flop: one card to come, enumerated; turn = final street, exact showdown vs range). Value-bets 60-80% pot when equity vs the opponent's *calling* range (range x observed call rate) is >= 50% (HU) or share >= 1.3 multiway; as preflop raiser heads-up it c-bets half pot 80% of the time on the flop, shoves when stack <= 1.4 pot. Raises with very strong equity. Each opponent bet/raise narrows their assumed range by a factor 0.55 + 0.5 x their observed aggression (was 0.35 in 003, 0.45 in 004), so it calls bets more readily. Calls when equity >= pot odds + 2% (5% if committing over half the stack). Small heads-up bluff frequency when the opponent's observed fold rate is high.

**Short stacks and the points table:** points 100/25/5 are top-heavy so play is close to chip-EV; push/fold below 15bb (EV model with fold equity, opponents assumed to call with ~top 15% adjusted by their VPIP). With 3-4 players left, big calls (>=30% of stack) use an exact ICM required-equity (Malmuth-Harville, 100/25/5) instead of plain pot odds.

**Opponents:** per seat VPIP, PFR, postflop aggression and fold-to-bet with priors; used for range widths and bluff decisions.

**Last change:** 005-2d9e4803: range narrowing per opponent bet raised again, 0.45 -> 0.55 + 0.5*agg (still looser calling). Test: 3 seeds (seeds 51/61/71, 400/400/700 tables), 3x variant + 4x 004 + montecarlo: +2.3, +1.1, +1.7 pts/table, each within noise but all positive.

004-675d653e: looser postflop calling (LOOSE_CALL: each opponent bet now narrows their range by 0.45 + 0.5*agg instead of 0.35 + 0.5*agg), because T1 showed a 61% showdown win rate with only 11% WTSD, a sign of over-folding. Test vs 3x 003 + 002 + montecarlo/nit/maniac, 500 tables x 2 seeds: seed 31 23.5 vs 21.2 avg, seed 41 26.0 vs 19.5 avg (about +4.4 pooled).

003-855c1318: fixed the preflop facing-raise equity (players behind over-penalized; the raiser and 3-bettor equities were multiplied, so KK could fold to a 3-bet). Test: 22.7 vs 21.4 (noise level). Wider opens tested worse (20.1 vs 21.6), so WIDE_OPEN stays off.

002-130c3a9a (T1, rank 4/8, 16.85 pts/table): value bets vs calling range, ICM calls at <=4 players, HU c-bets, push/fold up to 15bb. Test: 24.4 ± 2.7 vs v1 copies 21.4 avg.

v1 (001-e5ef784d): 43.0 ± 12 pts/table vs house zoo (60 tables).

## Notes
- Evaluator (rank counts) verified identical ordering to engine ranker on 20k random hands.
- Tables are computed at import in ~0.16 s; act() p99 ~50 us.

## Next steps / ideas
- Aggression helped (+3 pts/table vs v1): try more (wider opens/steals, turn barrels) and test.
- Preflop multiway equity is a product of heads-up equities (card removal ignored; at 8-handed all 20 cards are dealt).
- Shove ranges: calibrate with a Nash-like computation per M and players behind.
- localsim: 800 tables takes ~3.5-4 min on the busy machine.

## T1 results (002-130c3a9a)
- Rank 4/8, 16.85 ± 2.0 pts/table; places nearly uniform (1st 12.7%, 8th 12.7%). VPIP 32 / PFR 19, WTSD 11%, showdown win 61% (we may fold too much to aggression).
- Winner b08 is loose-aggressive (VPIP 45, PFR 26); others 22-37 VPIP.
- sample_hands.json only covers the first 10 hands of 4 tables (level 1), so it says nothing about late-stage play.
- Flags in agent.py: AGGR (c-bets/shove widening, on), FIX (preflop facing-raise fix, on), WIDE_OPEN (wider opens, off: tested worse), LOOSE_CALL (looser postflop calls, on).
- Next ideas: go further in the looser-calling direction (0.5 base) and test; shove ranges by a Nash-like computation; check late-stage (3-4 players) play.
- Exploratory (not submitted): variants/loose55 (range narrowing per bet 0.55 + 0.5*agg). 400 tables seed 51, 3x loose55 + 4x 004 + montecarlo: loose55 avg 19.0 vs 004 avg 16.7 (within noise). Next window: confirm on another seed, then submit if it still holds.
- loose55 second seed (61, 400 tables): loose55 avg 18.4 vs 004 avg 17.3. Pooled about +1.7, within noise, so it was not submitted; 004 stays active. Next: a bigger test (1000+ tables) before submitting it.
- UPDATE: after a third seed (71, 700 tables: +1.7), loose55 was submitted as 005-2d9e4803 (active). The 'not submitted' lines above are superseded.
