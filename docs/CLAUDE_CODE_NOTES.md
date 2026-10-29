# Claude Code notes for the arena

Every Claude Code CLI flag, settings key and stream event the referee uses to launch unattended builder sessions, checked against the installed CLI and the live docs on **2026-10-28**.

How this was verified: `claude --help` and `claude <subcommand> --help` output of the installed binary, plus the documentation pages listed under Sources. No model session was started. The only commands run were `claude --version`, `claude --help`, `claude auth|doctor|mcp|plugin|setup-token --help` and `claude auth status`. Doc content is paraphrased; short message strings are quoted exactly.

## Installed version and machine facts

- **Installed version:** `claude --version` prints `2.1.300 (Claude Code)`.
  - The binary is `~/.local/bin/claude`, a symlink to `~/.local/share/claude/versions/2.1.300`.
  - This is the native installer, which auto-updates unless `DISABLE_AUTOUPDATER=1` is set.
- **Auth:** `claude auth status --json` reports `loggedIn: true`, `authMethod: claude.ai`, `apiProvider: firstParty`, `subscriptionType: enterprise` (an education org) and `configDirectory: ~/.claude`.
  - Exit code 0 means logged in and 1 means not [CLI].
- **Unset variables:** `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` and `CLAUDE_CONFIG_DIR`.
  - So `auth.mode: api_key`, and with it `--bare`, can't be used today.
  - `configs/event.example.yaml` defaults to `api_key`. Set it to `subscription`, or ask the user for a Console API key.
- **Sandbox:** the macOS Seatbelt tool is present (`/usr/bin/sandbox-exec`). macOS needs no bubblewrap or socat [SBX].
- **Managed settings:** there is no `/Library/Application Support/ClaudeCode/managed-settings.json`. Server-managed settings from the claude.ai org could still apply; this is unknown, and `/status` in an interactive session would show them.
- **Operator customizations a builder could inherit** (checked by name only):
  - present: `~/.claude/skills/` (one personal skill plus the claude.ai `synced/` folder) and `~/.claude/plugins/synced/`;
  - absent: `~/.claude/CLAUDE.md`, any `CLAUDE.md` or `AGENTS.md` in `~`, and hooks or MCP servers in the user config;
  - `~/.claude/settings.json` holds one cosmetic key.
- **Inherited environment:** the shell used for these checks is itself a Claude Code agent session.
  - It exports `CLAUDECODE`, many `CLAUDE_CODE_*` variables (including `CLAUDE_CODE_MESSAGING_SOCKET`, `CLAUDE_CODE_MESSAGING_TOKEN` and `CLAUDE_CODE_SIMPLE`) and `ANTHROPIC_BASE_URL`.
  - A referee started from such a shell passes all of them to builders unless it builds a clean environment (see "Subscription-mode isolation").

## Sources (fetched 2026-10-28)

| Tag | URL |
| :- | :- |
| CLI | https://code.claude.com/docs/en/cli-reference |
| HL | https://code.claude.com/docs/en/headless |
| SBX | https://code.claude.com/docs/en/sandboxing |
| PERM | https://code.claude.com/docs/en/permissions |
| PM | https://code.claude.com/docs/en/permission-modes |
| SET | https://code.claude.com/docs/en/settings (files and precedence; the per-key list moved to SREF) |
| SREF | https://code.claude.com/docs/en/settings-reference |
| ENV | https://code.claude.com/docs/en/env-vars |
| AUTH | https://code.claude.com/docs/en/authentication |
| DBG | https://code.claude.com/docs/en/debug-your-config |
| MEM | https://code.claude.com/docs/en/memory |
| TOOLS | https://code.claude.com/docs/en/tools-reference |
| XSM | https://code.claude.com/docs/en/cross-session-messaging |
| ERR | https://code.claude.com/docs/en/errors |
| SDK-TS | https://code.claude.com/docs/en/agent-sdk/typescript |
| SDK-COST | https://code.claude.com/docs/en/agent-sdk/cost-tracking |
| SDK-FEAT | https://code.claude.com/docs/en/agent-sdk/claude-code-features |
| W24 | https://code.claude.com/docs/en/whats-new/2026-w24 (safe mode, v2.1.169) |
| W35 | https://code.claude.com/docs/en/whats-new/2026-w35 (restricted mode, v2.1.248) |
| KB-SDK | https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan |
| KB-TE | https://support.claude.com/en/articles/11845131-use-claude-code-with-your-team-or-enterprise-plan |

## Verification table

In the "Verified via" column, **help** means the flag is in `claude --help` for 2.1.300 and **docs** means it is documented on the cited page. [CLI] says `--help` doesn't list every flag, so a flag missing from help can still exist. Every documented minimum version needed here is at or below 2.1.300. One documented behavior arrives later: Manual mode as the default for `-p` starts at v2.1.302, which is why the referee always passes `--permission-mode`.

### Baseline invocation flags

