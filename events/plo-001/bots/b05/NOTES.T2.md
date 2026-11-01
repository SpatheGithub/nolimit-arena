# Team notes (b05, PLO)

## Submissions
- 001-3b3a0564: first version. 002-6a5757e3: tighter range model, nut-weighted draws, pair weights.
- 003-792fb6a9: + ICM risk premium, + short-handed widening (big gain: 35.0 vs 31.9 baseline vs v2 copies).
- 005-8f8a1cd9 (active): v4 with HU value-bet threshold .55 -> .52 (thinner value vs stations).
  Mixed seed 81: 49.8 (v4 48.0); zoo seed 11: 52.2 (v4 50.7); zoo seed 21: 56.8 (v4 58.3);
  vs 7x v4: 31.5. Net: v5 ~= v4 within noise. Kept v5 active.
- 004-a247b08d: + current-street callers modeled (f=.45), c-bet bluff freq from fold-to-bet,
  heads-up value threshold .50 and HU bluffs. vs 7x montecarlo 62.0 (v3: 57.7), neutral elsewhere.

## Approach
- `bot/evaluator.py`: numpy-vectorised exact Omaha evaluator (2 hole + 3 board). Lookup tables built at
  import (unsuited rank-key sum -> value, 26 MB int32; suited 13-bit mask -> flush/SF value).
  Verified 0 mismatches vs house Ranker on 3000 random deals. act() p99 ~300us on busy machine.
- Postflop: `board_strength` enumerates every opponent 2-card combo from unseen cards (card removal
  included) -> fraction `beat` of combos beating us now. q = 1-(1-beat)^5.5 = P(random 4-card hand
  beats us). Range model: bettor holds top f of hands (f by street .32/.25/.20, raise x0.35, scaled by
  their postflop aggression stat, bet size, and x1.5 HU / x1.25 3-handed) -> P(beat)=w*min(1,q/f)+(1-w)*q.
  Callers this street f=.45, earlier callers/aggressors f=.65, checkers random.
  Draws: exact enumeration of next card (`improve_outs`), outs weighted by nut-ness.
  eq = P(not beaten)*(1-risk) + P(beaten)*draw_eq, risk .20 flop / .10 turn.
- Betting: bet .75 pot (pot if eq>=.8) if eq>=.52 HU / .50 multiway (.50 on HU table); semi-bluff draws;
  c-bet bluff prob clip((ftb-.2)*1.8, 0, .75). Facing bet: raise pot if eq>=.72, call if
  eq >= pot odds + .03 (+.03 if big) + ICM margin.
- ICM: break-even for bust-or-double is ~.62 with 5-8 players under this payout table (computed with
  kit/icm.py). ICM_PREM {3:.05,4:.08,5-7:.09,8:.10} scaled by stack fraction at risk and cover.
- Preflop: heuristic score (`bot/preflop.py`) -> percentile (30k random hands). Open thresholds by players
  behind (.14 UTG .. .40 SB), all thresholds x wm = {2:2.2, 3:1.6, 4:1.3, 5:1.12} by players alive.
  3-bet top ~3.5%; 4-bet only AA. <=12bb: raise-max ranges; commit decisions by approx equity vs
  raiser range (PFR stat).
- Opponent stats per seat (vpip, pfr, postflop aggression, fold-to-bet) from observe() histories.

## Testing
- `tools/sim.py <zoo|name/path,...> <tables> <seed> [botdir]` prints place distribution (needs
  `timeout` param >120s for 600+ tables). Noise is about +-2 points at 1000 tables (self-play).
- Mixed field used: 003,montecarlo,pot_odds,nit,003,minraiser,003.
- Things that tested neutral/worse: wider wm (2.6/1.9/1.45), pot-size value bets at eq>=.65 (worse),
  preflop commit margin -0.01 (30.6) or +0.06 (31.6) vs +0.03, postflop short-handed f mult
  {2:1.75,3:1.4,4:1.2} (31.3), postflop raise threshold .68 (31.1), multiway vt .47 (mixed 49.0 vs v5 49.8),
  narrower wm at 4-5 players {4:1.15,5:1.05} (zoo seed 21: 55.7 vs v5 56.8). v4 seems at a local optimum within +-2 noise.
- v4 results: mixed field seed 81 48.0 (v3 47.2); zoo seed 11 50.7 (v3 51.4); 7x montecarlo 62.0.
- DEBUG flag in agent.py prints bust hands (must be False when submitting).

## T1 result (v5 005-8f8a1cd9)
- Rank 1/8, 36.26 +-2.0 (b06 34.8, b01 34.5 overlap). Places 158/113/157/157/131/102/98/84.
  VPIP 23% PFR 17%; field VPIP 21-37%, PFR 14-21% (TAG-ish pot-raisers). 1 timeout in 115k (max
  1366us; first-call warm-up measured 157us, so likely machine hiccup).
- sample_hands.json only has first 10 hands of 4 tables: little info.

## Patch window before T2: experiments (all vs 7x v5, seed 111, 1000 tables; baseline 31.9)
- Danger-board fix (opp raise on paired board w/ our hand < boat, or 3-flush board w/ hand < flush:
  f x0.5): 31.95 self, mixed seed 81 48.3 (v5 49.8). Not adopted; code in tools/agent_dangerfix.py.txt.
- ICM_PREM 3/4 players .03/.05: 31.5; .07/.10: 31.8. 3-bet base .05: 31.96. None adopted.
- Decision: keep v5 for T2 (no measurable gain from any change).

## Known weaknesses
- Preflop scoring heuristic, not equity based. Heads-up vs maniac we usually finish 2nd (short stack).
- Range model crude; no river bluffs; no check-raise.

## Bust-hand review of v5 (debug copy, mixed field, 40 tables) -> patch ideas
- Trips on paired board (AcAh2d flop, we hold A-K) raised, then called a re-raise vs a full house
  (pnb still .63). Idea: on paired boards, raises/re-raises are boat-heavy -> f x0.5 for our hands
  below full house.
- Medium hands (pct .25-.5) committing preflop when eff stack <=12bb vs a short opponent, then
  stacking off on the flop with pair+draw (eq .41-.61). Idea: in commit mode use k and f tighter
  when we are the covering big stack; avoid flop shoves with eq < .45 when called is likely.
- AA vs Tc Kc flush runouts: normal variance.

## Next steps
- Precompute real preflop equities (numpy MC over 16k canonical hands) and replace heuristic.
- Use opponent showdown info; better multiway sizing; late-stage push/fold tables.
