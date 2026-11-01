# Team b08 notes

## Strategy

**Summary:** Equity-driven bot for royal hold'em (20-card deck, 4-card board). All hand strength comes from tables precomputed for this deck (preflop equity vs 1..7 random hands, exact rank-only head-to-head equities for all 15x15 starting-hand types, flop/turn equity vs random); at decision time it computes equity against an estimated opponent range (top-X% of hands by strength, card-removal aware) and compares it with pot odds or a shove EV model. Points 100/25/5 are winner-take-most, so it plays close to chip-EV and leans aggressive.

**Before the flop:** Opens by strength percentile (HU equity order: AA > KK > AK > AQ > QQ ~ AJ > KQ > AT > KJ > JQ ~ KT ~ JJ > QT > TJ > TT). The threshold depends on how many players are left to act: about the top 30% UTG, 58% on the button and 65% in the SB. It opens about 88% heads-up and a little wider 3-handed, and loosens against seats that often fold to raises. Opens to 2.5bb (2.2bb under 30bb). Facing a raise, it estimates the raiser's range from observed PFR (default top 30%; top 14% for a 3-bet). It 3-bets or shoves premiums and calls when range equity beats pot odds plus a realization penalty. At 22bb or less it shoves light against raisers who fold a lot.

**After the flop:** Enumerates every opponent rank pair (and, on the flop, every turn card) to get equity against each opponent's range. The range is the top fraction of hands by board strength. Bets narrow it: bigger bets make it tighter, adjusted for that seat's observed aggression. Bets about 70% pot with equity >= 0.62 against those ranges (0.58 heads-up). The threshold moves 0.04 lower against calling stations and 0.02 higher against folders. Heads-up c-bet frequency is 0.55, adjusted by the opponent's observed fold-to-bet rate (20–85%). It bluffs the turn against high-fold seats. It calls when equity beats pot odds and raises with equity >= 0.80.

**Short stacks and the points table:** At 13bb effective or less it plays push/fold. It shoves when an EV model beats folding: each player behind calls with their top c% of hands, where c comes from that player's VPIP, is larger in the BB and smaller against big shoves. It calls shoves when equity against the shover's estimated range beats pot odds. That range blends a stack-depth default with the seat's observed shove rate. There is no ICM tightening, because 1st place is worth 4x 2nd.

**Opponents:** Tracks per seat: hands, VPIP, PFR, fold-to-raise preflop, preflop shove rate, postflop aggression (raises vs calls) and postflop fold-to-bet rate. These drive steal thresholds, calling-range estimates for shoves, raiser/shover/bettor range widths, and bluff and thin-value frequencies.

**Last change:** v3 (003-053b6ed2) added bluff and value thresholds driven by each seat's fold-to-bet rate. Over 600 tables against v2/v1 copies and house bots it scored 19.5 against 18.4–23.9 for v2 copies: within noise, no errors.

## Log
- 001: first accepted. vs zoo 40 tables 48.4 +- 15 (1st of 8). Self-play 200 tables: field avg 16.9.
- Param sweep (600 tables, pool of variants): looser/tighter opens (+-0.08), push/fold at 18bb, more c-bets all within +-3 of base. No detectable difference; identical bots differ by ~2-4 at 600 tables.
- 002: HU/3-handed wider opens, shove-rate tracking for shove calling ranges. Equal to v1 within noise, no errors.
- 003: fold-rate-driven c-bets/turn bluffs/thin value. Equal within noise.

## Known weaknesses / next steps
- Equity tables ignore straight flushes (0.16%), so tiny errors when one is possible.
- Turn decisions use range equity with a crude top-X% range model; no explicit check-raise logic.
- No ICM/ladder awareness at 3 left (payouts 100/25/5 make this small).
- Ideas: track opponents' showdown hands to calibrate ranges; tune push/fold calling thresholds against real opponents' shove frequencies from tournament results; larger value sizes vs stations.
- Testing: `python prep/mkvar.py NAME key=val` makes a variant in prep/var/NAME; pool several variants in one localsim run (opponents list) to compare.
