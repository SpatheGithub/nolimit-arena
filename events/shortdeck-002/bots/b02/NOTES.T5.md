## Strategy

**Summary:** Equity-driven bot for 36-card shortdeck. Preflop uses a precomputed 81x81 hand-class equity matrix (bot/data.npz) to price opens, shoves and calls against estimated ranges; postflop computes equity with a vectorised numpy lookup evaluator against every (river) or a 100-combo sample of (flop/turn) opponent hole-card combos, weighted by each opponent's preflop range and narrowed by their postflop aggression. Chip-EV first (points are top-heavy 100/45/20/8, so winning matters most), with small ICM margins when few players remain.

**Before the flop:** Hands ranked by heads-up equity vs a random hand (shortdeck-specific: AA, KK, QQ, JJ, TT, AQs, AKs ... worst are 66, 76o). Deeper than 14 BB effective: open 2.1-2.5 BB with a top-x% range by players left to act (15% UTG up to 55-60% button/SB), widened vs blinds that fold to raises, tightened with limpers. Facing a raise: equity vs the raiser's estimated range (observed PFR; when it is all-in, a default shove range by stack depth, widened for late-position shovers and by the seat's observed shove rate) -> 3-bet/shove at equity >= 0.60 (at 15-40 BB heads-up against one raiser, also shove when the fold-equity EV is positive and beats calling), call when equity x realisation (0.95 IP / 0.82 OOP) beats the price, else fold. 14 BB or less: shove-or-fold by chip EV with fold equity from every player who could call (call rates from their observed calls of big raises, else a by-depth default widened by 30% for each player fewer than 4 left behind).

**After the flop:** Equity vs each opponent's range (river: all combos; turn: every river card; flop: all 31 turn cards with a random river; flop/turn use a 100-combo sample), multiplied across opponents. Value bet 60-75% pot at equity >= 0.58 heads-up / 0.68 multiway; raise at >= 0.80; shove when SPR is small. C-bet bluffs heads-up as preflop aggressor (~55% scaled by opponent fold-to-bet), some later-street stabs and semi-bluffs. Calls when equity >= pot odds + 2% (river) / 4% (flop, turn).

**Short stacks and the points table:** push/fold chip-EV model at <= 14 BB; extra equity margin up to 3% for all-in calls when <= 4 players remain (1.5% at 5-6).

**Opponents:** per-seat VPIP, PFR, fold-to-raise preflop, fold-to-bet postflop, postflop aggression, calls of big raises, all-in shove count. Used for raiser/shover ranges, steal widening, fold equity of shoves, bluff frequency, and how much a bet narrows their range (less for very aggressive seats, more for bigger bets since v12).

**Last change:** v12 (012-56af3cce, for T5): bet-size-aware range narrowing. When an opponent has bet on the current street, the narrowing exponent is multiplied by 0.75 + 0.5 x min(bet / pot-before-bets, 1.5). Half-pot bets are unchanged, pot-size bets narrow 25% more, 1/3-pot bets slightly less. Rationale: bots usually size up with strong hands, and in the sample hands our losses came from calls that we then folded on a later street. Test, 4-vs-4 against v11 over five seeds (500/500/500/500/450 tables): +1.3, -0.3, +0.5, +0.76, +2.25 points per seat (mean +0.91, about 1.7 SE); mixed field with house bots: 27.2 vs 27.8 (one run). v11 (011) set the resteal fold assumption to 0.8; v10 widened resteal to 40 BB; v9 enabled resteal; v8 set WIDEN 0.3.

## Notes

- data.npz built by precompute.py (6000 sampled boards for the HU class matrix, 5000 samples multiway).
- Evaluator: base-5 rank-count code -> value table (5^9, padded x2 so invalid combos never index out of range) + 9-bit suited-mask table; verified vs kit fasteval on 20k hands.
- Timing on the busy build machine: p50 ~50 us, flop decisions ~180-400 us, max seen ~1.3 ms under heavy load (1 timeout in 300 zoo tables for v7). Guard: if >0.2 ms already used, 8 runouts / 70 combos; narrowing skipped past 0.62 ms. If the referee reports timeouts, cut FLOP_R (31) / NSUB (100) at the top of agent.py.
- A/B results (500 tables, mixed field, same seed): v2 (resteal + widened call priors) ~34-37 vs v1 37-40; call-narrowing postflop (opp calls narrow range) + thin value vs stations: 31.8 (bad, reverted; flags CALL_NARROW, THIN, RESTEAL, WIDEN at top of agent.py).
- WIDEN 0.45 vs v8 (WIDEN 0.3), 4-vs-4, 450 tables: 21.3 vs 21.9, so no gain from widening further; keep 0.3.
- Mixed field with house bots, 300 tables: v8 seats 28.9 and 32.5 vs v7 seats 32.6 and 28.9, equal. The v8 gain shows up against equity-calling bots like ours and does not cost anything against the house bots.
- v8 against the zoo: 50.6 +- 6.5 (200 tables, 0 substitutions), in line with v7.
- Zoo (house bots) score ~45-52 pts/table (v7: 47.0 +- 5.3 over 300 tables; 53.2 +- 6.4 over 200 tables, seed 404, 0 substitutions).

