"""SANITY: Vapi list_slots result is a single-line string per Vapi contract (mojibake regression)."""
from pathlib import Path
import sys, re
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, vapi_tool_payload, all_ascii  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/vapi/tools/list_slots",
                        body=vapi_tool_payload("list_slots", {"treatment": "consultation"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"call failed: {code}"}
    r = (d.get("results") or [{}])[0].get("result")
    if not isinstance(r, str):
        return {"ok": False, "summary": f"result type {type(r).__name__}, expected str"}
    if re.search(r"[\n\r]", r):
        return {"ok": False, "summary": "result contains newline (Vapi contract violation)"}
    if not all_ascii(r):
        return {"ok": False, "summary": "result contains non-ASCII byte (mojibake regression)"}
    if "slot_id=" not in r:
        return {"ok": False, "summary": "result missing slot_id pointer"}
    return {"ok": True, "summary": r[:80]}
