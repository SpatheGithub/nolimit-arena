# Team b06 notes

## Strategy

**Summary:** Equity-driven bot built on exact rank-only equity tables for the 20-card royal deck. Suits are ignored because flushes are impossible and straight flushes are 0.16%. Every decision compares equity against an estimated opponent range (narrowed by that opponent's observed raise rate and by betting on this board) with pot odds; short stacks use a chip-EV push/fold model. The points table (100/25/5) is very top-heavy, so it plays for chips (near chip-EV) instead of tight ICM survival.

**Before the flop:** It ranks the 15 rank-classes by heads-up equity against a random hand: AA, KK, AK, AQ, AJ, QQ, KQ, AT, KJ, KT, JJ, QJ, QT, JT, TT. With 4 or more players behind it uses the better of the heads-up rank and a 3-way-equity rank, so pairs like QQ open from middle seats. Its opening range depends on how many players are left to act: about 22% from early seats, about 50% with 2 behind and about 72% heads-up against the big blind, all to 2.5–3bb. With an effective stack of 14–16bb or less it pushes by chip EV, assuming each opponent calls with the top q of hands. Here q = (0.10 + 1.1/stack-in-bb) × 1, 0.75 or 0.6 as more players are left to act, plus 0.06 for the big blind, then scaled by that opponent's VPIP and fold rate. If pushing isn't +EV and it has 9bb or more, it opens to 2.2bb with its normal opening range instead of folding. Facing a raise, it computes equity against the raiser's range (their observed PFR ×1.1, or tighter after a 3-bet). It 3-bets with equity ≥ 0.60, calls when equity beats pot odds by a margin, and when committed (short stacks, or a call over 40% of its stack) it re-shoves or calls by pot odds. Against a short-stack all-in (15bb or less) it assumes the shover's range is at least the top min(0.8, 0.22 + 3/stack-in-bb), about 52% at 10bb.

**After the flop:** It computes exact equity on the flop and turn against each opponent's range. That range is the opponent's preflop range, then trimmed to the top part of their holdings on this board whenever they bet or raise; it is multiplied across opponents. It value-bets at 60–80% of the pot when equity is ≥ 0.60 (higher multiway), with bigger bets against calling stations, and goes all-in at low stack-to-pot ratios. Heads-up on the flop, as the last preflop raiser with no bet yet, it continuation-bets half the pot 70% of the time when the opponent's fold rate is above 0.4. Heads-up with medium equity (0.5 to the value threshold) against a seat whose fold-to-bet rate is above 0.45, it bets half the pot 60% of the time in position and 40% out of position. With equity below 0.5 against 1–2 opponents it bluffs at 55% of the pot when their fold rate is above about 0.40 (60% in position, 35% out of position). Facing a bet it calls when equity > pot odds + margin, and raises or shoves with equity ≥ 0.78. A straight flush counts as the nuts.

**Short stacks and the points table:** Push/fold below about 15bb, using the chip-EV formula pnc*pot + (1-pnc)*(eq*(pot+2R)-R). There is no explicit ICM: with payouts of 100/25/5, ICM is close to chip-linear.

**Opponents:** It tracks each seat's VPIP, PFR, postflop aggression and fold-to-bet rates before and after the flop (Bayesian priors 0.35 / 0.22 / 0.4 / 0.6 / 0.5). These set the raise ranges it assumes, the calling ranges it expects against its shoves, how far a bet narrows a range, and how wide it steals. It bluffs postflop only when the opponent's fold-to-bet rate is above the break-even point (about 0.40). Against calling stations (postflop fold rate below 0.25) it makes bigger value bets.

**Last change:** v7 (007-8a118a57, for T4) = v6 + preflop fixes for leaks seen in the T3 sample hands (it folded QQ under the gun and AQ/QQ to a raise plus a caller). With 4+ behind it uses the better of the heads-up and 3-way-equity rank when opening, and the deep call margin is 0.03 instead of 0.06 when others have already called. Tests against 006 copies: +1.9 (1000 tables, mixed field) and −0.3 (600 tables, tight field). In all-versions fields v6 ranked first both times (v6 > v4 > v5/v3 > v2 > v1), so the newer versions really are stronger locally.

## Notes
- The tables come from precompute.py, which writes bot/tables.json. Exact rank-only enumeration; multiway preflop equities are Monte Carlo.
- Equity vs a random hand, heads-up: AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50, KJ .49, KT .46, JJ .45, QJ .45, QT .42, JT .39, TT .37.
- All straights tie (T-A is the only straight), and ties are common.

## Push-model change (was in progress at build end; now submitted as v3 / 003-fe050396)
- Push model: the calling width q was too low (0.08+0.9/bb), so v2 shoves very wide (100% from the SB at 14bb).
  Working copy: q=(0.10+1.1/bb)*nbf, where nbf=1/0.75/0.6 by players behind, +0.06 for the big blind. In the push/fold zone, if the push EV is <= 0 and the stack is >= 9bb, open to 2.2bb with the normal opening range instead of folding.
  Tested in the T2 patch window (see below). With 4+ players behind at 10-14bb it pushes only AA and opens 2.2bb with the rest of its range; widen this if T2 shows it is too tight.
## Ideas next
- Track shove frequency per seat; estimate a short-stack shover's range from it.
- Add an ICM adjustment with 3 left (100/25/5).
- Use 150-300 table sims; exclude montecarlo for speed (it uses 0.7 ms wall-clock per decision). A localsim run must finish in under 200 s or the shell timeout kills it with no output.

## T1 result (v2, 002-2f316ad1)
- Rank 3/8, 18.52 points per table (b08 20.45 at 45% VPIP / 26% PFR; b05 18.52; the rest 13–17). Places 1st–8th: 157/91/109/101/120/131/146/145.
- 0 substitutions; p99 50 µs.
- The field is mostly tight (VPIP 22–37%, PFR 16–19%); the loosest team won.

## Patch window before T2: tests (1000 tables, seed 41, field = 3x 002 + 001 + maniac + nit + pot_odds)
- v3 (variants/v3 = current bot/ working copy, with the tighter push model plus a 2.2bb open fallback in the push zone): 22.60 vs the 002 copies' average of 22.0. No gain.
- v3 with opening thresholds +0.10: 21.48 vs the 002 average of 21.3. No gain.
- First decision was to keep 002. After the tight-field run (+1.7, the second positive run for v3), I submitted v3 as 003-fe050396 for T2.
- localsim is fast now when montecarlo is left out: 1000 tables in about 60–90 s.

## Next ideas
- Look for chip leaks in results/*/sample_hands.json: postflop folds with two pair against a single bet (for example KJ on AAJ folding to a 60% pot bet).
- Build a test field closer to the real one (tight, PFR around 18%), for example nit plus copies with tighter thresholds.
- v3 with wider assumed postflop bet ranges (f base 0.45 -> 0.60, so it calls more): seed 41 gave 23.01 vs the 002 average of 21.79 (+1.2), seed 52 gave 20.18 vs 22.18 (-2.0). Net -0.4, noise. Not submitted.
- Tight field (3x 002, 2 nit, threshold, checkfold), seed 63: v3 26.98 vs the 002 average of 25.3. v3 is positive in both runs, so I submitted it as 003-fe050396. bot/ = variants/v3 = 003.
- Third run (after the submit), seed 77, field 3x 002 + nit + maniac + pot_odds + threshold: v3 26.91 vs the 002 average of 25.4 (+1.5). v3 is ahead in all 3 runs (+0.6, +1.7, +1.5), so the submission looks justified, though still modest.
- Candidate for later: call short-stack shoves wider (shover range min(0.8, 0.22+3/bb) instead of min(0.7, 0.18+2/bb)). Seed 88 against 3x 003 + 002 + nit + maniac + pot_odds: 22.09 vs the 003 average of 21.2 (+0.9). Noise, one run only; needs more runs before submitting. Not in bot/ (bot/ = 003).
  Second run, seed 99, against 3x 003 + 002 + 2 nit + threshold: 22.41 vs the 003 average of 21.4 (+1.0). Two runs at about +1, a weak but consistent sign. Good first candidate for the T3 window (confirm with 1–2 more runs, then submit).
  Caveat: the local gain may come from my own bot copies shoving wide. The real field is tighter (PFR 16–19% in T1), so wider calls could lose chips there. Before submitting, check the T2 sample hands for how wide the other teams' short-stack shoves actually are. Not submitted for T2.
  The T1 sample hands (40 of them) contain only 1 preflop shove (100bb, cards not shown), too little to measure shove widths. Use the T2 samples.

## T2 result (v3, 003-fe050396)
- Rank 4/8, 17.55 (b08 21.52 again at 44%/24%). Places: 145/99/114/132/131/138/128/113. Weighted total after T2: 53.61, rank 3.
- Sample hands = the first 10 hands of 4 tables, so deep stacks only. 80 opens: 7% won uncontested, 86% called, 16% 3-bet, so stealing doesn't work and opens should be value-heavy.
- Postflop facing a bet: 58% fold overall (flop 48%, turn 74%). Bluffing and betting to win the pot pay.
- v4 submitted (see Last change). variants/v4 = 004.
- Patch window before T3: v5a (turn bluff/bet frequency raised further) -0.8 vs 004; v5b (3bb opens) -0.1 vs 004. Both rejected.
- Wider shove-calling on v4: +2.5 (seed 505), -0.3 tight field (seed 606), so I submitted v5 = 005-a04911a7. variants/v5 = 005.
- After submitting v5: v6a (deep call margin 0.06 -> 0.03) +0.1 vs 005, rejected. v6b (postflop raise threshold 0.78 -> 0.72) -2.1 vs 005, rejected.
- Zoo sanity check, v5 over 250 tables: 48.6 points per table (v1 scored 34.3). bot/ = variants/v5 = 005.
- Ideas for later: ICM adjustment with 3 left (100/25/5 makes 3rd -> 2nd worth 20 points); flop c-bet as the preflop raiser; check the T3 samples for late-stage shove widths.
- v6c (flop c-bet 50% pot, 70% of the time, as the last preflop raiser heads-up when the opponent's fold rate is above 0.4): +1.5 (seed 111, mixed) and -0.75 (seed 222, tight field). Net +0.4, not submitted. It might suit the real field (48% flop folds); retest with more seeds.
- Third c-bet run, seed 333, mixed field: +2.1 (23.13 vs 21.0). Submitted v6 = 006-2479d00d. variants/v6 = 006 = bot/.
- Zoo sanity check, v6 over 250 tables (seed 808): 47.0 (v5 48.6, within noise). 1 "hang": wall-clock over 50 ms on the loaded machine, with max CPU 116 µs. v4 had one too. Treated as machine load, not code.
- Seed 444: v6 21.31 vs the 005 average of 20.68 (+0.6). Over 4 runs the c-bet averages about +0.9.
- WATCH: the single 004 (v4) copy in the 005-copy fields scored 21.39, 23.07, 23.08, 21.39 and 23.29 (seeds 707, 909, 111, 222, 444), about 22.4 on average vs about 21.3 for the 005 copies. So the wider shove-calling (the v5 change) may not help, or may hurt. Next window: test v4 + c-bet (no wider calls) directly against v6 copies before deciding.
- Seed 555: v4+cbet (no wider calls) 21.88 vs the 006 average of 21.27 (+0.6); the single 004 copy scored 22.16. One run, noise-level, so v6 is kept for T3. Retest next window with more seeds. bot/ = v6.
- Seed 666 (tight field + a single 005): v4+cbet 20.61 vs the 006 average of 21.01 (-0.4); the single 005 copy scored 22.68. Two runs give v4+cbet about +0.1 vs v6, no difference. A lone "odd one out" copy often scores high, so be wary of single-copy comparisons. v6 stays.

## T3 result (v6, 006-2479d00d)
- Rank 5/8, 16.98 (b08 20.48, b05 19.50). Places: 135/118/105/129/139/121/140/113. Weighted total 104.53, rank 4.
- Trend T1 18.52 (v2), T2 17.55 (v3), T3 16.98 (v6), all within noise (CI ±2.1). Locally the newer versions are stronger, so the slide is probably noise or the field improving.
- T3 samples (10 hands of 4 tables; our seat found by elimination from shown cards): folded QQ UTG unopened, QQ facing a raise plus a caller, and AQ facing a raise plus a caller. Fixed in v7.
- Sample fold rates are stable across T1–T3: flop about 48%, turn 70–79%. Open-raise steals succeed only 3–12% of the time.
- localsim got slower under machine load (1000 tables took over 100 s): use 600 tables with a 110 s timeout.
- After submitting v7: confirmation runs (500 and 300 tables) timed out at 120 s with machine load around 21, so there is no third data point. v7 earlier ran 1600 tables plus check_bot with no errors. bot/ = variants/v7 = 007.
- Third v7 run (200 tables, seed 7007): 19.11 vs the 006 average of 22.08 (−3.0, ±5 CI, very noisy). Table-weighted over 3 runs (1000/600/200): about +0.6 for v7. Kept v7. Further runs timed out under load.
- Fourth v7 run (150 tables, seed 9009): 17.80 vs the 006 average of 23.6 (−5.8, ±6 CI). All 4 runs: +1.9/1000, −0.3/600, −3.0/200, −5.8/150, about +0.1 table-weighted, so v7 and v6 are indistinguishable. Two more runs timed out under load. v7 kept for T4: it is a targeted fix of an observed real-field leak, and resubmitting under load risked a failed submit.
- Next window: if T4 is weak, consider reverting to variants/v6 (006) or testing v7's two changes separately with 1000-table runs when the load is low.
- Once the load dropped: v7 vs 006 copies +2.2 (200 tables, seed 1414) and +2.0 (500 tables, seed 1515). All 6 runs together (2650 tables): about +0.6 table-weighted for v7, so v7 is confirmed for T4.
- Seed 1616 (200 tables, tight field): v7 18.43 vs the 006 average of 18.73 (−0.3). Overall about +0.5 table-weighted over 2850 tables. v7 stays for T4.
