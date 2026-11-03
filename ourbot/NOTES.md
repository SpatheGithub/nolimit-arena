# Our bot: lab notebook

Started 2026-11-03 at the user's request: build a bot from everything the events have taught
so far, and measure whether each lesson actually gains points or introduces a flaw.

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

## What has won so far (events)

| Event | Variant, points | Winner (starting idea) | P(1st) | Trust |
| :- | :- | :- | -: | :- |
| full-opus-001 | NLHE, standard | b06 (opponent model) | 98% | clean |
| full-opus-002 | NLHE, standard | b06 (math_core) | 96% | 27 of 107 window min asleep |
| plo-001 | PLO, standard | b05 (free) | 100% | clean |
| shortdeck-001 | short deck, top_heavy | b02 (model_pressure) | 99% | 109 of 138 min asleep |
| crazy-pineapple-001 | crazy pineapple, standard | b08 (free) | 100% | 130 of 136 min asleep; 5 bots missed T1 |
| royal-001 | royal, winner_take_most | b05 (math_core) | 87% | build 49 of 60 min asleep |
| shortdeck-002 | short deck rerun, same seed | running | | awake, on AC |
| crazy-pineapple-002 | crazy pineapple rerun, same seed | queued | | |

**What recurs:**
- **Re-steals win hold'em.** Pricing re-steals by fold rates won both hold'em events.
- **The field over-folds:** about 82% of the time to shoves and 73–81% to 3-bets, and it never adapted.
- **Starting ideas don't decide events.** Math-first and opponent-model bots have each won. The winners combined sound math with pressure, in whatever proportions.
