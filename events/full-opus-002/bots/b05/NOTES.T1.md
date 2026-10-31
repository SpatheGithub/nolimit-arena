# Team b05 notes

## Submissions
- 001 baseline; 002 ICM pair factors + range-threshold postflop model; 003 fold-to-bet tracking;
  004 shove-frequency tracking, ICM re-shove EV fix, bluff-catch weight; 005 full draw equity when
  all-in, combo-draw flop shoves, 22bb re-steal zone; 006 bettor preflop-aggression and
  caller terms in the range model, heads-up / 3-handed shove-range floors; 007 (active) deep 3-bet
  defence by equity vs the 3-bettor's range (call if eq >= pot odds + .06 IP / .10 OOP and call
  <= 25% stack; value 4-bet top max(2%, range/4)). 007 vs 006: self-play +1.05, mixed field +0.1.

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
- Use patch-window results: if many all-ins lost, revisit calling ranges / _ICM_W; if blinded out,
  widen push ranges (calling_range priors).
- Widen 3-bet defence vs high-PFR openers; track opponents' 3-bet frequency.
