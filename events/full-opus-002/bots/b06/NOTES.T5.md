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

- T2 result (007): rank 2/8, 32.88 pts/table, weighted total 99.08 (rank 2). 0 observe errors/hangs (fix worked).
  Places 136/135/122/105/108/135/141/118: more 1sts than T1 (121) but more 6th-8th (394 vs 333) -> higher variance.
  Local mixed field: 007 45.2/44.2 vs 004 43.1/42.3, similar bust rates. Kept 007 for T3 (no tested improvement in time).
  sample_hands.json only has the first 10 hands of one table: useless for bust analysis.
  All-bot fields run ~1.2 s/table: use <=150 tables per 200 s run (tools/sim.py prints place distributions).
  All-own-versions field, 90 tables (very noisy, +-7): 002 37.7 (22% 1st / 24% 8th), 003 33.7, 006 33.2, 007 32.9/30.1,
  005 32.7, 004 31.7/22.9. No sign 007 busts more than 004; hint that looser/aggressive (002) wins more 1sts vs tight bots.
  Health check before T3 (localsim 150 tables vs 004, 002, house): 0 subs; you 46.0, 004 50.2, 002 44.3 (all within +-5.5).
  007 kept active for T3.
  2nd all-versions run (100 tables, seed 71): 002 39.2 (again top: 24% 1st, 35% 7th-8th), 007 34.6/29.5, 006 32.8, 005 31.0,
  003 30.7, 004 29.5/28.0. Two runs combined: 007 avg ~31.8 vs 004 ~28.0; 007 busts (6-8th) ~0.31-0.36 vs 004 ~0.35-0.39.
  => 005-007 widening is NOT the bust cause. 002 (looser: VPIP 28/PFR 24, wide resteals) tops both competent-field runs:
  next window, try more aggression vs tight fields (wider opens/resteals when field VPIP low) and A/B in all-versions field.

- T3 result (007): rank 3/8, 33.60 pts/table; weighted total 199.88 (rank 2; b03 ~212.6 leads, b05 ~199.0 right behind).
  Places 135/138/123/118/141/119/129/97. b03 leads every event (34.8/35.4/35.7) with VPIP 25 / PFR 18.
- T4 window: variant tools/agg = 007 + bf_scale 0.6 (from 0.75), late-position (<=3 behind) open widths x1.15,
  resteal opener call width 0.55*w (from 0.65) and caps 0.35/0.25/0.16 (from 0.30/0.20/0.12). A/B in all-versions field
  (tools/agg1.log, agg2.log).

  Result: agg variant NOT better (avg ~29.2 vs 007 ~32.4 over 2 runs). 002 topped the all-versions field 4/4 runs (~+6.7 vs 007).
- 008 (ACTIVE for T4): adaptive resteal. If opener VPIP<=0.30, opener's shove-call ratio<=1.25 and everyone behind VPIP<=0.30
  (tight raise-or-fold field): 002-style resteal shove (opener calls w*0.45, behind x0.7, shove if EV>0 and (pct<=0.10 or
  EV>0.1*pot), eff<=30bb). Else 007 logic (capped). Evidence: ungated hybrid h2 vs 007 in all-versions field +3.3/+6.0
  (2 runs), but -5.2 in house-bot field (loose callers punish it); gated h3: house field -1.4 (noise), all-versions +0.7 (1 run).
  Real field looks like tight raise-or-fold bots (VPIP 21-25, PFR 15-21) -> expect small gain.
  Confirmation run (seed 111, all-versions): 008 38.6/34.1 (top two) vs 007 33.3/28.1 -> +5.6. Adaptive avg over 2 runs +3.2.
  House-field check #2 (seed 121, 400 tables): 008 49.5 vs 007 49.4/46.7 -> +1.4. House avg over 2 runs ~0 => gate works.
- Next: if T4 shows more busts, tighten the gate (e.g. VPIP<=0.27) or require EV>0.15*pot; consider same gating idea for
  first-in shove caps (002 had none).

- T4 result (008): RANK 1/8, 35.63 pts/table (b03 35.28). Places 198/118/81/88/89/117/161/148: many more 1sts (19.8%),
  more 7th/8th (30.9%) -> high-variance style pays with this payout table. VPIP 28 / PFR 23. Weighted 342.40 (rank 2;
  b03 ~353.7). Need ~+1 pt/table over b03 in T5+T6 to catch up.
- T5 window: h4 = 008 + first-in shove caps removed when everyone behind is tight (VPIP<=0.30, shove-call ratio<=1.25,
  no limpers). A/B logs tools/h4a.log, h4b.log (all-versions), h4c.log (house field).
  h4 - 008 per run (avg of 2 copies each): all-versions -0.6, +5.6, -3.3, +4.5 (avg +1.55, noisy); house +1.0.
- 009 = h4 submitted for T5 (accepted 23:31). Confirmation runs: +1.2, -4.3 -> 6-run avg +0.5 (no real gain).
  Reverted: resubmitted 008's exact code (proven rank 1 in T4) for T5 as 010-c2caa755 (same hash as 008). ACTIVE for T5.
- CAUTION: files copied from .submissions/ are read-only -> `chmod -R u+w` before editing (bot/ was restored from 008).
- h5 (T6 candidate) = 010 + 002-style resteal needs EV>0.2*pot (not 0.1) when eff>20bb. A/B: tools/h5c.log (seed 163).
  tools/h5a.log/h5b.log are accidentally 010-vs-unpatched-copy (= 010 vs 010) -> a noise baseline.
  Results: identical-code baseline differed by +2.4 (noise!); patched h5 vs 010: -0.7. No gain -> keep 010 for T5.
- Next idea (untested): reduce early busts of 008 without losing 1sts, e.g. require EV>0.15*pot for 002-style resteals when
  eff>20bb; or gate on opener VPIP<=0.27.

## Known weaknesses
- Postflop is heuristic (no equity vs range); multiway all-in equity rough (0.82^callers).
- Blind-bleed not modelled except by BF damping.

## Next steps
- (Done: 005-007 widening does not raise busts vs competent bots; keep it.)
- Try more aggression when the table is tight (002-style wider opens/resteals gated on low field VPIP), A/B in the
  all-versions field with tools/sim.py (<=100 tables per run, ~2 min).
- Short-handed (3-4 left) open/defend widths; postflop HU aggression; 3-bet light vs frequent openers.
- Push/fold call widths when HU (BB call vs 10bb SB shove ~30%, Nash ~40%).
