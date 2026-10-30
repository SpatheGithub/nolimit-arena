# Team notes (b04)

## Approach
Aggressive-pressure NLHE SNG bot (bot/agent.py) with helpers copied from house-bot `_common.py`
(Spot parser, Ranker, postflop `features()` strength, preflop class/percentile tables).

- Preflop:
  - Unopened: open-raise ranges by # players behind (OPEN table, BTN 48%, SB 62%), 2.3bb (3bb SB);
    deep (>40bb) early/mid positions tightened by DEEP_OPEN=0.7; widened/tightened by observed
    fold-to-raise rate of players behind.
  - <=13bb: open-shove. Candidate range = PUSH table (Nash-like) x PUSH_CAP, final decision by
    ICM EV with fold equity. Each player behind calls with top cr (prior 12%, from observed fold rate;
    x1.8 for BB, x1.2 SB, x1.6 if the call is cheap for them, x2.5 if they're nearly all-in anyway).
  - Facing a raise: raiser range = observed open rate x position factor (3-bet: observed re-raise rate).
    Re-steal shove (<=32bb) if ICM EV with fold equity > RESTEAL (0). All-in calls by ICM EV
    using precomputed equity vs top-R% ranges (bot/eqr.json, 4000 samples per cell, tools/eqrange.py).
    Cheap flat calls (BB pct<=35%, others <=12%) when the shove isn't +EV.
  - Deep: 3-bet value (pct<=3.5%), light 3-bets vs wide openers 35%, BB defend pct<=45% vs small opens.
- Postflop: features() strength s, outs. Value bet s>=0.6 (size x1.2 vs stations, x0.85 vs folders),
  c-bet HU 75%/50%/20% flop/turn/river, stabs 25% IP HU; bluff freq scaled by opponents' observed
  fold-to-bet rate. Semi-bluff draws. Facing bets: eq = s - bet-size penalty + bettor aggression adj;
  draws use 2-card equity on flop (x0.85) / implied odds on turn; call if eq >= pot odds; big commits
  (>=50% stack) need positive ICM EV.
- ICM: bot/icm.json = ICM points by (players left, my chip fraction), others equal (kit/icm.py);
  exact Malmuth-Harville (icm_me) with real stacks when <=4 players have chips and <=5 alive.
  Value = ICM_W*ICM + (1-ICM_W)*chip-linear points, ICM_W = 0.8.
- Opponent model (per table only): open rate, fold-to-raise, re-raise rate, postflop aggression,
  postflop fold-to-bet, all with priors.

## Key parameters
OPEN/PUSH tables, PUSH_CAP=1.6, RESTEAL=0.0 (ICM pts), STAB=0.25, RIVER_BLUFF=0.2, DEEP_OPEN=0.7, ICM_W=0.8.

## Test results (localsim)
- Each house field x7: nit 80, maniac 47, montecarlo 57, pot_odds 45, random 68, minraiser 48,
  threshold 57, checkfold 100 (all 1st).
- ICM vs chip-EV all-in decisions: +3.6 pts (600 tables, mixed field). Blend 0.6 vs 1.0: +1 (noise).
- Field of all my submissions: latest ~35 vs v1 ~28.
- In fields with several aggressive clones, the house nit scores ~37-43 (survival is worth a lot with
  100/60/40/25/15/10/5/0); ICM was the fix that helped most.

## Submissions
- 001 baseline; 002 opp model + ICM all-in; 003 RESTEAL=0 + flat calls + postflop fold stats + precise eqr;
  004 exact ICM (<=5p) + blind call-range fix; 005 draw-equity fix, ICM_W 0.8, exact ICM <=4p;
  006 value sizing vs stations/folders + showdown-based range widths; 007 multiway all-in eq^(1+0.4*callers).
- ACTIVE: 009-a15c20b6 (007 + unopened shove-or-fold up to 20bb; 008 was the 16bb step).
- Late A/Bs (600 tables, all within noise): SB deep-open x0.75 = no change; re-steal call_r lower
  (more re-steals) -1.8; call_r higher (fewer re-steals) -3 -> kept 007 values. Multiway exponent 0.7 was -2.

## Loss diagnostics (end of build, tools/vDiag logs hands losing >35% of stack to tools/diag.log)
- 300 mixed tables, share of big-loss chips: preflop re-shove 13-30bb 23%, preflop calls 13-30bb 16%,
  open/re-shove <=13bb 11%, calls <=13bb 9%, river calls (deep+mid) ~12%, everything else small.
- Re-shoves 13-30bb used hands with median pct 0.42 (90th pct 0.83) vs callers' shown median 0.05.
  Tried RESTEAL_PC=0.35 floor + RESTEAL_CAP=0.30: A/B -1.9 (noise) -> NOT submitted (the log only shows
  called re-steals, not the ones that won the pot uncontested). Worth re-testing with real tournament data.
- Postflop big losses looked like coolers (sets, two pair, full houses), not systematic.

## Extended window (16:14-16:25)
- Big A/B design: 3 copies of variant + 3-4 copies of baseline + nit, 1000 tables (~60-90s).
- Re-steal fix (RESTEAL_PC 0.35 + RESTEAL_CAP 0.30): -2.9 vs 007 -> rejected; wide re-steals ARE profitable.
- Open shove-or-fold threshold (unopened pot) 13bb -> 16bb: +1.7 (all 3 copies above all 007 copies) -> 008.
- 16bb -> 20bb: +2.6 vs 008 (again all 3 above all 4); zoo 300 tables 56.0 (1st) -> submitted as 009.
- 20bb -> 25bb (tools/vS25, 500 tables, not submitted: window closed): 34.1 avg vs 009 31.2 avg (+2.9,
  but only 500 tables and one 25bb copy fell below one 009 copy). FIRST THING TO DO IN THE PATCH WINDOW: confirm with
  1000 tables + zoo check, then submit (one-line change at agent.py `if eff_bb <= 20:` in the unopened branch).
  Second seed (400 tables): vS25 32.6 avg vs 009 32.5 avg -> no difference. Combined evidence is weak;
  20bb (009) may already be near the optimum. Only switch to 25bb if a 1000-table run is clearly positive.
- Then try widening the re-steal zone (eff_bb <= 32 now); aggression keeps paying in clone fields.

## Known weaknesses
- Postflop strength is a category heuristic, no real equity / range reading.
- Fold-equity model for shoves is crude (prior call range 12%), re-steal call_r guess.
- ICM table for >4 players assumes opponents have equal stacks; ICM ignores blind pressure (blend helps).
- Occasional localsim "hang"/max-time spikes are machine load (p50 25us, p99 ~100-200us).

## Next steps / ideas for patch windows
- Use showdown cards to calibrate opponent ranges; per-seat call-vs-shove frequency.
- Tune open-shove threshold (13bb) vs raise-fold at 13-20bb.
- Ramp ICM_W to 1.0 near the hand cap.
- Tools: tools/scen.py (preflop spots), tools/post.py (postflop spots), tools/scan.py (push range sizes),
  tools/bench.py (timing). A/B: copy bot to tools/vX and run localsim with mixed --opponents.
