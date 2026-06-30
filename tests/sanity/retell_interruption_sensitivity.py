"""SANITY: interruption_sensitivity is <= 0.5 (no mid-utterance-pickup regression).

Regression guard for the 2026-06-30 16:25 listen test: user said partial words
('And', 'At') during Lisa's slot list -> Lisa kept restarting the list. 0.7 was
too high. 0.4 is the post-fix value.
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
    s = a.get("interruption_sensitivity")
    if s is None:
        return {"ok": False, "summary": "interruption_sensitivity not set"}
    if s > 0.5:
        return {"ok": False,
                "summary": f"interruption_sensitivity={s} too high; should be <= 0.5"}
    return {"ok": True, "summary": f"interruption_sensitivity={s}"}
