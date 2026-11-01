# Team b05 notes

## Strategy

**Summary:** Math-first bot for shortdeck. Preflop uses precomputed shortdeck equity tables (81 hand classes: equity vs k random hands, head-to-head matrix, equity vs top-x% ranges); postflop runs a small vectorized numpy Monte Carlo (~200 samples, fixed precomputed permutation bank) against opponents whose hands are weighted by their preflop action and by their betting on this street. Decisions compare equity to pot odds, with an ICM-derived required equity for all-in spots when 6 or fewer players remain.

**Before the flop:** Hands ranked by a shortdeck-specific percentile (pairs/suited broadway high; small pairs like 66/77 are weak in shortdeck). Unopened: open-raise top 15% (8 behind) widening to ~50-60% from SB/BTN, 2.5bb (2.2bb when < 30bb). At <= 13bb effective: push/fold with a range that widens as stacks shrink and fewer players remain behind. Facing a raise: estimate raiser range from observed PFR, compute equity vs that range from the table; 3-bet top hands, call with equity > pot odds + margin, shove/call all-in by (ICM-adjusted) required equity.

**After the flop:** Equity vs weighted ranges. Bet 60-75% pot with equity >= 0.72 (>= 0.6 heads-up); raise ~2.8x with >= 0.82 (0.72 heads-up), shove when SPR is low. C-bet 40% pot as preflop aggressor heads-up on flop 60% of the time; occasional river/turn bluffs (12%). Calls when equity >= pot odds (+ ICM margin for all-in calls).

**Short stacks and the points table:** push/fold under 13bb; ICM (exact Malmuth-Harville, copied from kit/icm.py) computes required equity for all-in calls when 3-6 players are alive.

**Opponents:** Tracks per-seat VPIP, PFR and postflop aggression frequency during the table; raiser ranges come from PFR, caller ranges from VPIP, and aggressive opponents' bet ranges are widened.

**Last change:** v7 is kept unchanged for T5 as well. T4 with v7: rank 7/8, 20.83 pts/table, with all teams within noise (20.5-22.75). The variants tested since v7 (P3 bubble tightening -1.8; H push/fold at 16bb -0.7 over 500 tables) did not beat it. Earlier, v7 was kept for T4: with under 10 minutes left in the window, no change could be validated. T3 with v7: rank 4/8, 20.89 pts/table (was 20.26 in T2 with v6). v7 (007-d301fafe, for T3): tighter flop/turn calls against bets. The extra equity needed over pot odds when SPR > 2 rose from 4% to 7%. A bettor's assumed range on the current street narrowed: the top 42% of their range by current strength for small bets (was 50%) and 32% for big bets (was 38%). Reason: T1 and T2 sample hands show call-call-fold lines that bleed chips. T2 placed 8/8 with 20.26 pts/table and 8th 161 times. Mixed field, 500 tables: P2 averaged 25.6 vs v6's 25.1 (+0.5, within noise); a 1000-table confirmation timed out on the loaded machine. Previous change, v6 (006-071ff5d8, for T2): In T1 v5 placed 5/8 with 20.74 pts/table and finished 8th 178 times in 1000 tables (125 expected), so it busted first too often. In the sample hands it called a 5-bet shove with AKs while a 4-bettor holding KK was still in the hand, and it called big deep bets postflop. Fixes: preflop equity is multiplied by 0.75 for each earlier raiser still in the hand. Postflop, when a call costs >= 35% of a stack of >= 25bb, the bettor's range is narrowed (f x 0.6). Mixed field, 400 tables: P1 averaged 24.1 vs v5's 22.8 (+1.3). Earlier, v5 (005-c6e8f273): opens widen 1.4x when every player behind has VPIP < 25% (steal vs nits); postflop calls on flop/turn need +4% equity over pot odds when SPR > 2 (reverse implied odds). Mixed field 500 tables: +1.0 pts/table vs v4, nit's score dropped 21 -> 19. v4 (004-89442ed9) was a timing fix: ICM (156us per eval at 6 players, x3 per decision) now only runs with <= 5 alive preflop, <= 4 postflop; MC samples 170/130/96. v3: tighter deep preflop calls (+1.45).

## Log

