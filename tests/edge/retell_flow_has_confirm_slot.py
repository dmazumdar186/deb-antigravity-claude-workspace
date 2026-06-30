"""EDGE: deployed flow has confirm_slot conversation node between read_slots and book_slot_call.

Regression guard for the 2026-06-30 16:25 listen test: book_slot fired immediately
on "AM. Ten AM." without reading back the full datetime. Without this confirmation
step, a single misheard digit (e.g. "Ten" vs "Two") would silently book the wrong
appointment.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow {code}"}
    nodes = {n.get("id"): n for n in (f.get("nodes") or [])}
    confirm = nodes.get("confirm_slot")
    if not confirm:
        return {"ok": False, "summary": "confirm_slot node missing"}
    if confirm.get("type") != "conversation":
        return {"ok": False, "summary": f"confirm_slot wrong type: {confirm.get('type')}"}
    # read_slots must transition to confirm_slot for the chosen-slot path
    read = nodes.get("read_slots") or {}
    targets = [e.get("destination_node_id") for e in read.get("edges") or []]
    if "confirm_slot" not in targets:
        return {"ok": False, "summary": "read_slots does not transition to confirm_slot"}
    # confirm_slot must transition to book_slot_call on yes
    ctargets = [e.get("destination_node_id") for e in confirm.get("edges") or []]
    if "book_slot_call" not in ctargets:
        return {"ok": False, "summary": "confirm_slot does not transition to book_slot_call"}
    return {"ok": True, "summary": "read_slots -> confirm_slot -> book_slot_call wired"}
