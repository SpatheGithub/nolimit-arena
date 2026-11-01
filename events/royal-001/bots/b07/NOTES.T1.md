# Team b07 notes

## Strategy

**Summary:** Equity-driven bot for the royal (T-A, 20-card, 4-card board) variant. Hand values are looked up from a precomputed rank-multiset table (suits only matter for straight flushes); preflop uses an exact heads-up class-vs-class equity matrix, postflop does an exact enumeration of opponent rank classes (and turn card) weighted by each opponent's estimated range.

**Before the flop:** Opens top 30% of hands with 5+ players behind, up to 65% from the button/SB (heads-up: SB raises 80% and limps the rest), to 2.5bb (+1bb per limper). AA always re-raises; short (<=30bb) strong hands jam. Facing a raise: estimates the raiser's range from their observed raise frequency, computes equity vs that range and calls/3-bets/jams when it beats the price plus a margin. With 14bb or less effective it plays push/fold using an EV model of the callers behind.

**After the flop:** Equity vs each opponent's range (raiser -> top PFR%, caller -> top VPIP%, else random), multiplied across opponents. Facing a bet on the flop or turn, the bettor's range is cut to its strongest g fraction (exact final values on the turn, precomputed flop equity on the flop; g ~0.3-0.8 from bet size and their aggression), then it calls if equity beats pot odds +2%. Bets 70% pot (pot-sized above 0.75 equity) for value when equity > 0.62 (0.55 heads-up), c-bets heads-up as preflop raiser 40% of the time when equity > 0.33, stabs the turn heads-up 15% with equity > 0.4, and raises (3x) or jams when equity vs the narrowed range is > 0.85 (> 0.75 heads-up).

**Short stacks and the points table:** Push/fold at <=14bb effective. Points 100/25/5 are top-heavy, so it plays close to chip-EV (no strong ICM tightening).

**Opponents:** Tracks per-seat VPIP, PFR and postflop aggression frequency within a table (priors with 6 pseudo-hands) and uses them for range width and call margins.

**Last change:** 003: the bettor-range narrowing now also runs on the flop (top-g fraction by a precomputed per-class flop equity table, g 0.1 wider than on the turn), and value bets are 70% pot (eq<0.75) or pot-sized (eq>=0.75). 400-table test vs 2x v002 + 5 house bots: v003 32.2+-4.2 vs v002 29.4/26.3 (positive but within noise); earlier v002 beat v001 36.0 vs 25.3/23.6 over 500 tables.

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