| Flag or key | Verified via | Min version (documented) | Notes |
| :- | :- | :- | :- |
| `-p`, `--print` | help + docs [CLI][HL] | none | Runs non-interactively and shows no workspace-trust dialog. Exits 0 on success and non-zero on failure. A failure inside the run, such as missing auth, is printed as the result on stdout. Help says settings files that fail validation are **silently ignored** in this mode, which [SET] confirms (see the sentinel check below). |
| `--model <alias>` | help + docs [CLI] | none | Takes an alias (`sonnet`, `opus`, `haiku`, `fable`) or a full model name. Overrides the `model` setting and `ANTHROPIC_MODEL`. A managed `availableModels` list can narrow the choice [SET]. |
| `--append-system-prompt-file <path>` | **docs only** [CLI]; not in `--help` | none stated; using it together with `--append-system-prompt` needs v2.1.283 | Appends the file to the default system prompt, in both `-p` and interactive mode. Pass an absolute path. The prompt is recorded on the first request and reused on `--resume` until the conversation is compacted; after compaction, the current launch's flags apply. So pass it again on every resume. Under `--bare`, recording is off unless `--system-prompt-snapshot on` is set [CLI, "System prompt flags in resumed conversations"]. |
| `--settings <file-or-json>` | help + docs [CLI][SET] | none | **Pass an absolute path.** Builders run with the workspace as cwd, so a relative `events/<id>/...` would resolve inside the workspace. The file must be a regular file of 2 MiB or less. It sits below managed settings and above local, project and user settings, and can set any key the user settings file can. It applies to that launch only, so pass it on every resume. A permission rule starting with a single `/` anchors at this file's own directory, so always use `//abs` [PERM]. In `-p`, invalid JSON or a value the schema rejects makes Claude Code skip the file or the bad entries without saying so [SET, "Fix a broken settings file"]. |
| `--permission-mode acceptEdits` | help + docs [CLI][PM] | `manual` alias v2.1.200 | Help lists the choices `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`; the docs also accept `default`. `acceptEdits` auto-approves file edits and `mkdir touch rm rmdir mv cp sed` on paths inside the working directories. Protected paths (`.claude`, `.git`, `.mcp.json`, shell rc files and others) and all other Bash commands still prompt, unless the sandbox auto-allows them. **Always pass a mode.** On 2.1.300 a `-p` run without one can start in auto mode; `-p` starts in Manual only from v2.1.302 [PM]. |
| `--permission-prompts none` | help + docs [CLI][HL] | v2.1.259 | Help choices are `host` (the default) and `none`. With `none`, anything that would prompt is denied unless a `PermissionRequest` hook allows it, and Claude is told not to retry. The tools that need a person, such as `AskUserQuestion`, are removed. Denials stream as `system`/`permission_denied` events and are listed in `result.permission_denials` [HL]. |
| `--output-format stream-json` | help + docs [CLI][HL] | none | `-p` only. Prints newline-delimited JSON, and the last line is the `result` message [HL]. |
| `--verbose` | help + docs [CLI][HL] | none | The docs always pair it with `stream-json` in `-p`. Keep it. |
| `--bare` (`api_key` mode only) | help + docs [CLI][HL][AUTH] | limits fully enforced from v2.1.286 | **Skips:** hooks, skills, custom commands, subagents, plugins, MCP servers, auto memory, CLAUDE.md, LSP and keychain reads. **Auth:** only `ANTHROPIC_API_KEY`, or `apiKeyHelper` set in `--settings`; it never reads OAuth, the keychain or `CLAUDE_CODE_OAUTH_TOKEN`, so it can't run on this user's subscription login. **Also off:** system reminders, background tasks, and the cross-session inbox socket [XSM]. **Still read:** settings files, so a project `env` block applies [PERM]. [HL] says `--bare` will become the default for `-p` in a future release. Re-check subscription builders after every upgrade. |
| `--max-budget-usd <amount>` | help + docs [CLI][SDK-COST] | cap enforcement v2.1.217 | `-p` only. The cap is checked against Claude Code's **client-side cost estimate**, and spend can pass it, so leave headroom. Totals restored by `--resume` don't count toward it, so the cap applies **per run, not per builder**. Docs don't limit it to API-key auth. Under a subscription login it should cap the API-equivalent estimate; this is unverified. On hitting the cap, the result has `subtype: error_max_budget_usd` and `terminal_reason: budget_exhausted` [SDK-TS]. |
| `--resume <session-id>` with `-p` | help + docs [CLI][HL] | ID lookup across all projects v2.1.223; restored cost totals v2.1.277 | Only the conversation and its recorded system prompt carry over. `--settings`, the permission mode, `--tools`, the MCP flags, the output flags and the budget are launch options, so **repeat every flag**. Run from the workspace so the working directory and sandbox scope match. On a resumed run, `total_cost_usd` is the session's cumulative total, so record deltas. Never use `--no-session-persistence` or `CLAUDE_CODE_SKIP_PROMPT_HISTORY`: either one makes the session impossible to resume [CLI][ENV]. |
| `--session-id <uuid>` | help + docs [CLI] | none | Lets the referee assign each builder's session ID before launch instead of reading it from the `result` event, which SIGTERM or SIGKILL can prevent. **Recommended.** Don't pass it together with `--resume`. |

### Isolation flags (needed because subscription mode can't use `--bare`)

