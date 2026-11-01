# Debrief: full-opus-002

No-limit hold'em, 8 seats, 2,000 chips, points 100/60/40/25/15/10/5/0, blinds doubling every 25 hands, 6 tournaments × 1,000 tables, 8 Opus 5.5 builders. The rules are identical to full-opus-001, so this event is a replication with a different set of builders and briefs (2 × math_core, 2 × model_pressure, 4 × free choice).

Sources are in this folder unless a path says otherwise:
- `REPORT.md`;
- `../results/T<k>/` (`summary.json`, `profile.json`, hand logs);
- `../bots/<team>/T<k>/` and `NOTES.T<k>.md`;
- `../submissions/<team>/index.jsonl` and the submitted code;
- `../state.json`;
- the builder transcripts in `../logs/`.

There is no `strategies.json` for this event. All T1-vs-T6 rates, spot results and correlations below are my own computations from the two tournaments' `profile.json`. The array layout is in `arena/tournament/profile.py:17-20`.

## The short version

1. **The re-steal shove won again.**
   - **b06's mechanism:** it re-shoves over a single open at 30 bb or less with any hand whose shove EV clears 0.1 pot, assuming the opener calls with 45% of its opening range.
   - **Gate:** it does this only while the opener and everyone behind look tight (VPIP ≤ 0.30). It won T4, T5 and T6 and is 1st in 96% of bootstrap resamples.
   - **Volume:** in T6 it made **7.1 3-bets per 100 hands, against 1.3–3.4 for everyone else**. 90% were all-in, 79% took the pot uncontested, and they won +11.4 bb/100.
2. **b06 had this mechanism at build minute 4.9, then removed it.** At minute 21.9 a capped version replaced it, on a 450-table local A/B whose noise was ±3.3 points. That A/B also carried a real postflop bug fix.
   - **Restored for T4:** the builder brought the logic back, gated, after seeing its own minute-15 version beat its later ones against TAG-like opponents.
   - **Gain:** T4–T6 averaged 36.3 points per table, against 33.3 for T1–T3, a gain of +3.0 ± 1.8.
3. **The field kept over-folding and never adapted.** From T1 to T6, folds to a 3-bet rose from 73.0% to 77.4%, folds to a shove stayed at 82%, and folds to a c-bet rose from 70% to 73%. Over the same period b06 tripled its 3-bets.
4. **Blind defence by re-shoving separated the field.** In T6, b06 re-raised 25.6% of steals and made +0.10 bb per steal faced. The other seven re-raised 4–11% and lost 0.30–0.54 bb each.
5. **Robustness was nearly table stakes.** All 32 substitutions came in T1: 11 timeouts and 21 hangs, during a run 3× slower than the others. There were none in T2–T6 and no illegal actions anywhere.
6. **The build was disrupted.** A usage-limit pause hit at minute 32, and the computer then slept 23 of the 28 resumed build minutes. Five of the eight T1 bots were submitted in that window, so builders had about 37 awake minutes, not 60. The report's submission timeline is wrong again (§4).

**Caveats.**
- **One model.** All builders were Opus 5.5, so the field is more uniform than the real one.
- **Small samples.** Each tournament had 1,000 iterations, so per-tournament intervals are about ±2 points per table. Identical code moved 1.5–2.4 points between tournaments: b05's code 010 scored 33.95, 31.59 and 32.37; b06's code 008 scored 35.63, 37.37 and 35.78.
- **No zoo in scored play.** The house zoo never played in the scored tournaments.
- **Thin patch feedback.** Patch-window feedback held only hands 1–10 of a few tables (`bots/b06/NOTES.T6.md:47`, `bots/b04/NOTES.T6.md:89`).

---

## 1. What won

Points per table = weighted score / 21. The field mean is 31.875. Won, heads-up won, top 3 and last two are pooled from `REPORT.md`.

| Rank | Bot | Archetype | Weighted (95% CI) | Per table | vs mean | P(1st) | P(top 5) | Won | Heads-up won | Top 3 | Last two |
| -: | :- | :- | -: | -: | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | math_core | 743.9 ± 21.0 | 35.42 | +3.5 | 96% | 100% | 16% | 55% | 40% | 27% |
| 2 | b03 | math_core | 713.0 ± 19.7 | 33.95 | +2.1 | 4% | 100% | 16% | 60% | 39% | 22% |
| 3 | b08 | free | 698.4 ± 18.5 | 33.26 | +1.4 | 0% | 100% | 11% | 46% | 41% | 20% |
| 4 | b05 | free | 681.1 ± 18.3 | 32.43 | +0.6 | 0% | 100% | 12% | 48% | 39% | 23% |
| 5 | b02 | free | 642.6 ± 18.1 | 30.60 | −1.3 | 0% | 64% | 12% | 51% | 33% | 25% |
| 6 | b04 | model_pressure | 636.2 ± 18.8 | 30.30 | −1.6 | 0% | 30% | 12% | 54% | 34% | 28% |
| 7 | b01 | free | 624.7 ± 17.2 | 29.75 | −2.1 | 0% | 5% | 9% | 38% | 38% | 27% |
| 8 | b07 | model_pressure | 615.2 ± 17.7 | 29.30 | −2.6 | 0% | 0% | 11% | 47% | 36% | 28% |

**Which rank gaps are real (`REPORT.md`, rank view):**
- **b06 over b03 is real.** b06 is 1st in 96% of resamples. b03 led after T1–T3 and b06 after T4–T6.
- **2nd to 4th are close.** b03, b08 and b05 are 14.6 and 17.3 weighted points apart (0.7–0.8 points per table). b03 is 2nd in 80% of resamples, b08 3rd in 73%, b05 4th in 88%.
- **The top four against the rest is the clearest split.** The gap from b05 to b02 is 38.5 weighted points; the top four reach the top 5 in 100% of resamples, b02 in 64%.
- **5th to 8th is mostly noise.** b02, b04, b01 and b07 lie within 27 weighted points. P(top 5) is 64%, 30%, 5% and 0%.
- **Single tournaments separated nothing.** Every rank in every tournament carries the ≈ mark.

### b06: gated re-steal shove on a push/fold and bubble-factor core (1st)

