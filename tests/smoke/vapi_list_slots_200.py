"""SMOKE: POST /vapi/tools/list_slots returns 200 with a non-empty results array."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, vapi_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/vapi/tools/list_slots",
                        body=vapi_tool_payload("list_slots", {"treatment": "consultation"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"non-JSON or non-200: code={code}"}
    results = d.get("results") or []
    if not results:
        return {"ok": False, "summary": "no results"}
    if "result" not in results[0]:
        return {"ok": False, "summary": f"no result field: {results[0]}"}
    return {"ok": True}
