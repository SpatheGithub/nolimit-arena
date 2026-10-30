# Team notes (b01)

## Approach
- Bot = copy of the house `icm_pushfold` bot (TagCore from `_common.py` + `_common.json`
  preflop tables), copied into `bot/` with relative imports. Deep: tight-aggressive
  opens/3-bets/c-bets by made hand + draws; short (<= short_bb effective BB):
  ICM-aware push/fold (Malmuth-Harville under the event points table).
- Changes kept: `short_bb = 20` (house uses 15; push charts in the json cap at 20 BB) and
  `FUTURE_HANDS = 6` (fold cost in ICM push/fold; house uses 3). Final submission 004-c2452fa4.
- FUTURE_HANDS 3 vs 6: seed 7 49.5 vs 49.8; seed 11 (400 tables) 45.8 vs 47.7 -> kept 6.
- FUTURE_HANDS 10: seed 7 46.9 (worse) -> stayed at 6.
- short_bb 18 (with FUTURE_HANDS 6): seed 7 46.6 (worse than 20's 49.8) -> stayed at 20.
- Code in bot/ matches submission 004-c2452fa4 (short_bb 20, FUTURE_HANDS 6).
- Caution: localsim seed 11 seems to seat "you" badly (all variants ~45-47 vs house copy ~51);
  compare variants only on the same seed.

## Key parameters / experiments (localsim vs zoo, points/table, noise ~±3-4)
- short_bb 15 vs 20 (seed 7, 300 tables): 46.0 vs 49.5; seed 11, 500 tables (with bluff): 45.4 vs 46.0 -> kept 20.
- short_bb 25: 43.9 (worse; charts stop at 20 BB).
- Postflop 0.5-pot bluff vs tight folders (fold_rate>=.75, vpip<=.22): neutral / slightly negative -> removed.
- OPEN widths x1.25: neutral (48.5) -> reverted.
- Deep-shove villain prior 0.08->0.15, reads weight 10->6: 47.1 (noise) -> reverted.

## Known weaknesses
- Essentially same strategy as the house icm_pushfold; no edge over it, only over weaker bots.
- Deep-stack postflop is heuristic (no equity tables); calls maniac shoves tightly early in a table.

## Next steps
- Precompute equity tables vs ranges for postflop; exploit maniac (call shoves wider once reads confirm).
- Larger-sample A/B (1000+ tables, several seeds) before trusting any tweak.
