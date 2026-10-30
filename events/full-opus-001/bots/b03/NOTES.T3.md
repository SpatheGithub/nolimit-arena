# Team notes (b03)

## Approach
Minimal and robust: rule-based NLHE bot, no simulation at decision time (p99 ~100 µs).
- `bot/_common.py` + `_common.json`: copied from kit house bots (evaluator `Ranker`, `Spot` parser,
  safe action builders, `features()` postflop strength 0..1, preflop percentile `pct`).
- `bot/eqr.json`: precomputed 169x100 table, equity of each preflop class vs top-X% range
  (range ordered by pct). Built by `tools/eqmat.py` (MC class-vs-class, 400+1600 boards/pair) +
  `tools/build_eqr.py`.
- Preflop:
  - unopened, eff <= 14bb: shove if modeled chip EV > 0.15bb (`shove_ev`: each opponent calls with
    top `call_width(e_bb)` = 1.6/e_bb (x1.6 heads-up), equity from eqr), else fold/check.
  - facing a shove / commit-size raise: call if eq vs `shove_width` (2.8/S_bb, x1.3 late) >= pot odds
    + 0.02 + 0.03*players behind.
  - facing a normal open with eff <= 28bb: re-shove if shove_ev > 0.5bb and pct <= 0.30.
  - otherwise v1 rules: open 2.5bb (+1bb/limper) with pct <= OPEN[players behind]; 3-bet pct<=3.5%;
    call pct <= 9% (or <= 16% if cheap, BB defend <= 30% vs min-raise).
- Postflop: `features()` strength s; bet 0.65 pot when s >= 0.60 (+0.04 per extra opp); semi-bluff
  draws 50%; c-bet heads-up flop as preflop raiser; facing bets call by s tiers vs pot odds;
  raise s >= 0.85.
- act() wrapped in try/except -> safe default (prints first error once).

## Versions
- 001-0744e4dc (v1): pct-threshold push/fold + TAG opens + simple postflop.
- 002-90d5b3f0 (v3): + EV-model shoves (<=14bb), equity-vs-range calls of shoves, re-shove over opens,
  per-seat PFR/VPIP model, open_mult 1.3, shove3 (calls vs 3-bet shoves by equity).
- 003-3a682acc (v4+hu_def): + postflop aggression model (aggmod), ICM-required equity for calling
  all-ins (3-6 alive), bigger value bets with s>=0.85, HU BB defend 45%.
- v5: + fold-to-bet per seat (ftb): c-bet bluff only if opp folds >= 42%, never vs < 30%; turn stab if >= 60%.
  ICM limited to <= 5 alive (timing).
- 004-165c4e12 (v7): v5 + isolation raises over limpers tightened (thr*0.6, max 15%).
- 006-eb178efe (v9): steal=2: behind<=4; open 50%/70%/100% when P(all behind fold to open) >0.5/0.6/0.72.
- 005-25275e23 (v8): + fold-to-open stat per seat (fto); late-position (<=3 behind) open threshold widened to 60%/85%
  when product of behind players' fold-to-open > 0.6/0.75 (prior 0.7 each).

## T1 result (v9, 006): rank 6/8, 30.18 pts. Places 1-8: 121,125,120,88,78,163,155,150.
- Weakness: early busts (6th-8th in 47% of tables vs 37.5% uniform); field VPIP 19-25%, ours 28%.
- Winner b02 VPIP 19 / PFR 14 (tightest).

## Patch window before T2
- Debug copy (versions/dbg) prints the decision that put our stack in when we bust ("BUST" lines).
  Found leak: calling 3-bet+/multi-raiser all-ins with A9o/KTo (shove3 path blended last raiser's PFR
  and ignored other committed opponents).
- 007-6937a1be (v13): deep=0.05 (facing a >30bb-deep shove: no PFR blend, +5% margin) and
  stackoff=0.10 (postflop, eff>25bb, call >=35% of stack with s<0.85 -> s-0.10).
  Field v1,v3,nit,v9,v1,v3,nit seed 101: v9 36.0 (bust 44.8%) -> v13 37.0 (bust 43.2%).
