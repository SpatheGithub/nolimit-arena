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

- 005 v10: BB defense widened vs late-position steals (top 42%) and heads-up opens (top 60%); exact ICM for
  call-offs with 5 alive. 006 v11: range lists cached, enumerate only widths < 0.2. Tried "check caps range"
  (exclude two pair+ when opp checks): worse on 2 seeds (-3.9, -1.4) -> USE_CAP = False.
- vs all earlier submissions (seed 21, 400 tables): 001 31.3, 002 32.8, 003 36.7, 004 38.7, 005 41.3, v11 41.4.

## T1 result (006): rank 5/8, 30.70 pts (field 29.3-34.8, all within noise of each other)
- places 1st 101, 2nd 157, 3rd 129, 4th 88, 5th 129, 6th 116, 7th 144.5, 8th 135.5; vpip 22.5 pfr 17,
  wtsd 4.6%, showdown win 50.5%. 5 timeouts + 3 hangs out of 112,650 decisions; cpu max 1978 us.
- Takeaways: we lose heads-up 61% of the time (157 seconds vs 101 wins), and we bust 7th/8th 28% of the time.
- sample_hands.json only has hands 1-10 of 4 tables (no showdowns), so it says little.

## Patch before T2
- 007: timing safety: MC deadline 0.42 -> 0.38 ms; reuse the `used` set in the MC loop (fewer allocations
  and fewer GC pauses inside act).
- 009-56cbe984 (ACTIVE for T2): 007 + heads-up SB open top 80% only; BLUFF_SCALE back to 1.0.
  Check vs 003-008 + nit (seed 43, 400 tables): 009 37.3 (1st), 007 36.0, 006 35.3, 008 33.0, 005 32.2.
  Mixed house field (seed 2, 300 tables): 009 62.8 (v8 61.4, v10 60.5, 008 61.2) -- best so far there.
  Loose field (maniac x2, minraiser, random, pot_odds, montecarlo, threshold; seed 5, 250 tables): 009 67.0 (v11 62.9).
  vs 7 copies of 007 (tools/analyze.py, 200 tables): avg 30.9 (self-play par 31.9); places 1st 22, 2nd 24, 3rd 30,
  4th 27, 5th 21, 6th 20, 7th 29, 8th 27 -> heads-up 22 wins / 24 losses: no clear heads-up edge yet.
  Reason: vs a diverse field of my submissions 003-007, 008 scored -2.1 (seed 41) and -1.2 (seed 42) below
  the field average. That is within noise but the wrong direction, so I dropped the untested-in-field bluff change.
- 008-4ec1b7ea: (a) heads-up SB opens top 80% (was ~50%) when eff > 14bb. Folding half of our
  small blinds heads-up at 15-25bb was far too tight. (b) BLUFF_SCALE = 0.75 scales the assumed bluff share of
  opponents' postflop bets/raises (only when they bet or raised), so we call down less, aimed at T1's early busts
  and 50.5% showdown wins. Local tests were neutral: vs v11 copies 33.3 (avg 33.2) and 33.8 (avg 33.3),
  mixed 61.2 (v8 61.4).
- Note: `bm` (aggression ratio) raises the assumed bluff share for aggressive opponents, but aggression is not
  the same as bluffing. A value-heavy aggressive bot gets too much credit for bluffs. Possible fix: use
  showdown data (shown hands after big bets) instead.

## T2 result (009): rank 5/8, 31.61 pts; 0 timeouts (timing fix worked)
- places 1st 103, 2nd 164, 3rd 134, 4th 95, 5th 128, 6th 120, 7th 124, 8th 132. Again we lose heads-up about 61%
  of the time (103 wins vs 164 seconds). Weighted total 93.93, rank 5. Leader b03 (VPIP 24, PFR 18) 35.4.
- Locally (tools/hustart.py) we reach heads-up with ~50% of chips and win 55-61% of those matches vs our own
  versions. So the T2 heads-up losses depend on the real field's heads-up play, which I can't reproduce.
- Fresh short-stack heads-up matches (tools/hu.py, ~10bb at 160/320): 009-ish vs 007 52%, vs pot_odds ~50%,
  montecarlo 50-54%, maniac 57-60%, threshold 54%, nit 94%. Break-even vs calling stations: they limp every
  small blind and call ~70% of our 10bb shoves; we assume 38% (Nash) until sh_called stats exist.

## Patch before T3: 010-ccd88033 ACTIVE = 009 + heads-up shove/raise tracking only (tools/hutrack)
- Decided by a within-table design (hutrack x3 + 009 x4 + nit, 400 tables): seed 51 hutrack avg 34.3 vs 009
  avg 32.6 (+1.7); seed 52 33.8 vs 32.7 (+1.1); seed 53 (4 hutrack incl. you vs 3 x 009) 33.6 vs 32.7 (+0.95);
  seed 54 (3 x 010 vs 4 x 009) 33.4 vs 33.1 (+0.3); seed 55 32.6 vs 33.75 (-1.15).
  Mean of 5 paired runs about +0.6 (SE ~0.5): a small edge at best. T3 results should decide 010 vs 009.
  This outweighs the earlier separate-run -1.6 (seed 44).
