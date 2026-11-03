# Our bot: lab notebook

Started 2026-11-03 at the user's request: build a bot from everything the events have taught
so far, and measure whether each lesson actually gains points or introduces a flaw.

## Summary (morning of 2026-11-03)

1. **The lessons do work, once implemented correctly.** The biggest one is to re-shove over a single
   open at 8–30 bb, priced in chips from how often the opener folds. It adds **+7.5 ± 1.5
   points per table** in hold'em. Our bot then **ties event 2's winning builder bot** (−0.6 ± 1.7 over
   the same tables), beats event 1's winner (+3.1), and wins 20% of tables instead of 9%.
2. **It carries over to some variants and fields, not all.**
   - Short deck: +4.6 ± 1.6.
   - A mixed field of house bots and builders: +5.7.
   - The house zoo: no backfire.
   - Crazy pineapple: +1.4, once the preflop lessons were limited to two-card deals. Before that they cost 4.0.
   - Royal: about neutral.
   - **Weak spots:** royal, where the base sits far below the field, and **PLO**.
     In PLO the house Omaha game had no heads-up mode. Adding one (`plohu`, +0.41) raised table wins from 0.2% to 1.3%.
     It's still the weakest variant. If the event's variant is Omaha-like, build that strategy fresh.
3. **Some lessons failed the test.**
   - Shove-or-fold at 15–20 bb from late position (event 1 debrief §7) costs about 1.2 points per table.
   - Pricing everything in chips instead of ICM hurts. Calls need ICM: −0.6 in hold'em, −1.8 in short deck.
   - Calibrating hand strength for small decks hurt slightly.
   - No-flat-calls and respecting big bets are worth under a point each.
**Where the shipped bot stands** (points per table, 3,000 paired tables per row):

| Field | Ours | Field average | Our base | Verdict |
| :- | -: | -: | -: | :- |
| Hold'em builders, minus the winners | **37.6** | 31.9 | 30.1 | strong; ties event 2's winner |
| Hold'em builders + house zoo | **42.5** | 31.9 | 36.8 | strong |
| House zoo only | 49.6 | 31.9 | 49.2 | strong, no backfire |
| Short deck builders (top_heavy) | **25.7** | 21.6 | 21.2 | strong |
| Crazy pineapple, starved first run | 36.7 | 31.9 | 35.3 | above average |
| Crazy pineapple, awake rerun | 27.1 | 31.9 | 26.7 | **below average** |
| PLO builders | 26.5 | 31.9 | 26.1 | **weak** (1.3% wins) |
| Royal builders (winner_take_most) | 11.1 | 16.25 | 11.7 | **weak** |