- Self-field A/B tests (500 tables each, baseline = v5 copies): open ranges x0.8 worse (25.0 vs 28.8), x1.2 equal; ICM margins doubled worse (27.2 vs 30.7), halved equal; push/fold zone 18 BB not better; bluff 0.3 not better.
- Thinner HU value bets (0.54 instead of 0.58) worse (25.7 vs 29.1); bluff 0.75 equal.
- Resteal (15-30 BB, HU, fold prior x0.6) re-tested after v7: 27.3 vs v7 copies 28.8 avg -> still off.
- Extra +3% call-off margin for big preflop all-ins when > 12 BB (risk > 50% stack): seed 101: 28.8 vs v7 copies 29.6/24.0; seed 202: 27.0 vs 31.0/28.8 -> no gain over 800 tables, not submitted.
- OOP preflop realisation 0.88 instead of 0.82 (defend more): 27.5 vs v7 copies 28.5/26.9 (400 tables) -> equal, not submitted.
- Final 150-table run, v7 vs v1/v4/v5/v6 + 3 house bots: all my versions 27-31.5 (+-6), i.e. indistinguishable; 0 substitutions.
- In fields of my own versions, `nit` scores ~22-24 (it survives into 3rd/4th), so the field busts itself a lot.

## T1 result (v7)
- Rank 5/8, 21.41 pts/table (19.3-23.5); the whole field was 19.3-24.2, all within noise. Places 1st-8th: 136/106/106/115/147/121/152/117. 0 substitutions in 116,585 decisions; p99 500 us, max 833 us.
- Our stats: VPIP 29%, PFR 18%, aggression 2.16, WTSD 8.2%, showdown win 52.6%. Best teams: b06 24.2 (VPIP 35/PFR 20), b07 24.1 (VPIP 25/PFR 18).
- Sample hands: other bots open to 2.5 BB (50 at 10/20); ours are the 2.3 BB (46) opens.

## T2 result (v8)
- Rank 2/8, 24.53 pts/table (22.3-26.7); places 1st-8th 156/122/128/110.5/119.5/112/137/115; 0 substitutions. Weighted total after T2: 70.48, rank 2.

## T2 patch-window diagnostics
- Instrumented copy (per-hand chip delta by situation, 250 tables mixed field), average BB per hand: postflop deep, only called (never bet) -4.8 (n=670); postflop deep, we bet or raised +4.3 (n=2152); preflop re-shove over a raise +1.9 (n=161); preflop call of a big raise or all-in +3.1 (n=135); first-in shove +0.06 (n=344). Our postflop calls lose chips, but our bets win them.
- Test: tighter postflop calls (margin 0.08 flop/turn, 0.05 river; narrowing 1.6 instead of 1.3). Mixed field: +2.4 then -3.9. 4-vs-4 against v7: +1.8 then -0.65. Net about +0.4, i.e. noise, so not submitted.
- Test: BLUFF 0.75, 4-vs-4 against v7: +0.5, noise.
- Test: postflop raise threshold 0.72 instead of 0.80 (raise more, call less), 4-vs-4 against v7: -1.2 (21.0 vs 22.2), worse.
- Test: WIDEN 0.3 (assume wider calls of late-position shoves), 4-vs-4 against v7: +1.5 and +1.4 over two 500-table seeds. Submitted as v8 (008-c9add76e); a third 450-table seed after submitting gave +1.9. In the build phase, v2 bundled WIDEN with resteal and looked worse against house bots; the house bots call tight, which is different from the real field.
- A 4-vs-4 field of my own versions has VPIP 30%, WTSD 8%, close to the real T1 field. Use that format for A/B tests: same tables, and each group's mean has about half the per-seat noise.

## T3 patch-window tests (4-vs-4, same tables)
- Resteal 15-30 BB vs v8: +2.0, +1.2, +1.45, so submitted as v9. Mixed field with house bots: equal.
- Resteal zone 15-40 BB vs v9: +4.2, +1.3, +1.0, so submitted as v10 (010-63b1fcf4). Mixed field with house bots: v10 29.7 vs v8 30.4 (equal).
- Resteal zone 15-55 BB vs v10: +0.1 (noise); kept 40.
- Resteal fold-rate multiplier 0.8 instead of 0.6 vs v10: +0.2 (noise); kept 0.6.
- Direct check v10 vs v8, 4-vs-4, one 300-table seed: 21.1 vs 22.2 (-1.1, inside the noise; it conflicts with the step tests). Re-check v10 vs v8 with 2-3 x 500 tables in the next window before building on resteal further.
- Resteal with one caller already in (n_live <= 2) vs v10: one 300-table seed, 21.65 vs 21.60 (no gain); not adopted. Next ideas: resteal for 12-15 BB stacks (currently covered by the short-stack branch); per-seat 3-bet fold stats.

