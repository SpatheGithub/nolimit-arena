# Team notes (b02)

## Approach
- `bot/agent.py`, pure Python, ~25-100 µs per decision.
- Preflop tables: `pfbase.json` (house-bot pct / equity vs k random hands) and `pfeq.json`
  (169x169 class-vs-class all-in equity, Monte Carlo with 2000 boards per pair, built by
  `tools/pre_eq.py` with the kit evaluator offline). At import: equity of each class vs the
  "top x%" ranges on a grid (EQTOP).
- Preflop:
  - Push/fold when eff stack <= shove_bb (14bb, or 18bb with 3 or fewer players). Shove EV = fold equity
    plus called equity vs an assumed calling range per opponent (cp = cp_k/x_bb + 0.05, scaled by
    observed VPIP).
  - Deep: open top-x% by number of players behind (11%..45%), 2.5bb. Facing a raise: 3-bet top 3.5%,
    call top ~10% when cheap, set-mine pairs, BB defends top 30% vs small raises. Big raises or
    shoves: all-in or fold by EV vs the estimated raiser range (r_k/x_bb + 0.05, widened by the
    observed shove rate).
- Postflop: rule-based made-hand strength S (category, top/over/middle pair, kicker, board
  texture) plus draw equity D (flush/straight outs). E = S + (1-S)D, shrunk for multiway pots.
  Bet 0.7 pot for value when E >= 0.72, 0.5 pot for thin value, semi-bluff draws, c-bet the flop
  60% heads-up. Facing a bet: discount by bet size and the bettor's aggression; raise E >= 0.8;
  call when above pot odds; extra penalty to stack off with one pair.
- Opponent stats per seat (from hand_end histories): VPIP, PFR, preflop shove rate, postflop
  aggression.
- `params.json` (optional) overrides tunables in P; used for local A/B variants in tools/v_*.

## Key parameters
See P dict at the top of agent.py. Tuned by local A/B (1000-table runs, variants in tools/v_*,
made with `tools/mkvar.sh name '{json overrides}'`, opponents = own variants + house bots):
- shove_bb 11 (10-11 > 14 > 18), open_mult 1.2, call_margin 0.02 (0.10 worse),
- reshove_bb 16 with fold equity (fe=1): +3 pts vs no fold equity; 20/24 worse,
- value_e 0.66 (0.80 worse), thin_e/cbet neutral,
- ICM (exact Malmuth-Harville, copied from kit) for all-in calls when <= 4 players: neutral in self-play,
- hu=1: wider shove/call ranges and BB defense short-handed (HUF/DEF tables): slight plus,
- late_pen: turn/river call penalty (log analysis showed river calls lose ~6.5bb each).

## Tools
- `tools/logrun.py opp1,opp2 N` plays N logged tables; `tools/agg.py` sums my result per hand by my
  last action (st{street}-{action}[-sd]) and by blind level.

- late_pen 0.2 (0.3/0.4 not better), flop_pen 0 (0.05 neutral).
- steal_adapt (widen opens vs low-VPIP players behind), size_adapt (0.9 pot value bets when
  opponents fold < 30%), icm_shove (ICM open-shove EV when <= 4 players): all neutral in self-play,
  kept for exploitation/theory.
- Last sweep (open_mult 1.4, shove_bb 9, cp_k 1.0/1.8, r_k 2.6): all within noise of base.

- rs_fix: when facing a re-shove (n_raises >= 2) of <= 25bb, shover range = 0.8x (if we opened) or
  0.6x the open-shove estimate instead of a hard 6% cap; ICM call path also when heads-up in the
  pot. +1.5 pts vs v6 in two runs.
- pos_r: open-shove range widened by shover position (1 player left to act x1.6, 2 x1.3, 3 x1.1):
  +0.5 (noise level), kept.
- icm_shove_n 3: ICM open-shove only with <= 3 players (timing; the 4-player version cost ~140 µs).
- Re-tested at the end: stackoff 0.3/pen 0.25 and call_margin 0: both neutral.

## Timing
- p50 25 µs, p99 100-200 µs. Rare outliers of 0.5-1 ms are garbage-collector passes (verified:
  gc.disable() removes them); we don't touch global gc state since bots share a process.

## Submissions
- 001-3be122cc v1; 002-bd9d034b v3 (tuned); 003-877eb28a v4 (reshove fe, ICM, value_e);
  004-7ce38828 v5 (late_pen 0.2); 005-335047c5 v6 (adapt sizing/steals, ICM shoves);
  006-e909aca2 v7 (rs_fix): 35.6 vs v6/v5/v4 copies 31.7/32.1/30.0 in 600 tables;
  007-9dce3f36 v8 (pos_r).

## Patch-round checklist
- Look at results: if we bust early a lot -> tighten deep-stack calls (stackoff, late_pen).
- If opponents shove a lot, r_k up; if they call shoves wide, cp_k up (fewer light shoves).
- Timing: p99 ~200 µs (ICM paths), max ~600 µs on the busy machine. If timeouts are reported,
  set icm_n 3.

## Known weaknesses
- No exact ICM (chip EV + small margins).
- Postflop is rules, not equity vs ranges.

## Next steps
- Track fold-to-bet per opponent for bluff frequency.
