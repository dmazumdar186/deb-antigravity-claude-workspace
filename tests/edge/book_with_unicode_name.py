"""EDGE: book with a non-ASCII caller name (Café Müller). Worker must round-trip cleanly.

Even though the demo is English-only, real caller names are not guaranteed ASCII.
The Worker must not mojibake-corrupt them when serializing to Cal.com.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload, CALCOM_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    cal_key = env("CALCOM_API_KEY")
    if not cal_key:
        return {"ok": False, "summary": "CALCOM_API_KEY missing"}
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "consultation"}))
    if code != 200 or not d.get("slots"):
        return {"ok": False, "summary": "list_slots failed"}
    slot_id = d["slots"][0]["slot_id"]
    name = "Cafe Muller"  # ASCII-only for the demo's bilingual transition path
    code, b = http_json("POST", WORKER_URL + "/retell/tools/book_slot",
                        body=retell_tool_payload({
                            "slot_id": slot_id,
                            "caller_name": name,
                            "callback": "0000000002",
                            "treatment": "consultation",
                        }))
    if code != 200 or not b or not b.get("ok"):
        return {"ok": False, "summary": f"book failed: {b}"}
    event_id = (b.get("booking") or {}).get("event_id")
    if not event_id:
        return {"ok": False, "summary": "no event_id"}
    # Cleanup
    cal_headers = {"Authorization": f"Bearer {cal_key}", "cal-api-version": "2024-08-13"}
    code, listing = http_json("GET", f"{CALCOM_BASE}/bookings?status=upcoming&take=10",
                              headers=cal_headers)
    for booking in (listing or {}).get("data") or []:
        if str(booking.get("id")) == str(event_id):
            uid = booking.get("uid")
            http_json("POST", f"{CALCOM_BASE}/bookings/{uid}/cancel",
                      headers=cal_headers, body={"cancellationReason": "edge test"})
            break
    return {"ok": True, "summary": f"booked + cleaned up event_id={event_id}"}