| Flag or key | Verified via | Min version (documented) | Notes |
| :- | :- | :- | :- |
| `--restricted` | help + docs [CLI][W35] | v2.1.248 | Documented for an evaluation harness running `claude` on a shared machine. **Tools:** removes the built-in tools that run commands or code (Bash and others) and WebFetch, unless each is named in `--tools`; the `default` preset doesn't bring them back. **Files:** confines the built-in file tools to the working directories. **Settings:** loads only managed settings and `--settings`, ignoring the user, project and local files, so user hooks, `enabledPlugins` and allow rules don't apply. **Also:** refuses `bypassPermissions`. Add `--strict-mcp-config` to skip MCP servers too. **The docs don't say** whether CLAUDE.md, auto memory, skills folders or synced plugins still load, so block those separately. |
| `--safe-mode` | help + docs [CLI][DBG][ENV] | v2.1.169 [W24] | **Turns off:** CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands and agents, output styles, workflows, themes and keybindings, the status line, LSP and auto memory. **Managed policy:** hooks still run; managed plugins, skills, CLAUDE.md and MCP don't load. **Unchanged:** auth, model selection, built-in tools and permissions. **Not documented:** whether the sandbox keys in `--settings` still apply, so verify before relying on it. It's a troubleshooting mode, sets `CLAUDE_CODE_SAFE_MODE=1`, and child processes inherit that variable. |
| `--setting-sources <list>` | help + docs [CLI][PERM][SDK-FEAT][SBX] | v2.1.246 (sandbox ignores excluded sources) | **Values:** `user`, `project`, `local`. **`user`:** `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, rules, and user skills, commands and agents. **`project`:** `<cwd>/.claude/settings.json` and its hooks, CLAUDE.md in the cwd and every parent directory, project skills, and `.mcp.json`. **`local`:** `settings.local.json` and `CLAUDE.local.md`. **Not covered:** managed settings, `~/.claude.json`, auto memory, claude.ai connectors, and the user file's `sandbox.credentials` deny entries. `--settings` still applies. An **empty list** (the SDK's `settingSources: []`) is **not documented for the CLI**. |
| `--strict-mcp-config` + `--mcp-config '{"mcpServers":{}}'` | help + docs [CLI][SDK-FEAT] | v2.1.221 (`--mcp-config` wait) | Loads only the servers given in `--mcp-config`. According to [SDK-FEAT], strict MCP config also suppresses the claude.ai connectors; an empty server map on its own does not. |
| `--disable-slash-commands` | help + docs [CLI] | none | Turns off all skills and commands for the session. |
| `--tools "Bash,Read,Edit,Write,Glob,Grep"` | help + docs [CLI][TOOLS] | none | An allowlist of built-in tools. It drops `Agent`, `Workflow`, `WebFetch`, `WebSearch`, `Skill`, `SendMessage`, `ListAgents`, `RemoteTrigger`, `Artifact`, `CronCreate`, `Monitor`, `PushNotification`, `NotebookEdit` and the rest from context. It doesn't affect MCP tools. On macOS the default set leaves out Glob and Grep; naming them in `--tools` adds them. `EndConversation` can't be removed while other tools remain. The `system/init` tools list shows the Agent tool as `Task`. |
| `--disallowedTools` | help + docs [CLI] | none | Adds deny rules for the session. A bare tool name removes the tool. |
| `--exclude-dynamic-system-prompt-sections` | help + docs [CLI] | none | Optional, for `api_key` mode. Moves the cwd, environment and memory-path sections out of the system prompt, so 40 builders share a cacheable prompt prefix. |
| `--fallback-model` | help + docs [CLI] | none | Optional. It switches models silently when the primary is overloaded. That confounds model comparisons, so record it if you use it. |

### Subcommands and environment variables

| Item | Verified via | Min version (documented) | Notes |
| :- | :- | :- | :- |
| `claude auth status [--json\|--text]` | help (ran) + docs [CLI] | v2.1.268 (`configDirectory` field) | Makes no model call. JSON keys seen here: `loggedIn, authMethod, apiProvider, email, orgId, orgName, subscriptionType, configDirectory, projectsDirectory, analyticsDisabled`. `authMethod` is one of `none, claude.ai, oauth_token, api_key, api_key_helper, third_party`, and it exits 0 or 1. **Use it as the referee's preflight, run with the exact builder environment.** |
| `claude doctor` | help + docs [CLI][DBG] | none | Prints settings-file validation errors without starting a session. It reads the settings files in the current directory, not `--settings`, and contacts `api.anthropic.com` to check org policy. |
| `claude setup-token` | help + docs [CLI][AUTH] | none | Opens a browser flow and prints a one-year OAuth token once; nothing is saved. Requires a Pro, Max, Team or Enterprise plan. The token can only make model requests: no claude.ai connectors and no Remote Control. Use it through `CLAUDE_CODE_OAUTH_TOKEN`; `--bare` doesn't read it. The org restriction `forceLoginOrgUUID` isn't checked for setup tokens [AUTH]. |
| `CLAUDE_CODE_OAUTH_TOKEN` | docs [ENV][AUTH] | none | Takes precedence over the keychain login and stays fixed for the session. Sandboxed commands can see it unless `sandbox.credentials` denies it or the scrub removes it. |
| `CLAUDE_CONFIG_DIR` | docs [ENV][AUTH][DBG] | none | Moves settings, history, plugins, `.claude.json` and `.credentials.json` to another directory. **On macOS the Keychain entry is tied to the directory**, so a fresh directory starts **without a login**. It needs a one-time interactive `CLAUDE_CONFIG_DIR=<dir> claude auth login`, by the user, or a `CLAUDE_CODE_OAUTH_TOKEN`. It doesn't stop parent-directory CLAUDE.md files, claude.ai connectors or synced skills under a claude.ai login. `--resume` needs the same value. The subprocess scrub removes it from the env. |
| `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` | docs [ENV] | none | Stops all CLAUDE.md memory files from loading (user, project and auto memory). `AGENTS.md` isn't mentioned; a built-in plugin reads it [MEM]. |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` | docs [ENV][SDK-FEAT] | none | `--setting-sources` doesn't control auto memory, so turn it off here or with `autoMemoryEnabled: false`. |
| `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` | docs [ENV][SBX] | v2.1.251 (broader matching) | Removes variables that look like credentials (including `ANTHROPIC_API_KEY` and `CLAUDE_CONFIG_DIR`) from Bash, hook and MCP subprocesses. It leaves GitHub tokens and proxy settings in place. It matches by name and value shape only. The PID-namespace isolation it adds is **Linux-only**. |
| `ENABLE_CLAUDEAI_MCP_SERVERS=false` | docs [ENV] | none | Stops Claude Code from fetching the claude.ai connectors. |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` | docs [ENV][HL] | none | Removes `run_in_background`. Without it, a `-p` run waits up to 10 minutes for background work after the final turn. `--bare` turns background tasks off on its own. |
| `DISABLE_AUTOUPDATER=1` | docs [ENV] | none | Keeps the version fixed during an event. Record `system/init.claude_code_version` per builder. |

### Keys in `configs/builder_settings.example.json`

| Key | Verified via | Min version (documented) | Notes |
| :- | :- | :- | :- |
| `permissions.deny` with `Read(//abs/path/**)` | docs [PERM] | Write tool covered from v2.1.228; symlinks matched at their real path from v2.1.268 | **Path forms:** `//` is the filesystem root, `~/` is home, a single `/x` is relative to the settings source (for a `--settings` file, that file's directory), and a bare `x` is the cwd. Matching uses gitignore globs. **Coverage:** a Read deny also blocks Edit and Write on the path, but not NotebookEdit. It applies to Read, Grep and Glob (best effort), to Bash file commands Claude Code recognizes (`cat head tail sed tee`) and to redirections. It does **not** cover arbitrary subprocesses such as Python scripts; the sandbox covers those. **Precedence:** deny wins at every level, an allow can't carve an exception out of a deny, and `!` only carves out of unanchored rules. **On macOS:** write `/Users/<you>`, not `/home/you`, and expand `~/nolimit-workspaces` before building `//` rules. |
| `permissions.deny`: `WebFetch`, `WebSearch`, `Agent`, `Workflow` | docs [PERM][TOOLS] | none | All four are canonical tool names; `Task` is the legacy alias for `Agent`. A bare tool name removes the tool from context, and an unknown name triggers a startup warning. **Not enough on its own:** see "Gaps" below for `SendMessage`, `ListAgents`, `RemoteTrigger`, `Artifact`, `Skill` and the rest. |
| `permissions.blockReadsOutsideWorkingDirectories` | docs [SREF][PERM] | v2.1.257 | **Exists.** In every permission mode, Read, Grep, Glob and LSP refuse paths outside the working directories. A `true` from any scope wins. It covers the file tools only, not Bash. **It would replace the per-sibling `Read(...)` rules for the file tools**, because sibling workspaces and `events/` are outside the builder's cwd. It also blocks file-tool reads of `~/.claude/projects` (other sessions' transcripts), the rest of the arena repo (`LESSONS.md`, `arena/house_bots/`) and `~/.ssh`, which the per-path list misses. **Recommendation:** turn it on, and keep explicit `Read(//...)` denies for the events dir and workspaces root as a second layer. Read deny rules, unlike this key, are documented as merged into the sandbox configuration [SBX]. Bash is protected by the sandbox `denyRead` entries plus those merged rules. |
| `sandbox.enabled` | docs [SBX][SREF] | none | Defaults to false. macOS uses Seatbelt; Linux and WSL2 use bubblewrap and socat. Built on `@anthropic-ai/sandbox-runtime`. |
| `sandbox.failIfUnavailable` | docs [SBX][SREF] | none stated | When `true`, Claude Code **exits at startup** if the sandbox can't start, instead of running commands unsandboxed. If the sandbox fails after startup, each sandboxed command is refused with `Sandbox is required…` and never runs unsandboxed. The settings default is `false`; the Agent SDK's default is `true`. |
| `sandbox.allowUnsandboxedCommands: false` | docs [SBX][SREF] | v2.1.285 to hold against a project value | Claude Code ignores `dangerouslyDisableSandbox`, so nothing retries outside the sandbox. |
| `sandbox.autoAllowBashIfSandboxed: true` | docs [SBX][SREF][PERM] | none | Defaults to true and works regardless of permission mode. Some calls still go through the normal permission flow, which `--permission-prompts none` denies: deny rules, `rm` or `rmdir` on critical paths, content-scoped ask rules, and forms such as `FOO=bar cmd`, `make CC=clang` or `eval …`. **Builders should avoid `VAR=x cmd` prefixes.** |
| `sandbox.filesystem.denyRead` / `allowRead` | docs [SBX][SREF] | none | **Precedence:** the narrower path wins, so `denyRead` on the workspaces root plus `allowRead` on the team's own workspace leaves only that workspace readable under the root. **Paths:** `/abs` or `//abs`, `~/`, and `./` or bare. Bare and `./` mean the project root in project settings and `~/.claude` in user settings; their meaning in `--settings` isn't documented, so **use absolute paths**. A trailing slash is stripped. On macOS, denying a symlinked path also denies its real location. **Default reads** cover most of the machine, including `~/.ssh` and `~/.aws/credentials` [SBX], and so also `~/.claude`. |
| `sandbox.filesystem.allowWrite` / `denyWrite` | docs [SBX][SREF] | none | **`allowWrite` isn't needed.** By default, sandboxed commands can write to the cwd, `--add-dir` directories and the per-user temp directory, and `$TMPDIR` is set to that directory. **Always write-protected:** `.claude` settings, skills, agents, commands and hooks; `.mcp.json`; shell rc files; `.gitconfig`; `.git/hooks` and `.git/config`; `~/.claude` (or `CLAUDE_CONFIG_DIR`); and `~/.claude.json`. **The per-user temp directory is shared** by every builder running as the same OS user, which gives builders a channel to each other. Test before deciding whether to add a `denyWrite`. |
| `sandbox.network.allowedDomains: []` | docs [SBX][SREF] | v2.1.186 (bare `*`); v2.1.229 (bracketed IPv6) | The list starts empty. All traffic goes through a local proxy that checks hostnames. It doesn't inspect TLS, so domain fronting is possible. The proxy refuses hostnames that resolve only to link-local addresses, such as `169.254.169.254`. How it treats `localhost` under a strict, empty list isn't clear from the docs, so the canary probes it. |
| `sandbox.network.strictAllowlist: true` | docs [SBX][SREF][SDK-TS] | v2.1.219 | Refuses hosts outside the list instead of prompting. Honored from user settings, managed settings or `--settings`; project and local files are ignored. The docs disagree slightly: the [SREF] index lists the scope as user or managed only, while [SBX] and [SDK-TS] explicitly include `--settings`, and [SET] says `--settings` can set any user key. **Verify it at milestone 5.** |
| `sandbox.credentials.envVars` / `.files` | docs [SBX][SREF] | v2.1.221 for `mask` on files | **Exists.** With `deny`, the variable is unset for each sandboxed command and reads of the file path are blocked. With `mask`, sandboxed commands see a placeholder; masked files are simply blocked on macOS. There is no built-in list. **Add `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_AUTH_TOKEN`** next to `ANTHROPIC_API_KEY`. Env protection holds even if filesystem isolation is turned off. |

