# Debrief: full-opus-001

No-limit hold'em, 8 seats, 2,000 chips, points 100/60/40/25/15/10/5/0, blinds doubling every 25 hands, 6 tournaments × 1,000 tables, 8 Opus 5.5 builders. Sources are `REPORT.md` and `strategies.json` in this folder, `bots/<team>/T<k>/` with `NOTES.T<k>.md`, `results/T<k>/` (`summary.json`, `tables.json`, `profile.json`, hand logs), `submissions/<team>/index.jsonl`, `state.json` and the builder transcripts in `logs/`.

## The short version

1. **Preflop pressure, priced by fold rates, won.** b06 (1st, P(1st) 97%) and b04 (2nd) re-shoved over opens at 8–32 bb and shoved first-in when the price was right. They 3-bet 4.0 and 4.7 times per 100 hands; every other bot did so 1.2–2.2 times (T6 `profile.json`). Each bot made about **+1.1 bb per preflop shove**, whether it shoved 3.4 or 8.5 times per 100 hands. Wider shoving was never punished.
2. **The field's main leak is ICM applied too hard to calls**, the reverse of hypothesis 3. The field folded 83% to shoves and 80% to 3-bets, and drifted further that way during the event: folds to a 3-bet went from 78.2% in T1 to 81.2% in T6.
3. **Surviving doesn't pay under this points table.** 1st minus 2nd is 40 points; 8th minus 5th is only 15. b04 went out 7th or 8th on 32% of tables and still finished 2nd. b07 had the fewest early exits and finished last.
4. **The build decided it.** Both winners' key mechanisms were already in their T1 bots, accepted at build minutes 33 (b06) and 57 (b04). Later patches moved real-field scores by about 1–2 points, mostly inside the noise. Local proxy fields (the house zoo, self-play) misled at least four teams.
5. **Robustness was table stakes.** Over about 4.6M decisions there were 0 timeouts, errors, illegal actions or hangs.

**Caveats.** All 8 builders were the same model, so this field is more uniform than the real one. Each tournament had 1,000 iterations here against 10,000 at the real event, so per-tournament intervals here (±2 points per table) are about 3× wider. The house zoo never played in the scored tournaments. Converting chips to points is rough (see §6).

---

## 1. What won

Points per table = weighted score / 21. The field mean is 31.875.

| Rank | Bot | Weighted (95% CI) | Per table | vs mean | P(1st) | P(top 5) | Won | Heads-up won | Out 7th/8th |
| -: | :- | -: | -: | -: | -: | -: | -: | -: | -: |
| 1 | b06 | 733.9 ± 20.8 | 34.95 | +3.1 | 97% | 100% | 17% | 59% | 24% |
| 2 | b04 | 702.4 ± 20.8 | 33.45 | +1.6 | 3% | 100% | 17% | 58% | 32% |
| 3 | b02 | 681.9 ± 18.5 | 32.47 | +0.6 | 0% | 100% | 13% | 51% | 23% |
| 4 | b05 | 657.6 ± 18.1 | 31.31 | −0.6 | 0% | 72% | 10% | 42% | 24% |
| 5 | b01 | 656.0 ± 18.1 | 31.24 | −0.6 | 0% | 66% | 10% | 42% | 25% |
| 6 | b08 | 652.7 ± 18.3 | 31.08 | −0.8 | 0% | 52% | 12% | 49% | 24% |
| 7 | b03 | 637.9 ± 17.9 | 30.38 | −1.5 | 0% | 7% | 11% | 46% | 27% |
| 8 | b07 | 632.7 ± 17.2 | 30.13 | −1.7 | 0% | 2% | 10% | 49% | 22% |

**Rank gaps inside the noise:**
- **4th, 5th and 6th are a three-way tie.** b05, b01 and b08 are 4.9 weighted points apart, which is 0.23 points per table. Their 90% rank ranges are all 4–7 (`REPORT.md`, rank view).
- **7th against 8th is noise.** b03 and b07 are 5.2 weighted points apart.
- **No single tournament separated adjacent ranks.** Every rank in every tournament carries the ≈ mark. Identical code moved 2.7 points between tournaments: b04 scored 34.45 in T4 and 31.78 in T5, and b08's T4 code scored 32.04 in T4 and 29.72 in T6.
- **The real separations are three.** b06 over b04 (1st in 97% of resamples), b04 over b02 (2nd in 88%), and the top three over the rest (P(top 5) 100%).

### b06: in-table fold-rate model with re-steal shoves (1st)

**Approach.** A tight-aggressive bot built on the kit's house-bot helpers, plus per-seat counters reset at every table. The counters are folds to a raise, folds to a 3-bet, folds to a bet, VPIP/PFR, aggression and weak shown hands, each shrunk to a prior (`bots/b06/T6/agent.py:95-122`).

**Mechanisms that seem to matter:**
- **Re-steal shove**, priced from the opener's own fold-to-3-bet. The prior is 0.75 with weight 4. The builder measured this as its biggest gain: +2.9 points in self-play, +3.3 in a mixed field and +0.8 in a tight field (`bots/b06/NOTES.T6.md:16`).
  ```python
  # bots/b06/T6/agent.py:396-415 (abridged)
  if (RESTEAL and sp.raises == 1 and sp.callers <= SQUEEZE_MAX and ... 8 <= eff_bb <= RESTEAL_BB ...):
      fr = max(0.05, min(0.9, self.fold_to_3bet(raiser)))      # (folds + 0.75*4) / (faced + 4)
      pf = fr
      for s_ in behind:
          pf *= min(0.97, self.fold_to_raise(s_) + 0.05)
      eqc = eq_vs_range(cls, max(0.02, p_r * (1.0 - fr)))      # equity vs the part of the range that calls
      ev = pf * pot + (1.0 - pf) * (eqc * (pot + risk + call_amt) - risk)
      if ev > RESTEAL_MARGIN * risk:                           # 5% of the risk
          return self.allin(sp)
  ```
