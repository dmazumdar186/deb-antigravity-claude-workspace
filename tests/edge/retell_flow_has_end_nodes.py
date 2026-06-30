"""EDGE: deployed Retell flow has both end_success and end_handoff nodes wired.

Without these, the close conversation node loops the goodbye sentence rather than
hanging up (2026-06-30 13:20 production exhibit).
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
    if nodes.get("end_success", {}).get("type") != "end":
        return {"ok": False, "summary": "end_success node missing or wrong type"}
    if nodes.get("end_handoff", {}).get("type") != "end":
        return {"ok": False, "summary": "end_handoff node missing or wrong type"}
    close = nodes.get("close") or {}
    close_targets = [e.get("destination_node_id") for e in close.get("edges") or []]
    if "end_success" not in close_targets:
        return {"ok": False, "summary": "close does not transition to end_success"}
    handoff = nodes.get("handoff") or {}
    handoff_targets = [e.get("destination_node_id") for e in handoff.get("edges") or []]
    if "end_handoff" not in handoff_targets:
        return {"ok": False, "summary": "handoff does not transition to end_handoff"}
    return {"ok": True, "summary": "close->end_success + handoff->end_handoff wired"}
