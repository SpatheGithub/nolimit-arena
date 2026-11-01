# Team b04 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck, T-A, 4-card board). All equities are precomputed exactly (`precompute.py` -> `bot/tables.npz`): turn equity vs random / top-50% / top-25% hands for every (board, hole), flop equity averaged over turn cards, a 190x190 preflop heads-up matrix, preflop equity vs top-x% ranges and vs k random hands. Decisions are lookups plus pot-odds / chip-EV arithmetic (~10-50 us per act).

**Before the flop:** Hands ranked by equity vs one random hand (AA 69%, KK 61%, AK 60% ... TT 37%). Unopened with >14 BB effective: open to 2.5 BB (+1 BB per limper, +1 BB from blinds) with the top 17% (7 behind) up to 55% (SB), 70% heads-up SB; tighter with limpers. Facing a raise deep: 3-bet top 4-7%, flat the top 30% when cheap (<=8% of stack), otherwise call only when equity vs the raiser's estimated range (from observed PFR) beats pot odds by 12%. At <=14 BB: shove-or-fold by chip EV, assuming each player behind calls with the top 22%. Facing all-ins or committing raises: call when equity vs the shover's estimated range (PFR-based, >=35% wide for short shovers, >=50% heads-up, >=30% for late-position steals) beats pot odds +2%.

**After the flop:** Strength = exact equity from tables vs random / top-50% / top-25% hands. Value-bets 60-75% pot when equity vs top-50% (to the power of opponents) >= 0.57 flop / 0.54 turn (4 points thinner vs players who rarely fold). Facing a bet, the assumed bettor range depends on size: small bets -> mostly random-hand equity (0.3 top50 + 0.7 random), half-pot+ -> 50/50 blend, pot+ -> 0.7 top50 + 0.3 random, re-raises -> top50/top25 blend; calls when that beats pot odds. Raises with very strong hands (top-25% equity >= 0.72). Heads-up bluffs with low equity at a rate tied to the opponent's fold rate; semi-bluffs flop with equity >= 0.5.

**Short stacks and the points table:** Payouts 100/25/5 are top-heavy, so the bot plays close to chip-EV (small +2% margin on all-in calls); push/fold below 14 BB.

**Opponents:** Per-seat counters from hand histories: VPIP, PFR, postflop aggression, calls, folds. Used for the raiser's range width, bluff frequency, value thresholds vs calling stations, and widening calls vs maniacs.

**Last change:** v6 (004-d0c41f3a) = v3's preflop (the T1 version) + v5's postflop. T1 (v3) finished 8th of 8 at 13.09: it went to showdown only 13.8% of the time but won 63% there, so it over-folded after the flop. The preflop evidence was ambiguous (b05 played 37/16 and finished 2nd). v6 calls flop/turn bets on a less pessimistic range assumption (small bets: 0.3 top50 + 0.7 random-hand equity; half pot: 50/50; pot+: 0.7/0.3; raises: top50/top25 blend; no margin over pot odds) and value-bets thinner (0.57 flop / 0.54 turn). Seed 57, 200 tables vs 2x v3 + house bots: v6 28.8 (1st), v3 copies 22.8 / 21.7; v5 on the same seed scored 21.4.

## Test log
- v6 (004-d0c41f3a): seed 57, 200 tables: 28.8 (1st) vs v3 copies 22.8 / 21.7. Seed 71, 200 tables vs 2x v3 + v5 + house bots: v6 18.5, v3 23.6 / 22.2, v5 22.5. So v3/v5/v6 are within local noise of each other (+-5); v6 is kept because it targets the one leak T1 clearly showed. Saved as work/agent_v6.py; v5 = work/agent_v5.py, v3 = work/agent_v3.py.
- T1 real field (v3): rank 8/8, 13.09 +-1.86. Leaderboard: b08 20.45 (VPIP 45 / PFR 26), b05 18.5 (37/16), b06 18.5 (35/21), b01 16.9 (32/19), b03 14.6 (26/18), b07 14.6 (24/18), b02 13.4 (22/17). Places 1st..8th: 100,104,98,114,139,140,147,158.
- v5 (003-b4bff896) seed 57, 200 tables vs 2x v3 + 2x montecarlo + pot_odds + maniac + nit: v5 21.4, v3 copies 28.0 / 24.7. Locally v5 is ~2-3 pts below v3 against loose house bots, but v3 was last in the real (tighter) field, so v5 is kept for T2. NEXT WINDOW: compare T2 with T1 (13.09). If T2 is not better, revert to v3's preflop parameters (`work/agent_v3.py`) and keep only the postflop calling change.
- v4 (looser everywhere incl. more flat calls): 17.4 / 18.6 vs v3 copies ~20 locally; replaced by v5 (fewer flat calls, more raising).
- v3 = submission 002-d7e6ed0c (accepted 13:30:55, active for T1). Seed 11 vs 2x v1 + 3x montecarlo + maniac + nit, 100 tables: v3 26.7, v1 copies 25.5 / 19.0. Zoo 60 tables: v3 33.9 (1st), montecarlo 31.3.
- Seed 23, 80 tables, 2x v1 + 2x montecarlo + pot_odds + maniac + nit: v3 24.25, v1 copies 28.7 / 23.1, best house bot 13.3. v3 and v1 are within noise of each other; both clearly beat the house bots.
- Machine load makes 100-table runs take 40-370 s; run benchmarks in the background and poll.
- v1 (001-5a673031): zoo 30 tables 30.8 (2nd behind montecarlo 35.5); vs 4x montecarlo+pot_odds+threshold+maniac 60 tables: 39.5 (1st).
- Per-opponent shove-call model from VPIP made it worse (18 vs v1 copies 28): reverted to fixed 22% caller range.
- Calibration: on seed 11, v1 as "you" scores 20.6 vs its copies 26.5/24.2, so seat noise is +-6 at 100 tables.

## Known weaknesses / next steps
- Push/fold call model is fixed (22%); a better model would track how often each seat calls shoves.
- No ICM adjustment near the end (payouts top-heavy, so this probably costs little).
- Postflop ignores position and board texture beyond the equity tables; no turn probe/check-raise logic.
- Flop top-25% equity is extrapolated, not computed.
