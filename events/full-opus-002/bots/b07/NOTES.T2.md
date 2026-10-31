# Team b07 notes

## Approach
- `bot/agent.py` + copied house helpers `bot/_common.py/.json` (Ranker = engine-identical hand values, preflop pct table, postflop `features()` strength/outs).
- `bot/pfeq.json`: 169x169 preflop all-in equity matrix (tools/precompute_pf.py, 1500 samples per matchup via kit fasteval).
  At import, builds RE[c][k] = equity of class c vs top-k% range (ordered by equity vs random).
- Preflop:
  - Unopened, eff <= P["pf_bb"]=14 BB: shove iff EV > 0. 5-8 players: chip EV with ICM risk premium on losses;
    3-4 players: exact ICM (icm_small, Harville recursion, matches kit/icm.py, ~25us/call).
    Callers = all opponents still in (behind + limpers), each calling with top q%: q prior 0.10 + 0.9/effBB, scaled by
    VPIP, capped by (1 - observed fold-to-raise)*1.1+0.02, blended with observed call-vs-preflop-all-in rate.
  - lam_risk = lam_full(n_alive) * (risk / my stack) * P["icm"] (lam_full from exact ICM even-stack break-even:
    n=3 .33, 4 .53, 5+ .6). P["icm"]=0.5.
  - Deeper: open-raise by position threshold on pct (UTG 12% .. SB 42%; HU 72%; 3-handed ~50%), scaled by fold-to-raise
    of players behind. Steal-EV override (P["steal"]): open any hand (pct<0.97) if prod(fold-to-raise behind)*pot -
    (1-p)*0.55*raise > 0.2bb, once every player behind has faced >=4 raises.
  - Facing raise: raiser width from observed PFR. Deep all-ins (>25bb, P["deep"]): width 0.035 (>45bb) / 0.06,
    widened only by the seat's observed shove rate*1.5. Commit spots: call/shove by EV (exact ICM heads-up calls at 3-4 left).
    <= 22bb: resteal shove by EV. Deep: 3-bet premium, flat by odds+implied.
- Postflop: features() strength + outs -> equity proxy; value bet >=0.72 (bigger vs stations), c-bet, thin bets,
  semi-bluffs; bluff freq scaled by opponents' fold-to-bet. Facing bets: penalty by bet size and bettor aggression.
- Opp stats per seat (observe): hands, vpip, pfr, preflop all-ins, fold-to-raise, faced/called all-ins, postflop actions.

## Tools
- tools/ab.py TABLES SEED name=path,... (8 entries; prints places% histogram); tools/mkvar.py NAME '{json}' -> tools/var_NAME
- tools/diag (chip results by decision line), tools/strict (no exception guard; 0 errors found).

## Results
- T1 (sub 005): 30.01, rank 7/8 (all teams 29.3-34.8, overlapping CIs). Places: 1st 11%, 7th+8th 29% (early busts).
  Field is TAG-ish: VPIP 19-25%, PFR 12-18%. 1 timeout in 109k decisions (max 1.7ms, machine noise).
- Local: steal/call-cap change +4 vs 004 in nit-heavy field, +1 in loose field. Deep-shove fix +0.6/+1.1 vs 005 (noise).
  Variants callq0.75+open1.15 and pen1.3: no difference. 006 vs 005 in loose field (maniac/minraiser/random/nit):
  42.4 vs 43.0 (noise) -> no regression.
- Patch window 1 screens (2 copies each, 1000 tables, own-version field), none confirmed better than 006:
  pf_bb 12 (+2.2 then -0.5 on re-run), resteal_bb 26 (+1.5, +0.2), both (+0.2), icm 1.0 (-0.2),
  cbet 0.5 / 1.0 and pen 0.7 (all +1.7..2.1 in one run where 006 itself scored low - opposite cbet changes both
  "helping" = noise). Kept 006. Follow-up: resteal_bb 26 + cbet 1.0 combined, 4 copies vs 4 copies of 006,
  1000 tables: 31.8 vs 31.9 -> no gain; dropped. Street-dependent bet penalty (x1.15 turn, x1.3 river;
  tools/var_strp): 32.2 vs 31.6 (4v4, 1000 tables) -> +0.6, noise; not submitted. Could matter more vs value-heavy
  real bots than in self-play - candidate to re-test against T2 results. Replication (seed 137): 31.6 vs 32.2 ->
  pooled effect ~0 in self-play.
- Sanity (localsim, 800 tables, 006 vs 005/004/003 + nit/mc/thr/po): 006 46.9, 005 45.8, 004 42.8, 003 41.7,
  nit 34.8 -> each version >= its predecessor; 0 substitutions, max 782us. Parameter tuning in self-play looks exhausted; next gains need
  structural changes (e.g. better postflop equity vs range, or opponent-specific postflop reads).
- Patch-window diag (tools/diag, TAG-like field of own versions): every all-in line profitable (open shove +89/hand,
  call all-in +446 at 52% wins, shove-over +421, exact-ICM call +878); big losses are just variance of good all-ins.

## Submissions
- 001 first; 002 resteal+icm; 003 bugfixes/ftb/HU opens; 004 all-in call read; 005 exact ICM 3-4 left + fold-rate
  steals/call cap; 006-c23b47da deep all-in range tightened (T2).

## Known weaknesses / next
- Early busts: likely deep postflop stack-offs with one pair vs TAG value ranges; consider tighter calls of big turn/river bets.
- Postflop strength heuristic, not equity vs range. Self-play A/B can't resolve < ~2 points.
