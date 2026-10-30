# Team b02 notes

## Approach
- 15-minute build, so started from the house reference strategy: `bot/_common.py` + `_common.json` copied from
  `kit/house_bots/tag` (TagCore: position-aware opens, 3-bets, c-bets, made-hand/draw postflop,
  push/fold at <= 15 bb with precomputed preflop equity tables).
- `bot/agent.py` = icm_pushfold layer: all-in/shove decisions valued by Malmuth-Harville ICM on the
  event's points table (100/60/40/25/15/10/5/0), with a fold cost of ~3 hands of blinds.
- Own tweaks in `_common.py`:
  - steal widening vs high-fold-rate players behind: applies when <= 5 players behind (orig 3),
    `width += max(0, fold_rate - 0.5) * 0.8` (orig `- 0.6) * 0.3`).
  - Next idea: push steal widening further (all positions, larger coefficient) and measure with more tables.
  - Tried and reverted: 3-bet value cap 0.07 -> 0.11 vs wide openers (48.4, worse);
    FUTURE_HANDS 3 -> 5 (50.5 on seed 11 but 49.3 vs 50.9 for v3 on seed 23, so no gain).
- Stronger steal widening (<= 5 behind, `max(0, fold_rate - 0.5) * 0.8`): 55.0 ± 3.6 on 400 tables seed 11
  (v3 was 50.4) -> submitted as 004-fc7b2166.
- Final = submission 004-fc7b2166 (workspace bot/ matches it). Confirmed on seed 23: 53.3 ± 3.5
  over 400 tables (v3 was 50.9 there), so the steal gain held on a second seed.

## Local results (600 tables vs zoo, seed 11; ±2.8 CI)
- tag copy ~46 (150 tables), icm variant 49.8, short_bb 20: 47.8, short_bb 12: 48.3 (15 kept)
- wider steals: 50.4 (submitted as 003)
- postflop stabs vs folders (fold_rate > 0.62, 75% half-pot): 50.1 -> reverted (no gain)

## Known weaknesses
- Postflop is heuristic (made-hand class + outs), very tight: ~7% showdowns.
- No opponent-specific exploitation beyond VPIP/PFR/fold-rate reads.
- All differences measured are inside noise; more tables needed.

## Next
- Bigger sample sizes per variant; tune open widths per position; exploit maniacs with wider calls;
  value-bet sizing vs stations; ICM-aware postflop stack-off thresholds near pay jumps.
