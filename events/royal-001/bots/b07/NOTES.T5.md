# Team b07 notes

## Strategy

**Summary:** Equity-driven, fairly tight-aggressive bot for the royal (T-A, 20-card, 4-card board) variant. Hand values come from a precomputed rank-multiset table (suits only matter for straight flushes); preflop uses an exact class-vs-class equity matrix, postflop an exact enumeration of opponent rank classes (and turn card) weighted by each opponent's estimated range, narrowed when they bet. Submission 009-6f909ae0 = the T1 bot (003) plus per-opponent learning of how often each seat calls preflop shoves, wider assumed opener/shover ranges short-handed, a fix for over-shoving against small all-ins, and multiway value bets.

**Before the flop:** First in it opens the top 30% of hands with 5+ players behind, 40% with 3-4, 50% with 2 and 65% with 1 (heads-up: SB raises 80%, limps the rest), to 2.5bb (+1bb per limper). Facing a raise it estimates the raiser's range from their observed raise frequency (floored short-handed: heads-up opens >= 65% and shoves >= 75% of hands, 3-handed 40%/50%, SB vs BB 50%) and calls only when equity vs that range > pot odds + 0.06 and > 0.42; it re-shoves at <=22bb with equity > 0.5; AA always re-raises; calls that commit 40%+ of the stack become shoves when equity > pot odds + 0.03; facing a small all-in (under 40% of our stack) it just calls unless equity vs the shover is >= 0.6 (then it isolates with a shove).

**After the flop:** Equity vs each opponent's range (raiser -> top PFR%, caller -> top VPIP%, else random), multiplied across opponents. Facing a bet on the flop or turn, the bettor's range is cut to its strongest g fraction (exact final values on the turn, precomputed per-class flop equity on the flop; g = 0.32 + 0.6*aggression - 0.12*bet/pot, +0.1 on the flop, clipped 0.12-0.9), then it calls if equity beats pot odds +2% and raises/jams above 0.85 (0.75 heads-up). Bets 70% pot (pot-sized above 0.75 equity) for value when its chance to beat everyone exceeds 0.55 heads-up, 0.52 vs 2, 0.42 vs 3, 0.36 vs 4+ (fair share is 1/(n+1)); c-bets heads-up as preflop raiser 40% of the time with equity > 0.33 and stabs the turn 15% with equity > 0.4.

**Short stacks and the points table:** Push/fold at <=14bb effective: shove when the chip EV of shoving beats folding. Each player behind is assumed to call with the top c of hands, where c starts at 18-30% (wider when we are shorter, scaled by sqrt(their VPIP/0.4)) and is then blended with that seat's observed call rate against preflop shoves at this table (3 pseudo-observations of the prior), clipped 8-85%. Calls all-ins when equity vs the shover's estimated range beats pot odds + 0.03. Points 100/25/5: almost all points come from 1st place, so it stays chip-EV and does not tighten for survival.

**Opponents:** Tracks per seat within a table: VPIP, PFR, postflop raise-vs-call frequency, and how often they call when facing a preflop shove (start stacks recovered as stack after hand minus payoff). These set raiser/caller ranges, the bettor-range narrowing and the shove calling rates.

**Last change:** 009-6f909ae0 (for T5): multiway value betting. Equity is the chance to beat all opponents, and the old fixed 0.62 bet threshold meant a hand beating each of 3 opponents 80% of the time (product ~0.51) was checked; loose fields (every other team VPIP 35-40%) make multiway pots common. Threshold now 0.55 HU / 0.52 vs 2 / 0.42 vs 3 / 0.36 vs 4+. Local check (400 tables, seed 91, field 2x 008, v003, v004, v002, nit, montecarlo): 18.8 vs 008 19.9/18.1; seed 92: 18.8 vs 008 17.1/16.7 (about +0.9 over 008 across both); zoo 43.4; 0 errors. A matching multiway raise-threshold change (v010) tested worse on seed 92 and was dropped. Earlier changes kept from 008: shove model with v003 call rates plus learned per-seat call-vs-shove rates; short-handed range floors; small-all-in call fix.

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

