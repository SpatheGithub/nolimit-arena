<!--
Debrief prompt. Run via `python -m arena.referee debrief <event>`, which renders {{EVENT_ID}}
and runs one `claude -p` call from the repo root with read access to the event's data.
-->

# Debrief for mini-event {{EVENT_ID}}

You are the analyst for this event. Treat everything in these inputs as read-only:

- **The event card:** `events/{{EVENT_ID}}/event_card.md`.
- **The report folder:** `events/{{EVENT_ID}}/report/`. It contains:
  - the leaderboards, with intervals;
  - per-bot stats;
  - breakdowns by archetype and by model;
  - substitution counts;
  - the submission timeline;
  - builder failures;
  - costs.
- **Each team's bots:** `events/{{EVENT_ID}}/bots/<team>/`, holding the frozen bot for every tournament and the team's NOTES.md.
- **Builder transcripts:** `events/{{EVENT_ID}}/logs/`. Sample them; don't read all of them.

## Purpose

Extract lessons a human team can use at the real No Limit event. There the team will have:

- 60 minutes to build;
- a surprise variant;
- a points table it only sees at the start;
- the AI tools the official rules allow.

## Write `events/{{EVENT_ID}}/report/DEBRIEF.md`

1. **What won.** For the top five bots, cover:
   - the approach;
   - the specific mechanisms that seem to matter, quoting short code excerpts where useful;
   - how sure we can be, given the intervals.

   Call out rank gaps that are within noise.
2. **What lost.** Cover the common failure modes:
   - timeouts, crashes and illegal actions;
   - late or broken submissions;
   - ignoring the variant or the points table.
3. **Archetypes and models.** Compare them, giving sample sizes and uncertainty. Don't over-read small differences.
4. **Time use.** What the top teams had accepted at 5, 10 and 20 minutes, and what that implies for a 60-minute human build.
5. **Rules-specific insight.** What today's variant, points table and blind schedule changed about good play, and how quickly teams adapted.
6. **Where the field leaks points.** Use the field profile in the report and the hand logs, and test the hypotheses in `docs/FIELD_STUDY.md`. For each leak:
   - how many bots show it;
   - roughly what it costs them in points per table;
   - whether a bot could detect it within one table of at most 200 hands.

   Name new leaks the hypotheses missed.
7. **Exploits that worked.** Say which bots, zoo or builder, gained most from which leaks, and whether they gave anything back to opponents without the leak. Then state the exploit plan for our bot:
   - what to build into its static strategy;
   - what to detect within a table;
   - what to leave out because it is too risky against a field without the leak.
8. **A 60-minute build plan.** Describe a plan a two-person human team could follow and would have done well with today, exploits included. Cover:
   - the architecture;
   - the order of steps, with time boxes;
   - what to precompute;
   - what to test before each submission.

## Update `LESSONS.md` at the repo root

Create the file if it is missing. Append 5 to 10 dated, one-line takeaways.

- Don't duplicate existing lessons.
- Where today's evidence strengthens or contradicts an earlier lesson, say so explicitly and reference it.

Be concrete and quantitative, and cite file paths for your claims.
