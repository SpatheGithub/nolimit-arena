# Team b06 notes

## Strategy

**Summary:** Math-first bot. A custom shortdeck evaluator (base-5 rank-key dict lookup, verified identical to the engine on 30k hands) drives precomputed preflop tables (81 classes: equity vs k random hands + an 81x81 class-vs-class matrix) and postflop equity (time-boxed Monte Carlo vs opponents' estimated ranges on flop/turn, exact enumeration of all opponent combos on the river). Every decision compares range-adjusted equity with pot odds; all-in calls with <=4 players left are priced in ICM points.

**Before the flop:** Opens top ~14% (UTG) to ~50% (SB) of hands by shortdeck equity rank, 2.5bb (3bb from the SB), +1bb per limper; heads-up opens 85% from the SB. Facing a raise it estimates the raiser's range (observed PFR, position; short-stack shoves from a position-aware push formula, widened by the seat's observed jam rate and VPIP; wider short-handed), computes our equity vs that range from the matrix, 3-bets/jams at >=60% equity, calls when realized equity beats pot odds. Below 25bb it re-shoves over a single open when chip EV with fold equity (from the opener's range width) beats calling. At <=13bb effective: push/fold with a range that widens as stacks shrink and as fewer players are left to act.

**After the flop:** Equity vs each opponent's preflop range (raiser tight, callers medium, blinds/limpers any). Value-bets 65-90% pot above a threshold that scales with number of opponents (river +5pts); c-bets the flop as preflop raiser ~55% heads-up, barrels the turn with >=38% equity, rare river bluffs; bluff frequency and value thresholds adapt to each opponent's fold-to-bet rate. Facing a flop/turn bet it subtracts a penalty that grows with bet size and shrinks vs aggressive opponents. Facing a river bet it computes equity vs only the top q of the bettor's range by hand value, with q falling steeply for big bets (0.55 for small bets, ~0.22 for pot-size, 0.12 for overbets) and widening only for very aggressive seats. Raises with >=72% adjusted equity, jams when SPR is low.

**Short stacks and the points table:** Push/fold at <=13bb. Facing all-ins with <=4 players alive, call/fold by exact ICM (Malmuth-Harville over the remaining places' points 100/45/20/8); otherwise chip EV with a small margin plus a penalty for players left behind. Tables between our versions never reach the 200-hand cap (mean ~109 hands), so finishing order, especially 1st, dominates.

**Opponents:** Per-seat VPIP, PFR, postflop aggression (raise vs call), fold-to-bet, preflop jam rate, all with priors. They set range widths, bet penalties, river range fraction, bluff frequency and value thresholds.

**Last change:** v8b (006-de789549), for T2: timing safety only, same strategy as v8. T1's worst call used 790us of the 1ms limit. The river enumeration now uses precomputed per-suit masks instead of building lists on flush boards (identical results on 400 test spots; worst case 362 -> 269us). The Monte Carlo budget is 280us (was 350) with a time check every 8 samples. Smoke p99 326us (was ~500). v8 itself: tighter river calls vs big bets (self-play leak: big river calls won 17% for -6bb each); mixed field 600 tables v8 44.5 vs v6 39.5.

## Versions
- 001-d0c5857a v1: first complete bot. zoo 46.1.
- 002-fab9dff3 v2: HU/short-handed widening, fold-to-bet stats.
- 003-6037990e v3: position-aware shove ranges, jam tracking, fold-equity re-shove, river value thr +0.05.
- 004-38b6f847 v6: v3 with GC-safe evaluator table (dict instead of 1.95M list: full-GC pause 7.7ms -> 1.3ms).
- 005-b15eb3f4 v8: v6 + steal widening (v7) + river big-bet call tightening. T1: rank 3/8, 23.50 (CI 21.3-25.7; leader b02 24.95, all within noise). Places 1st 153, 2nd 108, 3rd 122, 4th 112, 5th 154, 6th 161, 7th 99, 8th 91 per 1000. 0 substitutions; cpu max 790us.
- 006-de789549 v8b: v8 with a faster river path and a 280us MC budget (timing safety). Plays T2.

## Patch-window ideas
- Many 5th/6th busts (315/1000): check bubble play with 5 alive (ICM is only used at <=4).
- T1 sample_hands.json has no seat id for us; infer it from payoffs and hole cards if needed.

## Tools (tools/)
- sim.py: any mix of bot dirs/house bots in one field (`python tools/sim.py vers/v8 vers/v6 maniac ... --tables 600`).
- dbgbot/: wrapper that runs bot/ without the try/except so exceptions count as errors (caught a NameError in v7 that silently made it fold).
- leaks.py / calls.py: hand-log analysis; calls.py gives marginal EV of final calls by street and bet size.

## Findings
- Self-field call EV (v6): preflop calls +10..19bb, turn calls +9..11bb, river small/med calls +12bb, river big calls -6bb (17% win), river overbet calls -26bb.
- Against house bots all call buckets are +EV (maniac-heavy), so calling-adjustments must be keyed on opponent aggression.
- Abandoned: v4 (BB defense realization by hand quality, position-aware open ranges) and v5 (jam-rate x2, fe model, stronger agg penalty): no gain.
- v8 self-field call EV: river big calls now 24% win, -1.2bb/call (was -6.1); other buckets still positive.
- v9 (wider assumed shove ranges x1.3, no extra call margin): tie with v8 (21.65 vs 21.61, 4v4 600 tables). Not submitted.
- v10 (c-bet bluff 0.55->0.40 HU, turn barrel 0.5->0.4): worse than v8 (21.1 vs 22.2, 4v4 600 tables). Not submitted.
- Final checks of 005 (v8): zoo 150 tables 49.5 (0 substitutions, max 527us); vs v1+v3 copies 80 tables 24.45 (avg 21.6), 1 "hang" (50ms wall) on the loaded machine while max CPU was 575us. Probably a scheduling stall, but check the hang count in the patch-window results.
- Test noise: one entry over 600 tables is about +/-2.7 points (95%), so only gains of ~2+ points show reliably. Run one sim at a time (machine is shared).

## Next ideas
- Same call-EV analysis for flop/turn raises and for our own bluffs (bet EV by bucket).
- EV-based open-shove (fold equity from players behind) instead of the formula.
- Showdown-based reads (what each seat shows after big bets).
