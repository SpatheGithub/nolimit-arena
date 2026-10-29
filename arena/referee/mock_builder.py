"""A scripted stand-in for a Claude builder, for free pipeline tests.

Runs in a workspace and uses the kit exactly as a builder would: copies a
house bot into bot/, sometimes breaks it, and submits with kit/submit.py on a
schedule within the window. Prints stream-json-like events so the referee's
log parsing is exercised.

Behaviors:
    normal    submit early, then a different house bot later
    breaker   submit a broken bot (rejected), then a working one
    late      submit only after the deadline (rejected: no bot this window)
    silent    never submit
    slowpoke  one submission near the end of the window
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid

BREAK = '''

_orig_act = Agent.act
_calls = [0]


def _broken_act(self, obs):
    _calls[0] += 1
    if _calls[0] % 5 == 0:
        raise RuntimeError("mock builder broke this bot")
    return _orig_act(self, obs)


Agent.act = _broken_act
'''


def emit(**event) -> None:
    print(json.dumps(event), flush=True)


def install(ws: str, bot: str, broken: bool = False) -> None:
    dst = os.path.join(ws, "bot")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(ws, "kit", "house_bots", bot), dst,
                    ignore=shutil.ignore_patterns("__pycache__"))
    if broken:
        with open(os.path.join(dst, "agent.py"), "a") as f:
            f.write(BREAK)
    with open(os.path.join(ws, "NOTES.md"), "a") as f:
        f.write(f"\n- {time.strftime('%H:%M:%S')}: installed house bot {bot}{' (broken)' if broken else ''}\n")


def submit(ws: str) -> bool:
    p = subprocess.run([sys.executable, "kit/submit.py"], cwd=ws, capture_output=True, text=True)
    last = (p.stdout.strip().splitlines() or ["(no output)"])[-1]
    emit(type="assistant", message={"content": [{"type": "text", "text": f"submit.py: {last}"}]})
    return "ACCEPTED" in p.stdout


def sleep_until(t: float) -> None:
    while time.time() < t:
        time.sleep(min(0.2, max(0.0, t - time.time())))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--phase", default="build")
    ap.add_argument("--deadline", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--behavior", default="normal")
    a = ap.parse_args(argv)
    ws, rng = a.workspace, random.Random(a.seed)
    start = time.time()
    span = max(a.deadline - start, 1.0)
    at = lambda frac: start + frac * span
    bots = sorted(d for d in os.listdir(os.path.join(ws, "kit", "house_bots"))
                  if os.path.isfile(os.path.join(ws, "kit", "house_bots", d, "agent.py")))
    session = f"mock-{uuid.UUID(int=rng.getrandbits(128))}"
    emit(type="system", subtype="init", session_id=session, tools=["Bash", "Read", "Edit", "Write"], mock=True)
    b = a.behavior
    if a.phase != "build" and b in ("late", "silent"):
        b = "normal" if rng.random() < 0.5 else b
    if b == "normal":
        sleep_until(at(0.2)); install(ws, rng.choice(bots)); submit(ws)
        sleep_until(at(0.65)); install(ws, rng.choice(bots)); submit(ws)
    elif b == "breaker":
        sleep_until(at(0.2)); install(ws, rng.choice(bots), broken=True); submit(ws)
        sleep_until(at(0.55)); install(ws, rng.choice(bots)); submit(ws)
    elif b == "slowpoke":
        sleep_until(at(0.85)); install(ws, rng.choice(bots)); submit(ws)
    elif b == "late":
        install(ws, rng.choice(bots))
        sleep_until(a.deadline + 0.5); submit(ws)
    emit(type="result", subtype="success", is_error=False, session_id=session, total_cost_usd=0.0,
         duration_ms=int((time.time() - start) * 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
