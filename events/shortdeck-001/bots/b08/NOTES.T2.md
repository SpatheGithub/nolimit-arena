# Team b08 notes

## Strategy

**Summary:** Equity- and ICM-driven bot. Preflop it uses precomputed shortdeck equity tables (81 hand classes, equity vs random hands and vs top-X% ranges). Postflop it runs a fast vectorized numpy Monte Carlo (about 240 samples, 0.1–0.4 ms) against opponents whose ranges are narrowed by their preflop raises and postflop bets. All-in calls use the exact Malmuth-Harville ICM equity for the 100/45/20/8 points table, so it avoids coin flips that cost points even when they gain chips.

**Before the flop:** Hands are ranked by percentile (a blend of heads-up and 3-way equity). Open-raise ranges depend on how many players are left to act (about 20% UTG up to 60% in the SB, times 0.6 when deeper than 40bb). Sizes are 2.2–2.5bb plus 1bb per limper. At 16bb effective or less it plays push/fold, with a shove range of 0.6*(10/bb)^0.75 / n_behind^0.9 (top fraction of hands). Facing a raise, it estimates the raiser's range from their observed raise frequency (the weight on observation grows with hands seen). Short shoves are read as wide, based on how many players were left behind the shover. When committed, it calls or shoves if equity vs that range exceeds the ICM-required equity plus 2%. It 3-bets with equity ≥ 0.6 vs the range or premiums, and flats only with the top ~32% at a good price (tighter when deep).

**After the flop:** Monte Carlo equity vs up to 3 opponents. Each sampled opponent hand is down-weighted (x0.2) if it is outside their preflop range, or (x0.15) if it is outside the top q of current made hands when they bet or raised. q runs from 0.25 to 0.65 and is scaled by their aggression rate. It value-bets 0.6–0.75 pot at equity ≥ 0.58 heads-up (0.45 3-way, 0.37 4-way) and shoves at SPR < 1.2. As the preflop raiser heads-up it c-bets about 55% of flops (less against aggressive opponents) and stabs 30% of later streets. Facing a bet it raises with equity ≥ 0.8 heads-up and calls when equity ≥ pot odds + 10% (river +9%). Big calls (≥ 40% of its stack) use the ICM-required equity instead of plain pot odds. When effective stacks are over 40bb, calls of 30%+ of the stack need 8% more equity.

**Short stacks and the points table:** Push/fold below 16bb. Every preflop all-in call and every large postflop call is checked with exact ICM, using the stacks after fold, win and loss, with busted players taking their place. With equal stacks that means about 55–59% equity for a flip. Heads-up it plays plain chip EV.

**Opponents:** Per-seat counts of hands, VPIP, PFR and postflop aggression (bets+raises vs calls+checks). Raise frequency sets the assumed raising range preflop and postflop. The aggression rate scales how much bets narrow the range and lowers the c-bet frequency.

**Last change:** 007-4e44c2e6 (plays T2) adds a deep-stack commitment margin: postflop calls of 30%+ of the stack with more than 40bb effective need 8% more equity. This targets the early busts seen in T1 (8th place 14.8%, 7th 14.3%). Local test, 3 vs 3 copies over 160 tables: 27.8 vs 22.7 points/table (small sample, z about 1.6). 006 (T1: rank 2, 23.87) had lowered the c-bet frequency to 0.55.

## Log / test results (localsim, points/table; even share 23.9)
- v1 (001): zoo 39.2 (150 tables); mixed house field 46.2.
- Wider opening (x1.3) and wider push (x1.25), push/fold up to 16bb: small gain (+1–2).
- Tighter postflop calling (margin 0.07 vs 0.03): +2–4; margin 0 clearly worse. Raising lighter (rthr 0.72): worse.
- Tighter when deep (>40bb: x0.6 open/flat ranges): +1.2.
- Exact ICM all-in calls: +3.7 (the clearest gain so far).
- With ICM in: push scale 1.0 > 1.25 > 1.5 (+0.9 per step); 0.8 slightly worse. Post margin 0.10 > 0.07 (+0.9).
- 005 vs 004 head-to-head: 25.5 vs 24.7.
- After 005 (not adopted): open_scale 1.0 gave 24.1 vs base 26.4. Thinner value (vthr1 0.54) gave 25.0 vs 26.4. BB defence def_p 0.5 gave 22.8 vs 25.5, clearly worse (also bad in an earlier test). cbet 0.55 gave 26.9 vs 25.5, but this is noise and an earlier test of more c-bets was also slightly positive.
- cbet 0.55 confirmation (3 vs 3, 330 tables): 25.6 vs 24.4. Two runs are both about +1.2, which is not significant, A third run (4 vs 3 copies, 280 tables) gave 22.6 vs 21.7, so it was submitted as 006.
- One 50 ms "hang" was seen once, while the machine was heavily loaded (localsim 3-4x slower than normal). Every act() path is bounded (MC ≤ 240 samples, ICM ≤ 3 evaluations), so I put it down to OS scheduling.

- A final sanity run of 006 vs 005/004/003/001 (220 tables) timed out on the overloaded machine, so it gave no result. 006 vs earlier versions has not been confirmed directly; 005 vs 004 was.

## T1 result (006)
- Rank 2/8, 23.87 points/table; leader b02 had 24.95 (within noise). All 8 teams scored 18.9-25.0.
- Places 1st-8th: 158/121/98/83/118/131/143/148. U-shaped: many wins, but many early busts (8th 14.8%, 7th 14.3%).
- VPIP 26%, PFR 18%, WTSD 8%, showdown win 51%. CPU p99 300 µs, max 876 µs (close to 1 ms!); 1 wall-clock hang (94 ms, environment).
- Field: VPIP 24-33%, PFR 14-20%, so similar TAG-style bots. Sample hands show deep preflop 4-bet/5-bet all-ins (QQ vs QQ, AA/KK/AK) in level 1.
- Patch T2: added an optional `deep_commit` margin (extra equity needed for postflop calls of 30%+ of the stack when eff > 40bb). A 160-table test gave 27.8 vs 22.7, so it was submitted as 007 with deep_commit=0.08. Confirmation run, 007 vs 006 (3 vs 3, 150 tables): 26.1 vs 24.3, the same direction.
- TODO next window: the local max CPU hit 1103 µs once (busy machine; T1 referee max 876 µs). Cut MC samples (e.g. 160/120) or add a time guard to make the tail safer.

## How to test (for patch rounds)
- `python tools/mkvar.py NAME '{"param": value}'` copies bot/ to variants/NAME with a params.json override (the P dict at the top of bot/agent.py).
- Compare with several copies at the same tables: `python kit/localsim.py --opponents variants/base,variants/X,variants/X,...,nit,montecarlo --tables 700`.
- Noise is about ±2.5 points per bot at 700 tables, so only trust differences of 2+ points or repeated results.
- The nit house bot (top 8% only) does very well in fields with maniacs (37 vs our 30): survival is worth a lot under this points table.

## Known weaknesses / next
- No check-raises or river bluff-raises; c-bet logic is simple.
- Open-shove decisions don't use ICM (only call decisions).
- MC timing p99 is about 0.5–0.6 ms on the busy machine; sample count is trimmed for 3+ opponents.
