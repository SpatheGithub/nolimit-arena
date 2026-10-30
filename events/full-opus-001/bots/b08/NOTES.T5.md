# Team b08 notes

## Approach
- `bot/agent.py` + `bot/_common.py` (copied house-bot helpers: Ranker, Spot, features()).
- Preflop: class percentile table (`_common.json`) + `bot/eqtop.json` = equity of each of 169
  classes vs the top k% of hands (k=1..100), built from a Monte Carlo 169x169 class-vs-class
  matrix (tools/pre_eq.py, 1500 deals/pair; tools/mk_eqtop.py).
  - Unopened: open-raise by position (players behind) thresholds on percentile; <=13bb: push/fold
    with Nash-ish thresholds (scaled by (10/eff_bb)^0.6, x PUSH_ICM when >=4 alive).
    Short-handed widening (HU open 80%, 3-handed x1.4, 4-handed x1.25). Steal wider when players
    behind have low observed VPIP.
  - Facing raise: estimate raiser range r (by raise size, shove stack depth, position, n alive,
    and observed per-seat PFR / big-raise frequency at this table), equity vs top-r, compare with
    pot odds (+ICM premium when committing). Multiway: eq^(1+0.6*callers).
- ICM: break-even equity for a coin-flip all-in with 8 equal stacks is ~0.62 (computed with
  kit/icm.py), so all-in / stack-off calls add an ICM premium (0.10 base, 0.07 3-handed, 0 HU,
  scaled by fraction of my stack at risk). Tables never reached the 200-hand cap in sims.
- Postflop: features() strength (0..1) + draw outs; multiway discount; value bet / c-bet;
  facing bets: call if eq - discount >= pot odds. Discount = street base (0.03/0.10/0.15) +
  size term + raised-over-my-bet term + extra for weak hands on turn/river; scaled down vs
  aggressive opponents (observed postflop aggression).

## T1 result (v8): rank 4/8, 32.01 pts/table (field 29.7-34.9, all within noise)
- Places flat (1st 11.7% ... 8th 11.4%). 0 substitutions. b02 won with VPIP 19 / PFR 14.
- results/T1/sample_hands.json = 40 level-1 hands from 4 tables: opponents open 2.3-3bb,
  c-bet ~0.45-0.6 pot, and preflop callers FOLD to flop bets very often (~8 of 10 seen).

## Patch before T2 -> v9 = 009-9d9bb941
- CBET 0.6 -> 0.8 (HU flop c-bet any hand, 0.45 pot) and STAB=0.6: as preflop caller in
  position HU, bet 0.5 pot on the flop when checked to.
  Mixed field +3.2 then -0.9 vs v8 (two seeds), self-play vs v8 copies 32.7 (avg 31.9).
- Tested, not submitted: turn stab after checked-through flop + more multiway c-bets
  (tools/v/cT): mixed +2.2, self-play 31.4 -> inconclusive.
- Tested, not submitted: OPEN_LATE=1.0 (tighter, like b02): self-play vs v9 copies 31.6 -> no gain.
- v10 = 010-b1654798 (ACTIVE for T2): CBET=1.0, STAB=0.8 (always c-bet HU flop 0.45 pot; stab
  0.5 pot IP as caller 80%). Self-play vs v9 copies 34.8 (avg 31.9, +2.9), mixed field 51.0 vs
  v9 46.5 / v8 47.0 (800 tables each). Exploits high fold-to-flop-bet rate seen in T1 sample.
- Tested on top of v10, not submitted: BARREL 0.55 (tools/v/cBar): self-play 31.9, mixed =v10.
  (A second mixed run had v9 47.4 vs v10 45.2 -> mixed-field noise is ~+-2.8 at 600 tables.)
- v10 health check vs house zoo (300 tables, seed 137): 1st, 56.3 +- 4.4 pts/table.

## T2 result (v10): rank 4/8, 32.08 pts/table (b06 36.4 top). Places flat again.
- T2 sample hands (level 1 only) showed call-down losses vs value lines: JJ overpair called
  turn+river leads by a flop check-caller on a 4-straight board (-750); 77 called flop bet in
  a 3-bet pot vs the 3-bettor (-294).

