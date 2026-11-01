# Team b02 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck, 4-card board). All equities come from exact rank-only enumeration precomputed into `bot/tables.json` (suits ignored: flushes are impossible, straight flushes are 0.16%; verified identical to the engine on 20k deals except SF). Decisions compare equity vs an estimated opponent range (from per-seat stats gathered during the table) against pot odds, with aggressive opening/stealing because the 100/25/5 payout rewards winning the table.

**Before the flop:** 15 rank classes ranked by equity vs a random hand (AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50, KJ .49 ... TT .37). Unopened: raise 2.3-2.5bb with a top fraction that widens as fewer players are left to act (24% with 5+ behind, 32% with 4, 46% with 3, 60% with 2, 62% SB vs BB, 85% SB heads-up); at 14bb or less effective it is push/fold with wider ranges as stacks shrink. Facing a raise: equity vs the raiser's estimated range (observed PFR with prior; tighter after re-raises); 3-bet with equity >= 0.60 or AA, call when equity+implied odds beats the price, shove/call all-ins on pot odds + a small ICM margin.

**After the flop:** Equity vs each of the 15 opponent classes from the table, weighted by card removal, the opponent's preflop range, and a strength-skew when they bet/raise (stronger skew for bigger bets, weaker for aggressive seats). Multiway equity ~ eq^(1+0.75(n-1)). Value bet 60% pot (equity >= .62) or 90% pot (>= .80), shove at low SPR, raise with very strong hands, call on pot odds plus a margin, 20% stab heads-up with equity >= .42 when checked to.

**Short stacks and the points table:** push/fold below 14bb effective (push fraction widens as stacks shrink); all-in shove ranges assumed wider for short shovers (45% at <=8bb, 30% <=15bb, 18% <=30bb, 8% deeper, or observed if wider); small ICM margin (+1.5-4% equity) when calling all-ins with 3-4 players left. Heads-up: SB opens 85%, raisers' ranges assumed >=55% HU and >=35% 3-handed. BB facing limpers isolates/shoves only with top 30% (50% HU).

**Opponents:** per-seat VPIP / PFR / preflop shove frequency / postflop aggression, with priors, used to set ranges.

**Last change:** v003: widened late-position opens/steals (2 behind 52%->60%, 3 behind 40%->46%). Paired local tests vs 2x v002 + 5 house bots, 2x800 tables: v003 32.3/31.3 vs v002 avg 30.2/30.5 pts/table (small, within-noise gain). v002 before it fixed BB raising/shoving any two over limpers, widened heads-up/3-handed ranges, added stack-aware shove-range priors and bigger value bets (34.3 vs v001 avg 32.0).

## Log
- 001: first accepted. 42 vs zoo, 54 vs montecarlo/threshold/pot_odds/nit mix.
- 003: accepted 13:32 (wider steals, see Last change).
- 002: accepted. v002 34.3 vs v001 avg 32.0 (800 paired tables). Self-play noise is ~±3 pts at 600 tables; changes were roughly neutral-to-positive.

## Known weaknesses / next steps
- Multiway equity is a crude power approximation (eq^(1+0.75(n-1))).
- No position-aware postflop play; no check-raise bluffs; bluff frequency fixed.
- Open ranges not adapted to blinds' fold-to-steal frequency yet (next: widen steals vs tight blinds).
- Straight flushes ignored (0.16%).
- Tests: `python kit/localsim.py --opponents .submissions/001-2b20e6ae,nit,pot_odds,.submissions/001-2b20e6ae,maniac,minraiser,threshold --tables 800` for paired comparison.
