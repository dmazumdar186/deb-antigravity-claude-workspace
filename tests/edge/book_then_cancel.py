"""EDGE: book a slot end-to-end then cancel it (full Cal.com round-trip)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload, CALCOM_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    cal_key = env("CALCOM_API_KEY")
    if not cal_key:
        return {"ok": False, "summary": "CALCOM_API_KEY missing"}
    # 1. list
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "consultation"}))
    if code != 200 or not d or not d.get("slots"):
        return {"ok": False, "summary": "list_slots failed"}
    slot_id = d["slots"][0]["slot_id"]
    # 2. book
    code, b = http_json("POST", WORKER_URL + "/retell/tools/book_slot",
                        body=retell_tool_payload({
                            "slot_id": slot_id,
                            "caller_name": "Edge Test Booking",
                            "callback": "0000000001",
                            "treatment": "consultation",
                        }))
    if code != 200 or not b or not b.get("ok"):
        return {"ok": False, "summary": f"book failed: {b}"}
    event_id = (b.get("booking") or {}).get("event_id")
    if not event_id:
        return {"ok": False, "summary": "no event_id"}
    # 3. cancel via Cal.com API
    cal_headers = {"Authorization": f"Bearer {cal_key}", "cal-api-version": "2024-08-13"}
    code, listing = http_json("GET", f"{CALCOM_BASE}/bookings?status=upcoming&take=10",
                              headers=cal_headers)
    uid = None
    for booking in (listing or {}).get("data") or []:
        if str(booking.get("id")) == str(event_id):
            uid = booking.get("uid")
            break
    if not uid:
        return {"ok": False, "summary": f"booking {event_id} not found upcoming"}
    code, _ = http_json("POST", f"{CALCOM_BASE}/bookings/{uid}/cancel",
                        headers=cal_headers,
                        body={"cancellationReason": "edge test cleanup"})
    if code not in (200, 201):
        return {"ok": False, "summary": f"cancel failed: {code}"}
    return {"ok": True, "summary": f"booked + cancelled event_id={event_id}"}
