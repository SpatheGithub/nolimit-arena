"""The post-event debrief: docs/ANALYST_PROMPT.md as one `claude -p` run.

    python -m arena.referee debrief <event> [--mock] [--model opus] [--effort max] [--budget-usd 15]

It spends usage, so it runs only when asked. First it rewrites REPORT.md (with
the rank view, field profile and exploit board) and the event card the prompt
cites (events/<id>/event_card.md). Then one analyst session runs from the repo
root. It may read the event, including builder transcripts and, through
`python -m arena.tournament.hands`, the compressed hand logs. It may write only
events/<id>/report/DEBRIEF.md and LESSONS.md at the repo root.

The guard rails are flags and a settings file, each checked against Claude
Code 2.1.300 (docs/CLAUDE_CODE_NOTES.md, "Debrief invocation"):

- `--permission-mode dontAsk` denies every call no allow rule covers.
- The allow rules are Edit rules (which cover Write) for those two files, and
  Bash rules for the hand printer; read-only commands need no rule.
- `--restricted` (or `--bare` with an API key) ignores the user's settings files.
- There are no MCP servers, skills, hooks, CLAUDE.md or auto memory.

The settings file also denies the sentinel tool named in `--tools`, so the init
event shows whether it loaded: `-p` silently ignores a settings file it can't use.

The stream goes to events/<id>/logs/debrief.jsonl (kept out of git, like the
builders' transcripts). report/debrief.json records the run: session, model,
cost, and what was written.

`--mock` runs a stub analyst instead of Claude, for tests. It writes
report/DEBRIEF.mock.md and appends a line to report/LESSONS.mock.md, so it
never overwrites a real debrief or touches the real LESSONS.md.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid

from .builders import DENIED_TOOLS, SENTINEL_TOOL, builder_env, read_stream, write_settings
from .config import REPO

TOOLS = "Bash,Read,Edit,Write,Glob,Grep," + SENTINEL_TOOL
HANDS = "arena.tournament.hands"
HEADINGS = ("What won", "What lost", "Archetypes and models", "Time use", "Rules-specific insight",
            "Where the field leaks points", "Exploits that worked", "A 60-minute build plan")


def render_prompt(event_id: str, repo: str = REPO) -> str:
    with open(os.path.join(repo, "docs", "ANALYST_PROMPT.md")) as f:
        text = f.read()
    text = re.sub(r"<!--.*?-->\s*", "", text, flags=re.S)  # the maintainers' note
    return text.replace("{{EVENT_ID}}", event_id)


def write_event_card(ev) -> str:
    """events/<id>/event_card.md: the EVENT.md builders were given, plus the card's raw numbers."""
    from ..variants.render import render_event_md
    path = ev.p("event_card.md")
    card = {k: v for k, v in ev.card.items() if k != "team"}
    with open(path, "w") as f:
        f.write(render_event_md(card) + "\n\n## The card as data\n\n```json\n" + json.dumps(card, indent=1) + "\n```\n")
    return path


def _edit_rule(path: str, repo: str) -> str:
    """An Edit rule for one file: ./relative to the run's working directory (the repo root)
    when inside it, else //absolute (a single leading / would anchor at the settings file)."""
    rel = os.path.relpath(path, repo)
    return f"Edit(./{rel})" if not rel.startswith("..") else f"Edit(/{os.path.abspath(path)})"


def debrief_settings(debrief_md: str, lessons: str, repo: str = REPO) -> dict:
    return {
        "permissions": {
            "allow": [_edit_rule(debrief_md, repo), _edit_rule(lessons, repo),
                      f"Bash(python -m {HANDS} *)", f"Bash(.venv/bin/python -m {HANDS} *)"],
            "deny": list(DENIED_TOOLS), "blockReadsOutsideWorkingDirectories": True},
        "disableAllHooks": True, "autoMemoryEnabled": False, "syncClaudeAiSkills": False,
        "syncClaudeAiPlugins": False, "disableClaudeAiConnectors": True, "disableWorkflows": True,
        "crossSessionInbound": "refuse",
    }


