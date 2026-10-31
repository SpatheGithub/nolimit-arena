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

- 004: postflop call-down discounts (turn -0.03, river -0.06, -0.04 per earlier barrel by same bettor), no bluffs vs loose (VPIP>=0.38).
- T1 result: rank 3/8, 33.32 pts/table; places 121/142/143/129/132/123/109/101 (1st only average -> endgame weak);
  156 observe errors + 2 hangs (8-player ICM in observe hit 50ms wall watchdog under load).
- 005: observe ICM refresh only 3 opponents/hand when >=7 alive (1.5ms vs 3.9ms; full at __init__); covered callers call x0.85;
  bigger value bets vs loose; position-aware ranges: raiser range x1.7/1.3/1.1/0.9 by players behind (SB/HU shoves wide),
  callers x1.4 (1 behind) / x1.15 (2 behind) vs my late shoves. A/B parity with 004.
- 007: preflop all-in call pot now includes my own posted chips (was excluding my blind -> calls too tight; HU BB vs 10bb
  shove 30% -> 35%). A/B parity with 006. ACTIVE for T2.
- 006: heads-up fixes: HU SB raise 60% + complete to 90% (was raise 42% / fold 40%); HU BB defend pct<=0.85 at
  po+0.02 (was folding 59% vs min-raise); BB vs late-position (<=2 behind) open defend pct<=0.6 at po+0.05.
  A/B 400 tables: 44.25 vs 005 43.5 (parity+). tools/probe_hu.py checks HU ranges.

## Known weaknesses
- Postflop is heuristic (no equity vs range); multiway all-in equity rough (0.82^callers).
- Blind-bleed not modelled except by BF damping.

## Next steps
- Short-handed (3-4 left) open/defend widths; postflop HU aggression; 3-bet light vs frequent openers.
- Push/fold call widths when HU (BB call vs 10bb SB shove ~30%, Nash ~40%).
