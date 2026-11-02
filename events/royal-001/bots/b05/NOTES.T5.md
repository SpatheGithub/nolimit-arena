## Strategy

**Summary:** Math-first bot for royal hold'em (20-card deck, 4-card board). All equities are precomputed exactly (rank-only, straight flushes ignored except a live check) into `bot/tables.json`: preflop HU matrix (15x15 rank classes), equity vs top-q ranges, flop/turn equity vs random and vs top 50/25/10% of holdings. Decisions compare range-adjusted equity to pot odds; big all-in calls are priced in tournament points with a 3-place ICM (100/25/5).

**Before the flop:** Hands ranked by HU equity (AA .69, KK .61, AK .60, AQ .57, AJ/QQ/KQ ~.53, ... TT .37 worst). Opens top 26% (early) to 62% (SB) of hands, 2.5bb + 1bb per limper; folds weak hands. Facing a raise: estimates raiser's range from their observed PFR, calls when equity vs range beats pot odds + margin (multiway penalty only for players who put chips in voluntarily), 3-bets/jams top ~12% (AA, KK, AK). No light re-steals (tested worse). At <=13bb effective: push/fold by chip-EV of a shove vs assumed calling ranges (15-40%); equities are so compressed in royal that wide shoves are +EV.

**After the flop:** Equity vs a range implied by bet size (small bet -> top 50%, pot -> top 25%, overbet -> top 10%), widened vs aggressive seats. Value-bets ~70-85% pot when ahead of the top-50% range, raises with equity >= .72, semi-bluffs/bluffs heads-up at low frequency (more as preflop aggressor). With 3 or fewer players left at the table, bluff frequency x1.5 (cap 70%), still scaled down vs seats that rarely fold.

**Short stacks and the points table:** push/fold at <=13bb; calls committing >=50% of stack go through ICM (fold vs call EV in points, bust = place points). Heads-up (1st 100 vs 2nd 25), the shove EV assumes the caller calls with >=50% of hands. Facing a heads-up raise or shove, the raiser's range is their own heads-up SB raise rate (prior 55%, clipped 30-100%) instead of full-table PFR. 3-handed short shoves (<15bb) are read as top >=50%.

**Opponents:** tracks per-seat VPIP, PFR, heads-up SB raise rate, postflop aggression (bets vs calls/checks) and fold-to-bet, shrunk to priors; used to size raiser ranges, widen calls vs aggressive bettors, bluff more vs folders (ftb>.5), stop bluffing and value-bet thinner/bigger vs stations (ftb<.3).

**Last change:** 006-51b23ec2 = 005 + short-handed bluffing (variants/shbluff): when <=3 players remain, postflop bluff frequency x1.5 (cap .7). Test vs 005 copies (split field, 800 tables/seed): seeds 71-79 = +1.4/+1.1/-0.7/-1.0/+1.7/-0.3/+1.5/+0.5/+1.2, avg +0.6 (~1.4-1.8 SE). T3 (005) showed HU conversion up to 55% (156 1st / 126 2nd) from 48% in T1-T2, so the endgame is where points move.

**Previous change:** 005-95ee62d4 (= variants/hu3) adds heads-up range modelling on top of 004. Reason: T1+T2 show we reach heads-up in ~30% of tables but win only 48.4% of those (285/589). 004 read heads-up shoves with the full-table PFR prior (~22-35%), so it folded hands like AQ/AJ/QQ that are ahead of a wide shover. Split-field self-play test (you + 4x 004 vs 3x hu3, 800 tables each): seeds 61/62/63 = +2.2/-0.6/-0.4, avg +0.4. That is neutral vs itself; the change is submitted because it fixes a modelling error, not on that test.

## Submissions
- 001-8ab9709b v1; 002-db29a180 AA-vs-shove fix + ftb; 003-ae9ebe7d + re-steal jam (played T1);
  004-db29a180 = v2 logic again (played T2); 005-95ee62d4 = 004 + heads-up range model (played T3);
  006-51b23ec2 = 005 + short-handed bluff x1.5 (played T4; kept for T5).

## T4 result (played 006)
- RANK 1/8, 21.00 ± 2.29 (b03 18.64, b08 17.77). Places 1st 172, 2nd 127, 3rd 126, 4th 135, 5th 129, 6th 112, 7th 98, 8th 101.
- HU conversion 57.5% (T3 55.3%, T1-T2 48.4%). Weighted total 199.08, rank 1.
- Score per version: 003 18.52 -> 004 19.02 -> 005 19.50 -> 006 21.00.

