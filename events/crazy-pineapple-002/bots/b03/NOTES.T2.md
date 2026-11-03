# Team b03 notes

## Strategy

**Summary:** Math-first bot. Preflop uses precomputed equities for every 3-card crazy-pineapple hand (vs 1/2/4 random hands and vs top-10/25/50% ranges, generated offline by Monte Carlo, shipped as JSON). Postflop uses a time-boxed Monte Carlo (~0.5 ms) against opponent hands that are re-weighted by how aggressive the opponent has been (bets/raises make "air" hands less likely), then compares equity to pot odds.

**Before the flop:** Hands are ranked by a percentile of equity vs random. Unopened pots: deep stacks open-raise 2.5-3 BB with a position-dependent top-X% (14% early to 55% from the SB); at <=13 BB effective (or <=18 BB late with no limpers) it plays shove/fold with a Nash-like push range c(nb)/S^0.6 by players behind. Flat calls are limited (since v10): call a raise only with a top-18% hand and equity >= pot odds + 0.08 vs the raiser's estimated range; SB completes only top 40%; BB defends a <=1.5 BB raise with top 45%. Facing a raise otherwise: estimate the raiser's range from stack depth (short stacks shove wide) and observed PFR, call/shove all-ins on ICM break-even equity, 3-bet premiums.

**After the flop:** When nobody has bet this street: MC equity vs 1-2 simulated opponents (extrapolated for more), weighted toward made hands if they called earlier streets. Facing a bet/raise: MC vs the bettor only, whose range is the top X% of hands by current strength (X = 0.58 x 50/40/33% flop/turn/river for a bet, 9% for a raise, shrunk for big bet sizes: x0.85 up to pot, x0.65 up to 2x pot, x0.5 beyond; x0.8 for each earlier street the same player bet (multi-street barrels are value-heavy); widened for aggressive bettors) plus 5% weight on the rest as bluffs/draws; equity is raised to the power of the number of distinct aggressors and x0.8 per extra passive opponent. Value-bet 60% pot at equity >= 0.66 heads-up (0.74 multiway), 85% pot at >= 0.82, shove when stack-to-pot < 1.2; semi-bluff 55% pot (30% of the time) with 0.42+ equity on flop/turn heads-up, 20% small in-position bluffs with < 0.35, 45%-pot thin bets in position at >= 0.56; facing a bet, raise/shove at equity >= 0.80, call when equity beats pot odds (+margin on the river and for big calls). Discard keeps the 2-card subset with best MC equity (common random numbers) at the turn.

**Short stacks and the points table:** Push/fold below ~13 BB (18 BB late with no limpers). Borderline shoves (0.5x-1.6x the Nash-like range) are decided by ICM: EV(shove) = P(no call)*ICM(steal) + sum over players behind of P(j calls)*[eq*ICM(win)+(1-eq)*ICM(lose)] vs ICM(fold); each player's call frequency comes from their observed VPIP. All-in calls preflop use the ICM break-even equity (Malmuth-Harville, places 1-4 exact, rest averaged) instead of chip pot odds.

**Opponents:** Tracks VPIP/PFR and postflop aggression per seat at this table; PFR sets the assumed opening range when facing raises, VPIP sets the assumed calling range vs our shoves, and the bettor's aggression factor scales how much "air" we assume in their betting range postflop.

**Last change:** v11 (011-3bc679aa) for T2 = v10 + barrel tightening: the bettor's assumed range shrinks x0.8 per earlier street they bet in this hand (hand logs showed calling down overpairs/top pair vs flop-turn-river barrels from tight bots, e.g. KK vs JJ full house, AK vs QQ set). Local tight-field test (400 tables): v11 34.2 vs v10 34.0/33.4, v9 29.6 (neutral locally, aimed at the value-heavy T1 field). v10 (010-d9d59fd8, after T1 rank 6 / 29.5 pts): fewer preflop flat calls (call-raise top 18%, SB complete 40%, BB defend 45%) and tighter bettor ranges (X x0.58, raise 9%, bluff weight 5%).

## Log
- Tables: bot/pre3.json (eq vs 1,2,4 random; hindsight best-5-of-8), bot/rng3.json (eq vs top 10/25/50% + percentile).
- Generators in work/gen_pre.py, work/gen_rng.py.

- v1 001-2946f4ce: base. v2 002-10377dd9: tighter value bets (eq>=0.66 HU), stronger range weighting vs bets (+5 pts vs v1).
- v3 003-49cc9f1c: ICM calls/shoves (+4-6 pts vs v1/v2).
- Observation: house nit finishes 2nd in ~60% of tables in my test field (survival is valuable with 100/60/40/25...).
- v4 004-49f04e74: per-opponent shove rate and call-vs-shove rate (neutral in tests, kept for robustness).
- v5 005-4b1daff0: top-X% range model facing bets (+4-5 pts vs v4).
- Tight-range variants (open x0.45-0.75, push x0.55-0.8) did NOT beat the base; parameter tweaks were within noise.
- v6 006-8ecb037d: bug fixes found from hand logs (work/logsim.py prints big losses) + tighter range params (+4 vs v5).
- v7 007-d322c0be: raise-over-our-bet = raise level; flop hero value = best keep-pair (+1.5-2.5 vs v6).
- v8 008-37e1ead7: river speedup in range MC (+6 vs v7 in one 400-table run; v6/v7/v8 differences are near noise).

