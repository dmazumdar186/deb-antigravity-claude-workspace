"""NEGATIVE: book_slot with callback='' returns 'Missing' error gracefully (synthetic email path)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/book_slot",
                        body=retell_tool_payload({
                            "slot_id": "2026-07-01T09:00:00.000+02:00",
                            "caller_name": "Negative Test",
                            "callback": "",  # empty -> should be caught as missing
                            "treatment": "consultation",
                        }))
    if code != 200 or not d:
        return {"ok": False, "summary": f"code={code}"}
    if d.get("ok") is True:
        return {"ok": False, "summary": "accepted booking with empty callback"}
    return {"ok": True, "summary": d.get("summary", "")[:80]}