**Approach.** The kit's house-bot helpers, a 169×169 equity matrix at 240 boards per pair, and push/fold at 14 bb or less, priced by explicit EV against modelled call widths:
- **Call widths:** a Nash-like table by stack, ×1.25 for the big blind, scaled by observed VPIP and by each seat's calls of its earlier shoves (`bots/b06/T6/agent.py:335-352, 375-389`).
- **ICM:** exact Malmuth–Harville bubble factors computed in `observe()`, used to weight losses.
- **Postflop:** the heuristic `features()`. It c-bets 81% of the time, usually at 40% of the pot.

**The mechanism.** It shoves over a single open when the table is tight:
```python
# bots/b06/T6/agent.py:459-474 (abridged)
tight_tbl = (self.vpip_est(raiser) <= 0.30 and ratio_r <= 1.25          # VPIP prior 0.25, weight 8; ratio = opener's
             and all(self.vpip_est(x) <= 0.30 for x in behind))          #   shove calls vs model-expected
if tight_tbl and eff_bb <= 30 and sp.can_raise:
    callers = [(raiser, max(0.04, min(0.5, w * 0.45)))]                  # opener calls with 45% of its open range
    for s_ in behind:
        callers.append((s_, self.call_width(s_, obs, my_total, bb, s_ == bbseat) * 0.7))
    ev = self.shove_ev(sp, obs, c, callers)                              # fold equity + bubble-factor-weighted equity
    if ev > 0.0 and (pct <= 0.10 or ev > 0.1 * sp.pot):                  # no hand cap
        return act_allin(sp)
elif eff_bb <= 25 and sp.can_raise:                                      # loose table: the capped T1–T3 version
    ...  cap = 0.30 if eff_bb <= 12 else 0.20 if eff_bb <= 18 else 0.12
```

**What the patch changed (T1 bot 004 → T6 bot 010).** All values are from `results/T1,T6/profile.json`:

| | T1 | T6 |
| :- | -: | -: |
| 3-bets per 100 hands | 2.3 | 7.1 |
| bb per 3-bet | +2.61 | +1.60 |
| Re-raises facing an open | 5.3% | 14.1% |
| Re-raises facing a steal | 6.4% | 25.6% |
| Result per steal faced | −0.44 bb | +0.10 bb |
| Shoves per 100 hands | 5.6 | 9.7 |
| Hands under 10 bb | 7.7% | 3.3% |
| 1st place | 12.1% | 19.2% |
| 7th or 8th place | 21.0% | 32.4% |

The 3-bets got smaller on average but came three times as often, and the bot spent less than half as many hands short. Hand examples (T6 table 7):
- **Hand 72:** b01 opens AJs to 2.5 bb; b06 re-shoves K8o, 24 bb effective; b01 folds.
- **Hand 73:** b03 opens KJs; b06 re-shoves 77; b03 folds.
- **Hand 80:** b02 opens KQo with 11 bb; b06 re-shoves T6o; b02 folds.

**How sure.**
- **The rank:** 1st in 96% of resamples. It won T4–T6 with 35.6, 37.4 and 35.8, against 33.3, 32.9 and 33.6 in T1–T3.
- **The patch:** T4–T6 minus T1–T3 is +3.0 ± 1.8. That is above the 1.5–2.4 same-code spread, but the rest of the field also patched, so the patch isn't isolated perfectly.
- **The builder's local A/B tests** (`bots/b06/NOTES.T6.md:65-71, 95-96`), with the TAG field made of its own versions:
  - **Ungated hybrid, TAG field:** +3.3 and +6.0.
  - **Ungated hybrid, loose house zoo:** −5.2.
  - **Gated version, TAG field:** +0.7 and +5.6.
  - **Gated version, house zoo:** −1.4 and +1.4, and about −1.4 over three later runs.
- **If the field adapted:** a stress test with copies that call all-ins wider left b06 at about the field average rather than collapsing (`NOTES.T6.md:92-94`).

### b03: ICM-points push/fold and re-steals against an ICM-tight caller model (2nd)

**Approach.** Its own tables:
- a 1326×1326 equity matrix from 4,000 boards;
- `eqr[class][x]`, a class's equity against the top x% of hands;
- an ICM table by players alive and chip share;
- `CF[x][t]`, the share of hands with equity ≥ t against a top-x% shove range.

Every all-in is scored in ICM points (λ = 1; it beat λ 0.5 and 0 with 37.3, 35.7 and 32.1 locally, `bots/b03/NOTES.T6.md:25`). Postflop it compares hand strength with a range weighted by preflop action, using 220–300 sampled combos.

**The mechanism: model callers as ICM-tight, then shove into them.** A caller is assumed to need pot odds plus 0.06 with four or more alive (0.03 three-handed, 0 heads-up), plus 0.03 more when b03 covers it:
```python
# bots/b03/T6/agent.py:499-501, 559-584 (abridged)
t = call_amt / max(1, final) + (0.06 if n_al > 3 else (0.03 if n_al == 3 else 0.0))
if n_al > 2 and obs["stacks"][me] + bets[me] >= obs["stacks"][s] + bets[s]:
    t += 0.03                                     # covered callers need more
...                                               # base = CF[x][t]: share of hands with that much equity
ev += pacc * cr * (eq * ew + (1 - eq) * el)       # ew/el: ICM value after winning/losing
ev += pacc * icm_val(S + pot, T, n)               # everyone folds
```
In T1 it shoved 7.1 times per 100 hands (the most) at +1.09 bb each, and 76% of those shoves took the pot. 47% of its late-position steals were all-in. It won T1–T3 (34.8, 35.4, 35.7) without big patches.

**Where it slipped.** For T6 it widened late-position opens: the button from 36% to 55%, the cutoff from 27% to 36%. The evidence was a proxy field built from the sample hands: +0.3, +0.5 and +1.3 locally (`NOTES.T6.md:120-133`). T6 scored 31.75, which is −3.2 ± 2.2 against its T1–T5 average of 35.0. More late opens also meant more opens for b06 to re-steal: b03 faced 2.5 3-bets per 100 hands in T6, against 1.6 in T1.

**How sure.** 2nd in 80% of resamples and 3rd in 16%. P(top 5) is 100%.

### b08: tight, exact-ICM, Monte Carlo postflop; every open is a shove at 18 bb or less (3rd)

