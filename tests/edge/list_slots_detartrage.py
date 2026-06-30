"""EDGE: list_slots for treatment=detartrage returns slots (non-default treatment path)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "detartrage"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"code={code}"}
    if not d.get("ok") or not d.get("slots"):
        return {"ok": False, "summary": d.get("summary", "no slots")}
    return {"ok": True, "summary": f"{len(d['slots'])} detartrage slots"}
