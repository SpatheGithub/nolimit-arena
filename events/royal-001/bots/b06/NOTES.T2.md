# Team b06 notes

## Strategy

**Summary:** Equity-driven bot built on exact rank-only equity tables for the 20-card royal deck. Suits are ignored because flushes are impossible and straight flushes are 0.16%. Every decision compares equity against an estimated opponent range (narrowed by that opponent's observed raise rate and by betting on this board) with pot odds; short stacks use a chip-EV push/fold model. The points table (100/25/5) is very top-heavy, so it plays for chips (near chip-EV) instead of tight ICM survival.

**Before the flop:** It ranks the 15 rank-classes by heads-up equity against a random hand: AA, KK, AK, AQ, AJ, QQ, KQ, AT, KJ, KT, JJ, QJ, QT, JT, TT. Its opening range depends on how many players are left to act: about 22% from early seats, about 50% with 2 behind and about 72% heads-up against the big blind, all to 2.5–3bb. With an effective stack of 14–16bb or less it pushes by chip EV, assuming each opponent calls with the top q of hands. Here q = (0.10 + 1.1/stack-in-bb) × 1, 0.75 or 0.6 as more players are left to act, plus 0.06 for the big blind, then scaled by that opponent's VPIP and fold rate. If pushing isn't +EV and it has 9bb or more, it opens to 2.2bb with its normal opening range instead of folding. Facing a raise, it computes equity against the raiser's range (their observed PFR ×1.1, or tighter after a 3-bet). It 3-bets with equity ≥ 0.60, calls when equity beats pot odds by a margin, and when committed (short stacks, or a call over 40% of its stack) it re-shoves or calls by pot odds.

**After the flop:** It computes exact equity on the flop and turn against each opponent's range. That range is the opponent's preflop range, then trimmed to the top part of their holdings on this board whenever they bet or raise; it is multiplied across opponents. It value-bets at 60–80% of the pot when equity is ≥ 0.60 (higher multiway) and goes all-in at low stack-to-pot ratios. With equity below 0.5 against 1–2 opponents it bluffs at 55% of the pot, but only if their fold-to-bet rate is above about 0.40: 60% of the time in position, 35% out of position. Otherwise it semi-bluffs the flop 8% of the time with equity above 0.33. Facing a bet it calls when equity > pot odds + margin, and raises or shoves with equity ≥ 0.78. A straight flush counts as the nuts.

**Short stacks and the points table:** Push/fold below about 15bb, using the chip-EV formula pnc*pot + (1-pnc)*(eq*(pot+2R)-R). There is no explicit ICM: with payouts of 100/25/5, ICM is close to chip-linear.

**Opponents:** It tracks each seat's VPIP, PFR, postflop aggression and fold-to-bet rates before and after the flop (Bayesian priors 0.35 / 0.22 / 0.4 / 0.6 / 0.3). These set the raise ranges it assumes, the calling ranges it expects against its shoves, how far a bet narrows a range, and how wide it steals. It bluffs postflop only when the opponent's fold-to-bet rate is above the break-even point (about 0.40). Against calling stations (postflop fold rate below 0.25) it makes bigger value bets.

**Last change:** v3 (003-fe050396, submitted for T2) replaces v2's push model, which assumed callers were too tight (it shoved every hand from the small blind at 14bb), and adds the 2.2bb open fallback. Tests over 1000 tables against 3 copies of v2: mixed field 22.60 vs a v2 average of 22.0; tight field (2 nit, threshold, checkfold) 26.98 vs 25.3. Both gains are small and within noise. v2 had come 3rd in T1 with 18.52.

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
