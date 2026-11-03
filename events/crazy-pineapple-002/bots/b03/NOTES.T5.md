# Team b03 notes

## Strategy

**Summary:** Math-first bot. Preflop uses precomputed equities for every 3-card crazy-pineapple hand (vs 1/2/4 random hands and vs top-10/25/50% ranges, Monte Carlo offline, shipped as JSON) under the keep-two rule: a hand's showdown value is the best of its three 2-card subsets with the board (since v13; before that the tables let all 3 hole cards play, which badly overrated suited/connected 3-card hands). Postflop uses a time-boxed Monte Carlo (~0.5 ms) against the bettor's estimated range (top X% by current strength, narrower for raises, big bets and multi-street barrels), then compares equity to pot odds; short stacks play ICM-aware push/fold.

**Before the flop:** Hands are ranked by a percentile of equity vs random. Unopened pots: deep stacks open-raise 2.5-3 BB with a position-dependent top-X% (14% early to 55% from the SB); at <=13 BB effective (or <=18 BB late with no limpers) it plays shove/fold with a Nash-like push range c(nb)/S^0.6 by players behind. Flat calls are limited (since v10): call a raise only with a top-18% hand and equity >= pot odds + 0.08 vs the raiser's estimated range; SB completes only top 40%; BB defends a <=1.5 BB raise with top 45%. Facing a raise otherwise: estimate the raiser's range from stack depth (short stacks shove wide) and observed PFR, call/shove all-ins on ICM break-even equity, 3-bet premiums. The raiser's/shover's range is estimated from their real position (players still to act behind them when they raised, 1-3): heads-up and short-handed shoves and opens are assumed much wider (open floor 50%/33%/22% for 1/2/3 behind).

**After the flop:** When nobody has bet this street: MC equity vs 1-2 simulated opponents (extrapolated for more), weighted toward made hands if they called earlier streets. Facing a bet/raise: MC vs the bettor only, whose range is the top X% of hands by current strength (X = 0.58 x 50/40/33% flop/turn/river for a bet, 9% for a raise, shrunk for big bet sizes: x0.85 up to pot, x0.65 up to 2x pot, x0.5 beyond; x0.8 for each earlier street the same player bet (multi-street barrels are value-heavy); widened for aggressive bettors) plus 5% weight on the rest as bluffs/draws; equity is raised to the power of the number of distinct aggressors and x0.8 per extra passive opponent. Value-bet 60% pot at equity >= 0.66 heads-up (0.74 multiway), 85% pot at >= 0.82, shove when stack-to-pot < 1.2; semi-bluff 55% pot (30% of the time) with 0.42+ equity on flop/turn heads-up, 20% small in-position bluffs with < 0.35, 45%-pot thin bets in position at >= 0.56; facing a bet, raise/shove at equity >= 0.80, call when equity beats pot odds (+margin on the river and for big calls). Discard keeps the 2-card subset with best MC equity (common random numbers) at the turn.

**Short stacks and the points table:** Push/fold below ~13 BB (18 BB late with no limpers). Borderline shoves (0.5x-1.6x the Nash-like range) are decided by ICM: EV(shove) = P(no call)*ICM(steal) + sum over players behind of P(j calls)*[eq*ICM(win)+(1-eq)*ICM(lose)] vs ICM(fold); each player's call frequency comes from their observed VPIP. All-in calls preflop use the ICM break-even equity (Malmuth-Harville, places 1-4 exact, rest averaged) + 0.03 margin, vs an assumed shove range of 0.75x the Nash-like push range (min 10%), widened only if the shover is seen shoving often.

**Opponents:** Tracks VPIP/PFR and postflop aggression per seat at this table; PFR sets the assumed opening range when facing raises, VPIP sets the assumed calling range vs our shoves, and the bettor's aggression factor scales how much "air" we assume in their betting range postflop.

**Last change:** v14 (014-ef31f97a) for T5: position-aware range estimates when facing a raise or shove. Before, a shover was always modelled as having 3 players behind (so a heads-up SB shove at 10 BB was read as a top-23% range instead of ~45-60%), and a non-all-in raise used the table-wide PFR (so heads-up min-raises looked tight). We folded far too much heads-up and short-handed. Real results had been flat at ~29.5 for 4 versions (T4 rank 7, 29.4; 1st 95 vs 2nd 141 = lost 60% of heads-ups). Local tight-field test: v14 35.7/30.4 vs v13 35.7/32.0 (neutral, all local bots share the old heads-up logic); zoo-style head-to-head (seed 293, 400 tables): v14 57.5 vs v13 53.2, 1st places 158 vs 129 (the heads-up effect). v13 (T4) fixed the preflop tables to the keep-two rule.

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

