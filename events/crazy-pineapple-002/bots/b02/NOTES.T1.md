# Team b02 notes

## Strategy

**Summary:** A precomputed equity table for 3-card starting hands drives the preflop ranges. It covers all 1755 suit-isomorphic classes, simulated with realistic flop discards. Every all-in decision (shoves, call-offs, postflop commits) is decided by ICM: exact Malmuth-Harville on the real stacks when 5 or fewer players remain, a precomputed table otherwise. Postflop, a Monte Carlo capped at 0.4 ms estimates equity; its samples are cut down to the share of opponent hands that fits what each opponent has done this hand.

**Before the flop:** It opens the top ~14% of 3-card hands from UTG up to ~55% from the SB, ~48–62% 3-handed and 80% heads-up. Opens are 2.5–3.3bb (2.2bb heads-up) and get wider against blinds that fold a lot to raises. At ≤12bb effective (≤16bb with ≤2 players behind) it plays shove-or-fold and picks the action with the higher ICM EV. Shove EV = P(all fold)·U(steal) + Σ P(seat calls)·[equity vs that seat's calling range], with call widths taken from each seat's fold-to-raise rate. Facing a raise, it uses equity against the raiser's range, which comes from their PFR (at least 55% heads-up, 35% 3-handed, and wider for short stacks). It 3-bets at ≥60% equity and calls when equity beats the pot odds by a margin. Big calls go through ICM, and it assumes no fold equity against raisers who have already committed half their stack.

**After the flop:** Monte Carlo against random holdings; on the flop, opponents get best-of-8 with their 3 cards. Samples are sorted by the strongest opponent's final hand, and equity is taken against the top X%. X shrinks with each opponent action this hand: preflop by VPIP/PFR, ×0.72 per postflop call, ×0.55 per raise scaled by aggression, ×0.5 more for re-raises, and by bet size on the current street. On the flop and turn it uses 1.45× / 1.2× wider ranges because of draws. With no bet in front, it bets 60–80% pot for value when equity against the calling range (60% of X) is ≥ 0.5. Otherwise it c-bets or stabs at a frequency scaled ×1.5 and by the opponents' fold-to-bet. Facing a bet, it raises when it is well ahead, calls when equity ≥ pot odds (+0.03 on the river), and decides commits by ICM. On discard, it keeps the two cards with the best Monte Carlo win rate.

**Short stacks and the points table:** ICM utility drives every shove, call-off and commit, so it tightens when shorter stacks are blinding out and pressures when it covers. Exact ICM (25 µs at 5 players) matters most in 4–5-handed spots where a short stack is blinding off.

**Opponents:** For each seat it tracks VPIP, PFR, fold-to-raise, fold-to-bet and postflop aggression, smoothed with priors. These feed steal width, shove call probabilities, raiser range width, bluff frequency and the width of a bettor's range.

**Last change:** v8: preflop value 3-bet threshold lowered from 0.64 to 0.60 equity vs the raiser's range. Against v7 copies: self-play +4.2 (36.1 vs 31.9), mixed field +0.1, tight field +2.3. (v7 raised bluff frequency ×1.5; v6 moved push/fold to ≤12bb and HU opens to 2.2bb.)

## Submissions
- 001 v1 initial; 002 v3 exact ICM + range narrowing; 003 v4 short-handed widen; 004 v5 re-raise narrowing + timing margin; 005 v6 push 12bb + HU 2.2bb; 006 v7 bluff ×1.5; 007 v8 3-bet threshold 0.60 (ACTIVE).

## Test log (tools/sim.py, 250–400 tables, ±3.5 noise per entry)
- Zoo (seed 11): v1 59.3, v2 61.6, v3 66.6, v7 62.7 (nit ~47, checkfold ~44).
- Self-play, against 7 copies of an older version (break-even 31.9): v4-ish vs v3 33.0; v5-ish vs v4 33.2; v6-ish vs v3 36.5; v6 vs v5 36.3; **v7 vs v1 40.6** (rarely busts early: 7th/8th only 10%).
- rr 0.35 vs v7: self-play −0.8, mixed field +1.0 → not adopted.
- Final official localsim checks of v8 (007): house zoo 61.6 pts/table (nit 47.6, checkfold 44.6), 300 tables, seed 7; vs 7 copies of submission 001: 41.6 (copies 27–33), seed 8. Max decision 690 µs, 0 substitutions.
- Last check: v8 vs a mix of copies of 006/004/002 (localsim, 250 tables, seed 9): v8 31.3, v7 copies 31.4–36.2, v5 copies 31.0–33.5, v3 copies 27.4–29.0. So v8 vs v7 is a wash (+4.2, +0.1, +2.3, −3.0 across tests). For the patch window: revisit the 3-bet threshold (0.60 vs 0.64) with bigger samples.
- 3-bet threshold: 0.60 vs v7 (0.64) +4.2 / +0.1 / +2.3 → adopted in v8; 0.56 vs v8 self-play 29.5 (−2.4) → 0.60 looks about right.
- Tried and rejected (vs 7× baseline): tighter opens ×0.8 (−9 mixed field), push at 18bb (−8), vb 0.45 (−3), call margin ±0.03 (−2 each), flop opponents keep their best 2 (−1.4), wf 1.6 (±0), opens ×1.3 (−1.4).
- Robustness: an always-shove bot and a calling station finish last, at 6.6 and 3.7 points per table.

## Key parameters (bot/agent.py `_P`)
push_bb 12, open_mult 1.15, bluff_mult 1.5, vb 0.5, call_margin 0, rr 0.5, wf 1.45, wt 1.2, hu_open 2.2. Postflop MC budget 0.4 ms wall time; discard MC 0.38 ms. Local p99 is ~470 µs.

## Known weaknesses / next steps
- Preflop percentile table is noisy (1200+500 samples per class). Rerun tools/pre.py with more samples, then tools/pre2.py, which depends on its percentiles.
- ICM for 6–8 players assumes the other stacks are equal.
- Postflop X-filtering by final hand value is crude: it can't tell a strong made hand from a draw. Facing raises in multiway pots is still the most common way we bust.
- No check-raise, no 4-bet bluff, no explicit squeeze logic.
- Preflop raiser range comes from PFR across all positions, with no positional adjustment except short-handed.
- Tools: tools/sim.py (place distributions), tools/mk.sh NAME "{dict}" builds parameter variants, tools/dbg logs bust hands to tools/bust.txt.
