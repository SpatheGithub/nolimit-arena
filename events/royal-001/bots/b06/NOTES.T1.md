# Team b06 notes

## Strategy

**Summary:** Equity-driven bot built on exact rank-only equity tables for the 20-card royal deck. Suits are ignored because flushes are impossible and straight flushes are 0.16%. Every decision compares equity against an estimated opponent range (narrowed by that opponent's observed raise rate and by betting on this board) with pot odds; short stacks use a chip-EV push/fold model. The points table (100/25/5) is very top-heavy, so it plays for chips (near chip-EV) instead of tight ICM survival.

**Before the flop:** It ranks the 15 rank-classes by heads-up equity against a random hand: AA, KK, AK, AQ, AJ, QQ, KQ, AT, KJ, KT, JJ, QJ, QT, JT, TT. Its opening range depends on how many players are left to act: about 22% from early seats, about 50% with 2 behind and about 72% heads-up against the big blind, all to 2.5–3bb. With an effective stack of 14–16bb or less it pushes or folds by chip EV, assuming each opponent calls with the top q of hands, where q = 0.08 + 0.9/stack-in-bb and is scaled by that opponent's VPIP. Facing a raise, it computes equity against the raiser's range (their observed PFR ×1.1, or tighter after a 3-bet). It 3-bets with equity ≥ 0.60, calls when equity beats pot odds by a margin, and when committed (short stacks, or a call over 40% of its stack) it re-shoves or calls by pot odds.

**After the flop:** It computes exact equity on the flop and turn against each opponent's range. That range is the opponent's preflop range, then trimmed to the top part of their holdings on this board whenever they bet or raise; it is multiplied across opponents. It value-bets at 60–80% of the pot when equity is ≥ 0.60 (higher multiway) and goes all-in at low stack-to-pot ratios. With equity below 0.5 against 1–2 opponents it bluffs at 55% of the pot, but only if their fold-to-bet rate is above about 0.40: 60% of the time in position, 35% out of position. Otherwise it semi-bluffs the flop 8% of the time with equity above 0.33. Facing a bet it calls when equity > pot odds + margin, and raises or shoves with equity ≥ 0.78. A straight flush counts as the nuts.

**Short stacks and the points table:** Push/fold below about 15bb, using the chip-EV formula pnc*pot + (1-pnc)*(eq*(pot+2R)-R). There is no explicit ICM: with payouts of 100/25/5, ICM is close to chip-linear.

**Opponents:** It tracks each seat's VPIP, PFR, postflop aggression and fold-to-bet rates before and after the flop (Bayesian priors 0.35 / 0.22 / 0.4 / 0.6 / 0.3). These set the raise ranges it assumes, the calling ranges it expects against its shoves, how far a bet narrows a range, and how wide it steals. It bluffs postflop only when the opponent's fold-to-bet rate is above the break-even point (about 0.40). Against calling stations (postflop fold rate below 0.25) it makes bigger value bets.

**Last change:** v2 (002-2f316ad1) adds fold-rate tracking, bluffs only against seats that fold, bigger value bets against calling stations, and wider steals against folders. Test over 60 tables against 4 v1 copies plus montecarlo, maniac and nit: v2 scored 26.1, the v1 copies averaged 20.4 (noisy). Earlier, v1 scored 34.3 against the zoo.

## Notes
- The tables come from precompute.py, which writes bot/tables.json. Exact rank-only enumeration; multiway preflop equities are Monte Carlo.
- Equity vs a random hand, heads-up: AA .69, KK .61, AK .60, AQ .57, AJ .54, QQ .53, KQ .52, AT .50, KJ .49, KT .46, JJ .45, QJ .45, QT .42, JT .39, TT .37.
- All straights tie (T-A is the only straight), and ties are common.

## In progress (NOT submitted; in bot/agent.py working copy)
- Push model: the calling width q was too low (0.08+0.9/bb), so v2 shoves very wide (100% from the SB at 14bb).
  Working copy: q=(0.10+1.1/bb)*nbf, where nbf=1/0.75/0.6 by players behind, +0.06 for the big blind. In the push/fold zone, if the push EV is <= 0 and the stack is >= 9bb, open to 2.2bb with the normal opening range instead of folding.
  It is untested. With 4+ players behind at 10-14bb it pushes only AA, which is probably too tight. Test it against v2 before submitting.
## Ideas next
- Track shove frequency per seat; estimate a short-stack shover's range from it.
- Add an ICM adjustment with 3 left (100/25/5).
- Use 150-300 table sims; exclude montecarlo for speed (it uses 0.7 ms wall-clock per decision). A localsim run must finish in under 200 s or the shell timeout kills it with no output.
