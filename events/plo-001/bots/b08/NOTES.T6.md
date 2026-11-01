# Team b08 notes (PLO, 8-max SNG, 1 ms/act)

## Strategy

**Summary.** Pot-limit Omaha bot built on precomputed hand tables: for every board rank pattern and
hole rank pair it knows the best non-flush hand, so in ~0.1-0.3 ms it counts how many opponent holdings beat
it, averaged over all turn/river rank runouts, with flushes handled separately. That equity vs a random hand is
then narrowed to each opponent's likely range. Style: tight preflop, very aggressive postflop when checked to,
disciplined when facing bets, push/fold when short. Results: T1 8th (too passive) -> T2 5th -> T3 2nd -> T4 2nd
-> T5 3rd (32.2; weighted rank 3 after T5).

**Before the flop.** A heuristic 4-card score (pairs, A-high suits, double-suitedness, connectivity, high cards,
dangler penalty) is mapped to a percentile. Deep (>14 BB effective): open pot-size with top ~13% early up to
~40% on the button (wider as players bust, wider vs tight blinds), 3-bet top ~3.5% (more vs loose raisers),
flat-call raises only with top ~8-15% (call_mult 0.6), never open-limp from the small blind when deep,
4-bet only top ~1.5-3.5%. Raise-or-fold style: VPIP ~25%, PFR ~21% locally.

**After the flop.** analyze() gives equity vs one random hand; each opponent's range is modelled as the top t
fraction of hands (callers 0.6, preflop raiser 0.5; narrowed by earlier bets/calls and by the size of the
current bet, widened for small bets and short all-ins, scaled by their observed aggression), eq_vs_range =
eq^(1/t), multiplied over opponents. When checked to: bet almost always (val_eq 0.05) - weak/thin hands half
pot, normal value 0.75 pot (0.7 river), near-nuts pot; low SPR (<=1.8) shove with eq_r >= 0.45; c-bet/bluff
0.6 pot when opponents' fold-to-bet is high. Facing a bet: call if eq_r beats pot odds (small margin, better
price for draws/tiny bets), pot-raise only with eq_r >= 0.72 and strong made hands.

**Short stacks and the points table.** Tables never reach the 200-hand cap, so places come from bust order
(100/60/40/25/15/10/5/0). <=14 BB: push/fold - pot-raise (max) with ranges that widen with fewer players
behind and shorter stacks; call shoves by a 20x20 Monte-Carlo preflop equity matrix (hero percentile vs
villain range width), cut x0.72 per extra player. ICM-style risk premium: +0.03 equity needed to call off
a big part of the stack with 3+ players left (x0.3 when we cover the bettor, 0 heads-up).

**Opponents.** Per-seat counts from every hand history: VPIP, PFR, postflop aggression, fold-vs-bet. Used to
widen/narrow bettors' ranges (aggression), raisers' ranges preflop (PFR), steals vs tight blinds (VPIP) and
bluff frequency (fold-vs-bet). Priors are mildly aggressive so unknown bots aren't over-respected.

**Last change.** 018 (plays T6): tighter preflop flat-calling (call_mult 1.0 -> 0.6) and no deep small-blind
limps (sb_limp 0). Motivation: the T5 leader b05 had VPIP 23% / PFR 17% vs our 26% / 17% (we flat-called more).
Three local runs vs 017 copies (800 tables each): +1.4, +0.1, +1.4 (avg +1.0, never negative).
Before that: 017 = 016 + warm-up of all numpy/evaluator paths at import and in __init__ (T4 had 2 rare
1.3 ms timeouts; decisions unchanged; T5 still had 2, max 1.27 ms - likely GC, negligible). 016 itself: low-SPR commit threshold 0.35 -> 0.45 (4 local runs vs 015:
+2.1, 0.0, +1.2, -0.3). Tested and rejected for T5 (each vs 017 copies, 700-800 tables): commit 0.55
(+0.5); multiway value threshold mw_val 0.3 (+0.6); AA-only 4/5-bets when >40 BB deep (-0.4, -0.9, though
logs show JJxx/QQxx 5-bet shoves at 100 BB as an early-bust source - may still help vs tighter real 4-bettors);
icm 0.06 (-0.8); bluff_frac 0.8 (+1.4, +0.1, -1.4 -> avg 0.0, no effect; dropped).
bot/ behaves exactly like 017 (mw_val 0.0, deep_aa_bb 9999 disable the new code paths; bluff_frac 0.6).