## Patch before T3 -> v11 = 011-c4a79989 (ACTIVE for T3)
- LINE_ADJ=0.05: when facing a bet, +0.05 discount per earlier postflop street on which the
  same bettor bet/raised, +0.05 if the bettor made the last preflop raise in a 3-bet+ pot.
- DANGER=0.08: one-pair/two-pair strength -0.08 on turn/river boards with 4 to a straight
  (incl. ace-low) or 4 of a suit.
- Local tests neutral (self-play 32.1 vs v10 copies; mixed 47.6 vs v10 46.8, 400 tables) -
  house bots / own copies rarely run multi-street value lines, so the gain can't show locally.
- Extra checks: self-play v11 vs v10 copies 30.9 (600 tables; pooled 1000 tables ~31.4 vs 31.9
  avg), mixed 47.9 vs v10 47.5 (300 tables) -> locally neutral; kept v11.
- Note: an 800-table 8-bot mixed sim once exceeded the 5-min tool timeout under load; use
  <=400 tables per command in patch windows.

## T3 result (v11): rank 3/8, 32.81 pts/table (b06 34.9, b04 34.1). Weighted total rank 4.
- Sample hands again level-1 only. IMPORTANT: identify our seat by decision CPU time (ours
  ~15-120 us); seats with 200-450 us are another team's Monte Carlo bot. The T8o river bet I
  first blamed on us was that bot. Our real losses in the sample: KK called an A-turn bet in a
  multiway pot (-392); A9 flop c-bet + turn barrel called down by a second-pair station (-339).
- Opponents include sticky callers (TT called down vs AA for 1139).

