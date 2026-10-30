# Team notes (b02)

## Submissions
- 001-88cd815a v1 chip-EV push/fold + heuristic postflop
- 002-2d98ffbf v4 ICM blend, blind-cost fold adjustment, shover position factor
- 003-346d23da v6 + BB defense vs small raises, river call tightening, adaptive shove-call multiplier
- 004-29382db0 v7 + ICM weight ramps to 1.0 in last 20 hands, per-seat fold-to-our-bet exploit, flush-board penalty
- 005-7e26b93f v9 + looseness clamp 3 -> 6 (maniacs that raise >45% get much wider ranges)
- 006-1e381b32 v11 = v9 + postflop: +0.12 strength penalty when an opponent raises OUR bet on the
  same street (bots rarely bluff-raise). Leak breakdown, mixed field seed 93, 250 tables: river
  call-downs after our aggression -511bb -> -219bb, total +7496bb -> +7871bb, points 48.8 -> 51.1;
  zoo seed 32: 59.3 -> 57.8 (noise +-4); v4-clone field seed 81: 29.6 (v9 29.5) = no regression;
  vs 7x v9 (005) seed 111 700 tables: 31.87 (break-even 31.875).
- 007-e2db5c55 v12 = v11 + (a) full-house strength relative to board (`_boat_strength`): boat that is
  board trips + our pair with a higher board card -> 0.50 (was 0.97), board-trips + top pair 0.84,
  boat under a higher board pair 0.70; (b) once our bet is raised on a street, re-raise only with
  s >= 0.96. Motivated by T1 sample hand: QQ on Js7hAsJcJd, river bet-raise-reshove, lost 2000 on hand 1.
  Tests: zoo s121 56.2 / s131 59.0 (v11 59.1 / 56.6), vs v11 copies 31.4 = neutral.  <- ACTIVE for T2

## T1 result (v11, 006): rank 1/8, 34.90 pts/table (b04 33.99, b06 33.95, b08 32.01, others 29.7-30.5)
- places 1st..8th per 1000: 146 129 132 138 139 127 94.5 94.5 -> we survive well but win only 14.6%.
- 0 cap survivals: tables always play down to one winner before hand 200 (hand-cap ICM irrelevant).
- Field VPIP 21-28%, PFR 15-22%; we are tightest (19/14). Opponents open 2.3-3bb, c-bet 1/2-2/3 pot.
- Candidate NOT submitted (tools/cand_v14): rank-aware flush strength on 4-flush boards and one-card
  straights beaten by a single higher card (0.66). Zoo s121 56.5 / s131 53.0, vs v11 copies 31.2 ->
  no evidence of gain (zoo bots overplay weak hands, so it may still help vs the real field).
- 4-seed zoo comparison (250 tables each, seeds 121/131/151/161): v12 56.2/59.0/57.6/57.2 = 57.5;
  cand_v14 56.5/53.0/52.2/58.2 = 55.0 -> v14 rejected. Use 4 seeds for future A/B tests.
- v12 vs mixed field of 005/006 copies (seed 171, 700 tables): 31.99 (break-even 31.875), 0 subs.
- Not submitted before T2: HU flop c-bet 0.6 -> 0.75 (tools/cand_v17): zoo 4 seeds 56.4/55.3/59.5/59.4
  = 57.6 vs 57.5; vs v11 copies 32.4 vs 31.4 -> within noise; plausible small plus, retry with more tables.
- Also rejected before T2: ICM_W 0.35 (zoo 4 seeds 54.1/57.7/58.0/57.7 = 56.9 vs 57.5; vs v11 copies 30.7).
- Also rejected before T2: heads-up wider SB opens (75%) + BB defence need+0.08 when 2 alive:
  zoo s121 54.6 / s131 57.2 (v12 56.2 / 59.0), vs v11 copies 31.6 (v12 31.4).

## Approach
- `bot/pre.json`: precomputed 169x169 preflop equity matrix (MC, 400 samples/pair, tools/precompute.py)
  reduced to `eqr[class][p]` = equity vs top-p% range (p=0..100), `pct[class]` = class percentile
  by equity vs random, `mw` multiway equity, `icm[n][k]` = my ICM equity with n players, my chip
  share k/200, others equal (tools/icm_table.py, points 100/60/40/25/15/10/5/0).
  Rebuild: python tools/precompute.py 400; python tools/build_tables.py; python tools/icm_table.py
- Preflop:
  - Unopened & eff stack <= 14bb: shove if ICM-EV(shove) > ICM-EV(fold). Callers modelled with
    `call_range(bb depth)` (BB x1.35, last-to-act x1.45, x looseness^.5, x adaptive call_mult =
    observed/expected calls of our shoves this table). Fold EV reduced by
    BLIND_COST*(sb+bb)*min(1,3/n) chips (blinds keep coming), faded in last 8 hands.
  - Deeper: open-raise top OPEN_PCT[players behind] (2.5bb, 3bb SB, 2.2bb if <=25bb).
  - Facing a raise: estimate raiser range (open 20%, 3bet 7%, 4bet 3.5%, shove by depth via
    `shove_range`, x position factor for late openers {1 behind: 2.2, 2: 1.45, 3: 1.15}, x per-seat
    looseness from observed PFR). All-in / big raise -> ICM call/fold. eff<=25bb -> ICM re-shove EV,
    flat cheap good hands, BB defends vs small raises. Deep -> 3bet if equity vs range >= .62.