- Caution: house-bot mixed field was worse: 010 57.0 vs 009 62.8 (seed 2, separate runs). Paired seed 61
  (010 x2 incl. you + 009 x1 + 5 house bots): 010 seats 53.2 / 46.6 vs 009 53.2. Same-code seats differ by
  6.5, so it's noise-dominated. Kept 010 because competent-bot fields are closer to the real field. If T3
  heads-up still loses ~61%, or the score drops, revert to 009 (identical except the hu_* tracking).
  Only heads-up BB decisions vs a small-blind raise change, after 4+ observed heads-up small blinds.
### Earlier in this window (details)
- Tried (tools/hutrack/): per-opponent heads-up small-blind raise/shove tracking (hu_sb/hu_raise,
  hu_sbs/hu_shove), used as the shover's range in heads-up. Also tried pooled table-level shove-call stats as
  the prior and limpers treated as likely callers (x1.1). Full-table vs 009 copies: -1.0, -1.6; vs
  submissions: -1.1 (all noise-level but consistently negative). Heads-up vs a field shoving any two at
  <=16bb: 57.7% vs 009 55.4% (n~75, noise). Not submitted.
- Idea for later: in heads-up, don't shrink the Nash push width by 0.8 using full-ring pfr
  (`w = max(wn*0.8, pfr*1.8)`). A full-ring pfr of ~0.17 makes us assume ~45% shoves at 10bb.
  Also consider heads-up SB limping vs passive bots.

## T3 result (010): rank 5/8, 30.50 pts (b03 35.7, b05 34.0, b06 33.6, b08 33.0)
- places 1st 111, 2nd 144, 3rd 115, 4th 102, 5th 104, 6th 140, 7th 130, 8th 154. Heads-up conversion
  improved (43.5% vs ~39%), but early busts rose. Showdown win ~50% in all of T1-T3. Weighted 185.43, rank 5.

## Patch before T4: 011-a30c46b8 ACTIVE = 010 + more bluffing (tools/morebluff)
- Heads-up flop c-bet 0.6 -> 0.72 (multiway 0.3 -> 0.35), turn barrel 0.4 -> 0.5, probe bet 0.25 -> 0.33 (all
  still x fmult from opponents' observed fold-to-bet rate, so they shrink vs calling stations).
- Paired vs 010 (3 variant seats vs 4 x 010 + nit, 400 tables): seed 71 +1.4, seed 72 +2.0, seed 73 +3.0
  (mean +2.1). Consistent with less bluffing being -1.8.
- Even more (0.8 / 0.6 / probe 0.4, tools/morebluff2) vs 011 copies, seed 71: 33.0 vs 33.4 (-0.4) -> 011 level
  is about right. If T4 shows a drop, the real field may call more than our copies do; revert to 010.
- 011 vs mixed house field (seed 2, 300 tables): 61.5 (010 57.0, 009 62.8): no collapse vs calling stations.
- 011 vs single copies of 005-010 + nit (seed 81, 400 tables): 34.3, 2nd after 010's 35.2 (single seats,
  noise about +/-3).
## Earlier experiments in this window (paired: 3 variant seats vs 4 x 010 + nit, 400 tables)
- ICM loss weighting: weight chip losses by 1 + k*fraction lost, k=0.62 at 5+ alive. Kit ICM says an even
  full-stack flip needs 62% equity at 5-8 players. Applied to shove EV, call-offs, resteal and postflop calls:
  31.3 vs 34.9 (-3.6), and all 4 x 010 seats beat all 3 variant seats. Tighter ICM play loses to
  chip-EV opponents with these fast blinds. Don't do this.
- Postflop-only, half weight (k=0.31): +1.3, -0.44, -0.23 (mean +0.2) -> no.
- Wider opens (+~15% thresholds): +0.6, -0.15 -> no.
- Opposite direction: no ICM at all (chip EV in shove/call decisions, no 6-handed premium): +0.41, +0.89,
  -1.78 (mean -0.16) -> no. The current partial ICM (exact at 3-4 for shoves, 3-5 for calls) is about neutral.
- Less bluffing (heads-up flop c-bet 0.6->0.45, turn 0.4->0.25, probe 0.25->0.15): seed 71 32.2 vs 34.1
  (-1.8) -> no; current bluff frequencies are fine vs our own copies.
- Variants saved in tools/icmw, tools/icmpost, tools/wideopen, tools/noicm, tools/lessbluff.
- Conclusion: every variant is within about +/-1 of 010 in self-play. Real-field gains need field-specific
  info, which the sample hands (hands 1-10 only) don't give.

## Known weaknesses / next
- Heads-up and 3-handed play: check push/fold widths against the field's actual calling ranges
  (sh_called stats). Could add HU limp/min-raise sizing.
- Possible over-calling postflop (showdown win 50.5%): consider lowering bluff-skip fractions
  (A==1 0.35, A>=2 0.25, raise 0.15) if the field is value-heavy. Untested.
- MC is noisy (~50-100 samples). Board-paired handling of requirements is crude.
- No 3-bet bluffing; no limping.
