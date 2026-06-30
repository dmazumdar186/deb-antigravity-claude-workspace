"""SANITY: Retell agent has responsiveness in the tuned band [0.5, 0.8].

2026-06-30 14:43 (responsiveness=1.0): 'Are you still there?' cascade.
2026-06-30 16:25 (responsiveness=0.5): too patient -> e2e p50=3.3s -> caller pauses
                                       -> agent fires 'are you still there?' anyway.
Current setting 0.7 = compromise. Below 0.5 = too sluggish; above 0.8 = eager again.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    aid = env("RETELL_AGENT_ID")
    if not all([key, aid]):
        return {"ok": False, "summary": "Retell keys missing"}
    code, a = http_json("GET", f"{RETELL_BASE}/get-agent/{aid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not a:
        return {"ok": False, "summary": f"get-agent failed: {code}"}
    r = a.get("responsiveness")
    if r is None:
        return {"ok": False, "summary": "responsiveness not set"}
    if r < 0.5 or r > 0.8:
        return {"ok": False,
                "summary": f"responsiveness={r} outside tuned band [0.5, 0.8]"}
    return {"ok": True, "summary": f"responsiveness={r}"}
