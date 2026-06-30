"""EDGE: deployed flow has the expected 15-node shape (regression for accidental node loss)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


EXPECTED = {
    "greet", "get_reason", "get_first_name", "get_last_name",
    "get_phone", "confirm_phone",
    "list_slots_call", "read_slots", "reroll_slots_call",
    "confirm_slot", "book_slot_call",
    "close", "end_success", "handoff", "end_handoff",
}


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow {code}"}
    actual = {n.get("id") for n in (f.get("nodes") or [])}
    missing = EXPECTED - actual
    extra = actual - EXPECTED
    if missing:
        return {"ok": False, "summary": f"missing: {missing}"}
    if extra:
        return {"ok": False, "summary": f"unexpected extra: {extra}"}
    return {"ok": True, "summary": f"{len(actual)} nodes match spec"}