- v1 accepted (001-5added71): 56.6 pts/table vs house zoo (60 tables).
- v2 accepted (002-fcf839c5): EV shove model, better preflop tables (30k samples). vs 7x v1: 23.5 (avg 21.6).
- Variant A (more bluffing driven by fold-to-bet rate): -1.7 vs v2 in mixed field -> reverted to v2 bluff logic + exploit only when fold rate >= 0.55.
- v3 accepted (003-1bdfb414): tighter preflop calling: +1.45 vs B.
- D (even tighter calling 0.12/0.36): -0.25 vs C -> rejected. E (thinner value bets 0.55/0.66): -0.4 vs C -> rejected.
- v4 accepted (004-89442ed9): ICM timing fix (see Last change).
- v5 accepted (005-c6e8f273): steal widening vs tight players + postflop call margin: +1.0 vs v4 (500 tables).
- localsim gets slow when the machine is busy (500 tables ~220 s); use <= 500 tables with timeout 250.
- H (SHOVE_BB 16): the test timed out three times under machine load and was never measured. bot/ was reverted to v5.
- Regression check, 300 tables (3x v5, 2x v2, 1x v3, nit, montecarlo): v5 averaged 23.4 per seat, v2 24.5 (its two seats were 28.5 and 20.4), v3 25.3. That is noise at this sample size, and the chained A/B tests favoured v5, so v5 stays active.
- Final sanity check, v5 vs house zoo, 50 tables, seed 51: 47.9 pts/table (1st), 0 substitutions.
- T1: rank 5/8, 20.74 pts/table. Places 1st 129, 2nd 101, 3rd 120, 4th 112, 5th 112, 6th 118, 7th 130, 8th 178. Leader b02 had 24.95. No substitutions.
- v6 accepted (006-071ff5d8): fixes for the early-bust leaks (see Last change).
- T2 (v6): rank 8/8, 20.26. Places 128/97/116/97/116/136/149/161. v7 (007-d301fafe) accepted for T3: tighter postflop calls (+0.5, noise).
- T3 (v7): rank 4/8, 20.89. Places 128/117/99/105/122/131/136/162. b02 leads every time (~26). 1st place is at par (12.8%), but 2nd-4th fall short (31% vs 37.5% expected) and 8th runs high (16%). We don't convert to the paid places, so the next fix is survival near the bubble: ICM-aware push/fold and calling with 5-6 players left (ICM is currently skipped at 6 alive for timing), and a larger SHOVE_MARGIN when a bust drops us from the paid places.
- T4: v7 kept. P3 tried bubble tightening: with 5-6 alive, a shove needed EV > 0.7bb instead of 0.1bb, and all-in calls at 6 alive needed pot odds + 4%. Over 500 tables P3 averaged 23.8 vs v7's 25.6 (-1.8), so I reverted it. Tightening up near the bubble seems to cost first places more than it gains in 2nd-4th. Next idea: the opposite direction (more aggression when short-handed), or postflop sizing.
- P4 (SHOVE_MARGIN -0.3bb): the test timed out and was never measured; reverted.
- T4 (v7): rank 7/8, 20.83. Places 124/114/117/120/110/129/138/148. 1 timeout in 113k decisions (cpu max 1.5ms, probably a GC pause; negligible).
- T5 window: H (SHOVE_BB 16) vs v7 over 500 tables: 24.6 vs 25.3 (-0.7), reverted. v7 stays for T5.
- Across T1-T4 we score 20.3-20.9 each time (field average 21.6). Every localsim gain of +1 to +1.5 has failed to show up in the real field, so the localsim field (our own copies plus house bots) is a poor proxy. Sample hands cover only each table's first ~10 hands, so the late game can't be seen in them. Next: look at call-call-fold lines postflop (calling flop and turn, then folding the river) and narrow a 3-bettor's postflop range.
- v5 vs house zoo, 80 tables: 44.2 +- 10 pts/table (1st). Occasional "hang" substitutions in localsim come from wall-clock delays on the loaded machine; thread CPU per call stays under ~0.5 ms.

## Known weaknesses / next steps
- Preflop opens and 3-bets are fixed by position, with no 4-bet bluffs. Deep preflop calls use a crude equity-vs-range check.
- Postflop: no check-raises and no draw-specific semi-bluffs (draws are only valued through MC equity). Bet sizing is fixed (40-75% pot).
- Shove-calling ranges come from PFR plus a stack-depth formula. Tracking each opponent's actual shove frequency would sharpen calls vs shove-happy bots.
- Ideas to test: SHOVE_BB 15-16; HU_OPEN 0.9; CALL_K 0.19 (expect wider callers); ICM-aware shove EV with <= 5 players.
- A/B noise is about +-1.3 pts/table at 1000 tables with 3v3 seats, so only trust differences of 1.5 or more, or repeat the run.
- Timing: postflop MC p50 ~145us, p99 ~230us thread CPU locally (busy machine shows up to ~500us p99).

## Key parameters (bot/agent.py top)
SHOVE_BB 13 (push/fold below), SHOVE_MARGIN 0.1bb, CALL_K 0.15 (opp call-range model), HU_OPEN 0.8, HU_RX 0.45, VAL_HU 0.6, CALL_MARGIN 0.09, CALL_PCT 0.45. MC samples 200/150/110 for 1/2/3 opponents.

## Testing method
localsim with 3 candidate seats vs 3 baseline seats + nit + montecarlo, 1000 tables (~2.5 min); compare seat averages (noise roughly +-1.3).
