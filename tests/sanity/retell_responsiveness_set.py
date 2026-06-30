"""SANITY: Retell agent has responsiveness <= 0.6 (2026-06-30 listen-test fix).

The default 1.0 caused 'Are you still there?' to fire after every ack. Lowered to
0.5 for patient turn-taking. Regression-protect against accidental revert.
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
    if r > 0.6:
        return {"ok": False,
                "summary": f"responsiveness={r} too high; should be <= 0.6 per 2026-06-30 fix"}
    return {"ok": True, "summary": f"responsiveness={r}"}