- **Auto-steal when everyone behind folds often enough.** If P(all behind fold) ≥ 0.72, it opens any hand in the top 90% (`agent.py:302-338`). At 13 bb or less it uses a model-based shove EV built from the same fold rates (`agent.py:311-334`).
- **A stack-off guard.** Postflop, a call of 35% or more of its stack with five or more players alive needs strength ≥ 0.66 (`agent.py:518-520`). Added for T2, it measured +0.7 to +3.8 in TAG fields and −0.3 in a mixed field (`NOTES.T6.md:19`).
- **Bet-or-fold postflop.** It made 3.4 bets or raises per call, the most aggressive in the field. Bluff frequency comes from the observed fold-to-bet rate.

**How sure.** b06 won T2–T6 and was 3rd in T1. Its weighted lead over b04 is 31.5 points, and it is 1st in 97% of bootstrap resamples. The per-mechanism numbers are the builder's local A/B tests, whose noise is about ±2 points at 500 tables, so treat them as directional. The real-field record supports the patches only weakly: the T1 version scored 33.95 and later versions averaged 35.2 over T2–T6, a gain of about +1.2 points that is within noise.

### b04: shove-or-fold to 20 bb, ICM-priced re-steals (2nd)

**Approach.** Wide late-position opens (button 48%, small blind 62%). First-in shove-or-fold at 20 bb or less. Re-steal shoves at 32 bb or less. All of these are scored in ICM points blended 80/20 with chip-linear points. It has an exact Malmuth–Harville calculation when five or fewer players are left (`bots/b04/T6/agent.py:38-89`).

**Mechanisms:**
- **First-in shove-or-fold at 20 bb or less**, with per-seat call ranges and a check of ICM EV including fold equity:
  ```python
  # bots/b04/T6/agent.py:417-458 (abridged)
  if eff_bb <= 20:
      f = PUSH.get(nb, 0.15) * (10.0 / max(eff_bb, 1.5)) ** 0.6
      if pct <= f * PUSH_CAP and sp.behind:
          for x in sp.behind:
              cr = max(0.05, min(0.5, 0.12 + 0.3 * (0.6 - self.fold_rate(x))))  # prior call range ~12%
              ...
              cr = min(0.7, self.shove_call(x, cr))   # learned per seat, prior weight 4
              pf *= 1 - cr
          ev = self.ev_allin(sp, eq, my_add, final, big[1] <= my_total, pf, big[0])
          if ev > 0 or pct <= 0.03:
              return self.allin(sp)
      ...
  ```
  The builder's A/B tests: 13→16 bb gave +1.7, and 16→20 bb gave +2.6, with all three variant copies above all baseline copies (`bots/b04/NOTES.T6.md:61-62`). Going to 25 bb won locally (+0.95 over 4,900 tables), but scored 31.59 in T2 against 33.99 at 20 bb in T1. The team reverted (`NOTES.T6.md:94-100`). That difference is within noise (±3.1).
- **Re-steal at 0 ICM-points EV** (`agent.py:507-523`). The builder's diagnostic found its re-shoves at 13–30 bb used a median hand percentile of 0.42, against 0.05 for the hands that called them (`NOTES.T6.md:53`). Narrowing them cost 1.9–2.9 points (`NOTES.T6.md:54,60`).
- **Re-raising steals from the blinds.** It re-raised 19.6% of steals it faced in T6. That held its average result to −0.05 bb per steal faced, against −0.16 to −0.59 for everyone else (T6 `profile.json`, `vs_steal`).

**What it gave back.** It called 48% of river bets (−4.2 bb/100 against the field) and called c-bets too often (−2.4 bb/100). Its T4 patch, a barrel penalty against passive bettors (`agent.py:630-639`), cut river calls from 54% in T1 to 40% in T6 (`profile.json`, `vs_river_bet`) without a visible change in score. It also had the most early exits (32%).

**How sure.** 2nd in 88% of resamples and top 3 in 100%. T1, T3, T4 and T6 were all 34.0–34.45; T2 and T5 dipped to 31.6–31.8, and T5 was identical code.

### b02: ICM-tight with a precomputed points table (3rd)

**Approach.** Its own tables, with no house helpers: 169×169 equity, equity against the top-p% of hands, and an ICM grid `icm[n][k]` for the announced points. It is the tightest bot (VPIP 18–19%). Push/fold at 14 bb or less is scored by ICM EV, with folding charged for the blinds still to come:
```python
# bots/b02/T6/agent.py:660,673-675
c = call_range(effc / bb, s == obs["bb_seat"]) * self.looseness(s) ** 0.5 * self.call_mult()
...
# folding is not free when short: blinds keep coming
r_fold = max(0.0, R - BLIND_COST * self.hl_fac * (obs["sb"] + bb) * min(1.0, 3.0 / max(2, n)))
return ev - self._icm(n, r_fold / tot)
```
`call_mult()` rescales the assumed calling range by how often its shoves were actually called at this table (`agent.py:414-416`). Postflop, it adds a +0.12 strength penalty when its own bet is raised (`agent.py:743-746`), because "bots rarely bluff-raise". That was worth +2.3 points in a mixed field (`bots/b02/NOTES.T6.md:9-13`).

**How sure.** It won T1 (34.90), then slid from 33.84 to 30.62 over T2–T4 on identical code. It is 3rd in 84% of resamples. Its profile is safe top 3 (38%) but few wins (13%): "tight ICM play buys a safe top 5, not wins" (`strategies.json`).

### b05: vectorized evaluator and Monte Carlo against bet-narrowed ranges (4th)

