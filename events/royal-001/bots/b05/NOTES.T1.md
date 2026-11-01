## Strategy

**Summary:** Math-first bot for royal hold'em (20-card deck, 4-card board). All equities are precomputed exactly (rank-only, straight flushes ignored except a live check) into `bot/tables.json`: preflop HU matrix (15x15 rank classes), equity vs top-q ranges, flop/turn equity vs random and vs top 50/25/10% of holdings. Decisions compare range-adjusted equity to pot odds; big all-in calls are priced in tournament points with a 3-place ICM (100/25/5).

**Before the flop:** Hands ranked by HU equity (AA .69, KK .61, AK .60, AQ .57, AJ/QQ/KQ ~.53, ... TT .37 worst). Opens top 26% (early) to 62% (SB) of hands, 2.5bb + 1bb per limper; folds weak hands. Facing a raise: estimates raiser's range from their observed PFR, calls when equity vs range beats pot odds + margin (multiway penalty only for players who put chips in voluntarily), 3-bets/jams top ~12%, and re-jams at <=25bb vs loose openers (range >=30%) with equity >=.5. At <=13bb effective: push/fold by chip-EV of a shove vs assumed calling ranges (15-40%); equities are so compressed in royal that wide shoves are +EV.

**After the flop:** Equity vs a range implied by bet size (small bet -> top 50%, pot -> top 25%, overbet -> top 10%), widened vs aggressive seats. Value-bets ~70-85% pot when ahead of the top-50% range, raises with equity >= .72, semi-bluffs/bluffs heads-up at low frequency (more as preflop aggressor).

**Short stacks and the points table:** push/fold at <=13bb; calls committing >=50% of stack go through ICM (fold vs call EV in points, bust = place points).

**Opponents:** tracks per-seat VPIP, PFR, postflop aggression (bets vs calls/checks) and fold-to-bet, shrunk to priors; used to size raiser ranges, widen calls vs aggressive bettors, bluff more vs folders (ftb>.5), stop bluffing and value-bet thinner/bigger vs stations (ftb<.3).

**Last change:** v3 (003-ae9ebe7d): fixed a preflop bug where blinds yet to act counted as callers (AA folded to a 100bb shove); added fold-to-bet tracking and re-steal jams. Zoo: 44-49 pts/table (next best ~22-27); vs 7 copies of v1: 16.0 ± 3.6 (baseline 16.25, noise too big to separate).

## Submissions
- 001-8ab9709b v1; 002-db29a180 AA-vs-shove fix + ftb; 003-ae9ebe7d + re-steal jam (current).

## Known weaknesses / next steps
- Turn vs pot-size shove: range model (0.5*eq50+0.5*eq25) folds straights on paired boards; could be too tight vs loose shovers.
- KK folds to an unknown 100bb shove (range prior top ~16% is AA-heavy); revisit if opponents shove wide.
- Self-play A/B needs >1000 tables to resolve ~2 pt differences; use zoo + submissions mixes in patch windows.
- Ideas: per-opponent calling-range estimates in push/fold; bet sizing by SPR; check-raise traps with full houses.

## Notes

- Evaluator verified vs engine: only straight-flush differences (0.1% of showdowns).
- Royal facts: min hand is two pair; only one straight (TJQKA, all straights tie -> many chops); pairs gain multiway (full houses).