**Approach.** The tightest bot (VPIP 19–22%, PFR 11–16%):
- **ICM:** exact on the real stacks when four or fewer are alive (`bots/b08/T6/agent.py:586-604`).
- **Postflop:** Monte Carlo equity against ranges, with a 0.35 ms budget after T1's timeouts.
- **Short stacks:** at 18 bb or less, every hand in the open range is shoved (`agent.py:457-461`).

Its profile is survival: the most top-3 finishes (41%) and the fewest last-two finishes (20%), but only 11% wins and 46% of heads-up finishes converted. Its shoves earned the least: +0.33 bb each in T6, 65% uncontested.

**What moved it.**
- **T3: less ICM margin.** It removed the 2-point ICM margin on calls with five or more alive and the ×0.85 open scaling. That gained +4 to +7 in a proxy field of its own submissions, a field that had reproduced its real T2 score exactly (31.8 local, 31.8 real; `bots/b08/NOTES.T6.md:31-36`). Real result: 31.79 (T2), then 33.04 (T3).
- **A winner's-curse check.** The builder re-tested its selected candidates on fresh seeds and found part of their gain was selection luck (`NOTES.T6.md:82-84`).

**How sure.** 3rd in 73% of resamples. It is the steadiest bot, at 31.8–34.5 in every tournament.

### b05: bubble-factor push/fold, light 3-bets against proven folders (4th)

**Approach.**
- **ICM:** bubble factors at equal stacks, damped by `_ICM_W = 0.5` because the blinds double.
- **Postflop:** a range-threshold model that narrows the bettor's range by bet size and earlier aggression.
- **The exploit:** light 3-bets against openers seen folding to 3-bets:
```python
# bots/b05/T6/agent.py:518-522
if (rst is not None and rst.faced3 >= 3 and sp.callers == 0 and pct <= 0.35
        and (rst.fold3 + 1.5) / (rst.faced3 + 3) >= 0.6 and r < 0.6):
    return self.raise_to(sp, raise_amt * mult)          # 3x in position, 3.6x out of position
```
Raising this from 40% to 60% of eligible spots measured +1.6 in self-play and +1.8 in a mixed field (`bots/b05/NOTES.T6.md:38-39`).

**In T6** it made 3.4 3-bets per 100 hands, the second most, at +2.17 bb each. It was the best river bettor on the exploit board (+4.8 bb/100). Its leak is folding 86% to c-bets (−0.7 ± 0.4 bb/100).

**How sure.** 4th in 88% of resamples. It scored 31.6–34.0 in every tournament, with no patch effect visible beyond noise.

### b02: concave chip utility on all-ins (5th)

**Approach.** Rule-based postflop. All-in EV uses a concave chip utility, x^0.75, with more than four players alive, and exact ICM at four or fewer (`bots/b02/T6/agent.py:40-42`, `"util": 1, "alpha": 0.75`).

**What moved it.**
- **T1, chip EV with tiny margins:** 29.27, 8th, with 17.5% of finishes in 8th place (`bots/b02/NOTES.T6.md:54-60`).
- **From T2, with the utility:** 8th places fell to 10–13%. In exchange, 4th place spiked: 16.3%, 15.6%, 16.5%, 18.3% and 17.5% in T2–T6, against 12.5% expected. Every local fix for the spike also cut 1sts (`NOTES.T6.md:162-179`).

**How sure.** 5th in 64% of resamples. It is tied with b04 within noise.

### What the top five share, and what separated them

- **Shared by all eight:** a 169-class or 1326-combo preflop table with equity against the top p% of hands, push/fold at 14–18 bb, ICM-priced calls of all-ins, per-seat VPIP/PFR counters, and opens of 2.2–2.5 bb.
- **What separated 1st was the volume of fold-equity aggression,** as in full-opus-001:

| Bot | 3-bets per 100 hands | bb per 3-bet | Shoves per 100 hands | bb per shove | Shoves taking the pot | Re-raises vs steals | bb per steal faced | Hands under 10 bb |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b06 | 7.1 | +1.60 | 9.7 | +0.99 | 77% | 25.6% | +0.10 | 3.3% |
| b03 | 2.7 | +2.45 | 6.5 | +1.00 | 73% | 10.7% | −0.30 | 6.5% |
| b08 | 1.9 | +2.19 | 4.7 | +0.33 | 65% | 4.6% | −0.35 | 9.6% |
| b05 | 3.4 | +2.17 | 5.4 | +0.79 | 71% | 10.1% | −0.37 | 6.0% |
| b02 | 1.8 | +2.41 | 3.9 | +1.00 | 55% | 5.1% | −0.46 | 11.3% |
| b04 | 1.6 | +3.32 | 4.9 | +0.80 | 68% | 4.9% | −0.43 | 5.1% |
| b01 | 2.0 | +1.80 | 4.3 | +0.74 | 63% | 6.7% | −0.44 | 6.7% |
| b07 | 1.3 | +3.32 | 3.9 | +0.92 | 71% | 4.2% | −0.54 | 5.8% |

  All values are T6, from `results/T6/profile.json`. 3-bets are raises in the `vs_open` and `vs_steal` spots, and results are whole-hand big blinds.
  - **Correlation with final rank (Spearman, n = 8):** about 0.76 for 3-bets per 100 hands and 0.69 for the re-raise rate against steals. Full-opus-001 had 0.83 for the second.
  - **The outlier is b08.** It is 3rd with the lowest bb per shove and almost no re-raising: it scores by surviving and placing, not by winning.

## 2. What lost

**Timeouts, crashes and illegal actions: T1 only, and cheap.**
- **Count:** T1 had 32 substitutions across 6 bots: 11 timeouts and 21 hangs (`REPORT.md`, Substitutions). T2–T6 had none, and no tournament had an error or illegal action. That is 0 in about 4.4M decisions in T2–T6 (about 885k per tournament, `results/T6/summary.json`).
- **Load:** T1 took 125 s against 41–43 s for T2–T6 (`state.json`, `tournaments`), so the machine was loaded.
- **Causes:**
  - **Monte Carlo budgets near the limit:** b01 used 0.5 ms (CPU max 1,978 µs) and b08 0.45 ms (max 2.7 ms). Both cut their budgets for T2: b01 to a 0.38 ms deadline, b08 to 0.35 ms.
  - **An 8-player ICM in `observe()`:** b06's overran the 50 ms wall watchdog, causing 156 `observe()` errors and 2 hangs. The fix refreshes three opponents per hand, cutting 3.9 ms to 1.5 ms (`bots/b06/NOTES.T6.md:34-35`).
  - **Scheduling hangs:** b03's "hangs" were wall time over 50 ms with at most 1.4 ms of CPU, which is scheduling, not code.