## Patch before T4: kept v11 (011-c4a79989)
- BARREL 0.15 (fewer turn barrels): self-play 28.1 (avg 31.9), mixed 46.9 vs v11 47.6 -> worse.
- Bigger value bets (1.0 / 0.7 pot): self-play 28.7 -> worse.
- Smaller value bets (0.6 / 0.5 pot, tools/v/cSm): self-play 32.8, mixed 48.8 vs v11 48.9 -> neutral.
- tools/mkvar.py NAME BIG MID builds value-size variants without shell rm.
- v12 = 012-11df6101 (ACTIVE for T4): per-seat fold-to-bet tracking (any postflop bet at the
  table; prior 3/6); vs a single opponent with fold rate < FOLD_MIN=0.35, pure bluffs
  (s<0.45, draw_eq<0.15: c-bets, stabs, barrels) become checks. Value bets unchanged.
  Tests: self-play vs v11 copies 31.85 (neutral, copies aren't sticky); mixed 48.9 vs v11 46.3;
  station-heavy field 51.2 vs v11 copies 51.5/45.8. Pooled ~ +1.5 +- 2; low-risk exploit.
  Extra mixed run (seed 193, 400 tables): v12 50.9 vs v11 46.0 / v10 45.5 -> kept v12.
  Extra self-play vs v11 copies (seed 197): 31.6 (neutral, as expected).
- Next idea (untested): thin value bets (s 0.45-0.52) vs sticky opponents; more barrels vs
  opponents with fold rate > 0.6.

## T4 result (v12): rank 4/8, 32.04 (b06 34.8, b04 34.5). Weighted total rank 3.
- Every version scored ~32 in the real field (v8 32.0, v10 32.1, v11 32.8, v12 32.0).
- Places summed T1-T4 (of 4000): 1st 501, 2nd 512, 3rd 501, 4th 499, 5th 528, 6th 530,
  7th 477, 8th 452 -> we bust early less than average but don't convert to 1sts more.
- Leaders b04/b06 are a bit looser/more aggressive preflop (VPIP 23-26, PFR 18-20).

## Patch before T5 -> v13 = 013-2b413d9f (ACTIVE for T5)
- RESTEAL=0.12: facing a single standard open (<=3.5bb, no callers, raiser not all-in) from
  CO/BTN/SB (or any position when <=5 alive), with 10-25bb effective and pct<=0.12 -> shove.
  Self-play vs v12 copies: 33.2 (500 tables), 33.4 (1000 tables) vs avg 31.9 (+1.4 +- 1.7);
  mixed field 45.0 vs v12 46.7 (400 tables, noise +-3.4). tools/mkresteal.py NAME PCT.
  HU (25bb start): v13 52% vs v12 (80.8 vs 79.2). 3-handed: v13 68.2 vs v12 65.9/65.8 (900).
  RESTEAL=0.18 vs v13 copies: 33.0 (+1.1 +- 2.0) -> not adopted.
  Second mixed run (seed 219): v13 48.3 vs v12 47.3 / v11 48.9 -> mixed overall neutral.
  Open-shove cutoff 15bb instead of 13bb (tools/v/cP15): 32.3 vs v13 copies -> neutral, not adopted.
  Resteal from any position at <=6 alive (tools/v/cRS6): 31.9 vs v13 copies -> neutral, not adopted.
  HU vs maniac: v13 = v12 (maniac never min-opens, resteal never triggers).
  Field of versions (600 tables, seed 227): v10 37.8, v11 37.1, v13 35.7, v12 35.1, v8 34.9,
  v5 32.5, v3 32.1, mc 9.9 (+-2.6) -> v8+ all tied; kept v13.
- Next ideas: check T4 places/sample hands for later-level leaks (sample was level 1 only);
  light 3-bets vs late opens if opponents open wide; river bluffs if folds stay frequent.

## Status at end of build phase
- Active submission: 008-b88d2d85 (= bot/ now). Versions: 001 base, 002 +ICM premium,
  003 +street-based postflop discount, 004 +short-handed widening, 005 +VPIP steals/multiway,
  006 +weak turn/river call tightening/turn barrel, 007 +3-bet top 5%, 008 +late opens x1.15,
  F_CAP=8 (range widening vs frequent shovers).
- Final mixed-field check (1000 tables, seed 83): v8 47.6, v7 43.6, v5 42.1, v3 40.2 (+-2.2).
- Rejected at the end: OPEN_LATE=1.3 (+1.6 mixed, 0 in self-play), PUSH_ICM=1.05 (-2.9),
  halving HU postflop discounts (no gain), BARREL=0 / TB_PCT=0.035 in HU (no gain).
- HU sims are seed-sensitive: same seed gives correlated results; always confirm on a 2nd seed.
- Final health check, v8 vs house zoo (localsim, 300 tables, seed 101): 59.0 +- 4.4 pts/table
  (1st place; v1 scored ~48-50 there), 0 substitutions, p99 100 us.
- Tested last: river value-bet threshold s>=0.56 HU (tools/v/cRV): 47.97 vs v8 47.84 (700
  tables) -> no difference, not submitted.
- v8 vs 7 copies of v1 (localsim, 500 tables): 39.2 +- 3.0 pts/table (field average 31.9),
  1st of 8 -> the v2..v8 changes (mainly ICM premium) beat chip-EV-style bots.
- Ideas for patch rounds: check-raise monsters OOP; tune vs real tournament results (bust
  order / places) rather than house bots, which can't separate v5..v8 reliably.

## Evidence (local sims, tools/sim.py mixed field, tools/an4.py decision logs)
- Turn/river calls with s<0.45 won only 4-20% of the time -> tightened.
- Thin value bets (s>=0.5) and flop c-bets win; HU widening beat v3 54/46 in HU-only sims.
- v3..v6 are statistically tied in the house-bot field (+-2 pts at 1000 tables).

## Key parameters (top of agent.py)
- PUSH_ICM, ICM3, ICM4, STREET_ADJ, HU_OPEN, RAISED_ADJ, WEAK_TURN, WEAK_RIVER, BARREL.

## Tools
- tools/sim.py TABLES SEED ['{json settings overrides}'] name=path ... (house bot names ok)
  e.g. HU test: '{"seats":2,"starting_stack":8000,"points":[100,60],"blinds":[[160,320,0],...]}'
- tools/mkdbg.py builds an instrumented copy (tools/v/dbg) that logs decisions to tools/dbg.log.

## Known weaknesses
- Postflop is heuristic only; no check-raises, no river bluffs.
- Range estimates are guesses; push/call thresholds not solved.

## Next steps
- Use real tournament results to see if we bust early (too loose) or rarely win (too tight).
