"""NEGATIVE: book_slot with garbage slot_id returns graceful error, not 5xx."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/book_slot",
                        body=retell_tool_payload({
                            "slot_id": "GARBAGE-NOT-A-DATE",
                            "caller_name": "Negative Test",
                            "callback": "0000000003",
                            "treatment": "consultation",
                        }))
    if code != 200:
        return {"ok": False, "summary": f"non-200 on bad input: {code}"}
    if not d:
        return {"ok": False, "summary": "no JSON body"}
    # ok=False or status!=confirmed both acceptable; what matters is graceful return
    if d.get("ok") is True and (d.get("booking") or {}).get("status") == "confirmed":
        return {"ok": False, "summary": "garbage slot_id booked anyway"}
    return {"ok": True, "summary": "graceful error"}