**Approach.** The most engineered bot: a numpy 7-card evaluator with a 31 MB lookup table (`bots/b05/T6/nf.npy`), and postflop Monte Carlo equity against opponent ranges weighted by how they bet. The narrowing grows with bet size and with raises:
```python
# bots/b05/T6/agent.py:421-436 (abridged)
ratio0 = to_call / max(1, pot - to_call)
gam.append(GAM0 + GAM1 * min(ratio0, 1.5) + 0.6 * (a - 1.0))   # GAM0 0.8, GAM1 1.0; raises add RAISE_X = 1.0
eq = ev.equity(hole, board, n_opp, ranges, gam)                 # weight ∝ (strength rank + 0.05) ** gamma
```
The builder called the bet narrowing its "biggest single gain" (`bots/b05/NOTES.T6.md:9`). It had the best result facing c-bets: −1.1 bb per c-bet faced against −1.2 to −2.3 for the others (T6).

**Weakness.** It is passive preflop. It re-raised only 3.7% of steals (T6) and shoved 3.4 times per 100 hands, the fewest. It spent 11.9% of its hands under 10 bb, the most, and converted only 42% of heads-up finishes.

**How sure.** Tied with b01 and b08 for 4th to 6th; P(top 5) 72%.

### b01: ICM push/fold, MC postflop, position-aware opener ranges (5th)

**Approach.** Push/fold at 14 bb or less (18 bb with two or fewer behind) in ICM points. Monte Carlo postflop within a 0.22–0.4 ms budget, and ICM checks on big calls. Its real-field gain came from two patches:
```python
# bots/b01/T6/agent.py:80-88 (selected lines)
SHOVE_K = 2.6  # prior shove range ~ SHOVE_K / stack_bb
HU_SHOVE_K = 6.5    # HU opponent shove range prior ~ HU_SHOVE_K / stack_bb
OPEN_POS_F = {0: 2.0, 1: 2.0, 2: 1.6, 3: 1.25, 4: 0.95}
ICM_ALPHA = 0.85  # blend of ICM vs chip-linear utility
```
`OPEN_POS_F` widens the opener's estimated range by position, so the bot re-steals and defends more against late opens. It arrived for T3, and the T4 stack-off guard followed (`bots/b01/NOTES.T6.md:141-145,120-123`). The bot went from 29.7 points per table in T1–T3 to 31.8 in T4–T6. At +2.1 ± 1.5 this is the only clearly real patch gain in the event.

**Limits.** Three tournaments of heads-up patches (a heads-up harness, heads-up-only stats, a limp variant) left heads-up conversion at 41–45% (`NOTES.T6.md:59-60,89-90`). It also calls river bets too often (−2.3 bb/100); for example, T6 table 3 hand 69 calls a 1,492 river bet with a pair of threes.

**How sure.** P(top 5) 66%, tied with b05.

### What the top five share, and what separated the top two

- **Shared by all five:** a 169-class preflop table with equity against the top-p% of hands, push/fold when short, and points-table-aware all-in decisions.
- **What separated the top two was volume of fold-equity aggression**, not accuracy:

| Bot | 3-bets per 100 hands | bb per 3-bet | Shoves per 100 hands | bb per shove | Shoves taking the pot | Re-raises vs steals | bb per steal faced | Hands under 10 bb |
| :- | -: | -: | -: | -: | -: | -: | -: | -: |
| b04 | 4.7 | +2.1 | 8.5 | +1.12 | 71% | 19.6% | −0.05 | 3.9% |
| b06 | 4.0 | +1.9 | 6.7 | +1.10 | 75% | 15.3% | −0.16 | 2.9% |
| b02 | 2.2 | +2.6 | 5.3 | +1.06 | 70% | 7.7% | −0.44 | 6.1% |
| b08 | 2.2 | +3.2 | 4.1 | +0.96 | 67% | 4.5% | −0.44 | 6.2% |
| b01 | 1.8 | +3.5 | 5.1 | +1.22 | 67% | 6.3% | −0.38 | 9.5% |
| b03 | 1.7 | +3.0 | 4.2 | +1.14 | 61% | 4.3% | −0.51 | 8.2% |
| b07 | 1.6 | +3.1 | 3.7 | +1.09 | 66% | 3.5% | −0.59 | 10.6% |
| b05 | 1.2 | +3.0 | 3.4 | +1.15 | 60% | 3.7% | −0.40 | 11.9% |

  All T6 (`results/T6/profile.json`). 3-bets are raises in the `vs_open` and `vs_steal` spots. Results are whole-hand big blinds.
- **The tight 3-bettors earn more per 3-bet; the winners make two to three times as many.** The spread in bb per shove (+0.96 to +1.22) is small against the 2.5× spread in volume.
- **Re-raise rate against steals follows final rank closely** (Spearman ρ ≈ 0.83, n = 8).

## 2. What lost

- **Timeouts, crashes, illegal actions: none.**
  - **Scored tournaments:** 0 timeouts, errors, illegal actions or hangs in all 48 bot-tournaments, about 4.6M decisions (`REPORT.md`, Substitutions).
  - **Near misses:** three decisions ran over 1 ms of raw CPU. They were b08 at 1,247 µs (T2), and b04 at 1,197 µs and b05 at 1,099 µs (T3). All three passed only because of the runner's slow-core adjustment (`slow_core_passes` in `results/T2,T3/summary.json`; rule in `arena/tournament/play.py:156-161`). Under a strict 1 ms rule each would have been a fold; that costs nothing measurable at one in 110,000 decisions.
  - **Robustness alone bought nothing.** b03 was built for robustness, with a try/except safety net and about 0.1 ms per decision, and finished 7th.
- **Late or broken submissions: none reached a table.**
  - **Validator rejections:** the only non-cooldown rejection was b06 around build minute 27, "1 decisions ran past 50 ms". It was fixed and accepted at minute 28 (`logs/b06.jsonl`, around line 533).
  - **Cooldown:** most rejections were the 5-minute cooldown, which b04 hit at least five times in the build.
  - **Last-minute submissions:** b04's T1 bot was accepted at build minute 56.8 and placed 2nd in T1, so late submission did not hurt when `check_bot` was run first.
