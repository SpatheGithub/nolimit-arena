"""An event's lifecycle, as a crash-safe state machine.

    events/<id>/
      config.yaml  card.json  teams.json  state.json     state.json is rewritten atomically per step
      settings/<team>.json  briefs/<team>.md  logs/<team>.jsonl|.stderr
      submissions/<team>/<sid>/ + index.jsonl             snapshots as the referee observed them
      bots/<team>/T<k>/                                   frozen bot per tournament
      entered/<name>/                                     external bots (`enter`)
      results/T<k>/summary.json + hand logs               per tournament
      report/                                             REPORT.md (and DEBRIEF.md)

Phases: created -> build -> (freeze:k -> tournament:k -> patch:k) ... -> report -> done.
``run`` resumes from the phase in state.json: windows still open keep going
(builders that died with the referee are relaunched or resumed), tournaments
are replayed from scratch (they're deterministic), and freezes are idempotent.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import os
import shutil
import signal
import subprocess
import time
import uuid

import yaml

from ..runner.loader import bot_hash
from ..tournament.card import save_card, settings_from_card
from ..tournament.play import derive
from ..tournament.pool import Entry
from ..tournament.tournament import default_workers, run_tournament
from ..tournament.validate import validate
from ..tournament.wsstate import fmt_clock, submissions as ws_submissions, write_json_atomic
from ..variants.render import render_event_md
from .builders import builder_env, claude_command, mock_command, read_stream, team_settings, write_settings
from .config import REPO, Team, draw_event, load_config
from .prompts import render_brief, render_patch
from .workspace import build_workspace, write_clock

EVENTS_ROOT = os.environ.get("ARENA_EVENTS_ROOT") or os.path.join(REPO, "events")
HOUSE = os.path.join(REPO, "arena", "house_bots")
MOCK_BEHAVIORS = ["normal"] * 6 + ["breaker", "slowpoke", "late", "silent"]


class Paused(Exception):
    pass


class Event:
    def __init__(self, event_id: str, root: str = EVENTS_ROOT):
        self.id = event_id
        self.dir = os.path.join(root, event_id)
        with open(self.p("card.json")) as f:
            self.card = json.load(f)
        with open(self.p("teams.json")) as f:
            self.teams = [Team(**t) for t in json.load(f)]
        with open(self.p("config.yaml")) as f:
            self.cfg = yaml.safe_load(f)
        self.state = self._load_state()

    # ------------------------------------------------------------ paths and state

    def p(self, *parts: str) -> str:
        return os.path.join(self.dir, *parts)

    def _load_state(self) -> dict:
        with open(self.p("state.json")) as f:
            return json.load(f)

    def save(self) -> None:
        write_json_atomic(self.p("state.json"), self.state)

    def note(self, kind: str, **detail) -> None:
        self.state.setdefault("events", []).append({"time": time.time(), "kind": kind, **detail})
        self.save()

    @property
    def scale(self) -> float:
        return self.state.get("time_scale", 1.0)

    @property
    def mock(self) -> bool:
        return self.state.get("mock", False)

    # ------------------------------------------------------------ new

    @classmethod
    def new(cls, config_path: str | None, card_from: str | None = None, root: str = EVENTS_ROOT,
            event_name: str | None = None) -> Event:
        cfg = load_config(config_path)
        if event_name:
            cfg["event"]["name"] = event_name
        event_id = cfg["event"]["name"]
        d = os.path.join(root, event_id)
        if os.path.exists(d):
            raise FileExistsError(f"{d} already exists")
        card, teams, notes = draw_event(cfg)
        if card_from:
            with open(os.path.join(root, card_from, "card.json")) as f:
                old = json.load(f)
            card = {**old, "event": event_id, "card_from": card_from}
        root_ws = os.path.dirname(teams[0].workspace) if teams else None
        if root_ws and os.path.realpath(root_ws).startswith(os.path.realpath(REPO) + os.sep):
            raise ValueError("paths.workspaces_root must be outside the arena repo")
        os.makedirs(d)
        save_card(card, os.path.join(d, "card.json"))
        with open(os.path.join(d, "teams.json"), "w") as f:
            json.dump([t.__dict__ for t in teams], f, indent=1)
        with open(os.path.join(d, "config.yaml"), "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)
        events_dir = os.path.realpath(d)
        for t in teams:
            if os.path.exists(t.workspace):
                raise FileExistsError(f"workspace {t.workspace} already exists")
            build_workspace(t.workspace, None, "# The event hasn't started yet.\n")
            write_settings(os.path.join(d, "settings", f"{t.team}.json"),
                           team_settings(t, teams, events_dir, os.path.realpath(REPO)))
        write_json_atomic(os.path.join(d, "state.json"), {
            "event": event_id, "phase": "created", "created": time.time(), "notes": notes,
            "builders": {}, "windows": [], "frozen": {}, "tournaments": {}, "events": []})
        return cls(event_id, root)

    # ------------------------------------------------------------ run

    def run(self, mock: bool = False, time_scale: float = 1.0, max_phases: int | None = None) -> None:
        if self.state["phase"] == "created":
            self.state.update(mock=mock, time_scale=time_scale)
            self.save()
        steps = 0
        while self.state["phase"] != "done":
            phase = self.state["phase"]
            kind, _, k = phase.partition(":")
            k = int(k) if k else 0
            if kind == "created":
                self._reveal()
            elif kind in ("build", "patch"):
                self._watch_window(kind, k)
            elif kind == "freeze":
                self._freeze(k)
            elif kind == "tournament":
                self._tournament(k)
            elif kind == "report":
                from .report import write_report
                write_report(self)
                self.state["phase"] = "done"
                self.save()
            steps += 1
            if max_phases and steps >= max_phases:
                return

    def _reveal(self) -> None:
        card = self.card
        start = time.time()
        end = start + card["build_minutes"] * 60 * self.scale
        md = render_event_md(card)
        ws_card = {**card, "cooldown_seconds": card["cooldown_seconds"] * self.scale}
        then = "Tournament T1 starts with your latest accepted submission."
        for t in self.teams:
            save_card({**ws_card, "team": t.team}, os.path.join(t.workspace, "kit", "event.json"))
            with open(os.path.join(t.workspace, "EVENT.md"), "w") as f:
                f.write(md)
            write_clock(t.workspace, [{"name": "Build window", "start": start, "end": end, "then": then, "submit": True}])
            with open(self._mkdir("briefs", f"{t.team}.md"), "w") as f:
                f.write(render_brief(card, t.team, len(self.teams), fmt_clock(end), t.archetype))
        self.state["windows"].append({"kind": "build", "k": 0, "start": start, "end": end})
        self.state["phase"] = "build"
        self.save()
        self._launch_all("build", 0, end)

    def _mkdir(self, *parts: str) -> str:
        os.makedirs(self.p(*parts[:-1]), exist_ok=True)
        return self.p(*parts)

    # ------------------------------------------------------------ builders

    def _launch_all(self, phase: str, k: int, deadline: float, prompts: dict[str, str] | None = None) -> None:
        stagger = self.cfg["builders"].get("launch_stagger_seconds", 2) * self.scale
        for i, t in enumerate(self.teams):
            if time.time() >= deadline:
                break
            self._launch(t, phase, k, deadline, (prompts or {}).get(t.team))
            if stagger and i + 1 < len(self.teams):
                time.sleep(stagger)

    def _launch(self, t: Team, phase: str, k: int, deadline: float, prompt: str | None) -> None:
        os.makedirs(self.p("logs"), exist_ok=True)
        b = self.state["builders"].setdefault(t.team, {})
        resume = phase == "patch" and bool(b.get("session_id"))
        if self.mock:
            behavior = MOCK_BEHAVIORS[derive(self.card["seed"], t.team) % len(MOCK_BEHAVIORS)]
            cmd = mock_command(t.workspace, phase, deadline, derive(self.card["seed"], t.team, phase, k), behavior)
            b["behavior"] = behavior
            env = {**os.environ, "PYTHONPATH": REPO}
        else:
            session = b.get("session_id") or str(uuid.uuid4())
            b["session_id"] = session
            first = "The build phase has started. Read EVENT.md, then build and submit your bot."
            budget = self.cfg["builders"].get("max_budget_usd_per_builder")
            cmd = claude_command(prompt or first, model=t.model, brief_file=self.p("briefs", f"{t.team}.md"),
                                 settings_file=self.p("settings", f"{t.team}.json"), session_id=session,
                                 auth_mode=self.cfg["auth"]["mode"], resume=resume, budget_usd=budget)
            env = builder_env(REPO)
        out = open(self.p("logs", f"{t.team}.jsonl"), "a")
        err = open(self.p("logs", f"{t.team}.stderr"), "a")
        proc = subprocess.Popen(cmd, cwd=t.workspace, env=env, stdout=out, stderr=err, start_new_session=True)
        out.close()
        err.close()
        b.update(pid=proc.pid, phase=f"{phase}:{k}", started=time.time(), exit=None)
        self.save()
        self._procs = getattr(self, "_procs", {})
        self._procs[t.team] = proc

    def _alive(self, team: str) -> bool:
        proc = getattr(self, "_procs", {}).get(team)
        if proc is not None:
            return proc.poll() is None
        pid = self.state["builders"].get(team, {}).get("pid")
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _stop_all(self) -> None:
        live = [t.team for t in self.teams if self._alive(t.team)]
        for sig, wait in ((signal.SIGINT, 10), (signal.SIGTERM, 30), (signal.SIGKILL, 5)):
            for team in live:
                pid = self.state["builders"][team]["pid"]
                try:
                    os.killpg(pid, sig)
                except OSError:
                    pass
            end = time.time() + wait
            while time.time() < end and any(self._alive(t) for t in live):
                time.sleep(0.2)
            live = [t for t in live if self._alive(t)]
            if not live:
                break
        for t in self.teams:
            b = self.state["builders"].get(t.team, {})
            proc = getattr(self, "_procs", {}).get(t.team)
            if proc is not None:
                b["exit"] = proc.returncode
            s = read_stream(self.p("logs", f"{t.team}.jsonl"))
            if s["session_id"] and not self.mock:
                b["session_id"] = s["session_id"]
            b["cost_usd"] = s["cost_usd"]
            b["errors"] = s["errors"]
        self.save()

    # ------------------------------------------------------------ windows

    def _watch_window(self, kind: str, k: int) -> None:
        w = self.state["windows"][-1]
        if time.time() < w["end"]:
            for t in self.teams:
                if not self._alive(t.team) and self.state["builders"].get(t.team, {}).get("phase") != f"{kind}:{k}":
                    self._launch(t, kind, k, w["end"], None)
        early_check = w["start"] + min(120 * self.scale, (w["end"] - w["start"]) / 2)
        checked = False
        while time.time() < w["end"]:
            self._observe_submissions()
            if not self.mock and not checked and time.time() > early_check:
                checked = True
                self._check_failures()
            time.sleep(0.5)
        self._observe_submissions()
        self._stop_all()
        self._observe_submissions(final=True)
        self.state["phase"] = f"freeze:{k + 1}"
        self.save()

    def resume_paused(self) -> None:
        """Restart the window that was paused, with its full length, and relaunch builders."""
        w = self.state["windows"][-1]
        length = w["end"] - w["start"]
        w["start"], w["end"] = time.time(), time.time() + length
        for t in self.teams:
            write_clock(t.workspace, [{"name": f"{w['kind'].title()} window", "start": w["start"], "end": w["end"],
                                       "then": "The next tournament starts with your latest accepted submission.",
                                       "submit": True}])
            self.state["builders"].get(t.team, {}).pop("phase", None)
        self.state["paused"] = None
        self.note("resumed", window=w["kind"])

    def _check_failures(self) -> None:
        bad = []
        for t in self.teams:
            s = read_stream(self.p("logs", f"{t.team}.jsonl"))
            if s["errors"] or (not self._alive(t.team) and s["events"] == 0):
                bad.append(t.team)
        if len(bad) > 0.2 * len(self.teams):
            self._stop_all()
            self.state["paused"] = f"{len(bad)} of {len(self.teams)} builders failed to start or hit auth/usage errors"
            self.note("paused", teams=bad)
            raise Paused(self.state["paused"])

    def _observe_submissions(self, final: bool = False) -> None:
        seen = self.state.setdefault("seen", {})
        for t in self.teams:
            records = ws_submissions(t.workspace)
            start = seen.get(t.team, 0)
            for r in records[start:]:
                if r.get("status") != "accepted" or not r.get("id"):
                    continue
                src = os.path.join(t.workspace, ".submissions", r["id"])
                dst = self.p("submissions", t.team, r["id"])
                if not os.path.isdir(src) or os.path.exists(dst):
                    continue
                shutil.copytree(src, dst)
                h = bot_hash(dst)
                with open(self._mkdir("submissions", t.team, "index.jsonl"), "a") as f:
                    f.write(json.dumps({"sid": r["id"], "hash": h, "claimed_hash": r.get("hash"),
                                        "ws_time": r.get("time"), "observed": time.time(), "final_sweep": final}) + "\n")
            seen[t.team] = len(records)
        self.save()

    def submissions(self, team: str) -> list[dict]:
        path = self.p("submissions", team, "index.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]

    # ------------------------------------------------------------ freeze

    def _candidates(self, team: str, cutoff: float) -> list[dict]:
        """Accepted snapshots the referee saw by ``cutoff``, honouring the cooldown, newest first."""
        cooldown = self.card["cooldown_seconds"] * self.scale * 0.9
        ok, last = [], None
        for r in self.submissions(team):
            if r["observed"] > cutoff + 2 or r.get("hash") != r.get("claimed_hash"):
                continue
            if last is not None and (r["ws_time"] or 0) - last < cooldown:
                continue
            ok.append(r)
            last = r["ws_time"] or r["observed"]
        return list(reversed(ok))

    def _freeze(self, k: int) -> None:
        cutoff = self.state["windows"][-1]["end"]
        settings = settings_from_card(self.card)
        cache = self.state.setdefault("validated", {})
        frozen = {}

        def check(team: str) -> tuple[str, dict]:
            for r in self._candidates(team, cutoff):
                path = self.p("submissions", team, r["sid"])
                if r["hash"] not in cache:
                    v = validate(path, settings, HOUSE, tables=2, seed=k)
                    cache[r["hash"]] = {"ok": v["ok"], "reasons": v["reasons"], "timing": {
                        x: v["stats"][x] for x in ("cpu_p50_us", "cpu_p99_us", "cpu_max_us")} if v["stats"] else None}
                if cache[r["hash"]]["ok"]:
                    return team, {"sid": r["sid"], "hash": r["hash"], "observed": r["observed"],
                                  "timing": cache[r["hash"]]["timing"]}
            return team, {"sid": None, "reason": "no valid accepted submission"}

        with cf.ThreadPoolExecutor(max_workers=max(1, default_workers())) as ex:
            for team, info in ex.map(check, [t.team for t in self.teams]):
                frozen[team] = info
                if info["sid"]:
                    dst = self.p("bots", team, f"T{k}")
                    shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(self.p("submissions", team, info["sid"]), dst)
                    notes = os.path.join(self._team(team).workspace, "NOTES.md")
                    if os.path.exists(notes):
                        shutil.copy2(notes, os.path.join(self.p("bots", team), f"NOTES.T{k}.md"))
        self.state["frozen"][str(k)] = frozen
        self.state["phase"] = f"tournament:{k}"
        self.save()

    def _team(self, team: str) -> Team:
        return next(t for t in self.teams if t.team == team)

    # ------------------------------------------------------------ tournaments

    def entries(self, k: int) -> list[Entry]:
        out = [Entry(team, self.p("bots", team, f"T{k}"))
               for team, info in sorted(self.state["frozen"][str(k)].items()) if info["sid"]]
        entered = self.p("entered")
        if os.path.isdir(entered):
            out += [Entry(name, os.path.join(entered, name)) for name in sorted(os.listdir(entered))
                    if os.path.isfile(os.path.join(entered, name, "agent.py"))]
        return out

    def _tournament(self, k: int) -> None:
        entries = self.entries(k)
        out_dir = self.p("results", f"T{k}")
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)
        if len(entries) < 2:
            self.note("tournament_skipped", k=k, entries=len(entries))
            result = {"meta": {"skipped": True, "entries": len(entries)}, "entries": []}
        else:
            workers = self.cfg["tournament"].get("workers", "auto")
            result = run_tournament(entries, settings_from_card(self.card), self.card["iterations"],
                                    seed=derive(self.card["seed"], "T", k),
                                    workers=0 if workers == "auto" else int(workers), log_dir=out_dir)
        with open(os.path.join(out_dir, "summary.json"), "w") as f:
            json.dump({"meta": result["meta"], "entries": result["entries"]}, f, indent=1, default=str)
        self.state["tournaments"][str(k)] = {"done": True, "elapsed_s": result["meta"].get("elapsed_s")}
        if k < self.card["tournaments"]:
            self._feedback_and_patch(k)
        else:
            self.state["phase"] = "report"
            self.save()

    def summary(self, k: int) -> dict | None:
        path = self.p("results", f"T{k}", "summary.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def weighted(self, upto: int) -> dict[str, float]:
        """Cumulative weighted score per team: sum of k * mean points in T<k>."""
        out = {t.team: 0.0 for t in self.teams}
        for k in range(1, upto + 1):
            s = self.summary(k)
            if s:
                for row in s["entries"]:
                    if row["name"] in out:
                        out[row["name"]] += k * row["mean"]
        return out

    def _feedback_and_patch(self, k: int) -> None:
        from .report import write_feedback
        summary = self.summary(k)
        start = time.time()
        end = start + self.card["patch_minutes"] * 60 * self.scale
        cum = self.weighted(k)
        cum_rank = {team: i + 1 for i, team in enumerate(sorted(cum, key=lambda x: -cum[x]))}
        rows = {r["name"]: r for r in summary["entries"]}
        ranked = {r["name"]: r["rank"] for r in summary["entries"]}
        prompts = {}
        for t in self.teams:
            files = write_feedback(self, t, k, summary)
            write_clock(t.workspace, [{"name": f"Patch window before T{k + 1}", "start": start, "end": end,
                                       "then": f"T{k + 1} starts with your latest accepted submission.", "submit": True}])
            row = rows.get(t.team)
            if row is None:
                prompts[t.team] = (f"Tournament T{k} is finished and you had no valid bot in it. Your next chance "
                                   f"is T{k + 1}, frozen at {fmt_clock(end)}. Get a working bot accepted with "
                                   "kit/submit.py now; kit/clock.py shows the time left.")
            else:
                prompts[t.team] = render_patch(self.card, k, self.card["patch_minutes"], fmt_clock(end), row,
                                               ranked[t.team], len(rows), cum[t.team], cum_rank[t.team], files)
        self.state["windows"].append({"kind": "patch", "k": k, "start": start, "end": end})
        self.state["phase"] = f"patch:{k}"
        self.save()
        if self.card["patch_minutes"] > 0:
            self._launch_all("patch", k, end, prompts)