### Extra settings keys recommended for builders

| Key | Verified via | Min version (documented) | Notes |
| :- | :- | :- | :- |
| `disableAllHooks: true` | docs [SREF][PERM] | none | From `--settings` it turns off user, project, local and plugin hooks, any custom status line or file-suggestion command, and mods. Managed hooks keep running. |
| `autoMemoryEnabled: false` | docs [SREF][MEM] | none | Turns off auto memory, which `--setting-sources` doesn't reach. Use it together with the environment variable. |
| `syncClaudeAiSkills: false`, `syncClaudeAiPlugins: false` | docs [SREF] | v2.1.273 for the plugins key | Honored from `--settings`. They stop loading the skills and plugins synced from the account. [KB-TE] says org-provided skills and plugins load automatically from v2.1.273. [SREF] says already-synced items move to `.trash` when this is set in **user or managed** settings; check that nothing moves when it's set only through `--settings`. |
| `disableClaudeAiConnectors: true` | docs [SREF] | none | Can be set from any file. |
| `crossSessionInbound: "refuse"` | docs [XSM][SREF] | v2.1.224 (cross-session messaging) | A `-p` session opens an inbox socket by default and appears in other sessions' agent lists. Messages between two sessions that both prompt for permission are **delivered by default**, and `acceptEdits` counts as prompting. Set `refuse`, and remove `SendMessage` and `ListAgents` (with `--tools` or deny rules), to isolate builders from each other and from the operator's own sessions. |
| `disableWorkflows: true` | docs [SREF] | none | Can be set from any file. |
| `permissions.disableBypassPermissionsMode: "disable"` | docs [PERM] | none | An extra lock; `--restricted` already refuses bypass mode. |

## Stream-json events the referee parses

| Event | Fields that matter | Source |
| :- | :- | :- |
| `system` / `init` (first event, unless hook or plugin-install events come first) | `session_id, cwd, model, permissionMode, apiKeySource, tools, mcp_servers, plugins, plugin_errors, skills, slash_commands, claude_code_version, capabilities` (capabilities v2.1.205+). `tools` reports the Agent tool as `Task`. | [HL][SDK-TS] |
| `result` (last line) | `subtype` is `success`, `error_max_turns`, `error_during_execution`, `error_max_budget_usd` or `error_max_structured_output_retries`. Other fields: `is_error, session_id, total_cost_usd, usage, modelUsage, num_turns, duration_ms, duration_api_ms, permission_denials, terminal_reason`. The success shape adds `result` and `api_error_status`; error shapes add `errors[]`. `terminal_reason` values include `completed`, `api_error`, `model_error`, `budget_exhausted` and `max_turns`. | [SDK-TS] |
| `system` / `api_retry` | `attempt, max_retries, retry_delay_ms, error_status` (HTTP code or null), `error` category, and `no_response` (v2.1.261+). | [HL] |
| `assistant` with `error` | Shares the category list with `api_retry`: `authentication_failed, oauth_org_not_allowed, account_on_hold, billing_error, rate_limit, overloaded, invalid_request, model_not_found, server_error, max_output_tokens, cloud_credential_error, unknown`. | [SDK-TS][HL] |
| `rate_limit_event` | `rate_limit_info.status` is `allowed`, `allowed_warning` or `rejected`. Also `resetsAt` and `utilization`. `errorCode: "credits_required"` (v2.1.181+) means a claude.ai subscription's included usage is used up. | [SDK-TS] |
| `system` / `permission_denied` | `tool_name, decision_reason_type, decision_reason, message`. Best effort; `result.permission_denials` is the authoritative list. | [SDK-TS][HL] |

`total_cost_usd` is a **client-side estimate** computed from a price table bundled with the CLI, not a bill. It includes subagents, and on a resumed session it includes earlier spend (v2.1.277+). If the session crashes, the final `error_during_execution` result may report zeroed totals [SDK-COST].

**Signals [HL]:**
- **SIGTERM:** exits with code 143 and records no result for the turn in progress. It kills the process trees of running Bash commands and runs `SessionEnd` hooks.
- **SIGINT:** ends the turn cleanly, so send it before stopping the process. The SETUP_PROMPT order (SIGINT, then SIGTERM after 10 seconds, then SIGKILL after 30) matches the docs.
- **Session totals:** written to the transcript only when the process exits normally.

### Error detection

Prefer the structured fields. The message strings from [ERR] are a fallback and change between versions.

