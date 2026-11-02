## Strategy

**Summary:** Equity-driven bot for 36-card shortdeck. Preflop uses a precomputed 81x81 hand-class equity matrix (bot/data.npz) to price opens, shoves and calls against estimated ranges; postflop computes equity with a vectorised numpy lookup evaluator against every (river) or a 100-combo sample of (flop/turn) opponent hole-card combos, weighted by each opponent's preflop range and narrowed by their postflop aggression. Chip-EV first (points are top-heavy 100/45/20/8, so winning matters most), with small ICM margins when few players remain.

**Before the flop:** Hands ranked by heads-up equity vs a random hand (shortdeck-specific: AA, KK, QQ, JJ, TT, AQs, AKs ... worst are 66, 76o). Deeper than 14 BB effective: open 2.1-2.5 BB with a top-x% range by players left to act (15% UTG up to 55-60% button/SB), widened vs blinds that fold to raises, tightened with limpers. Facing a raise: equity vs the raiser's estimated range (observed PFR; when it is all-in, a default shove range by stack depth, widened for late-position shovers and by the seat's observed shove rate) -> 3-bet/shove at equity >= 0.60, call when equity x realisation (0.95 IP / 0.82 OOP) beats the price, else fold. 14 BB or less: shove-or-fold by chip EV with fold equity from every player who could call (call rates from their observed calls of big raises, else a by-depth default).

**After the flop:** Equity vs each opponent's range (river: all combos; turn: every river card; flop: all 31 turn cards with a random river; flop/turn use a 100-combo sample), multiplied across opponents. Value bet 60-75% pot at equity >= 0.58 heads-up / 0.68 multiway; raise at >= 0.80; shove when SPR is small. C-bet bluffs heads-up as preflop aggressor (~55% scaled by opponent fold-to-bet), some later-street stabs and semi-bluffs. Calls when equity >= pot odds + 2% (river) / 4% (flop, turn).

**Short stacks and the points table:** push/fold chip-EV model at <= 14 BB; extra equity margin up to 3% for all-in calls when <= 4 players remain (1.5% at 5-6).

**Opponents:** per-seat VPIP, PFR, fold-to-raise preflop, fold-to-bet postflop, postflop aggression, calls of big raises, all-in shove count. Used for raiser/shover ranges, steal widening, fold equity of shoves, bluff frequency, and how much a bet narrows their range (less for very aggressive seats).

**Last change:** v7 (007-9b02e9a7): flop equity now uses every turn card (31) with a random river and a 100-combo opponent sample (flush-draw equity noise sd 0.083 -> 0.057, unbiased vs brute force); CPU guard falls back to cheap sampling after 0.2 ms. Builds on v6: EV-based re-shoves at <= 15 BB (fold equity instead of call price) and a multiway preflop penalty that counts only voluntary entrants. 300-table check vs v6 copies: 29.0 vs 28.3 avg (equal within noise).

## Notes

- data.npz built by precompute.py (6000 sampled boards for the HU class matrix, 5000 samples multiway).
- Evaluator: base-5 rank-count code -> value table (5^9, padded x2 so invalid combos never index out of range) + 9-bit suited-mask table; verified vs kit fasteval on 20k hands.
- Timing on the busy build machine: p50 ~50 us, flop decisions ~180-400 us, max seen ~1.3 ms under heavy load (1 timeout in 300 zoo tables for v7). Guard: if >0.2 ms already used, 8 runouts / 70 combos; narrowing skipped past 0.62 ms. If the referee reports timeouts, cut FLOP_R (31) / NSUB (100) at the top of agent.py.
- A/B results (500 tables, mixed field, same seed): v2 (resteal + widened call priors) ~34-37 vs v1 37-40; call-narrowing postflop (opp calls narrow range) + thin value vs stations: 31.8 (bad, reverted; flags CALL_NARROW, THIN, RESTEAL, WIDEN at top of agent.py).
- Zoo (house bots) score ~45-52 pts/table (v7: 47.0 +- 5.3 over 300 tables; 53.2 +- 6.4 over 200 tables, seed 404, 0 substitutions).

- Self-field A/B tests (500 tables each, baseline = v5 copies): open ranges x0.8 worse (25.0 vs 28.8), x1.2 equal; ICM margins doubled worse (27.2 vs 30.7), halved equal; push/fold zone 18 BB not better; bluff 0.3 not better.
- Thinner HU value bets (0.54 instead of 0.58) worse (25.7 vs 29.1); bluff 0.75 equal.
- Resteal (15-30 BB, HU, fold prior x0.6) re-tested after v7: 27.3 vs v7 copies 28.8 avg -> still off.
- Extra +3% call-off margin for big preflop all-ins when > 12 BB (risk > 50% stack): seed 101: 28.8 vs v7 copies 29.6/24.0; seed 202: 27.0 vs 31.0/28.8 -> no gain over 800 tables, not submitted.
- OOP preflop realisation 0.88 instead of 0.82 (defend more): 27.5 vs v7 copies 28.5/26.9 (400 tables) -> equal, not submitted.
- Final 150-table run, v7 vs v1/v4/v5/v6 + 3 house bots: all my versions 27-31.5 (+-6), i.e. indistinguishable; 0 substitutions.
- In fields of my own versions, `nit` scores ~22-24 (it survives into 3rd/4th), so the field busts itself a lot.

## Next ideas
- Re-tune resteal with lower fold prior; per-seat 3-bet fold stats.
- Better multiway equity than product of HU equities.
- Use patch windows: check substitution counts and results first.
