"""SANITY: Retell list_slots summary is ASCII-only English with AM/PM (mojibake regression)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload, all_ascii  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "consultation"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"call failed: {code}"}
    s = d.get("summary")
    if not isinstance(s, str):
        return {"ok": False, "summary": "summary not string"}
    if not all_ascii(s):
        return {"ok": False, "summary": "summary contains non-ASCII byte"}
    if "AM" not in s and "PM" not in s and "No slots" not in s:
        return {"ok": False, "summary": "summary not English-time-formatted"}
    return {"ok": True}