| Condition | Structured signal | Text in `result.result` or stderr [ERR] |
| :- | :- | :- |
| Not logged in, or login expired or revoked | `error: authentication_failed`; `result.is_error: true` with `api_error_status` 401 or 403 | `Not logged in · Please run /login`, `Login expired · Please run /login`, `OAuth token revoked`, `Invalid API key` |
| Org blocks the login | `oauth_org_not_allowed` | `Your organization has disabled Claude subscription access` |
| Account or billing problem | `account_on_hold`, `billing_error` | `Credit balance is too low`, `You've hit your monthly spend limit` |
| Plan usage limit (subscription) | `rate_limit_event` with `status: "rejected"` (plus `resetsAt`, and `credits_required` when usage is used up); `allowed_warning` comes first as an early warning | `You've hit your session limit`, `You've hit your weekly limit`, `You've hit your Opus limit` |
| Throttled (429) | `error: rate_limit`, `error_status: 429` | `Request rejected (429)`, `Server is temporarily limiting requests` |
| Overloaded (529) | `error: overloaded`; per [ERR], doesn't count against the quota | `API Error: Repeated 529 Overloaded errors…` |
| Server error | `server_error`, 5xx | `API Error: 500 Internal server error…` |
| Budget cap reached | `subtype: error_max_budget_usd`, `terminal_reason: budget_exhausted` | none |
| Sandbox can't start (`failIfUnavailable`) | Exits at startup; the SDK reports `error_during_execution` with the reason in `errors` | `Sandbox is required but failed to initialize: …` |

## Subscription-mode isolation

The user has a claude.ai Enterprise login and no API key, so `--bare` isn't available. Each item `--bare` would normally keep out of a builder has to be blocked with documented levers instead.

| What could leak into a builder | Levers that stop it (documented) |
| :- | :- |
| Operator's `~/.claude/CLAUDE.md`, plus `CLAUDE.md` or `AGENTS.md` in any parent of the workspace | `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`, `--safe-mode`, or excluding the `user` and `project` setting sources. A referee preflight should also confirm that no ancestor of `workspaces_root` holds one. |
| Auto memory (`~/.claude/projects/<project>/memory/`) | `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` and `autoMemoryEnabled: false`. Setting sources don't cover it. |
| Personal skills (`~/.claude/skills/`) and synced claude.ai skills | `--disable-slash-commands`, leaving `Skill` out of `--tools`, `syncClaudeAiSkills: false`, `--safe-mode` |
| Plugins (installed, synced, or provided by the org), including plugin hooks, MCP servers and mods | `--restricted` (doesn't read `enabledPlugins` from the user file), `syncClaudeAiPlugins: false`, `disableAllHooks: true` (also stops mods), `--safe-mode` (also stops managed plugins) |
| Hooks in user, project or local settings | `--restricted` or setting sources, plus `disableAllHooks: true` from `--settings`. Managed hooks always run. |
| MCP servers (`~/.claude.json`, `.mcp.json`) and claude.ai connectors | `--strict-mcp-config --mcp-config '{"mcpServers":{}}'`, `ENABLE_CLAUDEAI_MCP_SERVERS=false`, `disableClaudeAiConnectors: true` |
| Subagents, workflows, web tools, cross-session messaging, cloud triggers, artifact publishing | The `--tools` allowlist, mirrored as deny rules, plus `crossSessionInbound: "refuse"` and `disableWorkflows: true` |
| Other sessions' transcripts (`~/.claude/projects/*`), the arena repo (`LESSONS.md`, house bots) and `~/.claude.json` | File tools: `--restricted` or `blockReadsOutsideWorkingDirectories`. Bash: sandbox `denyRead` (see Gaps). |
| Parent-session environment (`CLAUDECODE`, `CLAUDE_CODE_*`, messaging token, `ANTHROPIC_BASE_URL`) | Launch each builder with a minimal, explicit environment. Never pass the referee's `os.environ` through. |
| Credentials in the environment (`CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`) | `sandbox.credentials.envVars` deny entries. **Not** `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`: on 2.1.300 it forces permission mode `default`, so every Bash call is refused (see "Milestone 5 results"). Reading another process's environment (`ps eww`) and the macOS Keychain from inside the sandbox are **not covered by the docs; test them.** |

### Recommended builder invocation: `auth.mode: subscription`

Launch the builder with the workspace as cwd, in its own process group (`start_new_session=True`), and signal the whole group at the deadline. The referee builds the environment dictionary itself, without inheriting anything. The shell syntax below is only for readability.

```bash
env -i \
  HOME="$HOME" USER="$USER" LOGNAME="$USER" LANG=en_US.UTF-8 \
  SHELL=/bin/zsh TMPDIR="$TMPDIR" \
  PATH="/Users/<you>/nolimit-workspaces/.venv/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/<you>/.local/bin" \
  CLAUDE_ENV_FILE=/Users/<you>/nolimit-workspaces/.venv/arena-env.sh \
  CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 \
  CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \
  CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 \
  ENABLE_CLAUDEAI_MCP_SERVERS=false \
  DISABLE_AUTOUPDATER=1 \
  /Users/<you>/.local/bin/claude -p "The build phase has started. Read EVENT.md, then build and submit your bot." \
    --model <alias> \
    --append-system-prompt-file /Users/<you>/<repo>/events/<id>/briefs/<team>.md \
    --settings /Users/<you>/<repo>/events/<id>/settings/<team>.json \
    --restricted \
    --tools "Bash,Read,Edit,Write,Glob,Grep,NotebookEdit" \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --disable-slash-commands \
    --permission-mode acceptEdits \
    --permission-prompts none \
    --output-format stream-json --verbose \
    --session-id <uuid4> \
    [--max-budget-usd <remaining budget for this run>]
```

- **Why `--restricted` is the main lever.** It is the only documented mode built for an evaluation harness. Its docs put no limit on authentication, while `--bare` refuses OAuth and the keychain, so the keychain login should still work; the auth preflight and the smoke test confirm this. It loads no user, project or local settings files, so the builder can't loosen the sandbox through a `.claude/settings.local.json` it writes, and the operator's settings never apply. It also confines the file tools to the workspace. The environment variables and the flags after it cover what its docs don't mention.
- **Fallbacks if `--restricted` misbehaves:**
  - Replace it with `--setting-sources` excluding `user`, keeping `project` only if needed. Workspace `.claude/` files are write-protected, but `project` still reads parent-directory CLAUDE.md files.
  - Or add `--safe-mode`, once the canary shows the sandbox and `--settings` still apply under it.
  - Pass an empty `--setting-sources ""` only after checking the CLI accepts it.
- **Settings-loaded sentinel.** Add one harmless extra tool to `--tools`, for example `NotebookEdit`, and deny it by bare name in the settings file. If `system/init.tools` still lists it, the settings file was skipped. Kill the builder at once, because a skipped file also means no sandbox.
- **`SHELL`.** The Bash tool sources the user's `~/.zshrc`, `~/.bashrc` or `~/.profile` at session start and applies its aliases, functions and options to every command [TOOLS]. Check `type python` inside a builder. Setting `SHELL=/bin/bash` avoids the operator's zsh customizations if there's no `~/.bashrc`; verify this.
- **Optional token variant:**
  - Have the user run `claude setup-token` once and store the token in the macOS Keychain, never in the repo or `events/`.
  - The referee passes it as `CLAUDE_CODE_OAUTH_TOKEN`, optionally with a per-event `CLAUDE_CONFIG_DIR` (for example `<repo>/events/<id>/claude-home`).
  - Gains: builder state stays out of the operator's `~/.claude` (transcripts, `.claude.json`, synced skills); 40 processes don't share one refreshing OAuth login; claude.ai connectors aren't fetched.
  - Costs: the token sits in every builder process's environment. Deny it in `sandbox.credentials.envVars` and test the `ps eww` leak (the env scrub can't be used; see "Milestone 5 results"). `--resume` must use the same `CLAUDE_CONFIG_DIR`. With a token instead of a Team or Enterprise `/login`, a mod can override deny rules [PERM]. That doesn't matter here only because hooks and plugins, and with them mods, are off.