- **Cost:** 32 substitutions over 8,000 bot-tables, so about 0.

**Late or broken submissions: none.**
- **Rejections:** zero validator rejections, and about 17 cooldown rejections across the field. Each appears twice in `logs/b0*.jsonl`, 35 lines in all.
- **Timing:** every team had a bot accepted by minute 5.6.
- **What actually cost time was the environment (§4).** b01, b04 and b06 made no submission after the usage-limit pause. b06's transcript says the build "ended mid-command" and "the earlier hangs look like the session was paused" (`logs/b06.jsonl` lines 889, 1056).

**Ignoring the variant or the points table: nobody.** The variant was standard hold'em, and every T1 bot priced all-ins with ICM; for the six teams whose notes date it, ICM arrived at minutes 4.9–17.1 (§5). The real losses came from these patches:
- **Removing ICM.** b01's T5 patch dropped ICM from shoves and calls and widened opens. It scored 27.21, against 30.29 and 30.34 for the same base code in T4 and T6, so about −3.1. Locally it had measured +0.5 against copies of itself (`bots/b01/NOTES.T6.md:126-151`).
- **Chip-EV all-ins.** b02's T1 bot made all-in decisions at 52–54% equity where ICM needs about 62%. It finished 8th with 17.5% 8th places (`bots/b02/NOTES.T6.md:57-60`).
- **Field-calibrated priors that tightened the bot:** b07's fold-to-raise prior of 0.85, its BB caller model, and its 3-bet range of premium hands only. T3 scored 28.38 against 30.97 for T2; reverted (`bots/b07/NOTES.T6.md:71-74`).
- **Stronger bettor ranges.** b04's T4 version folded more to big bets and raises, winning locally in 4 of 4 runs. T4 scored 28.70; reverted (`bots/b04/NOTES.T6.md:116-123`).
- **Removing the winning mechanism.** b06 capped its re-steals at minute 21.9 (§4). It played T1–T3 about 3 points per table below its later level, which is roughly 18 weighted points.

## 3. Archetypes and models

| Group | n | Weighted, mean ± 95% CI across teams (`REPORT.md`) | Teams | full-opus-001 |
| :- | -: | -: | :- | :- |
| math_core | 2 | 728.5 ± 30.3 | b06 743.9, b03 713.0 | not used |
| free choice | 4 | 661.7 ± 33.3 | b08 698.4, b05 681.1, b02 642.6, b01 624.7 | 662.0 ± 13.1 (n = 4) |
| model_pressure | 2 | 625.7 ± 20.6 | b04 636.2, b07 615.2 | its two parts won: opponent_model 1st (733.9), pressure 2nd (702.4) |
| **Model: Opus 5.5** | 8 | 669.4 ± 32.3 | all | 669.4 ± 23.9 |

- **The intervals for n = 2 are too narrow.** The report uses 1.96 × SE. A t-interval with one degree of freedom is about ±200 points, so no archetype difference here is established.
- **The labels flip between events.** "Opponent model with pressure" is essentially the brief behind full-opus-001's top two, yet it finished 6th and 8th today. The math_core teams finished 1st and 2nd, but both won with the same fold-equity shove mechanism that the model_pressure brief describes. Builder variance dominates the starting idea. Within math_core, b06 and b03 are 31 weighted points apart. The two model_pressure bots spent their patches on postflop reads and priors, which per-seat samples within a table can't support (§6).
- **Free choice is stable.** It averaged 661.7 here against 662.0 in full-opus-001, and its four bots span 74 weighted points (3.5 points per table).
- **No model comparison is possible.** Every builder was Opus 5.5.
- **Coincidence:** team id b06 won both events with different briefs. Workspaces are fresh each event, so nothing carries over.

## 4. Time use

**The report's timeline is wrong.** `arena/referee/report.py:158-168` counts from `windows[build].start`, which `state.json` overwrote with the resume time after a usage-limit pause (18:06:18). Its "8 of 8 by minute 5" is therefore trivially true. This repeats the tooling bug in `LESSONS.md`.

**The real clock.**
- **Build start:** 16:01:34. The briefs say "ends at 17:01:34" (`briefs/b0*.md:23`).
- **Pause:** at 16:33:51, build minute 32.3, when b02, b03 and b04 hit the usage limit.
- **Resume:** at 18:06:18 with 1,689 s left (`state.json` events), so the referee clock resumed at minute 31.85.
- **Sleep:** the computer was asleep 1,397 s of the remaining 1,689 s (`state.json` `windows[0].asleep_s`).
- **Effective build:** about 37 awake minutes.
- **The report's sleep line is also off.** "27 of 107 builder-window minutes" leaves out the 32 pre-pause build minutes and patch 2's 19 pre-pause minutes.

Build minutes for the top five below come from `submissions/<team>/index.jsonl`; contents come from each team's `NOTES.T6.md`. Minutes after the pause are on the referee clock.

| Team (rank) | First accepted | At 5 min | At 10 min | At 20 min | T1 bot | Build submissions |
| :- | -: | :- | :- | :- | :- | -: |
| b06 (1) | 4.9 | v1: push/fold EV at 14 bb or less, **uncapped re-steal shove** at 30 bb or less, ICM bubble factors | v1 | v2 (15.6): + bubble-factor damping, VPIP-scaled steal widths, re-steal unchanged | v4 at 29.7. The re-steal was capped in v3 (21.9) | 4 |
| b03 (2) | 5.6 | none | v1: baseline | v3 (15.8): + ICM table, range narrowing. v4 at 20.9: positional ranges | v7 after the resume (51.9) | 7 |
| b08 (3) | 5.5 | none | v1: baseline | v2 (11.6): + ICM on big calls. v3 at 20.2: opponent reads, EV bluffs | v5 after the resume (41.8) | 5 |
| b05 (4) | 4.5 | v1: baseline | v1 | v3 (17.4): + ICM pair factors, fold-to-bet tracking | v7 after the resume (51.8) | 7 |
| b02 (5) | 5.4 | none | v1 | v3 (17.1): + re-shove fold equity, ICM | v7 after the resume (39.8) | 7 |