def debrief_command(prompt: str, *, model: str, settings_file: str, session_id: str, auth_mode: str,
                    effort: str | None = None, budget_usd: float | None = None) -> list[str]:
    cmd = ["claude", "-p", prompt, "--model", model, "--settings", settings_file, "--tools", TOOLS,
           "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands",
           "--permission-mode", "dontAsk", "--permission-prompts", "none",
           "--output-format", "stream-json", "--verbose", "--session-id", session_id]
    cmd += ["--bare"] if auth_mode == "api_key" else ["--restricted"]
    if effort:
        cmd += ["--effort", effort]
    if budget_usd:
        cmd += ["--max-budget-usd", f"{budget_usd:g}"]
    return cmd


def _lines(path: str) -> int:
    try:
        with open(path) as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def run_debrief(ev, *, mock: bool = False, model: str = "opus", effort: str | None = "max",
                budget_usd: float | None = 15.0, lessons: str | None = None, repo: str = REPO) -> dict:
    from .report import write_report
    write_report(ev)
    write_event_card(ev)
    debrief_md = ev.p("report", "DEBRIEF.mock.md" if mock else "DEBRIEF.md")
    lessons = lessons or (ev.p("report", "LESSONS.mock.md") if mock else os.path.join(repo, "LESSONS.md"))
    for d in ("logs", "settings", "report"):
        os.makedirs(ev.p(d), exist_ok=True)
    log, err = ev.p("logs", "debrief.jsonl"), ev.p("logs", "debrief.stderr")
    offset = os.path.getsize(log) if os.path.exists(log) else 0
    session = str(uuid.uuid4())
    if mock:
        cmd = [sys.executable, "-m", "arena.referee.debrief", "--stub", ev.id, debrief_md, lessons]
        env = {**os.environ, "PYTHONPATH": repo}
    else:
        settings_file = ev.p("settings", "debrief.json")
        write_settings(settings_file, debrief_settings(debrief_md, lessons, repo))
        cmd = debrief_command(render_prompt(ev.id, repo), model=model, settings_file=settings_file,
                              session_id=session, auth_mode=ev.cfg["auth"]["mode"], effort=effort,
                              budget_usd=budget_usd)
        env = builder_env(repo)
    had = _lines(lessons)
    start = time.time()
    with open(log, "ab") as out, open(err, "ab") as errf:
        code = subprocess.run(cmd, cwd=repo, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=errf).returncode
    s = read_stream(log, errors_from=offset)
    info = {"session_id": session, "mock": mock, "model": s["model"] or model, "effort": effort,
            "started": start, "finished": time.time(), "exit": code, "result": s["result"], "errors": s["errors"],
            "cost_usd": s["cost_usd"], "settings_loaded": SENTINEL_TOOL not in (s["tools"] or []),
            "debrief": os.path.basename(debrief_md),
            "wrote_debrief": os.path.exists(debrief_md) and os.path.getmtime(debrief_md) >= start,
            "lessons": os.path.relpath(lessons, repo), "lessons_added": max(0, _lines(lessons) - had)}
    with open(ev.p("report", "debrief.json"), "w") as f:
        json.dump(info, f, indent=1)
    return info


def _stub(event_id: str, debrief_md: str, lessons: str) -> None:
    """The mock analyst: the stream events and files a real run leaves, with no model behind them."""
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "mock", "model": "mock",
                      "tools": TOOLS.replace("," + SENTINEL_TOOL, "").split(",")}), flush=True)
    os.makedirs(os.path.dirname(debrief_md), exist_ok=True)
    with open(debrief_md, "w") as f:
        f.write(f"# Debrief for mini-event {event_id} (mock)\n\nWritten by the mock analyst; no model ran.\n\n"
                + "".join(f"## {i}. {h}\n\nNothing yet.\n\n" for i, h in enumerate(HEADINGS, 1)))
    new = not os.path.exists(lessons)
    with open(lessons, "a") as f:
        if new:
            f.write("# Lessons\n\n")
        f.write(f"- {time.strftime('%Y-%m-%d')} ({event_id}, mock debrief): a real debrief appends 5 to 10 here.\n")
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": "mock",
                      "total_cost_usd": 0.0, "num_turns": 1}), flush=True)


if __name__ == "__main__" and len(sys.argv) == 5 and sys.argv[1] == "--stub":
    _stub(*sys.argv[2:])