## Known weaknesses / next steps
- River range equity is steep in F near the cutoff (eq ~ (x-F)/x), so even with ~250 enumerated combos the estimate swings +-0.1 in boundary spots; a smooth (ramped) range weight was tried after v9 and scored worse (36.5 vs v9 42.7/38.0 in one 400-table run), so it is not used.
- Tried and rejected: soft rank cutoff (raises equity at the boundary -> more bad calls), keep-pair valuation in the no-bet path (neutral), tighter preflop ranges (neutral/worse), tighter time budget 0.5 ms (slightly worse, likely noise).
- Preflop equities use hindsight best-5-of-8 (all 3 hole cards); real discard happens after the flop.
- No river bluff-catching model per opponent beyond aggression factor; no explicit HU-specific strategy beyond push/fold ranges.
- Testing: work/sim.py (multi-variant fields with place counts), work/logsim.py (big-loss hand dumps). Variant dirs in work/vN.
- v9 009-45c046b4: river enumeration + analytic top-X equity (+2-4 vs v8).
- Final build-phase check: v9 vs house zoo (300 tables, seed 9): 58.8 pts/table, 1st (nit 50.0, checkfold 46.2); p99 709 us, 0 substitutions. Pure survival (checkfold) scores 46 vs the zoo: busting early is costly with this points table.
- Patch-round ideas: per-opponent river bluff frequency from showdowns; HU-specific postflop aggression; faster sampler (index-based instead of rng.sample) for more MC samples on flop/turn.
- v9 vs v8 follow-up (end of build): localsim seed 21 (300 tables): v8 50.4, v6 48.4, v9 44.0, v3 35.7; work/sim.py seed 113 (400 tables, 2 copies each): v8 45.3/44.2, v9 43.8/44.1. Pooled v9-v8 is about -1 pt, i.e. noise; kept v9 (theoretically lower-variance river estimate). If patch-round results look worse on river calls, v8 (008-37e1ead7) is a safe fallback.
- Last run (localsim seed 31, 300 tables, v9 x2 + v8 + 5 house bots): v9 52.1/51.8, v8 50.0, nit 43.0; 0 substitutions, p99 701 us. Over 5 runs v8 and v9 are equal within noise; v9 stays.

## T1 result (v9 009-45c046b4)
- Rank 6/8, 29.50 pts/table (CI 27.6-31.4). Places 1st..8th: 112,126,106,97,127,146,143,143. VPIP 26%, PFR 17%, WTSD 6%, showdown win 47%, 0 subs, p99 730 us.
- Leaders: b07 37.5 (VPIP 20/PFR 17), b02 35.9 (24/19), b01 35.3 (20/16). Field is tight; our flat-calling (VPIP-PFR 9 pts vs 3-7) and early busts are the suspected leaks.
- v10 010-d9d59fd8 submitted for T2 (tighter calls preflop and postflop).
- Tried for T2, not submitted: scaling the assumed shove range by the shover's VPIP/0.30 (v11). Two 400-table seeds: v11 40.5/34.7 vs v10b 42.1/37.2/38.2/38.1, v9 41.1/39.9/35.7/35.1. Also flawed in principle: VPIP reflects deep-stack play, while push/fold bots shove wide when short regardless of VPIP.
- v10 zoo sanity (300 tables, seed 9): 57.1 pts/table, 1st (v9 was 58.8 on the same seed; within noise), 0 subs, p99 750 us.
- Tight-field test (to mimic T1: 3x 'tag' = v10 with open x0.6, push x0.85, call 12%, VPIP ~17%; plus v9 x2, v10 x2, nit), seeds 151+157, 400 tables each: v10 avg 32.7, v9 32.6, tag 32.4. All tied; kept v10 for T2. work/tag holds the tight variant.
- v11 011-3bc679aa submitted for T2: barrel tightening (x0.8 per earlier street the bettor bet). Fallbacks: v10 010-d9d59fd8, v9 009-45c046b4.
- v11 zoo sanity (300 tables, seed 9): 58.0 pts/table, 1st (v10 57.1, v9 58.8 same seed), 0 subs, p99 709 us. No breakage vs bluff-heavy house bots.
- v11 vs v10 second tight-field run (seed 173): v11 32.7/31.5 vs v10 37.2/33.8. Pooled over 2 runs v11 is ~1.8 pts behind v10 (about 1.4 sigma, not significant). My local 'tight' bots semi-bluff 15-30% (they are my own variants), so folding to barrels is penalised locally more than vs a value-heavy field. Kept v11 for T2; if T2 shows more folds-to-bets losses or a lower score than T1, revert to v10 (010-d9d59fd8).
- v11 vs v10 third run (seed 181, + montecarlo): v11 40.1/38.3 vs v10 35.2/35.1. Pooled over 3 runs: v11 35.4 (5 entries) vs v10 34.8 (6 entries) -> tied; v11 stays for T2.
