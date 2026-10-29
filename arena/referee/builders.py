"""Launching builders: per-team Claude Code settings, the command line, the
environment, and reading their stream-json logs.

Every flag and settings key here was checked against Claude Code 2.1.300
(docs/CLAUDE_CODE_NOTES.md). The isolation proof runs at milestone 5;
pipeline tests use mock builders (arena/referee/mock_builder.py) and never
start Claude.
"""

from __future__ import annotations

import json
import os
import shutil
import sys

from .config import Team

SENTINEL_TOOL = "NotebookEdit"  # named in --tools and denied in settings: proves the settings file loaded
DENIED_TOOLS = ["WebFetch", "WebSearch", "Agent", "Workflow", "SendMessage", "ListAgents", "Skill",
                "RemoteTrigger", "Artifact", "CronCreate", "Monitor", "PushNotification", SENTINEL_TOOL, "mcp__*"]
TOOLS = "Bash,Read,Edit,Write,Glob,Grep," + SENTINEL_TOOL
CREDENTIAL_VARS = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"]
FAILURE_CATEGORIES = {"authentication_failed", "oauth_org_not_allowed", "account_on_hold", "billing_error",
                      "rate_limit", "overloaded", "model_not_found"}


def team_settings(team: Team, all_teams: list[Team], events_dir: str, repo: str) -> dict:
    """Claude Code settings for one builder: OS sandbox for Bash, permission
    rules for the file and web tools, and the operator's customizations off."""
    others = [t.workspace for t in all_teams if t.team != team.team]
    ws_root = os.path.dirname(team.workspace)
    venv = os.path.join(repo, ".venv")
    deny = list(DENIED_TOOLS)
    deny += [f"Read(/{p}/**)" for p in [events_dir, repo, *others]]
    return {
        "permissions": {"deny": deny, "blockReadsOutsideWorkingDirectories": True},
        "sandbox": {
            "enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": True,
            "filesystem": {
                "denyRead": [ws_root, events_dir, repo, os.path.expanduser("~/.claude/projects"),
                             os.path.expanduser("~/.claude.json"), os.path.expanduser("~/.ssh"),
                             os.path.expanduser("~/.aws")],
                "allowRead": [team.workspace, venv],
            },
            "network": {"allowedDomains": [], "strictAllowlist": True},
            "credentials": {"envVars": [{"name": v, "mode": "deny"} for v in CREDENTIAL_VARS]},
        },
        "disableAllHooks": True, "autoMemoryEnabled": False, "syncClaudeAiSkills": False,
        "syncClaudeAiPlugins": False, "disableClaudeAiConnectors": True, "disableWorkflows": True,
        "crossSessionInbound": "refuse",
    }


def builder_env(repo: str, extra: dict | None = None) -> dict:
    """A clean environment: nothing inherited from a parent Claude session,
    the arena venv first on PATH, and CLAUDE.md, memory and connectors off."""
    keep = {k: v for k, v in os.environ.items()
            if k in ("HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "TMPDIR", "TERM")}
    path = os.pathsep.join([os.path.join(repo, ".venv", "bin"), "/usr/bin", "/bin", "/usr/sbin", "/sbin",
                            os.path.dirname(shutil.which("claude") or "/usr/local/bin/claude")])
    env = {**keep, "PATH": path, "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
           "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
           "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "DISABLE_AUTOUPDATER": "1"}
    env.update(extra or {})
    return env


def claude_command(prompt: str, *, model: str, brief_file: str, settings_file: str, session_id: str,
                   auth_mode: str, resume: bool = False, budget_usd: float | None = None) -> list[str]:
    cmd = ["claude", "-p", prompt, "--model", model, "--settings", settings_file,
           "--tools", TOOLS, "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
           "--disable-slash-commands", "--permission-mode", "acceptEdits", "--permission-prompts", "none",
           "--output-format", "stream-json", "--verbose"]
    cmd += ["--bare"] if auth_mode == "api_key" else ["--restricted"]
    if resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id, "--append-system-prompt-file", brief_file]
    if budget_usd:
        cmd += ["--max-budget-usd", f"{budget_usd:g}"]
    return cmd


def mock_command(ws: str, phase: str, deadline: float, seed: int, behavior: str) -> list[str]:
    return [sys.executable, "-m", "arena.referee.mock_builder", "--workspace", ws, "--phase", phase,
            "--deadline", f"{deadline:.3f}", "--seed", str(seed), "--behavior", behavior]


def read_stream(path: str) -> dict:
    """Summary of a builder's stream-json log: session, cost, errors."""
    out = {"session_id": None, "cost_usd": 0.0, "errors": [], "result": None, "tools": None, "events": 0}
    try:
        with open(path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                out["events"] += 1
                t = ev.get("type")
                if t == "system" and ev.get("subtype") == "init":
                    out["session_id"] = ev.get("session_id") or out["session_id"]
                    out["tools"] = ev.get("tools")
                elif t == "system" and ev.get("subtype") == "api_retry":
                    cat = (ev.get("error") or {}).get("category") or ev.get("category")
                    if cat in FAILURE_CATEGORIES:
                        out["errors"].append(cat)
                elif t == "result":
                    out["result"] = ev.get("subtype")
                    out["session_id"] = ev.get("session_id") or out["session_id"]
                    out["cost_usd"] = float(ev.get("total_cost_usd") or 0.0)
                    if ev.get("is_error"):
                        out["errors"].append(ev.get("subtype") or "error")
    except OSError:
        pass
    return out


def write_settings(path: str, settings: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(settings, f, indent=1)
