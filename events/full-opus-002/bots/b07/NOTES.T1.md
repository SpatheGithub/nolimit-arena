# Team b07 notes

## Approach
- `bot/agent.py` + copied house helpers `bot/_common.py/.json` (Ranker = engine-identical hand values, preflop pct table, postflop `features()` strength/outs).
- `bot/pfeq.json`: 169x169 preflop all-in equity matrix (tools/precompute_pf.py, 1500 samples per matchup via kit fasteval).
  At import, builds RE[c][k] = equity of class c vs top-k% range (ordered by equity vs random).
- Preflop:
  - Unopened, eff <= P["pf_bb"]=14 BB: shove iff chip EV (with ICM risk premium on losses) > 0.
    EV sums over all opponents still in (behind + limpers), each calling with top q%: q prior from stack depth
    (0.10 + 0.9/effBB), scaled by observed VPIP, then blended with the seat's observed call-vs-preflop-all-in rate.
  - ICM risk premium `lam_risk`: lam_full(n_alive) * (risk / my stack) * P["icm"], lam_full calibrated with exact
    kit/icm.py break-even for even-stack all-ins (n=3: .33, 4: .53, 5+: .6). P["icm"]=0.5 (hedge; tests inconclusive).
  - Deeper: open-raise by position threshold on pct (UTG 12% .. SB 42%; HU 72%; 3-handed ~50%), scaled by observed
    fold-to-raise of players behind. 2.3bb (<25bb) / 2.6bb, SB 3bb, +1bb per limper.
  - Facing raise: raiser width from observed PFR (all-ins wider when short). Commit spots: call/shove by EV.
    <= 22bb: resteal shove by EV (raiser calls with top 40% of range). Deep: 3-bet premium (eq>=0.6 vs range), flat by odds+implied.
- Postflop: features() strength + outs -> equity proxy (2-card draw equity on flop only when all-in), multiway exponent.
  Value bet >=0.72 (bigger vs stations), c-bet as PF aggressor, thin bet >=0.55 HU, semi-bluff 8+ outs; bluff freq scaled
  by opponents' fold-to-bet. Facing bets: penalty by bet size and bettor's postflop aggression.
- Opp stats per seat (observe): hands, vpip, pfr, fold-to-raise, faced/called preflop all-ins, postflop bets/calls/checks/folds.

## Key parameters (P dict in agent.py)
icm, lam (legacy), pf_bb, open (open-range mult), call_m, pen (postflop bet-respect), cbet, callq, resteal_bb, rs_margin.

## Tools
- tools/ab.py TABLES SEED name=path,...  (8 entries, own field); tools/mkvar.py NAME '{json overrides}' -> tools/var_NAME
- tools/diag: instrumented copy logging chip results by decision line to $TMPDIR/diag.jsonl
- tools/strict: copy without the exception guard (checks for hidden errors) - 0 errors.

## Test results (noise ~ +-2.5 per entry at 800-1000 tables; most param tweaks indistinguishable)
- v1 vs zoo: 48.7 (nit 48.6). v3 vs zoo: 55.1 (nit 47.1).
- Variants: tighter opens / pf_bb 18 looked worse (-3); looser / icm 1.0 / pen tweaks ~ equal.

## Submissions
- 001-7ff3034b first; 002-9376012c resteal+icm0.5; 003-5a848478 bugfixes (stale cbet flag, limpers as callers, draw eq), ftb read, HU opens.
- 004: per-seat preflop all-in call-rate read.

## Known weaknesses
- Postflop strength is heuristic, not real equity vs range; river calls slightly losing.
- ICM only approximated (no exact ICM at decision time - too slow for 8 players).
- Self-play-heavy A/B tests can't separate small changes; real field unknown.

## Next steps
- Use T1 results: if busting early, raise icm to 1.0 / tighten calls; if losing chips postflop, raise pen.
- Exact ICM for <=4 players (16 masks, cheap) in call/shove decisions.
