# Team b02 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck, 4-card board). All equities come from exact rank-only enumeration precomputed into `bot/tables.json` (suits ignored: flushes are impossible, straight flushes are 0.16%; verified identical to the engine on 20k deals except SF). Decisions compare equity vs an estimated opponent range (from per-seat stats gathered during the table) against pot odds, with aggressive opening/stealing because the 100/25/5 payout rewards winning the table.

**Before the flop:** 15 rank classes ranked by equity vs a random hand (AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50, KJ .49 ... TT .37). Unopened: raise 2.3-2.5bb with a top fraction that widens as fewer players are left to act (24% with 5+ behind, 32% with 4, 46% with 3, 60% with 2, 62% SB vs BB, 85% SB heads-up); at 14bb or less effective it is push/fold with wider ranges as stacks shrink. Facing a raise: equity vs the raiser's estimated range = max(observed PFR, positional prior: 25% with 5+ behind, 30%/38%/48% with 4/3/2 behind, 60% from SB, >=55% heads-up, >=35% 3-handed; x0.45 after re-raises); multiway exponent counts players who called/raised as full opponents and blinds still to act as 0.3 each; 3-bet with equity >= 0.58 or AA, call when equity+implied odds (3-6%) beats the price and equity >= floor (0.38; 0.34 in BB; 0.30 heads-up; 0.45 vs re-raises), shove/call all-ins on pot odds + a small ICM margin.

**After the flop:** Equity vs each of the 15 opponent classes from the table, weighted by card removal, the opponent's preflop range, and a strength-skew when they bet/raise (stronger skew for bigger bets, weaker for aggressive seats). Multiway equity ~ eq^(1+0.75(n-1)). Value bet 60% pot (equity >= .62) or 90% pot (>= .80), shove at low SPR, raise with very strong hands, call on pot odds plus a margin, 20% stab heads-up with equity >= .42 when checked to.

**Short stacks and the points table:** push/fold below 14bb effective (push fraction widens as stacks shrink); all-in shove ranges assumed wider for short shovers (45% at <=8bb, 30% <=15bb, 18% <=30bb, 8% deeper, or observed if wider); all-in calls need pot odds + 2% + an ICM margin (1.5% with 5+ alive, 3% with 4, 4% with 3, 0 heads-up). Heads-up: SB opens 85%, raisers' ranges assumed >=55% HU and >=35% 3-handed. BB facing limpers isolates/shoves only with top 30% (50% HU).

**Opponents:** per-seat VPIP / PFR / preflop shove frequency / postflop aggression, with priors, used to set ranges.

**Last change:** v005: in the facing-a-raise equity, blinds that have not acted yet count as 0.3 of an opponent instead of a full one (v004 counted every seat with chips in, over-folding vs single raises; counting them as 0 was too loose: -2.6). Paired local tests vs 2x v004 + 5 house bots, 2x800 tables: v005 34.6/34.0 vs v004 avg 30.4/30.6 pts/table (+3.8), VPIP ~52%. v004 before it (after T1 rank 7, VPIP 22%) added positional raiser-range priors and a lower calling floor: +7.8 vs v003.

## Log
- 001: first accepted. 42 vs zoo, 54 vs montecarlo/threshold/pot_odds/nit mix.
- 005: accepted 14:13 (blinds yet to act weigh 0.3 in multiway exponent; +3.8 vs v004 over 2 seeds).
- 004: accepted 13:47 (looser vs raises; +7.8 pts vs v003 in paired test).
- T1 result (v003): rank 7/8, 13.40 pts/table; places 1st 82, 2nd 176, 3rd 161; VPIP 22% (field 24-45%, winners loosest: b08 45/26). Too tight, poor HU conversion.
- 003: accepted 13:32 (wider steals).
- 002: accepted. v002 34.3 vs v001 avg 32.0 (800 paired tables). Self-play noise is ~±3 pts at 600 tables; changes were roughly neutral-to-positive.

## Patch window before T2 experiments (not submitted)
- Weaker postflop bet-strength skew (pw 0.6+0.6b -> 0.4+0.45b): 32.5 vs v004 avg 33.4 (800 tables) -> reverted.
- Wider early opens (5+ behind 24%->31%, 4 behind 32%->38%): +2.5 on seed 42, -4.5 on seed 43 -> net -1, not submitted.
- Count only voluntary callers/raisers (not blinds) as opponents in the preflop facing-raise multiway exponent: VPIP 58%, 31.1 vs v004 avg 33.7 -> reverted (the blind-counting acts as useful tightening; revisit with a softer weight, e.g. 0.3 per unacted blind).
- (window before T3) Postflop multiway exponent 0.75 -> 0.6: +0.5 / -0.1 vs v005 over 2x800 tables -> neutral, not submitted.
- (window before T3) Looser heads-up (BB call floor 0.30 -> 0.25, BB raise over HU limp 50% -> 65%): -0.1 / +2.7 vs v005 -> +1.3 avg, within noise; candidate to retest with more tables.
- ICM check: with 100/25/5 an equal-stack all-in call needs ~54-55% equity at 3-4 left and ~54% at 8 left (vs 50% chip-EV); current margins (+3.5-6%) are about right.

## Known weaknesses / next steps
- v005 sanity vs fast house bots (300 tables, seed 21): 50.5 pts/table, VPIP 50%, 0 substitutions (v002 scored 51.2 on the same seed).
- After T2: check heads-up conversion (1st vs 2nd count) and VPIP vs field; v004 should be ~45% VPIP.
- Multiway equity is a crude power approximation (eq^(1+0.75(n-1))).
- No position-aware postflop play; no check-raise bluffs; bluff frequency fixed.
- Open ranges not adapted to blinds' fold-to-steal frequency yet (next: widen steals vs tight blinds).
- Straight flushes ignored (0.16%).
- Tests: `python kit/localsim.py --opponents .submissions/001-2b20e6ae,nit,pot_odds,.submissions/001-2b20e6ae,maniac,minraiser,threshold --tables 800` for paired comparison.