### Recommended builder invocation: `auth.mode: api_key`

Use the same environment, minus the variables `--bare` already covers, plus the key. Alternatively, set `apiKeyHelper` in the `--settings` file so the key never sits in the environment; `--bare` reads `apiKeyHelper` only from `--settings`.

```bash
env -i HOME=… USER=… LOGNAME=… LANG=… SHELL=… TMPDIR=… PATH="<repo>/.venv/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  ANTHROPIC_API_KEY=<key> DISABLE_AUTOUPDATER=1 CLAUDE_ENV_FILE=… \
  claude --bare -p "<prompt>" \
    --model <alias> \
    --append-system-prompt-file <abs>/.brief/BRIEF.md \
    --settings <abs>/events/<id>/settings/<team>.json \
    --tools "Bash,Read,Edit,Write,Glob,Grep" \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --disable-slash-commands \
    --permission-mode acceptEdits --permission-prompts none \
    --output-format stream-json --verbose \
    --session-id <uuid4> \
    [--max-budget-usd <x>] [--exclude-dynamic-system-prompt-sections]
```

`--bare` still reads settings files [PERM], so keep `blockReadsOutsideWorkingDirectories` in the builder settings. The env scrub is left out here too: it broke the permission mode in subscription mode, and `--bare` with it is untested; `sandbox.credentials.envVars` already unsets the key for Bash. Adding `--restricted` to `--bare` would also skip the user, project and local files; that combination isn't documented, so test it before using it.

### Patch-round resume (both modes)

Use the same cwd, environment and flags, with the rendered patch prompt. Replace `--session-id <uuid>` with `--resume <uuid>`. Pass `--append-system-prompt-file` again: under `--bare` the prompt is rebuilt from the flags on every request, and in subscription mode it is rebuilt after compaction. Set `--max-budget-usd` to the remaining budget, because restored totals don't count toward it. Read the cumulative `total_cost_usd` and store the difference from the previous run.

### Gaps in `configs/builder_settings.example.json` (proposed, not applied)

1. **Paths.** Use macOS paths (`/Users/<you>/…`) with `~` expanded. Keep every sandbox path absolute.
2. **Turn on `permissions.blockReadsOutsideWorkingDirectories: true`.** It is simpler than listing 39 siblings and also covers `~/.claude/projects`, the repo and the home directory.
3. **Sandbox `denyRead` should cover the whole arena repo, not only `events/`.** Otherwise Bash can read `LESSONS.md`, past events' material and `arena/house_bots/`. Builders therefore can't use `<repo>/.venv`; they get their own venv outside the repo, in `allowRead` (applied at milestone 5, see "Milestone 5 results"). Also deny `~/.claude/projects` (every session's transcripts, including sibling builders') and `~/.claude.json`. Don't deny all of `~/.claude`: the Bash tool may need its shell-snapshot files there. Verify Bash still works after the change.
4. **Deny more tools.** Add `SendMessage`, `ListAgents`, `Skill`, `RemoteTrigger` (cloud scheduled tasks), `Artifact` (publishing to claude.ai), `CronCreate`, `Monitor`, `PushNotification`, `NotebookEdit`, `EnterWorktree` and `mcp__*` to `permissions.deny`, as a second layer behind the `--tools` allowlist.
5. **Add the top-level keys:** `disableAllHooks: true`, `autoMemoryEnabled: false`, `disableWorkflows: true`, `disableClaudeAiConnectors: true`, `syncClaudeAiSkills: false`, `syncClaudeAiPlugins: false`, `crossSessionInbound: "refuse"`.
6. **Credential variables.** Add `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_AUTH_TOKEN` to `sandbox.credentials.envVars` with `mode: deny`.
7. **The brief's location.** `--append-system-prompt-file` points inside the workspace, so the builder can edit its own brief, and the edit takes effect after compaction or on resume. Keep it, or move the brief under `events/<id>/` (the builder doesn't need to read it with tools).

### Plan policy: `claude -p` on a Claude plan

From [KB-SDK], which showed "Updated yesterday" on 2026-10-28:
- **Plan login:** with a Claude plan login, Agent SDK and `claude -p` usage counts against the subscription's usage limits, the same pool as interactive use.
- **2026-06-15:** a previously announced change to Agent SDK usage was paused. The SDK, `claude -p` and third-party apps still draw on subscription limits.
- **2026-10-07:** Max and Team plans gained a monthly allowance of API credits. It covers the Claude API, Managed Agents, and the SDK or `claude -p` **when run with an API key** from the linked Console org. Plan-login usage is unchanged.
- **Gaps:** nothing in that article is specific to Enterprise or Education seats, parallel sessions, automation, or `setup-token`.

From [KB-TE]:
- **Seats:** Claude Code is included in Team seats and in the single Enterprise seat. On older Enterprise plans it comes with "Chat + Claude Code" seats (usage-based) or Premium seats.
- **Usage-based Enterprise:** has no per-seat limits and bills at API rates. On Team and seat-based Enterprise, admins can turn on usage credits beyond the included limits.
- **API credits:** Team plans' monthly API credits **can't be used** in Claude Code.
- **Org content:** org-provided skills and plugins load automatically in v2.1.273 and later.

**Implication:** in subscription mode all builders draw on the operator's one Enterprise seat. Whether 40 parallel builders hit session and weekly limits or are billed per use depends on the org's contract, so ask the org admin.

## To verify empirically

### Milestone 3: no model session, no spend

1. **Flag presence.** Parse `claude --help` and fail fast with a clear message if any of these is missing: `--permission-prompts`, `--restricted`, `--safe-mode`, `--setting-sources`, `--strict-mcp-config`, `--mcp-config`, `--tools`, `--disable-slash-commands`, `--session-id`, `--resume`, `--max-budget-usd`, `--bare`, `--output-format`, `--verbose`. `--append-system-prompt-file` isn't in help; check it at milestone 5. Record `claude --version` in `state.json`.
2. **Auth preflight.** Run `claude auth status --json` with the **exact builder environment**. Expect exit 0 and `authMethod` of `claude.ai`, or `oauth_token` or `api_key` for the other variants. Pause the event if it fails. This also confirms the `env -i` environment can still reach the Keychain login.
3. **Settings generator tests (pytest).**
   - The file is valid JSON and under 2 MiB.
   - Every path is absolute and exists, and no `~` or `/home/you` remains.
   - `Read(//…)` rules cover every sibling workspace and the events dir.
   - `allowRead` is exactly the team's own workspace, plus the builder venv and its interpreter copy.
   - The key set matches the reviewed list in this note.
