# Team b03 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck). Exact precomputed tables (preflop 190x190 pairwise equity, flop pairwise equity per 3-card board, exact turn hand values) let every decision compute equity against a Bayesian range for each opponent in ~50-100 µs. Decisions are chip-EV with small risk margins (payouts 100/25/5 are near winner-take-all, so chips ≈ points). For T6: v8 (2nd in T4) plus bet-size-aware opponent ranges (012-e1377362).

**Before the flop:** Hands ranked by equity vs a random hand (AA > KK > AK > AQ > AJ > QQ > KQ > AT > KJ ... TT last). Deep (>14 BB effective): open-raise 2.2-2.5 BB + 1 BB per limper with the top 36% (early) up to 75% (button/SB) of hands, widened by 0.25 when every player behind is tight (VPIP < 28% after 12+ hands); SB completes top 60%; BB raises limped pots with top 30-35%. Facing a raise, equity counts only players who put money in voluntarily (×0.95 per player still to act): 3-bet (3x) with ≥56% vs the raiser's modelled range and ≥42% overall; call when equity × realisation (0.86-0.92) beats pot odds +2% and the call is ≤30% of stack. ≤20-25 BB facing a raise: jam/call/fold by chip EV.

**After the flop:** Equity vs each opponent's range (product for multiway; facing a bet, players who haven't put chips in on this street count 60% toward cutting our equity). Bet 0.6-0.75 pot for value with ≥58% heads-up (≥50% multiway), shove when stack ≤ 1.1 pot. Heads-up bluffs when checked to: 22% base, +0.4 × (opponent fold-to-bet rate - 30%), +15% on the flop with equity ≥38%, another +15% on the flop as the last preflop raiser. Opponent bets are read as stronger the bigger they are relative to the pot. Facing a bet: raise/shove with ≥68% heads-up (≥78% multiway), call when equity > pot odds (+2% on the turn), else fold.

**Short stacks and the points table:** Shove-or-fold at ≤14 BB, with EV computed against calling ranges of 18-33% by depth, blended with each player's observed VPIP. Calls of shoves use the shover's range width from stack depth (≤8 BB: 55%, ≤15: 35%, ≤25: 20%, else 10%) and their observed all-in frequency (prior (n+0.5)/(hands+10)). No explicit ICM (the payout is steep enough that chip EV is close); small margins avoid coin-flip calls.

**Opponents:** Per-seat counts (hands, VPIP, PFR, all-ins, postflop aggression, fold-to-bet). Ranges: preflop raises keep the top PFR-width (narrower for 3-bets), calls keep VPIP-width; postflop bets/raises reweight toward hands whose equity vs random exceeds an aggression-adjusted threshold with a bluff floor; checks discount the nuts slightly. Fold-to-bet raises bluff frequency vs folders.

