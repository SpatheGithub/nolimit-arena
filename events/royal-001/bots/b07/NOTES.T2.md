# Team b07 notes

## Strategy

**Summary:** Equity-driven bot for the royal (T-A, 20-card, 4-card board) variant. Hand values are looked up from a precomputed rank-multiset table (suits only matter for straight flushes); preflop uses an exact heads-up class-vs-class equity matrix, postflop does an exact enumeration of opponent rank classes (and turn card) weighted by each opponent's estimated range.

**Before the flop:** Loose-aggressive because equities are compressed here (even JT has ~37% vs a top-20% raising range). First in it opens the top 40% of hands with 5+ players behind, 50% with 3-4, 60% with 2 and 75% with 1 (heads-up: SB raises 80% and limps the rest), to 2.5bb (+1bb per limper). Facing a raise it estimates the raiser's range from their observed raise frequency and calls when equity vs that range > pot odds + 0.04 and > 0.35 (so the big blind defends wide); it re-shoves at <=25bb with equity > 0.47; AA always re-raises. With 14bb or less effective it plays push/fold with an EV model of the callers behind.

**After the flop:** Equity vs each opponent's range (raiser -> top PFR%, caller -> top VPIP%, else random), multiplied across opponents. Facing a bet on the flop or turn, the bettor's range is cut to its strongest g fraction (exact final values on the turn, precomputed per-class flop equity on the flop; g = 0.4 + 0.6*aggression - 0.12*bet/pot, +0.1 on the flop, clipped 0.12-0.9), then it calls if equity beats pot odds +2% and raises/jams above 0.85 (0.75 heads-up). Bets 70% pot (pot-sized above 0.75 equity) for value when equity > 0.62 (0.55 heads-up); c-bets heads-up as preflop raiser 40% of the time with equity > 0.33 and stabs the turn 15% with equity > 0.4.

**Short stacks and the points table:** Push/fold at <=14bb effective. Points 100/25/5 are top-heavy, so it plays close to chip-EV (no strong ICM tightening).

**Opponents:** Tracks per-seat VPIP, PFR and postflop aggression frequency within a table (priors with 6 pseudo-hands) and uses them for range width and call margins.

**Last change:** 004 (for T2): T1 showed v003 too tight (VPIP 24%, 6th of 8; it rarely finished 8th but won only 11.1% of tables, while the top teams played VPIP 35-45%). So: wider opens (+10 points per position), call-vs-raise floor 0.42 -> 0.35 and margin 0.06 -> 0.04, re-shove at <=25bb with eq > 0.47, committed calls margin 0.03 -> 0.015, postflop bettor range g +0.08. 400 tables vs 3x v003, 2x v002, nit, montecarlo (seed 31): v004 20.5 vs v003 21.4/18.6/16.5, VPIP 45% PFR 28%. Sanity vs house zoo (250 tables): 47.3 pts/table (v001 scored 33.2 on that field).

## Notes
- Variant facts: every 6-card hand is at least two pair; straight = all five ranks present, all straights tie; flush only as straight flush.
- HU equity vs random: AA .676, AK .600, KK .598, AQ .567, AJ .535, KQ .525, QQ .524, AT .504, KJ .492, KT .462, QJ .455, JJ .444, QT .425, JT .395, TT .363.
- Tools: tools/pre.py (rank evaluator, verified vs house ranker, 0 mismatches), tools/pre2.py (writes bot/pre.json).

## Test log (localsim, field = 2 copies of a previous version + montecarlo, nit, threshold, pot_odds, maniac)
- v001 vs zoo (150 tables): 33.2 pts/table, montecarlo 29.3.
- v002 (turn narrowing + HU widening + committed calls shove) vs 2x v001 (500 tables): 36.0+-3.9 vs 25.3/23.6. Submitted as 002-62374d54.
- v4 = v002 + value bets 70% pot (eq<0.75) / 100% pot (eq>=0.75): vs 2x v002 (500 tables) 29.8 vs 30.5/26.6, neutral.
- v5 = v4 + flop narrowing (precomputed per-class flop equity table FE in pre.json, g +0.1 on the flop): vs 2x v002 (400 tables) 32.2+-4.2 vs 29.4/26.3. Submitted as 003-71a8c559.

## Known weaknesses / next ideas
- No ICM at all (payouts 100/25/5 are top-heavy so chip-EV is close, but 3-handed spots could use it).
- Opponent calling ranges vs our shoves are guessed (0.18-0.30 scaled by VPIP); track actual call-vs-allin frequency.
- No postflop raise-bluffs; flop c-bet bluff only heads-up as preflop raiser.
- Flop with made straight vs a bet only calls unless eq>0.75 heads-up; could raise more for value.
- Sims are noisy: 500 tables gives about +-3.5 pts/table.
- Confirmation (300 tables, field 2x v002, 2x v001, montecarlo, nit, pot_odds): v003 25.1+-4.4, v002 22.8/22.5, v001 21.2/17.6. Ordering v003 > v002 > v001 holds again.
- Patch-window ideas: raise made straights on the flop for value; track opponents' actual call-vs-shove frequency; light ICM 3-handed.

## T1 result (bot 003-71a8c559)
- Rank 6/8, 14.55 pts/table. Places 1st..8th: 111 115 115 136 130 149 154 90. VPIP 24% PFR 18%, WTSD 10.5%, showdown win 58%.
- Leaders: b08 20.45 (VPIP 45 PFR 26), b05 18.5 (37/16), b06 18.5 (35/21). Looser bots won more.
- Patch: loosened (see Last change). Intermediate step (opens widened, floor 0.39): 18.8 vs v003 avg 19.3 (neutral); floor 0.35: 20.5 vs v003 avg 18.8.
- v004 vs house zoo (250 tables, seed 5): 47.3 pts/table, VPIP 51% PFR 45%, 0 substitutions.
- Next ideas: push/fold cutoff 14bb -> 16bb and wider assumed calling ranges (looser real field); look at T2 places to see whether the 4th-7th pile-up moved to 1st/2nd.
- Tried push/fold cutoff 16bb (vs 4x v004, v003, nit, montecarlo; 300 tables seed 41): 20.2 vs v004 copies avg 18.7, within noise; not submitted, reverted. One 'hang' (wall > 50 ms, CPU only 193 us) seen under machine load.
- Started a value-bet-threshold experiment (0.62/0.55 -> 0.58/0.52); the run was stopped before testing, the edit was reverted, nothing submitted. Untested idea for a later window.
- Read-only check (300 tables, seed 51; field 2x v003, 2x v002, v001, nit, montecarlo): v004 18.6 vs v003 22.3/20.1, v002 25.2/13.5. Together with seed 31 (v004 20.5 vs v003 avg 18.8), v004 and v003 are level against my own versions; kept v004 because T1's real field rewarded loose play. Use the T2 result to decide whether looseness helped.
- Same field, seed 61 (300 tables): v004 22.3 (1st) vs v003 21.4/20.6, v002 19.6/18.4. Over seeds 31/51/61 v004 averages ~20.5 vs v003 ~20.7: level against my own versions, no regressions, 0 substitutions.