4. **The method lesson.** The first build looked useless (+0.25) because of a bug (blind posts
   counted as acting) and timid pricing. Profiling the behaviour (3-bet rate 4% against the
   winner's 18%) found both. **Check what the bot actually does before trusting a null result.**
5. **For the build day:** the variant is secret. This bot is variant-generic. It runs on any
   community-card variant through the house framework, and its edge (`chipsteal`) is about 40 lines
   (`ourbot/lessons/agent.py`, `chip_resteal_gains`). The plan is to start from it, then check
   preflop behaviour with `profile2.py` against the new variant early.

- **Bot:** `ourbot/lessons/` is the house `icm_pushfold` game with four lessons added, each behind a
  switch in `switches.json`. With every switch off it plays exactly like `icm_pushfold`.
- **Lab:** `python -m ourbot.lab run` plays paired A/B tests against archived builder bots, and
  `python -m ourbot.lab report` writes the tables to `ourbot/LAB.md`. Raw per-table results are in
  `ourbot/runs/results.jsonl`.

## The lessons under test

| Switch | Lesson | Where it comes from | How the bot does it |
| :- | :- | :- | :- |
| `resteal` | Re-shove over a single open at 8–30 bb, priced by fold equity | LESSONS.md lines 1, 2 and 11–12; DEBRIEF §7 of both hold'em events. The biggest single edge in both | The shove's EV against folding, using the house ICM `values()`: the opener folds at its in-table fold-to-3-bet rate (prior 0.75, weight 4) and otherwise continues with the top of its opening range; players behind call with 0.6× their calling chart. Fires only on a tight table, where the opener and everyone behind have VPIP ≤ 0.30 (prior 0.25, weight 8) |
| `shove20` | First-in shove-or-fold at 15–20 bb from the cutoff or later | DEBRIEF event 1 §7 item 1; b04's T6 notes | The house push/fold EV (`push_gains`), extended from ≤15 bb to ≤20 bb when three or fewer players are behind |
| `noflat` | Defend the blinds by re-shoving, not flat-calling | LESSONS.md line 5; event 2's "strengthens" line. Flatting steals lost 0.3–0.6 bb per steal faced | In the blinds against a single unraised open at ≤30 bb, a flat call becomes a fold, except a big-blind call with a top-40% hand. Re-shoves come from `resteal` |
| `respect` | The field's raises are value; respect big late bets | DEBRIEF event 1 §7 item 5 (N4, H7) | Fold one pair or worse to a raise, or to a turn or river bet of 0.7 pot or more, unless drawing to 8+ outs |

Not switched, because they're already in the base: exact ICM on all-in calls (event 2 refined
event 1's "moderate margin" into "your own calls still need full ICM"), no survival premium
(icm_pushfold's `premium()` is 0), and heads-up push/fold from the chip-EV charts.

## Method

- **Fields:** each field is one variant's archived builder bots, played on that variant's event card.
  - **nlhe:** the final bots of events 1 and 2, 16 in all.
  - **shortdeck:** the latest bots of `shortdeck-001` and `shortdeck-002`. 001's builders mostly slept.
  - **royal:** the final bots of `royal-001`.
  - PLO isn't tested: the lessons are hold'em preflop and postflop logic, and Omaha play goes through the base `omaha()` path untouched.
- **Blocks:** a block seats our bot with 7 opponents drawn from the field (seeded) and plays 50 tables. Every config plays the same 60 blocks with the same seeds, so each comparison is paired over the same 3,000 tables. The config order rotates from block to block, so drift in machine load hits every config alike.
- **Configs:** `base` (all off, which is the house `icm_pushfold`), `all`, `only_<switch>` and `no_<switch>`. `only_X` minus `base` is what X adds alone; `all` minus `no_X` is what X adds on top of the rest.
- **Live guard:** the lab never plays while a live event freezes bots or runs a tournament, and it starts a block only with 150 s or more left in the live window. Those tournaments time every decision.
- **Noise:** points per table have an SD of about 30–40, so 3,000 paired tables give a 95% interval of roughly ±1.3 points per table. Event winners beat the field average by about 2–4 points per table.

## Results log

### 2026-11-03 02:44: setup

- **Validation:** the bot passes the referee's validator in nlhe, shortdeck, royal, plo and crazy_pineapple, with timing p99 ≤ 300 µs and a max of 313 µs against the 1 ms limit. 5 tests are in `tests/test_ourbot.py`.
- **Smoke test** (royal, one 10-table block per config): the harness works. Ten tables say nothing about the effects.
- **Full run started:** nlhe, then shortdeck, then royal, with 60 blocks of 50 tables and 2 workers.

### 2026-11-03 03:49: hold'em done (3,000 paired tables per config)

Field: the 16 final bots of events 1 and 2. The field average is 31.9 points per table (255/8),
and an average bot wins 12.5% of tables.

| Switch | Alone vs base | On top of the rest (all − no_X) |
| :- | -: | -: |
| resteal | +0.27 ± 1.08 | +0.25 ± 1.06 |
| shove20 | −0.21 ± 1.05 | **−1.16 ± 1.08** |
| noflat | −0.34 ± 0.99 | +0.03 ± 0.99 |
| respect | −0.20 ± 1.00 | −0.13 ± 1.04 |

- **Our base is below this field.** The house `icm_pushfold` averages 29.68, below the field's 31.9. It wins 9.0% of tables and finishes 4th more often than anywhere else (15.7%). The builders' final bots are stronger than the house's best bot.
- **The best config is `no_shove20`** (resteal, noflat and respect): +1.41 ± 1.12 points per table, with wins up from 9.0% to 10.2%. Even so, it stays below the field average.
- **shove20 is a flaw.** Extending first-in shove-or-fold to 15–20 bb in late position costs about 1.2 points on top of the other lessons. That is the event 1 debrief's own §7 item 1 failing the test. It agrees with that debrief's warning about b04's 25 bb push range, which looked good locally and lost in the real field. Off by default from now on.
- **resteal, the "biggest lever", barely registers here:** +0.25, within noise. Possible reasons:
  - the base already re-shoves at 15 bb or less, priced by equity, in `short_preflop`;
  - the tight-table gate or the fold model may leave it rarely firing;
  - these final bots, the field's best, may fold less to re-steals than the field in general.
  To check, I'll count how often it fires.
- **noflat and respect have no measurable effect,** positive or negative.
- **The toughest opponent is event 2's winner (b06).** With it at the table our mean drops to 27.7; with event 1's b07 or b04, the weakest, it's 31.3.

**Next experiments,** after the shortdeck and royal runs finish, so as not to confound them:
1. Instrument `resteal`: how often it fires, and its EV margin.
2. Calibrate against a strong base: score event 2's b06 against the same field, minus itself.
3. Test whether ICM on every shove and call makes the base too survival-minded, since it wins too rarely: chip EV until late, against ICM throughout.

### 2026-11-03 05:15: short deck and royal done (3,000 paired tables per config each)

**Short deck** (top_heavy points 100/45/20/8; field average 21.6 per table). Field: the latest bots
of shortdeck-001 and shortdeck-002, as they stood when the run reached short deck (002 was mid-event).
- **Base is about average:** 21.30 points per table, with 11.5% wins.
- **No lesson helps:** `all` is −0.63 ± 1.45, and `only_noflat` −1.34 ± 1.36, borderline harmful. The best result is `no_noflat` at +0.56 ± 1.42, which is noise.

**Royal** (winner_take_most 100/25/5; field average 16.25). Field: royal-001's 8 final bots.
- **Base is badly weak:** 11.67 points per table, and only 7.8% wins against 12.5% for an average bot.
- **The lessons barely touch it.** `only_noflat` changed no decisions at all (+0.00 ± 0.00), `only_respect` almost none, and every config is within 0.3 of base.
- **Royal is a different game:** 20 cards, T to A, with a 4-card board. Every hand is broadway, and the house postflop strength model, built for a full deck, misjudges hands there.

**Verdict on the lessons so far.** As implemented, none of them gains significantly in any variant.
- **shove20 is a real flaw in hold'em,** at −1.2 on top of the rest.
- **Our base is the bigger problem.** It sits below the hold'em builder field and far below the royal one. The debrief lessons are edges for a bot that's already strong. Bolting them onto the house bot doesn't close the gap to the best builders, whose final bots beat the house's best.

**Next:**
1. The `bases` experiment: score our base and best configs, the house tag, and each hold'em winner's final bot on the same pool, the hold'em field minus the two winners. That measures the gap.
2. Then ICM against chip EV.

### 2026-11-03 05:40: does build time make stronger bots? (short deck, both runs pooled)

shortdeck-002 reran shortdeck-001 with the same seed, slots and starting ideas, with its
builders awake: 0 minutes lost against 109 of 138. I pooled both runs' final bots in one
tournament on the short deck card: 16 bots, 1,000 iterations, seed 20261103, 2 workers.
The script is `cross_event.py <card_event> <event_a> <event_b> [iterations]`, kept in the
session scratchpad. Its core is `run_tournament(archived_bots("event:a,b"), ...)`.

- **Awake builds are stronger, by about 1.2 points per table.** The awake run's bots averaged 22.23 points per table and the asleep run's 21.02, roughly ±1.1. Build time helps, but modestly.
- **The effect is very uneven by slot:**
  - b06 (math_core) went from 20.1 to **26.2**, the strongest bot of all 16.
  - b02 (model_pressure), the asleep run's winner, scored 25.2, level with its awake rerun (25.2).
  - b05 (math_core) got *worse* with more time, from 22.0 to 18.8.

  The builder's path matters more than the minutes.
- **The ranking is real:** pooled against both runs, the awake run's top two, b06 and b02, are the top two of all 16.

**Event result** (shortdeck-002, top_heavy): b06 math_core 533.3 (P(1st) 97%), b02 model_pressure
500.3, then b08, b07 and b04, all free choice. The bottom three were b01 (free), b05 (math_core)
and b03 (model_pressure). The same five bots made the top five in both runs, partly because the
seed shares every deal and seating.

### 2026-11-03 05:35: bases. How far are we from the best builders? (hold'em)

Five candidates, each over the same 3,000 tables against the hold'em pool minus both events' winners
(14 bots), so no candidate met its own copy.

| Candidate | Points/table | Δ vs our base | Wins | 1st / 2nd / 7th / 8th |
| :- | -: | -: | -: | :- |
| event 2 winner (b06, math_core) | **38.25** | **+8.20 ± 1.61** | 21.2% | 21 / 14 / 13 / 16% |
| event 1 winner (b06, opponent model) | 34.55 | +4.50 ± 1.52 | 16.3% | 16 / 13 / 14 / 11% |
| our best (resteal, noflat, respect) | 31.04 | +1.00 ± 1.13 | 10.1% | 10 / 13 / 11 / 10% |
| our base (house icm_pushfold) | 30.05 | · | 9.2% | 9 / 13 / 11 / 10% |
| house tag | 29.42 | −0.62 ± 1.15 | 7.7% | 8 / 13 / 10 / 10% |

- **The gap is 8 points per table, and the lessons close 1 of them.** Event 2's winner scores 27% more than our base.
- **The winners win tables and accept busts.** Event 2's b06 finishes 1st in 21% and 8th in 16% of tables, with few middle places. That is "optimise P(1st), not survival" in the data. Our bots peak at 4th and 5th.
- **Implication for the real event.** The add-on lessons are worth a point. The rest of the winner's edge comes from a whole bot built and tested around pressure and P(1st). Two follow-ups:
  1. The `icm` experiment, running now: does chip EV make our bot win more?
  2. Use event 2's winner as a base, and test our lessons as changes to *it*.

### 2026-11-03 06:05: why resteal didn't register. A bug, and timid pricing

I profiled the bots at shared tables with hand logs, using the reports' own spot definitions
(`arena/tournament/profile.py`). The script is `profile_bots.py <log_dir> <iterations> NAME=DIR ...`,
in the session scratchpad. It seats the candidates with field bots and prints steal, fold-vs-steal,
3-bet rate, 3-bets and shoves per 100 hands, and c-bet.

| Bot (shared tables) | 3-bets an open | 3-bets/100 | Folds to a steal | Points |
| :- | -: | -: | -: | -: |
| our best, as first built | 4.4% | 1.9 | 82% | 29.4 |
| event 2's winner | 18.1% | 7.6 | 55% | 43.5 |
| **fixed, ICM-priced (v1)** | 9.7% | 4.1 | 72% | 32.7 |
| **fixed, chip-priced (chipsteal)** | **17.1%** | **7.1** | **62%** | **37.2** |
| event 2's winner (same tables as the two fixed rows) | 16.8% | 6.9 | 56% | 39.0 |

The points for the last three rows come from 400 tables. They're indicative only.

1. **A bug.** The hand history holds the blinds' own `sb`/`bb` posts. `single_open` counted them as
   hero having acted, so **resteal and noflat never fired from the blinds**, where most steal
   defense happens. That is why noflat changed nothing in royal. Fixed in commit ed1c8d2, with a
   regression test. The `switches` results for resteal and noflat measured the broken version,
   so ignore them. shove20 and respect weren't affected.
2. **Timid pricing.** Even outside the blinds, resteal priced each shove with full ICM and a 25%
   chance that the opener calls, so it rarely cleared the bar. Event 2's winner prices it in chips,
   with the opener calling with probability 0.45 × its opening width. That is about 9–12% for a
   late open, close to the field's actual folds to shoves. That's now the `chipsteal` switch.

With both fixes the bot re-steals like the winner. The `v2` experiment, started 06:03, measures it
on 3,000 paired tables per config: nlhe-x with the same blocks and seeds as `bases`, so it pairs with
the winners' results, plus shortdeck and royal. The configs are base, v1, chipsteal, chipsteal
without noflat, and chipsteal with chipev.

**Lesson about the lessons:** a lesson can test as useless because the code never carries it out.
Profile the behaviour before trusting a null result.

### 2026-11-03 06:00: v2 hold'em. **Our bot now matches the best builder bot**

3,000 paired tables per config on nlhe-x, with the same blocks and seeds as `bases`, so every config
also pairs table for table with the winners' recorded results.

| Config | Points/table | Δ vs base | Wins | vs event 2 winner | vs event 1 winner |
| :- | -: | -: | -: | -: | -: |
| **chipsteal** (resteal in chips, noflat, respect) | **37.62** | **+7.52 ± 1.48** | **20.4%** | **−0.63 ± 1.70** | +3.06 ± 1.71 |
| chipsteal + chipev | 37.00 | +6.91 ± 1.50 | 19.8% | −1.24 ± 1.70 | +2.45 ± 1.70 |
| chipsteal without noflat | 36.88 | +6.78 ± 1.46 | 18.7% | −1.37 ± 1.68 | +2.33 ± 1.68 |
| v1 (resteal priced by ICM, fixed) | 35.62 | +5.53 ± 1.37 | 15.2% | −2.62 ± 1.66 | +1.07 ± 1.57 |
| base (house icm_pushfold) | 30.09 | · | 9.3% | −8.15 ± 1.57 | −4.46 ± 1.50 |

- **The re-steal lesson was right, and it's worth 7.5 points per table.** Implemented correctly, it
  takes the house bot from 8 points behind event 2's winner to level with it (−0.6 ± 1.7), and
  past event 1's winner.
- **Where the gain comes from:**
  - The blind-post fix alone is worth +5.5. That's v1, still priced by ICM.
  - Chip pricing, the winner's model, adds about +2.0.
  - noflat adds about +0.7 on top, which is within noise.
  - chipev is −0.6, also within noise. ICM on calls stays.
- **Same profile as the winner.** chipsteal now finishes 1st 20.4% / 8th 14.2%; the winner 21.2% / 15.7%.
- **Sanity check:** the v2 `base` reproduced the earlier `base` to +0.05 ± 1.05 over the same tables.
- **Shipped defaults now:** resteal, chipsteal, noflat and respect on; shove20 and chipev off.

### 2026-11-03 06:36: v2 short deck and royal. The edge transfers to short deck, not royal

| Config | Short deck (top_heavy; avg 21.6) | Royal (winner_take_most; avg 16.25) |
| :- | -: | -: |
| base | 21.17 (10.7% wins) | 11.67 (7.8% wins) |
| v1 (fixed, ICM-priced) | +2.86 ± 1.50 | −0.17 ± 1.14 |
| **chipsteal** (shipped) | **+4.56 ± 1.57** (16.6% wins) | −0.60 ± 1.18 |
| chipsteal without noflat | +3.51 ± 1.54 | −0.27 ± 1.13 |
| chipsteal + chipev | +2.75 ± 1.57 | −0.53 ± 1.16 |

The short deck field is the latest bots of shortdeck-001 and the finished shortdeck-002.

- **Short deck:** the re-steal edge transfers, at +4.6 points per table with 16.6% wins against 10.7%.
  noflat helps here (+1.1 on top). **chipev is clearly bad** (−1.8 on top of chipsteal), so
  ICM on calls matters even more under a top-heavy table.
- **Royal:** nothing in v2 moves our bot, and the base stays far below this field (11.7 against 16.25).
  The re-steal model's equities come from the royal charts, so the problem is likely elsewhere:
  postflop strength, or how hands play on a 20-card deck. Next: profile our base against
  royal-001's bots, to find where it loses.

### 2026-11-03 06:57: royal diagnosis, and calib doesn't help

Our bot was profiled in royal against royal-001's winner (b05) and 5 field bots over 400 shared
tables, with `profile2.py` from the session scratchpad.

| Bot | Points | VPIP | Folds to c-bet | Folds to river bet | Saw flop | Showdowns won |
| :- | -: | -: | -: | -: | -: | -: |
| ours (shipped) | 11.3 | 27% | 28% | 36% | 21% | 46% |
| royal winner b05 | 22.6 | 39% | 51% | 68% | 35% | 57% |
| other royal bots | 13–19 | 32–40% | 47–84% | 57–83% | 27–34% | 52–60% |

- **Our bot calls too much postflop and loses at showdown.** With five ranks, every 6-card royal
  hand holds at least a pair. The house strength scale, tuned on 52 cards, rates a pair as decent.
- **It also plays too few hands preflop.** Equities run close when every card is broadway, and the
  winner saw 35% of flops to our 21%.
- **`calib` didn't help.** It shifts postflop strength by the variant's mean strength: royal +0.17
  flop and +0.31 turn, short deck up to +0.14. Results over 3,000 paired tables: royal −0.78 ± 1.30,
  short deck −1.31 ± 1.62. The shift makes the bot fold more, but also bet and c-bet less, and
  aggression is what wins. It ships **off**.
- **Royal stays an open problem.** A real fix would need postflop decisions from equity against
  ranges, which is cheap to enumerate with 20 cards, plus looser preflop play in small decks.
  That is a bigger change than one night allows.

### 2026-11-03 ~08:00: robust. The edge holds against other kinds of fields

Our base and the shipped bot each played 3,000 paired tables on the hold'em card.

| Field | Base | Shipped | Δ | Wins: base → shipped |
| :- | -: | -: | -: | :- |
| zoo: the 11 house bots (nit, maniac, min-raiser, calling station, random…) | 49.23 | 49.58 | +0.35 ± 1.44 | 25.2% → 28.4% |
| mixed: zoo + hold'em builder bots minus winners | 36.77 | 42.48 | **+5.71 ± 1.51** | 13.9% → 23.1% |

- **No backfire.** Against loose and odd bots the re-steal neither helps nor hurts, because its tight-table gate keeps it quiet there. Both versions crush the zoo, at about 49 points per table against an average of 31.9.
- **In a mixed field the edge stays large** (+5.7). It doesn't depend on every opponent being a tight AI-built bot.

### 2026-11-03 10:31: PLO and crazy pineapple. Two weaknesses, one fixed

Our base and the shipped bot each played 3,000 paired tables.

| Field | Base | Shipped | Δ | Wins |
| :- | -: | -: | -: | :- |
| plo (plo-001's bots; standard points, avg 31.9) | 26.10 | 26.10 | 0.00 | **0.2%** |
| crazy (crazy-pineapple-001's weak bots) | 35.33 | 31.31 | **−4.03 ± 1.38** | 19.1% → 16.7% |

- **PLO: our bot almost never wins.** It took 6 of 3,000 tables. Both configs play the house `omaha()`
  game, so they're identical. That game opens only strong hands and calls raises only with strong ones, using fixed thresholds.
  In PLO, where equities run close, it survives into middle places and gets blinded down.
  **If the event's variant is Omaha-like, don't rely on this code;** it needs a real strategy.
- **Crazy pineapple: the lessons hurt.** It deals 3 hole cards preflop, but the re-steal prices hands
  with two-card equity tables, so it misjudges both our hand and the openers' ranges. **Fix:** the
  preflop lessons (resteal, shove20, noflat) now apply only when exactly two hole cards are dealt.
  Hold'em, short deck and royal are unchanged.
  **Re-test, 3,000 paired tables:** shipped is now **+1.36 ± 1.22** against base, up from −4.03, with 19.9%
  wins. The remaining gain comes from the postflop `respect` lesson, which still applies after the discard.

### 2026-11-03 11:05: PLO. Looser early play hurts; heads-up was the leak

Profile over 400 shared tables: our bot played 11% VPIP, 8% PFR and 18% steals, and c-bet 46%.
Every PLO builder converged on about 23% VPIP, 17% PFR and 40%+ steals, with c-bets of 48–94%.

| Config, 3,000 paired PLO tables | Points | Δ | Wins | Heads-up reached → won |
| :- | -: | -: | -: | :- |
| base (house omaha()) | 26.10 | · | 0.2% | 12.9% → 2% of those |
| plo (open the top 40/22/15% by position, c-bet 85%) | 24.50 | **−1.61 ± 0.84** | 0.6% | |
| **plohu** (heads-up mode) | 26.52 | **+0.41 ± 0.15** | 1.3% | 12.9% → 10% of those |

- **Matching the field's looseness hurts.** It adds early busts (7th/8th up from 12.7% to 20.7%)
  without building chips. Off.
- **The house Omaha game has no heads-up mode.** Heads-up it folded the small blind about 75%
  of the time and called shoves with the top 9%. `plohu` plays the top 70% heads-up and calls all-ins
  with the top 55%. It's a small, certain gain, and **on**. It changes only heads-up decisions, hence the tight interval.
- **PLO is still our weakest variant.** We reach heads-up on half the average share of tables and
  usually arrive short-stacked, having survived by folding. The real fix is building chips earlier
  with equity-based Omaha play, which is beyond tonight's scope.
  **If the event's variant is Omaha-like, build its strategy fresh on the day.**

### 2026-11-03 11:40: crazy pineapple rerun, and how much build time matters

**Event** (crazy-pineapple-002: same seed and slots as 001, builders awake, no lost minutes):
1. b02 model_pressure 719.0 (P(1st) 68%), 6th in 001.
2. b08 free 710.3 (27%).
3. to 5. b01, b07 and b04, all free choice.

The bottom three were b03 math_core, b05 model_pressure and b06 math_core (3rd in 001).

**Pooled both runs' final bots in one tournament** (16 bots, 1,000 iterations, seed 20261103):
the awake run's bots average **36.86** points per table and the starved run's **26.89**, so **+10.0**.
*Every* awake bot beat *every* starved bot: the worst rerun bot scored 33.6 and the best 001 bot 31.3.

**What build time buys** (two natural experiments, same seeds and slots):

| Variant | Awake minutes in the first run | Gain from full time (pooled) |
| :- | -: | -: |
| short deck | about 29 of 138 | +1.2 per table |
| crazy pineapple | about 6 of 136 | **+10.0** per table |

Most of a bot's strength comes in the first half hour or so, and returns diminish after that.
**For the 60-minute build day:** get a sound bot submitted early. After that, test discipline
matters more than extra minutes.

### 2026-11-03 11:46: crazy pineapple against the awake rerun's bots

3,000 paired tables, shipped against base: **+0.46 ± 1.40**, within noise. Both score about 27 points per
table against an average of 31.9, so we're below average against strong crazy pineapple bots.
With the two-card gate, the preflop lessons are off there, which leaves only the postflop `respect`.
**The missing piece** is a re-steal priced for three-card hands: equity of the best two of three
against ranges, by Monte Carlo. It's the same mechanism that took hold'em from −8 to level with the winner.

### 2026-11-03 11:53: the re-steal alone with three hole cards (resteal3)

3,000 paired tables against the crazy pineapple rerun's bots, standard points:
- **Points:** −0.57 ± 1.51 against the shipped bot, within noise.
- **Wins:** 16.1% against 13.5%, a **+2.6** point rise in win rate.

That's the winners' trade: more 1st places, more busts. Under 100/60/40/… they cancel.
**Ships off.** Turn it on for a three-card variant if the announced points table is top-heavy or
winner-take-most, where the extra wins should outweigh the busts. That's untested; check it on the day.

## What has won so far (events)

| Event | Variant, points | Winner (starting idea) | P(1st) | Trust |
| :- | :- | :- | -: | :- |
| full-opus-001 | NLHE, standard | b06 (opponent model) | 98% | clean |
| full-opus-002 | NLHE, standard | b06 (math_core) | 96% | 27 of 107 window min asleep |
| plo-001 | PLO, standard | b05 (free) | 100% | clean |
| shortdeck-001 | short deck, top_heavy | b02 (model_pressure) | 99% | 109 of 138 min asleep |
| crazy-pineapple-001 | crazy pineapple, standard | b08 (free) | 100% | 130 of 136 min asleep; 5 bots missed T1 |
| royal-001 | royal, winner_take_most | b05 (math_core) | 87% | build 49 of 60 min asleep |
| shortdeck-002 | short deck rerun, same seed | b06 (math_core) | 97% | clean; its bots beat 001's by ~1.2 pts/table |
| crazy-pineapple-002 | crazy pineapple rerun, same seed | b02 (model_pressure) | 68% | clean; its bots beat 001's by ~10 pts/table |

**What recurs:**
- **Re-steals win hold'em.** Pricing re-steals by fold rates won both hold'em events.
- **The field over-folds:** about 82% of the time to shoves and 73–81% to 3-bets, and it never adapted.
- **Starting ideas don't decide events.** Math-first and opponent-model bots have each won. The winners combined sound math with pressure, in whatever proportions.