## T5 RESULT: rank 3/8, 32.23 (b05 35.98, b06 32.73). 7th+8th 27.6%. 2 timeouts (max 1.27 ms).
- 018: call_mult 0.6 + sb_limp 0 (see Last change).
- Rejected after 018 (vs 018 copies, 800 tables): call_mult 0.4 (+0.5, neutral); no SB completes in
  push/fold mode sb_limp_pf 0 (+1.1 then -2.6). bot/ == 018 (sb_limp_pf 1 keeps the push/fold SB complete).
- Zoo check (500 tables, seed 2): 018 49.9 (014 53.4, 010 58.7). Zoo score falls as we tighten/aggress, but
  the zoo's random/checkfold/minraiser bots aren't in the real field; bot-like mirror tests + T3-T5 ranks
  (2,2,3) are the better guide, so 018 kept for T6.
- Weak-bot field check (v17x2, v16, maniac, pot_odds, minraiser, montecarlo; 700 tables): 018 43.5 vs 017 avg
  44.7 (-1.2). All four 018-vs-017 runs: +1.4, +0.1, +1.4, -1.2 (avg +0.4) -> roughly equal; kept 018.
  Fifth run (650 tables, 2x018 vs 3x017): -0.8 -> five-run avg +0.2: 018 == 017 within noise. Kept 018.

## T4 RESULT: rank 2/8, 34.22 (b05 34.28). 2 timeouts (cpu max 1.33 ms) -> 017 warm-up fix.

## T3 RESULT: rank 2/8, 34.47 (b05 35.54). 1st 15.7% but 7th+8th 24.5% (early busts). aggression 7.75.
- 015: commit_eq 0.15 -> 0.35 (low-SPR shove needs more equity; fewer early busts): +2.1/+0.5 vs 014.
  014 beat 013 again by ~3 in both runs (val_eq 0.05 confirmed). Later runs: 015 copies beat 014 by ~2.6.
- Rejected after 015: spr_commit 1.2 (+0.2, neutral).
- 016: commit_eq 0.45 (three runs vs 015 copies: +2.1, 0.0, +1.2; never negative). bot/ == 016.
  If T4 is worse than T3, fall back to 015 (commit 0.35).
  Untested next: commit_eq 0.55 (trend 0.15->0.35->0.45 positive). bot/ verified == 016 (commit 0.45).
  4th run 016 vs 015 copies (450 tables): -0.3 -> overall avg +0.75 over 4 runs; 016 ~= 015, kept 016. Local machine is loaded: localsim shows occasional wall-clock "hangs"
  (CPU max < 1 ms); T3 had 0 timeouts, so ignore unless the referee reports them.

## T2 RESULT: rank 5/8, 30.87 (1st 9.9%), aggression 5.1, wtsd 4.7%. 1 timeout (cpu spike 1.75 ms, rare).
- 012: val_eq 0.12 (two runs +4.4/+5.3 vs 011). 013: thin value bets (val_eq<0.5) sized 0.5 pot instead of
  0.75 (thin_frac; +2.0/+2.3 vs 012). Tried call_disc 0.85 (call more vs bets): neutral -> off (1.0).
- Rejected after 013 (each one 700-800 table run vs 013 copies): thin 0.35 + bluff 0.4 sizing -3.0;
  open_mult 1.2 -0.7; raise_eq 0.8 -1.4; push_add 0.15 -1.2. bot/ == 013 behaviour (P values restored).
- 014: val_eq 0.05 (bet ~always when checked to; weak hands at 0.5 pot): +3.0 vs 013 copies (one 650-table
  run). If T3 drops vs T2, revert to 013 (val_eq 0.12). bot/ == 014.
  Confirmation run (600 tables, maniac+station in field): 014 42.8 vs 013 copies avg 41.1 (+1.7) -> 014 is
  at least not worse; combined with first run ~+2.3.
  Zoo sanity (450 tables, seed 2): 014 53.4 vs 010 58.7 / v3-v7 ~57 -> betting ~always costs a bit vs the
  house zoo (checkfold/random/stations). If T3 is worse than T2, 013 (val_eq 0.12) is the safer fallback.