- **Field-wide:** 4 of 8 teams had a bot accepted by minute 5.0 (b07 4.15, b01 4.27, b05 4.53, b06 4.90). b04 followed at 5.01, and all 8 had one by 5.6.
- **T1 bots after the pause:** five teams submitted theirs in the 28 resumed minutes, of which about 5 were awake: b02, b03, b05, b07 and b08. b01, b04 and b06 played T1 with their minute-30 bots.
- **T1 scores were all within noise:** 29.3–34.8.

**The winning mechanism was in the minute-4.9 bot.**
- **v1 and v2:** the re-steal block in b06's v1 and v2 (`submissions/b06/001-0a685c53/agent.py:370-379`, `002-8122ea81/agent.py:400-411`) is the same code its T4–T6 bot runs on tight tables.
- **v3 capped it at minute 21.9.** The opener's call width went from 0.45 to 0.65 of its range, with hand caps of 0.30, 0.20 and 0.12 by depth (`003-3fa342d3/agent.py:439-450`).
- **The evidence for the cap was weak.** It was a 450-table A/B: v3 44.4, v2 41.3, v1 40.6, with noise of ±3.3, in a field of house bots and its own versions. v3 also fixed a real bug: postflop it had been calling maniac shoves with middle pair (`bots/b06/NOTES.T6.md:25-27`). The cap rode along on that fix.
- **The reversal.** In patch window 2 the builder found that "002 (looser … wide resteals) tops both competent-field runs" (`NOTES.T6.md:49-55`), and restored the logic, gated, for T4.

**Implications for a 60-minute human build:**
- **About 37 minutes of focused work produced a competitive T1 bot** for every AI team. The rest of the window is for not breaking it.
- **The money mechanism is small.** It is about 15 lines plus a `shove_ev` helper over precomputed equity tables. A human team can have it by minute 25–30 if v1 (minute 10) already has push/fold.
- **Change one thing per A/B.** A bundled change can remove the winner along with fixing a bug.
- **Never let a house-zoo A/B decide preflop aggression.** The zoo's loose callers punish exactly the move the AI-built field folds to. b06's ungated re-steal scored −5.2 against the zoo and +3.3 to +6.0 against TAG bots.
- **Keep the laptop awake** (`caffeinate -dims` on macOS) and power plugged in. Minutes lost to sleep are not returned.

## 5. Rules-specific insight

The rules matched full-opus-001, and the rules-level conclusions replicate:

- **The blind schedule compresses the game.**
  - **Length:** tables lasted 125.8–130.9 hands (T1 130.9, T6 126.8), and 0 of 6,000 reached the 200-hand cap. The cap logic that some bots had never triggered.
  - **Where hands are played (T6, pooled):** 53% at 40 bb or more, 23% at 20–40 bb, 17% at 10–20 bb and 7% under 10 bb.
  - **Where chips change hands:** at 10–30 bb, in levels 3–5 (hands 51–125), almost entirely preflop. All of b06's T4–T6 gain came there.
  - **Shorter tables late:** tables got about 4 hands shorter from T4 on, when the field got more aggressive.
- **The points table rewards winning.**
  - **b06 traded the middle for 1sts.** Its gated version took 1st on 19.2–20.6% of tables in T4–T6, against 12.1% in T1, and went out 7th or 8th on 29–32%, against 21%. Its 3rd–5th places nearly emptied (T6: 6.6%, 7.2%, 9.0%).
  - **The arithmetic:** with 1st minus 2nd at 40 points and 8th minus 5th at 15, that trade is worth about +3 points per table.
  - **Late survival only shifts places.** b02's survival tuning moved finishes into 4th, which pays 25 points.
- **ICM still taxes calls, not shoves.**
  - **The tax:** an 8-handed full-stack flip needs about 62% equity. Doubling from 2,000 to 4,000 is worth +19 points and busting −32 (`bots/b04/NOTES.T6.md:18`, `bots/b03/NOTES.T6.md:143`).
  - **The shover's side:** shoves won the blinds uncontested 55–77% of the time.
  - **Every controlled test agreed that ICM on calls helps:**
    - b03: full ICM beat half ICM and none, 37.3 against 35.7 and 32.1.
    - b04: plain ICM beat a softer version by 1.7 and a harder one by 2.8.
    - b07: a 50/50 blend at 3–4 players lost 1.33.
    - b01: removing ICM cost about 3 points in the real field.
  - **Over-applying ICM hurt as well:** b01's loss weighting k = 0.62 cost −3.6 locally.
- **No variant to adapt to.** It was standard hold'em, so this event says nothing about variant-generic builds.
- **Adapting to the points table was fast.** Points-table pricing of all-ins arrived by minute 10–17: b04 10.1, b03 10.6, b05 10.9, b08 11.6, b07 16.9, b02 17.1. b06 had ICM bubble factors in v1 at 4.9.
- **Adapting to the field was slow, and one-sided.**
  - **Who moved:** b08 at T3 (less ICM margin, wider opens), b06 at T4 (the gated re-steal), b04 at T4–T6 (postflop aggression), b03 at T6 (wider steals).
  - **Nobody moved against the re-stealer:**

  | | T1 | T6 |
  | :- | -: | -: |
  | Folds to a 3-bet (all bots) | 73.0% | 77.4% |
  | 3-bets faced | 15,066 | 20,744 |
  | Folds to a shove | 82.0% | 82.2% |
  | Folds to a steal (all bots / without b06) | 75.1% / 74.2% | 73.0% / 75.3% |
  | Folds to a c-bet | 70.3% | 73.4% |

  Teams tuned against their own versions and saw only hands 1–10 of the real field. A static exploit designed on day one kept paying through T6, as in full-opus-001.

## 6. Where the field leaks points