## Window 5 tests (split field vs 006 control, 800 tables/seed, ~55 s each)
- variants/bl2 (bluff x2.0, cap .75, when <=3 alive): seeds 111-116 = +0.5/+1.65/-1.7/+1.3/-0.6/-0.2 (avg +0.15). Neutral; not submitted.
  The x1.5 in 006 looks close to the optimum.
- variants/bl4 (bluff x1.5 from <=4 alive): seed 111 = +0.1. Not submitted.
- variants/shvalue (HU-or-3-handed value-bet threshold .58 -> .54): seeds 111/112 = -0.7/+1.0 (avg +0.2). Not submitted.
- variants/wide6 (006 + late opens SB .75/BTN .60/CO .45): seeds 131/132 = -1.5/-1.6. REJECTED.
- variants/tight6 (006 + late opens SB .55/BTN .42/CO .33): seeds 131/132 = -0.8/-1.1. REJECTED.
  The current opening ranges (.62/.48/.38) sit at a local optimum vs this field type.
- variants/pf11 (push/fold threshold 13bb -> 11bb): seeds 141/142 = -0.1/-0.2 (neutral). With pf18 at -0.4, 13bb looks right.
- Mixed field (you=006, 001, 003, 004, 005, nit, pot_odds, maniac; seed 121, 600 tables): 005 24.6, 006 23.6, 003 21.3,
  004 21.1, 001 19.0, nit 10.6, maniac 6.2, pot_odds 3.7. The later versions are best, matching the real-tournament trend.
- Decision: keep 006 (leading). Only submit changes with avg >= +1 over >= 4 seeds and no big negative seed.

## T3 result (played 005)
- Rank 2/8, 19.50 ± 2.20 (b08 20.48, b03 17.27). Places 1st 156, 2nd 126, 3rd 150, 4th 133, 5th 114, 6th 111, 7th 111, 8th 99.
- HU conversion 55.3% (vs 48.4% in T1+T2). Weighted total 115.06, rank 2.

