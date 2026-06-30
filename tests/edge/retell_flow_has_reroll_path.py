"""EDGE: deployed flow has a reroll_slots_call function node + read_slots edge to it.

Regression guard for the 2026-06-30 16:25 listen test: user said "Wednesday night"
and "Can we have a Thursday?" -- Lisa had no way to fetch alternative slots and
just repeated the same Wednesday morning list. Adding reroll path closes this.
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
    reroll = nodes.get("reroll_slots_call")
    if not reroll:
        return {"ok": False, "summary": "reroll_slots_call node missing"}
    if reroll.get("type") != "function":
        return {"ok": False, "summary": f"reroll_slots_call wrong type: {reroll.get('type')}"}
    if reroll.get("tool_id") != "list_slots":
        return {"ok": False, "summary": "reroll_slots_call not bound to list_slots"}
    read_slots = nodes.get("read_slots") or {}
    edge_targets = [e.get("destination_node_id") for e in read_slots.get("edges") or []]
    if "reroll_slots_call" not in edge_targets:
        return {"ok": False, "summary": "read_slots has no edge to reroll_slots_call"}
    return {"ok": True, "summary": "reroll path wired"}