- 008-c2823f19 (v16): m3=1: in raises>=2 all-in spots, no PFR blend, range x0.7 if raises>=3, equity
  ^(1+0.8*multi) for every other opponent with > 1bb in. Same test: 39.3, bust 38.2% (best).
- Confirmed seed 303: v16 37.5 (bust 41.0%) vs v13 36.0 (bust 44.7%); no timeouts (max 385us).
- Next ideas: HU shove range may be too wide (EV model assumes HU caller 2.56/e_bb, Nash ~3.7/e_bb);
  bust log (versions/dbg) still shows 42o shoves HU at ~12bb. v18 (hu_cw=2.2): 39.9 vs v16 39.3 on seed
  101 (1st 215 vs 207) but 36.6 vs 37.5 on seed 303 -> net zero; not adopted.
- bot/ has hu_cw=1.6 (= v16 behaviour).
- 008 vs field of submissions 001-007 (400 tables, seed 404): 008 35.6 (1st), 007 35.4, 006 33.1,
  older 28.8-31.1; 008 bust6-8 32.8%. Newer versions rank above older ones (noise +-3.2).
- Tested, not adopted: cw=2.0 (36.5, same), steal=1 (35.8, worse), blend_bb=18 (identical).
- One timeout / one hang seen locally under heavy machine load (max 2.6ms); check_bot max ~110-260us.

## T2 result (v16, 008): rank 7/8, 29.32 pts. Places: 104,137,119,90,98,141,162,148 (bust6-8 45%).
- Same profile as T1: we are the loosest bot (VPIP 28 / PFR 22; field 19-24 / 14-19) and bust too often.
- Local gains vs my own bots did not transfer: my versions are a poor proxy for the real field.

## Patch window before T3
- ICM insight (kit/icm.py, standard payouts): an all-in flip for the whole stack with 8 equal stacks needs
  62% equity (not 50%); bubble factor ~1.3-1.85 at 8 players, 1.1-1.6 at 6, ~1.1-1.3 at 4, ~1.05 at 3.
  Bot only used exact ICM for <=5 players and only for calls -> took chip-EV-neutral all-ins at 6-8 players.
- 009-25bf25a4 (v19): icmx=1.0: bubble factor BF = 1 + BF_A[k]*min(1, e/my_stack),
  BF_A = {8:.65, 7:.55, 6:.45, 5:.33, 4:.2, 3:.06}. Used (a) in need_icm for k>=6 calls:
  need = BF*cn/(BF*cn + 1 - cn); (b) in shove_ev: loss term x BF for every caller (all k>=3).
  Local field seed 101: 39.5 (v16 39.3), bust6-8 34.9% (v16 38.2%), top3 48.3% (46.7%).
- v19 vs 7x v16 (300 tables, seed 111): 33.7 (baseline 31.9), bust6-8 33%, VPIP 23 / PFR 17.
- Local runs under load show rare single timeouts/hangs (max 1.4-2.6 ms); referee T1/T2: 0 subs, max <0.8 ms.
- v19 seed 303 (1000 tables): 39.2 vs v16 37.5; bust6-8 33.9% vs 41.0%. Consistent improvement.
- 009 vs submissions 002-008 (400 tables, seed 505): 32.8 (4th; all 28.6-34.4 within +-3.2 noise);
  profile: fewer 1sts (10.8%), many 3rd/4th, bust6-8 only 28.7%, VPIP 25 / PFR 18.
- v20 (icmpost=1: BF also on postflop calls >= 35% of stack): 34.0 vs v19 33.7 same seed (noise);
  not submitted; code kept with icmpost=0.
- Next ideas: if T3 still busts >42% -> raise BF_A further or add BF to postflop all-in calls;
  if we blind out (many 4th-5th) -> lower icmx to ~0.7.
- Machine is heavily loaded in patch windows: a 1000-table run can take >3 min; keep runs <= 500 tables.

