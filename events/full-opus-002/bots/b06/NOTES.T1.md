# Team b06 notes

## Approach
- `bot/_common.py` + `_common.json`: copied from kit house-bot helpers (Spot parser, Ranker, preflop class table, postflop `features()`).
- `bot/eqmat.json`: 169x169 class-vs-class preflop equity matrix (tools/matrix.py, 240 boards/pair). At import we build
  `_ER[class][k]` = equity vs top (k+1)*2% range (combo-weighted, ordered by `pct`).
- Preflop:
  - eff stack <= 14bb (or <=16bb with limpers): push/fold by explicit EV: P(all fold)*pot + sum over callers
    (call width from Nash-ish table by eff stack, x1.25 for BB, scaled by their observed VPIP) of eq*win - (1-eq)*risk*BF.
  - deeper: open-raise widths by #players behind (_OPENW), 2.2-2.5bb + 1bb/limper; BB raises top 10% vs limps.
  - facing raise: if committing (>=40% stack or raiser all-in): call if eq vs estimated range >= BF-adjusted pot odds; shove over
    non-allin raises when eq clears. Range of raiser = max(shove width by stack, 0.8*observed PFR).
  - not committing: resteal shove EV when eff <= 30bb; 3-bet top 3.5%; call by equity vs range + margin.
- ICM: exact Malmuth-Harville (forward subset DP) computed in observe() after every hand (observe only has 50ms wall watchdog)
  giving bubble factor vs each opponent for a full-stack flip. BF damped by risk fraction and when my stack < 15bb.
- Postflop: `features()` strength/outs; value bet >=0.62, c-bet 40% pot HU flop, semi-bluff draws; facing bets discount strength
  by bet size and raises; BF-adjusted price when committing.
- Opponent stats: per-seat hands, VPIP, PFR (Bayesian prior), used for range widths.

## Key parameters
- bf_scale (ICM pressure multiplier), _OPENW, _CALLW, _SHOVEW, push threshold 14bb.

## History / findings
- 001: first version. 002: ICM zero-stack fix, BF damping when short, bf_scale 0.75, VPIP-based steal widths, postflop bettor-aggression read.
- 003: resteal fix (opener's call width = 0.65*open width, hand caps by depth, max 25bb), first-in shove caps (pct<=0.30 at >10bb
  unless HU/SB-vs-BB), postflop pot capped at our stack (big bug: we called maniac shoves w/ middle pair), 4-flush/4-straight
  board penalty. A/B (450 tables): 003 44.4 vs 002 41.3 vs 001 40.6.
- Per-opponent shove-call tracking (calls vs model-expected width ratio) scales call widths in push EV.
- tools/: sim.py (A/B runner, any bot dirs), logs.py + showloss.py (hand logs, print big losses), probe.py/probe2.py (range dumps).
- Noise: ~±3.3 points at 450 tables; only big effects are detectable.

## Known weaknesses
- Postflop is heuristic (no equity vs range); multiway all-in equity rough (0.82^callers).
- Blind-bleed not modelled except by BF damping.

## Next steps
- A/B bf_scale; tune postflop call thresholds vs big bets; steal more vs tight blinds.