**How costs are converted.** Costs are big blinds per 100 hands relative to the rest of the field: the `REPORT.md` leak measure, or my T6 recomputation with the same formula (`arena/tournament/profile.py:323-332`).
- **Rough conversion: 1 bb/100 ≈ 0.3 points per table.** b06's T1→T6 change was about +10.6 bb/100 in the hands where it faced an open or a steal, alongside +2.5 to +3.0 points per table. Full-opus-001 estimated 0.5 (range 0.3–1), so treat every cost below as ±50%.
- **Spots per table:** a bot plays about 93 hands per table. Over a table, each opponent faces about 12 steals, 25 opens, 9 shoves, 2–3 3-bets, 1–3 c-bets and fewer than 1 river bet.

### The hypotheses in `docs/FIELD_STUDY.md`

| # | Hypothesis | Verdict today | Bots | Rough cost | Detectable within one table? |
| :- | :- | :- | :- | :- | :- |
| 1 | Timeouts, exceptions, illegal amounts in rare spots | **Partly, in T1 only.** 11 timeouts and 21 hangs from MC budgets and `observe()` work under load; 0 illegal actions in 6 tournaments | 6 (T1) | about 0 | n/a |
| 2 | Same thresholds at every depth | **Two bots.** b08's VPIP is 22/18/22/19% and b02's 23/24/24/20% from under 10 bb to 40+ bb. The other six widen to 31–37% under 10 bb | 2 | Indirect: b02 spends 11.3% and b08 9.6% of hands under 10 bb, against 3.3% for b06. b02 also has the 4th-place spike. Hard to price | Weakly: about 10–20 short-stack hands per opponent |
| 3 | Chip-EV play ignoring the points table | **Contradicted again.** Every bot priced all-ins in points; the field over-applies ICM to calls (calls 17% of shoves) | 0 | — | — |
| 4 | Hold'em intuition in other variants | Not testable (NLHE) | — | — | — |
| 5 | Folding too often to aggression | **Confirmed preflop.** In T6 the field folds 73% to steals, 77% to 3-bets, 82% to shoves and 73% to c-bets | Steals: 5 fold ≥ 75% (b01 75, b04 76, b07 79, b02 80, b08 81). 3-bets: b01 85%, b04 83% | **Steals:** b07 −2.2 ± 0.4 and b02 −1.4 ± 0.4 bb/100 against the field (≈ 0.4–0.7 points); against b06's re-shove defence the gap is 0.64 bb per steal faced, about 8 bb/100 (**≈ 2.5 points**). **3-bets:** b08 −1.1, b01 −0.8 (≈ 0.3) | **Fold to steal:** yes, about 12 per opponent per table. **Fold to 3-bet:** no, 2–3, so use a prior |
| 6 | Calling stations | **Weak.** Pooled river call rates: b07 55%, b02 46%, b01 43%, b08 38%; b03 calls 14% | 3–4 | b04 −1.9 ± 0.6 and b08 −1.6 ± 0.5 bb/100 facing river bets (≈ 0.5 points) | No: under 1 river bet per opponent per table |
| 7 | Bet size tracks hand strength | **Confirmed in code** | at least 3 | Not measured | No; use a static rule |
| 8 | Full-table ranges when short-handed | **Not at the VPIP level** (19% at 7–8 dealt → 55% heads-up, every bot widens). **Yes in heads-up responses:** b08 folds 73.5% of big-blind spots facing the button's raise, b01 62.5%, against 42% for b06 (T6 `hu_vs_raise`) | 2 | b01 converts 38% of heads-up finishes against 55–60% for b06 and b03. Over about 24% of tables reaching heads-up, that is ≈ 1.6 points | No: heads-up lasts a handful of hands |
| 9 | Ignoring the 200-hand cap | Not testable: 0 of 6,000 tables capped | — | 0 | — |
| 10 | Raise-to/raise-by confusion; fixed sizes | No illegal actions. Opens are 2.5 bb for 38–76% of each bot's opens; little information | 8 | about 0 | — |

The three bots whose large bets are value-only (hypothesis 7):
- **b08:** 0.75 pot (0.8 on the river) only with equity ≥ 0.72; thin value at 0.55 pot; bluffs at 0.5–0.6 pot (`bots/b08/T6/agent.py:833-851`).
- **b04:** 0.8 pot only with equity ≥ 0.8; 0.65 otherwise (`bots/b04/T6/agent.py:736-744`).
- **b02:** 0.7 pot only with equity ≥ 0.72; 0.5 for thin value (`bots/b02/NOTES.T6.md:19`).

### New leaks the hypotheses missed

- **N1: opening 2.2–2.5 bb at 10–30 bb, then folding to the re-shove.** This repeats full-opus-001's N2.
  - **Evidence:** openers fold 77% to 3-bets in T6. At 11–24 bb effective they fold AJs, KJs and KQo to b06's K8o, 77 and T6o (T6 table 7, hands 72, 73, 80).
  - **Bots:** every opener. b02, b04 and b07 faced the most 3-bets (3.3–3.4 per 100 hands in T6); b03 made the most opens.
  - **Cost:** b06 took +11.4 bb/100 out of these spots, mostly from the openers.
  - **Fix:** shove-or-fold at 20 bb or less, or call re-shoves with the top of the open range.
  - **Detectable within a table?** Slowly, from an opponent's open count.
- **N2: heads-up 3 bb opens folded to re-shoves.**
  - **Evidence:** in T6 table 7, hands 113, 117, 119 and 121, b07 opens to 3 bb at 160/320, 18–25 bb effective, and folds QJo, 96o, 85s and 97o to b04's re-shove. That is −3 bb four times in nine hands.
  - **Cost:** part of b07's 47% heads-up conversion.
  - **Fix:** open 2–2.2 bb heads-up and call re-shoves with the top 40–50%, or shove-or-fold at 15 bb or less.
- **N3: the field doesn't adapt to a re-stealer.** b06 tripled its 3-bets while the field's fold-to-3-bet rose 4.4 points.
  - **Why:** an opener meets b06's re-steal 2–3 times per table, far too few for a per-seat counter. No team built a population-level response between tournaments.
  - **Meaning:** the exploit is durable within the event.
- **N4: survival utility produces 4th places.**
  - **Evidence:** b02's concave utility at more than four alive, plus exact ICM at four or fewer, gave a 16–18% 4th-place rate for five tournaments.
  - **Fixes tried:** each local fix converted 4ths into 5ths and 6ths or cost 1sts (`bots/b02/NOTES.T6.md:162-179`).
  - **Cost:** b02 is −1.3 points per table against the mean, although its 7th–8th rate after T1 (21–25%) is at or below par.
