# Team b06 notes

## Strategy

**Summary:** Math-first bot. A custom shortdeck evaluator (base-5 rank-key dict lookup, verified identical to the engine on 30k hands) drives precomputed preflop tables (81 classes: equity vs k random hands + an 81x81 class-vs-class matrix) and postflop equity (time-boxed Monte Carlo vs opponents' estimated ranges on flop/turn, exact enumeration of all opponent combos on the river). Every decision compares range-adjusted equity with pot odds; all-in calls with <=4 players left are priced in ICM points.

**Before the flop:** Opens top ~14% (UTG) to ~50% (SB) of hands by shortdeck equity rank, 2.5bb (3bb from the SB), +1bb per limper; heads-up opens 85% from the SB. Facing a raise it estimates the raiser's range (observed PFR, position; short-stack shoves from a position-aware push formula, widened by the seat's observed jam rate and VPIP; wider short-handed), computes our equity vs that range from the matrix, 3-bets/jams at >=60% equity, calls when realized equity beats pot odds. Below 25bb it re-shoves over a single open when chip EV with fold equity (from the opener's range width) beats calling. At <=13bb effective: push/fold with a range that widens as stacks shrink and as fewer players are left to act.

**After the flop:** Equity vs each opponent's preflop range (raiser tight, callers medium, blinds/limpers any). Value-bets 65-90% pot above a threshold that scales with number of opponents (river +5pts); c-bets the flop as preflop raiser ~55% heads-up, barrels the turn with >=38% equity, rare river bluffs; bluff frequency and value thresholds adapt to each opponent's fold-to-bet rate. Facing a flop/turn bet it subtracts a penalty that grows with bet size and shrinks vs aggressive opponents. Facing a river bet it computes equity vs only the top q of the bettor's range by hand value, with q falling steeply for big bets (0.55 for small bets, ~0.22 for pot-size, 0.12 for overbets) and widening only for very aggressive seats. Raises with >=72% adjusted equity, jams when SPR is low.

**Short stacks and the points table:** Push/fold at <=13bb. Facing all-ins with <=4 players alive, call/fold by exact ICM (Malmuth-Harville over the remaining places' points 100/45/20/8); otherwise chip EV with a small margin plus a penalty for players left behind. Tables between our versions never reach the 200-hand cap (mean ~109 hands), so finishing order, especially 1st, dominates.

**Opponents:** Per-seat VPIP, PFR, postflop aggression (raise vs call), fold-to-bet, preflop jam rate, all with priors. They set range widths, bet penalties, river range fraction, bluff frequency and value thresholds.

**Last change:** No change for T5: 006-de789549 (v8b) keeps playing (T4: 6th at 21.09, all 8 teams within 20.5-22.8, i.e. noise). The T5-window candidate v13 (more bluffing: flop c-bet 0.55->0.65 HU / 0.3->0.4 multiway, turn barrel 0.5->0.6) only tied v8b (21.8 vs 21.4, 4v4, 600 tables), so it was not submitted. Kept for T4 after finishing 2nd in T3 (21.85). Before T3, it stayed on. The one candidate tested in the T3 window (v11, wider opponent postflop ranges with <=4 alive) lost to v8b 20.5 vs 22.8 (4v4, 600 tables), so it was not submitted. v8b's own change, for T2: timing safety only, same strategy as v8. T1's worst call used 790us of the 1ms limit. The river enumeration now uses precomputed per-suit masks instead of building lists on flush boards (identical results on 400 test spots; worst case 362 -> 269us). The Monte Carlo budget is 280us (was 350) with a time check every 8 samples. Smoke p99 326us (was ~500). v8 itself: tighter river calls vs big bets (self-play leak: big river calls won 17% for -6bb each); mixed field 600 tables v8 44.5 vs v6 39.5.

## Versions
- 001-d0c5857a v1: first complete bot. zoo 46.1.
- 002-fab9dff3 v2: HU/short-handed widening, fold-to-bet stats.
- 003-6037990e v3: position-aware shove ranges, jam tracking, fold-equity re-shove, river value thr +0.05.
- 004-38b6f847 v6: v3 with GC-safe evaluator table (dict instead of 1.95M list: full-GC pause 7.7ms -> 1.3ms).
- 005-b15eb3f4 v8: v6 + steal widening (v7) + river big-bet call tightening. T1: rank 3/8, 23.50 (CI 21.3-25.7; leader b02 24.95, all within noise). Places 1st 153, 2nd 108, 3rd 122, 4th 112, 5th 154, 6th 161, 7th 99, 8th 91 per 1000. 0 substitutions; cpu max 790us.
- 006-de789549 v8b: v8 with a faster river path and a 280us MC budget (timing safety). T2: rank 6/8, 20.45 (CI 18.4-22.5). Ranks 2-8 overlap; b02 leads clearly (26.29, also 1st in T1). Places 1st 118, 2nd 120, 3rd 113, 4th 124, 5th 136, 6th 156, 7th 136, 8th 97. Heads-up conversion 1st/(1st+2nd) fell from 59% (T1) to 50%. One call reached 1230us CPU but no timeout was charged. Weighted score after T2: 64.40, rank 3. Also plays T3.
- T3 (006 v8b): rank 2/8, 21.85 (CI 19.7-24.0); b02 1st at 26.22 (their third straight win, clearly ahead), ranks 2-8 within noise. Places 1st 136, 2nd 112, 3rd 113, 4th 116, 5th 144, 6th 160, 7th 112, 8th 106. 0 substitutions, cpu max 610us. Weighted score after T3: 129.94, rank 3. Kept for T4 (only ~10 min of window left).
- Across T1-T3 the most common finishes are 5th/6th (~30% of tables), and heads-up conversion swings 50-59%. Bubble play (5 alive, ICM only at <=4) and HU play remain the main untested levers.
- T4 (006 v8b): rank 6/8, 21.09 (CI 19.0-23.2); the whole field was within 20.5-22.8 (b01 22.75 1st, b02 22.55). Places 1st 137, 2nd 95, 3rd 112, 4th 110, 5th 133, 6th 149, 7th 140, 8th 124. 0 substitutions. Weighted score after T4: 214.32, rank 3.
- v13 (more bluffing) vs v8b: 21.8 vs 21.4 (noise). With v10 (less bluffing, -1.1), bluff frequency looks roughly right as is.
- End of T5 window: zoo health check 50 tables, 48.0 pts (1st), 0 substitutions, max 342us. 006 plays T5 unchanged.
- The v8 vs v8b MC-budget A/B timed out (400 tables took more than 3 min on the loaded machine); still untested.
- v12 idea (push/fold cutoff 13bb -> 16bb): built but its test was declined, so it is untested.
- T4-window localsim check (006 vs copies of 005/003/001, 120 tables): you 19.7, 005 copies 23.2-25.8 (same strategy; noise is +/-6 at 120 tables). 0 substitutions, max 452us. Possible follow-up: does the 280us MC budget (vs 350us in v8) cost anything? Needs a 1000-table A/B to see.
- v11 (not submitted): postflop opponent ranges floored wider when <=4 alive (HU raiser 0.7 / caller 0.8). Lost to v8b 20.5 vs 22.8: calling more short-handed hurts vs value-heavy bettors.

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
