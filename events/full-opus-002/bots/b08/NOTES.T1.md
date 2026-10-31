# Team notes (b08)

## Submissions
- 001 baseline; 002 +ICM on postflop big calls; 003 +opponent reads (shove freq, call-vs-allin, fold-to-bet)
  and EV-based bluffing; 004 +exact ICM (<=4 alive), ICM margin 2pts when >=5 alive, opens x0.85;
- 005-4412fcfa (active): + wider short-handed opens (HU 80%, 3-handed BTN 45%), postflop calling fix
  (DISC_MULT=1.5 on the bet-narrowing discount; the "cheap draw call" branch now needs discounted equity).

## Approach
- Precomputed (tools/pre_*.py): evaluator lookup tables (evtab.pkl, copied from kit fasteval),
  169x169 preflop HU equity matrix (pf_eq.npy, MC 1500/pair), equity vs k random hands (pf_mw.npy),
  ICM table icm_tab.npy: f(n players, my chip share) with others equal, exact kit icm.
- Preflop: hand percentile ranking; EQR[class, top-x%] equity vs ranges (matrix product at import).
  - Unopened, eff <= 18bb: shove iff ICM EV(shove) - ICM(fold) > margin (2 pts when >=5 alive, else 0).
    Callers' ranges: 0.06 + 2/shove_bb (BB), x0.65 others, scaled by vpip, blended with observed
    call-vs-allin frequency. <=4 alive: exact ICM on the real stack vector (icm_exact, ~9us).
  - Deeper: open ranges by # players behind (x0.85), 2.5bb; 3bet strong vs raiser range; set-mine.
  - Facing all-in: ICM call check (call_ok) with equity vs estimated shove range (observed first-in
    shove frequency when <=20bb, prior by depth 45/32/22/12%).
- Postflop: Monte Carlo equity (budget 0.45ms, sd ~0.03) vs opponents' preflop ranges.
  Facing bets: equity minus discount (size/street/opp aggression, x1.5); big calls (>=35% stack) and
  all-ins use the ICM call check. Value bet >=0.55 eq; bluffs/c-bets when fold-equity EV beats checking
  (per-opponent fold-to-bet read).

## Findings
- Tables almost never reach the 200-hand cap; place = elimination order. Survival is worth a lot
  (house nit takes 2nd/3rd ~60% by folding). ICM at 8 equal stacks needs ~73% equity to call off.
- Leak analysis (tools/vdbg = instrumented copy logging tag/payoff per hand to $DBG_OUT):
  all all-in categories are chip-positive; postflop bets/raises strongly positive; postflop CALLS were
  the big leak (~-1250bb/250 tables) -> fixed in 005 (now ~-700bb). Small 3bets at 6-8 alive slightly negative.
- Parameter tests vs copies are noisy (+-2.5 pts at 700 tables); use paired seeds (--me tools/vX same --seed).
  Blending ICM toward chip-EV (W_LIN) tested worse; extra ICM margin slightly better.

## Tools
- tools/sim.py --me <dir> --opp a,b,... --tables N --seed S : prints place distribution per bot.
- tools/probe2.py : shove-range widths in synthetic spots. tools/v1..v5 snapshots.

## Known weaknesses / next steps
- Postflop calls still negative: try DISC_MULT 2.0 (tools/vD2 ready; its paired test vs v5 on seed 73
  was killed by timeouts on the loaded machine, so it is untested), or model multi-barrel range narrowing.
- Paired evidence for 005: seed 71, 450 tables: 005 46.1 vs 004 44.9 as "me"; seed 61, 250 tables: ~equal.
- Late in the window the shared machine was overloaded (sims and even `sleep` timed out): run single
  sims with timeout <= 200s and fewer tables.
- 3bet pots deep (6-8 alive) lose small; BB defence check-folds a lot.
- ICM table assumes equal other stacks for >=5 alive.
