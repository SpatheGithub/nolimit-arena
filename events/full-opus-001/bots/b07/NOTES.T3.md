# Team b07 notes

## Approach
Precomputed-equity NLHE bot (bot/agent.py), all decisions are lookups + arithmetic (~25 us/act).
- Preflop: 169-class tables in bot/_common.json (percentile + equity vs k random hands, from kit house
  bots) and bot/rangeeq.json (my precompute, tools/rangeeq.py: equity of each class vs top-w% range,
  w in {3,6,10,15,20,30,40,55,75,100}%, 1500 MC deals each).
  - Unopened: S<=13bb push/fold: shove if pct <= 5/(S * k^0.75), k = players behind + limpers.
    Deeper: open-raise 2.5bb (+1/limper) with pct <= OPEN[players behind].
  - Facing raise: estimate raiser range width w from #raises and the seat's observed PFR rate
    (per-table stats from observe()), short all-in shovers widen to 4/S. eq = eq_vs_range(class, w).
    All-in decisions: call if eq >= pot-odds + 0.01 + ICM premium.
- ICM premium: ICM (kit/icm.py) says calling off a full stack at equal stacks needs ~61% equity with
  4-8 players (57% 3-handed, 50% HU). premium(n_alive, risk_frac, S) = 0.10 (n>=4) / 0.06 (n=3) /
  0 (HU), scaled by fraction of stack at risk, reduced when S<10bb. Gave +5 pts/table vs zoo.
- Postflop: house-bot `features()` (strength 0..1, draw outs, wet) + rule-of-2/4 draw equity,
  multiway discount 0.07/opp; bet >=0.58 for value, raise >=0.76-0.86; calls when est. equity
  (minus a bet-size penalty, reduced vs observed aggressive bettors) beats pot odds (+ICM premium
  if the call is >25% of stack).

## Testing
- tools/sim.py TABLES SEED BOTDIR opp1,opp2,... -> points + finishing-place distribution.
- Zoo (600 tables seed 7): v1 44.8, v2 50.1 (nit ~49, checkfold ~41 because loose bots bust each other).

- A/B (600 tables; "mix" = montecarlo,pot_odds,threshold,nit,maniac,minraiser,v1 seed 7;
  "tag" = v2,v2,cA,nit,montecarlo,pot_odds,maniac seed 9):
  - mix: v2 (PREM 1.0) 48.0 | PREM 1.6 51.2 | PREM 2.2 54.8 | PREM 3.0 56.2
    | PREM1.6+tighter opens 47.5 | PREM1.6+looser opens 52.3 | PREM1.6+shove k=4 52.3
    | PREM2.2+fold-tracking (bluff only vs folders, bigger value vs stations) 55.1
  - tag: v2 39.2 | PREM 2.2 44.4  -> bigger ICM premium is robust, not just a zoo artifact.
  - cI = PREM 3.0 + fold-tracking + looser opens (OPEN x~1.15) + shove k=4: mix 58.2, tag 47.1
    (PREM 3.0 alone: mix 56.2, tag 45.0). Submitted as 004-092848fa.
  - vs cI (mix/tag): PREM 4.0 56.7/44.9 (worse) | OPEN x1.15 more 56.4/45.2 (worse)
    | postflop premium when call >15% stack (vs 25%) 55.1/46.6 (worse)
    | push/fold up to 16bb (vs 13) 54.9/44.0 (worse)  -> cI is a local optimum on these knobs.

  - cN thinner value bets (0.54/0.62) 55.6/46.6 | cO more c-bets (gated by fold rate) 55.5/47.6.
- Final (cI) vs zoo, localsim seed 7, 600 tables: 60.3 (v1 44.8, v2 50.1; nit 47.7).
- Self-heavy field (cI x3, v2, nit, montecarlo, maniac; seed 13, 500 tables): cI 36.6 vs cD (PREM 2.2)
  38.0 -> within noise, but the PREM 3.0 edge may shrink vs bots like ours. First patch-window
  candidate: PREM ~2.5 with the rest of cI.
- Patch window 1: cP = cI with PREM 2.5 -> mix 56.1 / tag 46.6 / self 36.6 vs cI 58.2 / 47.1 / 36.6:
  not better, kept cI. cQ = cI but premium x0.5 when the all-in raiser's observed PFR rate > 0.35
  (maniac): mix 54.6 vs cI 58.2 -> worse even in the maniac-heavy field (busting costs more than
  the chips won); not submitted. Active submission stays 004-092848fa (cI).
- cR = cI + steal wider (OPEN x1.3, shove x1.25) when every player behind has observed VPIP < 0.22:
  mix 52.8 vs 58.2 -> worse (like cK: extra opens get punished); not submitted.
- Head-to-head, all submissions at one table (+nit, montecarlo, pot_odds, maniac; seed 21, 300 tables):
  004 48.4 > 003 42.4 > 002 39.8 > 001 37.8; 0 timeouts/errors, p99 100 us. Each version beat its
  predecessor.
- Fresh seed check vs zoo (seed 33, 300 tables): 004 58.2 (nit 45.2) -> consistent with seed 7 (60.3).
- Every one-knob variant of cI has tested equal-or-worse; next gains likely need new structure
  (calibrated postflop equity table, stack-aware ICM at runtime for <=5 players), not re-tuning.

## Submissions
- 001-47171877 v1 baseline
- 002-e5df263c v2 = v1 + ICM premium (PREM 1.0)
- 003-58394a26 PREM 2.2
- 004-092848fa cI (FINAL of build phase): PREM 3.0, fold-tracking, OPEN looser, shove k=4.
  Candidate dirs live in tools/c*/ (tools/cI == bot/).

