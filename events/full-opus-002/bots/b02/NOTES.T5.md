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

## T1 result (v8 007-9dce3f36): 29.27, rank 8/8 (field 29.3-34.8, mostly within noise)
- Places 1st 139, 2nd 93, 3rd 82, 4th 112, 5th 102, 6th 138, 7th 159, 8th 175: far too many early
  busts (8th +4.8 SE over 125). High variance: lots of 1sts, lots of 7th/8th.
- Diagnosis: all-in decisions were chip-EV with tiny margins. Exact ICM at 8 equal stacks says calling
  for the whole stack needs ~62% equity (6 players: ~61%); we used ~52-54%. Also big non-all-in raises
  (e.g. to 35bb) were read as the opener's wide range, and re-shove fold equity assumed 55% folds
  even from committed raisers.
- Patch 1 (008-dafb1270, big_r): big raises (>= 6bb) -> range min(r, 0.6/rb + 0.03); re-shove call
  probability pc = 0.45 + 1.5 * raise/raiser_stack; early_margin +0.05 when >= 6 players; postflop
  stack-off penalty +0.07 when >= 6 alive. Local: +1-2 pts, fewer 8ths.
- Patch 2 (util): concave chip utility u(x) = x^0.75 for all-in EV (calls, re-shoves, open shoves)
  when > 4 players (exact ICM below that). Local: score neutral/slightly up, 8th places down ~20%.

- alpha 0.65 vs 0.75: score noise, both cut 8ths vs 008; kept 0.75.
- Final head-to-head (700 tables, v10 vs 008/007/006 copies): v10 33.5, 008 32.6, 007 31.2, 006 30.6.
  v10 places [76, 95, 109, 141, 80, 79, 53, 67]: far fewer 7th/8th, but fewer 1sts too (tighter).
- alpha 0.82 vs 0.75 (2 x 600 tables): 0.75 better in both (32.9/33.4 vs 32.3/30.3); 008 copies
  29.6/30.4. Kept 009 (alpha 0.75) for T2.
- early_pen 0.12 vs 0.07 (2 x 600): 32.3/32.4 vs 31.9/32.1, noise; candidate only if T2 still
  shows many early busts.
- Note: with util on, early_margin is unused (util branch returns first for > 4 players);
  early_pen (postflop) still applies.
- Active for T2: 009-c54c104e (big_r + util). Zoo sanity: 60.3 pts/table, 0 errors.

## Next patch window: what to check
- In T2 places: did 7th/8th drop toward 125 each? If still high, lower alpha (0.65) and/or raise
  early_pen; if 1st place drops a lot, we got too tight (alpha 0.8).
- `tools/places.py opp1,opp2 N seed` prints the place distribution per bot (more useful than
  the mean alone).

## T2 result (009-c54c104e): 31.28, rank 6/8 (weighted total 91.83, rank 7)
- Places 129/106/107/163/121/126/118/130: early busts fixed (8th 130 ~ expected 125), but 4th = 163
  (expected 125): we reach the final four and bust 4th.
- Cause: at 4 players open shoves were chip EV with a looser threshold (icm_shove_n was 3), and
  re-shove/call spots not eligible for the exact-ICM path fell back to chip EV.
- Patch (T3): icm_shove_n 4; util_late: utility branch also for 3-4 players when exact ICM is not
  applicable; new icm_me() = exact Malmuth-Harville equity of one player for <= 5 players with
  no per-mask allocations (matches kit icm to 1e-13, 4 µs vs 24 µs). 4-player shove p99 48 µs.
  Local A/B: score level, 4th places 78 vs ~100-107 per 800 tables (they become 3rds).
  Submitted as 010-127f4b59.
- pos_min_n 4: the positional shove-range factor (x1.6 SB / x1.3 BTN) double-counted with HUF in
  heads-up / 3-handed (HU SB shove range was assumed 70%); now only with >= 4 players.
  4 runs: +0.4..+1.2 vs 010 (noise-level but consistent). Submitted as 011-6d0fd783 (active for T3).
  Zoo sanity 59.0 pts/table, timing p99 50 µs / max 96 µs (icm_me removed the old ~600 µs outliers).
- huf3 (3-handed range factor) 1.2 vs 1.4: noise; kept 1.4 (now a P key, "huf3").
- Head-to-head 800 tables: 011 avg 32.7 (4th places ~98), 009 31.4 (4ths ~120), 008 31.4.
- alpha 0.70 vs 0.75 on the 011 build (2 x 800): 0.75 better in both (32.4/32.3 vs 31.3/31.2).
  With 0.82 also worse earlier, 0.75 looks like the local optimum.
- For the T4 window: compare T3 places to T2 (4th 163, 2nd 106, 3rd 107). If 4ths fell and 1sts
  held, keep; if 1sts dropped, consider util_late 0 (ICM shoves alone tested equal).

## T3 result (011-6d0fd783): 29.39, rank 7/8 (weighted total 180.01, rank 6)
- Places 101/105/125/156/141/141/114/117. 1sts fell (T1 139, T2 129, T3 101); heads-up win rate
  60% -> 55% -> 49%; reached HU 232/235/206 times. VPIP drifted down 23.6 -> 22.0 -> 20.9%.