- **Ignoring the variant or the points table: nobody.** All eight priced all-ins with the points table, every one of them by build minute 21 (§5). The failure ran the other way:
  - **Over-weighting survival.** b07 needed about 80% equity to call off its stack with four or more players left. Its builder flagged this as "exploitable by bots that shove relentlessly" (`bots/b07/NOTES.T6.md:71`); it had the fewest early exits (22%) and finished last. b03's T3 ICM "bubble factor" cut its 6th–8th finishes from 45% to 37% (`bots/b03/NOTES.T6.md:83`) without raising its score (30.2–31.3 in every tournament).
  - **Loose play that wasn't priced.** b03 had the most opens and steals (60%), then folded 87% to 3-bets by T6 and faced 4.5 3-bets per 100 hands. Hands where it faced a 3-bet cost it −8.3 bb/100, against a field average of −4.4.
  - **Trusting local proxies over real results:**
    - b07 raised its ICM premium on zoo and TAG-field evidence (PREM 2.2: 44.4 vs 39.2 for v2, `bots/b07/NOTES.T6.md:30`).
    - b04's 25 bb push range won locally and lost in T2.
    - b05's loosening against aggression (T3–T4) scored 30.8 and 29.8, then was reverted (`bots/b05/NOTES.T6.md:41-44`).
    - b08 added a fixed top-12% re-steal for T5 (30.32, with 147 8th places), blamed it, and reverted. The reverted code then scored 29.72 with 144 8th places in T6 (`bots/b08/NOTES.T6.md:101-107`; `results/T6/summary.json`). The drop was most likely noise or field drift, not the patch.

## 3. Archetypes and models

| Group | n | Weighted score (mean ± 95% CI across teams) | Notes |
| :- | -: | -: | :- |
| opponent_model | 1 | 733.9 | b06 |
| pressure | 1 | 702.4 | b04 |
| free choice | 4 | 662.0 ± 13.1 | b02 681.9, b05 657.6, b01 656.0, b08 652.7 |
| minimal_robust | 1 | 637.9 | b03 |
| equity_tables | 1 | 632.7 | b07 |
| **Model: Opus 5.5** | 8 | 669.4 ± 23.9 | the only model |

- **Archetypes can't be separated from builders.** With n = 1 in four groups, the two "aggressive" starting ideas finishing 1st and 2nd is one draw. The ranks themselves are well separated (b06 1st 97%, b04 2nd 88%), so the result is real for these bots. Whether it came from the starting idea or from the builder is unknown.
- **Free choice converged on one style.** The four free-choice bots landed in a 29-point band, 1.4 points per table. All four built "ICM TAG plus push/fold", and only b02 broke away.
- **No model comparison is possible.** A mixed-model event is needed before reading anything into model.

## 4. Time use

The report's submission timeline is wrong for this event. It counts from the *resumed* build window, because `arena/referee/report.py:142-151` uses `windows[kind=build].start`, the time the build resumed after a usage-limit pause.

**The real clock.**
- **Build start:** 11:56:45.7. The nudge `left_s` values in `state.json` and "ends 12:56:45" in the transcripts agree.
- **The pause:** at build minute 48.55, after which the build resumed with 687 s left.

On the real clock:

| Team (rank) | First accepted | At 5 min | At 10 min | At 20 min | Key mechanism accepted | T1 bot accepted | Build submissions |
| :- | -: | :- | :- | :- | :- | -: | -: |
| b06 (1) | 4.3 | v1: TAG + per-seat fold stats | v1 (v2 at 10.1) | v2: + ICM margin, tighter opens | model shove EV + auto-steal 28.1; re-steal shove 33.3 | 33.3 | 5 |
| b04 (2) | 3.4 | v1: ≤13 bb push/fold chart | v1 | v2 (13.9): + opponent model, ICM all-ins, re-steal at EV ≥ 1 bb | re-steal at EV ≥ 0 21.0; shove-or-fold ≤16 bb 51.7, ≤20 bb 56.8 | 56.8 | 9 |
| b02 (3) | 5.0 (4:59.6) | v1: chip-EV push/fold, heuristic postflop | v1 | v4 (14.9): ICM blend, blind cost | +0.12 penalty when raised postflop 50.4 | 50.4 | 6 |
| b05 (4) | 5.9 | none | v1: equity bot, no ICM | v3 (19.3): ICM all-ins, position-aware ranges | bet-based range narrowing 32.1 | 52.7 | 6 |
| b01 (5) | 4.6 | v1: heuristic postflop | v1 | v5 (17.3): MC postflop, re-steal, ICM blend | — | 44.0 | 8 |

Minutes are build minutes, from `submissions/<team>/index.jsonl`. Contents come from each team's `NOTES.T6.md` submission list. Field-wide, 7 of 8 teams had a bot accepted by minute 5 (b05 at 5.9), and 8 of 8 by minute 10. b03's first came at 2.0 minutes.

**What a first bot looked like.** b06's minute-4 bot was a complete 15 KB agent. The builder read the rules, copied the kit's house-bot helper `_common.py` (evaluator, Spot parser, `features()`, preflop tables), started a precompute in the background, wrote the agent in one pass, ran a 30-table smoke sim, ran `check_bot`, and submitted (`logs/b06.jsonl` lines 3–164). Six of eight bots shipped that copied helper; b02 wrote its own tables, and b05 its own evaluator.

