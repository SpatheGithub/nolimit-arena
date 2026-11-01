# Team b03 notes

## Strategy

**Summary:** Table-driven equity bot for royal hold'em (20-card deck). Exact precomputed tables (preflop 190x190 pairwise equity, flop pairwise equity per 3-card board, exact turn hand values) let every decision compute equity against a Bayesian range for each opponent in ~50-100 µs. Decisions are chip-EV with small risk margins (payouts 100/25/5 are near winner-take-all, so chips ≈ points).

**Before the flop:** Hands ranked by equity vs a random hand (AA > KK > AK > AQ > AJ > QQ > KQ > AT > KJ ... TT last). Deep (>16 BB effective): open-raise 2.2-2.5 BB + 1 BB per limper with top 28% (UTG) to 55% (late/SB), widened by 0.25 when every player behind is tight (VPIP < 28% after 12+ hands); SB completes top 60%; BB raises limped pots with top 20%. Facing a raise: 3-bet (3x) with ≥60% equity vs the raiser's modelled range, call when equity*realisation (0.82-0.88) beats pot odds and the call is ≤25% of stack. ≤16 BB: shove-or-fold by EV, using each player behind's observed calling width; ≤20-25 BB facing a raise: jam/call/fold by chip EV.

**After the flop:** Equity vs each opponent's range (product for multiway). Bet 0.6-0.75 pot for value with ≥58% heads-up (≥50% multiway), shove when stack ≤ 1.1 pot. Heads-up bluffs ~15% (more vs players who fold to bets, more on the flop with equity ≥38%). Facing a bet: raise/shove with ≥68% HU (≥78% multiway), call when equity > pot odds (+2% on the turn), else fold.

**Short stacks and the points table:** Push/fold below 16 BB with EV computed against assumed calling ranges (18-33% of hands by depth, blended with observed VPIP). Calls of shoves use the shover's range width from stack depth (≤8 BB: 55%, ≤15: 35%, ≤25: 20%, else 10%) and their observed all-in frequency. No explicit ICM (payout steep enough that chip EV is close); small margins avoid coin-flip calls.

**Opponents:** Per-seat counts (hands, VPIP, PFR, all-ins, postflop aggression, fold-to-bet). Ranges: preflop raises keep the top PFR-width (narrower for 3-bets), calls keep VPIP-width; postflop bets/raises reweight toward hands whose equity vs random exceeds an aggression-adjusted threshold with a bluff floor; checks discount the nuts slightly.

**Last change:** v2 (002-050df968): calling widths from opponent stats in push/fold, steal-widening vs tight players, all-in frequency tracking. 600 tables vs 3x v1 + 4 house bots: v2 28.2 vs v1 avg 25.2 pts/table.

## Test log
- v1 (001-f83c2b8b) vs zoo, 60 tables: 54.6 pts/table (zoo avg ~17).
- v2 vs 3x v1 + pot_odds,nit,maniac,minraiser, 600 tables: 28.2 vs 25.2.

- Knob tests (seed 21, vs 3x v2 + pot_odds,nit,maniac,minraiser; baseline v2 settings = 25.9 on this seed, 400 tables — the "you" seat runs ~2-3 below the v2 copies on this seed):
  - PUSH_BB 22: 24.6 (600 t) — worse; PUSH_BB 12: 24.2 (300 t) — worse. Keep 16.
  - BLUFF0 0.08: 24.8 (400 t) — worse. BLUFF0 0.22: 27.5 (400 t) — maybe better (+1.7, under 1 sigma); a 1000-table check on a new seed timed out on the busy machine. Not submitted. Try it first in the patch window.
- Avoid `montecarlo` in localsim tests: it uses wall-clock time per decision and made runs time out.
- bot/ now has module knobs PUSH_BB=16 and BLUFF0=0.15, and with these values it plays the same as 002-050df968.

## Files
- tools/gen.py builds bot/data.npz (turn_vals, pre_eq, flop_eq uint8, pre_multi) ; strength arrays (flop_str, turn_str, pre_str) were added by an inline script (mean equity vs random).

## Ideas / next
- Better postflop sizing, check-raises, multiway thresholds.
- ICM near the bubble of 3 (2nd=25, 3rd=5).