## T2 result (bot 004-b0291885)
- Rank 8/8, 11.10 pts/table. Places 1st..8th: 84 88 100 127 123 129 170 179. VPIP 37% PFR 22%, WTSD 16.7%, showdown win 54%.
- Leaders: b08 21.5 (44/24), b05 19.0 (38/16), b01 18.3 (35/19). The extra passive calling of v004 was the leak; local self-play fields ranked v004 first, so local tests vs my own versions do NOT predict the real field.
- Patch for T3: back to v003 + wider assumed callers in push EV (submission 005-7ba3b974).
- 005-7ba3b974 vs house zoo (300 tables, seed 5): 44.3 pts/table (montecarlo 24.8), 0 substitutions.
- Next ideas: if T3 still shows many 6th/7th finishes, look at calling all-ins (f = max(PFR, 0.2+3/bb)) and the 14-25bb open/fold zone; avoid adding passive calls.
- sample_hands.json only holds the first 10 hands of 4 tables (blinds 10/20): useless for mid-game leaks. Our seat can be inferred by eliminating seats whose shown cards differ from our hole cards.
- 005-7ba3b974, seed 73 (600 tables, same field): 20.4 vs v003 19.5/16.1, v004 21.1/20.9. Over seeds 72+73 it averages ~19.3 vs v003 ~17.7: level-to-slightly-better than the T1 bot, no regressions.
- 006-89ccc8d8 (= 005 + small-all-in call fix), seed 73: 19.8 vs v003 19.5/18.4 (005 scored 20.4 on that seed; within noise). Submitted on reasoning: shoving 30bb over a 3bb all-in with a marginal hand risks the stack against players behind.
- 006-89ccc8d8 vs house zoo (300 tables, seed 5): 41.1 pts/table (005 scored 44.3 on the same seed; within +-5.4 noise), 0 substitutions.
- Idea not done: in multiway pots treat players who already called a bet with a narrowed range too (now only the bettor's range is narrowed).

## T3 result (bot 006-89ccc8d8)
- Rank 8/8, 12.10 pts/table. Places 1st..8th: 81 132 139 173 135 132 104 104. VPIP 24% PFR 17%, WTSD 11.2%, showdown win 59%.
- Points arithmetic: T1 = 111*100 + 115*25 + 115*5 = 14.55; T3 = 81*100 + 132*25 + 139*5 = 12.10. Wins are everything.
- Leaders: b08 20.5 (40/25), b05 19.5 (38/16), b03 17.3 (35/24).
- Patch for T4: 007-7f710850 (see Last change).
- 008-a9854893 = 007 + short-handed range floors: seat-73 field 17.7 vs v003 17.3/17.1, v006 18.6; 1 wall-clock 'hang' under machine load (CPU max 314 us).
- T4 window: machine saturated, zoo sanity runs for 008 could not finish in time (background output in runs/v008_zoo.txt if it completes). 008 passed check_bot and submit smoke with 0 substitutions.
- 008 vs house zoo (only 40 tables, machine saturated): 45.5+-15 pts/table, 1st; 0 substitutions, CPU max 198 us. Consistent with 005-007 (41-47).
- 008, seed 81 (300 tables, field 2x v003, v004, v006, v002, nit, montecarlo): 17.5 vs v006 20.1, v003 19.6/19.1, v002 19.1, v004 17.7 -- all within +-4 noise; 0 substitutions. Local self-play fields have not predicted real results (v004 topped them, finished last in T2).

## T4 result (bot 008-a9854893)
- Rank 7/8, 12.91 pts/table. Places 1st..8th: 92 120 142 143 144 161 108 90. HU conversion 43% (T1 49%, T3 38%). VPIP 25% PFR 17%, WTSD 11.5%, showdown win 59%.
- Leaders: b05 21.0 (37/16, loose-passive), b03 18.6 (35/24), b08 17.8 (40/25). Every other team plays VPIP 35-40%; we are the tightest at 25%.
- Patch for T5: 009-6f909ae0, multiway value bets (see Last change).
- 009, seed 92 (400 tables, field 2x 008, 2x v004, v002, v003, montecarlo): 18.8 vs 008 17.1/16.7. Two seeds together: 009 ~+0.9 over 008, 0 errors.
- Tried v010 = 009 + multiway raise threshold scaled like the bet threshold (0.75 HU, 0.73/0.61/0.5 vs 2/3/4+): seed 92 15.9 vs 008 20.0/18.8 -> dropped, not submitted.
- 009 vs house zoo (300 tables, seed 5): 43.4 pts/table (008 41.8, 006 41.1, 005 44.3 on the same seed), 0 substitutions.
- 009, seed 93 (500 tables, same field as seed 92): 17.8 vs 008 20.4/18.5. Over seeds 91/92/93 009 minus 008 = -0.15/+1.9/-1.7, about 0 on average: level locally. Kept 009 because the change targets multiway pots, which my tight local fields rarely produce but the loose real field (VPIP 35-40%) does.
- 009 in a looser field (500 tables, seed 94: 2x 008, 2x montecarlo, pot_odds, maniac, v004): 24.1 vs 008 26.3/23.1 -- level. No local test separates 009 from 008.