**Implications for a 60-minute human build:**
- **The money mechanisms came late.** b06's re-steal shove came at minute 33, and b04's 20 bb shove-or-fold at minute 57. A first bot at minute 4 is insurance, not the score. b06's own versions in self-play: v1 (minute 4) 29.6, v6 (minute 33) 34.1 (`bots/b06/NOTES.T6.md:17`).
- **The real starter kit probably has no hand evaluator or strength helper.** It lists an agent template, simulator, ICM calculator, points and blinds (`docs/OFFICIAL_FORMAT.md:11`). A human team must budget for an evaluator and preflop tables, or confirm that bringing them is allowed.
- **Humans will be slower than these builders.** A two-person team with Codex or Astra should plan on a legal bot by about minute 10, the all-in EV engine by about minute 30, and no untested change after minute 50.
- **Patches mattered less than the build.** Real-field scores moved about 1–2 points from patches, mostly inside noise (b06 +1.2, b04 none, b01 +2.1). Because T2–T6 carry 20/21 of the weight, still prepare a patch-window checklist (§8).

## 5. Rules-specific insight

- **The blind schedule compresses the game.** Tables lasted about 127 hands; T1–T6 averaged 126.3–127.5 hands per table, and 0 of 6,000 tables reached the 200-hand cap. By level 6 (hands 126+, 320/640) the whole table holds 25 bb.
  - **Where hands are played:** 53% at 40 bb or more (levels 1–2, low stakes), 24% at 20–40 bb, 18% at 10–20 bb and 7% under 10 bb (T6 `profile.json`, stack buckets).
  - **Where chips change hands:** at 8–30 bb, in levels 3–5 (hands 51–125).
  - **Heads-up is a coin-flip phase.** It typically lasts 3–12 shove/fold hands with 25–50 bb in play. Samples: T6 tables 5, 8, 9, 41 and 62, where the chip leader at the start of the sampled heads-up won 3 of 5.
- **The points table rewards winning.** 1st minus 2nd is 40, 2nd minus 3rd is 20, and the bottom four places are 5 apart. Busting 8th instead of 5th costs 15 points; converting 2nd into 1st gains 40.
  - **ICM still taxes calls.** A full-stack call-off at eight equal stacks needs about 61–62% equity, because a double-up is worth about 51 points against 31.9 (`bots/b01/NOTES.T6.md:166-167`, `bots/b07/NOTES.T6.md:13`).
  - **That tax hits callers, not shovers.** Shoves win the blinds 60–75% of the time without a call. The good play was therefore "ICM-tight calls, fold-equity-loose shoves", which is exactly what b04 and b06 did.