## Testing
- `tools/sim.py --me versions/X ...` = localsim with selectable hero. `tools/mkvar.py name k=v` makes
  a parameter variant in versions/. `tools/runexp.sh seed tables names...` appends to tools/exp.log.
- Field used: v1 x3, nit, montecarlo, threshold, maniac; later v1 x2, M0, nit, maniac, montecarlo, pot_odds.
- NOISE: 400 tables gives +-3.4 (95%); near-identical bots differed by 3 points. 1000 tables +-2.1.
  Only differences > ~3 points are detectable; most tweaks are below that.
- Results (seed 31, 1000 tables, mixed field v1,M0,nit,v1,maniac,montecarlo,pot_odds):
  v3 41.8, v1 43.5, v4 45.9, X1(evpush=0) 45.5, X0(evpush=1) 45.0, v5(+ftb) 46.2, v6(posw=.15) 41.7.
  v4 vs 7x v3: 33.15 (baseline 31.9).
- posw (wider assumed calls vs late-position shoves -> tighter late shoves) hurt: reverted to 0.
- v9 (steal=2) 44.9 (mixed), 35.7 (v3 field) -> submitted as 006-eb178efe.
- v10 (ftoshove=1) 45.4 (mixed), 34.4 (v3 field): wash, not submitted (code kept, ftoshove=0).
- v11 (steal=3: behind<=5, open 50/70/100% at pf>0.45/0.55/0.65): 47.9 (mixed), 34.6 (v3 field).
  Ambiguous (mixed +3, v3 field -1.1); not submitted. Re-test seed 71 v3 field: v11 34.04 vs v9 33.98
  (tie) -> kept v9.
- v12 (sdef=1: vs openers with PFR>30% BB defend 50%, cheap-call 28%): 30.5 vs 7x v9 (baseline 31.9)
  -> no help; not submitted.
- 006 vs field of earlier submissions 001-005 (400 tables, seed 81): 006 33.67 (1st), others 29.4-32.5;
  all within +-3.2 noise. Max decision time seen 518 us (busy machine), 0 substitutions.
- 006 vs house zoo (300 tables, seed 91): 57.3 (1st; nit 46.5, checkfold 37.2, rest <= 28).
  v1 scored 56.1 vs zoo at build start: zoo no longer separates versions; use v3/mixed fields.
- bot/ = v19 (icmx=1.0); active submission 009-25bf25a4.
- v8 44.8 (mixed), 34.0 (v3 field: steals pay vs TAG fields).
- v7 44.4 (mixed), 32.8 (v3 field); v7b (cw=1.25) 43.3; v7c (open_mult=1.6) 44.8. All noise-level.
- Shover/station field (v1,shover,v3,station,v3,nit,shover): ~45-49 for us, shovers ~13, station ~5.

## Key parameters
See `P` dict at the top of bot/agent.py.

## Known weaknesses
- Opponent ranges are prior guesses blended with simple per-seat stats (PFR, VPIP, postflop
  aggression, fold-to-bet, fold-to-open); no showdown-based range learning.
- Non-all-in 3-bets deep: we fold all but top ~3.5% (exploitable by 3-bet-happy bots).
- HU deep-stack play is simple (SB opens 55%, BB defends 45% vs small opens).
- Postflop is category-based; no board-texture-aware bluffing, no river thin value logic.

## Next steps (patch windows)
- Use tournament results: if we bust early often -> tighten calls; if we blind out -> widen shoves.
- ftoshove (use fold-to-open to scale assumed shove-call widths): v10 = wash.
- Steal-defense (sdef) tested: no gain vs 7x v9. Re-shove <=28bb already adapts to loose openers.
- Re-test steal=3 (v11) on more seeds/fields before adopting; use tournament results to pick field.
- Consider fold-to-3bet stat to widen 3-bet bluffs vs openers who over-fold.
- Always run kit/check_bot.py then kit/submit.py; tools/runexp2.sh for 1000-table A/B (noise +-2).
