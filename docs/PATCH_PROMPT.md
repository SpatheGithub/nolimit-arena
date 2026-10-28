<!--
Patch-round prompt template. The referee renders it after tournament T{{K}} and resumes each
builder's session with: claude -p "<rendered text>" --resume <session_id>  (cwd = workspace).

Placeholders: {{K}} {{K_NEXT}} {{PATCH_MINUTES}} {{DEADLINE_HUMAN}} {{RANK}} {{N_TEAMS}}
  {{AVG}} {{CI95}} {{PLACE_DISTRIBUTION}} {{TIMEOUTS}} {{ERRORS}} {{ILLEGAL}} {{DECISIONS}}
  {{CUM_SCORE}} {{CUM_RANK}} {{REMAINING_PLAN}} {{FEEDBACK_FILES}}
-->

# Patch window before T{{K_NEXT}}

Tournament T{{K}} is finished. Your bot will be frozen for T{{K_NEXT}} (weight {{K_NEXT}}) at {{DEADLINE_HUMAN}}, {{PATCH_MINUTES}} minutes from now. `python kit/clock.py` counts down to it.

## Your T{{K}} result

- **Rank:** {{RANK}} of {{N_TEAMS}}.
- **Average points per table:** {{AVG}} (95% interval {{CI95}}).
- **Finishing places:** {{PLACE_DISTRIBUTION}}.
- **Substitutions:** {{TIMEOUTS}} timeouts, {{ERRORS}} errors and {{ILLEGAL}} illegal actions, out of {{DECISIONS}} decisions.
- **Weighted score so far:** {{CUM_SCORE}}, rank {{CUM_RANK}}.
- **Still to come:** {{REMAINING_PLAN}}.

Details are in `results/T{{K}}/`: {{FEEDBACK_FILES}}.

## What to do

Your current bot keeps playing unless you submit a new one.

1. Use the results to find your bot's biggest weakness and fix that first.
2. Run `kit/check_bot.py`.
3. Submit with `kit/submit.py` before the deadline.

Later tournaments weigh more, so a broken bot now costs more than it did before. Keeping your current bot is a legitimate choice when you aren't sure a change helps.

Before you finish:

1. Update NOTES.md.
2. End with at most five lines: what you changed and your active submission id.
