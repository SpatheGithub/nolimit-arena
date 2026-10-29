"""What the viewer shows about an event outside the tables: the phase and its
clock, each builder's state and latest action, the plan's usage meter, and the
leaderboard so far. It reads the referee's files only (state.json, teams.json,
card.json, submissions, builder logs) and never writes.
"""

from __future__ import annotations

import json
import os
import time

PHASES = {"created": "Not started", "build": "Build window", "freeze": "Freezing bots for", "tournament": "Tournament",
          "patch": "Patch window before", "report": "Writing the report", "done": "Finished"}
TAIL_BYTES = 32_000  # enough for a builder's last few events


def _load(path: str, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tail_events(path: str, nbytes: int = TAIL_BYTES) -> list[dict]:
    """The last stream-json events of a builder log, oldest first."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - nbytes))
            lines = f.read().split(b"\n")
    except OSError:
        return []
    if size > nbytes:
        lines = lines[1:]  # the first line is cut
    out = []
    for raw in lines:
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def _describe(call: dict) -> str:
    name, args = call.get("name", "?"), call.get("input") or {}
    if name == "Bash":
        what = args.get("description") or args.get("command", "")
    elif name in ("Read", "Edit", "Write"):
        what = os.path.basename(args.get("file_path", ""))
    else:
        what = args.get("pattern", "")
    what = " ".join(str(what).split())[:100]
    return f"{name}: {what}" if what else name


def last_action(events: list[dict]) -> str | None:
    """The builder's latest tool call, or what it said if that came after."""
    for ev in reversed(events):
        if ev.get("type") != "assistant":
            continue
        for c in reversed((ev.get("message") or {}).get("content") or []):
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                return _describe(c)
            if c.get("type") == "text" and c.get("text", "").strip():
                return "Says: " + " ".join(c["text"].split())[:100]
    return None


def _label(kind: str, k: str) -> str:
    base = PHASES.get(kind, kind)
    if kind in ("freeze", "tournament"):
        return f"{base} T{k}"
    if kind == "patch":
        return f"{base} T{int(k) + 1}"
    return base


def event_status(ev_dir: str) -> dict:
    state = _load(os.path.join(ev_dir, "state.json"), {}) or {}
    teams = _load(os.path.join(ev_dir, "teams.json"), []) or []
    card = _load(os.path.join(ev_dir, "card.json"), {}) or {}
    now = time.time()
    kind, _, k = state.get("phase", "created").partition(":")
    window = (state.get("windows") or [None])[-1]
    in_window = kind in ("build", "patch") and window is not None and now < window["end"]
    meter, meter_mtime = None, -1.0
    builders = []
    for t in teams:
        team = t["team"]
        b = (state.get("builders") or {}).get(team, {})
        log = os.path.join(ev_dir, "logs", f"{team}.jsonl")
        events = tail_events(log)
        try:
            mtime = os.stat(log).st_mtime
        except OSError:
            mtime = None
        for ev in reversed(events):
            if ev.get("type") == "rate_limit_event" and mtime and mtime > meter_mtime:
                info = ev.get("rate_limit_info") or {}
                five = (info.get("unifiedWindows") or {}).get("five_hour") or {}
                meter = {"used": five.get("utilization"), "resets_at": five.get("resetsAt") or info.get("resetsAt"),
                         "status": info.get("status")}
                meter_mtime = mtime
                break
        alive = _alive(b.get("pid"))
        if state.get("paused"):
            status = "paused"
        elif kind == "created" or not b:
            status = "waiting"
        elif in_window:
            status = "working" if alive else "idle"
        else:
            status = "working" if alive else "stopped"
        try:
            with open(os.path.join(ev_dir, "submissions", team, "index.jsonl")) as f:
                subs = sum(1 for line in f if line.strip())
        except OSError:
            subs = 0
        builders.append({"team": team, "model": b.get("model") or t.get("model"), "archetype": t.get("archetype"),
                         "status": status, "runs": b.get("launches", 0),
                         "checks": sum((b.get("nudges") or {}).values()), "subs": subs,
                         "last": last_action(events), "active": mtime})
    done, weighted, latest = [], {}, None
    for j in range(1, int(card.get("tournaments") or 0) + 1):
        summary = _load(os.path.join(ev_dir, "results", f"T{j}", "summary.json"))
        if not summary:
            continue
        done.append(j)
        latest = (j, summary["entries"])
        for e in summary["entries"]:
            weighted[e["name"]] = weighted.get(e["name"], 0.0) + j * e["mean"]
    board = None
    if latest:
        j, entries = latest
        rows = sorted(entries, key=lambda e: -weighted[e["name"]])
        board = {"t": j, "rows": [{"team": e["name"], "mean": round(e["mean"], 2), "lo": round(e["lo"], 2),
                                   "hi": round(e["hi"], 2), "weighted": round(weighted[e["name"]], 1)}
                                  for e in rows]}
    return {"id": os.path.basename(os.path.normpath(ev_dir)), "phase": state.get("phase", "created"),
            "label": _label(kind, k), "now": now, "window": window if kind in ("build", "patch") else None,
            "paused": state.get("paused"), "resume_at": state.get("resume_at"),
            "variant": (card.get("variant") or {}).get("name"), "tournaments": {"done": len(done),
                                                                                "total": card.get("tournaments")},
            "builders": builders, "meter": meter, "leaderboard": board}