- **The hand cap never mattered.** No table reached it. b02's ICM ramp over the last 20 hands (`bots/b02/T6/agent.py:475-477`) never triggered.
- **The variant was standard hold'em,** so there was nothing to adapt to.
- **Adapting to the points table was fast:**
  - **Push/fold modes:** in the first or second submission of all eight bots.
  - **Points-table pricing of all-ins:** b08 at 8.3 min (ICM premium), b06 at 10.1 (heuristic margin), b07 at 10.7 (ICM premium), b04 at 13.9, b05 at 14.1, b02 at 14.9, b01 at 17.3 and b03 at 20.7 (`bots/b08/NOTES.T6.md:114-115` and each team's submission list).
- **Adapting to the field never happened.** Between tournaments the field got *more* exploitable.

  | | T1 | T6 |
  | :- | -: | -: |
  | Folds to a 3-bet (all bots) | 78.2% | 81.2% |
  | 3-bets faced | 16,612 | 18,851 |
  | Folds to a shove | 82.4% | 83.5% |

  b03 went from folding 79% of 3-bets to 87%, and b01 from 83% to 86% (`results/T1,T6/profile.json`). Teams tuned against their own versions and could not see the other bots. A static exploit designed on day one kept paying through T6.

## 6. Where the field leaks points

**How costs are converted.** Costs are big blinds per 100 hands relative to the rest of the field: the report's leak measure, or my T6 recomputation from `profile.json` with the same formula (`arena/tournament/profile.py:323-332`).

Rough conversion: **1 bb/100 ≈ 0.5 points per table, range 0.3–1.**
- **1 bb/100 ≈ 1 bb per table**, since a bot plays 93–98 hands per table.
- **An average big blind over the hands played is about 80 chips** (T6 stack mix).
- **A chip is worth about 0.012 points** at eight equal stacks, and about 0.004 points across a whole table: b06's +720 expected chips per table came with +3.1 points.

### The hypotheses in `docs/FIELD_STUDY.md`

| # | Hypothesis | Verdict today | Bots | Rough cost | Detectable within one table? |
| :- | :- | :- | :- | :- | :- |
| 1 | Timeouts, exceptions, illegal amounts in rare spots | **Not seen.** 0 of each in about 4.6M decisions; 3 decisions over 1 ms passed only via the slow-core rule | 0 (3 near-misses) | ~0 | n/a |
| 2 | Same thresholds at every depth, no push/fold mode | **Partly.** Every bot has push/fold code, but three don't widen when short: b05 VPIP 22% under 10 bb vs 25% at 20–40 bb, b07 25% vs 23%, b03 26% vs 31%. b06 goes 18% → 51% | 3 | Indirect: these bots spend 8–12% of hands under 10 bb (b04/b06: 3–4%) and convert 42–49% of heads-up finishes. Hard to price | Yes. An opponent's VPIP while under about 10 bb shows within about 20 of its short hands |
| 3 | Chip-EV play ignoring the points table | **Contradicted.** Every bot priced all-ins in points; the field errs toward over-applying ICM (N1) | 0 | — | — |
| 4 | Hold'em intuition in other variants | Not testable (NLHE) | — | — | — |
| 5 | Folding too often to aggression | **Confirmed preflop.** Field folds 76% to steals, 80% to 3-bets (81% by T6), 83% to shoves. On c-bets the field folds 69%, but calling more lost: b04 −2.4 bb/100 facing c-bets | 4 fold ≥82% to 3-bets (b01, b03, b05, b08); 4 fold ≥79% to steals (b01, b02, b03, b05) | Facing steals, the over-folders trail the field by 0.4–1.4 bb/100 (pooled) and trail b04 by about 4–6 bb/100 (T6): **≈ 2–3 points per table** | Fold to a raise: yes, about 20–40 observations per opponent. Fold to a 3-bet: **no**, 2–5 observations, so use a prior |
| 6 | Calling stations | **Weak; two bots.** b04 called 48% of river bets (−4.2 bb/100), b01 41% (−2.3). Everyone else folds 54–71% | 2 | ≈ 1–2 points per table | No. Under 1 river-bet decision per opponent per table; only showdowns hint at it |
| 7 | Bet size tracks hand strength | **Confirmed in code** (see the list below) | 4 | Not measured | No. Needs showdowns tied to sizes, a handful per table. Use a static rule |
| 8 | Full-table ranges when short-handed | **Mostly not.** Field VPIP 20% at 7–8 dealt, 35% at 3–4, 54% heads-up. But b01, b02, b07 and b08 fold the heads-up button 26–29%, against 10–12% for b03 and b06 (T6 `hu_open`) | 4 | Heads-up conversion 42–51% vs 58–59%. Worth up to 1.6 points, but heads-up-only patches didn't move it (N5) | No. Heads-up lasts 3–12 hands |
| 9 | Ignoring the 200-hand cap | Not testable: 0 of 6,000 tables reached the cap | — | 0 | — |
| 10 | Raise-to/raise-by confusion; fixed sizes | No illegal actions. Opens are fixed at 2.2–2.5 bb (42–83% of each bot's opens at its usual size) and carry little information | 8 (fixed sizes) | ~0 | — |

Hypothesis 7, the four bots whose biggest sizes are value-only:
- b02 bets 0.75–0.9 pot only with equity ≥ 0.78 (`bots/b02/T6/agent.py:716-721`).
- b04 bets 0.75×pot (0.9 against stations) only with strength ≥ 0.80 (`bots/b04/T6/agent.py:592-595`).
- b05's 0.75-pot river bets are value only (`bots/b05/T6/agent.py:440-443`).
- b06 uses 0.75 pot for value on wet boards or against stations, and 0.5 for c-bets and bluffs (`bots/b06/T6/agent.py:467-485`).

### New leaks the hypotheses missed

- **N1: ICM applied too hard to calls (the inverse of hypothesis 3).**
  - **Evidence:** the field calls only 16% of shoves, 13% at 20–40 bb. Meanwhile b04 re-shoves near-random hands at 13–30 bb: median hand percentile 0.42, against 0.05 for the callers (`bots/b04/NOTES.T6.md:53`).
  - **Bots:** six call shoves 17% of the time or less: b01 12%, b03 13%, b04 15%, b05 15%, b08 16%, b07 17%.
  - **Cost:** b03 −1.7 and b07 −0.7 bb/100 facing shoves (pooled), plus the opens and blinds surrendered in N2 and N3.
  - **Detectable within a table?** Weakly. Each opponent faces a shove about 8–10 times per table.
- **N2: opening small at 13–30 bb, then folding to the re-shove.**
  - **Evidence:** b05's own diagnostic: "M pf_raise_fold -357 (n=229) and M pf_raise_call -259 (n=66): opening 2.2bb at 13-30bb then folding to / flatting a 3-bet" (`bots/b05/NOTES.T6.md:155-156`). In T6 table 13, hands 79 and 91, b03 opens 2.5 bb and b04 re-shoves 52s and Q5o for 15–18 bb.
  - **Bots:** b03 above all, plus b05, b07 and b08.
  - **Cost:** in hands where it faced a 3-bet, b03 lost −8.3 bb/100 against −4.4 for the field, ≈ −2 points per table.
  - **Fix:** shove-or-fold at 20 bb or less (b04).
  - **Detectable within a table?** Slowly, from counts of opens and folds to 3-bets.
- **N3: passive blind defense.**
  - **Evidence:** flat-calling steals (b07 18%, b08 19.5%) or folding them (b03, b05 81%) instead of re-raising. Per steal faced, b07 loses 0.59 bb and b04 loses 0.05.
  - **Cost:** b07 −2.5 bb/100 against the field (pooled), ≈ −1.3 points per table. b04 is +4.0 bb/100 (T6), ≈ +2 points.
- **N4: calling postflop raises.**
  - **Evidence:** raises are almost always value in this field. b02 checked T1–T5 sample hands: "multi-street raises were nearly always value (sets, boats, 2 pair)" (`bots/b02/NOTES.T6.md:146`). Example: T6 table 3 hand 43, where b07 with AQ called a flop raise and a turn shove against quads and lost 49 bb. Treating raises as strong was worth +2.3 points for b02 (mixed field), and similar narrowing was b05's biggest gain.
  - **Detectable within a table?** No; build it in statically.
- **N5: heads-up decided by stacks, not by heads-up skill.** Heads-up conversion tracks how rarely a bot is short-stacked:

  | Bot | Hands under 10 bb (T6) | Heads-up won (pooled) |
  | :- | -: | -: |
  | b06 | 2.9% | 59% |
  | b04 | 3.9% | 58% |
  | b02 | 6.1% | 51% |
  | b08 | 6.2% | 49% |
  | b03 | 8.2% | 46% |
  | b01 | 9.5% | 42% |
  | b07 | 10.6% | 49% |
  | b05 | 11.9% | 42% |

  - **Correlation:** Spearman ρ ≈ 0.88 over the eight bots.
  - **Heads-up patches didn't help:** b01's T4–T6 patches and b05's T6 patch left their conversion at 41–43% (T6: b01 107/250, b05 104/255).
  - **Even the winner leaks heads-up:** b06 opens 2.7 bb and then folds ATo, A4o and JTs to 13–18 bb re-shoves (T6 table 62 hand 122, table 41 hand 122, table 8 hand 124). Its 3-bet range model, `p_r × 0.4`, is too tight heads-up.
  - **Cost and fix:** the cost is mostly the chips not accumulated earlier (N1–N3). The open-fold leak itself is small, about 1.7 heads-up button decisions per table.
- **N6: patches drifted tighter.** Fold-to-3-bet rose from 78.2% to 81.2% between T1 and T6 (§5). Our bot should expect the field to stay at least as exploitable as on day one.

## 7. Exploits that worked

The house zoo never played in the scored tournaments. Every builder beat it by a wide margin in localsim (about 55–65 points per table; the house nit about 36–51), and zoo-tuned changes misled b07. Zoo evidence is therefore only a sanity check.

| Exploit (leak) | Who gained most | Evidence | Gave back? |
| :- | :- | :- | :- |
| Re-steal shove over a single open at 8–32 bb (N1, N2, hypothesis 5) | b04: +8.9 bb/100 from 3-bets, the opener folds 70%. b06: +7.0, 82% | b06 A/B +2.9 / +3.3 / +0.8 points (self / mixed / tight). Re-raise rate vs steals tracks final rank (ρ ≈ 0.83) | b06: nothing measurable; its leaks are within noise (`REPORT.md`). b04: most early exits (32%). b08's fixed top-12% value re-steal (no fold-equity pricing) did not help |
| First-in shove-or-fold to 20 bb (N1, hypothesis 5) | b04: 8.5 shoves per 100 hands, +1.12 bb each, 71% take the pot | A/B +1.7 (13→16 bb) and +2.6 (16→20 bb) | Over-extended to 25 bb it scored 31.6 in T2 against 34.0 at 20 bb (within noise) and was reverted |
| Steals into folding blinds (hypothesis 5) | b06 +6.1 bb/100 (63% take the pot), b03 +5.9 (55%) | Each blind folds 76%; about 58% of the time both fold | b03 lost it all back to re-steals (N2) |
| C-bets (hypothesis 5) | b08: 84% c-bets, +6.2 bb/100, 65% take the pot. b03 +5.9 | The field folds 69% to c-bets | — |
| River value bets (hypothesis 6) | b03 +6.5 bb/100, b07 +6.1 from river bets; b08 and b02 earn 12–15 bb per river bet at 15–17% frequency (T6) | b04 and b01 paid them off | — |
| Treating raises and big bets as strong (N4, hypothesis 7) | b02 (+0.12 penalty), b05 (narrowing by bet size) | +2.3 points (b02, mixed); b05's "biggest single gain" | No sign of it |

### The exploit plan for our bot

**Build into the static strategy:**
1. **First-in shove-or-fold at 15 bb or less from any seat, and 15–20 bb from the cutoff or later.** At 20 bb and above, open 2.2–2.5 bb. Score each shove as P(all fold)·pot + Σ P(call)·(equity·final pot − risk), with a prior of 15–20% for each player behind calling a shove at 10–40 bb, and about 22% under 10 bb (`REPORT.md`, "Calls a shove, by own stack").
2. **Re-steal shove over a single open with no callers at 8–30 bb** whenever that EV is positive. Assume the opener folds to a 3-bet with prior 0.75, weight 4. Widen the opener's range by position (b01's `OPEN_POS_F`), and treat any hand as a candidate. This is the biggest single lever.
3. **Defend the blinds by re-shoving rather than flatting** at 30 bb or less. Flat only cheap calls in the big blind with hands in the top 35–45%.
4. **Calls of all-ins:** pot odds plus a moderate ICM margin, 0.02 + 0.012·(players alive − 2) when risking more than half the stack (b06's rule), and nothing like b07's 80%.
   - **Stack-off guard:** with five or more players alive, a call of 35% or more of the stack needs a strong hand.
5. **Postflop: bet or fold.**
   - **C-bets:** heads-up flops about 70% of the time at about half pot.
   - **Value bets:** strength ≥ 0.62 heads-up, 0.70 multiway.
   - **Facing a raise:** fold one-pair hands; a raise from these bots is value (N4).
   - **Facing big turn or river bets (0.7 pot or more):** need two pair or better (hypothesis 7).
6. **Heads-up:** shove-or-fold at 15 bb or less with wide ranges, roughly 60% of hands from the small blind at 10 bb. Never open-fold a top-40% hand to a 20 bb-or-less re-shove; call it (N5).
7. **Points table:** an ICM grid from the official calculator for the announced points, but use it on calls only. Shove decisions are dominated by fold equity.

**Detect within a table** (counters reset at every table; priors in brackets with their weight):
- **Fold to any preflop raise** [0.6, w 6]. Widen steals to the top 90% when P(all behind fold) ≥ 0.72.
- **Fold to a 3-bet** [0.75, w 4]. Turns re-steals off against an opener who calls them.
- **Calls a shove** [0.15, w 4]. Count a response only if the shove was at least 30% of the responder's starting stack; b04 found that counting tiny shoves biased its estimates (`bots/b04/NOTES.T6.md:108-109`).
- **Fold to a postflop bet** [0.45, w 6]. Under 0.35 means a station: no bluffs, bigger value bets.
- **PFR** [0.16, w 8]. Sets the opener's range; PFR over 0.45 flags a maniac, so call wider.

**Leave out (too risky against a field without the leak):**
- **Shove-or-fold above 20 bb** (b04, T2).
- **Squeeze shoves over an open plus callers.** b06 measured −1.9 points in its TAG field (`bots/b06/NOTES.T6.md:34`).
- **Light deep 3-bets more than about 25% of the time.** LIGHT3 .5 measured −2.8 in the TAG field (`NOTES.T6.md:48`).
- **Thin river value bets against stations.** b04 measured −1.75 (`bots/b04/NOTES.T6.md:134`).
- **Wider flat blind defense against steals.** b05's v10 scored 29.8 in the real field (`bots/b05/NOTES.T6.md:41-44`).
- **Postflop bluff-raises.** The field folds to raises, but nobody tested this. It is a patch-window candidate only if T1 sample hands show the real field also respects raises.

## 8. A 60-minute build plan for a two-person team

**Architecture: one package, three small modules.**
- **`agent.py`.**
  - **Safety:** `act()` is wrapped in try/except with a check-or-fold fallback. Legal-amount helpers: `raise_to(x)` clamps to [min_to, max_to] and shoves if less than 30% of the pot would be left behind; plus `allin()`, `call()` and `fold()` (b06's `agent.py:248-276`).
  - **Opponent counters:** kept in `observe(hand_end)`.
  - **Preflop and postflop decisions:** as in §7.
- **`tables.py`.** Loads the precomputed tables at import, with everything indexed by hand class:
  - `cls(hole)`;
  - `pct[cls]`, each class's percentile by equity against a random hand;
  - `eq_vs_top[cls][p]` for p = 1..100%;
  - `icm[n][k]` for n = 2..8 players and k = 0..200 (chip share k/200).
- **`tools/precompute.py`.** It must be **variant-generic**: deck, hole-card count, card-use rule and ranking all come from the event card, because the variant is a surprise. Writing it this way also covers a missing evaluator in the official kit (§4).

**Time boxes.** Person A handles the pipeline and testing; person B handles the poker logic.

| Min | A | B | Submit |
| -: | :- | :- | :- |
| 0–3 | Both read the rules, variant, points and blinds. Write down hand ranks, deck size and the action format | ← | |
| 3–10 | Template → safe bot: legal actions, try/except, shove the top 15% at 15 bb or less first-in, otherwise fold or check. Run the validator | Write `precompute.py` (an evaluator for the variant, Monte Carlo class-vs-class equity); start it in the background with a log | **v1 by ~10** (insurance) |
| 10–22 | Write the ICM grid from the official ICM calculator and the announced points. Build a fuzz and timing harness. Script a 4-vs-4 localsim A/B | Preflop: opens by players behind (2.2–2.5 bb); shove-or-fold EV with call-range priors; calls of shoves with the ICM margin | **v2 by ~22** |
| 22–35 | Opponent counters in `observe()` with priors; wire them into P(fold) | Re-steal shove EV (8–30 bb); re-shove blind defense; heads-up shove/call ranges | **v3 by ~35** (has every money mechanism) |
| 35–48 | A/B v3 vs v2: 500+ tables in two field types (self-play 4v4, mixed house field). Check timing | Postflop bet-or-fold: made-hand strength relative to the board, outs, c-bet 70% at half pot, fold to raises, stack-off guard | **v4 by ~45**, only if the A/B is ≥ 0 in both fields |
| 48–58 | Final validator, fuzz and timing on the exact files; write notes for the patch windows | Probe printouts (§ below); one knob at most (push depth 15 vs 20 bb) | **Last by ~55**, leaving cooldown slack |

**Precompute (minutes 3–15, in the background):**
- **Class equity:** class-vs-class all-in equity, 169×169 for 2-card hold'em, with 400–1,500 Monte Carlo deals per pair as the top teams used. Reduce it to `eq_vs_top[cls][p]`, sorting the range by `pct`.
- **Multiway equity:** equity against 2–3 random hands, for multiway pots.
- **ICM grid:** the points-table ICM grid with other stacks equal (b02 and b04 used 200 steps), plus exact Malmuth–Harville at runtime when four or fewer players are left.
- **Push and call charts (optional):** charts by (players behind, effective bb), used as a fallback and a sanity check.
- **For other variants:** if the variant has more hole cards, replace the 169 classes with sampled buckets keyed by (high-card rank, pair, suitedness, connectivity), and keep the same interfaces.

**Test before every submission (about 3 minutes):**
1. **Validator:** the submit validator or `check_bot` passes.
2. **Fuzz:** 0 exceptions with the try/except disabled. Cover all-in for less, side pots, two-handed play, stacks under 1 bb, and a raise when only an all-in is legal. b01 and b02 both ran "exceptions re-raised" builds.
3. **Timing:** p99 under 300 µs and max under 600 µs locally. The real 1 ms may be measured more strictly than this runner's slow-core rule.
4. **Probes:** print the shove range at 10 bb on the button, 8-handed; the re-steal range at 20 bb against a button open; the call range against a 10 bb shove; and the heads-up small-blind shove range at 12 bb. Compare each against intuition (b01's `tools/probe.py` habit).
5. **A/B:** 500+ tables against the previous version in **two** field types. Only accept a change that is ≥ 0 in both and clearly positive in one. Noise is ±2–3 points at 500 tables (`bots/b06/NOTES.T6.md:60`, `bots/b01/NOTES.T6.md:157-158`).

**Patch windows (20 minutes each):**
- **Read the right numbers.** Look at the place histogram (1st and 7th/8th rates), not the mean. Identical code moved 2.7 points between tournaments.
- **Compare against your own baseline.** Before blaming a patch, compare against the same code's earlier results (b08's lesson).
- **Use pre-built knobs.** Make each change a single constant: push depth (13/15/20 bb), fold-to-3-bet prior (0.65/0.75/0.85), open scale, ICM margin.
- **Change little late.** Change only what tournament data contradicts. Keep the last version that scored well as the fallback.

**Expected result.** This plan reproduces b06's and b04's T1 mechanisms: the re-steal shove, first-in shove-or-fold, fold-rate counters, and a moderate ICM margin on calls, with b02's raise-respecting postflop. Those two bots scored 33.95 and 33.99 in T1 and finished 1st and 2nd. Nothing here was tested as a single bot; the estimate rests on those two bots' records.
