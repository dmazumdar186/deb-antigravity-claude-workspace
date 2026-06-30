"""NEGATIVE: responsiveness MUST NOT be back at the default 1.0.

Regression guard: 1.0 produced the eager 'Are you still there?' cascade. Any
value > 0.8 means a future agent.patch accidentally reset the knob.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    aid = env("RETELL_AGENT_ID")
    code, a = http_json("GET", f"{RETELL_BASE}/get-agent/{aid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not a:
        return {"ok": False, "summary": f"get-agent {code}"}
    r = a.get("responsiveness")
    if r is None:
        return {"ok": False, "summary": "responsiveness unset (would default to 1.0)"}
    if r > 0.8:
        return {"ok": False,
                "summary": f"responsiveness={r} too high (default 1.0 regression)"}
    return {"ok": True, "summary": f"responsiveness={r}"}
