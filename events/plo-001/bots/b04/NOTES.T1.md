# Team notes (b04, PLO 8-max SNG)

## Approach
- `bot/agent.py`, single file, tables built at import (~0.2 s):
  - 5-card rank-multiset table (RK key sums, like engine fasteval) + flush table by 13-bit mask.
    Hero PLO value = max over 6 hole pairs x C(board,3) triples. Verified identical ordering to engine.
  - `analyze()`: exact fraction of opponent 2-card combos (rank pairs weighted by available cards,
    plus suited flush combos) that beat / tie our made hand -> q = 1 - p_beat - p_tie/2.
  - Equity vs a range of "tightness" k: q^(6 * n_opp * k) (6 = two-card combos in a 4-card hand),
    times a board-texture vulnerability factor on flop/turn, plus draw equity (straight outs via
    5-rank windows, flush draws, nut flag).
  - k rises with bet size (2*bet/pot), raises this street, and the opponent's earlier actions this hand
    (H_BET 0.8 per postflop bet/raise, H_CALL 0.35 per postflop call, H_PF 0.4 per preflop raise).
    Value bets are judged vs the calling range (K_CALL=2 + hist).
  - Opponent aggression stats per seat (within a table only) scale k (maniacs -> looser calls).
  - Preflop: heuristic 4-card score (pairs, suits w/ high-card bonus, connectedness, danglers) ->
    percentile via 12k random hands. Position-based pot-raise opens; 3-bet ~top 3.5%; vs 3-bet+ continue
    with AA / top ~1% (call cheap top 3.5%).
  - Short stack (<=12bb): commit mode (pot-raise = "allin").
  - ICM-ish: risk premium on calls risking >35% of stack (bigger if we'd bust).

## Versions
- v1 001-8167d767: first version.
- v3 002-3473c3a1: range-aware equity (history k), texture vulnerability, tight 4-bet range.
  A/B (500 tables, seed 11, field v1x3+montecarlo,nit,pot_odds,minraiser): v3 45.1 vs v1 43.4; busts down.

- v6 003-85cd93eb: + HU/3-handed wide ranges (HU_SHOVE .80, HU_CALL .60, HU_OPEN .50, HU_LIMP .85, HU_DEF .65),
  fold-to-bet tracking -> adaptive c-bets/bluffs, steal widening vs tight blinds, no low-SPR shove on river,
  4-bet calls only AA / top 2% cheap. vs 7x v3: 35.2 (fair 31.9).
- v9 004-8c0d5ef7: + value-bet thinner vs non-folders (K_CALL -0.5 if fold rate <.3), cheap-raise defense x1.35,
  IP stabs vs folders. Paired 1000-table test equal to v6 (44.0).
- v11: + preflop call vs all-in shoves on pot odds (eq_est = .62 - .25*pct, adj by shover vpip, multiway,
  ICM risk). Paired test 45.3 vs 44.0; vs 7x v9: 34.8 (fair 31.9).

## Tried and rejected
- ICM-exact bust premiums (+.10): 42.4 vs 44.0 (too tight vs maniacs). Kept .07-.04.
- Preflop "pot-odds commit" for 35%+ stack calls with eq_est .56-.45*pct: more busts, worse.

- v12 (not submitted): aggression stat postflop-only + pfr-based preflop loose read + 5-bet only AA.
  vs 7x v11: 31.6 (seed 71), 31.8 vs baseline 33.3 (seed 81); mixed field 44.0 vs 45.3. Not better -> kept v11.
- K_CALL 1.6 / 2.5: 31.0 / 30.6 vs v11 copies (seed 71) -> keep 2.0.
- Big-stack late-game open widening x1.25: 30.4 (seed 71) -> no gain.
- CBET 0.25 vs 0.40: 32.7 vs 33.3 baseline (seed 81) -> keep 0.40.

- Rundown bonus 1.5 -> 3.0 (JT98ds 6.4% -> 4.4%): 32.0 vs 33.3 baseline (seed 81) -> no gain.
- Wider HU (SHOVE .9, CALL .72, OPEN .6, DEF .78): 33.0 vs 33.3 (seed 81) -> no gain.

## FINAL (end of build): active submission 005-e6298178 = versions/v11 = bot/
- v11 vs house zoo (localsim 400 tables, seed 5): 57.9 (nit 46.1, checkfold 40.8); 0 substitutions, max 257 us.
- Paired-test baseline for patch windows: v11 vs 7x v11, 900 tables, seed 81 -> 33.26.
- v11 vs field of earlier submissions 001-004 (localsim 600 tables, seed 9): 34.3 (2nd of 8); v1 copies
  27.8-29.7, 002 ~31, 003 33-35.7, 004 32.5.
- All-in rule: count only players who already called the shove (-.10 each), -.03 per player yet to act:
  32.7 vs 33.3 baseline -> not submitted (preflop all-ins are rare in PLO; effect within noise).
- Lower bust premiums (.04-.02): 33.4 vs 33.3 baseline -> flat. With +.10 being worse in the maniac field,
  RISK_BUST looks flat-to-optimal at .07-.04; leave it unless real results show early busts.
- Opening ranges x1.15 wider (non-HU): 31.9 vs 33.3 baseline -> worse.
- Opening ranges x0.88 tighter: 31.6 vs 33.3 -> also worse. Current open widths look locally optimal.
- CBET 0.55: 33.1 vs 33.3 -> flat (0.25 was 32.7). Keep 0.40.
- Final check: v11 vs earlier submissions 001-004 (400 tables, seed 99): 35.3, ranked 1st of 8; 0 substitutions.

## Testing tools
- tools/sim.py --me bot --opponents versions/v9,... (place distribution); tools/logsim.py prints biggest losing hands.
- Noise: +-3 pts at 500 tables, +-2 at 1000. Paired seeds help a little.

## Findings
- House-bot zoo: nit/checkfold score ~40 by surviving -> survival is worth a lot; early busts hurt.
- Biggest leaks seen in logs: stacking off one pair / top two / sets vs multi-street aggression; 4-bet wars
  with non-AA hands.

## Known weaknesses / next steps
- aggr() counts preflop raises, so raise-or-fold TAGs look "aggressive" (>0.45) and we loosen calls vs
  their postflop bets. Fixing it (v12) tested neutral/slightly worse vs our own bluffing copies; revisit if
  real opponents prove straightforward (check hand logs in patch windows: do they bluff?).
- Preflop score is heuristic, not equity-based (JT98ds ranked ~6%, probably too low).
- No range modelling beyond the k exponent; draw equity crude (no redraw / reverse-implied adjustments).
- Tables never reached the 200-hand cap in sims; cap-ICM logic untested.
- Patch-window ideas: read tournament results for bust patterns; tune RISK_BUST, HU_* params, opening
  widths per position; consider equity-based preflop table (MC vs random, offline) if time.
