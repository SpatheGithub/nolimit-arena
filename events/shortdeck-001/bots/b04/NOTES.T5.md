# Team b04 notes

## Strategy

**Summary:** Equity-driven bot for shortdeck (36 cards, flush > full house). A lookup-table hand evaluator (validated against the engine on 100k hands, ~0.4 µs per 7-card eval) and precomputed preflop equity tables (81 classes: vs k random hands and class-vs-class heads-up, in `bot/pre.json`) drive every decision. Postflop it runs a time-boxed Monte Carlo (≤0.25 ms, ~150-250 trials) against each opponent's estimated range. When short it plays an EV push/fold model with an ICM risk premium, because only 4 places pay (100/45/20/8) and busting costs more than chip EV suggests.

**Before the flop:** Hands are ranked by heads-up equity vs a random hand (in shortdeck AA 0.73, 99 0.56, 77 only 0.45, 66 0.38: small pairs are weak). It open-raises 2.5bb (3bb from the SB, +1bb per limper) with a position-dependent top-X%: about 12% with 7 players behind, 14/17/21/27/36% as fewer remain, 50% from the SB, ×1.15 at 3 or fewer alive, ×0.6 with limpers, wider against tight blinds. It never open-limps. BB with an option raises the top 10%. Facing a raise, it estimates the raiser's range from their observed PFR (shoves get a wider stack-depth-based range, ×1.6 from the SB or heads-up). It 3-bets the top ~30% of that range (shoving at ≤25bb), calls when equity vs the range beats the price plus a margin (BB defends up to 55% of hands, the SB 42%, others 35%), and folds otherwise. At ≤14bb it shoves or folds using an EV model over each player behind. Their calling ranges come from pot odds vs an assumed 35% shoving range, adjusted by their VPIP.

**After the flop:** Monte Carlo equity against all live opponents at once, each sampled from the top-X% of combos implied by their preflop action (raiser = PFR, caller = VPIP, checked BB = any). It value-bets 60% pot (75% when very strong, all-in at SPR ≤1.3) when equity is ≥0.58 heads-up, ≥0.45 against two, or ≥0.38 against three or more. As heads-up preflop raiser it c-bets 45% pot on the flop about 60% of the time (more against players who fold to bets), and bets some turns and rivers with equity ≥0.35. Facing a bet, equity is discounted as eq^(1 + k·bet/pot), with k smaller against aggressive bettors and larger after a raise. It raises (2.8x, or all-in when SPR is low) at discounted equity ≥0.72, calls when it beats pot odds (+ICM premium for big calls), and folds otherwise.

**Short stacks and the points table:** Push/fold at ≤14bb. ICM premium = PREM[n_alive] × share of my stack at risk × 0.75, where PREM is 0.05 at 8 alive and peaks at 0.093 at 5 alive (from exact kit/icm.py runs: stacking off needs about 55-59% equity at every stage here). It is subtracted from my equity in shove EV and added to the required equity for all-in calls and big postflop calls. With 3-6 alive, all-in calls also blend in an exact ICM required equity. Heads-up has no premium (pure chip EV).

**Opponents:** Per-seat counts of hands, VPIP, PFR, postflop aggression and folds to bets, with priors (VPIP 0.4, PFR 0.2). These set opener and caller ranges, opponents' calling ranges in shove EV, the bet-discount strength, and c-bet frequency.

**Last change:** 004-de6a1241 (accepted, current, plays T4) = 003 with KSCALE raised 1.4 → 2.0, so facing a bet, equity is discounted as eq^(1 + 1.1·bet/pot) against an average-aggression bettor and it folds more to postflop bets. Local results, in order: k0.7 22.6 < k1.0 ≈ 23-24 < k1.4 < k1.8 (+1.0 pooled over 1000 tables vs 003) < k2.2 (27.1 vs 003-avg 22.8 in a 600-table run); every run pointed the same way. In T1-T3 the field (other teams) bets mostly for value, and we bust first more than anyone (8th place 15-17%). Earlier, 003-079d861e = 002 + KSCALE 1.4, so equity is discounted 40% harder when facing postflop bets and the bot folds more to bets. Two 400-table runs: k14 29.7 vs 002 avg 25.3, then 25.4 vs 24.1. Pooled about +2 points (≈1.3σ, suggestive, not conclusive). Also checks the MC clock every 4 trials. Before that, 002: parameterized constants, ICM premium, shove-calling model, fixed a bug that counted posted blinds as callers. 1000 tables in one field with v1 copies: 28.4 vs v1 26.2. Later tested changes (re-shove at ≤22bb, showdown-based range widening, early-level tightening, looser play, push threshold 18bb, other ICM scales, open size 2.2/3.0, raise threshold 0.65/0.80) were neutral or worse, so 002 stays.

