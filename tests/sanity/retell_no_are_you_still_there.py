"""SANITY: global_prompt FORBIDS 'Are you still there?' phrasing.

Regression guard for the 2026-06-30 16:25 listen test, which fired the phrase
immediately after every question. Retell's native silence detection handles
dead air; this phrase kills the call rhythm.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow {code}"}
    gp = f.get("global_prompt") or ""
    # The prompt must explicitly contain a hard ban on the phrase.
    if "NEVER" not in gp or "Are you still there" not in gp:
        return {"ok": False, "summary": "global_prompt does not explicitly ban 'Are you still there?'"}
    if "Retell's silence detection" not in gp and "silence detection" not in gp:
        return {"ok": False, "summary": "global_prompt missing rationale (silence-detection)"}
    return {"ok": True, "summary": "hard-ban rule present"}
