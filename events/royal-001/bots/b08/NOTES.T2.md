# Team b08 notes

## Strategy

**Summary:** Equity-driven bot for royal hold'em (20-card deck, 4-card board). All hand strength comes from tables precomputed for this deck (preflop equity vs 1..7 random hands, exact rank-only head-to-head equities for all 15x15 starting-hand types, flop/turn equity vs random); at decision time it computes equity against an estimated opponent range (top-X% of hands by strength, card-removal aware) and compares it with pot odds or a shove EV model. Points 100/25/5 are winner-take-most, so it plays close to chip-EV and leans aggressive.

**Before the flop:** Opens by strength percentile (HU equity order: AA > KK > AK > AQ > QQ ~ AJ > KQ > AT > KJ > JQ ~ KT ~ JJ > QT > TJ > TT). The threshold depends on how many players are left to act: about the top 30% UTG, 58% on the button and 65% in the SB. It opens about 88% heads-up and a little wider 3-handed, and loosens against seats that often fold to raises. Opens to 2.5bb (2.2bb under 30bb). Facing a raise, it estimates the raiser's range from observed PFR (default top 30%; top 14% for a 3-bet). It 3-bets or shoves premiums and calls when range equity beats pot odds plus a realization penalty. At 22bb or less it shoves light against raisers who fold a lot.

**After the flop:** Enumerates every opponent rank pair (and, on the flop, every turn card) to get equity against each opponent's range. The range is the top fraction of hands by board strength. Bets narrow it: bigger bets make it tighter, adjusted for that seat's observed aggression. Bets about 70% pot with equity >= 0.62 against those ranges (0.58 heads-up). The threshold moves 0.04 lower against calling stations and 0.02 higher against folders. Heads-up c-bet frequency is 0.55, adjusted by the opponent's observed fold-to-bet rate (20–85%). It bluffs the turn against high-fold seats. It calls when equity beats pot odds and raises with equity >= 0.80.

**Short stacks and the points table:** At 16bb effective or less (13bb before v5) it plays push/fold. It shoves when an EV model beats folding: each player behind calls with their top c% of hands, where c comes from that player's VPIP, is larger in the BB and smaller against big shoves. It calls shoves when equity against the shover's estimated range beats pot odds. That range blends a stack-depth default with the seat's observed shove rate. When stacks are deep (over 30bb, 3+ players alive), a shove or huge raise is read as a tight range (about the top 12%, wider for high-PFR seats), and stacking off needs a 4-point equity margin over pot odds. The same applies postflop: a bet of 45% or more of our deep stack shrinks the bettor's range by 25%. There is no ICM tightening, because 1st place is worth 4x 2nd.

**Opponents:** Tracks per seat: hands, VPIP, PFR, fold-to-raise preflop, preflop shove rate, postflop aggression (raises vs calls) and postflop fold-to-bet rate. These drive steal thresholds, calling-range estimates for shoves, raiser/shover/bettor range widths, and bluff and thin-value frequencies.

**Last change:** v5 (005-b9dd39f3) moves the push/fold switch from 13bb to 16bb effective. In three four-against-four head-to-heads with v4 (500, 450 and 300 tables), pf16 led each time: 16.6 vs 15.9, 16.9 vs 15.6, 17.2 vs 15.3. Earlier, v4 (004-157fa018) tightened deep-stack stack-off decisions. In T1 (v3) we ranked 1st with 20.45, but finished 8th in 24.5% of tables. Local test: 700 tables against v1-v3 copies + nit + threshold scored 22.2 against 18.9-21.4 for v3 copies. A 600-table placement run (v3/v2/v1 copies + nit, maniac, threshold) gave v4 12 eighth places against 23-30 for the v3 copies, with similar points.

