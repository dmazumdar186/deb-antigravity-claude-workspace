"""SMOKE: POST /retell/tools/list_slots returns 200 + ok:true + summary string."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "consultation"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"non-JSON or non-200: code={code}"}
    if d.get("ok") is not True:
        return {"ok": False, "summary": f"ok != true: {d}"}
    if not isinstance(d.get("summary"), str):
        return {"ok": False, "summary": "summary must be string"}
    if not d.get("slots"):
        return {"ok": False, "summary": "slots array empty"}
    return {"ok": True}
