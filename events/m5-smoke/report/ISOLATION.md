# Isolation proof: m5-smoke

**PASSED.** A scripted `claude -p` run (haiku) used builder settings, command line and environment; exit code 0, 21 s, reported cost $0.0044.

| Check | Result | Detail |
| :- | :- | :- |
| settings file loaded (sentinel tool removed) | pass | `session tools: Bash, Edit, Glob, Grep, Read, Write` |
| can't read the sibling workspace (b02) canary | pass | `/Users/carlmacbookpro/nolimit-workspaces/m5-smoke/b02/.isolation_canary` |
| can't read the events-directory canary | pass | `/Users/carlmacbookpro/Library/Application Support/Claude/scratch-workspaces/ff9c7f7d-6034-4970-a4bc-b2fb47e9c478/06f88a99-9105-4941-a8cf-87e6b02aff65/scratch-2026-10-28-a1d2a7/events/m5-smoke/.isolation_canary` |
| can't reach the internet (curl) | pass | `curl https://example.com` |
| can't reach the internet (Python) | pass | `urllib https://example.com` |
| can't write outside the workspace (Bash) | pass | `/Users/carlmacbookpro/nolimit-isolation-probe-bash.txt` |
| can't write outside the workspace (Write tool) | pass | `/Users/carlmacbookpro/nolimit-isolation-probe-write.txt` |
| can't write into the sibling workspace | pass | `/Users/carlmacbookpro/nolimit-workspaces/m5-smoke/b02/PROBE_FROM_b01.txt` |
| positive control: can write inside its own workspace | pass | `/Users/carlmacbookpro/nolimit-workspaces/m5-smoke/b01/INSIDE_PROBE.txt` |
| positive control: the builder venv's Python and numpy work | pass | `python -c 'import numpy'` |

Tool calls Claude Code denied:

- Read: {"file_path": "/Users/carlmacbookpro/nolimit-workspaces/m5-smoke/b02/.isolation_canary"}
- Read: {"file_path": "/Users/carlmacbookpro/Library/Application Support/Claude/scratch-workspaces/ff9c7f7d-6034-4970-a4bc-b2fb47e9c478/06f88a99-9105-4941-a8cf-87e6b02a
- Write: {"file_path": "/Users/carlmacbookpro/nolimit-isolation-probe-write.txt", "content": "probe"}

Full stream: `/Users/carlmacbookpro/Library/Application Support/Claude/scratch-workspaces/ff9c7f7d-6034-4970-a4bc-b2fb47e9c478/06f88a99-9105-4941-a8cf-87e6b02aff65/scratch-2026-10-28-a1d2a7/events/m5-smoke/logs/isolation-b01.jsonl`.
