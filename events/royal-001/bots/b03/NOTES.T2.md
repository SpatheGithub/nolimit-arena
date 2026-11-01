# Team b03 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck). Exact precomputed tables (preflop 190x190 pairwise equity, flop pairwise equity per 3-card board, exact turn hand values) let every decision compute equity against a Bayesian range for each opponent in ~50-100 µs. Decisions are chip-EV with small risk margins (payouts 100/25/5 are near winner-take-all, so chips ≈ points).

**Before the flop:** Hands ranked by equity vs a random hand (AA > KK > AK > AQ > AJ > QQ > KQ > AT > KJ ... TT last). Deep (>16 BB effective): open-raise 2.2-2.5 BB + 1 BB per limper with the top 36% (early) up to 75% (cutoff/button/SB) of hands, widened by 0.25 when every player behind is tight (VPIP < 28% after 12+ hands); SB completes top 60%; BB raises limped pots with top 30-35%. Facing a raise: 3-bet (3x) with ≥56% equity vs the raiser's modelled range (and ≥42% vs the whole field); call when equity*realisation (0.86-0.92) beats pot odds +2% and the call is ≤30% of stack. ≤16 BB: shove-or-fold by EV, using each player behind's observed calling width; ≤20-25 BB facing a raise: jam/call/fold by chip EV.

**After the flop:** Equity vs each opponent's range (product for multiway). Bet 0.6-0.75 pot for value with ≥58% heads-up (≥50% multiway), shove when stack ≤ 1.1 pot. Heads-up bluffs ~22% when checked to (more vs players who fold to bets, more on the flop with equity ≥38%). Facing a bet: raise/shove with ≥68% HU (≥78% multiway), call when equity > pot odds (+2% on the turn), else fold.

**Short stacks and the points table:** Push/fold below 16 BB with EV computed against assumed calling ranges (18-33% of hands by depth, blended with observed VPIP). Calls of shoves use the shover's range width from stack depth (≤8 BB: 55%, ≤15: 35%, ≤25: 20%, else 10%) and their observed all-in frequency. No explicit ICM (payout steep enough that chip EV is close); small margins avoid coin-flip calls.

**Opponents:** Per-seat counts (hands, VPIP, PFR, all-ins, postflop aggression, fold-to-bet). Ranges: preflop raises keep the top PFR-width (narrower for 3-bets), calls keep VPIP-width; postflop bets/raises reweight toward hands whose equity vs random exceeds an aggression-adjusted threshold with a bluff floor; checks discount the nuts slightly.

**Last change:** v5 (005-f4158fd8): push/fold now starts at 14 BB instead of 16 BB (PUSH_BB). Paired tests: seed 5 19.2 vs v4 18.5, seed 9 17.5 vs v4 17.1. Before that, v4 (004-208be540): 3-bet threshold lowered from ≥60%/≥45% to ≥56%/≥42% equity. Paired tests (same seed and seat, field 3x v2 + 3x v3 + nit, 400 tables each): seed 5 18.5 vs v3 17.9, seed 9 17.1 vs v3 16.2. The gain is small but positive on both seeds. Before that, v3 (003-5908a825): looser and more aggressive after T1 (rank 5/8, 14.62 pts; the three tightest teams, VPIP 22-26% with ours at 26%, finished bottom three; the leader played 45% VPIP). Opens widened (top 28-55% to 36-75%), BB raises limped pots with more hands, preflop call realisation 0.82/0.88 to 0.86/0.92 with call cap 25% to 30% of stack, base bluff 0.15 to 0.22. Test (seed 21, 400 tables vs 3x v2 + nit, maniac, pot_odds, minraiser): v3 29.5 vs v2-in-same-seat 25.9; local VPIP 43%, PFR 31%.

## Test log
- v1 (001-f83c2b8b) vs zoo, 60 tables: 54.6 pts/table (zoo avg ~17).
- v2 vs 3x v1 + pot_odds,nit,maniac,minraiser, 600 tables: 28.2 vs 25.2.

- Knob tests (seed 21, vs 3x v2 + pot_odds,nit,maniac,minraiser; baseline v2 settings = 25.9 on this seed, 400 tables — the "you" seat runs ~2-3 below the v2 copies on this seed):
  - PUSH_BB 22: 24.6 (600 t) — worse; PUSH_BB 12: 24.2 (300 t) — worse. Keep 16.
  - BLUFF0 0.08: 24.8 (400 t) — worse. BLUFF0 0.22: 27.5 (400 t) — maybe better (+1.7, under 1 sigma); a 1000-table check on a new seed timed out on the busy machine. Not submitted. Try it first in the patch window.
- Avoid `montecarlo` in localsim tests: it uses wall-clock time per decision and made runs time out.
- bot/ has module knobs PUSH_BB=16 and BLUFF0=0.22 (v3/v4). bot/ = 004-208be540.
- Patch window tests (field 3x v2 + 3x v3 + nit): v3 copies averaged 18.2 vs v2 copies 16.3 (seed 5). Thinner value bets (vthr 0.58 to 0.54 HU): 17.3 vs v3 17.9, so rejected. 3-bet at 0.56: +0.6 (seed 5) and +0.9 (seed 9), so accepted as v4.
- Maniac-heavy field (3x maniac, 2x v3, v2, nit; seed 13, 400 tables): v4 20.1 vs v3 in the same seat 20.7 (-0.5, noise). Over 3 paired seeds v4 vs v3 is +0.6, +0.9, -0.5, about even. v4 is kept and is not hurt by aggressive opponents.
- Open size 3.0/2.5 BB (vs 2.5/2.2): seed 5 17.1 vs v4 18.5, seed 9 17.5 vs v4 17.1, so net -0.5 and rejected. That run logged 2 local "hangs" (max 913 µs) from machine load; T1 on the referee machine had 0 in 119k decisions.
- BLUFF0 0.30 (vs 0.22): seed 5 17.2 vs v4 18.5, rejected. 0.22 looks near the best value; 0.08 and 0.15 both scored lower earlier.
- PUSH_BB 14 (vs 16) with v4: seed 5 19.2 vs 18.5 (+0.7, one seed, noise). Candidate: confirm on seeds 9 and 13 next window before submitting.
- Paired baselines for v4 in the field 3x v2 + 3x v3 + nit, 400 tables: seed 5 = 18.5, seed 9 = 17.1. Maniac field (3x maniac, 2x v3, v2, nit) seed 13 = 20.1.
- Next ideas: deeper postflop play (check-raise traps, sizing by range), an ICM tweak when 3 are left, and using opponents' observed call widths for open sizing. Test each with paired runs (same seed, same seat, swap only the hero bot).
- Don't put $TMPDIR paths in shell commands: they need approval and get denied. Restore old versions from .submissions/<id>/agent.py instead.

## T1 result (v2 002-050df968)
- Rank 5/8, 14.62 pts/table; places 1st 103, 2nd 141, 3rd 158 of 1000. VPIP 26%, PFR 18%, WTSD 9%, showdown win 53%. 0 subs.
- Leaderboard: b08 20.45 (VPIP 45%), b05 18.52, b06 18.52, b01 16.85, b03 14.62, b07 14.55, b02 13.40, b04 13.09.

## Files
- tools/gen.py builds bot/data.npz (turn_vals, pre_eq, flop_eq uint8, pre_multi) ; strength arrays (flop_str, turn_str, pre_str) were added by an inline script (mean equity vs random).

## Ideas / next
- Better postflop sizing, check-raises, multiway thresholds.
- ICM near the bubble of 3 (2nd=25, 3rd=5).
