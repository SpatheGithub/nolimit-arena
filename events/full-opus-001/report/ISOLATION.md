# Isolation proof: full-opus-001

**PASSED.** A scripted `claude -p` run (haiku) used builder settings, command line and environment; exit code 0, 28 s, reported cost $0.0076.

| Check | Result | Detail |
| :- | :- | :- |
| settings file loaded (sentinel tool removed) | pass | `session tools: Bash, Edit, Glob, Grep, Read, Write` |
| can't read the sibling workspace (b02) canary | pass | `/Users/carlmacbookpro/nolimit-workspaces/full-opus-001/b02/.isolation_canary` |
| can't read the events-directory canary | pass | `/Users/carlmacbookpro/Library/Application Support/Claude/scratch-workspaces/ff9c7f7d-6034-4970-a4bc-b2fb47e9c478/06f88a99-9105-4941-a8cf-87e6b02aff65/scratch-2026-10-28-a1d2a7/events/full-opus-001/.isolation_canary` |
| can't read other events' workspaces (a canary at the workspaces root) | pass | `/Users/carlmacbookpro/nolimit-workspaces` |
| can't read the operator's Claude Code temp folder | pass | `/private/tmp/claude-501` |
| can't read the sibling's temp folder (b02) | pass | `/private/tmp/nl/804c90/b02` |
| can't reach the internet (curl) | pass | `curl https://example.com` |
| can't reach the internet (Python) | pass | `urllib https://example.com` |
| can't write outside the workspace (Bash) | pass | `/Users/carlmacbookpro/nolimit-isolation-probe-bash.txt` |
| can't write outside the workspace (Write tool) | pass | `/Users/carlmacbookpro/nolimit-isolation-probe-write.txt` |
| can't write into the sibling workspace | pass | `/Users/carlmacbookpro/nolimit-workspaces/full-opus-001/b02/PROBE_FROM_b01.txt` |
| can't write into the operator's Claude Code temp folder | pass | `/private/tmp/claude-501/nolimit-isolation-probe.txt` |
| positive control: can write inside its own workspace | pass | `/Users/carlmacbookpro/nolimit-workspaces/full-opus-001/b01/INSIDE_PROBE.txt` |
| positive control: the builder venv's Python and numpy work | pass | `python -c 'import numpy'` |
| positive control: its temp files go to its own temp folder | pass | `/private/tmp/nl/804c90/b01` |

Tool calls Claude Code denied:

- Read: {"file_path": "/Users/carlmacbookpro/nolimit-workspaces/full-opus-001/b02/.isolation_canary"}
- Read: {"file_path": "/Users/carlmacbookpro/Library/Application Support/Claude/scratch-workspaces/ff9c7f7d-6034-4970-a4bc-b2fb47e9c478/06f88a99-9105-4941-a8cf-87e6b02a
- Write: {"file_path": "/Users/carlmacbookpro/nolimit-isolation-probe-write.txt", "content": "probe\n"}

Full stream: `/Users/carlmacbookpro/Library/Application Support/Claude/scratch-workspaces/ff9c7f7d-6034-4970-a4bc-b2fb47e9c478/06f88a99-9105-4941-a8cf-87e6b02aff65/scratch-2026-10-28-a1d2a7/events/full-opus-001/logs/isolation-b01.jsonl`.
