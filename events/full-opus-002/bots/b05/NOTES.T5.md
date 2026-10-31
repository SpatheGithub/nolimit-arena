# Team b05 notes

## Submissions
- 001 baseline; 002 ICM pair factors + range-threshold postflop model; 003 fold-to-bet tracking;
  004 shove-frequency tracking, ICM re-shove EV fix, bluff-catch weight; 005 full draw equity when
  all-in, combo-draw flop shoves, 22bb re-steal zone; 006 bettor preflop-aggression and
  caller terms in the range model, heads-up / 3-handed shove-range floors; 007 (active) deep 3-bet
  defence by equity vs the 3-bettor's range (call if eq >= pot odds + .06 IP / .10 OOP and call
  <= 25% stack; value 4-bet top max(2%, range/4)). 007 vs 006: self-play +1.05, mixed field +0.1.

## Tournament log
- T1 (007): rank 4/8, 32.91 (30.90-34.93); leaders b03 34.78, b08 33.73, b06 33.32 (all within
  noise). Places 1st..8th per 1000: 138 120 129 115 124 137 130 107. 0 subs, p99 100us.
  Field VPIP 19-25%, PFR 12-20%. sample_hands.json = only first 10 hands of 4 tables (deep, small
  pots): field opens 2.5bb, 3-bets ~3x, callers often check-fold to half-pot c-bets, openers
  often fold to 3-bets.
- Patch before T2: tested a flop stab (IP, preflop raiser checks, 35% x fold-rate scale, 0.5 pot):
  self-play -1.17 / +0.78, mixed -0.23 => neutral, NOT submitted; bot/ reverted to 007.
  `tools/sim3.py` (place histograms via run_tournament) crashes in the worker pool - unfinished.
- 008 (active for T2): per-opponent fold-to-3-bet tracking (`faced3`/`fold3`: an opener who
  raised preflop and then faced a re-raise) + light 3-bet (3x IP / 3.6x OOP, 40% of the time,
  hands pct <= .35 that would otherwise fold) only vs openers with >= 3 samples and shrunk
  fold-to-3bet >= .60. A/B vs 007: self-play -0.64 / +0.21 / +0.05, mixed field +1.66 / -0.83
  (avg ~+0.1: neutral in sims; kept because the T1 field visibly over-folds to 3-bets).
  All-versions field (600 tables, seed 701): 003 34.7, 007 33.9, 005 33.5, 008 31.3, 006 31.3,
  004 30.8, 002 30.0, 001 29.5 - all within +-2.5 CI. Re-checked head-to-head (ab.py, 600 tables):
  008 33.2 vs 003 29.6 -> 008 clearly better; the all-versions ordering was noise.

- T2 (008): rank 3/8, 32.13 (30.19-34.08); b03 35.37 leads again. Places 118 143 129 109 121 141
  129 110. Pooled T1+T2: 6th+7th 26.9% (exp 25%), 4th/8th low -> mid-stage busts. Samples again
  only hands 1-10 (100bb); one opponent 4-bet shoves 100bb (QQ shown).