## Tournament results
- T1 (bot 003): rank 6/8, 19.95 ± 2.0 (field 18.9-25.0, all within noise). Places 1st-8th: 119/111/103/125/115/112/150/166 per 1000. Our VPIP of 33% is the field's highest (PFR 19%); 7th+8th finishes are 31.5%, so we bust early too often. 1 timeout in 110k decisions (max CPU 2.5 ms, one-off).
- T2 (bot 003): rank 3/8, 21.21. Places 126/127/101/110/126/133/121/156. b02 leads every tournament (~25-26, VPIP 30 / PFR 20).
- T3 (bot 003; the KSCALE 2.0 submit was interrupted): rank 8/8, 20.43 (2nd-8th all within 20.4-21.9). Places 106/157/98/101/123/126/129/160.
- Patch before T4: submitted 004 = KSCALE 2.0 (tests: k18 vs 003 +1.7 at 400 tables and +0.6 at 600; k22 +4.1 at 600). Check after submitting, 500 tables: KSCALE 2.0 seats 25.7 vs 003 copies 21.8. Then k2.6 27.8, k3.0 22.9 vs 004 seats 23.8 (500 tables): the peak is likely 2.2-2.6. Next window: test k2.4 vs 004 at 1000 tables before moving.
- T4 (bot 004, KSCALE 2.0): rank 4/8, 21.66. Places 131/113/126/119/133/106/138/134: 8th-place finishes fell from 156-166 to 134, and postflop calls fell 4.5k → 4.0k. Field is very tight at the top (20.5-22.8).
- Patch before T5 (004 kept): 450 tables each. k2.4 22.4 and CALLW 0.7 (on KSCALE 2.0) 22.8, vs 004 seats 24.75, so both worse. VAL_HU 0.54 27.6 vs 004 23.7 vs VAL_HU 0.62 22.6 (thinner value betting looks better, but one run, single seat). Not confirmed in time, so not submitted. NEXT: confirm v54 (tools/mkvar.py v54 VAL_HU=0.54) with 2 seats over ≥800 tables. If still ahead by more than 2, submit.
- Patch before T2: CALLW 0.7 (flat-call ranges ×0.7), 400 tables: 22.3 vs 003 copies 23.0. No gain, not submitted. 003 kept for T2.
- Next idea: find where the early busts come from (deep-stack postflop stack-offs vs preflop all-ins). The sample hands don't mark our seat; it can be inferred from bet sizes (2.5bb opens, 3.0x/3.6x 3-bets).

## Test log (1000 tables unless noted; ±2.3 per entry, so differences under ~3 are noise)
- v1 (001) vs zoo, 150 tables: 44.3 (avg seat ~21.6).
- v3 (ICM premium + fixes) vs [v1×3, nit, montecarlo, maniac, pot_odds]: 30.15 vs v1 avg 30.3 (neutral).
- Multi-variant field [base, tight, prem, v1×2, nit, maniac, montecarlo]: base 28.4, prem(scale 1.0 + call margin .02) 26.5, v1 26.2/25.4, tight(early ×0.7, VAL_HU .63, cbet .25) 24.5.
- [base2, loose, premlo, push18, v1, nit, maniac, montecarlo]: base 27.0, loose 26.2, push18 26.0, v1 25.6, premlo(scale 0.4) 22.3 → the ICM premium matters, keep 0.75.
- Re-shove (RESTEAL_BB 22) vs 002×3: 25.6 vs 26.35, and with reads 24.0 vs 26.6 → dropped.
- Showdown reads alone vs 002×3: 25.4 vs 26.0. In a loose field (002×2, maniac×2, minraiser, random, pot_odds): 34.4 vs 002 37.9 → dropped (widening ranges against maniacs made it call too much).
- Open 2.2 / 3.0, raise threshold 0.65 / 0.80: all 23.0-23.9 vs 002 22.5 (flat).
- KSCALE (facing-bet discount ×0.7 / ×1.4, variants in tools/runs/k07, k14): the run timed out under machine load with no result. Untested; try in a patch window.
- The nit house bot scores ~24-25 in these fields by reaching 2nd/3rd (35-40% 2nd). Our bots bust in 5th-8th about 45% of the time. Survival matters, but plain tightening tested worse.

## Timing
- p50 25 µs, p99 300 µs. Max 600-1100 µs only on the heavily loaded shared machine. One loaded run (284 s for 1000 tables) logged 4 "hangs" (>50 ms wall), most likely scheduling stalls rather than code. MC is wall-clock budgeted (0.25 ms in 002) and checks time every 8 trials (every 4 in the working copy).
- Exact ICM for 6 players costs ~130 µs per call (3 calls per decision). It is used only for preflop all-in calls.

## Known weaknesses / next steps
- No hand-reading beyond preflop-action ranges plus a bet-size discount. Multiway postflop thresholds are crude.
- Push/fold calling ranges for opponents are assumed, not learned. Learning each opponent's shove frequency when short might help, but the showdown-max approach hurt.
- If timing substitutions show up in tournament results, lower `limit_s` to 0.0002.
- Tools: `tools/mkvar.py NAME KEY=VAL` makes a variant copy in tools/runs/. `kit/localsim.py --opponents tools/runs/A,tools/runs/B,...` seats many variants in one field (the best A/B method found).