4. **Offline schema check (optional).** Copy a generated file to `<scratch>/.claude/settings.json` and run `claude doctor` from `<scratch>`. First confirm that `doctor` reports a deliberately broken copy; it makes no model call but does contact `api.anthropic.com`.
5. **Ancestor scan.** No ancestor of `workspaces_root` contains `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`, `.claude/` or `.mcp.json`. `workspaces_root` is outside the repo and isn't a git repository.
6. **Canary script** (`tests/isolation/canary.*`). It prints only probe names and PASS/FAIL, never file contents or secret values. Run it **without** a sandbox as the control, where every probe should report "accessible", so the probes are known to work. If the user approves installing `@anthropic-ai/sandbox-runtime`, an `srt` run gives an early but non-authoritative sandbox result. The probes:
   - `cat` the canaries in a sibling workspace, in `events/`, in `~/.claude/projects/` and in the repo (`LESSONS.md`);
   - write to a sibling workspace, `~`, the repo, `/tmp` and `$TMPDIR`;
   - `curl -m 5 https://example.com`, a raw socket to `1.1.1.1:53`, and `curl localhost:<referee test port>`;
   - count (don't print) `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN` in `env`;
   - count the same names in `ps eww -A`;
   - check the exit status of `security find-generic-password -s "Claude Code-credentials" >/dev/null` (never with `-w`);
   - connect to another session's inbox socket;
   - write `<workspace>/.claude/settings.local.json`;
   - check that `python -c "import numpy"` runs from the venv.
7. **Kit tools in a temp workspace.** Test `localsim`, `check_bot`, `submit` and `clock` under the same constraints: no network, writes only in the workspace and `$TMPDIR`, no repo reads apart from `.venv`.

### Milestone 5: smoke test, minimal spend

Use a cheap model alias for the isolation-proof run, and cap it with `--max-turns` and `--max-budget-usd`.

1. **Check `system/init` for each builder.** Abort on any mismatch.
   - `cwd` is the workspace, `permissionMode` is `acceptEdits`, and `claude_code_version` is `2.1.300`.
   - `tools` is exactly the allowlist plus `EndConversation`, with no `Task`/`Agent`, `Workflow`, `WebFetch`, `WebSearch`, `SendMessage`, `ListAgents` or `Skill`.
   - `mcp_servers` and `plugins` are empty.
   - `skills` and `slash_commands` contain none of the operator's skills (the personal one or the synced ones).
   - Record `apiKeySource`.
2. **Settings sentinel.** The denied sentinel tool is absent from `init.tools`.
3. **Isolation proof.**
   - The scripted builder runs the canary script in one Bash call, then uses the Read tool on the sibling and events canaries.
   - Expect: every read and write outside the workspace fails, and the Read attempts appear in `permission_denials`.
   - Expect: all network probes fail and no credential names are visible.
   - Record whether `$TMPDIR` writes and `ps eww` or Keychain access succeed.
   - Confirm `strictAllowlist` was honored from `--settings` (no prompt; the connection is refused).
4. **Brief.** `--append-system-prompt-file` is accepted, with no unknown-option error, and the brief is followed.
5. **Resume.** `--resume <id>` with the same flags continues the session. `total_cost_usd` is cumulative. The sentinel and sandbox still hold.
6. **Deadline signals.** After SIGINT, record whether a `result` event arrives within 10 seconds and the exit code. After SIGTERM, expect exit code 143 and no result. Check whether totals reach the transcript.
7. **Subscription accounting.** Check that `total_cost_usd` is filled in. Record how often `rate_limit_event` arrives and its `utilization`. Optionally run a throwaway prompt with a tiny cap to see whether `--max-budget-usd` stops a subscription-auth run.
8. **Builder ergonomics.** Check that `type python` resolves to the venv and that aliases sourced from the operator's shell rc file don't interfere. Check whether `VAR=x cmd` prefixes are denied, so the brief can warn builders. The default Bash timeout is 2 minutes; `localsim` is capped at 60 seconds.
9. **Synced items.** `~/.claude/skills/synced` and `~/.claude/plugins/synced` are unchanged after the runs, and nothing moved to `.trash`.
10. **Combined flags.** If `--safe-mode` is added to `--restricted`, the canary still passes and the sentinel still holds.
11. **40-way concurrency (later, a user-run event).** Watch for OAuth refresh failures when 40 processes share one Keychain login. The setup-token variant shouldn't have this problem.

## Milestone 5 results (2026-10-29, 2.1.300, claude.ai login)

### Isolation proof

`python -m arena.referee isolation <event>` runs a scripted `claude -p` session (Haiku) with one builder's exact settings, command line and environment, then judges from files and the stream, not from the model's account. Final run: **10 of 10 checks pass**, 12 turns, about 15 s, reported cost $0.004. Each negative probe was stopped by the layer meant to stop it:

| Probe | Stopped by | What the session saw |
| :- | :- | :- |
| `cat` the sibling workspace's or the events dir's canary | Sandbox `denyRead` | `Operation not permitted` |
| Read tool on the same files | `Read(//…)` deny rules | `File is in a directory that is denied by your permission settings.` |
| `curl https://example.com` (output inside the workspace) | Sandbox network proxy | `CONNECT tunnel failed, response 403`, then `<sandbox_violations> deny network-outbound example.com:443 (host is not on the allow list)` appended to the tool result |
| Python `urllib` to the same host | Sandbox network proxy | `Tunnel connection failed: 403 Forbidden`, same violation line |
| Bash write to `~` or into the sibling workspace | Sandbox write policy | `Operation not permitted` |
| Write tool outside the workspace | `--restricted` | `… is outside <ws>; --restricted confines the file tools to the working directory.` |

- **`strictAllowlist` from `--settings` is honored:** no prompt, the connection is refused.
- **`system/init`:** `cwd` is the workspace, `permissionMode` is `acceptEdits`, `claude_code_version` is `2.1.300`, `apiKeySource` is `none` (keychain login), and `tools` is exactly `Bash, Edit, Glob, Grep, Read, Write`, so the sentinel is gone. `mcp_servers`, `skills` and `slash_commands` are empty. `plugins` lists four built-ins only (`cc-plugin-sec-default`, `cc-plugin-agents-md`, `cc-plugin-telemetry`, `cc-plugin-plugin-authoring`, all `path: builtin`), none of the operator's synced plugins. `agents` lists the built-in subagent types, which can't run without the Agent tool.
- Claude Code creates an empty `<workspace>/.claude/.cc-writes/` during a sandboxed session.

### What had to change (each found by a failed run)

1. **`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` forces permission mode `default`.** `system/init` reported `default` despite `--permission-mode acceptEdits`, and every Bash call was refused with "requires approval, and this session has no approval surface". Removing variables one at a time pinned it on this one. The referee no longer sets it; `sandbox.credentials.envVars` still unsets the credential variables for Bash. Until this was fixed, the negative probes "passed" only because nothing ran at all; positive controls are what caught it.
2. **Sandbox auto-allow refuses some compound commands** (`a && b`). The settings now carry `permissions.allow: ["Bash"]`. The OS sandbox, not the permission layer, is what confines Bash.
3. **`blockReadsOutsideWorkingDirectories` also gates Bash arguments.** A command that names a path outside the working directories (`curl -o /dev/null …`) goes to the permission flow and is denied under `--permission-prompts none`: "curl names '/dev/null', outside the working directories, which the read block does not allow without asking". Builders should keep paths inside the workspace.
4. **The Bash tool rebuilds `PATH` from the login shell.** Neither the process's `PATH` nor `env.PATH` in settings reached Bash; the operator's `~/.bash_profile` (conda init, `~/.local/bin`) won. `CLAUDE_ENV_FILE` works, and Claude Code doesn't modify the file. The referee points it at `<builder venv>/arena-env.sh` (venv first on `PATH`, `PYTHONDONTWRITEBYTECODE=1`). That location is readable but not writable for builders, so a builder can't add commands to a file sourced before every Bash call.
5. **The builder venv can't live in the repo or point into `~/.local/share`.** The sandbox denies the repo by design. It also denies `~/.local/share/uv/python/` (`Operation not permitted`) although no setting of ours names it, and uv's interpreters live there behind a `cpython-3.12-…` symlink. `allowRead` on the versioned interpreter directory didn't help, because the symlink sits in the denied parent. The referee now copies the standalone interpreter to `~/nolimit-workspaces/.python`, 85 MB with the stdlib byte-compiled once (builders can't write bytecode there). It then builds `~/nolimit-workspaces/.venv` from that copy, with numpy copied in. Both are in `allowRead`; builders can read them but not write them.