- **N5: passive blind defence (full-opus-001's N3).** It is still the largest single gap: five bots re-raise 4–7% of steals and lose 0.35–0.54 bb per steal faced. Today's evidence is in §1.
- **Weaker this time: heads-up conversion tracking short-stack time** (full-opus-001's N5, ρ ≈ 0.88). With T6 hands under 10 bb against pooled heads-up wins, Spearman ρ is about 0.43.
  - **Counterexamples:** b03 converted 60% with 6.5% short hands, and b02 51% with 11.3%.
  - **What holds:** the re-steal cut b06's short-stack hands from 7.7% to 3.3%.

## 7. Exploits that worked

The house zoo never played in the scored tournaments. Every builder beat it in localsim (about 54–63 points per table), and zoo-tuned changes misled at least two teams. b06 capped its re-steal on zoo-heavy evidence. b08 was pulled toward tightness: "the house-bot field misled me toward tightness" (`bots/b08/NOTES.T6.md:31-33`). Zoo evidence is a crash and regression check only.

| Exploit (leak) | Who gained most | Evidence | Gave back? |
| :- | :- | :- | :- |
| Re-steal shove over a single open at 30 bb or less, gated on a tight table (N1, hypothesis 5) | b06: 7.1 3-bets per 100 hands, +1.60 bb each, 79% uncontested, **+11.4 bb/100** (T6). Exploit board, pooled: b06 +8.6, b03 +7.3 | +3.0 ± 1.8 points per table, T4–T6 against T1–T3. TAG-field A/B: ungated +3.3 and +6.0; gated +0.7 and +5.6 | **More busts:** 7th/8th rose from 21% to 29–32%, cheap under this table. **Against loose callers:** −5.2 ungated and −1.4 gated (house zoo). The gate is what makes it safe |
| Re-shove blind defence (N5) | b06: re-raises 25.6% of steals, +0.10 bb per steal faced against −0.30 to −0.54 for everyone else | Re-raise rate vs rank, ρ ≈ 0.69 | Nothing visible: b06's own leaks are within noise (`REPORT.md`) |
| First-in shoves into ICM-tight callers (hypotheses 3 and 5) | b03: 7.1 shoves per 100 hands, +1.09 bb each in T1. b06: 9.7 per 100, +0.99 each in T6. Exploit board, pooled: b06 +8.0, b03 +7.5 bb/100 | Every bot made +0.33 to +1.00 bb per shove; nobody was punished for volume | b08's open-equals-shove at 18 bb or less earned only +0.33 per shove; its shoves are less selective late |
| Light 3-bets against openers seen folding to 3-bets (hypothesis 5) | b05: 3.4 3-bets per 100 hands, +2.17 bb each | Local +1.6 and +1.8 at 60% frequency | Nothing measurable; it needs 3 or more samples per opener, which rarely accumulate |
| Steals and c-bets into folding blinds (hypothesis 5) | Exploit board: steals b03 +6.7, b07 +6.2; c-bets b07 +6.3, b03 +5.9 bb/100 | Blinds fold 73–75%; c-bets fold 73% | **b07 gave it all back:** the worst facing steals (−2.2) and facing opens (−1.1), and last overall |
| River value bets (hypothesis 6) | b05 +4.8 and b06 +3.8 bb/100. b02 and b05 earn +9.7 to +9.9 bb per river bet (T6) | b07, b02 and b01 call 43–55% of river bets | — |

### The exploit plan for our bot

**Build into the static strategy:**
1. **Re-steal shove over a single open with no callers at 30 bb effective or less.**
   - **Model:** the opener calls with 45% of its position-based open range, and each player behind calls with 0.7 × the default call width.
   - **Rule:** shove any hand with EV > 0.1 pot, or a top-10% hand with EV > 0 (b06's v1 rule).
   - **Gate:** use this wide version only while the table is tight (next list). Otherwise use a capped version with hand caps of 0.30, 0.20 and 0.12 at 12 bb or less, 18 bb or less, and 25 bb or less.
2. **First-in push/fold at 14–15 bb or less.** Score it in ICM points against callers modelled as ICM-tight: a caller needs pot odds + 0.06 with four or more alive, plus 0.03 when covered (b03's `CF` table). At 15–20 bb from the cutoff or later, shove the open range (b08) rather than open 2.5 bb and fold to a re-shove.
3. **Blind defence by re-shoving at 30 bb or less,** with the same EV as in 1. Flat only cheap big-blind defences, at pot odds + 0.05–0.07.
4. **Calls of all-ins with full ICM** (λ = 1): exact Malmuth–Harville on real stacks at five or fewer alive, and an equal-stacks grid above that. Expect about 62% equity to call off 8-handed. No extra margin: b08 measured both +1 and −1 margins as worse.
5. **Postflop: a simple bet-or-fold heuristic is enough.**
   - **C-bets:** about 80% of heads-up flops at 40–50% pot.
   - **Value bets:** at strength 0.62 or more.
   - **Facing large bets:** fold marginal hands to bets of 0.75 pot or more and to raises; those sizes are value in this field (hypothesis 7).
6. **Heads-up:**
   - **Small blind:** raise at least 60% and complete up to 90% (b06 v6).
   - **Big blind:** defend the top 85% against a min-raise and call about 35–40% against a 10 bb shove.
   - **Shove-or-fold:** at 15 bb or less. Never open 3 bb and fold to a re-shove (N2).

**Detect within a table.** Counters reset each table; priors and weights are in brackets.
- **VPIP per seat** [0.25, w 8]. It is observable every hand, so after about 30 hands it reliably gates the wide re-steal: opener and everyone behind ≤ 0.30.
- **Shove calls against the model's expectation** [k = 1.5]. Take the ratio of a seat's actual calls of our shoves to the calls the width model predicts. Scale that seat's call width by it, clamped to 0.4–2.5; it also turns the wide re-steal off at a ratio above 1.25.
- **Fold to steal, blinds only** [0.75, w 6]. Count only players in the blinds facing a cutoff, button or small-blind open. b03's T5 counter counted every player's response and fired on everyone (`bots/b03/NOTES.T6.md:100-104`).
- **Fold to 3-bet** [0.77, w 4]. Light 3-bets only after 3 or more samples and a shrunk rate of 0.60 or more (b05).

**Leave out (too risky against a field without the leak):**
- **Ungated wide re-steals at loose tables:** −5.2 against loose callers (`bots/b06/NOTES.T6.md:67-68`).
- **Late-position opens beyond about 45% on the button and 33% in the cutoff, until the real field shows it pays.** b03's 55%/36% for T6 coincided with its worst tournament. b08's 52%/36% measured −1.0 to −1.9 on one seed set and +1.5 to +2.5 on fresh seeds (`bots/b08/NOTES.T6.md:72, 85-87`). The evidence is mixed: keep it as a patch-window knob.
- **Removing ICM from calls:** b01, −3.1 in T5.
- **Heavier ICM or utility at four left:** b02's 4th-place spike.
- **Value bets of 0.9–1.0 pot:** b08 measured −1.2 to −2.9.
- **Postflop bluff-raises:** untested.
- **First-in shove-or-fold above 20 bb:** full-opus-001's b04.

## 8. A 60-minute build plan for a two-person team

**Architecture: one package.**
- **`agent.py`:** `act()` wrapped in try/except with a check-or-fold fallback; legal-amount helpers; the preflop engine; postflop rules; counters in `observe()` that do O(1) work per hand, with nothing like an 8-player ICM there.
- **`tables.py`:** loads precomputed arrays at import: `cls()`, `pct[cls]`, `eq_vs_top[cls][p]`, `CF[x][t]`, `icm[n][k]` and a call-width table by effective bb.
- **`tools/precompute.py`:** variant-generic. Deck, hole cards, card-use rule and ranking come from the event card. Run it in the background with a log.

**Time boxes.** Person A handles the pipeline and testing; person B handles the poker logic.

| Min | A | B | Submit |
| -: | :- | :- | :- |
| 0–3 | Both read the rules, variant, points and blinds; write down hand ranks, deck and action format. Run `caffeinate` | ← | |
| 3–10 | Template → safe bot: legal actions, try/except, push/fold at 14 bb or less from a fixed top-x% by players behind, otherwise fold or check. Run the validator | Write `precompute.py` (evaluator for the variant; class-vs-class equity, 240–1,500 boards per pair); start it | **v1 by about 10** |
| 10–22 | ICM grid from the official calculator and the announced points; exact Malmuth–Harville at five or fewer alive; fuzz and timing harness; 4-vs-4 A/B script | `shove_ev()`: P(all fold)·pot + Σ P(call)·(equity·win − risk·bubble factor), with ICM-tight caller widths. Push/fold and **re-steal shove at 30 bb or less** both use it | **v2 by about 22**, carrying the money mechanism |
| 22–35 | VPIP, PFR and shove-call counters in `observe()`; the tight-table gate | Blind re-shove defence; ICM calls of all-ins; heads-up ranges | **v3 by about 35** |
| 35–48 | A/B v3 against v2 in two fields: **(a) TAG proxy** (own versions plus a tight raise-or-fold variant: VPIP 20–25, folds 75–80% to raises) and (b) the house zoo, for regressions only. 600+ tables, two seeds | Postflop bet-or-fold: c-bet, value at 0.62 or more, fold to 0.75-pot bets and raises without two pair or better, stack-off guard | **v4 by about 45**, only if the A/B is ≥ 0 in the TAG proxy and no collapse in the zoo |
| 48–58 | Final validator, fuzz and timing on the exact files; notes for the patch windows | Probes (below); at most one knob | **Last by about 55** |

**Precompute (minutes 3–15):**
- **Equity:** class-vs-class all-in equity. b06 won with 240 boards per pair; b03 used 4,000. Reduce it to `eq_vs_top[cls][p]` with ranges sorted by `pct`.
- **The `CF[x][t]` table:** the share of hands with equity ≥ t against a top-x% shove range. It turns "the caller needs pot odds + ICM premium" into a call width in one lookup (b03).
- **ICM:** an `icm[n][k]` grid for the announced points (n = 2..8, chip share k/200), plus exact Malmuth–Harville at runtime for five or fewer alive. That is about 4–25 µs (`bots/b02/NOTES.T6.md:90-91`).
- **A call-width table by effective bb** (b06's `_CALLW`) as a fallback when tables are missing.

**Test before every submission (about 3 minutes):**
1. **Validator:** it passes.
2. **Fuzz:** 0 exceptions with the try/except disabled, covering all-in for less, side pots, two-handed play and stacks under 1 bb.
3. **Timing:** p99 under 300 µs and max under 600 µs locally. Monte Carlo budgets of 0.35 ms or less, since T1 timed out at 0.45–0.5 ms under load. `observe()` should stay under 5 ms, with nothing at the 50 ms watchdog.
4. **Probes:**
   - the re-steal range at 20 bb against a button open, with a tight and with a loose table;
   - the push range at 10 bb on the button, 8-handed;
   - the call range against a 10 bb shove;
   - the heads-up small-blind and big-blind ranges at 15 bb.
5. **A/B:** one change at a time, in the TAG proxy field, ≥ 0 on two seeds. Confirm a selected winner on a fresh seed (b08's winner's-curse lesson). Noise is ±1.5–3 points at 600–1,000 tables.

**Patch windows (20 minutes each):**
- **Read the real field's rates first:** folds to opens, 3-bets and c-bets.
- **Compare with the same code's earlier tournaments,** where identical code moved 1.5–2.4 points.
- **Prepare knobs:** re-steal gate (VPIP 0.27, 0.30 or 0.33), opener call share (0.40, 0.45 or 0.55), push depth (14 or 18 bb), open scale.
- **Change one knob at a time.** Keep the last good version as a resubmittable fallback.

**Expected result.** This plan reproduces b06's T4–T6 bot, which scored 35.6–37.4 in a field where everyone else scored 27.2–35.3. b06's minute-4.9 v1 already had its core, so the plan is feasible in 35 minutes for builders who copy tables. For humans it needs the precompute to start by minute 5. Nothing here was tested as a single bot, and the real field (other AI tools, human steering) may call more. That is why the re-steal is gated per table rather than always on.
