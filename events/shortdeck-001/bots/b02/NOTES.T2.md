# Team b02 notes

## Strategy

**Summary:** Equity-driven TAG bot for short-deck with ICM-priced all-ins. Preflop uses precomputed 81-class equity tables (HU matrix + multiway) to rank hands and price calls/shoves vs estimated opponent ranges; every all-in decision (shove, resteal, calling a shove, big postflop calls) is valued in tournament points with an ICM table, which stops it flipping its stack away while reckless bots bust each other. Postflop runs a time-budgeted Monte Carlo (<0.4 ms) against range- and action-weighted opponent hands.

**Before the flop:** Opens top X% by players behind (≈16% UTG → 43% button, SB vs BB 45%, 3-handed button 50%, heads-up 75%), 2.3-2.6bb; widens vs tight blinds. ≤14bb effective: open-shove / iso-shove over limpers when ICM value of shoving beats folding, using modelled calling ranges (call fraction from risk in bb, blind position, seat looseness). 8-handed 10bb: UTG ~6 classes, button ~17, SB ~43 of 81; heads-up unchanged from chip-EV (~57-65). Facing raises: raiser range = observed PFR widened by folds before the open; equity vs that range decides 3-bet (eq≥0.58)/shove, call (eq×realization ≥ pot odds+3%), or fold. BB defends ~50% vs a button open. ≤25bb: resteal shove over a single open with top-24% hands when ICM gain > 10% of the pot's value.

**After the flop:** MC equity vs opponents' ranges (preflop raiser: PFR×1.4 range; callers: VPIP range), with each sampled opponent hand weighted by how well its current made-hand category fits that opponent's postflop bets/raises/calls this hand (bettors rarely hold air, double-barrellers mostly two pair+; weights loosen for aggressive seats). Value bets 66-80% pot when equity share ≥1.3 (shoves when stack ≤1.2 pots), c-bets heads-up as preflop raiser scaled by the opponent's postflop fold rate, bluffs later streets only vs high folders. Facing bets: raises big equity (river raises need ≥0.85), calls when discounted equity beats pot odds — or the ICM requirement when the call is half our stack or more.

**Short stacks and the points table:** Points 100/45/20/8 with reckless opponents make survival valuable: ICM table (bot/icm.json: n players × our chip share, others equal; exact kit/icm.py values) converts every all-in into points. E.g. 8 equal stacks: a stack-for-stack flip needs ≈55% equity. Heads-up it reduces to chip EV automatically.

**Opponents:** per-seat VPIP, PFR, postflop aggression, postflop fold-to-bet (priors until ~5 samples); used for preflop ranges, steal widths, shove-calling ranges, MC hand weights, bluff and c-bet frequency.

**Last change:** v5 (005-75e667c0, for T2): heads-up shove calling fixed to equilibrium. T1 (rank 1, 24.95 pts/table) showed 2nd (172) more often than 1st (137), i.e. only 44% of heads-up endings won. A push/fold equilibrium solved from our equity matrix (tools/nash.py) matched our SB shoves but showed the BB folding too much: vs a 15bb heads-up open-shove it called only 6 hand classes (equilibrium ~31), because shove ranges were only widened below 15bb. Now heads-up open-shoves are read as 0.40+2.3/bb of hands (<30bb) and the extra +2% call margin is dropped heads-up. HU BB calls now 5bb 70 / 7bb 54 / 10bb 41 / 15bb 31 classes vs equilibrium 66/52/41/31. Range-only change (verified with tools/hu.py); no table test in time. Previous v4: ICM-based all-ins, all-maniac field 29.4 → 45.5, mixed field 35.2 vs v3 26.6.

## History
- v1 (001-dac57c7d): equity tables + MC postflop + chip-EV push/fold. Zoo: 51.5 pts/table.
- v2 (002-97a93f3a): action-weighted postflop MC, resteal/iso shoves, 3000-sample preflop tables. Self-play vs 7x v1: 23.6 vs 21.4.
- v3 (003-32380f0b): fixed preflop leaks found by range printing (resteal shoved 100%; BB folded ~90% vs button opens; shove/call ranges by blind position). Mixed field: 32.0 vs v2 29.6.
- v4 (004-eb232a23): ICM all-ins. T1: rank 1, 24.95 pts/table; places 137/172/130/114/122/107/116/102; 1 environmental hang (101 ms wall), 0 timeouts.
- v5 (005-75e667c0): heads-up shove-calling at equilibrium (see Last change).

## Key parameters
- Push/fold threshold: 14bb effective. Resteal ≤25bb, hands ≤ top 24%.
- Call fraction model vs our shove: BB 0.12+2.2/rbb, SB 0.06+1.6/rbb, others 0.04+1.2/rbb, +0.08 heads-up, × (0.6+1.3·VPIP), clamp [0.04, 0.8].
- MC budget 0.38 ms wall, time checked every 4 samples; p99 ≈ 0.45-0.5 ms on the busy machine.

## Tools
- tools/precompute.py (preflop tables), tools/icmtab.py (ICM table), tools/ranges.py (prints preflop ranges in constructed spots), tools/post.py (postflop spot probes).

## Known weaknesses / next steps
- ICM table assumes the other stacks are equal; it ignores rising blinds, so it may be slightly too tight in the late game. The shove margin was set to 0 to compensate.
- No all-in-specific opponent stats (shove frequency); shove ranges are estimated from PFR and position.
- Postflop has no check-raise bluffs and no slow-play; multiway c-bets are off.
- Self-play tests vs earlier versions are noisy (±2.5 pts at 700 tables); single-style fields (maniac/nit) are cheaper and more sensitive diagnostics.
- End-of-build sanity run of 004 vs maniac (seed 9, 300 tables): 42.9 ± 3.5, 0 substitutions, p99 450 µs.
- Weakest single-style fields: minraiser (44) and maniac (45). Vs minraiser, check how we handle repeated min-raises (cheap prices on every street).
- The machine gets very loaded late in windows (load avg 10-13): localsim runs of v4-vs-v3 took 136 s for 200 tables. Run long tests in the background (nohup ... > tools/x.log &) so the 2-4 min tool timeout doesn't eat the result.
