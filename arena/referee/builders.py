"""Launching builders: per-team Claude Code settings, the command line, the
environment, and reading their stream-json logs.

Every flag and settings key here was checked against Claude Code 2.1.300
(docs/CLAUDE_CODE_NOTES.md). The isolation proof runs at milestone 5;
pipeline tests use mock builders (arena/referee/mock_builder.py) and never
start Claude.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys

from .config import Team

SENTINEL_TOOL = "NotebookEdit"  # named in --tools and denied in settings: proves the settings file loaded
DENIED_TOOLS = ["WebFetch", "WebSearch", "Agent", "Workflow", "SendMessage", "ListAgents", "Skill",
                "RemoteTrigger", "Artifact", "CronCreate", "Monitor", "PushNotification", SENTINEL_TOOL, "mcp__*"]
TOOLS = "Bash,Read,Edit,Write,Glob,Grep," + SENTINEL_TOOL
CREDENTIAL_VARS = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"]
ENV_FILE = "arena-env.sh"
# Fatal for a builder. rate_limit and overloaded are retried by Claude Code and only count if the run fails.
FATAL_CATEGORIES = {"authentication_failed", "oauth_org_not_allowed", "account_on_hold", "billing_error",
                    "model_not_found"}


def _venv_home(path: str) -> str | None:
    try:
        with open(os.path.join(path, "pyvenv.cfg")) as f:
            for line in f:
                key, _, value = line.partition("=")
                if key.strip() == "home":
                    return value.strip()
    except OSError:
        pass
    return None


def ensure_builder_venv(path: str, repo: str) -> str:
    """The Python builders run: a venv outside the repo (the sandbox denies the
    repo, so builders can't read past events or our notes) with numpy copied
    from the arena's venv. Its base interpreter is a copy of the arena's in
    `.python` next to it, because the sandbox denies ~/.local/share, where uv
    keeps interpreters (and the symlinks into them). Offline; reused across events."""
    path = os.path.expanduser(path)
    base = os.path.join(os.path.dirname(path), ".python")
    if _venv_home(path) != os.path.join(base, "bin") or not os.path.exists(os.path.join(path, "bin", "python")):
        if os.path.exists(path):
            shutil.rmtree(path)  # an older layout whose interpreter the sandbox can't read
        if not os.path.exists(os.path.join(base, "bin", "python3")):
            shutil.copytree(os.path.realpath(python_base_prefix(os.path.join(repo, ".venv"))), base, symlinks=True)
            # Sandboxed builders can't write bytecode here, so compile the stdlib once.
            subprocess.run([os.path.join(base, "bin", "python3"), "-m", "compileall", "-q", "-j0",
                            glob.glob(os.path.join(base, "lib", "python3.*"))[0]], check=False)
        subprocess.run([os.path.join(base, "bin", "python3"), "-m", "venv", "--without-pip", path], check=True)
        src = glob.glob(os.path.join(repo, ".venv", "lib", "python3.*", "site-packages"))[0]
        dst = glob.glob(os.path.join(path, "lib", "python3.*", "site-packages"))[0]
        for name in os.listdir(src):
            if name == "numpy" or name.startswith("numpy-") or name == "numpy.libs":
                shutil.copytree(os.path.join(src, name), os.path.join(dst, name))
    write_env_file(path)
    return path


def python_base_prefix(builder_venv: str) -> str:
    """The interpreter's install directory (stdlib), which the venv symlinks into.
    The sandbox denies ~/.local/share by default, where uv puts it."""
    out = subprocess.run([os.path.join(builder_venv, "bin", "python"), "-c", "import sys; print(sys.base_prefix)"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def env_file(builder_venv: str) -> str:
    return os.path.join(builder_venv, ENV_FILE)


def write_env_file(builder_venv: str) -> str:
    """Sourced before each of the builder's Bash commands (CLAUDE_ENV_FILE):
    Claude Code rebuilds PATH from the login shell, which would hide the venv.
    It lives in the venv, which builders can read but not write, so a builder
    can't put commands in it."""
    path = env_file(builder_venv)
    with open(path, "w") as f:
        f.write(f'export PATH="{os.path.join(builder_venv, "bin")}:$PATH"\nexport PYTHONDONTWRITEBYTECODE=1\n')
    return path


def team_settings(team: Team, all_teams: list[Team], events_dir: str, repo: str, builder_venv: str,
                  extra_read: tuple[str, ...] = ()) -> dict:
    """Claude Code settings for one builder: OS sandbox for Bash, permission
    rules for the file and web tools, and the operator's customizations off.
    Bash is allowed at the permission layer because the sandbox is what
    confines it; leaving it to auto-approval refuses some compound commands."""
    others = [t.workspace for t in all_teams if t.team != team.team]
    ws_root = os.path.dirname(team.workspace)
    deny = list(DENIED_TOOLS)
    deny += [f"Read(/{p}/**)" for p in [events_dir, repo, *others]]
    return {
        "permissions": {"allow": ["Bash"], "deny": deny, "blockReadsOutsideWorkingDirectories": True},
        "sandbox": {
            "enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": True,
            "filesystem": {
                "denyRead": [ws_root, events_dir, repo, os.path.expanduser("~/.claude/projects"),
                             os.path.expanduser("~/.claude.json"), os.path.expanduser("~/.ssh"),
                             os.path.expanduser("~/.aws")],
                "allowRead": [team.workspace, builder_venv, *extra_read],
            },
            "network": {"allowedDomains": [], "strictAllowlist": True},
            "credentials": {"envVars": [{"name": v, "mode": "deny"} for v in CREDENTIAL_VARS]},
        },
        "disableAllHooks": True, "autoMemoryEnabled": False, "syncClaudeAiSkills": False,
        "syncClaudeAiPlugins": False, "disableClaudeAiConnectors": True, "disableWorkflows": True,
        "crossSessionInbound": "refuse",
    }


def builder_env(repo: str, extra: dict | None = None, builder_venv: str | None = None,
                env_file: str | None = None) -> dict:
    """A clean environment: nothing inherited from a parent Claude session,
    the builder venv first on PATH (and in CLAUDE_ENV_FILE for the Bash tool),
    and CLAUDE.md, memory and connectors off."""
    keep = {k: v for k, v in os.environ.items()
            if k in ("HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "TMPDIR", "TERM")}
    venv_bin = os.path.join(builder_venv, "bin") if builder_venv else os.path.join(repo, ".venv", "bin")
    path = os.pathsep.join([venv_bin, "/usr/bin", "/bin", "/usr/sbin", "/sbin",
                            os.path.dirname(shutil.which("claude") or "/usr/local/bin/claude")])
    # No CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: on 2.1.300 it silently forces the permission mode back to
    # "default", so Bash needs approvals nobody can give. Nothing secret is in this environment anyway,
    # and the sandbox settings deny credential variables to Bash.
    env = {**keep, "PATH": path, "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
           "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
           "DISABLE_AUTOUPDATER": "1"}
    if env_file:
        env["CLAUDE_ENV_FILE"] = env_file
    env.update(extra or {})
    return env


def claude_command(prompt: str, *, model: str, brief_file: str, settings_file: str, session_id: str,
                   auth_mode: str, resume: bool = False, budget_usd: float | None = None,
                   effort: str | None = None) -> list[str]:
    cmd = ["claude", "-p", prompt, "--model", model, "--settings", settings_file,
           "--tools", TOOLS, "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
           "--disable-slash-commands", "--permission-mode", "acceptEdits", "--permission-prompts", "none",
           "--output-format", "stream-json", "--verbose"]
    cmd += ["--bare"] if auth_mode == "api_key" else ["--restricted"]
    # The brief goes on every run: a resumed system prompt is rebuilt after compaction.
    cmd += ["--resume" if resume else "--session-id", session_id, "--append-system-prompt-file", brief_file]
    if budget_usd:
        cmd += ["--max-budget-usd", f"{budget_usd:g}"]
    if effort:
        # A launch option like the rest: settings files can't hold "max", and Opus 5.5 defaults to medium.
        cmd += ["--effort", effort]
    return cmd


def mock_command(ws: str, phase: str, deadline: float, seed: int, behavior: str) -> list[str]:
    return [sys.executable, "-m", "arena.referee.mock_builder", "--workspace", ws, "--phase", phase,
            "--deadline", f"{deadline:.3f}", "--seed", str(seed), "--behavior", behavior]


def _category(ev: dict) -> str | None:
    """The error category of an api_retry or assistant event (documented as a string)."""
    err = ev.get("error")
    return (err.get("category") or err.get("type")) if isinstance(err, dict) else (err or ev.get("category"))


def read_stream(path: str, errors_from: int = 0) -> dict:
    """Summary of a builder's stream-json log (every run appended): latest session,
    cumulative cost, errors, how many runs ended with a result event, how many
    of the last finished runs in a row made no tool call (``idle_streak``), and
    the plan's five-hour usage meter.

    Errors are what should stop a builder: a fatal API category, a rejected
    plan limit, or a run that ended in error. Retried throttling (429, 529) is
    only counted, and the deadline SIGINT is an interruption, not an error.
    ``errors`` and ``events_since`` count only lines from byte ``errors_from``
    on, so a resumed event isn't re-paused by the errors that paused it."""
    out = {"session_id": None, "cost_usd": 0.0, "errors": [], "result": None, "results": 0, "tools": None,
           "events": 0, "events_since": 0, "run_calls": 0, "idle_streak": 0, "interrupted": 0, "retries": 0,
           "usage_first": None, "usage": None, "resets_at": None, "model": None}
    try:
        with open(path, "rb") as f:
            pos = 0
            for raw in f:
                counting = pos >= errors_from
                pos += len(raw)
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                out["events"] += 1
                out["events_since"] += counting
                error = None
                t = ev.get("type")
                if t == "system" and ev.get("subtype") == "init":
                    out["session_id"] = ev.get("session_id") or out["session_id"]
                    out["tools"] = ev.get("tools")
                    out["model"] = ev.get("model") or out["model"]
                    out["run_calls"] = 0
                elif t == "assistant":
                    content = (ev.get("message") or {}).get("content") or []
                    out["run_calls"] += sum(1 for c in content if isinstance(c, dict) and c.get("type") == "tool_use")
                    if _category(ev) in FATAL_CATEGORIES:
                        error = _category(ev)
                elif t == "system" and ev.get("subtype") == "api_retry":
                    if _category(ev) in FATAL_CATEGORIES:
                        error = _category(ev)
                    else:
                        out["retries"] += 1
                elif t == "rate_limit_event":
                    info = ev.get("rate_limit_info") or {}
                    five = (info.get("unifiedWindows") or {}).get("five_hour") or {}
                    out["resets_at"] = five.get("resetsAt") or info.get("resetsAt") or out["resets_at"]
                    if info.get("status") == "rejected":
                        error = "usage_limit"
                    used = five.get("utilization")
                    if used is not None:
                        out["usage_first"] = used if out["usage_first"] is None else out["usage_first"]
                        out["usage"] = used
                elif t == "result":
                    out["results"] += 1
                    out["idle_streak"] = out["idle_streak"] + 1 if out["run_calls"] == 0 else 0
                    out["result"] = ev.get("subtype")
                    out["session_id"] = ev.get("session_id") or out["session_id"]
                    out["cost_usd"] = float(ev.get("total_cost_usd") or 0.0)
                    # The deadline SIGINT ends a turn as an error with terminal_reason "aborted_tools"
                    # (or another "aborted_*"); that is the referee stopping it, not a builder failure.
                    if ev.get("is_error") and str(ev.get("terminal_reason") or "").startswith("aborted"):
                        out["interrupted"] += 1
                    elif ev.get("is_error"):
                        error = ev.get("subtype") or "error"
                if error and counting:
                    out["errors"].append(error)
    except OSError:
        pass
    return out


def write_settings(path: str, settings: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(settings, f, indent=1)
