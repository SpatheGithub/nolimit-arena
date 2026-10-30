# Team b08 notes

## Approach
- `bot/agent.py` + `bot/_common.py` (copied house-bot helpers: Ranker, Spot, features()).
- Preflop: class percentile table (`_common.json`) + `bot/eqtop.json` = equity of each of 169
  classes vs the top k% of hands (k=1..100), built from a Monte Carlo 169x169 class-vs-class
  matrix (tools/pre_eq.py, 1500 deals/pair; tools/mk_eqtop.py).
  - Unopened: open-raise by position (players behind) thresholds on percentile; <=13bb: push/fold
    with Nash-ish thresholds (scaled by (10/eff_bb)^0.6, x PUSH_ICM when >=4 alive).
    Short-handed widening (HU open 80%, 3-handed x1.4, 4-handed x1.25). Steal wider when players
    behind have low observed VPIP.
  - Facing raise: estimate raiser range r (by raise size, shove stack depth, position, n alive,
    and observed per-seat PFR / big-raise frequency at this table), equity vs top-r, compare with
    pot odds (+ICM premium when committing). Multiway: eq^(1+0.6*callers).
- ICM: break-even equity for a coin-flip all-in with 8 equal stacks is ~0.62 (computed with
  kit/icm.py), so all-in / stack-off calls add an ICM premium (0.10 base, 0.07 3-handed, 0 HU,
  scaled by fraction of my stack at risk). Tables never reached the 200-hand cap in sims.
- Postflop: features() strength (0..1) + draw outs; multiway discount; value bet / c-bet;
  facing bets: call if eq - discount >= pot odds. Discount = street base (0.03/0.10/0.15) +
  size term + raised-over-my-bet term + extra for weak hands on turn/river; scaled down vs
  aggressive opponents (observed postflop aggression).

## T1 result (v8): rank 4/8, 32.01 pts/table (field 29.7-34.9, all within noise)
- Places flat (1st 11.7% ... 8th 11.4%). 0 substitutions. b02 won with VPIP 19 / PFR 14.
- results/T1/sample_hands.json = 40 level-1 hands from 4 tables: opponents open 2.3-3bb,
  c-bet ~0.45-0.6 pot, and preflop callers FOLD to flop bets very often (~8 of 10 seen).

## Patch before T2 -> v9 = 009-9d9bb941
- CBET 0.6 -> 0.8 (HU flop c-bet any hand, 0.45 pot) and STAB=0.6: as preflop caller in
  position HU, bet 0.5 pot on the flop when checked to.
  Mixed field +3.2 then -0.9 vs v8 (two seeds), self-play vs v8 copies 32.7 (avg 31.9).
- Tested, not submitted: turn stab after checked-through flop + more multiway c-bets
  (tools/v/cT): mixed +2.2, self-play 31.4 -> inconclusive.
- Tested, not submitted: OPEN_LATE=1.0 (tighter, like b02): self-play vs v9 copies 31.6 -> no gain.
- v10 = 010-b1654798 (ACTIVE for T2): CBET=1.0, STAB=0.8 (always c-bet HU flop 0.45 pot; stab
  0.5 pot IP as caller 80%). Self-play vs v9 copies 34.8 (avg 31.9, +2.9), mixed field 51.0 vs
  v9 46.5 / v8 47.0 (800 tables each). Exploits high fold-to-flop-bet rate seen in T1 sample.
- Tested on top of v10, not submitted: BARREL 0.55 (tools/v/cBar): self-play 31.9, mixed =v10.
  (A second mixed run had v9 47.4 vs v10 45.2 -> mixed-field noise is ~+-2.8 at 600 tables.)
- v10 health check vs house zoo (300 tables, seed 137): 1st, 56.3 +- 4.4 pts/table.
- Next ideas: check T2 places/sample hands for later-level leaks (sample was level 1 only);
  light 3-bets vs late opens if opponents open wide; river bluffs if folds stay frequent.

## Status at end of build phase
- Active submission: 008-b88d2d85 (= bot/ now). Versions: 001 base, 002 +ICM premium,
  003 +street-based postflop discount, 004 +short-handed widening, 005 +VPIP steals/multiway,
  006 +weak turn/river call tightening/turn barrel, 007 +3-bet top 5%, 008 +late opens x1.15,
  F_CAP=8 (range widening vs frequent shovers).
- Final mixed-field check (1000 tables, seed 83): v8 47.6, v7 43.6, v5 42.1, v3 40.2 (+-2.2).
- Rejected at the end: OPEN_LATE=1.3 (+1.6 mixed, 0 in self-play), PUSH_ICM=1.05 (-2.9),
  halving HU postflop discounts (no gain), BARREL=0 / TB_PCT=0.035 in HU (no gain).
- HU sims are seed-sensitive: same seed gives correlated results; always confirm on a 2nd seed.
- Final health check, v8 vs house zoo (localsim, 300 tables, seed 101): 59.0 +- 4.4 pts/table
  (1st place; v1 scored ~48-50 there), 0 substitutions, p99 100 us.
- Tested last: river value-bet threshold s>=0.56 HU (tools/v/cRV): 47.97 vs v8 47.84 (700
  tables) -> no difference, not submitted.
- v8 vs 7 copies of v1 (localsim, 500 tables): 39.2 +- 3.0 pts/table (field average 31.9),
  1st of 8 -> the v2..v8 changes (mainly ICM premium) beat chip-EV-style bots.
- Ideas for patch rounds: check-raise monsters OOP; tune vs real tournament results (bust
  order / places) rather than house bots, which can't separate v5..v8 reliably.

## Evidence (local sims, tools/sim.py mixed field, tools/an4.py decision logs)
- Turn/river calls with s<0.45 won only 4-20% of the time -> tightened.
- Thin value bets (s>=0.5) and flop c-bets win; HU widening beat v3 54/46 in HU-only sims.
- v3..v6 are statistically tied in the house-bot field (+-2 pts at 1000 tables).

## Key parameters (top of agent.py)
- PUSH_ICM, ICM3, ICM4, STREET_ADJ, HU_OPEN, RAISED_ADJ, WEAK_TURN, WEAK_RIVER, BARREL.

## Tools
- tools/sim.py TABLES SEED ['{json settings overrides}'] name=path ... (house bot names ok)
  e.g. HU test: '{"seats":2,"starting_stack":8000,"points":[100,60],"blinds":[[160,320,0],...]}'
- tools/mkdbg.py builds an instrumented copy (tools/v/dbg) that logs decisions to tools/dbg.log.

## Known weaknesses
- Postflop is heuristic only; no check-raises, no river bluffs.
- Range estimates are guesses; push/call thresholds not solved.

## Next steps
- Use real tournament results to see if we bust early (too loose) or rarely win (too tight).
