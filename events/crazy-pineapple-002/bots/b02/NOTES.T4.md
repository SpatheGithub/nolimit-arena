# Team b02 notes

## Strategy

**Summary:** A precomputed equity table for 3-card starting hands drives the preflop ranges. It covers all 1755 suit-isomorphic classes, simulated with realistic flop discards. Every all-in decision (shoves, call-offs, postflop commits) is decided by ICM: exact Malmuth-Harville on the real stacks when 5 or fewer players remain, a precomputed table otherwise. Postflop, a Monte Carlo capped at 0.4 ms estimates equity; its samples are cut down to the share of opponent hands that fits what each opponent has done this hand.

**Before the flop:** It opens the top ~14% of 3-card hands from UTG up to ~55% from the SB, ~48–62% 3-handed and 80% heads-up. Opens are 2.5–3.3bb (2.2bb heads-up) and get wider against blinds that fold a lot to raises. At ≤12bb effective it plays shove-or-fold and picks the action with the higher ICM EV. Between 12bb and 16bb with ≤2 players behind, it shoves when that is +EV and otherwise falls back to a normal open-raise. Shove EV = P(all fold)·U(steal) + Σ P(seat calls)·[equity vs that seat's calling range], with call widths taken from each seat's fold-to-raise rate, scaled ×0.8. Facing a raise, it uses equity against the raiser's range. That range comes from their PFR, widened by the opener's position (×1.12 hijack to ×2.0 SB), at least 55% heads-up and 35% 3-handed, and wider for short stacks. It 3-bets at ≥60% equity and calls when equity beats the pot odds by a margin. Big calls go through ICM, and it assumes no fold equity against raisers who have already committed half their stack.

**After the flop:** Monte Carlo against random holdings; on the flop, opponents get best-of-8 with their 3 cards. Samples are sorted by the strongest opponent's final hand, and equity is taken against the top X%. X shrinks with each opponent action this hand: preflop by VPIP/PFR, ×0.72 per postflop call, ×0.55 per raise scaled by aggression, ×0.5 more for re-raises, and by bet size on the current street. On the flop and turn it uses 1.45× / 1.2× wider ranges because of draws. With no bet in front, it bets 60–80% pot for value when equity against the calling range (60% of X) is ≥ 0.5. Otherwise it c-bets or stabs at a frequency scaled ×1.5 and by the opponents' fold-to-bet. Facing a bet, it raises when it is well ahead, calls when equity ≥ pot odds (+0.03 on the river), and decides commits by ICM. On discard, it keeps the two cards with the best Monte Carlo win rate.

**Short stacks and the points table:** ICM utility drives every shove, call-off and commit, so it tightens when shorter stacks are blinding out and pressures when it covers. Exact ICM (25 µs at 5 players) matters most in 4–5-handed spots where a short stack is blinding off.

**Opponents:** For each seat it tracks VPIP, PFR, fold-to-raise, fold-to-bet and postflop aggression, smoothed with priors. These feed steal width, shove call probabilities, raiser range width, bluff frequency and the width of a bettor's range.

**Last change:** No change for T4: v11 won T3 (rank 1/8, 34.2 points per table). v11 (active, 010-6583be76): in the 12–16bb band with ≤2 players behind, a hand that isn't a +EV shove now gets a normal open-raise (2.2bb heads-up) instead of a fold. v10 folded 65% of heads-up SB hands at 16bb; v11 folds 19%. Against v10 copies: 0.0 self-play, +3.7 mixed field, −3.6 on localsim seed 67, so neutral on average. Not submitted: v12 (tools/v12), which applies the fallback only from the SB and keeps the button on shove-or-fold. v12 scored 32.7 vs v10 copies on seed 67 (where v11 got 28.2) but only 31.4 vs v11 copies (−0.5), so it isn't proven better. Revisit next window. v10 folded 65% of heads-up SB hands at 16bb (measured with tools/hu_test.py); v11 folds 19%. Against v10 copies: 0.0 in self-play and +3.7 in a mixed field with a min-raiser (300 tables each). T2 with v10: rank 4/8, 33.5 points per table. Earlier: v10 (T2) made two preflop changes since v8, which played T1 (rank 2, 35.9). (1) v9: the opener's range widens with position: ×2.0 SB vs BB, ×1.7 button, ×1.35 cutoff, ×1.12 hijack, capped at 70%. Against v8 copies: +1.6, +1.1, +2.0, −2.0. (2) v10: assumed call probability vs our shoves ×0.8, so it shoves somewhat wider. Against v9 copies: +1.8 and +3.8 in self-play, +0.6 in the mixed field.

## Submissions
- 001 v1 initial; 002 v3 exact ICM + range narrowing; 003 v4 short-handed widen; 004 v5 re-raise narrowing + timing margin; 005 v6 push 12bb + HU 2.2bb; 006 v7 bluff ×1.5; 007 v8 3-bet threshold 0.60 (played T1: rank 2, 35.9); 008 v9 position-aware opener range; 009 v10 shove-caller probability ×0.8 (played T2: rank 4, 33.5); 010 v11 push-zone fallback to open-raise, ≤2 behind (ACTIVE). v12 (SB-only fallback) is in tools/v12, not submitted. bot/ == v11.

## T3 result (v11, 010-6583be76): kept for T4
- Rank 1/8, 34.16 points per table (b07 33.94, b01 33.40, b04 32.98). Places 1st–8th: 140 110 141 152 152 134 101 70. VPIP 25.5%, PFR 19.4%, showdown win 53%. 0 substitutions; max CPU 782 µs (p99 500).
- Weighted total after T3: 205.48, rank 2.
- Patch window before T4: tested the heads-up-only small-raise defence (HU BB calls a 2.2bb open by pot odds instead of a call-as-all-in at ≤22bb; defends 95% instead of 50%). Against v11 copies: +0.8 and −0.7 self-play, −1.4 mixed field → NOT adopted (tools/var_hud, built by tools/mk_hud.py). Also tested a less risk-averse utility, 0.7·ICM + 0.3·chip-linear (tools/mk_blend.py): +0.4 self-play (but 8th place 17%, 1st 11%), −0.9 mixed field → NOT adopted; exact ICM stays. Also tested 2.2bb opens at ≤25bb, instead of 2.5–3.3bb (tools/mk_small.py): +1.7, −2.4 self-play, −1.2 mixed → NOT adopted. v11 kept: T3 rank 1, and no tested alternative is better.

## T2 result (v10)
- Rank 4/8, 33.53 points per table (b07 35.34, b01 34.41, b08 33.78). Places 1st–8th: 119 117 164 167 139 130 99 65. 0 substitutions.
- VPIP rose 24.3 → 26.0% and showdown win rate fell 54.5 → 51.4% vs T1. The field also changed: b05 gained 2.3 and b06 3.4, taken from the top bots (b07 −2.2, us −2.4, b01 −0.9).
- Sample hands are again only the first 10 hands of each table.
- Leaks found with tools/hu_test.py (preflop decision frequencies on 2500 random hands):
  (1) HU SB at 13–16bb folded 65% (shove-or-fold with no fallback). Fixed in v11.
  (2) At ≤22bb, facing a small raise, calling was judged as if all-in, so HU BB folded 50% to a 2.2bb open. A fix (defend by pot odds, re-shove by ICM) tested −0.6/−0.5 self-play and +2.0 mixed; restricted to ≤3 players it tested −1.2/−1.3. NOT adopted. Worth revisiting with more samples, since in theory it's clearly a leak.

## T1 result (v8)
- Rank 2/8, 35.91 points per table (b07 37.49 first; b01 35.34). Places 1st–8th per 1000 tables: 140 129 153 175 141 114 85 63. 0 substitutions; p99 500 µs, max 754 µs.
- The winners are tighter (VPIP 20%, PFR 16–17%); we were at 24/19. Most common finish is 4th, so we often reach the last 4 without converting.
- sample_hands.json only has the first 10 hands of 4 tables (level 1), which is little to go on. Patch-window tests rejected: squeezing with premiums over callers (−2.7 vs v8 copies) and opens ×1.0 (−0.5 vs v9). v9 on the house zoo: 67.4 points per table. Caller probability ×0.65 vs v10: −0.3 (neutral), so ×0.8 kept. v10 on the house zoo (localsim seed 27): 66.1 points per table, max decision 630 µs, 0 substitutions. v10 vs 7 copies of v8 (007, localsim seed 37): 32.5 (break-even 31.9), so the T2 bot is level with or slightly ahead of the T1 bot. v10 vs a mix of v9/v8/v7 copies (localsim seed 47, 250 tables): 32.4 (break-even 31.9). Next window: get more samples before changing anything; ideas include a better HU strategy, a positional BB-defence check, and rerunning the preflop table with more samples.

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