- Reading: early-stage risk aversion (T2's util) helped (busts down, score up); the T3 late-stage
  tightening (ICM shoves at 4, util at 3-4 players, no positional widening HU) cost wins. Self-play
  had shown it level on score but with fewer 1sts too (95 vs 104 per 800).
- T4 patch: reverted to the exact v10 code (resubmitted as 012-c54c104e, same hash as 009).
  v12 is backed up in tools/bot_v12_backup/.
- Tested on v10: alpha schedule by players left (a6 0.8, a5 0.85): level with v10 in self-play,
  no gain in 1sts; ICM says x^0.75 is already slightly less risk-averse than exact ICM at 6 players.
  Not submitted.
- icm_n 3 vs 4 (exact-ICM calls at <= 3 players instead of <= 4), 2 x 800 self-play: score level
  (31.8 vs 31.85), fewer 4ths (~86 vs ~107) and more 3rds. Not submitted (self-play place shifts did
  not transfer in T3); a candidate if T4 still shows ~160 4ths.
- Self-play 1000 tables, v8/v10/v12 x2-3 each: v12 32.6, v10 32.1, v8 31.1. Place SHAPES match the
  tournaments (v8 many 1sts + many 8ths like T1; v10 4th spike 159-168 like T2; v12 more 3rds, fewer
  1sts like T3), but score order did not (T2 v10 31.28 > T3 v12 29.39, within ~1.3 SE).
- Candidate for T5 if T4 shows the 4th spike again: v10 + icm_shove_n 4 only (keep pos factor in HU,
  no util_late). Self-play "hA" tested level with v10 on score. v10's 4th spike most likely comes
  from chip-EV shoves at 4 players with the looser -0.02*stack threshold.
- hA2 (= tools/bot_v12_backup code + {"util_late": 0, "pos_min_n": 2}, i.e. v10 + 4-player ICM
  shoves with fast icm_me) vs v10, 1000 tables x4 each: 32.0 vs 31.7; 1sts 123 vs 127, 3rds 131 vs
  118, 4ths 119 vs 131. Small shift, not submitted for T4. Ready-made dir: tools/v_hA2/.
  Second 1000-table run: hA2 31.5 vs v10 32.1; 1sts 119 vs 129, 4ths 113 vs 132. Combined: level,
  hA2 trades 1sts for fewer 4ths, which the field punished in T3. Kept v10 for T4.
- T3 sample hands (first 10 hands x 4 tables): biggest loss KK vs AA 100bb preflop (cooler);
  nothing broken.
- Lesson: self-play is a weak proxy for the field; trust tournament place distributions, and
  watch the 1st-place count, not only busts.

## T4 result (012-c54c104e = v10 code): 30.29, rank 6/8 (weighted 301.15, rank 6)
- Places 103/126/112/165/133/125/115/121. Same code as T2 but 1sts 129 -> 103: the T2->T3 1st drop
  was field/noise, not my late-stage change. 4th spike persists in T2/T3/T4 (163/156/165), but
  every self-play "fix" for it also cut 1sts.
- HU win rate keeps falling: T1 60%, T2 55%, T3 49%, T4 45% (n ~ 230 each); the field is getting
  more aggressive (T4 winner b06: VPIP 28%, PFR 23%).
- HU leak in code: with eff > 15bb the SB opened only top 54% (raise) + limped up to 60%, folding
  ~40%; BB defended only 60% vs small raises. Candidate: hu_open 0.85 (raise top 85% HU, 2.5bb),
  def2 0.75 (code saved in tools/agent_hu_variant.py; defaults there = v10 behaviour).
  Self-play (v10-only pool) 2 x 1000 tables: score 31.75 vs 32.0, HU win 50.8% vs 50.5%: no effect.
  Aggressive-field proxy (tools/v_aggro: open_mult 1.5, shove_bb 14, reshove 20, util 0, cbet 0.8,
  wide HU) reproduces T4's symptom: v10 wins only ~45-47% of HUs there. HU-wide version: HU win
  51-52% vs 45-49% for v10 over 4 runs; score level overall (32.58 vs 32.65; expected gain from the
  HU rate ~+0.45/table, below test noise). The aggro proxy itself scores lower (31.3).
- 5th run (aggro field, 013 x2 vs 012 x2): 32.25 vs 33.4, HU win 48% vs 48%. All 5 runs: score
  32.5 vs 32.8 (level), HU win better for 013 in 4/5. Kept 013 (no evidence either way on score).
- T5 submission: 013-71b0010d = v10 + hu_open 0.85 (HU SB raises top 85% to 2.5bb when eff > 15bb)
  + def2 0.75 (HU BB defends top 75% vs raises to <= 3bb). Nothing else changed.
- Zoo sanity for 013: 59.4 pts/table, 0 substitutions.
- Info for T6: HU shove-range cap 0.55 instead of 0.7 (tools/v_rcap, params {"rcap": 0.55}),
  1 run in aggro field: 32.9 vs 31.95 for 013, but HU win 50% vs 55%. Mixed; needs more runs.
  2nd run: rcap 32.96 vs 013 31.98, HU win 50% vs 49%. Two runs: rcap +0.95 (3 vs 5 entries,
  noise ~1). 3rd run: rcap 32.07 vs 013 33.0. All 3 runs: 32.58 vs 32.26 (+0.3) = noise.
  Not a real candidate.
- If T5 HU win rate is still < 50%: look at HU push/fold ranges (r for SB shoves 0.7 cap with pos
  x1.6; cp HUF 2.0) next.

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