- Patch before T3: 009 (active) - re-shove fold equity now from opener's fold-to-3bet stat
  (fe = .9*(fold3+1.5)/(faced3+3), cap .7) when >= 3 samples; generic preflop fold rate (which
  overstates openers' folding) only as fallback, scaled .6 and capped .5. A/B vs 008: self-play
  +0.25 / +0.44, mixed field +1.81.
  Tested vs 009, NOT submitted (inconsistent): `_ICM_W` 0.7 (mixed +1.14, self +0.21 / -0.89);
  thin-value threshold .58 -> .62 (self +0.93, mixed -0.47).
- 010 (active for T3): light 3-bet frequency vs proven 3-bet folders 40% -> 60% (same gate:
  >= 3 samples, shrunk fold-to-3bet >= .60). A/B vs 009: self-play +1.59, mixed +1.77.
  Zoo sanity (200 tables): 60.1/table, 1st. If T3 drops, the 3-bet exploit is the suspect:
  revert r < 0.6 -> 0.4 (009) first.
  Versions field (600 tables, seed 951): 007 39.0, 010 37.6, 003 36.7, 008 36.3, 009 35.4,
  005 33.2, nit 26.9, montecarlo 9.8 - all bots within +-2.7 CI (noise); 010 not worse.
- T3 (010): rank 2/8, 33.95 (31.98-35.93); b03 35.70 1st. Weighted total 199.05, rank 3.
  Places 132 143 122 143 133 116 113 98: 6th+7th fell 26.9% -> 22.9% after 009/010.
  Samples again hands 1-10 only.
- Patch before T4: kept 010. Tested vs 010, NOT submitted:
  light 3-bets pct<=.45 & r<.75 (self +0.39, mixed +0.15); re-steal zone 25bb (self +0.49,
  mixed +0.07); both combined (self +1.17, mixed -0.50 / -0.41). Self-play gains come from
  exploiting our own fold-to-3bet; not robust in the mixed field.
  No SB limp (raise-or-fold, pct<=.6 completes removed): self -0.95 -> rejected.
  Flop stab retested vs 010: mixed +0.62, self -0.18 (vs 007 earlier -1.17/+0.78/-0.23) -> neutral.
- T4 (010): rank 4/8, 31.59 (29.69-33.49). b06 35.63 1st after going LAG (VPIP/PFR 23/17 ->
  28/23); b03 35.28 (steady ~35.3 avg over T1-T4). Our 1st places fell to 109 (from 132); our
  postflop actions fell ~13% (more hands end preflop). Weighted total 325.41, rank 4.
- Patch before T5: kept 010. NOISE BASELINE: `tools/ab3.py` (cur x3 vs base x2 + bot, plus 2 LAG
  copies in `tools/lag`: opens x1.5, 3-bet .05+.2w, light 3-bets 30%) with IDENTICAL code gave
  diff +1.51 at 800 tables -> A/B noise is ~+-1.5; earlier "wins" of ~1-2 points were noise-level.
  LAG copy scores ~30.2-30.9 (below field avg) locally. Rejected vs 010 in LAG field: light 3-bet
  vs loose openers pfr>.22 (-1.16); late-position steals x1.15 (-0.56).
  010 vs 007 in LAG field: about equal (-0.33, noise). Real results: 007 32.91 (T1), 008 32.13
  (T2), 010 33.95 / 31.59 (T3/T4) - all within noise; no reason to switch versions.
  HU conversion T1-T4: 1st 497 vs 2nd 547 -> win 47.6% of heads-ups (40 pts at stake). Possible
  cause: raiser range from whole-table PFR (~20%) underrates HU opens. Tested HU floors (open
  >= .5, 3-bet >= .2, 4-bet >= .08): self -1.29 -> rejected (may also be chip-position on
  arrival, not HU play).
  Probe (`tools/probe_hu.py`): HU BB calls vs SB shove = 42% @6bb, 35% @10bb, 24% @15bb,
  15% @20bb vs Nash ~55-60 / 37-40 / 27-30 / ~22%. Tight at 6bb and 20bb because HU shove-range
  floors are .55 (<=10bb) / .42 (<=15) / .30 (<=25). Lead for T6 window: Nash-like floors
  (.70 <=6bb, .55 <=10, .45 <=15, .35 <=20) if opponents are seen shoving wide HU.
  BB vs HU 2.2bb open already defends ~70% (pot odds), so open-range floors aren't needed.
  Nash-like HU floors tested in self-play (our bot shoves ~Nash-wide HU): +0.25 -> neutral, kept 010.
  Push zone 15bb -> 13bb (unopened): self -0.37 -> rejected.

## Approach
- `bot/agent.py` + `bot/hcommon.py` (house-bot helpers copied from kit: Ranker evaluator, Spot parser,
  `features()` postflop strength heuristic) + data files:
  - `bot/hcommon.json`: preflop class percentile + equity vs k random hands (from kit).
  - `bot/eqmat.json`: 169x169 class-vs-class preflop equity (MC, 400 boards/pair, `tools/pre_eq.py`).
  - At import: `_EQR[c][x]` = equity of class c vs top-x% range (grid, interpolated).
- Preflop:
  - eff stack <= 15bb and unopened: push/fold by chip-EV of shoving; each player behind assumed to
    call with a top-c range (c by shove size in bb, BB x1.35, HU x1.3), replaced by the observed rate
    at which that opponent called MY shoves once >= 3 samples. Loss weighted by ICM `bf_pair`.
  - deeper: open-raise top-X% by players behind (12%..45%, HU 75%), 2.2-2.5bb; 3-bet value range
    scaled by raiser's PFR; set-mine pairs (call <= eff/15); flat by equity vs raiser range.
  - facing a shove / commitment (call >= 35% stack, eff <= 18bb, or single raise at eff <= 22bb):
    equity vs estimated range against ICM-adjusted pot odds; re-shove EV with fold equity.
    Shover range = max(PFR-based, stack-based default), blended with observed preflop shove rate
    (1.7 x shoves/hands), floored HU (55%/42%/30% at <=10/15/25bb) and 3-handed (35/26/18%).
  - multiway: equity vs callers of a raise uses a tighter range; players behind discount 0.975 each.
- Postflop: strength s from `features()` + draw outs (eq1 = s + (1-s)*draw).
  - Not facing bet: value bet eq >= .78 (shove at SPR <= 1.3), thin value >= .58 (.52 vs stations),
    semi-bluff draws, c-bet HU as aggressor (65% dry / 45% wet), bluff frequencies scaled by the
    lowest postflop fold-to-bet rate among opponents (stations < .30 -> 0.4x, folders > .55 -> 1.4x).
  - Facing bet: bettor-range threshold T = .30 + .15*betfrac (+.15 raise, +.08/.12 per earlier
    street the bettor bet/raised, +.05 river, +.02/.06 if bettor raised/3-bet preflop, +.05 per
    caller). eq = beta*bw + (1-beta)*(s-T)/(1-T); beta (bluff share) from bettor AF (.06...25);
    bw = min(1, .25 + 1.5 s) so air doesn't bluff-catch. All-in calls take max with full draw
    equity (85%). Raise/shove with eq >= .88; shove 12+ out draws on flop at SPR <= 4.
- ICM: bubble factors from kit/icm.py at equal stacks (1.3 at 3 left .. 1.55 at 8), multiplied by
  stack relation (cover short 0.75-0.82, covered by bigger 1.12, I'm short 0.88), damped
  `_ICM_W = 0.5` because blinds double every 25 hands (folding is costly).

## Testing
- `tools/ab.py <tables> <seed> <opp_dir> [edits]`: bot copy (tools/cur) x4 + bot vs opp x3.
- `tools/ab2.py`: cur x2 + bot vs base x2 + nit, maniac, montecarlo.
- `tools/dbg/`: debug copy that logs big pots (dbg.log) and swallowed exceptions (err.log).
- Seat SE is ~±3 points at 600 tables; most single changes are not separable by sim. Zoo: ~60/table.
  006 vs 005: self-play +1.0, mixed field +0.1.

## Known weaknesses
- Postflop strength is a heuristic (no runtime equity); decision time p99 ~75us, lots of headroom.
- Deep 3-bet defence is tight (fold everything but top 4.5% to 3-bets); no squeeze, no check-raise.
- Shove range estimate from shove frequency is crude (frequency != range width when opponents mix).

## Next steps
- Light 3-bets vs over-folders are in 008; if T2 shows worse results, revert to 007 (only change).
- Flop stab is neutral in self-play; may still pay vs the real field (check-folders). Retry only
  with real-field evidence.
- If later results show many early busts (6th-7th), revisit deep stack-off thresholds / _ICM_W.
