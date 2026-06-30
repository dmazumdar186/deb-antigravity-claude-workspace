"""NEGATIVE: list_slots with treatment='invalid-xyz' should default to 'consultation'."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "invalid-xyz"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"code={code}"}
    # Worker normalizes unknown treatment to "consultation" (defensive default)
    if not d.get("ok"):
        return {"ok": False, "summary": f"errored on unknown treatment: {d.get('summary')}"}
    if not d.get("slots"):
        return {"ok": False, "summary": "no slots returned for fallback"}
    return {"ok": True, "summary": "unknown treatment fell back gracefully"}