## T3 result (v10)
- Rank 2/8, 24.30 pts/table (22.1-26.5); places 1st-8th 161/116/101/120/127/146/132/97; 0 substitutions in 118,720 decisions. Weighted total 143.38, rank 2. b06 leads every round (24.2/24.9/25.8; VPIP 35, PFR 20).

## T4 patch-window tests (4-vs-4 against v10, 500 tables per seed)
- v10 vs v8 re-check: +0.6 (with the earlier -1.1, direct difference about 0; real field T2 v8 24.53, T3 v10 24.30). Kept v10.
- Value bet sizes 0.7/0.9 pot instead of 0.6/0.75: +0.2 (noise).
- Heads-up SB open 85% / 3-handed button open 65%: +0.3 (noise).
- More turn/river stabs (BLUFF x 0.6 instead of x 0.36): +1.5, then -1.0 (noise).
- Push/fold zone 12 BB instead of 14: -0.3 (noise).
- OOP preflop realisation 0.75 instead of 0.82 (tighter defence): +0.4 (noise).
- OPEN_MULT 1.2 (open 20% wider, like b06's looser style): +0.1 (noise).
- Direct v10 vs v9, 500 tables: -1.9 for v10. Over all four v10-vs-v9 seeds: +4.2, +1.3, +1.0, -1.9, mean +1.1. v10 vs v8 direct is about 0. The version differences look like noise around zero; kept v10. If T4 is weak, v8 (008) and v9 (009) are equally good fallbacks.
- Resteal fold multiplier 0.45 (fewer resteals) vs v10, 450 tables: 20.2 vs 23.1 (-2.9). Fewer resteals looks worse, which supports keeping 0.6 or higher.
- Resteal fold multiplier 0.8 vs v10, second seed (400 tables): 22.3 vs 20.9 (+1.4); third seed (350 tables): 22.9 vs 20.35 (+2.55). Three seeds +0.2, +1.4, +2.55, mean about +1.4. Submitted as v11 (011-87311c94) at the end of the T4 window. v11 against the zoo: 52.1 +- 6.5 (200 tables, 0 substitutions).
- Conclusion: single-parameter tweaks are below what 500-1000-table self-play can detect (SE about 1.2 per seat per run). Only change on consistent multi-seed gains.

## T4 result (v11)
- Rank 2/8, 24.29 pts/table (22.1-26.5); places 1st-8th 162/111/112/107/110/136/135/127; 0 substitutions in 115,583 decisions; max 877 us. Weighted total 240.54, rank 2. Real field: v8 24.53, v10 24.30, v11 24.29, so the self-play gains did not show up in the real field (its noise is about +-2.2).
- T4 sample hands show the familiar leak: call a flop or turn bet, then fold a later street (-113, -116, -278 chips).

## T5 patch-window tests (against v11)
- Resteal fold multiplier 1.0 instead of 0.8, 4-vs-4 x3: +0.85, +0.3, -1.2, mean 0 (kept 0.8).
- Tighter turn/river calls (margin 0.07 turn, 0.05 river), mixed field with nit/montecarlo/pot_odds: 27.5 vs 28.4 (no gain even against non-bluffers).
- Bet-size-aware narrowing (expo x (0.75 + 0.5 x min(bet/pot, 1.5)) for the current street's bet), 4-vs-4 x4: +1.3, -0.3, +0.5, +0.76 (mean +0.57, about 1 SE); mixed field 27.2 vs 27.8. A fifth seed gave +2.25 (mean +0.91), so submitted as v12 (012-56af3cce) at the end of the T5 window. v12 against the zoo: 48.4 +- 6.6 (200 tables, 0 substitutions; normal range 45-53).
- Informational: v12 vs v8, 4-vs-4, 450 tables: 21.4 vs 21.9 (-0.5, noise). The chain of self-play gains v8 -> v12 does not add up in direct comparisons; the versions are probably all within about 1 point of each other. Code is in the T5 window notes: in equities(), after `expo = 1.3 * k * ...`, multiply by 0.75 + 0.5 * min(bets[s] / (pot - sum(bets)), 1.5) when bets[s] > 0.

## Next ideas
- Re-tune resteal with lower fold prior; per-seat 3-bet fold stats.
- Better multiway equity than product of HU equities.
- Use patch windows: check substitution counts and results first.