### Subscription accounting

- **`rate_limit_event`** carries `rateLimitType: five_hour`, `utilization` and `resetsAt`. It read 0.56 at the isolation run, a figure that includes the operator's own concurrent session. It also carries `overageStatus: rejected` with `overageDisabledReason: org_level_disabled`: on this account, reaching the five-hour limit stops builders instead of billing overage.
- **`total_cost_usd` is filled in for subscription runs.** It is a notional API-price cost, not a bill.
- **One `rate_limit_event` per run**, right after `system/init`. Also seen: `system/thinking_tokens`, `system/permission_denied` and `tool_progress` events, which the referee ignores.

### Smoke events (2 Sonnet builders, 4-minute build, 1 tournament)

| | Run 1 (`m5-smoke`) | Run 2 (`m5-smoke-2`) |
| :- | :- | :- |
| Referee | as built at milestone 4 | resumes builders that end their turn early (clock checks) |
| Builder runs | 1 each | 18 and 16 (17 and 15 clock checks) |
| Time spent working | about 20 s each, then idle for 3 min 40 s | 123 s and 139 s of the 240 s |
| Accepted submissions | 1 each, at 19 s | b01: 1 at 21 s; b02: 2, at 15 s and 141 s |
| Reported cost | $0.09 + $0.08 | $0.24 + $0.18, of which about $0.14 was 28 one-line "still my final bot" replies |
| At the deadline | both had already exited (code 0) | both had already exited (code 0) |

- **Builders stop as soon as they feel done.** `claude -p` ends when the model ends its turn, and in run 1 both did after 4 turns (read EVENT.md, write a heuristic bot, check, submit). The brief now says the whole window is the job. The referee resumes a builder that ends its turn with at least 45 s left, saying the time left and its latest submission. After a reply with no tool calls it waits 60 s, doubling with each such reply in a row; run 2 predates that backoff.
- **Working time costs about $0.065 per builder-minute** at this context size (run 2: $0.28 over 4.4 working minutes; mostly cache reads and writes of a 20k to 50k-token context).
- **`--resume` keeps the session id** across all 34 resumed runs. `total_cost_usd` is the session's cumulative total, and `--append-system-prompt-file` is accepted on resumed runs.
- **A compound command containing `sed -i` needs approval**, even with `permissions.allow: ["Bash"]`: "This Bash command contains multiple operations. The following part requires approval: sed -i …". Both builders lost a turn to it and switched to the Edit tool. The brief now says to edit files with the Edit tool and not to chain `sed -i`.
- **Deadline SIGINT, tested on its own** (Haiku, `sleep 30` running in the sandbox): the process exits with code 0 within 1.3 s and kills the sandboxed command. The last event is a `result` with `subtype: error_during_execution`, `is_error: true`, `terminal_reason: "aborted_tools"` and the cost filled in. The session then resumes normally. The referee counts `aborted_*` endings as interruptions, not failures; before that fix, every builder stopped at the build deadline would have looked failed and paused the event at the first patch window.
- **Isolation held in the real builder logs:** neither event's logs contain another workspace's or the events directory's canary token.

### Estimate: a 40-builder, 6-tournament event at the defaults

- **Builder time:** a 20-minute build plus five 7-minute patch windows is 55 minutes per builder, so **2,200 builder-minutes**.
- **Wall clock:** about 65 minutes. That is 55 minutes of windows plus six freezes and tournaments of about a minute each (40 bots × 400 iterations took 63 s at milestone 2).
- **Cost, using Claude Code's API-price estimates:**
  - About **$80** if builders behave as in run 2: working 55% of each window at $0.065 a minute, with backed-off clock checks costing little.
  - About **$290** if they stay busy all the time and longer contexts double the per-minute rate.
  - **Central guess: $150**, about $3.75 per builder. With an API key this is the bill.
- **On this claude.ai login:** the five-hour meter went from 63% to 65% during run 2, which includes the operator's own session. So the builders' $0.42 used at most 2 points, about 5 points per dollar at worst. At that rate $150 is up to about seven five-hour windows; it would be fewer if the operator's session caused most of those 2 points.
- **Either way, a full default event very likely can't finish inside one five-hour window, and overage is disabled.** Options: a scaled event (for example 8 builders, a 20-minute build and 2 tournaments, about a tenth of the builder-minutes), an API key, or asking the org admin about limits.
- **To calibrate:** run the next real event with no other Claude sessions on the login and read the meter line in its REPORT.md.

## Open questions

- **The org's terms.** Does the education Enterprise contract bill by usage or by seat? Does it allow automated, parallel `claude -p` use on one seat? Does the org push server-managed settings (forced plugins, hooks or permission rules) that would override builder settings?
- **Auth choice.** Would the user rather create a Console API key (enables `--bare`, billed separately) or a `setup-token` (keeps subscription billing and decouples builders from the Keychain login)?
- **Shared temp directory.** Is a temp directory shared by all builders acceptable? Is the sandbox's writable temp directory derived from the `TMPDIR` of the `claude` process? If so, giving each builder its own temp directory would close that channel.
- **Brief location.** Should the brief stay inside the workspace, where the builder can edit it, or move under `events/`?
