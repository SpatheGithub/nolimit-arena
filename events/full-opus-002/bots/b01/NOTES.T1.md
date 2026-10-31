# Team b01 notes

## Approach
- `bot/data.pkl` (built by `tools/precompute.py`): fasteval 5-7 card rank table + suited table (copied from kit engine),
  169x169 preflop class-vs-class equity matrix (1200 MC boards per pair), house-bot preflop pct table.
- Preflop: EQR[class][top-k%] = equity vs top k% range (prefix sums over classes sorted by pct).
  - First-in, eff <= 14bb: push/fold by EV with modelled calling widths (Nash-like HU call table x
    position factor NB_CALL, opponent vpip adjust). ICM (exact, kit/icm algorithm) when 3-4 alive.
  - Deeper: open-raise ranges by players behind (55%..12%), 2.5bb (+1bb/limper), 3bb HU.
  - Facing raise: commit decisions (to_call >= 40% stack or <= 16bb) via equity vs raiser width
    (pfr*position mult, or Nash push width for shoves), cold callers multiply equity; ICM when 3-4 alive,
    else risk premium. Deep: 3-bet top 3.5%, call top 11% / pairs at <= 8% stack.
- Postflop: Monte Carlo (~0.5 ms budget, perf_counter deadline) vs opponents sampled from preflop range width
  AND conditioned on their postflop actions (bet -> pair+, 2 bets -> top pair+, raise -> two pair+;
  bluff skip prob scaled by observed aggression). Value bet eq>=0.58 HU, c-bet 60% HU flop, call if
  eq*(1-disc) >= pot odds.
- Opponent stats per seat (vpip, pfr, postflop aggression) from observe().

## Version history (localsim; mixed = v1+6 house bots seed 2 300 tables; v5field = 6 v5 copies + nit seed 11 400 tables)
- 001 v1 baseline. 002 v3 conditioned MC. 003 v5: effective-pot fix (uncalled overshove excluded from pot odds),
  limpers counted as callers in shove EV, resteal shove EV with fold equity. 004 v7: fold-to-bet tracking
  (scales c-bet/probe bluffs and value threshold), shove-call-rate tracking (scales call widths), steal widening
  vs tight blinds. v8: MC opponent sampling from enumerated combo lists (rank-based requirement check on current
  board, intersected with preflop width) instead of rejection sampling, which silently fell back to random hands
  (AK on K72 vs two-pair+ was 0.87, now 0.20). Raise reqs: 1 raise = top pair+, river raise / 2 raises = two pair+.
  mixed: v3 58.7, v5 56.1, v7 56.4, v8 61.4. v5field: v6 34.9, v7 33.1, v8 36.7 (v5 copies avg ~33).
## Results (localsim, mixed field v1+6 house bots, seed 2, 300 tables)
- v1 (001): ~47; v3 (002): 58.7 (conditioned MC was the big win; early busts from paying off raises).

## Known weaknesses / next
- MC is noisy (~50-100 samples). Board-paired handling of requirements is crude.
- No 3-bet bluffing / resteal shove logic beyond equity; no limping.