## T2 result (v11 011-3bc679aa)
- Rank 6/8, 29.30 pts (CI 27.3-31.3). Places 1st..8th: 119,106,115,104,123,126,147,160. VPIP 23%, PFR 17%, aggression 2.66, WTSD 5%, showdown win 48%.
- Leaders: b07 35.3 (VPIP 20/PFR 17), b01 34.4 (19/15), b08 33.8 (29/18), b02 33.5 (26/20), b04 33.1 (22/16). Tightening VPIP to 23% did not change our score (29.5 -> 29.3).
- Bust analysis (work/logsim, 60 tables, tight field): 46 busts = 31 preflop (12+ calling all-ins, ~7 shoving) + 15 postflop (several overpairs/sets committed on 3-4 flush boards).
- Tested for T3 and neutral locally: fewer bluffs (bluff 0.05/semi 0.15) 34.5; wider caller model (qcm 1.0, push 0.9) 31.9; v11 35.2.
- v12 012-766afd62 submitted for T3 (tighter shove-calling).
- Rejected for T3: caller range model for our own value bets (opponent who called k earlier streets = top 0.6^k of hands + 20% weight on the rest). Local tight field (seed 211): v13 30.3/30.2 vs v12 38.4/33.8, v11 32.6 -> clearly worse (checks away too much value). The 7-8 handed busts it targeted (one pair bet 3 streets into AA/better kicker) are the visible cost of value bets that are profitable overall.
- Tested for T3, not submitted: river value-bet threshold +0.06 (work/vR). Seed 223: vR 34.7/32.6 vs v12 34.1/31.4, v11 33.1 -> within noise. v12 zoo (seed 9): 60.9 (best of all versions on that seed). v12 012-766afd62 plays T3.
- Tested for T3, not submitted: narrower ICM shove band (up to 1.25x instead of 1.6x the push range) + qcm 0.8 (work/vPB). Seeds 227/229: vPB 33.9/33.9 and 31.4/31.4 vs v12 32.6/31.6 and 35.6/33.1 -> pooled -0.6, no gain.
- v12 vs real submissions (localsim seed 233, 400 tables; 009 x2, 011 x2, tag x2, nit): v12 35.0, 009 33.8/31.7, 011 32.7/30.1, tag 31.6/31.6, nit 28.6. v12 leads, but within noise.

## T3 result (v12 012-766afd62)
- Rank 6/8, 30.16 pts (CI 28.2-32.1). Places 1st..8th: 112,128,123,105,118,125,144,145. VPIP 22%, PFR 16%, aggression 2.67, WTSD 4.8%, showdown win 48.5%.
- Leaders: b02 34.2, b07 33.9, b01 33.4, b04 33.0, b08 32.1.
- Root cause found for T4: biased preflop tables (all 3 hole cards counted). v13 013-b297ef2d = v12 + keep-two tables.
- Tested for T4, not submitted: flop keep-pair valuation in the no-bet MC + 2-card opponents (work/vF). Seed 257: vF 34.3/32.4 vs v13 33.9/33.7, v12 33.8 -> neutral. Pooled v13 vs v12 over 3 seeds: 34.8 (6 entries) vs 32.7 (5 entries).
- Push-range scale with the new tables (seed 263, 2 copies each): push 1.0 (v13) 34.2/32.4, push 1.15 34.3/31.8, push 0.85 31.7/30.5 -> keep 1.0.
- Open-range scale with the new tables (seed 269, 2 copies each): open 0.85 33.3/32.5, open 1.15 33.3/32.9, open 1.0 (v13) 30.3/29.1. Both directions 'beat' the base -> base unlucky / noise; no change.
- v13 vs v12 seed 271: v13 36.4/32.3 vs v12 33.4/31.5. Pooled over 4 seeds (241, 251, 257, 271): v13 34.7 (8 entries) vs v12 32.6 (7 entries), +2.0, v13 never behind -> v13 plays T4.

## T4 result (v13 013-b297ef2d)
- Rank 7/8, 29.41 pts (CI 27.6-31.3). Places 1st..8th: 95,141,113,124,139,112,124,152. VPIP 23%, PFR 16%, aggression 2.61, showdown win 47%.
- Leaders: b07 34.3, b01 33.9, b02 33.5, b04 32.6, b08 32.6. Our real score has been flat (29.5/29.3/30.2/29.4) across v9-v13 even though local tests improved -> the local field does not capture the real leak.
- v14 014-ef31f97a submitted for T5 (position-aware raiser ranges; big effect expected heads-up/short-handed).
- Tested for T5, not submitted: re-shove range floor (raises>=2, short/all-in re-raiser: q >= 0.7 x push range for their position). Seed 283: 33.7/33.0 vs v14 35.7/30.8, v13 34.4 -> neutral; sign uncertain vs tight real re-shovers, so kept v14.
- v14 vs v13 seed 281: v14 35.7/30.4 vs v13 35.7/32.0 (neutral locally).
- Tested for T5, not submitted: conservative postflop (vth1 0.72, vthm 0.78, thin 0.62, bluff 0.12, semi 0.2; work/vV2). Seed 287: vV2 33.3/30.3 vs v14 33.4/33.3, v13 33.4 -> worse/neutral.
- v14 vs v13 zoo-style field (seed 293): v14 57.5 (1st 158) vs v13 53.2 (1st 129). Zoo seed 9: v14 59.0 (v13 62.4, within noise).
- Tested for T5, not submitted: widen bettor range x1.35 and bluff weight x1.5 when heads-up (work/vHU). Seed 297 zoo-style: vHU 48.0 vs v14 53.4 -> worse.
- Tested for T5, not submitted: heads-up SB open floor 80% when deep (work/vSB). Seed 299 zoo-style: vSB 47.3 vs v14 47.7 -> neutral (deep heads-up is rare).
- v14 vs v13 zoo-style seed 307: 52.5 vs 53.7. Pooled over 2 zoo-style seeds: v14 55.0 vs v13 53.4 (+1.6); tight field ~equal. Kept v14 for T5.