## Log
- 001: first accepted. vs zoo 40 tables 48.4 +- 15 (1st of 8). Self-play 200 tables: field avg 16.9.
- Param sweep (600 tables, pool of variants): looser/tighter opens (+-0.08), push/fold at 18bb, more c-bets all within +-3 of base. No detectable difference; identical bots differ by ~2-4 at 600 tables.
- 002: HU/3-handed wider opens, shove-rate tracking for shove calling ranges. Equal to v1 within noise, no errors.
- 003: fold-rate-driven c-bets/turn bluffs/thin value. Equal within noise.
- T1 (v3): rank 1/8, 20.45 pts/table (CI 18.1-22.8). Places 1st 179, 2nd 84, 3rd 89, 4th 93, 5th 86, 6th 103, 7th 121, 8th 245. VPIP 45% (loosest; field 22-37%). 1 hang (wall 84ms, cpu max 820us; probably GC/machine).
- 004: deep stack-off tightening (see Last change). prep/places.py prints place distributions per entry.

## Known weaknesses / next steps
- Equity tables ignore straight flushes (0.16%), so tiny errors when one is possible.
- Turn decisions use range equity with a crude top-X% range model; no explicit check-raise logic.
- No ICM/ladder awareness at 3 left (payouts 100/25/5 make this small).
- Ideas: track opponents' showdown hands to calibrate ranges; tune push/fold calling thresholds against real opponents' shove frequencies from tournament results; larger value sizes vs stations.
- Testing: `python prep/mkvar.py NAME key=val` makes a variant in prep/var/NAME; pool several variants in one localsim run (opponents list) to compare.
- Tight-field check (450 tables: v4, cand open_adj+0.05, 3x tagA open_adj+0.12/call_pen 0.08, v3, v1, nit): v4 18.1, v3 19.9, cand 16.2, tagA 17-20 -> all noise; kept v4 looseness.
- v4 confirmation (700 tables: v4, 3x v3, v2, v1, nit, maniac): v4 21.4 (8th 34x) vs v3 17.7-20.4 (8th 56-65x), v1 17.5, v2 15.0. Kept v4 for T2.
- Candidate d20 (deep stack-off tightening from 20bb instead of 30bb), 500 tables same pool: v4 21.5, d20 19.9, v3 18.6-18.8, v1 15.8, v2 15.7. Not better -> not submitted; v4 stays active.
- Candidates big (bet_size 0.85) and r75 (raise_eq 0.75), 450 tables with v4, 2x v3, v1, nit, maniac: v3 20.5/20.5, v1 18.0, big 17.9, r75 17.2, v4 16.6 -> all within noise (+-3.3). Over 4 pooled runs v4 = 22.2/21.4/21.5/16.6 vs v3 copies 17.7-21.4; v4 still >= v3 on average and busts first less. Not submitted.
- Head-to-head 4x v4 vs 4x v3, 600 tables: v4 copies 18.5/17.3/16.0/14.4 (mean 16.5), v3 copies 17.1/16.2/15.3/15.2 (mean 16.0). Equal within noise; v4 kept active.
- v4 vs full house zoo (40 tables): 53.1 pts/table (1st; v1 was 48.4), 0 substitutions, max 102 us.
- Head-to-head 4x v4 vs 4x pf16 (push/fold from 16bb), 500 tables: v4 mean 15.9, pf16 mean 16.6 -> noise; not submitted. Next idea: test pf16 again with more tables / against tighter fields before adopting.
- Retest 4x v4 vs 4x pf16, 450 tables seed 67: v4 mean 15.6, pf16 mean 16.9. Two runs combined pf16 +~1.0 (~1.2 SE): promising lead, not significant; no time to confirm, so v4 kept. NEXT WINDOW: run one more pf16 head-to-head; if it is ahead again, adopt pf_bb=16.
- Third head-to-head (300 tables seed 71): pf16 mean 17.2 vs v4 15.3 -> adopted. 005-b9dd39f3 = v4 + pf_bb=16. Zoo check 60 tables: 47.7 pts/table (1st), 0 substitutions, max 85 us.
- Post-submit check 4x v5 vs 4x v4, 250 tables seed 83: v5 mean 16.0, v4 mean 16.5 (noise). Four runs total pf16 vs pf13: +0.65, +1.24, +1.95, -0.54 -> mean ~+0.8, lean positive but unproven. If results show more early busts in short-stack play, revert pf_bb to 13.