- Parameter space around 013 looks locally flat; next gains need new logic (e.g. multiway betting,
  turn/river barrel plans, opponent-specific exploitation of the field's T-stats, exact ICM).

## T1 RESULT: rank 8/8, 24.43 pts/table (1st only 4.7%, wtsd 5%, postflop aggression 2.6) -> far too PASSIVE.
- Lesson: local tests vs house bots / own copies hid it. A self-variant with aggressive P (val_eq 0.42,
  bluff 1.0, commit 0.25) beat v7/v8 by +5.5 pts in a mixed field; more aggression kept winning:
  aggmax (val_eq 0.35, bluff 1.0, commit_eq 0.2) 43.2 vs v8 36.2 (with pot_odds station + nit present).
- 008: softer range narrowing for bettors/callers (af prior 0.5, raiser t 0.5, bet mult 0.45+0.6a,
  call_narrow 0.92). Neutral locally. 009: aggmax P values (val_eq 0.35, bluff 1.0, commit_eq 0.2).
- Always test candidates against an AGGRESSIVE self-variant (tools/mkvar.py aggro ...) not just house bots.
- 010: val_eq 0.28, commit_eq 0.15 (agg2): +2.8 and +1.4 vs v9 copies in two runs; v9 beat v8 by ~6.
- Tried raise_eq 0.6 (value-raise facing bets more often): -3.9 vs v10 copies -> rejected; bot/ keeps
  raise_eq 0.72 (identical to 010). Aggression gain is in BETTING when checked to, not in raising bets.
- Next ideas: c-bet/bluff sizing, turn/river barrels, bet sizing by eq (smaller with medium hands).
- Sanity: v10-equivalent vs zoo (500 tables, seed 2) 58.7 (v3-v7 were ~57): aggression did not hurt vs house bots.
- 011: val_eq 0.20 (+4.3 vs v10 copies, one 600-table run). Trend monotonic so far: 0.62->0.42->0.35->0.28->0.20
  all better. Next window: try 0.12 / always-bet-when-checked-to, and bet SIZING (currently 0.75 pot / 0.7 river).
- After 011: val_eq 0.12 scored +4.4 vs 011 copies (450 tables, one run). bot/ NOW HOLDS val_eq 0.12 (candidate,
  NOT yet submitted; 011 = val_eq 0.20). Second run (350 tables, maniac in field): 45.8 vs 011 copies avg 40.5
  (+5.3). Two positive runs -> run check_bot and submit it at the start of the next window.

## Submissions
- 001 template (safety). 002 first real bot. 003 bet-size-aware ranges + pair-score fix (zoo 50 -> 57).
- 004 pot-odds fix for tiny bets/all-ins + caller-range narrowing. 005 push_add=0.08 (wider short-stack pushes).
- 006 icm=0.03: ICM-style risk premium (+0.03 needed equity, x0.7 at 3-handed, x0.3 when we cover, 0 heads-up)
  on calls that risk a big part of the stack (runs: +2.3, +0.35, +1.1 vs v5).
- 007 low-SPR commit: spr_commit 1.3->1.8, commit_eq 0.42->0.35 (two runs: +1.3, +1.55 vs v6).

## Approach
- `bot/evalcore.py`: engine-identical 5-card evaluator (house `_common.py` Ranker, standard order).
- `bot/ranktab.npz` (`tools/precompute.py`, ~2 s): for every board rank-multiset of size 3/4/5 and every hole
  rank pair (91), best NON-flush value with exactly 2 hole + 3 board. Counting opponent 2-card combos that beat
  us is a numpy compare; flop/turn enumerate all rank runouts (91 / 13 river rows).
- `analyze()` -> equity vs one random 4-card hand: p = share of 2-card combos beating us, win ≈ (1-p)^6,
  averaged over runouts; flushes exact on the current board, probabilistic for the future (flush-draw nutness,
  opponent flush factor). ~100-170 us.
- Range model: eq_vs_range = eq ** (1/t); t = continuing fraction: blind 0.8, caller 0.55, raiser 0.45,
  x(0.75+0.3*aggr) per earlier-street raise, x0.85 per earlier-street call, current bet scaled by aggression
  and SOFTENED by bet size (small bets / short all-ins keep wide ranges). Multiway = product.
- Preflop: heuristic 4-card score -> percentile (6000 random hands sampled at import).
  `bot/preeq.npy` (`tools/preeq.py`, 2.5M MC matchups, 60 s): 20x20 all-in equity by hero/villain percentile
  bucket; used for push/fold call decisions (eq vs top-w range, x0.72 per extra player).
- Deep (>14 BB eff): position open ranges with pot raises, 3-bet top ~3.5%, percentile call thresholds.
  <=14 BB: push/fold (pot-raise max), opens widen with fewer players behind, push_add=0.08.
- Postflop: value raise eq_r>=0.72, call if eq_r >= pot odds (+0.02 unless odds<0.2, then 0.85*odds),
  bet if eq_r>=0.62, low-SPR commit, semi-bluff draws, c-bet/bluff by observed fold-vs-bet.

## Findings (localsim, 1000 tables, noise between identical copies ~±2)
- Tables NEVER reach the 200-hand cap (cap_survivals 0): ICM-at-cap irrelevant; places come from busts.
  Points sum is 255/table (avg 31.9).
- Wider pushes (+0.08) won ~+2 in three separate runs. pf_bb=18 worse (~-3). pf_bb=10, looser opens,
  more bluffs, tighter calls: no clear effect.
- Equity-matrix-priced preflop defense (calling more in BB/short-handed) was WORSE (~-2.7): keep tight.
- Biggest losses now are short-stack preflop coolers and +EV calls vs maniacs.

## Tools
- `tools/mkvar.py name key=val` copies bot to tools/vars/name with P overrides (for localsim --opponents).
- `tools/sim.py opps tables seed` place distributions; `tools/logsim.py opps tables seed N [maxbb]` prints our
  N biggest losing hands (optionally only postflop hands with bb <= maxbb).

## Known weaknesses / next
- ICM premium is a flat approximation; exact ICM (kit/icm.py, fast for <=5 players) for all-in calls/pushes
  is the principled next step.
- Preflop percentile is heuristic (rundowns slightly undervalued vs pairs); could rank by preeq-style MC.
- 4-card opponent approximated by 6 independent 2-card combos.
- Heads-up play uses generic thresholds; 1st vs 2nd is worth 40 points, worth a dedicated HU look
  (logsim filtered to 2 alive).
- Final regression check: v7 vs v6 copies 36.0 vs 35.6 (neutral/slightly positive).
- Place profile (600 tables, field v7x3/v6/v5/nit/montecarlo/maniac): ours ~15% 1st, 15% 2nd, 11% 3rd,
  12% 4th, 16% 5th, 15% 6th, 11% 7th, 3% 8th. ~42% of tables we bust 5th-7th; the nit never wins but
  scores 34 by landing 3rd/4th. Next test: larger risk premium / tighter calls when 5-7 players remain
  (mid levels, 10-25 BB), aiming to turn 5th-7th busts into 3rd-4th without losing 1sts.
- Tried icm_mid=0.04 (extra premium on at-risk calls with >=5 alive): +0.4 vs v7 (noise) -> not submitted;
  param left at 0.0 in bot/ (identical behaviour to 007). Bigger levers probably: steal/3-bet vs nits,
  postflop sizing vs calling stations, exact ICM.
- Nit-heavy field (3 nit, checkfold, threshold + 3 v7 copies, 600 tables): v7 copies ~51 each, nits ~26.
  We already exploit passive/tight bots well; gains must come from playing vs other strong bots (mirror).
- Cumulative check, v7 x4 (incl. working copy) vs v3 x3 + nit, 700 tables: v7 avg 32.6 vs v3 avg 31.7
  (+0.9, within noise). The v4-v7 tweaks are small; bigger structural changes are needed for real gains.
- Last accepted submission: 007-ace0e8bc.