**Last change:** v12 (012-e1377362) = v8 plus bet-size-aware ranges. When an opponent bets or raises after the flop, the range threshold rises by 0.08 x (min(2, bet/pot) - 0.6) and the bluff floor is divided by 1 + max(0, bet/pot - 1), so overbets and shoves get stronger ranges. Preflop all-in frequency prior lowered from (n+1)/(hands+8) to (n+0.5)/(hands+10), so early deep 4-bet shoves read as about 5% instead of 12.5%. Aimed at early busts (8th place 13.7-15.4% in T3-T5 vs 12.5% fair). Clean paired tests vs v8 (400 tables, 0 hangs, 0 errors in debug mode): F seed 9 19.9 vs 19.4, limper seed 9 25.1 vs 23.5, F seed 13 22.2 vs 21.0, limper seed 13 27.2 vs 25.8; 4/4 positive, mean +1.2. Head-to-head (3x v12 vs 3x v8 at the same tables, 400 tables): with nit and maniac, seed 41 -0.7, seed 43 +3.1; with pot_odds and threshold, seed 41 +1.9, seed 43 +2.2 (mean +1.6; v10 in the same test was -0.1). v9/v10 (adaptive fold-rate thresholds) were dropped after T5 (16.20 vs T4's 18.64 with v8).

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

## T2 result (005-f4158fd8)
- Rank 5/8, 16.45 pts/table (T1 14.62); places 1st 122, 2nd 144, 3rd 130, 4th 134, 5th 155. VPIP 29%, PFR 21%, WTSD 11%, showdown win 54%. 0 subs.
- Leaderboard: b08 21.52 (VPIP 44%, PFR 24%), b05 19.02 (38/16), b01 18.34, b06 17.55, b03 16.45, b02 13.48, b04 12.55, b07 11.10.
- The low VPIP relative to PFR led to the multiway-equity bug fixed in v6.

## Patch window before T3
- Maniac field (3x maniac, 2x v3, v2, nit; seed 13): v7 23.5 vs v4 20.1 and v3 20.7 in the same seat. The equity fixes help most vs aggressive raisers.
- Rejected on top of v7: over-limping (limper field -0.6, +0.2) and UNACTED_PEN 0.90 (F seeds 9 and 13: +0.7, -0.8). Keep 0.95. POST_UNACT 0.4 (limper field: -0.3, -0.6), so keep 0.6. All-in call margins at 0 (were +2% odds and 1% of the effective stack in EV): F seed 9 20.9 vs 20.3, seed 13 19.6 vs 19.7. Limper field: 24.4 vs 24.6, 24.3 vs 25.3. Rejected; keep the margins.
- Next ideas: postflop check-raise and sizing by range; ICM when 3 are left; a b08-like loose-passive test opponent (44% VPIP, 24% PFR) to stand in for the leaders.
- Over-limping behind limpers (OVERLIMP 0.2) on top of v6: limper field seed 9 24.3 vs 24.5, seed 13 26.3 vs 25.0. Never triggers vs fields without limpers. Not shipped in v7.
- v6 baselines: field F (3x v5, 2x v4, nit, maniac) seed 5 18.3, seed 9 20.1, seed 13 19.5; limper field seed 9 24.5, seed 13 25.0. Zoo check (house bots except montecarlo, plus v6; seed 3, 300 tables): v7 37.5, v6 45.2 (different seats, ±5), house bots ≤12.5; 0 subs.
- v7 baselines (400 tables each): F seeds 5/9/13 = 18.1/20.3/19.7; limper field seeds 5/9/13 = 25.5/24.6/25.3; maniac field seed 13 = 23.5.

## T3 result (007-9c75a0b1)
- Rank 3/8, 17.27 pts/table; places 1st 136, 2nd 124, 3rd 114 ... 7th 138, 8th 145 (more early busts, more wins). VPIP 35%, PFR 24%, WTSD 14%, showdown win 54%. 0 subs.
- Leaderboard: b08 20.48 (40/25), b05 19.50 (38/16), b03 17.27, b01 17.00, b06 16.98, b02 13.96, b04 12.71, b07 12.10.

## Patch window before T4
- Turn value-bet threshold 0.64 (vs 0.58): F +0.9/-2.1, limper -0.6/+0.4, so rejected.
- C-bet bonus 0.15 as preflop raiser: accepted as v8 (see Last change).
- The machine was heavily loaded (load average 15-17; runs of 400 tables took 60-200+ s and several timed out); local hangs come from load.
- CBET_BONUS 0.30: both test runs timed out with no result. A candidate for the next window (v8 baselines: F seeds 9/13 19.2/21.0; limper seeds 5/9/13 29.1/26.0/26.0).
- Safer A/B under load: put the candidate in tools/cand/ (copy __init__.py, data.npz and cats.json from .submissions/<id>/ plus the modified agent.py) and seat it as an opponent, so bot/ is never modified. The 3x cand (CBET 0.30) vs 3x v8 run (seed 17, 300 tables) also timed out at 200 s. With 200 tables (98 s): cand 20.4/20.4/16.1 (avg 19.0) vs v8 18.9/17.0/16.1 (avg 17.3), +1.6 unpaired (about ±3). Promising but unconfirmed; confirm with paired runs next window before shipping. (A seed-23 run of 200 tables timed out under load.) Seed 23 with 150 tables: cand avg 20.0 vs v8 18.5 (unpaired). Paired limper seed 9: cand 22.6 vs v8 26.0 (-3.3). Rejected; keep CBET_BONUS 0.15.
- If a localsim run may be killed, keep the restore step separate: a killed command skips the trailing `cp .submissions/<id>/agent.py bot/agent.py`.

## T4 result (008-4a8a9809)
- Rank 2/8, 18.64 pts/table; places 1st 146, 2nd 138, 3rd 117 ... 8th 137. VPIP 35%, PFR 24%, WTSD 13.5%, showdown win 54.5%. 0 subs. Weighted total 173.87 (rank 4).
- Leaderboard: b05 21.00 (37/16), b03 18.64, b08 17.77, b06 17.67, b01 17.16, b02 14.49, b07 12.91, b04 10.37.

## Patch window before T5
- IMPORTANT: a local run with any 'hang' (wall time > 50 ms under machine load) is not reproducible, because the substituted fold changes the whole table. Only compare runs with 0 hangs. E.g. v8 limper seed 9 was 25.95 with 1 hang vs 23.51 clean.
- Clean v8 baselines: limper seed 9 23.5, seed 13 25.8; F seed 9 19.4, seed 13 21.0.
- v9 clean baselines: F seed 9 20.3, seed 13 21.2; limper seed 9 25.1, seed 13 25.3.
- v10 clean baselines: F seed 9 22.5, seed 13 19.9; limper seed 9 26.4, seed 13 26.6. Vs house bots incl. random (seed 31, 200 tables): 58.9 pts/table, 0 subs.
- Steeper adaptive vthr (slope 0.3, clamp 0.50-0.66) vs v10: +0.3, -0.7, -0.2, +0.6 (mean 0), so keep slope 0.2.
- Next ideas: the adaptive thresholds could also cover multiway pots and barrel decisions; a squeeze vs loose openers; check-raise traps with strong hands vs aggressive bettors.
- Turn call margin 0 or 0.04 (vs 0.02): no gain (F seed 13 -0.2 / -0.5; limper seed 9 about 0). Keep 0.02.

## T5 result (010-fb6e5600, v10)
- Rank 5/8, 16.20 pts/table; places 1st 128 ... 8th 154. Stats almost identical to T4 (VPIP 35%, PFR 24%). Weighted total 254.89 (rank 5).
- Leaderboard: b05 20.80, b08 20.09, b06 18.73, b01 16.91, b03 16.20, b02 12.85, b07 12.67, b04 11.74.
- Reverted to v8 for T6 (see Last change).
- Mixed-field check (v8 hero + 2x v10, 2x v7, 2x v6, nit; seed 47, 400 tables, 0 hangs): v6 avg 18.3, v10 avg 18.3, v8 17.6, v7 avg 15.6, all within noise (±3.3). No reason to switch.
- v12 vs house bots incl. random (seed 31, 200 tables): 55.5 pts/table, rank 1 (v10: 58.9 on the same seed, within ±6.7).
- SIZE_K 0.12 (vs 0.08): F seed 13 21.9 vs 22.2, limper seed 13 26.5 vs 27.2, so worse; keep 0.08.
- SIZE_K 0.05: F seed 13 21.95 vs 22.2, limper seed 13 26.7 vs 27.2, slightly worse. 0.08 looks near the best value.
- If there were more windows: make fold-to-bet a heads-up-only stat (multiway folds inflate it), then retest v9/v10's adaptive bluff and value thresholds on it.

## Files
- tools/gen.py builds bot/data.npz (turn_vals, pre_eq, flop_eq uint8, pre_multi) ; strength arrays (flop_str, turn_str, pre_str) were added by an inline script (mean equity vs random).

## Ideas / next
- Better postflop sizing, check-raises, multiway thresholds.
- ICM near the bubble of 3 (2nd=25, 3rd=5).
