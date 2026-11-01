# Team b04 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck, T-A, 4-card board). All equities are precomputed exactly (`precompute.py` -> `bot/tables.npz`): turn equity vs random / top-50% / top-25% hands for every (board, hole), flop equity averaged over turn cards, a 190x190 preflop heads-up matrix, preflop equity vs top-x% ranges and vs k random hands. Decisions are lookups plus pot-odds / chip-EV arithmetic (~10-50 us per act).

**Before the flop:** Hands ranked by equity vs one random hand (AA 69%, KK 61%, AK 60% ... TT 37%). Unopened with >14 BB effective: open to 2.5 BB (+1 BB per limper, +1 BB from blinds) with the top 17% (7 behind) up to 55% (SB), 70% heads-up SB; tighter with limpers. Facing a raise deep: 3-bet top 4-7%, call top 30% if cheap, otherwise call only on equity vs the raiser's estimated range (from observed PFR) beating pot odds by 12%. At <=14 BB: shove-or-fold by chip EV, assuming each player behind calls with the top 22% and computing equity vs that range. Facing all-ins or committing raises: call when equity vs the shover's estimated range (PFR-based, >=35% wide for short shovers, >=50% heads-up, >=30% for late-position steals) beats pot odds +2%.

**After the flop:** Strength = exact equity vs a top-50% range (value bets) or vs top-25% (big bets/raises), raised to the number of opponents. Bets 60-75% pot when strength >= 0.62 flop / 0.58 turn (4 points thinner against opponents who rarely fold). Calls when range-adjusted equity beats pot odds +3%; raises with very strong hands (top-25% equity >= 0.72). Heads-up bluffs with low equity at a rate tied to the opponent's observed fold rate; semi-bluffs flop with equity >= 0.5.

**Short stacks and the points table:** Payouts 100/25/5 are top-heavy, so the bot plays close to chip-EV (small +2% margin on all-in calls); push/fold below 14 BB.

**Opponents:** Per-seat counters from hand histories: VPIP, PFR, postflop aggression, calls, folds. Used for the raiser's range width, bluff frequency, value thresholds vs calling stations, and widening calls vs maniacs.

**Last change:** v3: heads-up widening (SB opens 70%, defends vs a 50% range), BB no longer raises 100% vs limpers, steal-spot detection, thinner value vs stations. v1 vs montecarlo-heavy field: 39.5 pts/table (field average 16.25).

## Test log
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
