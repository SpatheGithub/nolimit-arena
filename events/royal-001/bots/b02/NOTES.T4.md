# Team b02 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck, 4-card board). All equities come from exact rank-only enumeration precomputed into `bot/tables.json` (suits ignored: flushes are impossible, straight flushes are 0.16%; verified identical to the engine on 20k deals except SF). Decisions compare equity vs an estimated opponent range (from per-seat stats gathered during the table) against pot odds, with aggressive opening/stealing because the 100/25/5 payout rewards winning the table.

**Before the flop:** 15 rank classes ranked by equity vs a random hand (AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50, KJ .49 ... TT .37). Unopened: raise 2.3-2.5bb with a top fraction that widens as fewer players are left to act (24% with 5+ behind, 32% with 4, 46% with 3, 60% with 2, 62% SB vs BB, 85% SB heads-up); at 17bb or less effective it is push/fold (unopened: shove the open range, widening below 14bb as stacks shrink). Facing a raise: equity vs the raiser's estimated range = max(observed PFR, positional prior: 25% with 5+ behind, 30%/38%/48% with 4/3/2 behind, 60% from SB, >=55% heads-up, >=35% 3-handed; x0.45 after re-raises); multiway exponent counts players who called/raised as full opponents and blinds still to act as 0.3 each; 3-bet with equity >= 0.58 or AA, call when equity+implied odds (3-6%) beats the price and equity >= floor (0.38; 0.34 in BB; 0.30 heads-up; 0.45 vs re-raises), shove/call all-ins on pot odds + a small ICM margin.

**After the flop:** Equity vs each of the 15 opponent classes from the table, weighted by card removal, the opponent's preflop range, and a strength-skew when they bet/raise (stronger skew for bigger bets, weaker for aggressive seats). Multiway equity ~ eq^(1+0.75(n-1)). Value bet 60% pot (equity >= .62) or 90% pot (>= .80), shove at low SPR, raise with very strong hands, call on pot odds plus a margin, 20% stab heads-up with equity >= .42 when checked to. Heads-up (2 alive): bet-strength skew x0.6, value-bet threshold .58, no extra calling margin, stab 45% with equity >= .33.

**Short stacks and the points table:** push/fold at 17bb or less effective when first in (push fraction = open fraction, widening below 14bb as stacks shrink); all-in shove ranges assumed wider for short shovers (45% at <=8bb, 30% <=15bb, 18% <=30bb, 8% deeper, or observed if wider); all-in calls need pot odds + 2% + an ICM margin (1.5% with 5+ alive, 3% with 4, 4% with 3, 0 heads-up). Heads-up: SB opens 85%, raisers' ranges assumed >=55% HU (>=65% for HU shoves) and >=35% 3-handed; HU re-raise ranges x0.65 (not x0.45) and calling floor vs re-raises 0.38 (not 0.45). BB facing limpers isolates/shoves only with top 30% (50% HU).

**Opponents:** per-seat VPIP / PFR / preflop shove frequency / postflop aggression, with priors, used to set ranges.

**Last change:** v007: unopened push/fold now starts at 17bb effective instead of 14bb (14-17bb first-in hands are shoved with the open range instead of min-raised). Paired local tests vs 2x/3x v006 + house bots, 3x800 tables: +3.5, +1.4, +3.0 pts/table (avg +2.6, all positive). v006 before it (after T2: rank 6, HU conversion 34%) added a heads-up mode (weaker bet-strength skew, more stabs, lower value threshold, wider assumed HU ranges), avg +0.4 vs v005.

## Log
- 001: first accepted. 42 vs zoo, 54 vs montecarlo/threshold/pot_odds/nit mix.
- T3 result (v007): rank 6/8, 13.96 pts; places 1st 95, 2nd 141, 3rd 187, 4th 153, 5th 134, 6th 122, 7th 93, 8th 75; HU conversion 40% (up from 34%); VPIP 40% PFR 18% (largest call gap in field; b08 40/25 wins); cpu max 738us (p99 100us), 0 timeouts.
- 007: accepted 14:33 (push/fold cutoff 14bb -> 17bb; +2.6 avg vs v006 over 3 seeds).
- 006: accepted 14:25 (heads-up mode; avg +0.4 vs v005 over 5 paired runs).
- T2 result (v004 played; v005 was accepted after the freeze): rank 6/8, 13.48 pts; places 1st 86, 2nd 164, 3rd 156, 4th 168, 5th 153; VPIP 39% PFR 18%; HU conversion 34%. Field winners b08 (44/24), b05 (38/16), b01 (35/19).
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
- (window before T3) 3-bet threshold 0.58 -> 0.54: +1.7, +0.4, -2.7 vs v006 -> neutral, not submitted.
- (window before T3) v006 vs v005 extra seeds in standard field: +1.2, -1.35 -> v006 overall avg +0.3 over 7 runs (no regression).
- (window before T3) Per-seat short-handed (<=3 dealt in) raise stats as range floor in HU/3-handed: +0.65, -2.0 vs v006 -> not submitted.
- (window before T3) Push/fold cutoff 17 -> 20bb: -1.5, +0.8 vs v007 -> not submitted (17 kept).
- T2 sample hands (40, all early-table, our seat not marked) showed no clear misplay by us; no short-handed hands sampled.
- (window before T4, all vs v007, 800 tables each; none submitted):
  - wider 3-4 handed raiser/shover priors (3h 0.42/0.50, 4h 0.30/0.38): -1.4, -3.7
  - postflop call margin 0.03/0.01 -> 0.06/0.04 (non-HU): +0.6, -0.2
  - wider defense vs 3-bets (range x0.55, floor 0.41): -0.9, -0.5
  - looser HU (BB floor 0.25, BB raise over HU limp 65%): -5.0 (second seed timed out)
  - tighter short-stack push widening (0.6 -> 0.25 factor below 14bb): -2.3 (400 tables, machine overloaded so only one seed) -> not submitted. Rationale was: field bots likely call shoves with equity-vs-random > pot odds (~top 55-60%), so shoving 75% 3-handed (down to KT/QJ) is about -0.5bb per shove. Test first next window.
  - steal ranges adapted to blinds' observed fold-to-open rate (prior 0.6, +-0.12-0.15): -2.2 (one seed; second timed out) -> not submitted.
- ICM check: with 100/25/5 an equal-stack all-in call needs ~54-55% equity at 3-4 left and ~54% at 8 left (vs 50% chip-EV); current margins (+3.5-6%) are about right.

## Known weaknesses / next steps
- v007 sanity vs fast house bots (300 tables, seed 21): 52.7 pts/table, VPIP 49%, 0 substitutions (v005 50.5, v002 51.2 on the same seed); v007 vs 2x v005 (800 tables): 32.8 vs 30.4 avg.
- HU conversion: T1 32%, T2 34% (v003/v004), T3 40% (v007 with HU mode). Still busting 3rd often (187/1000 in T3).
- Tried per-seat short-handed raise stats (not better locally); local fields can't measure HU vs strong LAGs, so judge HU changes on T3 conversion rate.
- Multiway equity is a crude power approximation (eq^(1+0.75(n-1))).
- No position-aware postflop play; no check-raise bluffs; bluff frequency fixed.
- Fold-to-steal adaptive opens tried (-2.2, one seed); not adopted.
- Straight flushes ignored (0.16%).
- Tests: `python kit/localsim.py --opponents .submissions/001-2b20e6ae,nit,pot_odds,.submissions/001-2b20e6ae,maniac,minraiser,threshold --tables 800` for paired comparison.