- Postflop: heuristic strength (made-hand class relative to board + draw bonus), multiway
  exponent, value bet >=.78/.6, semi-bluff draws, flop c-bet HU (25%/60%/85% vs station/normal/folder),
  rare river bluff; facing bets: equity vs pot odds with penalties for bet size and later streets;
  committed spots use ICM.
- ICM_W = 0.5 blend of ICM and chip-linear points (1.0 and 0.0 both tested slightly worse).

## Testing
- tools/sim.py = localsim with --bot DIR. tools/dbgbot (python tools/mkdbg.py) = copy without
  try/except, to surface errors. tools/probe.py push/call ranges; tools/probe_post.py postflop spots.
- tools/anabot + tools/agg.py: per-situation chip results (leak finding).
- vs zoo ~53-59 pts/table (1st). Self-play/mixed fields: all variants within noise (+-2 at 1000 tables).
- Tried and rejected: PUSH_DEPTH 20 (no gain), wider steal ranges (no gain), stronger top-pair
  kicker scaling (-2, reverted), BLIND_COST 0.45 (zoo 56 vs 59), counting limpers as callers in
  shove EV with x0.7 (zoo 55 vs 59, mixed equal) -> reverted; might retry with smaller factor.
- Reference numbers (same seeds): zoo seed 32 300 tables: v9 59.3; mixed field seed 91 700 tables
  (snap_v4,montecarlo,pot_odds,nit,maniac,minraiser,snap_v6): v7 48.5; v4-clone field seed 81
  1000 tables: v4 30.1, v9 29.5 (all within noise).
- Snapshots of every version in tools/snap_v4, snap_v5, snap_v6, snap_v7, snap_v9, snap_v11 (= current build).
- Leak finder: python tools/mkana.py; rm -f tools/ana_log.jsonl; python tools/sim.py --bot tools/anabot ...;
  python tools/agg.py tools/ana_log.jsonl (net bb by situation; biggest remaining postflop losses are
  folds after our bet gets raised, i.e. c-bet/semi-bluff then fold).
- Also rejected: tighter deep-stack opens (x0.7 when eff>50bb): zoo 55.6 vs 59.3.
- Also rejected: multiway all-in equity e**(1+.75*already_in)*.95**behind instead of e*.92**extra
  (zoo 57.1 vs 59.3, mixed 46.5 vs 48.5).

## Leak breakdown of v11 vs zoo (seed 121, 250 tables, 59.1 pts/table, +13.7k bb total)
- Calling preflop, then folding the flop: n=965, -1.55bb each (-1496bb) -> flat calls / BB defence
  cost. TRIED tightening BB defence (need+0.14/0.15 -> +0.18/0.19): zoo seed 121 53.2 vs 59.1 pts,
  +11.1k vs +13.7k bb -> rejected. TRIED widening (+0.10/0.11): 53.6 pts, +9.4k bb -> rejected too.
  Current BB-defence margins (+0.14/+0.15) look locally best; leave them.
- v11 (006) zoo baselines for future A/B: seed 121 250 tables 59.1; seed 131 250 tables 56.6.
  Single-seed differences of ~5 pts happen from card-flow alone; compare on 2+ seeds.
- Folding the turn/river after only checking/calling: -2.25 / -2.46bb each.
- Betting, then folding to a raise (failed bluffs/semi-bluffs): flop -5.6, turn -6.7, river -8.3bb each,
  ~145 hands, about -1000bb -> candidate: fewer turn/river bluffs vs non-folders, smaller bluff sizes.

## T2 result (v12, 007): rank 2/8, 33.84 pts/table (b06 36.36 first; b05 32.15, b08 32.08, b04 31.59)
- places 1st..8th: 135 142 131 113 128 119 128 104 -> more 7th/8th than T1 (94.5 each); within noise?
- 0 subs, 0 cap survivals. T2 sample hands (hands 1-10) show no mistake of ours (we folded the big pots).
- Before T3 kept v12. Rejected: adaptive steal multiplier from our uncontested-open rate (tools/cand_v18):
  zoo 4 seeds 57.6/53.2/56.6/58.4 = 56.5 vs v12 57.5; vs v12 copies seed 141: 30.2 vs v12 31.0.
- Rejected again: c-bet 0.75 (cand_v17) vs v12 copies seed 141: 31.1 (v12 31.0); zoo seed 171: 54.6
  vs v12 56.4. Total over all tests ~ neutral -> not worth submitting.
- Machine load hit ~158 near the end of the T3 window: sims stall, so start tests early in a window.

## Known weaknesses
- Postflop is heuristic, no range reading; texture handling crude (straights on 4-straight boards
  overvalued; board flush vs our higher flush card treated as air).
- Call-range assumptions for opponents are guesses; adaptation only via PFR / shove calls / fold-to-bet.

## Next steps (patch windows)
- Look at real tournament results: if we bust early often -> tighten calls; if we blind out -> widen pushes.
- Track opponents' postflop aggression and showdown strength to adjust call-downs.
