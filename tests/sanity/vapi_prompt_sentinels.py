"""SANITY: Vapi system prompt contains all 6 corpus-scenario sentinels."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, VAPI_BASE, env  # type: ignore[import-not-found]


REQUIRED_SENTINELS = [
    "TOOL CALL PRECONDITIONS",
    "NEVER use bare filler phrases",
    "HANDOFF MEANS NO TOOLS",
    "Goodbye / Hello / single ambiguous words",
    "Tool failure recovery",
    "ONE-QUESTION-AT-A-TIME",
]


def run() -> dict:
    key = env("VAPI_API_KEY")
    aid = env("VAPI_ASSISTANT_ID")
    if not all([key, aid]):
        return {"ok": False, "summary": "VAPI keys missing"}
    code, a = http_json("GET", f"{VAPI_BASE}/assistant/{aid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not a:
        return {"ok": False, "summary": f"get-assistant failed: {code}"}
    sys_msg = next(
        (m.get("content", "") for m in (a.get("model") or {}).get("messages", [])
         if m.get("role") == "system"),
        "",
    )
    missing = [s for s in REQUIRED_SENTINELS if s not in sys_msg]
    if missing:
        return {"ok": False, "summary": f"missing sentinels: {missing}"}
    return {"ok": True, "summary": f"all {len(REQUIRED_SENTINELS)} sentinels present"}
