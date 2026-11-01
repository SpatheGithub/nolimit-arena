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

## T2 result (v5 005-8f8a1cd9)
- Rank 1/8, 36.60 +-2.0 (b06 35.3 next). Places 149/127/172/160/121/96/86/89, 0 timeouts.
  Field VPIP 19-28%, PFR 13-20%. Weighted total after T2: 109.47 (rank 1).
- Pattern: 3rd/4th finishes (172/160) more common than 1st/2nd -> converting short-handed is the
  candidate weakness.

## Patch window before T3: experiment (copy in $TMPDIR, bot/ untouched)
- Looser short-handed commit calls (n_alive<=4: margin 0 instead of .03, ICM premium x0.5):
  vs 7x v5 seeds 121/131: 32.46, 33.53 (baseline 31.875, ~+1.1); mixed seed 81: 46.8 (v5 49.8).
  Conflicting -> not adopted.
- Thinner postflop value bets at n_alive<=4 and SPR<=1.5 (vt .45): vs 7x v5 seed 121: 32.39;
  mixed seed 81: 45.6 (v5 49.8). Rejected. Short-handed loosening helps a bit in self-play but
  hurts vs mixed styles -> v5 late-stage balance looks right.
- Tighter short-handed commit calls (n_alive<=4 margin .06): mixed seed 81: 47.7 (v5 49.8). Rejected.
- Postflop raise threshold .76 (fewer raise/stack-offs): mixed seed 81: 48.9. Rejected (neutral).
- Calibration: v5 on mixed seed 91 = 47.5 (seed 81 = 49.8), so seed-81 v5 baseline is on the high
  side; compare variants on >=2 seeds next time (seed noise ~+-2.9 per 600 tables).
  Kept v5 for T3.

## T3 result (v5 005-8f8a1cd9)
- Rank 1/8, 35.54 +-2.0; b08 rose to 34.5 (was 24.4 in T1, 30.9 in T2) -> field adapting.
  Places 143/122/151/176/126/112/94/76. Weighted total 216.09 (rank 1). Our aggression 2.9
  (T1 3.6, T2 3.5): opponents may be raising/calling more vs our bets.
- 1 substitution = hang (wall 84 ms, CPU 540 us): machine scheduling, not our code.
- Decision for T4: keep v5 (3/3 wins; all tested variants neutral or worse).

## KEY FINDING (patch window before T4): v5 is exploitable by hyper-aggressive opponents
- LAG variant of v5 (vt .42/.45, c-bet/barrel 70% as pf raiser on all streets, bluff 60% when
  checked to, raise if eq>=.62 or 12% random on flop/turn). v5 vs 7x LAG (600t seed 141): 26.98
  (baseline 31.9; LAGs 31-34). Only 44 firsts.
- Tried: aggr multiplier cap 2.2->3.0 and w=.55 for a>=.65: 27.33 (no help).
- Bust hands vs LAG look like normal gambles -> loss is likely chip bleed: folding to frequent
  bets/raises in small/medium pots (our bets with eq>=.52 get raised by random raisers; we fold).
- Next window: track per-opponent raise-vs-our-bet frequency and bet-when-checked-to frequency;
  widen calls/re-raises vs high-frequency raisers; consider check-raising strong hands vs
  frequent bettors; test vs LAG field AND v5 copies AND mixed (2 seeds each).
- LAG test bot recipe: copy bot/ to $TMPDIR/lag and apply the 4 replacements above.
- Also tried: raise-range factor .35 -> .6 when opp aggr>=.55: 27.39 (no help). Place
  distributions nearly identical across all 3 variants -> those code paths rarely trigger.
  Next: print LAG opponents' aggr()/fold_to_bet() values and our fold-when-checked-then-bet rate;
  suspect bleed = we check (eq<vt) then fold to their 60% bluffs. Possible fix: bluff-catch more
  when opponent's bet-when-checked-to frequency is high (new stat), or bet more ourselves.
- DIAGNOSIS (debug copy, stats printed at hands 30/60 vs LAG field): LAG opponents measure
  aggr() only .35-.64 (mostly .40-.55; v5 itself .25-.46) because the prior (.35, weight 8)
  damps small samples -> thresholds a>=.55/.65 rarely fire. OUR fold_to_bet is .45-.61: we fold
  to ~half of bets, which 60%-bluffers exploit. Next fix to test: (1) weaker aggr prior (weight
  4) and multiplier from (a-.30); (2) cap our fold rate: if opp's bluff-able line (bet when
  checked to), call with eq >= need (no margin) when n_opp==1; validate on LAG + v5 + mixed.
- Tried (2) as: HU and we checked this street -> margin -.02: vs LAG 28.12 (v5 26.98; 53 firsts
  vs 44). Validation: vs 7x v5 seed 121: 33.17 (+1.3); mixed seed 91: 43.68 (v5 47.48, -3.8).
  Rejected: blanket lighter calls lose to honest bettors (nit/montecarlo). A fix must be
  opponent-specific (needs a fast-reacting per-opponent bluff/bet-when-checked-to stat).

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