## Key parameters (bot/agent.py)
- PREM = 3.0; premium base 0.10 (>=4 alive) / 0.06 (3) / 0 (HU), x risk fraction, x S/10 if S<10bb.
- OPEN = {0:.34, 1:.48, 2:.37, 3:.29, 4:.23, 5:.19, 6:.16, 7:.14} (percentile by players behind).
- Push/fold when S<=13bb: shove pct <= 4/(S*k^0.75).
- Postflop premium only when call > 25% of stack. Value bet sm>=0.58 (vsize 0.6/0.7/0.85 by
  opponents' fold rate); bluffs scaled by bluff_mult from fold-to-bet rate (prior 0.4, n0=4).

## Known weaknesses
- Postflop strength is heuristic (features()), not true equity vs ranges.
- Very tight all-in calling (needs ~80% eq for a full-stack call with >=4 alive): exploitable by
  bots that shove relentlessly; watch T1 results for many blinds lost / low 1st-place rate.
- No ICM at decision time beyond the premium heuristic; tables never reached the 200-hand cap in sims.
- A/B noise is +-2.8 per 600 tables; small tweaks (<2 pts) are not distinguishable.

## Next steps (patch windows)
- If real opponents shove a lot: lower PREM toward 2.2 or make it depend on the shover's observed
  shove rate (seat stats already tracked: pfr, faced/folded, aggr/passive).
- Postflop calibrated equity table (MC over features() buckets) to replace raw `s`.
- Test vs a self-heavy field (copies of tools/cI) to find what exploits bots like ours.

## T1 result (004 = cI): rank 5/8, 30.52 pts/table; places 1st 89, 2nd 126, 3rd 165, 4th 121,
5th 161, 6th 147, 7th 110, 8th 81. Field is tight (all teams VPIP 19-28%, PFR 14-22%), all within noise.
Diagnosis: we lose most heads-up endings (2nd > 1st) and are over-tight 3-handed.

## Patch window before T2
- New proxy field "real" = tools/cI,cD,v2,v1,nit,cA,cE (all deterministic -> same seed gives PAIRED
  comparisons: tables play identically until the changed logic kicks in). montecarlo is time-based,
  so mix/tag fields are NOT paired (noise +-2.8).
- PREM in real field (seed 17): 3.0 35.5 | 2.0 34.8 | 1.3 30.9 -> keep 3.0.
  Resteal (re-shove eq>=0.47) / shove k=5 with PREM 2.0: 34.7-35.4 (noise).
- cW = cI + endgame: push/fold coef 6 (not 4) when <=3 alive; HU push/fold up to 16bb; HU SB open
  80%, 3-handed open >=50% BTN / 60% SB (not in BB); HU raiser range w>=0.6; 3-handed premium base
  0.035 (was 0.06). Paired: s17 36.26 vs 35.50, s23 35.54 vs 34.58 (+0.8/+1.0, all from more 1sts).
  SUBMITTED 005-9565257c.
- Tried on top of cW (paired, s17/s23): HU coef 7.5: 35.86/35.38 (worse); 4-handed premium base
  0.06: 36.32/35.05 (flat); no 3-handed premium: 35.50/34.46 (worse).
- Next: HU postflop (deep HU rarely happens; most HU is push/fold), BB defense vs HU min-raises,
  check T2 places for whether 1st/2nd ratio improved.
- 3-handed premium base 0.05 (cAB): 36.14/35.30 vs cW 36.26/35.54 -> slightly worse; 0.035 stays.
  Active for T2: 005-9565257c (cW).
- Head-to-head (005 vs 004 x2, 003, 002, 001, nit, threshold; seed 41, 400 tables): 005 39.7 (1st),
  003 38.9, 004 37.4/33.8, 002 36.1, 001 32.8 -> 005 on top, gaps within noise (+-3.3); 0 errors.

## T2 result (005 = cW): rank 6/8, 30.39 pts/table (weighted total 91.30, rank 6).
Places 1st 106, 2nd 98, 3rd 147, 4th 157, 5th 146, 6th 132, 7th 119, 8th 95. Endgame fix worked
(1st/2nd 106/98 vs T1 89/126) but we bust 4th-6th a lot (mid phase, 10-25bb). VPIP 24 / PFR 15:
our call gap (9%) is larger than other teams' (5-6%).

## Patch window before T3 (machine heavily loaded: 1000 tables took 3-6 min)
- cBA = cW + BB defense needs pct<=0.50 & eq>=need+0.05 (was eq>=need+0.02) + cold calls pct<=0.15
  (was 0.25): real field s51 1000 tables: 35.02 vs cW 35.19 (VPIP 25%->22%, same points). No
  evidence it helps -> kept 005-9565257c for T3.
- Ideas not yet tested: mid-phase (10-25bb) aggression: open-shove/re-shove more vs tight openers;
  the local proxy field (my own bots) scores us ~35 while the real field gives ~30, so the real
  opponents are stronger than my proxies; consider testing vs threshold/nit-heavy + self copies.
- cBB = cW + only the tighter BB defense: s51 1000 tables 35.26 vs cW 35.19 -> flat. BB-defense /
  cold-call width is not a measurable lever in the proxy field. 005 stays for T3.
- cBC = cW + push/fold up to 16bb at any table size: s51 1000 tables 34.02 vs cW 35.19 -> worse
  (consistent with cM earlier). 13bb threshold stays.