## Window 4 tests (split field vs 006 control, 800 tables/seed; machine slower now, ~70-100 s per run)
- variants/huopen (HU SB opens .85 when deep, 3-handed BTN .60): seeds 81/82/83 = -0.7/+0.3/+0.7 (avg +0.1). Not submitted.
- variants/pfvpip (push/fold: each player-to-act's calling range scaled by their VPIP/.35, clipped .6-1.6):
  seeds 81/82 = -0.5/+0.8 (avg +0.2). Mixed field (006, pfvpip, nit, maniac; seed 91, 400 tables): 006 avg 21.3 vs
  pfvpip 19.4 (-1.9). Not submitted.
- 006-51b23ec2 stays active for T4. The machine is heavily loaded late in this window (400 mixed tables took 184 s).
- variants/reshove (after we open, a re-shove <=25bb is read as top >=22% instead of ~10%): UNTESTED. Runs of 500 and
  250 tables timed out on the overloaded machine. A 100-table probe (seed 102, 90 s) gave 006 17.0 vs reshove 15.1:
  pure noise at that size. Seed 103 (150 tables): 006 16.24 vs reshove 16.26 (even). Seed 104 (400 tables): 006 17.17
  vs reshove 14.72 (-2.45). REJECTED. Partly by construction: our copies only re-shove AA/KK/AK, so calling wider loses vs them.
  Only revisit with evidence that real opponents re-shove wide.
- Health check of active 006 vs zoo (seed 1, 300 tables): 47.2 ± 5.5 (earlier versions 46-50), 0 substitutions, p99 100 µs.

## T2 result (played 004)
- Rank 2/8, 19.02 ± 2.13 (b08 21.52, b01 18.34). Places 1st 144, 2nd 154, 3rd 154, 4th 125 ... 8th 97.
- Weighted total after T2: 56.56, rank 2. Sample hands are only hands 1-10 of 4 tables, so they say nothing about the endgame.

## Window 3 tests (split field vs 004 control, 800 tables)
- variants/hu2 (fixed wide HU/3-handed ranges + HU shove caller c>=.5): seeds 61/62/63 = +1.4/-0.9/-0.35 (avg 0).
- variants/hu3 (adaptive HU SB raise-rate range + c>=.5): +2.2/-0.6/-0.4 (avg +0.4). Better than hu2 on every seed; submitted as 005.
- After submitting: zoo seed 1 (300 tables): 005 = 46.6 ± 5.5 (v2 49.6, v3 46.2): no regression, 0 substitutions.
  Seed 64 (4x 005 incl. you vs 4x 004): 16.23 vs 16.28. Seed 65 (2x 004, 2x 005 + you, 2 maniac, nit): 004 20.45 vs 005 20.6 (excl. you).
  005 is neutral in self-play across 6 runs; kept for T3 on modelling grounds.
- variants/shbluff (005 + bluff freq x1.5, cap .7, when <=3 alive; still scaled by fold-to-bet): vs 005 copies,
  seeds 71-79 = +1.4/+1.1/-0.7/-1.0/+1.7/-0.3/+1.5/+0.5/+1.2 (avg +0.6, ~1.8 SE over 9 seeds; ~1.4 SE excluding
  the low-scoring "you" seat). Not submitted for T3 (too close to the deadline). NEXT WINDOW: submit shbluff early
  (copy variants/shbluff/agent.py to bot/, run check_bot) unless T3 data shows a reason not to.
- Pattern so far: every variant's first-seed edge fades toward 0. Use >=4 seeds (800 tables each) before submitting.
- Next ideas: retest shbluff; 3-handed/HU postflop aggression; check T3 places to see if 1st/2nd conversion moved (T1+T2: 48.4%).

## T1 result (played 003)
- Rank 2/8, 18.52 ± 2.12 pts/table (b08 20.45 first; b06 18.52). Places 1st 14.1%, 2nd 15.0%, 3rd 13.5%, rest ~11-12%.
- 0 substitutions in 140,981 decisions; p99 50 µs.
- Field VPIP/PFR: b08 45/26 (winner, loose-aggressive), b06 35/21, b01 32/19, others tight (22-26% VPIP). We were 37/16 (lots of flatting).

## Patch-window tests (before T2), all 400 tables seed 41, field = you + 3x004 + nit/threshold/pot_odds/checkfold
- Wider late opens (SB .75, BTN .60, CO .45): you 29.2 vs 004 copies avg 29.2. No gain; not submitted.
- HU SB open 100% + 3-handed BTN .70: you 27.8 vs copies avg 29.6. No gain; not submitted.
- Softer calls vs big bets (pot bet: .7*eq50+.3*eq25; overbet: .4/.4/.2): you 26.9 vs copies avg 29.8. No gain; not submitted.
- Tighter calls vs big bets (pot bet: .3*eq50+.7*eq25; overbet: .3*eq25+.7*eq10): you 27.7 vs copies avg 29.8. No gain.
- Caveat: every variant scored 27-29 in the "you" seat vs ~29.5 for 004 copies at seed 41, so this setup looks seat-biased.
  CONTROL (unchanged 004 as "you", seed 41): 27.5, which confirms the seat bias. Vs control: wider opens +1.7, HU 100% +0.3,
  softer calls -0.6, tighter calls +0.2. All are noise (±4). Wider late opens is the best candidate to retest with more seeds.
  Next window: always compare against a control run on the same seeds and use several seeds.

## Window 2 tests (split field: you + 4x 004 control vs 3x variant at the same tables; variants in variants/)
- Better design: control and variant share the same tables, so seat and deal effects cancel. 600-800 tables take ~35-45 s.
- variants/wide (late opens SB .75/BTN .60/CO .45): seed 51 control 16.0 vs wide 16.7; seed 52 control 16.4 vs wide 16.0;
  seed 56 control 15.9 vs wide 16.8. About +0.4 over 3 seeds, still noise. Best candidate: retest at the start of the next window.
- variants/hu (HU SB opens 100%, 3-handed BTN .70): seed 53 control 16.6 vs hu 15.7. No gain.
- variants/pf18 (push/fold threshold 13bb -> 18bb): seed 54 control 16.4 vs pf18 16.0. No gain.
- variants/thin (value-bet threshold .58 -> .54): seed 55 control 16.26 vs thin 16.24. No difference.
- Decision: keep 004-db29a180. No tested tweak beats it beyond noise; the remaining edge has to come from new ideas, not from tuning these ranges.
  This field (v2 copies + weak house bots) also differs from the real one; differences under ~4 pts are noise.
- Next ideas: per-opponent calling ranges in push/fold (from VPIP); c-bet frequency vs tight seats; review HU endgame with longer runs.

## Known weaknesses / next steps
- Turn vs pot-size shove: range model (0.5*eq50+0.5*eq25) folds straights on paired boards; could be too tight vs loose shovers.
- KK folds to an unknown 100bb shove (range prior top ~16% is AA-heavy); revisit if opponents shove wide.
- Self-play A/B needs >1000 tables to resolve ~2 pt differences; use zoo + submissions mixes in patch windows.
- Ideas: per-opponent calling-range estimates in push/fold; bet sizing by SPR; check-raise traps with full houses.

## Notes

- Evaluator verified vs engine: only straight-flush differences (0.1% of showdowns).
- Royal facts: min hand is two pair; only one straight (TJQKA, all straights tie -> many chops); pairs gain multiway (full houses).
